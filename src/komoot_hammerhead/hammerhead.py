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
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            hh_token: str | None = None

            # Intercept the Hammerhead token exchange response
            async def capture_token(response):
                nonlocal hh_token
                if response.url.startswith(HH_TOKEN_URL):
                    try:
                        body = await response.json()
                        if "access_token" in body:
                            hh_token = body["access_token"]
                    except Exception:
                        pass

            page = await context.new_page()
            page.on("response", capture_token)

            # Step 1: Go to dashboard landing
            await page.goto(DASHBOARD_URL, wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # Step 1b: Dismiss the iubenda cookie consent banner if present
            # (appears on first visit in a fresh browser context / Docker)
            try:
                await page.evaluate("""
                    document.querySelectorAll(
                        '#iubenda-cs-banner, .iubenda-cs-container, ' +
                        '[id*="iubenda"], [class*="iubenda"]'
                    ).forEach(el => el.remove());
                """)
            except Exception:
                pass
            await asyncio.sleep(1)

            # Step 2: Click "Continue to Log in" (redirects to SRAM Auth0)
            await page.click("button.bg-sram")

            # Step 3: Wait for Auth0 Lock form and fill credentials
            email_input = await page.wait_for_selector(
                'input[name="email"]', timeout=30000
            )
            await email_input.fill(settings.hammerhead_email)
            pass_input = await page.wait_for_selector(
                'input[name="password"]', timeout=5000
            )
            await pass_input.fill(settings.hammerhead_password)

            # Step 4: Submit (Auth0 Lock uses Enter, not button click)
            await pass_input.press("Enter")

            # Step 5: Wait for redirect back to dashboard
            await page.wait_for_url(f"{DASHBOARD_URL}/**", timeout=45000)
            await asyncio.sleep(3)  # let token exchange complete

            # Fallback: read from localStorage
            if not hh_token:
                hh_token = await page.evaluate(
                    "localStorage.getItem('jwt:token')"
                )

            await browser.close()

        if not hh_token:
            raise RuntimeError(
                "Failed to extract Hammerhead JWT. "
                "Login selectors may have changed — inspect dashboard.hammerhead.io manually."
            )

        # Cache with 1-hour expiry (token expires_in is 3600s)
        expires = (datetime.now(timezone.utc) + timedelta(minutes=55)).isoformat()
        db.save_token(
            "hammerhead", hh_token, user_id=settings.hammerhead_user_id, expires_at=expires
        )
        log.info("Hammerhead: login OK, token cached")
        return hh_token

    def upload_gpx(self, name: str, gpx_bytes: bytes) -> str | None:
        """Upload a GPX file to Hammerhead and return the route ID."""
        token = self.ensure_auth()
        url = IMPORT_URL.format(user_id=settings.hammerhead_user_id)
        filename = f"{name}.gpx"

        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filename, gpx_bytes, "application/gpx+xml")},
            timeout=60,
        )

        if resp.status_code == 401:
            # Token expired — clear cache and retry once
            log.warning("Hammerhead: 401, clearing token cache and retrying...")
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
        # Response is a list of imported routes (one per GPX track)
        if isinstance(data, list) and data:
            route_id = data[0].get("id")
        elif isinstance(data, dict):
            route_id = data.get("id")
        else:
            route_id = None
        log.info("Hammerhead: uploaded '%s' -> route %s", name, route_id)
        return str(route_id) if route_id else None
