import math

EARTH_RADIUS_METERS = 6_371_000


def haversine_meters(origin, point):
    lat1 = math.radians(origin["lat"])
    lat2 = math.radians(point["lat"])
    d_lat = math.radians(point["lat"] - origin["lat"])
    d_lng = math.radians(point["lng"] - origin["lng"])
    a = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(min(1, math.sqrt(a)))


def bbox_key(bbox):
    rounded = [round(bbox[name], 3) for name in ("west", "south", "east", "north")]
    return ",".join(str(value) for value in rounded)


def span_too_large(bbox, max_span):
    return (bbox["east"] - bbox["west"]) > max_span or (bbox["north"] - bbox["south"]) > max_span
