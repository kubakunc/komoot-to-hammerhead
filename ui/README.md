# Komoot → Hammerhead Sync UI

React-based web interface for syncing planned routes from Komoot to Hammerhead Karoo. Shows all your planned Komoot routes and lets you pick which ones to sync.

## Features

- Browse planned routes from Komoot (last N days)
- See which routes are already synced
- Multi-select routes and sync them in one click
- Live status indicators (syncing, synced, failed)
- Filter by sync status (all / unsynced / synced)
- Dark theme, responsive layout

## Setup

### Prerequisites

- Node.js ≥ 18
- The backend API server running (`komoot-hh serve`)

### Install & Run

```bash
cd ui
npm install

# Copy and edit env vars
cp .env .env.local
# Set VITE_API_KEY to match your API_SECRET from the backend .env

npm run dev
# → http://localhost:5173
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Backend API base URL |
| `VITE_API_KEY` | (empty) | Must match `API_SECRET` from backend `.env` |

### Build for Production

```bash
npm run build
# Output in dist/
```

## Project Structure

```
ui/
  src/
    api.js                API client (tours, sync, status)
    App.jsx               Main component (layout, state, sync logic)
    components/
      RouteCard.jsx       Individual route card with sport icons
      StatusBar.jsx       Stats bar (total, success, failed)
    index.css             Design system (dark theme, variables, animations)
    main.jsx              React entry point
  .env                    Environment config
  index.html              HTML shell
```
