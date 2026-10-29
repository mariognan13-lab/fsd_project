import time
from urllib.parse import urlencode

from .errors import AppError, map_upstream_error
from .geo import haversine_meters

OSM_ATTRIBUTION = "© OpenStreetMap contributors, ODbL"


class OverpassClient:
    def __init__(self, http, urls, user_agent, timeout_ms, min_interval_ms=1500):
        self.http = http
        self.urls = urls
        self.user_agent = user_agent
        self.timeout = timeout_ms / 1000
        self.min_interval = min_interval_ms / 1000
        self._next_allowed = 0

    def query(self, data):
        last_error = None
        call_timeout = max(5.0, min(self.timeout, 12.0))
        for endpoint in self.urls:
            try:
                self._wait()
                body = self.http.post(
                    endpoint,
                    data=urlencode({"data": data}),
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                        "User-Agent": self.user_agent,
                    },
                    timeout=call_timeout,
                )
                return parse_overpass_body(body)
            except AppError as error:
                last_error = error
            except Exception as error:
                last_error = map_upstream_error(error, "Overpass")
        raise last_error or AppError("Overpass request failed.", status=502, code="UPSTREAM_FAILURE")

    def _wait(self):
        wait = max(0, self._next_allowed - time.time())
        self._next_allowed = time.time() + wait + self.min_interval
        if wait:
            time.sleep(wait)


def parse_overpass_body(data):
    if isinstance(data, str):
        if any(token in data for token in ("Gateway Timeout", "rate_limited", "Too Many Requests", "runtime error")):
            raise AppError(
                "The public Overpass service is busy. Wait a moment and try again.",
                status=503,
                code="UPSTREAM_CAPACITY",
            )
        raise AppError("Overpass returned an unexpected response.", status=502, code="UPSTREAM_FAILURE")
    if not isinstance(data, dict) or not isinstance(data.get("elements"), list):
        remark = data.get("remark") if isinstance(data, dict) else ""
        if isinstance(remark, str) and any(token in remark.lower() for token in ("timeout", "busy", "rate")):
            raise AppError(
                "The public Overpass service is busy. Wait a moment and try again.",
                status=503,
                code="UPSTREAM_CAPACITY",
            )
        raise AppError("Overpass returned an unexpected response.", status=502, code="UPSTREAM_FAILURE")
    return data


def normalize_tolls(elements):
    tolls = []
    omitted = 0
    for element in elements:
        point = _point(element)
        if not point:
            omitted += 1
            continue
        tags = element.get("tags") or {}
        if tags.get("highway") == "toll_gantry":
            kind = "toll_gantry"
        elif tags.get("barrier") == "toll_booth":
            kind = "toll_booth"
        else:
            kind = tags.get("barrier") or tags.get("highway") or "toll"
        tolls.append({
            "id": f"{element.get('type')}/{element.get('id')}",
            "name": _tag(tags, "name") or _tag(tags, "name:en"),
            "lat": point["lat"],
            "lng": point["lng"],
            "kind": kind,
            "operator": _tag(tags, "operator"),
            "ref": _tag(tags, "ref"),
            "road": _tag(tags, "addr:street"),
            "openingHours": _tag(tags, "opening_hours"),
            "fee": _tag(tags, "fee"),
            "source": "openstreetmap",
        })
    return {
        "tolls": tolls,
        "omittedCount": omitted,
        "attribution": OSM_ATTRIBUTION,
        "source": "openstreetmap",
        "provider": "overpass",
    }


def normalize_eateries(elements, origin):
    places = []
    omitted = 0
    for element in elements:
        point = _point(element)
        if not point:
            omitted += 1
            continue
        tags = element.get("tags") or {}
        rating = _tag(tags, "rating")
        places.append({
            "id": f"{element.get('type')}/{element.get('id')}",
            "name": _tag(tags, "name") or _tag(tags, "name:en"),
            "category": _tag(tags, "amenity"),
            "cuisine": _tag(tags, "cuisine"),
            "lat": point["lat"],
            "lng": point["lng"],
            "distanceMeters": round(haversine_meters(origin, point)),
            "openingHours": _tag(tags, "opening_hours"),
            "phone": _tag(tags, "phone") or _tag(tags, "contact:phone"),
            "website": _tag(tags, "website") or _tag(tags, "contact:website"),
            "wheelchair": _tag(tags, "wheelchair"),
            "rating": rating,
            "ratingSource": "openstreetmap-tag" if rating else None,
            "source": "openstreetmap",
            "directionsUrl": f"https://www.openstreetmap.org/directions?to={point['lat']}%2C{point['lng']}",
        })
    places.sort(key=lambda place: place["distanceMeters"])
    return {
        "places": places,
        "omittedCount": omitted,
        "attribution": OSM_ATTRIBUTION,
        "source": "openstreetmap",
        "provider": "overpass",
    }


def toll_query(bbox):
    box = f"{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']}"
    return f"""[out:json][timeout:10];
(
  node["barrier"="toll_booth"]({box});
  node["highway"="toll_gantry"]({box});
  way["barrier"="toll_booth"]({box});
  way["highway"="toll_gantry"]({box});
);
out center tags;"""


def eatery_query(lat, lng, radius):
    around = f"(around:{radius},{lat},{lng})"
    clauses = []
    for amenity in ("restaurant", "cafe", "fast_food", "food_court"):
        clauses.append(f'node["amenity"="{amenity}"]{around};')
        clauses.append(f'way["amenity"="{amenity}"]{around};')
    joined = "\n  ".join(clauses)
    return f"""[out:json][timeout:10];
(
  {joined}
);
out center tags;"""


def _point(element):
    if isinstance(element.get("lat"), (int, float)) and isinstance(element.get("lon"), (int, float)):
        return {"lat": element["lat"], "lng": element["lon"]}
    center = element.get("center") or {}
    if isinstance(center.get("lat"), (int, float)) and isinstance(center.get("lon"), (int, float)):
        return {"lat": center["lat"], "lng": center["lon"]}
    return None


def _tag(tags, key):
    value = tags.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None
