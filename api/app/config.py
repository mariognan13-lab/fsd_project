import os

CONGESTION_NOTES = [
    "HERE jamFactor is a provider score from 0.0 (no congestion) to 10.0 (road blocked). A value of 10.0 means the roadway is blocked.",
    "This application maps jamFactor as: below 3 free-flow, 3 up to below 5 light, 5 up to below 8 moderate, and 8 or above heavy. These cuts are starting assumptions and can be changed with JAM_FREE_BELOW, JAM_LIGHT_BELOW, and JAM_MODERATE_BELOW.",
    "If jamFactor is absent, speed ratio = observed speed / free-flow speed. Below 0.40 is heavy, below 0.65 is moderate, below 0.85 is light, and 0.85 or above is free-flow. These cuts are assumptions, not a universal standard.",
    "If jamFactor and a valid speed pair are both unavailable, the segment is Unknown. Closed roads reported by the provider are Heavy.",
]


def _int_env(name, fallback):
    try:
        value = float(os.environ.get(name, ""))
    except ValueError:
        return fallback
    return int(value) if value > 0 else fallback


def _float_env(name, fallback):
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return fallback
    try:
        return float(raw)
    except ValueError:
        return fallback


def congestion_thresholds():
    thresholds = {
        "jamFactor": {
            "freeFlowBelow": _float_env("JAM_FREE_BELOW", 3),
            "lightBelow": _float_env("JAM_LIGHT_BELOW", 5),
            "moderateBelow": _float_env("JAM_MODERATE_BELOW", 8),
        },
        "speedRatio": {
            "heavyBelow": _float_env("RATIO_HEAVY_BELOW", 0.4),
            "moderateBelow": _float_env("RATIO_MODERATE_BELOW", 0.65),
            "lightBelow": _float_env("RATIO_LIGHT_BELOW", 0.85),
        },
    }
    jam = thresholds["jamFactor"]
    ratio = thresholds["speedRatio"]
    jam_ok = jam["freeFlowBelow"] < jam["lightBelow"] < jam["moderateBelow"] <= 10
    ratio_ok = ratio["heavyBelow"] < ratio["moderateBelow"] < ratio["lightBelow"] <= 1
    if not jam_ok or not ratio_ok:
        return {
            "jamFactor": {"freeFlowBelow": 3, "lightBelow": 5, "moderateBelow": 8},
            "speedRatio": {"heavyBelow": 0.4, "moderateBelow": 0.65, "lightBelow": 0.85},
        }
    return thresholds


def get_config():
    urls = os.environ.get(
        "OVERPASS_URLS",
        "https://overpass-api.de/api/interpreter,https://overpass.kumi.systems/api/interpreter",
    )
    return {
        "port": _int_env("PORT", 5050),
        "clientOrigin": os.environ.get("CLIENT_ORIGIN", "http://localhost:5173"),
        "serveClient": os.environ.get("SERVE_CLIENT") == "true",
        "mongoUri": os.environ.get("MONGODB_URI", ""),
        "trafficProvider": os.environ.get("TRAFFIC_PROVIDER", "here").lower(),
        "trafficApiKey": os.environ.get("TRAFFIC_API_KEY", ""),
        "hereApiBaseUrl": os.environ.get("HERE_API_BASE_URL", "https://data.traffic.hereapi.com/v7"),
        "hereFunctionalClasses": os.environ.get("HERE_FUNCTIONAL_CLASSES", "1,2,3,4"),
        "simulateTraffic": os.environ.get("SIMULATE_TRAFFIC", "true").lower() == "true",

        "tomtomApiKey": (os.environ.get("TOMTOM_API_KEY", "") or os.environ.get("TRAFFIC_API_KEY", "")).strip("\"'"),
        "tomtomBaseUrl": os.environ.get("TOMTOM_BASE_URL", "https://api.tomtom.com/traffic/services"),
        "tomtomSearchBaseUrl": os.environ.get("TOMTOM_SEARCH_BASE_URL", "https://api.tomtom.com/search/2"),
        "tomtomVersion": os.environ.get("TOMTOM_TRAFFIC_VERSION", "4"),
        "tomtomZoom": _int_env("TOMTOM_ZOOM", 12),
        "tomtomGrid": _int_env("TOMTOM_GRID", 3),
        "mapStyleUrl": os.environ.get("MAP_STYLE_URL", "https://tiles.openfreemap.org/styles/liberty"),
        "defaultLng": _float_env("DEFAULT_LNG", 80.653),
        "defaultLat": _float_env("DEFAULT_LAT", 16.5125),
        "defaultZoom": _float_env("DEFAULT_ZOOM", 14),
        "defaultLabel": os.environ.get("DEFAULT_LABEL", "Kanuru–Vijayawada"),
        "nominatimBaseUrl": os.environ.get("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org"),
        "nominatimUserAgent": os.environ.get(
            "NOMINATIM_USER_AGENT",
            "TrafficIQ/1.0 (local development; set NOMINATIM_USER_AGENT)",
        ),
        "overpassUrls": [item.strip() for item in urls.split(",") if item.strip()],
        "appUserAgent": os.environ.get("APP_USER_AGENT", "TrafficIQ/1.0 (local development overpass client)"),
        "trafficPollIntervalMs": _int_env("TRAFFIC_POLL_INTERVAL_MS", 60000),
        "trafficCacheTtlMs": _int_env("TRAFFIC_CACHE_TTL_MS", 30000),
        "trafficStaleMaxAgeMs": _int_env("TRAFFIC_STALE_MAX_AGE_MS", 900000),
        "placesCacheTtlMs": _int_env("PLACES_CACHE_TTL_MS", 600000),
        "placesStaleMaxAgeMs": _int_env("PLACES_STALE_MAX_AGE_MS", 1800000),
        "maxBboxSpanDegrees": _float_env("MAX_BBOX_SPAN_DEGREES", 0.22),
        "requestTimeoutMs": _int_env("REQUEST_TIMEOUT_MS", 20000),
        "overpassTimeoutMs": _int_env("OVERPASS_TIMEOUT_MS", 45000),
        "persistTrafficSnapshots": os.environ.get("TRAFFIC_PERSIST_SNAPSHOTS") == "true",
        "eateryRadii": [1000, 3000, 5000, 10000],
        "congestionThresholds": congestion_thresholds(),
        "congestionNotes": CONGESTION_NOTES,
    }


def public_config(config=None):
    config = config or get_config()
    provider = config["trafficProvider"]
    if provider == "here":
        provider_key = config["trafficApiKey"]
        provider_label = "HERE"
    elif provider == "tomtom":
        provider_key = config.get("tomtomApiKey") or config["trafficApiKey"]
        provider_label = "TomTom"
    else:
        provider_key = ""
        provider_label = None
    traffic_configured = bool(provider_key) and provider_label is not None
    return {
        "mapStyleUrl": config["mapStyleUrl"],
        "defaultCenter": [config["defaultLng"], config["defaultLat"]],
        "defaultZoom": config["defaultZoom"],
        "defaultLabel": config["defaultLabel"],
        "trafficPollIntervalMs": config["trafficPollIntervalMs"],
        "trafficProvider": config["trafficProvider"],
         "trafficSimulationEnabled": config.get("simulateTraffic", True),

        "trafficConfigured": traffic_configured,
        "maxBboxSpanDegrees": config["maxBboxSpanDegrees"],
        "eateryRadii": config["eateryRadii"],
        "hereFunctionalClasses": config["hereFunctionalClasses"],
        "congestion": {
            "thresholds": {
                "jamFactor": config["congestionThresholds"]["jamFactor"],
                "speedRatio": config["congestionThresholds"]["speedRatio"],
            },
            "notes": config["congestionNotes"],
        },
        "attributions": {
            "map": "OpenFreeMap © OpenMapTiles © OpenStreetMap contributors",
            "geocoder": "Search data © OpenStreetMap contributors, ODbL 1.0",
            "places": "Place and toll data © OpenStreetMap contributors, ODbL",
            "traffic": f"Traffic data © {provider_label}" if traffic_configured else None,
        },
    }
