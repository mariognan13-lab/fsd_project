# Traffic IQ

College project for viewing traffic and congestion around a city. The application consists of a Python/FastAPI backend and a Next.js frontend.

## Architecture

- **Backend**: FastAPI (Python) - all API routes, traffic providers, geocoding, Overpass queries
- **Frontend**: Next.js 16 with React 19 - responsive dashboard UI, map controls, forms
- **Map**: Folium (Python) generates HTML that Next.js renders in an iframe
- **Data**: OpenStreetMap Overpass (toll plazas, eateries), HERE Traffic API v7 or TomTom Traffic Flow (live flow), Nominatim (geocoding)
- **Deployment**: Railway

## Frontend (Next.js)

The frontend is in `frontend/` and provides a responsive, clean UI:

- **Page**: `frontend/src/app/page.tsx` - Main dashboard with form for origin/destination, radius controls, layer toggles (traffic/tolls/places), and route planning
- **API Routes**: `frontend/src/app/api/route.ts` - Proxies to FastAPI backend:
  - `/api/traffic?bbox=...` - Traffic data
  - `/api/summary?bbox=...` - Traffic summary
  - `/api/config/public` - Public configuration
  - `/api/health` - Liveness probe
  - `/api/geocode?q=...` - Geocoding search
  - `/api/places/nearby?lat=...&lng=...&radius=...` - Nearby eateries
  - `/api/route?origin=...&destination=...` - Driving route

- **UI Features**:
  - Modern responsive layout with sidebar form and map area
  - Location input with autocomplete suggestions
  - Traffic, toll plaza, and eatery layer toggles
  - Route planning between origin and destination
  - Area traffic summary with distribution
  - Nearby eateries list

- **Build**: `npm run build` (output to `frontend/out`)
- **Development**: `npm run dev` (uses Turbopack)

## Backend (FastAPI)

- **Entry point**: `api/app/main.py` - Creates the FastAPI app with all routes
- **Key routes**:
  - `GET /` - Serves Next.js frontend HTML (or falls back to Folium template)
  - `GET /api/config/public` - Public config for frontend
  - `GET /api/health` - Liveness probe
  - `GET /api/health/data-sources` - Data source status
  - `GET /api/traffic?bbox=...` - Traffic flow data
  - `GET /api/traffic/segment/{segment_id}` - Segment details
  - `GET /api/summary?bbox=...` - Traffic summary
  - `GET /api/tolls?bbox=...` - Toll plazas
  - `GET /api/places/nearby?lat=...&lng=...&radius=...&category=...` - Nearby eateries
  - `GET /api/geocode?q=...` - Geocoding search
  - `GET /api/geocode/reverse?lat=...&lng=...` - Reverse geocoding
  - `GET /api/saved/places` - List saved places
  - `POST /api/saved/places` - Save a place
  - `DELETE /api/saved/places/{place_id}` - Delete a place
  - `GET /api/saved/corridors` - List saved corridors
  - `POST /api/saved/corridors` - Save a corridor

- **Configuration** (via environment variables):
  - `TRAFFIC_PROVIDER` - `here` or `tomtom` (both implement live flow)
  - `TRAFFIC_API_KEY` - Required for live HERE traffic
  - `TOMTOM_API_KEY` - Required for live TomTom traffic (falls back to `TRAFFIC_API_KEY`); `TOMTOM_ZOOM` and `TOMTOM_GRID` tune coverage
  - `MONGODB_URI` - Optional, needed for saving places
  - `SIMULATE_TRAFFIC` - Defaults to `true`; when no live traffic key is configured, deterministic seed traffic is rendered so the map remains useful. Set to `false` to preserve the not-configured response.

  - `OVERPASS_URLS` - Overpass API endpoints
  - `NOMINATIM_BASE_URL` - Nominatim geocoding endpoint
  - `HERE_API_BASE_URL` - HERE Traffic API base URL
  - Defaults for port, location, zoom, etc.

## Deployment (Render)

The repository includes a Render Blueprint in `render.yaml` for two web services:

- `trafficiq-api`: FastAPI backend with `/api/health` as its health check.
- `trafficiq-web`: Next.js frontend, proxying API requests to the backend.

Deploy from the Render dashboard by selecting **New → Blueprint** and connecting this repository, or with the Render CLI if it is installed and authenticated. Render will prompt for the secret `TOMTOM_API_KEY`; `MONGODB_URI` is optional. `SIMULATE_TRAFFIC=true` keeps deterministic traffic available when no live key is configured.

After deployment, set `CLIENT_ORIGIN` on `trafficiq-api` to the public `trafficiq-web` URL if Render does not resolve the service reference automatically.


## Run Locally

### Option 1: All-in-One Script (Recommended)

Run both backend and frontend concurrently with automatic setup:

```bash
chmod +x run-local.sh
./run-local.sh
```

You can also run individual services using flags:
```bash
./run-local.sh --backend    # Run only FastAPI backend (http://localhost:5050)
./run-local.sh --frontend   # Run only Next.js frontend (http://localhost:3000)
```

### Option 2: Individual Scripts

In separate terminals:

```bash
# Terminal 1: Backend
./scripts/run-backend.sh

# Terminal 2: Frontend
./scripts/run-frontend.sh
```

### Option 3: Manual Steps

```bash
# 1. Set up backend
cp .env.example .env
python3 -m venv api/.venv
source api/.venv/bin/activate  # On Windows Git Bash: source api/.venv/Scripts/activate
pip install -r api/requirements.txt
uvicorn app.main:app --app-dir api --port 5050 --reload

# 2. Set up frontend (in separate terminal)
cd frontend
npm install
npm run dev
```

- Frontend UI: http://localhost:3000
- Backend API & Docs: http://localhost:5050 and http://localhost:5050/docs


## Tests

```bash
api/.venv/bin/pytest api/tests
```

All 8 tests pass.

## Environment Variables That Matter

- `TRAFFIC_API_KEY` - Required for live traffic. Without it, the map, search, tolls, and eateries still work, but traffic shows as "not configured"
- `MONGODB_URI` - Optional. Saving a place needs MongoDB. The map does not.
- `NOMINATIM_USER_AGENT` - Should identify this project
- `MAX_BBOX_SPAN_DEGREES` - Defaults to `0.22`. The page requests a smaller area around the search point.
- `SERVE_CLIENT` - Set to `"true"` if you want the backend to also serve the Next.js dev client

## Congestion Colors

HERE `jamFactor` runs from 0 to 10. This project treats:
- Below 3 as free-flow
- Below 5 as light
- Below 8 as moderate
- 8 or above as heavy

If jam factor is missing, the page uses observed speed divided by free-flow speed:
- Below 0.40 heavy
- Below 0.65 moderate
- Below 0.85 light
- Otherwise free-flow

Missing values stay unknown. These cuts are project settings, not a HERE standard.

## Limits

- A road with no color was not returned by the traffic provider for this view
- Average speed uses realtime and historical observations only
- Delay is estimated from length and the two speeds when both are present. Left blank when a speed is missing or zero
- TomTom: the standard key only exposes the point-based flow API, so a bounding box is sampled on a `TOMTOM_GRID` × `TOMTOM_GRID` grid of points and segments are de-duplicated (no street names; congestion uses the speed ratio)
- Public Overpass can be slow or busy. The page shows that error instead of invented places