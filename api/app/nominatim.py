import time
from urllib.parse import urlencode

from .errors import AppError, map_upstream_error

ATTRIBUTION = "Data © OpenStreetMap contributors, ODbL 1.0. https://www.openstreetmap.org/copyright"


class NominatimGeocoder:
    def __init__(self, http, base_url, user_agent, timeout_ms, cache_ttl_ms=86_400_000, min_interval_ms=1100):
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.timeout = timeout_ms / 1000
        self.cache_ttl = cache_ttl_ms / 1000
        self.min_interval = min_interval_ms / 1000
        self.id = "nominatim"
        self.attribution = ATTRIBUTION
        self._cache = {}
        self._next_allowed = 0

    def search(self, query):
        key = f"s:{query.lower()}"
        cached = self._read(key)
        if cached:
            return cached
        payload = self._request("/search", {"q": query, "format": "jsonv2", "addressdetails": "0", "limit": "5"})
        results = [item for item in (normalize_result(entry) for entry in payload or []) if item]
        body = {"source": "nominatim", "attribution": ATTRIBUTION, "results": results}
        self._cache[key] = (time.time(), body)
        return body

    def reverse(self, lat, lng):
        key = f"r:{lat:.4f},{lng:.4f}"
        cached = self._read(key)
        if cached:
            return cached
        payload = self._request("/reverse", {"lat": str(lat), "lon": str(lng), "format": "jsonv2"})
        result = None if not payload or payload.get("error") else normalize_result(payload)
        body = {"source": "nominatim", "attribution": ATTRIBUTION, "result": result}
        self._cache[key] = (time.time(), body)
        return body

    def _request(self, path, params):
        wait = max(0, self._next_allowed - time.time())
        self._next_allowed = time.time() + wait + self.min_interval
        if wait:
            time.sleep(wait)
        url = f"{self.base_url}{path}?{urlencode(params)}"
        try:
            return self.http.get(url, headers={"Accept": "application/json", "User-Agent": self.user_agent}, timeout=self.timeout)
        except Exception as error:
            if getattr(error, "status_code", None) == 429:
                raise AppError(
                    "Geocoding rate limit was reached. Wait a moment and try again.",
                    status=429,
                    code="UPSTREAM_RATE_LIMIT",
                ) from error
            raise map_upstream_error(error, "Nominatim") from error

    def _read(self, key):
        entry = self._cache.get(key)
        if not entry or time.time() - entry[0] > self.cache_ttl:
            return None
        return entry[1]


def normalize_result(entry):
    try:
        lat = float(entry.get("lat"))
        lng = float(entry.get("lon"))
    except (TypeError, ValueError):
        return None
    box = entry.get("boundingbox")
    bounding = None
    if isinstance(box, list) and len(box) == 4:
        try:
            south, north, west, east = [float(value) for value in box]
            bounding = {"south": south, "north": north, "west": west, "east": east}
        except ValueError:
            bounding = None
    name = entry.get("name")
    return {
        "id": f"{entry.get('osm_type') or 'osm'}/{entry.get('osm_id')}" if entry.get("osm_id") is not None else f"{lat},{lng}",
        "name": name.strip() if isinstance(name, str) and name.strip() else None,
        "label": entry.get("display_name") if isinstance(entry.get("display_name"), str) else None,
        "lat": lat,
        "lng": lng,
        "boundingBox": bounding,
    }
