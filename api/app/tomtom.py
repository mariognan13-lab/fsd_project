import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode

from .congestion import classify_flow, observation_basis
from .errors import AppError, map_upstream_error
from .geo import haversine_meters
from .here import TRAFFIC_UNITS, _estimate_delay

TOMTOM_ATTRIBUTION = "Traffic data © TomTom"
# Only the point-based flowSegmentData (service v4) is available on the standard
# TomTom key, so a bounding box is sampled on a N x N grid of points and the
# returned segments are de-duplicated.
DEFAULT_GRID = 3


def _finite(value):
    return value if isinstance(value, (int, float)) and value == value else None


def _points_to_line(points):
    """TomTom returns [{'latitude', 'longitude'}, ...]; emit [lng, lat] pairs."""
    if not isinstance(points, list):
        return []
    coordinates = []
    for point in points:
        if not isinstance(point, dict):
            continue
        lat = point.get("latitude")
        lng = point.get("longitude")
        if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            continue
        nxt = [lng, lat]
        if coordinates and coordinates[-1] == nxt:
            continue
        coordinates.append(nxt)
    return coordinates if len(coordinates) >= 2 else []


def _segment_length(coordinates):
    total = 0.0
    for index in range(1, len(coordinates)):
        prev = {"lat": coordinates[index - 1][1], "lng": coordinates[index - 1][0]}
        curr = {"lat": coordinates[index][1], "lng": coordinates[index][0]}
        total += haversine_meters(prev, curr)
    return round(total) if total else None


def _segment_id(first, last, speed):
    raw = "|".join([
        ",".join(str(value) for value in first),
        ",".join(str(value) for value in last),
        str(speed),
    ])
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _confidence_to_unit(value):
    """TomTom has used both 0-1 and 0-10 confidence scales; normalize to 0-1."""
    number = _finite(value)
    if number is None:
        return None
    return number / 10 if number > 1 else number


def _build_feature(coordinates, observed, free_flow, confidence, closed, thresholds, frc=None):
    if not coordinates or len(coordinates) < 2:
        return None
    length = _segment_length(coordinates)
    observed_mps = observed / 3.6 if isinstance(observed, (int, float)) and observed > 0 else None
    free_mps = free_flow / 3.6 if isinstance(free_flow, (int, float)) and free_flow > 0 else None
    delay = _estimate_delay(length, observed_mps, free_mps)
    confidence_unit = _confidence_to_unit(confidence)
    classification = classify_flow(
        {
            "jamFactor": None,
            "observedSpeed": observed,
            "freeFlowSpeed": free_flow,
            "traversability": "closed" if closed else "open",
        },
        thresholds,
    )
    return {
        "id": _segment_id(coordinates[0], coordinates[-1], observed),
        "name": None,
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "observedSpeed": _finite(observed),
        "freeFlowSpeed": _finite(free_flow),
        "delay": delay,
        "delayEstimated": delay is not None,
        "congestionLevel": classification["congestionLevel"],
        "congestionMethod": classification["congestionMethod"],
        "speedRatio": classification["speedRatio"],
        "observedAt": None,
        "lengthMeters": length,
        "jamFactor": None,
        "confidence": confidence_unit,
        "observationBasis": observation_basis(confidence_unit),
        "roadStatus": "closed" if closed else "open",
        "subSegmentCount": None,
        "functionalClass": _frc_to_number(frc),
        "provider": "tomtom",
    }


def _frc_to_number(frc):
    if isinstance(frc, str) and frc.upper().startswith("FRC"):
        digits = "".join(ch for ch in frc if ch.isdigit())
        if digits:
            return int(digits)
    return None


def _at(values, index):
    if isinstance(values, list) and index < len(values):
        return values[index]
    return None


def _feature_from_single(data, thresholds):
    if not isinstance(data, dict):
        return None
    raw_coords = ((data.get("coordinates") or {}).get("coordinate")) or []
    points = [{"latitude": c.get("latitude"), "longitude": c.get("longitude")} for c in raw_coords if isinstance(c, dict)]
    return _build_feature(
        _points_to_line(points),
        data.get("currentSpeed"),
        data.get("freeFlowSpeed"),
        data.get("confidence"),
        bool(data.get("roadClosure")),
        thresholds,
        data.get("frc"),
    )


def normalize_tomtom_flow(payload, thresholds):
    """Supports both the point shape ({'flowSegmentData': {...}}) and the
    denormalized multi-segment shape ({'flowSegments': {...}, 'locations': [...]})."""
    features = []
    omitted = 0
    if not isinstance(payload, dict):
        payload = {}

    locations = payload.get("locations") or []
    segments = payload.get("flowSegments") or {}
    if locations:
        current = segments.get("currentFlowSpeed") or []
        freeflow = segments.get("freeFlowSpeed") or []
        confidence = segments.get("currentConfidence") or segments.get("confidence") or []
        closed = segments.get("roadClosed") or []
        for index, location in enumerate(locations):
            feature = _build_feature(
                _points_to_line((location or {}).get("points")),
                _at(current, index),
                _at(freeflow, index),
                _at(confidence, index),
                bool(_at(closed, index)),
                thresholds,
            )
            if feature:
                features.append(feature)
            else:
                omitted += 1
    elif payload.get("flowSegmentData"):
        feature = _feature_from_single(payload["flowSegmentData"], thresholds)
        if feature:
            features.append(feature)
        else:
            omitted += 1

    return {
        "source": "tomtom",
        "observedAt": None,
        "features": features,
        "omittedCount": omitted,
        "units": TRAFFIC_UNITS,
        "attribution": TOMTOM_ATTRIBUTION,
    }


class TomTomTrafficProvider:
    """TomTom Traffic Flow. The standard key only exposes the point-based
    flowSegmentData (service v4), so a bounding box is sampled on a grid of
    points and the returned segments are de-duplicated. Speeds are in km/h."""

    def __init__(self, http, api_key, base_url, version, zoom, timeout_ms, thresholds, grid=DEFAULT_GRID):
        self.http = http
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.version = str(version or "4")
        self.zoom = zoom
        self.timeout = timeout_ms / 1000
        # Bound each grid call well below the global timeout: 9 sequential
        # 20 s calls could otherwise stall a worker for minutes. Parallel + capped
        # keeps the whole fetch to roughly one slow call.
        self.call_timeout = min(self.timeout, 8)
        self.thresholds = thresholds
        self.grid = max(2, min(int(grid or DEFAULT_GRID), 5))
        self.id = "tomtom"

    def _fetch_feature(self, lat, lng):
        query = urlencode({"key": self.api_key, "point": f"{lat:.6f},{lng:.6f}", "unit": "kmph"})
        url = f"{self.base_url}/{self.version}/flowSegmentData/absolute/{self.zoom}/json?{query}"
        try:
            payload = self.http.get(url, timeout=self.call_timeout)
        except AppError:
            raise
        except Exception as error:
            mapped = map_upstream_error(error, "TomTom Traffic API")
            # Credentials/quota problems must surface rather than return an empty map.
            if mapped.code in {"UPSTREAM_UNAUTHORIZED", "UPSTREAM_RATE_LIMIT"}:
                raise mapped from None
            return None
        return _feature_from_single((payload or {}).get("flowSegmentData"), self.thresholds)

    def fetch_flow(self, bbox):
        if not self.api_key:
            raise AppError(
                "TomTom API key is not configured. Set TOMTOM_API_KEY (or TRAFFIC_API_KEY) in the server environment and restart the API.",
                status=503,
                code="NOT_CONFIGURED",
            )
        west, south, east, north = bbox["west"], bbox["south"], bbox["east"], bbox["north"]
        step_lng = (east - west) / self.grid
        step_lat = (north - south) / self.grid

        points = [
            (south + step_lat * (row + 0.5), west + step_lng * (col + 0.5))
            for row in range(self.grid)
            for col in range(self.grid)
        ]

        features = []
        seen = set()
        omitted = 0
        # Fetch the grid points concurrently (httpx.Client is thread-safe). A
        # per-point failure is skipped; auth/quota errors still surface.
        with ThreadPoolExecutor(max_workers=max(1, min(len(points), 6))) as pool:
            futures = [pool.submit(self._fetch_feature, lat, lng) for lat, lng in points]
            for future in as_completed(futures):
                try:
                    feature = future.result()
                except AppError:
                    raise
                except Exception:
                    omitted += 1
                    continue
                if not feature:
                    omitted += 1
                    continue
                if feature["id"] in seen:
                    continue
                seen.add(feature["id"])
                features.append(feature)

        return {
            "source": "tomtom",
            "observedAt": None,
            "features": features,
            "omittedCount": omitted,
            "units": TRAFFIC_UNITS,
            "attribution": TOMTOM_ATTRIBUTION,
        }


class TomTomPlacesClient:
    def __init__(self, http, api_key, base_url="https://api.tomtom.com/search/2", timeout=8.0):
        self.http = http
        self.api_key = (api_key or "").strip("\"'")
        self.base_url = (base_url or "https://api.tomtom.com/search/2").rstrip("/")
        self.timeout = timeout

    def search_nearby(self, lat, lng, radius, category="eatery"):
        if not self.api_key:
            raise AppError(
                "TomTom API key is not configured.",
                status=503,
                code="NOT_CONFIGURED",
            )
        # 7315 is TomTom POI categorySet for Restaurant / Dining
        query = urlencode({
            "key": self.api_key,
            "lat": f"{lat:.6f}",
            "lon": f"{lng:.6f}",
            "radius": str(min(int(radius), 50000)),
            "categorySet": "7315",
            "limit": "100",
        })
        url = f"{self.base_url}/nearbySearch/.json?{query}"
        try:
            payload = self.http.get(url, timeout=self.timeout)
        except AppError:
            raise
        except Exception as error:
            raise map_upstream_error(error, "TomTom Search API")

        results = (payload or {}).get("results") or []
        places = []
        for item in results:
            poi = item.get("poi") or {}
            pos = item.get("position") or {}
            if not isinstance(pos.get("lat"), (int, float)) or not isinstance(pos.get("lon"), (int, float)):
                continue
            name = poi.get("name") or "Eatery"
            categories = poi.get("categories") or []
            cuisine = None
            primary_cat = "restaurant"
            if categories:
                primary_cat = str(categories[0])
                if len(categories) > 1:
                    cuisine = str(categories[0])
                    primary_cat = str(categories[1])

            for cls in poi.get("classifications") or []:
                for name_info in cls.get("names") or []:
                    n = str(name_info.get("name", "")).lower()
                    if n in ("restaurant", "fast food", "cafe", "food court"):
                        primary_cat = n

            dist = item.get("dist")
            distance_meters = round(dist) if isinstance(dist, (int, float)) else round(
                haversine_meters({"lat": lat, "lng": lng}, {"lat": pos["lat"], "lng": pos["lon"]})
            )

            places.append({
                "id": str(item.get("id") or f"tomtom/{pos['lat']},{pos['lon']}"),
                "name": name,
                "category": primary_cat,
                "cuisine": cuisine,
                "lat": pos["lat"],
                "lng": pos["lon"],
                "distanceMeters": distance_meters,
                "openingHours": None,
                "phone": poi.get("phone"),
                "website": poi.get("url"),
                "wheelchair": None,
                "rating": None,
                "ratingSource": None,
                "source": "tomtom",
                "directionsUrl": f"https://www.openstreetmap.org/directions?to={pos['lat']}%2C{pos['lon']}",
            })

        places.sort(key=lambda p: p["distanceMeters"])
        return {
            "places": places,
            "omittedCount": 0,
            "attribution": "Places data © TomTom",
            "source": "tomtom",
            "provider": "tomtom",
        }

