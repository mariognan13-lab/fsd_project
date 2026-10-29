import re

from .errors import validation_error
from .geo import span_too_large

MAX_RADIUS_METERS = 500_000


def parse_bbox(value, max_span):
    if not isinstance(value, str) or not value.strip():
        raise validation_error("Query parameter bbox is required. Use west,south,east,north.")
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise validation_error("bbox must be four comma-separated numbers: west,south,east,north.")
    try:
        west, south, east, north = [float(part) for part in parts]
    except ValueError as error:
        raise validation_error("bbox values must be finite numbers.") from error
    if west < -180 or east > 180 or south < -90 or north > 90:
        raise validation_error("bbox coordinates are outside the valid longitude and latitude ranges.")
    if south >= north or west >= east:
        raise validation_error(
            "bbox south must be below north, and west must be left of east. Areas that cross the antimeridian are not supported."
        )
    bbox = {"west": west, "south": south, "east": east, "north": north}
    if span_too_large(bbox, max_span):
        raise validation_error(
            f"bbox is larger than {max_span} degrees on a side. Zoom in before requesting traffic, tolls, or a summary."
        )
    return bbox


def parse_lat_lng(lat, lng):
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError) as error:
        raise validation_error("lat must be a number from -90 to 90.") from error
    if lat < -90 or lat > 90:
        raise validation_error("lat must be a number from -90 to 90.")
    if lng < -180 or lng > 180:
        raise validation_error("lng must be a number from -180 to 180.")
    return lat, lng


def parse_radius(value):
    try:
        radius = int(value)
    except (TypeError, ValueError) as error:
        raise validation_error("radius must be a whole number of meters.") from error
    if radius <= 0 or radius > MAX_RADIUS_METERS:
        raise validation_error("radius must be greater than 0 and at most 500000 meters.")
    return radius


def parse_category(value):
    if value != "eatery":
        raise validation_error("category must be eatery.")
    return value


def parse_search_query(value):
    if not isinstance(value, str):
        raise validation_error("Query parameter q is required.")
    query = value.strip()
    if len(query) < 2:
        raise validation_error("Enter at least 2 characters to search.")
    if len(query) > 200:
        raise validation_error("Search text is too long.")
    return query


def parse_saved_place(body):
    if not isinstance(body, dict):
        raise validation_error("A JSON body is required.")
    lat, lng = parse_lat_lng(body.get("lat"), body.get("lng"))
    return {
        "name": _required(body.get("name"), "name", 200),
        "category": _optional(body.get("category"), "category", 80),
        "lat": lat,
        "lng": lng,
        "notes": _optional(body.get("notes"), "notes", 1000),
        "source": _optional(body.get("source"), "source", 80),
    }


def parse_saved_corridor(body):
    if not isinstance(body, dict):
        raise validation_error("A JSON body is required.")
    tags = body.get("tags") if isinstance(body.get("tags"), list) else []
    clean_tags = [tag.strip()[:40] for tag in tags if isinstance(tag, str) and tag.strip()][:12]
    geometry = parse_line(body["geometry"]) if body.get("geometry") is not None else None
    return {
        "name": _required(body.get("name"), "name", 200),
        "roadReference": _optional(body.get("roadReference"), "roadReference", 300),
        "tags": clean_tags,
        "geometry": geometry,
    }


def parse_line(geometry):
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if geometry.get("type") != "LineString" or not isinstance(coordinates, list) or len(coordinates) < 2:
        raise validation_error("geometry must be a GeoJSON LineString with at least two positions.")
    parsed = []
    for position in coordinates:
        if not isinstance(position, list) or len(position) < 2:
            raise validation_error("Each geometry position must be [longitude, latitude].")
        lng, lat = position[0], position[1]
        if not isinstance(lng, (int, float)) or not isinstance(lat, (int, float)) or not -90 <= lat <= 90 or not -180 <= lng <= 180:
            raise validation_error("Geometry coordinates are invalid.")
        parsed.append([lng, lat])
    return {"type": "LineString", "coordinates": parsed}


def _required(value, field, limit):
    if not isinstance(value, str) or not value.strip():
        raise validation_error(f"{field} is required.")
    if len(value.strip()) > limit:
        raise validation_error(f"{field} must be {limit} characters or fewer.")
    return value.strip()


def _optional(value, field, limit):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise validation_error(f"{field} must be a string.")
    if len(value.strip()) > limit:
        raise validation_error(f"{field} must be {limit} characters or fewer.")
    return value.strip()


SEGMENT_ID = re.compile(r"^[a-zA-Z0-9_-]{4,64}$")
OBJECT_ID = re.compile(r"^[a-f0-9]{24}$", re.I)
