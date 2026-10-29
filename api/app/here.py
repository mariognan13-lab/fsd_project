import hashlib
from datetime import datetime, timezone

from .congestion import classify_flow, observation_basis
from .errors import AppError, map_upstream_error

TRAFFIC_UNITS = {
    "observedSpeed": "km/h",
    "freeFlowSpeed": "km/h",
    "delay": "seconds",
    "length": "meters",
    "jamFactor": "here-score-0-to-10",
}


class HereTrafficProvider:
    """HERE Traffic API v7 flow. Speeds arrive in m/s and are stored as km/h."""

    def __init__(self, http, api_key, base_url, functional_classes, timeout_ms, thresholds):
        self.http = http
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.functional_classes = functional_classes
        self.timeout = timeout_ms / 1000
        self.thresholds = thresholds
        self.id = "here"

    def fetch_flow(self, bbox):
        if not self.api_key:
            raise AppError(
                "HERE Traffic API key is not configured. Set TRAFFIC_API_KEY in the server environment and restart the API.",
                status=503,
                code="NOT_CONFIGURED",
            )
        body = {
            "in": {
                "type": "bbox",
                "west": bbox["west"],
                "south": bbox["south"],
                "east": bbox["east"],
                "north": bbox["north"],
            },
            "locationReferencing": ["shape"],
        }
        classes = parse_functional_classes(self.functional_classes)
        if classes:
            body["functionalClasses"] = classes
        url = f"{self.base_url}/flow?apiKey={self.api_key}"
        try:
            payload = self.http.post(url, json=body, timeout=self.timeout)
        except AppError:
            raise
        except Exception as error:
            mapped = map_upstream_error(error, "HERE Traffic API")
            raise mapped from None
        return normalize_here_flow(payload, self.thresholds)


def normalize_here_flow(payload, thresholds):
    features = []
    omitted = 0
    for result in payload.get("results") or []:
        feature = _normalize_result(result, thresholds)
        if feature:
            features.append(feature)
        else:
            omitted += 1
    return {
        "source": "here",
        "observedAt": _timestamp(payload.get("sourceUpdated")),
        "features": features,
        "omittedCount": omitted,
        "units": TRAFFIC_UNITS,
        "attribution": "Traffic data © HERE",
    }


def _normalize_result(result, thresholds):
    location = result.get("location") or {}
    flow = result.get("currentFlow") or {}
    line = _shape_to_line(location.get("shape"))
    if not line:
        return None
    observed_mps = _finite(flow.get("speed"))
    free_mps = _finite(flow.get("freeFlow"))
    observed = _to_kmh(observed_mps)
    free_flow = _to_kmh(free_mps)
    jam = _finite(flow.get("jamFactor"))
    confidence = _finite(flow.get("confidence"))
    classification = classify_flow(
        {
            "jamFactor": jam,
            "observedSpeed": observed,
            "freeFlowSpeed": free_flow,
            "traversability": flow.get("traversability") if isinstance(flow.get("traversability"), str) else None,
        },
        thresholds,
    )
    delay = _estimate_delay(_finite(location.get("length")), observed_mps, free_mps)
    description = location.get("description")
    name = description.strip() if isinstance(description, str) and description.strip() else None
    return {
        "id": _segment_id(location, line["coordinates"]),
        "name": name,
        "geometry": {"type": "LineString", "coordinates": line["coordinates"]},
        "observedSpeed": observed,
        "freeFlowSpeed": free_flow,
        "delay": delay,
        "delayEstimated": delay is not None,
        "congestionLevel": classification["congestionLevel"],
        "congestionMethod": classification["congestionMethod"],
        "speedRatio": classification["speedRatio"],
        "observedAt": None,
        "lengthMeters": _finite(location.get("length")),
        "jamFactor": jam,
        "confidence": confidence,
        "observationBasis": observation_basis(confidence),
        "roadStatus": _road_status(flow.get("traversability")),
        "subSegmentCount": len(flow["subSegments"]) if isinstance(flow.get("subSegments"), list) else None,
        "functionalClass": line["functionalClass"],
        "provider": "here",
    }


def _shape_to_line(shape):
    if not shape or not isinstance(shape.get("links"), list):
        return None
    coordinates = []
    classes = []
    for link in shape["links"]:
        if isinstance(link.get("functionalClass"), (int, float)):
            classes.append(link["functionalClass"])
        for point in link.get("points") or []:
            lat = point.get("lat")
            lng = point.get("lng")
            if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
                continue
            nxt = [lng, lat]
            if coordinates and coordinates[-1] == nxt:
                continue
            coordinates.append(nxt)
    if len(coordinates) < 2:
        return None
    unique = list(dict.fromkeys(classes))
    return {"coordinates": coordinates, "functionalClass": unique[0] if len(unique) == 1 else None}


def _segment_id(location, coordinates):
    raw = "|".join([
        location.get("description") or "",
        str(location.get("length") or ""),
        ",".join(str(value) for value in coordinates[0]),
        ",".join(str(value) for value in coordinates[-1]),
    ])
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _estimate_delay(length_m, speed_mps, free_mps):
    if length_m is None or length_m <= 0 or speed_mps is None or speed_mps <= 0 or free_mps is None or free_mps <= 0:
        return None
    delay = (length_m / speed_mps) - (length_m / free_mps)
    return round(delay) if math_isfinite(delay) else None


def _to_kmh(meters_per_second):
    if meters_per_second is None or meters_per_second < 0:
        return None
    return round(meters_per_second * 3.6, 1)


def _finite(value):
    return value if isinstance(value, (int, float)) and math_isfinite(value) else None


def math_isfinite(value):
    return value == value and value not in {float("inf"), float("-inf")}


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _road_status(traversability):
    return {
        "open": "open",
        "closed": "closed",
        "reversibleNotRoutable": "reversible-not-routable",
    }.get(traversability, "unknown")


def parse_functional_classes(value):
    if not value or not str(value).strip():
        return []
    classes = []
    for part in str(value).split(","):
        try:
            number = int(part.strip())
        except ValueError:
            continue
        if 1 <= number <= 5:
            classes.append(number)
    return classes


def create_traffic_provider(config, http):
    if config["trafficProvider"] == "here":
        return HereTrafficProvider(
            http,
            config["trafficApiKey"],
            config["hereApiBaseUrl"],
            config["hereFunctionalClasses"],
            config["requestTimeoutMs"],
            config["congestionThresholds"],
        )

    if config["trafficProvider"] == "tomtom":
        from .tomtom import TomTomTrafficProvider

        return TomTomTrafficProvider(
            http,
            config.get("tomtomApiKey") or config["trafficApiKey"],
            config.get("tomtomBaseUrl", "https://api.tomtom.com/traffic/services"),
            config.get("tomtomVersion", "4"),
            config.get("tomtomZoom", 12),
            config["requestTimeoutMs"],
            config["congestionThresholds"],
            config.get("tomtomGrid", 3),
        )

    class Unsupported:
        id = config["trafficProvider"] or "unconfigured"

        def fetch_flow(self, _bbox):
            message = (
                f'Traffic provider "{self.id}" is not implemented. '
                "Set TRAFFIC_PROVIDER=here or TRAFFIC_PROVIDER=tomtom."
            )
            raise AppError(message, status=503, code="NOT_CONFIGURED")

    return Unsupported()
