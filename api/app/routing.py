from urllib.parse import urlencode

from .errors import AppError, map_upstream_error


def fetch_driving_route(http, origin, destination, timeout, user_agent):
    path = f"{origin['lng']},{origin['lat']};{destination['lng']},{destination['lat']}"
    query = urlencode({"overview": "full", "geometries": "geojson", "steps": "true"})
    url = f"https://router.project-osrm.org/route/v1/driving/{path}?{query}"
    try:
        payload = http.get(url, headers={"User-Agent": user_agent, "Accept": "application/json"}, timeout=timeout)
    except AppError:
        raise
    except Exception as error:
        raise map_upstream_error(error, "Driving route") from error
    route = parse_osrm(payload)
    if route is None:
        raise AppError("No driving route was returned for these two places.", status=404, code="ROUTE_NOT_FOUND")
    return route


def parse_osrm(payload):
    if not isinstance(payload, dict) or payload.get("code") != "Ok":
        return None
    routes = payload.get("routes") or []
    if not routes:
        return None
    route = routes[0]
    geometry = route.get("geometry") or {}
    line = []
    for point in geometry.get("coordinates") or []:
        if isinstance(point, list) and len(point) >= 2:
            line.append([point[1], point[0]])
    if len(line) < 2:
        return None
    steps = []
    for leg in route.get("legs") or []:
        for step in leg.get("steps") or []:
            text = _instruction(step)
            if text:
                steps.append(text)
    distance = route.get("distance")
    duration = route.get("duration")
    return {
        "line": line,
        "distance_km": round(distance / 1000, 1) if isinstance(distance, (int, float)) else None,
        "duration_min": round(duration / 60) if isinstance(duration, (int, float)) else None,
        "steps": steps[:15],
    }


def _instruction(step):
    maneuver = step.get("maneuver") or {}
    kind = maneuver.get("type") or ""
    modifier = (maneuver.get("modifier") or "").replace("-", " ")
    name = step.get("name") or ""
    if kind == "depart":
        return f"Start on {name}" if name else "Start"
    if kind == "arrive":
        return "Arrive at the destination"
    if kind in {"turn", "end of road", "fork", "roundabout", "rotary"}:
        action = f"{kind} {modifier}".strip()
        return f"{action} onto {name}" if name else action
    if kind in {"new name", "continue"}:
        return f"Continue on {name}" if name else "Continue"
    if name:
        return name
    return kind or None
