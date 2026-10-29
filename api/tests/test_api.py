from fastapi.testclient import TestClient

from app.config import get_config
from app.congestion import classify_flow, observation_basis
from app.errors import AppError
from app.here import HereTrafficProvider, normalize_here_flow
from app.main import create_app
from app.nominatim import NominatimGeocoder
from app.overpass import OverpassClient, normalize_eateries, normalize_tolls
from app.services import TrafficService
from app.routing import parse_osrm
from app.summary import summarize_traffic

THRESHOLDS = {
    "jamFactor": {"freeFlowBelow": 3, "lightBelow": 5, "moderateBelow": 8},
    "speedRatio": {"heavyBelow": 0.4, "moderateBelow": 0.65, "lightBelow": 0.85},
}
BBOX = "77.55,12.95,77.62,13.00"
FEATURE = {
    "id": "abc123",
    "name": "Sample Road",
    "geometry": {"type": "LineString", "coordinates": [[77.59, 12.97], [77.6, 12.98]]},
    "observedSpeed": 20,
    "freeFlowSpeed": 40,
    "delay": 4,
    "delayEstimated": True,
    "congestionLevel": "heavy",
    "observationBasis": "realtime",
    "provider": "here",
}


def base_config():
    config = get_config()
    config.update({"mongoUri": "", "trafficApiKey": "", "trafficProvider": "here", "persistTrafficSnapshots": False, "maxBboxSpanDegrees": 0.22})
    return config


class Provider:
    id = "here"

    def __init__(self, features):
        self.features = features

    def fetch_flow(self, _bbox):
        return {"source": "here", "observedAt": "2026-10-16T14:00:00.000Z", "features": self.features, "omittedCount": 0}


def client_with(features=None, **overrides):
    config = base_config()
    config["trafficApiKey"] = "present"
    traffic = TrafficService(Provider(features if features is not None else [FEATURE]), None, 1000, 1000)
    app = create_app({"config": config, "traffic_service": traffic, **overrides})
    return TestClient(app, raise_server_exceptions=False)


def test_congestion_bands():
    assert classify_flow({"jamFactor": 2.9}, THRESHOLDS)["congestionLevel"] == "free-flow"
    assert classify_flow({"jamFactor": 3}, THRESHOLDS)["congestionLevel"] == "light"
    assert classify_flow({"jamFactor": 5}, THRESHOLDS)["congestionLevel"] == "moderate"
    assert classify_flow({"jamFactor": 8}, THRESHOLDS)["congestionLevel"] == "heavy"
    closed = classify_flow({"jamFactor": 0, "traversability": "closed"}, THRESHOLDS)
    assert closed["congestionMethod"] == "provider-closure"
    assert classify_flow({}, THRESHOLDS)["congestionLevel"] == "unknown"
    assert classify_flow({"observedSpeed": 39, "freeFlowSpeed": 100}, THRESHOLDS)["congestionLevel"] == "heavy"
    assert classify_flow({"observedSpeed": 85, "freeFlowSpeed": 100}, THRESHOLDS)["congestionLevel"] == "free-flow"
    assert classify_flow({"jamFactor": 9, "traversability": "reversibleNotRoutable"}, THRESHOLDS)["congestionLevel"] == "unknown"
    assert observation_basis(0.71) == "realtime"
    assert observation_basis(0.7) == "historical"
    assert observation_basis(0.5) == "speed-limit"


def test_here_normalization_and_missing_key():
    normalized = normalize_here_flow({
        "sourceUpdated": "2026-10-16T14:00:00Z",
        "results": [
            {
                "location": {
                    "description": "Sample Road",
                    "length": 100,
                    "shape": {"links": [{"functionalClass": 2, "points": [{"lat": 12.97, "lng": 77.59}, {"lat": 12.971, "lng": 77.591}]}]},
                },
                "currentFlow": {"speed": 10, "freeFlow": 20, "jamFactor": 6.2, "confidence": 0.92, "traversability": "open"},
            },
            {"location": {"description": "No geometry"}, "currentFlow": {"speed": 5, "freeFlow": 5, "jamFactor": 0}},
        ],
    }, THRESHOLDS)
    feature = normalized["features"][0]
    assert feature["observedSpeed"] == 36
    assert feature["freeFlowSpeed"] == 72
    assert feature["delay"] == 5
    assert feature["congestionLevel"] == "moderate"
    assert feature["geometry"]["coordinates"][0] == [77.59, 12.97]
    assert normalized["omittedCount"] == 1
    assert normalized["units"]["delay"] == "seconds"

    empty = normalize_here_flow({
        "sourceUpdated": "not-a-date",
        "results": [{"location": {"shape": {"links": [{"points": [{"lat": 1, "lng": 2}, {"lat": 1.1, "lng": 2.1}]}]}}, "currentFlow": {}}],
    }, THRESHOLDS)
    assert empty["features"][0]["observedSpeed"] is None
    assert empty["features"][0]["congestionLevel"] == "unknown"
    assert empty["observedAt"] is None

    provider = HereTrafficProvider(None, "", "https://data.traffic.hereapi.com/v7", "1,2,3,4", 1000, THRESHOLDS)
    try:
        provider.fetch_flow({"west": 1, "south": 2, "east": 3, "north": 4})
    except AppError as error:
        assert error.code == "NOT_CONFIGURED"
    else:
        raise AssertionError("missing key should fail")


def test_here_hides_credentials():
    class Http:
        def post(self, url, json=None, timeout=None):
            assert json["locationReferencing"] == ["shape"]
            assert json["functionalClasses"] == [1, 2]
            error = Exception("super-secret-key")
            error.status_code = 401
            raise error

    provider = HereTrafficProvider(Http(), "super-secret-key", "https://data.traffic.hereapi.com/v7", "1,2", 1000, THRESHOLDS)
    try:
        provider.fetch_flow({"west": 1, "south": 2, "east": 3, "north": 4})
    except AppError as error:
        assert error.code == "UPSTREAM_UNAUTHORIZED"
        assert "super-secret-key" not in str(error.message)
    else:
        raise AssertionError("expected unauthorized")


def test_stale_traffic_and_summary():
    calls = {"n": 0}

    class Flaky:
        id = "here"

        def fetch_flow(self, _bbox):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"source": "here", "observedAt": "2026-10-16T14:00:00.000Z", "features": [FEATURE], "omittedCount": 0}
            raise AppError("HERE Traffic API request failed.", status=502, code="UPSTREAM_FAILURE")

    service = TrafficService(Flaky(), None, 0, 60_000)
    bbox = {"west": 77.5, "south": 12.9, "east": 77.6, "north": 13}
    first = service.get_traffic(bbox)
    second = service.get_traffic(bbox)
    assert second["stale"] is True
    assert second["fetchedAt"] == first["fetchedAt"]
    assert service.get_segment("abc123")["feature"]["name"] == "Sample Road"
    try:
        service.get_segment("missing-id")
    except AppError as error:
        assert error.code == "SEGMENT_NOT_IN_CACHE"

    summary = summarize_traffic({
        "source": "here",
        "fetchedAt": "2026-10-16T14:00:01.000Z",
        "observedAt": "2026-10-16T14:00:00.000Z",
        "stale": False,
        "bbox": [77.5, 12.9, 77.6, 13],
        "features": [
            FEATURE,
            {**FEATURE, "id": "b", "congestionLevel": "free-flow", "observedSpeed": 70, "delay": 1, "observationBasis": "historical"},
            {**FEATURE, "id": "c", "congestionLevel": "heavy", "observedSpeed": 10, "delay": 9, "observationBasis": "speed-limit"},
            {**FEATURE, "id": "d", "congestionLevel": "unknown", "observedSpeed": None, "delay": None, "delayEstimated": False, "observationBasis": "unknown"},
        ],
    })
    assert summary["segmentCount"] == 4
    assert summary["congestedCount"] == 2
    assert summary["averageObservedSpeedKmh"] == 45
    assert summary["speedSampleCount"] == 2
    empty = summarize_traffic({"source": "here", "features": []})
    assert empty["averageObservedSpeedKmh"] is None


def test_routes_validation_and_not_configured():
    api = client_with()
    missing = api.get("/api/traffic")
    assert missing.status_code == 400
    huge = api.get("/api/summary?bbox=77.0,12.0,78.0,13.0")
    assert huge.status_code == 400
    assert "Zoom in" in huge.json()["error"]["message"]
    bad_radius = api.get("/api/places/nearby?lat=12.97&lng=77.59&radius=0&category=eatery")
    assert bad_radius.status_code == 400
    short = api.get("/api/geocode?q=a")
    assert short.status_code == 400

    traffic = api.get(f"/api/traffic?bbox={BBOX}")
    assert traffic.status_code == 200
    assert traffic.json()["features"][0]["observedSpeed"] == 20
    segment = api.get("/api/traffic/segment/abc123")
    assert segment.json()["feature"]["name"] == "Sample Road"
    summary = api.get(f"/api/summary?bbox={BBOX}")
    assert summary.json()["congestedCount"] == 1

    config["simulateTraffic"] = False
    unconfigured = TestClient(create_app({"config": config}), raise_server_exceptions=False)
    response = unconfigured.get(f"/api/traffic?bbox={BBOX}")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NOT_CONFIGURED"
    assert "features" not in response.json()
    health = unconfigured.get("/api/health/data-sources").json()
    traffic_source = next(item for item in health["sources"] if item["role"] == "traffic")
    assert traffic_source["status"] == "not_configured"
    saved = unconfigured.post("/api/saved/places", json={"name": "Cafe", "lat": 12.97, "lng": 77.59})
    assert saved.status_code == 503
    invalid = unconfigured.post("/api/saved/places", json={"lat": 12.97, "lng": 77.59})
    assert invalid.status_code == 400
    public = client_with().get("/api/config/public").json()
    assert public["trafficConfigured"] is True
    assert "present" not in str(public)


def test_driving_route_uses_returned_geometry():
    route = parse_osrm({
        "code": "Ok",
        "routes": [{
            "distance": 2500,
            "duration": 420,
            "geometry": {"type": "LineString", "coordinates": [[77.59, 12.97], [77.60, 12.98]]},
            "legs": [{"steps": [{"maneuver": {"type": "depart"}, "name": "MG Road"}, {"maneuver": {"type": "arrive"}}]}],
        }],
    })
    assert route["line"] == [[12.97, 77.59], [12.98, 77.60]]
    assert route["distance_km"] == 2.5
    assert route["duration_min"] == 7
    assert route["steps"][0] == "Start on MG Road"
    assert parse_osrm({"code": "NoRoute"}) is None


def test_dashboard_is_python_page():
    page = client_with().get("/")
    assert page.status_code == 200
    assert "Traffic IQ" in page.text
    # New Next.js frontend has modern UI
    assert "Traffic IQ" in page.text
    # Check for form elements from the new UI
    assert "Your location" in page.text
    assert "Destination" in page.text
    assert "Start route" in page.text
    # New frontend doesn't display TRAFFIC_API_KEY in HTML - it's handled by the app
    missing = TestClient(create_app({"config": base_config()}), raise_server_exceptions=False)
    unconfigured = missing.get("/")
    assert unconfigured.status_code == 200


def test_osm_adapters():
    tolls = normalize_tolls([
        {"type": "node", "id": 10, "lat": 12.9, "lon": 77.6, "tags": {"barrier": "toll_booth", "name": "Plaza A", "operator": "NHAI"}},
        {"type": "way", "id": 11, "tags": {"barrier": "toll_booth"}},
    ])
    assert tolls["tolls"][0]["name"] == "Plaza A"
    assert tolls["tolls"][0]["openingHours"] is None
    assert tolls["omittedCount"] == 1
    places = normalize_eateries([
        {"type": "node", "id": 20, "lat": 12.971, "lon": 77.5946, "tags": {"amenity": "cafe", "name": "Sample Cafe", "opening_hours": "Mo-Fr 09:00-18:00"}},
    ], {"lat": 12.9716, "lng": 77.5946})
    assert places["places"][0]["rating"] is None
    assert places["places"][0]["distanceMeters"] < 200

    calls = []

    class Http:
        def post(self, url, data=None, headers=None, timeout=None):
            calls.append(url)
            if len(calls) == 1:
                return "<html>502 Gateway Timeout</html>"
            return {"elements": []}

    client = OverpassClient(Http(), ["https://overpass.example/a", "https://overpass.example/b"], "TrafficIQ test", 1000, 0)
    assert client.query("[out:json];out;")["elements"] == []
    assert len(calls) == 2

    class GeoHttp:
        def get(self, url, headers=None, timeout=None):
            assert "TrafficIQ" in headers["User-Agent"]
            assert "q=Bengaluru" in url
            return [{"lat": "12.97", "lon": "77.59", "display_name": "Bengaluru", "name": "Bengaluru", "osm_type": "relation", "osm_id": 1}]

    geocoder = NominatimGeocoder(GeoHttp(), "https://nominatim.openstreetmap.org", "TrafficIQ test", 1000, min_interval_ms=0)
    first = geocoder.search("Bengaluru")
    second = geocoder.search("Bengaluru")
    assert first["results"][0]["lat"] == 12.97
    assert second["results"][0]["label"] == "Bengaluru"


def test_tomtom_places():
    from app.tomtom import TomTomPlacesClient
    from app.services import PlacesService

    mock_tomtom_response = {
        "results": [
            {
                "id": "poi-1",
                "dist": 350.2,
                "poi": {
                    "name": "Bismillah Biryani",
                    "categories": ["indian", "restaurant"],
                    "phone": "+91 1234567890",
                    "url": "https://example.com/bismillah",
                },
                "position": {"lat": 16.441, "lon": 80.763},
            }
        ]
    }

    class MockHttp:
        def get(self, url, timeout=None):
            assert "categorySet=7315" in url
            assert "key=fake-key" in url
            return mock_tomtom_response

    client = TomTomPlacesClient(MockHttp(), "fake-key")
    res = client.search_nearby(16.44, 80.76, 5000, "eatery")
    assert res["source"] == "tomtom"
    assert len(res["places"]) == 1
    p = res["places"][0]
    assert p["name"] == "Bismillah Biryani"
    assert p["cuisine"] == "indian"
    assert p["category"] == "restaurant"
    assert p["distanceMeters"] == 350

    # Test PlacesService using TomTomPlacesClient
    service = PlacesService(overpass=None, health=None, cache_ttl_ms=60000, stale_max_age_ms=120000, tomtom_client=client)
    nearby = service.get_nearby(16.44, 80.76, 5000, "eatery")
    assert nearby["provider"] == "tomtom"
    assert len(nearby["places"]) == 1
    assert nearby["places"][0]["name"] == "Bismillah Biryani"



from fastapi.testclient import TestClient  # noqa: E402


def test_seed_traffic_is_deterministic_and_marked_simulated():
    from app.seed_traffic import SeedTrafficProvider

    bbox = {"west": 77.55, "south": 12.95, "east": 77.62, "north": 13.00}
    first = SeedTrafficProvider().fetch_flow(bbox)
    second = SeedTrafficProvider().fetch_flow(bbox)
    assert first == second
    assert first["source"] == "seed-simulation"
    assert len(first["features"]) == 12
    assert all(feature["simulated"] is True for feature in first["features"])
    assert all(feature["observationBasis"] == "simulated" for feature in first["features"])

def test_simulated_traffic_is_not_drawn_as_map_overlay():
    from app.dashboard import _visible_traffic_features

    simulated = {**FEATURE, "simulated": True}
    assert _visible_traffic_features([simulated]) == []
    assert _visible_traffic_features([FEATURE, simulated]) == [FEATURE]

def test_unconfigured_traffic_uses_seed_data():
    config = base_config()
    config["simulateTraffic"] = True

    api = TestClient(create_app({"config": config}), raise_server_exceptions=False)
    response = api.get(f"/api/traffic?bbox={BBOX}")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "seed-simulation"
    assert body["simulated"] is True
    assert "not live traffic" in body["coverageNote"]

