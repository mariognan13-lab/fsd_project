import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from .seed_traffic import SeedTrafficProvider

from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from .config import get_config, public_config
from .dashboard import render_dashboard
from .errors import AppError
from .here import create_traffic_provider
from .http import HttpxClient
from .nominatim import NominatimGeocoder
from .overpass import OverpassClient
from .persistence import connect, connected, corridors, persist_snapshots, persist_status, places, require_db
from .services import HealthService, PlacesService, TollService, TrafficService
from .summary import summarize_traffic
from .tomtom import TomTomPlacesClient
from .validation import (
    OBJECT_ID,
    SEGMENT_ID,
    parse_bbox,
    parse_category,
    parse_lat_lng,
    parse_radius,
    parse_saved_corridor,
    parse_saved_place,
    parse_search_query,
)

logger = logging.getLogger("trafficiq")


def create_app(overrides=None):
    overrides = overrides or {}
    config = overrides.get("config") or get_config()
    http = overrides.get("http") or HttpxClient()
    health = overrides.get("health") or HealthService(
        persist_status if config["mongoUri"] else None
    )
    _seed_health(health, config)
    traffic = overrides.get("traffic_service") or TrafficService(
        create_traffic_provider(config, http),
        health,
        config["trafficCacheTtlMs"],
        config["trafficStaleMaxAgeMs"],
        persist_snapshots if config["persistTrafficSnapshots"] else None,
    )
    live_traffic_key = config.get("trafficApiKey") or (config.get("tomtomApiKey") if config.get("trafficProvider") == "tomtom" else "")
    if config.get("simulateTraffic", True) and not live_traffic_key:
        traffic = TrafficService(
            SeedTrafficProvider(), health, config["trafficCacheTtlMs"], config["trafficStaleMaxAgeMs"]
        )
    tomtom_places = overrides.get("tomtom_places") or (
        TomTomPlacesClient(http, config["tomtomApiKey"], config.get("tomtomSearchBaseUrl", "https://api.tomtom.com/search/2"))
        if config.get("tomtomApiKey")
        else None
    )
    overpass = overrides.get("overpass") or OverpassClient(
        http, config["overpassUrls"], config["appUserAgent"], config["overpassTimeoutMs"]
    )
    tolls = overrides.get("toll_service") or TollService(
        overpass, health, config["placesCacheTtlMs"], config["placesStaleMaxAgeMs"]
    )
    eateries = overrides.get("places_service") or PlacesService(
        overpass, health, config["placesCacheTtlMs"], config["placesStaleMaxAgeMs"], tomtom_places
    )
    geocoder = overrides.get("geocoder") or NominatimGeocoder(
        http, config["nominatimBaseUrl"], config["nominatimUserAgent"], config["requestTimeoutMs"]
    )
    db_status = overrides.get("db_status") or (lambda: {"connected": connected(), "required": False})

    app = FastAPI(title="Traffic IQ")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[config["clientOrigin"]],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, error: AppError):
        if os.environ.get("LOG_LEVEL") != "silent":
            logger.error("%s %s", error.code, error.message)
        return JSONResponse(status_code=error.status, content={"error": {"code": error.code, "message": error.message}})

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, error: Exception):
        logger.exception("Unhandled API error")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}},
        )

    bundle = {
        "config": config,
        "geocoder": geocoder,
        "traffic": traffic,
        "tolls": tolls,
        "places": eateries,
        "http": http,
    }

    @app.get("/", response_class=HTMLResponse)
    def dashboard(
        q: str = "",
        origin: str = "",
        destination: str = "",
        dest_lat: str = "",
        dest_lng: str = "",
        lat: str = "",
        lng: str = "",
        radius: str = "3",
        layers: str = "",
        traffic: str = "1",
        tolls: str = "",
        places: str = "",
        segment: str = "",
        route: str = "",
        embed: str = "",
    ):
        return render_dashboard(bundle, {
            "q": q,
            "origin": origin,
            "destination": destination,
            "dest_lat": dest_lat,
            "dest_lng": dest_lng,
            "lat": lat,
            "lng": lng,
            "radius": radius,
            "layers": layers,
            "traffic": traffic,
            "tolls": tolls,
            "places": places,
            "segment": segment,
            "route": route,
            "embed": embed,
        })

    @app.get("/api/config/public")
    def config_route():
        return public_config(config)

    @app.get("/api/health")
    def liveness():
        return {"status": "ok", "service": "traffic-iq"}

    @app.get("/api/health/data-sources")
    def data_sources():
        return health.snapshot({"mongodb": db_status()})

    @app.get("/api/traffic")
    def traffic_route(bbox: str = ""):
        return traffic.get_traffic(parse_bbox(bbox, config["maxBboxSpanDegrees"]))

    @app.get("/api/traffic/segment/{segment_id}")
    def segment_route(segment_id: str):
        if not SEGMENT_ID.match(segment_id):
            raise AppError("Segment id is invalid.", status=400, code="VALIDATION_ERROR")
        return traffic.get_segment(segment_id)

    @app.get("/api/summary")
    def summary_route(bbox: str = ""):
        return summarize_traffic(traffic.get_traffic(parse_bbox(bbox, config["maxBboxSpanDegrees"])))

    @app.get("/api/tolls")
    def toll_route(bbox: str = ""):
        return tolls.get_tolls(parse_bbox(bbox, config["maxBboxSpanDegrees"]))

    @app.get("/api/places/nearby")
    def places_route(lat: str = "", lng: str = "", radius: str = "", category: str = ""):
        parsed_lat, parsed_lng = parse_lat_lng(lat, lng)
        return eateries.get_nearby(parsed_lat, parsed_lng, parse_radius(radius), parse_category(category))

    @app.get("/api/geocode")
    def geocode_route(q: str = ""):
        query = parse_search_query(q)
        health.mark_attempt("geocoding", geocoder.id)
        try:
            result = geocoder.search(query)
            health.mark_success("geocoding", geocoder.id)
        except Exception as error:
            health.mark_failure("geocoding", geocoder.id, error)
            raise
        return {**result, "fetchedAt": _stamp()}

    @app.get("/api/geocode/reverse")
    def reverse_route(lat: str = "", lng: str = ""):
        parsed_lat, parsed_lng = parse_lat_lng(lat, lng)
        health.mark_attempt("geocoding", geocoder.id)
        try:
            result = geocoder.reverse(parsed_lat, parsed_lng)
            health.mark_success("geocoding", geocoder.id)
        except Exception as error:
            health.mark_failure("geocoding", geocoder.id, error)
            raise
        return {**result, "fetchedAt": _stamp()}

    @app.get("/api/saved/places")
    def list_places():
        docs = places().find().sort("createdAt", -1).limit(100)
        return {"places": [_place(doc) for doc in docs]}

    @app.post("/api/saved/places", status_code=201)
    async def create_place(request: Request):
        body = parse_saved_place(await request.json())
        require_db()
        doc = {
            "name": body["name"],
            "category": body["category"],
            "coordinates": {"type": "Point", "coordinates": [body["lng"], body["lat"]]},
            "notes": body["notes"],
            "source": body["source"],
            "createdAt": datetime.now(timezone.utc),
        }
        inserted = places().insert_one(doc)
        doc["_id"] = inserted.inserted_id
        return {"place": _place(doc)}

    @app.delete("/api/saved/places/{place_id}")
    def delete_place(place_id: str):
        require_db()
        if not OBJECT_ID.match(place_id):
            raise AppError("Place id is invalid.", status=400, code="VALIDATION_ERROR")
        from bson import ObjectId
        result = places().delete_one({"_id": ObjectId(place_id)})
        if not result.deleted_count:
            raise AppError("Saved place was not found.", status=404, code="NOT_FOUND")
        return {"deleted": True, "id": place_id}

    @app.get("/api/saved/corridors")
    def list_corridors():
        docs = corridors().find().sort("createdAt", -1).limit(100)
        return {"corridors": [_corridor(doc) for doc in docs]}

    @app.post("/api/saved/corridors", status_code=201)
    async def create_corridor(request: Request):
        body = parse_saved_corridor(await request.json())
        require_db()
        body["createdAt"] = datetime.now(timezone.utc)
        inserted = corridors().insert_one(body)
        body["_id"] = inserted.inserted_id
        return {"corridor": _corridor(body)}

    return app


def _seed_health(health, config):
    provider = config["trafficProvider"] or "here"
    if provider == "here":
        configured = bool(config["trafficApiKey"])
    elif provider == "tomtom":
        configured = bool(config.get("tomtomApiKey") or config["trafficApiKey"])
    else:
        configured = False
    health.seed("traffic", provider, {
        "configured": configured,
        "status": "unknown" if configured else "not_configured",
        "message": (
            "Waiting for the first traffic request."
            if configured
            else f"Set TRAFFIC_PROVIDER={provider} and supply the matching API key to retrieve live flow."
        ),
    })
    health.seed("geocoding", "nominatim", {
        "configured": True,
        "status": "unknown",
        "message": "Nominatim is contacted when a search is submitted. Results are cached in memory.",
    })
    health.seed("tolls", "overpass", {
        "configured": True,
        "status": "unknown",
        "message": "OpenStreetMap toll plazas load when the toll layer is enabled.",
    })
    if config.get("tomtomApiKey"):
        health.seed("places", "tomtom", {
            "configured": True,
            "status": "unknown",
            "message": "TomTom POI search loads eateries for a selected point and radius.",
        })
    else:
        health.seed("places", "overpass", {
            "configured": True,
            "status": "unknown",
            "message": "OpenStreetMap eateries load for a selected point and radius.",
        })
    health.seed("map-tiles", "openfreemap", {
        "configured": True,
        "status": "unknown",
        "message": "The map is drawn in Python with OpenStreetMap tiles.",
    })


def _stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _place(doc):
    coordinates = (doc.get("coordinates") or {}).get("coordinates") or [None, None]
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name"),
        "category": doc.get("category"),
        "lng": coordinates[0],
        "lat": coordinates[1],
        "notes": doc.get("notes"),
        "source": doc.get("source"),
        "createdAt": doc.get("createdAt"),
    }


def _corridor(doc):
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name"),
        "roadReference": doc.get("roadReference"),
        "tags": doc.get("tags") or [],
        "geometry": doc.get("geometry") if doc.get("geometry") and doc["geometry"].get("type") else None,
        "createdAt": doc.get("createdAt"),
    }


def _load_env():
    from dotenv import load_dotenv
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env")
    load_dotenv()


_load_env()

# Build the FastAPI app
def build_app():
    app = create_app()

    # Serve Next.js frontend at /(path).* for Railway deployment
    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "out"

    @app.get("/(path).*", include_in_schema=False)
    async def serve_frontend(path: str):
        """Serve Next.js static files from the frontend build directory."""
        index_path = frontend_dist / "index.html"
        if index_path.exists() and not path.startswith("api"):
            return FileResponse(str(index_path))
        return JSONResponse(status_code=404, content={"error": "Not found"})

    @app.post("/api/*")
    async def api_post(path: str):
        return JSONResponse(status_code=405, content={"error": "Method not allowed"})

    @app.get("/api/*")
    async def api_get(path: str):
        return JSONResponse(status_code=405, content={"error": "Method not allowed"})

    return app

app = build_app()
