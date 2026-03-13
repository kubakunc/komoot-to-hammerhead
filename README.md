# Komoot → Hammerhead Route Sync

Automatically syncs planned routes from Komoot to Hammerhead Karoo, bypassing the Premium paywall introduced after the Bending Spoons acquisition.

Runs as a **CLI** for one-off syncs or as a **web API** for on-demand triggering (e.g. from a shortcut, webhook, or cron).

## How It Works

1. Logs into Komoot via [KomootGPX](https://github.com/timschneeb/KomootGPX), fetches planned routes from the last N days
2. Logs into Hammerhead via headless Chromium (Playwright) through the SRAM/Auth0 flow
3. Downloads each route as GPX (including highlights/waypoints)
4. Uploads GPX to the Hammerhead dashboard API
5. Tracks sync state in a local SQLite database to avoid duplicates

## Setup

### Docker (recommended)

```bash
cp .env.example .env
# Edit .env with your credentials

# Run with docker compose
docker compose up -d

# Or build and run directly
docker build -t komoot-hh .
docker run -d -p 8000:8000 --env-file .env -v komoot-data:/data komoot-hh
```

The container bundles Python, Playwright, and Chromium -- no local dependencies needed.

### Local

```bash
uv venv --python 3.13
uv pip install -e .
playwright install chromium

cp .env.example .env
# Edit .env with your credentials
```

## Configuration

All settings are loaded from `.env` (or environment variables):

| Variable | Required | Default | Description |
|---|---|---|---|
| `KOMOOT_EMAIL` | Yes | | Komoot account email |
| `KOMOOT_PASSWORD` | Yes | | Komoot account password |
| `HAMMERHEAD_EMAIL` | Yes | | Hammerhead/SRAM account email |
| `HAMMERHEAD_PASSWORD` | Yes | | Hammerhead/SRAM account password |
| `HAMMERHEAD_USER_ID` | Yes | | Your Hammerhead user ID (from JWT `sub` claim) |
| `API_SECRET` | Yes | | Shared secret for API authentication |
| `DB_PATH` | No | `./komoot_hammerhead.db` | SQLite database path |
| `KOMOOT_TOUR_TYPE` | No | `tour_planned` | Tour type filter (`tour_planned`, `tour_recorded`, `tour_all`) |
| `SYNC_DAYS` | No | `3` | Only sync routes created/modified within this many days |

### Finding your Hammerhead User ID

Log into [dashboard.hammerhead.io](https://dashboard.hammerhead.io), open browser DevTools, and look in localStorage for `jwt:token`. Decode the JWT at [jwt.io](https://jwt.io) -- the `sub` field is your user ID.

## CLI Usage

```bash
# Sync all new planned routes (last SYNC_DAYS days)
komoot-hh sync

# Sync a specific tour by Komoot tour ID
komoot-hh sync --tour-id 2825652918

# Show sync statistics
komoot-hh status

# Start the web API server
komoot-hh serve
komoot-hh serve --host 127.0.0.1 --port 9000

# Verbose output
komoot-hh -v sync
```

## API Usage

Start the server:

```bash
komoot-hh serve
# → Uvicorn running on http://0.0.0.0:8000
```

All endpoints require the `X-API-Key` header matching your `API_SECRET` env var.

### Endpoints

#### `POST /sync` -- Sync all new routes

Fetches planned routes from Komoot created in the last `SYNC_DAYS`, skips already-synced ones, uploads the rest to Hammerhead.

```bash
curl -X POST http://localhost:8000/sync \
  -H "X-API-Key: your_api_secret"
```

```json
{
  "synced": 3,
  "skipped": 91,
  "failed": 0,
  "errors": []
}
```

#### `POST /sync/{tour_id}` -- Sync a single route

Downloads and uploads a specific Komoot tour by ID. Skips if already synced.

```bash
curl -X POST http://localhost:8000/sync/2825652918 \
  -H "X-API-Key: your_api_secret"
```

```json
{
  "synced": 1,
  "skipped": 0,
  "failed": 0,
  "errors": []
}
```

#### `GET /status` -- Sync statistics

```bash
curl http://localhost:8000/status \
  -H "X-API-Key: your_api_secret"
```

```json
{
  "total": 94,
  "success": 94,
  "failed": 0
}
```

#### `GET /routes` -- List synced routes

Returns synced routes, most recent first. Supports pagination.

```bash
curl "http://localhost:8000/routes?limit=2&offset=0" \
  -H "X-API-Key: your_api_secret"
```

```json
[
  {
    "komoot_tour_id": "862296556",
    "name": "Srodmiescie → Warszawa",
    "sport_type": "touringbicycle",
    "distance_km": 7.84,
    "hammerhead_id": "131560.route.a6815f13-cba3-451f-a06b-bcde7296dc42",
    "synced_at": "2026-03-13T18:51:47.597474+00:00",
    "status": "success"
  }
]
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 50 | Max routes to return (1-500) |
| `offset` | int | 0 | Pagination offset |

#### `GET /routes/{tour_id}` -- Get a single route

```bash
curl http://localhost:8000/routes/2825652918 \
  -H "X-API-Key: your_api_secret"
```

```json
{
  "komoot_tour_id": "2825652918",
  "name": "Kolarstwo szosowe do: Rezerwat Przyrody Wyspy Swiderskie",
  "sport_type": "racebike",
  "distance_km": 85.23,
  "hammerhead_id": "131560.route.086fcd37-77b0-4175-a3cd-16082f3fd72b",
  "synced_at": "2026-03-13T18:44:22.123456+00:00",
  "status": "success"
}
```

Returns `404` if the route has not been synced.

#### `PATCH /routes/{tour_id}` -- Update a route

Updates mutable fields of a synced route record. Only provided fields are changed.

```bash
curl -X PATCH http://localhost:8000/routes/2825652918 \
  -H "X-API-Key: your_api_secret" \
  -H "Content-Type: application/json" \
  -d '{"name": "Sunday morning ride", "status": "success"}'
```

```json
{
  "komoot_tour_id": "2825652918",
  "name": "Sunday morning ride",
  "sport_type": "racebike",
  "distance_km": 85.23,
  "hammerhead_id": "131560.route.086fcd37-77b0-4175-a3cd-16082f3fd72b",
  "synced_at": "2026-03-13T18:44:22.123456+00:00",
  "status": "success"
}
```

Updatable fields: `name`, `sport_type`, `distance_km`, `hammerhead_id`, `status`.

#### `DELETE /routes/{tour_id}` -- Delete a route

Removes a synced route record from the local database. Does **not** delete the route from Hammerhead. Useful for re-triggering a sync for a specific tour.

```bash
curl -X DELETE http://localhost:8000/routes/2825652918 \
  -H "X-API-Key: your_api_secret"
```

```json
{
  "deleted": true
}
```

Returns `404` if the route was not found.

### Interactive Docs

When the server is running, Swagger UI is available at:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

## Web UI

A React-based dashboard for browsing and selectively syncing routes. Requires the API server to be running.

```bash
# Terminal 1: start the API
komoot-hh serve

# Terminal 2: start the UI
cd ui
npm install
cp .env .env.local   # set VITE_API_KEY to match your API_SECRET
npm run dev
# → http://localhost:5173
```

See [`ui/README.md`](ui/README.md) for full details.

## Architecture

```
src/komoot_hammerhead/
  config.py       Pydantic-settings, loads from .env
  db.py           SQLite: synced_routes + auth_cache tables
  komoot.py       KomootGPX wrapper: login, list tours, download GPX
  hammerhead.py   Playwright SRAM login + httpx GPX upload
  sync.py         Orchestrator: komoot → filter → hammerhead → db
  cli.py          Click CLI: sync, status, serve
  server.py       FastAPI: full CRUD + sync endpoints
```

### Auth Flow

**Komoot**: Email/password via KomootGPX library (HTTP Basic Auth to `api.komoot.de`).

**Hammerhead**: Three-step browser automation:
1. Navigate to `dashboard.hammerhead.io/landing`
2. Click "Continue to Log in" -> redirects to SRAM Auth0 (`sramid-auth.sram.com`)
3. Fill email/password in Auth0 Lock widget, submit
4. Intercept the JWT from the `dashboard.hammerhead.io/v1/auth/sram/mobile/token` response

Both tokens are cached in SQLite (`auth_cache` table). The Hammerhead JWT expires after ~1 hour and is automatically refreshed.

### Database

SQLite with two tables:

**`synced_routes`** -- tracks which Komoot tours have been uploaded to Hammerhead:
| Column | Type | Description |
|---|---|---|
| `komoot_tour_id` | TEXT PK | Komoot tour ID |
| `name` | TEXT | Route name |
| `sport_type` | TEXT | e.g. `racebike`, `touringbicycle` |
| `distance_km` | REAL | Distance in km |
| `hammerhead_id` | TEXT | Hammerhead route ID after upload |
| `synced_at` | TEXT | ISO 8601 timestamp |
| `status` | TEXT | `success` or `failed` |

**`auth_cache`** -- cached auth tokens to avoid repeated logins:
| Column | Type | Description |
|---|---|---|
| `service` | TEXT PK | `komoot` or `hammerhead` |
| `token` | TEXT | Auth token / JWT |
| `user_id` | TEXT | User ID for the service |
| `expires_at` | TEXT | ISO 8601 expiry (NULL if unknown) |
