# Implementation Plan

## Overview

Repair the Traffic IQ repository so the backend and frontend build and run locally with a valid dashboard, a single Mapbox/Folium map implementation, and simulated traffic retained in API responses but excluded from visual traffic overlays.

The current working tree contains malformed duplicate edits in the dashboard, Mapbox component, and Render Blueprint. The implementation will restore source integrity, align local proxy/configuration behavior, update documentation, and validate with Python tests, TypeScript/Next.js build checks, and Git whitespace checks. No commit, push, deployment, or token insertion is part of this plan.

## Types

- Retain a typed frontend traffic feature containing `geometry`, optional `congestionLevel`, and optional `simulated`; use GeoJSON `FeatureCollection` data for Mapbox sources.
- Use typed overlay color properties derived from congestion levels with an explicit unknown fallback.
- Preserve backend traffic fields including `simulated`, `observationBasis`, `source`, and `coverageNote`.
- Do not change public API schemas or query parameters.

## Files

### Existing files to modify

- `d:\Projects2\fsd_project\api\app\dashboard.py`: remove duplicated/empty toll loops, restore one toll-marker loop, preserve route/marker/place behavior, and ensure Folium traffic lines use `_visible_traffic_features()`.
- `d:\Projects2\fsd_project\api\tests\test_api.py`: retain one deterministic seed test, one simulated-overlay exclusion test, and the existing simulated API response test; remove malformed duplicates.
- `d:\Projects2\fsd_project\frontend\src\components\MapContainer.tsx`: replace concatenated implementations with one client-only Mapbox component, Streets style, prominent coordinate marker, real-traffic filtering, safe source/layer cleanup, and Folium iframe fallback.
- `d:\Projects2\fsd_project\frontend\package.json`: confirm `mapbox-gl` is declared only in the frontend package.
- `d:\Projects2\fsd_project\frontend\package-lock.json`: keep lockfile synchronized if dependency metadata requires it.
- `d:\Projects2\fsd_project\render.yaml`: restore exactly `trafficiq-api` and `trafficiq-web`; keep `NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN` only on the web service with `sync: false`; remove duplicate/incomplete environment entries.
- `d:\Projects2\fsd_project\README.md`: deduplicate Mapbox documentation, correct the test claim, add Windows commands, and document that simulated traffic is not drawn as an overlay.
- `d:\Projects2\fsd_project\.env.example`: optionally add an empty/commented local Mapbox variable, never a token, and keep local proxy URLs consistent.

### New files

- `d:\Projects2\fsd_project\implementation_plan.md`: this implementation plan.

### Files not to modify

- No credentials, Mapbox token, generated `.next`, `node_modules`, virtual-environment files, deployment state, provider replacement, or API redesign.

## Functions

### Modified functions

- `render_dashboard(bundle, params)` in `d:\Projects2\fsd_project\api\app\dashboard.py`: repair only the malformed toll-marker section and verify simulated features remain excluded from Folium traffic lines.
- `_visible_traffic_features(features)` in the same file: preserve its contract of returning only non-simulated features.
- `MapContainer({ params })` in `d:\Projects2\fsd_project\frontend\src\components\MapContainer.tsx`: consolidate map lifecycle, marker, overlay loading, request abort, and cleanup behavior.

### New functions

- No backend functions are required. Small local frontend helpers for coordinate parsing, congestion colors, or GeoJSON conversion may be added only if they improve clarity.

### Removed functions

- Remove duplicate anonymous MapContainer implementations; retain one exported component.

## Classes

No new, removed, or replaced classes are required. Existing provider/service classes, including `SeedTrafficProvider`, `TrafficService`, and the application factory, remain unchanged unless validation reveals a directly related defect.

## Dependencies

- Keep existing Next.js, React, TypeScript, Tailwind, and `mapbox-gl` versions.
- Do not introduce another mapping library or runtime dependency.
- Confirm `mapbox-gl` is represented consistently in `frontend/package.json` and `frontend/package-lock.json`.
- Keep backend dependencies from `api/requirements.txt`.

## Testing

1. Compile `api/app/dashboard.py` and `api/tests/test_api.py`.
2. Run `d:\Projects2\fsd_project\api\.venv\Scripts\python.exe -m pytest -q api/tests` on Windows.
3. Run `npm run build` in `d:\Projects2\fsd_project\frontend`.
4. Run `git diff --check` and inspect status/diff for duplicate fragments, secrets, and generated artifacts.
5. Validate Render YAML structure and service/env-var placement.
6. Smoke-test the backend at `http://localhost:5050`, frontend at `http://localhost:3000`, `/api/health`, the no-token Folium fallback, and the Mapbox path only when a developer supplies an untracked local token.
7. Do not require live provider credentials for the local build; simulated API data must remain labeled and invisible as road overlays.

## Implementation Order

1. Preserve and inspect unrelated working-tree changes; do not reset them.
2. Repair `api/app/dashboard.py` and `api/tests/test_api.py`.
3. Replace `frontend/src/components/MapContainer.tsx` with one clean implementation.
4. Verify frontend dependency and lockfile consistency.
5. Normalize `render.yaml` into two valid services.
6. Deduplicate README and local environment instructions.
7. Run Python compilation and backend tests; fix cleanup-related failures.
8. Run the frontend build and resolve TypeScript, CSS, Next.js, or Mapbox errors.
9. Run `git diff --check`, inspect the final diff/status, and verify no secrets/generated artifacts were added.
10. Report local build/test results and limitations; do not commit, push, or deploy without a separate request.
