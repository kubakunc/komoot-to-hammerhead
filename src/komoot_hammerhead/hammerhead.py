from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from playwright.async_api import async_playwright

from . import db
from .config import settings

log = logging.getLogger(__name__)

DASHBOARD_URL = "https://dashboard.hammerhead.io"
HH_TOKEN_URL = "https://dashboard.hammerhead.io/v1/auth/sram/mobile/token"
IMPORT_URL = "https://dashboard.hammerhead.io/v1/users/{user_id}/routes/import/file"


class HammerheadClient:
    def __init__(self) -> None:
        self._token: str | None = None

    def ensure_auth(self) -> str:
        """Return a valid JWT, refreshing via Playwright if needed."""
        if self._token:
            return self._token
        cached = db.get_cached_token("hammerhead")
        if cached:
            self._token = cached[0]
            return self._token
        # Need a fresh browser login
        loop = asyncio.new_event_loop()
        try:
            self._token = loop.run_until_complete(self._playwright_login())
        finally:
            loop.close()
        return self._token

    async def _playwright_login(self) -> str:
        """Launch headless browser, complete SRAM/Auth0 login, extract JWT."""
        log.info("Hammerhead: launching browser for SRAM login...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )

            # Hide automation traits
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            hh_token: str | None = None

            # Intercept the Hammerhead token exchange response
            async def capture_token(response):
                nonlocal hh_token
                if response.url.startswith(HH_TOKEN_URL):
                    try:
                        body = await response.json()
                        if "access_token" in body:
                            hh_token = body["access_token"]
                            log.info("Hammerhead: intercepted access token")
                    except Exception:
                        pass

            page = await context.new_page()
            
            page.on("console", lambda msg: log.debug(f"Hammerhead Browser Console: {msg.type}: {msg.text}"))
            page.on("pageerror", lambda err: log.error(f"Hammerhead Browser Page Error: {err.message}"))
            page.on("response", capture_token)

            # Step 1: Go to dashboard landing
            log.info("Hammerhead: navigating to %s", DASHBOARD_URL)
            try:
                await page.goto(DASHBOARD_URL, wait_until="load", timeout=90000)
                log.info("Hammerhead: page load event fired")
            except Exception as e:
                log.warning("Hammerhead: page load timed out or failed: %s", e)

            # Wait for SPA hydration
            try:
                await page.wait_for_selector("#root > *", timeout=15000)
                log.info("Hammerhead: SPA hydrated")
            except Exception:
                log.warning("Hammerhead: hydration check timed out")

            await asyncio.sleep(3) 

            # Step 1b: Dismiss Cookie Banners and Overlays
            log.info("Hammerhead: removing overlays via JS...")
            await page.evaluate("""() => {
                const selectors = [
                    '#iubenda-cs-banner', '.iubenda-cs-container', '.iubenda-cs-overlay',
                    '.MuiBackdrop-root', '[class*="backdrop"]', '[class*="overlay"]',
                    '.MuiDialog-root', '[role="presentation"]'
                ];
                selectors.forEach(s => {
                    document.querySelectorAll(s).forEach(el => {
                        // Only remove if it's broad or seems like a backdrop
                        if (el.classList.contains('MuiBackdrop-root') || el.style.position === 'fixed' || getComputedStyle(el).position === 'fixed') {
                            el.remove();
                        }
                    });
                });
                document.body.style.overflow = 'auto';
                document.documentElement.style.pointerEvents = 'auto';
                document.body.style.pointerEvents = 'auto';
            }""")

            # Step 2: Click Login Button
            log.info("Hammerhead: triggering login click...")
            login_selectors = [
                "button.bg-sram",
                "button.btn-sram",
                "button:has-text('Log in')",
                "button:has-text('Continue')",
                "a:has-text('Log in')"
            ]
            
            # We'll try to click via JS first as it's more reliable for elements inside complex modals
            success = False
            for selector in login_selectors:
                try:
                    # Wait for element presence
                    el = await page.wait_for_selector(selector, timeout=5000)
                    if el:
                        log.info("Hammerhead: found login button via '%s', clicking via JS", selector)
                        # Direct JS click bypasses pointer-event interception and stability checks
                        await page.evaluate("(sel) => { const el = document.querySelector(sel); if(el) el.click(); }", selector)
                        success = True
                        break
                except Exception:
                    continue
            
            if not success:
                # Last resort: try clicking the first button that looks like a login button
                try:
                    await page.evaluate("""() => {
                        const btns = Array.from(document.querySelectorAll('button'));
                        const loginBtn = btns.find(b => b.innerText.toLowerCase().includes('log in') || b.innerText.toLowerCase().includes('continue'));
                        if (loginBtn) loginBtn.click();
                    }""")
                    log.info("Hammerhead: attempted generic JS click on suspected login button")
                except Exception:
                    pass

            # Step 3: Wait for Auth0 login page
            log.info("Hammerhead: waiting for Auth0 form...")
            try:
                # We wait specifically for the Auth0 email input
                email_input = await page.wait_for_selector('input[name="email"]', timeout=45000)
                log.info("Hammerhead: Auth0 login page reached")
                await email_input.fill(settings.hammerhead_email)
                pass_input = await page.wait_for_selector('input[name="password"]', timeout=10000)
                await pass_input.fill(settings.hammerhead_password)
                log.info("Hammerhead: submitting credentials...")
                await pass_input.press("Enter")
            except Exception as e:
                await page.screenshot(path="/data/hammerhead_auth0_fail.png")
                # Also log the current URL to see where we are
                log.error("Hammerhead: failed at Auth0 step. Current URL: %s", page.url)
                raise e

            # Step 5: Wait for success redirect
            log.info("Hammerhead: waiting for final redirect...")
            try:
                await page.wait_for_url(f"{DASHBOARD_URL}/**", timeout=60000)
                log.info("Hammerhead: redirect complete")
            except Exception:
                if not hh_token:
                    await page.screenshot(path="/data/hammerhead_redirect_fail.png")
                    raise RuntimeError("Timeout waiting for dashboard after Auth0 login")

            await asyncio.sleep(5) 

            if not hh_token:
                hh_token = await page.evaluate("localStorage.getItem('jwt:token')")
                if hh_token:
                    log.info("Hammerhead: extracted token from localStorage")

            await browser.close()

        if not hh_token:
            raise RuntimeError("Failed to extract Hammerhead JWT. Verify credentials and dashboard flow.")

        # Cache token
        expires = (datetime.now(timezone.utc) + timedelta(minutes=55)).isoformat()
        db.save_token("hammerhead", hh_token, user_id=settings.hammerhead_user_id, expires_at=expires)
        log.info("Hammerhead: login successful, token cached")
        return hh_token

    def upload_gpx(self, name: str, gpx_bytes: bytes) -> str | None:
        """Upload a GPX file to Hammerhead and return the route ID."""
        token = self.ensure_auth()
        url = IMPORT_URL.format(user_id=settings.hammerhead_user_id)
        filename = f"{name}.gpx"

        log.info("Hammerhead: uploading GPX '%s'...", name)
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filename, gpx_bytes, "application/gpx+xml")},
            timeout=60,
        )

        if resp.status_code == 401:
            log.warning("Hammerhead: 401, re-authenticating...")
            self._token = None
            db.save_token("hammerhead", "", expires_at="2000-01-01T00:00:00+00:00")
            token = self.ensure_auth()
            resp = httpx.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                files={"file": (filename, gpx_bytes, "application/gpx+xml")},
                timeout=60,
            )

        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            route_id = data[0].get("id")
        elif isinstance(data, dict):
            route_id = data.get("id")
        else:
            route_id = None
        log.info("Hammerhead: uploaded '%s' -> route %s", name, route_id)
        return str(route_id) if route_id else None
