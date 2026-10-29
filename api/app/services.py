import time
from datetime import datetime, timezone

from .errors import AppError
from .geo import bbox_key
from .here import TRAFFIC_UNITS
from .overpass import eatery_query, normalize_eateries, normalize_tolls, toll_query

MAX_PLACES = 100


class HealthService:
    def __init__(self, persist_status=None):
        self.records = {}
        self.persist_status = persist_status

    def seed(self, role, provider, patch):
        self._update(role, provider, patch)

    def mark_attempt(self, role, provider):
        self._update(role, provider, {
            "configured": True,
            "lastAttemptAt": _now(),
            "errorCode": None,
        })

    def mark_success(self, role, provider, message=None):
        now = _now()
        self._update(role, provider, {
            "configured": True,
            "status": "ok",
            "lastAttemptAt": now,
            "lastSuccessAt": now,
            "errorCode": None,
            "message": message,
        })

    def mark_failure(self, role, provider, error):
        current = self.records.get(f"{role}:{provider}")
        code = getattr(error, "code", None) or "UPSTREAM_FAILURE"
        self._update(role, provider, {
            "status": "not_configured" if code == "NOT_CONFIGURED" else "error",
            "configured": code != "NOT_CONFIGURED",
            "lastAttemptAt": _now(),
            "lastSuccessAt": None if not current else current.get("lastSuccessAt"),
            "errorCode": code,
            "message": getattr(error, "message", "Request failed."),
        })

    def snapshot(self, extra=None):
        body = {"checkedAt": _now(), "sources": list(self.records.values())}
        if extra:
            body.update(extra)
        return body

    def _update(self, role, provider, patch):
        key = f"{role}:{provider}"
        current = self.records.get(key) or {
            "role": role,
            "provider": provider,
            "configured": True,
            "status": "unknown",
            "lastAttemptAt": None,
            "lastSuccessAt": None,
            "errorCode": None,
            "message": None,
        }
        current.update(patch)
        self.records[key] = current
        if self.persist_status:
            try:
                self.persist_status(current)
            except Exception:
                pass
        return current


class MemoryCache:
    def __init__(self, limit=200):
        self.limit = limit
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value):
        self.store.pop(key, None)
        self.store[key] = value
        while len(self.store) > self.limit:
            self.store.pop(next(iter(self.store)))


class TrafficService:
    def __init__(self, provider, health, cache_ttl_ms, stale_max_age_ms, persist_snapshots=None):
        self.provider = provider
        self.health = health
        self.cache_ttl = cache_ttl_ms / 1000
        self.stale_max_age = stale_max_age_ms / 1000
        self.persist_snapshots = persist_snapshots
        self.cache = MemoryCache(80)
        self.segments = MemoryCache(4000)

    def get_traffic(self, bbox):
        key = bbox_key(bbox)
        cached = self.cache.get(key)
        if cached and time.time() - cached["storedAt"] < self.cache_ttl:
            return cached["payload"]
        if self.health:
            self.health.mark_attempt("traffic", self.provider.id)
        try:
            result = self.provider.fetch_flow(bbox)
            payload = {
                "source": result["source"],
                "fetchedAt": _now(),
                "observedAt": result.get("observedAt"),
                "stale": False,
                "staleReason": None,
                "bbox": [bbox["west"], bbox["south"], bbox["east"], bbox["north"]],
                "units": result.get("units") or TRAFFIC_UNITS,
                "attribution": result.get("attribution"),
                "omittedCount": result.get("omittedCount") or 0,
                "features": result["features"],
                "coverageNote": (
                    "Segments are limited to the requested bounds and the configured HERE functional classes. "
                    "A missing road means HERE did not return it for this request, not that traffic is free-flowing."
                    if self.provider.id == "here"
                    else (
                        "Segments are limited to the requested bounds and the map zoom level. "
                        "A missing road means TomTom did not return flow for it at this zoom, not that traffic is free-flowing."
                        if self.provider.id == "tomtom"
                        else None
                    )
                ),
            }
            self.cache.set(key, {"storedAt": time.time(), "payload": payload})
            self._remember(payload)
            if self.health:
                self.health.mark_success("traffic", self.provider.id)
            if self.persist_snapshots:
                try:
                    self.persist_snapshots(payload["features"], payload)
                except Exception:
                    pass
            return payload
        except Exception as error:
            if self.health:
                self.health.mark_failure("traffic", self.provider.id, error)
            last = self.cache.get(key)
            if last and time.time() - last["storedAt"] <= self.stale_max_age and getattr(error, "code", None) != "NOT_CONFIGURED":
                stale = {
                    **last["payload"],
                    "stale": True,
                    "staleReason": "The latest traffic request failed. Showing the last successful retrieval for this area.",
                }
                self._remember(stale)
                return stale
            raise

    def get_segment(self, segment_id):
        entry = self.segments.get(segment_id)
        if not entry:
            raise AppError(
                "Detailed metrics for this segment are not in the current result set. Load traffic for the map area that contains the road, then select it again.",
                status=404,
                code="SEGMENT_NOT_IN_CACHE",
            )
        return entry

    def _remember(self, payload):
        for feature in payload["features"]:
            self.segments.set(feature["id"], {
                "source": payload["source"],
                "fetchedAt": payload["fetchedAt"],
                "observedAt": payload["observedAt"],
                "stale": payload["stale"],
                "staleReason": payload["staleReason"],
                "units": payload["units"],
                "feature": feature,
            })


class TollService:
    def __init__(self, overpass, health, cache_ttl_ms, stale_max_age_ms):
        self.overpass = overpass
        self.health = health
        self.cache_ttl = cache_ttl_ms / 1000
        self.stale_max_age = stale_max_age_ms / 1000
        self.cache = MemoryCache(60)

    def get_tolls(self, bbox):
        key = bbox_key(bbox)

        def load():
            data = self.overpass.query(toll_query(bbox))
            normalized = normalize_tolls(data["elements"])
            return {
                **normalized,
                "fetchedAt": _now(),
                "stale": False,
                "staleReason": None,
                "bbox": [bbox["west"], bbox["south"], bbox["east"], bbox["north"]],
                "truncated": False,
            }

        return _cached(self, "tolls", key, load)


class PlacesService:
    def __init__(self, overpass, health, cache_ttl_ms, stale_max_age_ms, tomtom_client=None):
        self.overpass = overpass
        self.tomtom = tomtom_client
        self.health = health
        self.cache_ttl = cache_ttl_ms / 1000
        self.stale_max_age = stale_max_age_ms / 1000
        self.cache = MemoryCache(60)

    def get_nearby(self, lat, lng, radius, category):
        key = f"{lat:.3f},{lng:.3f},{radius},{category}"

        def load():
            if self.tomtom and getattr(self.tomtom, "api_key", None):
                try:
                    normalized = self.tomtom.search_nearby(lat, lng, radius, category)
                    places = normalized["places"]
                    return {
                        "source": normalized["source"],
                        "provider": normalized["provider"],
                        "attribution": normalized["attribution"],
                        "fetchedAt": _now(),
                        "stale": False,
                        "staleReason": None,
                        "origin": {"lat": lat, "lng": lng},
                        "radiusMeters": radius,
                        "category": category,
                        "omittedCount": normalized["omittedCount"],
                        "truncated": len(places) > MAX_PLACES,
                        "places": places[:MAX_PLACES],
                    }
                except Exception as tomtom_err:
                    if self.health:
                        self.health.mark_failure("places", "tomtom", tomtom_err)

            data = self.overpass.query(eatery_query(lat, lng, radius))
            normalized = normalize_eateries(data["elements"], {"lat": lat, "lng": lng})
            places = normalized["places"]
            return {
                "source": normalized["source"],
                "provider": normalized["provider"],
                "attribution": normalized["attribution"],
                "fetchedAt": _now(),
                "stale": False,
                "staleReason": None,
                "origin": {"lat": lat, "lng": lng},
                "radiusMeters": radius,
                "category": category,
                "omittedCount": normalized["omittedCount"],
                "truncated": len(places) > MAX_PLACES,
                "places": places[:MAX_PLACES],
            }

        return _cached(self, "places", key, load)


def _cached(service, role, key, load):
    cached = service.cache.get(key)
    if cached and time.time() - cached["storedAt"] < service.cache_ttl:
        return cached["payload"]
    provider_name = "tomtom" if (getattr(service, "tomtom", None) and getattr(service.tomtom, "api_key", None)) else "overpass"
    if service.health:
        service.health.mark_attempt(role, provider_name)
    try:
        payload = load()
        service.cache.set(key, {"storedAt": time.time(), "payload": payload})
        if service.health:
            service.health.mark_success(role, payload.get("provider") or provider_name)
        return payload
    except Exception as error:
        if service.health:
            service.health.mark_failure(role, provider_name, error)
        if cached and time.time() - cached["storedAt"] <= service.stale_max_age:
            return {
                **cached["payload"],
                "stale": True,
                "staleReason": "The latest places request failed. Showing the last successful result.",
            }
        raise


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
