import html
import math

import folium

from .errors import AppError
from .geo import haversine_meters
from .routing import fetch_driving_route
from .summary import summarize_traffic

COLORS = {
    "free-flow": "#1f9d55",
    "light": "#e0b000",
    "moderate": "#e07a1f",
    "heavy": "#d64545",
    "unknown": "#7d8794",
}
MAX_RADIUS_KM = 500


def render_dashboard(bundle, params):
    config = bundle["config"]
    center = {"lat": config["defaultLat"], "lng": config["defaultLng"]}
    notices = []
    origin_query = (params.get("origin") or "").strip()
    destination_query = (params.get("destination") or params.get("q") or "").strip()
    radius_m, radius_notice = _radius_meters(params.get("radius"))
    if radius_notice:
        notices.append(radius_notice)
    submitted = params.get("layers") == "1"
    embed = params.get("embed") == "1"

    origin = _coords(params.get("lat"), params.get("lng"), notices, "Your location")
    origin_results = []
    if origin is None and origin_query:
        origin, origin_results = _lookup(bundle["geocoder"], origin_query, "Your location", notices)
    if origin:
        # Reverse geocoding (Nominatim) is slow and, in embed mode, only feeds the
        # marker popup. Skip the network call for the iframe map so it renders fast.
        origin_label = (
            f"{origin['lat']:.5f}, {origin['lng']:.5f}"
            if embed
            else _place_label(bundle["geocoder"], origin, notices)
        )
    else:
        origin_label = origin_query

    destination = _coords(params.get("dest_lat"), params.get("dest_lng"), notices, "Destination")
    destination_results = []
    if destination and destination_query:
        destination["label"] = destination_query
    elif destination_query:
        destination, destination_results = _lookup(bundle["geocoder"], destination_query, "Destination", notices)

    focus = destination or origin or center
    nearby_mode = destination is None
    search_radius = radius_m if nearby_mode else 1500
    anchor = (origin or focus) if nearby_mode else destination
    covered = [origin, destination] if origin and destination else [anchor]
    bbox = _cover(covered, search_radius)
    asked = origin is not None or destination is not None
    traffic_on = asked and (params.get("traffic") == "1" if submitted else True)
    tolls_on = asked and (params.get("tolls") == "1" if submitted else True)
    places_on = asked and (params.get("places") == "1" if submitted else True)
    trip_km = None
    if origin and destination:
        trip_km = round(haversine_meters(origin, destination) / 1000, 1)
    driving = None
    if params.get("route") == "1":
        if not origin or not destination:
            notices.append("Add your location and a destination, then start the route.")
        else:
            try:
                driving = fetch_driving_route(
                    bundle["http"],
                    origin,
                    destination,
                    config["requestTimeoutMs"] / 1000,
                    config["appUserAgent"],
                )
            except AppError as error:
                notices.append(error.message)
    if driving and driving["line"]:
        bbox = _cover([{"lat": lat, "lng": lng} for lat, lng in driving["line"][:: max(1, len(driving["line"]) // 25)]], 800)
    traffic_payload = None
    toll_payload = None
    place_payload = None

    if traffic_on:
        try:
            traffic_payload = bundle["traffic"].get_traffic(bbox)
        except AppError as error:
            if error.code == "NOT_CONFIGURED":
                notices.append("Live traffic is not configured. Add TRAFFIC_API_KEY (or TOMTOM_API_KEY) and restart the app.")
            else:
                notices.append(error.message)
    if tolls_on:
        try:
            toll_payload = bundle["tolls"].get_tolls(bbox)
        except AppError as error:
            notices.append(error.message)
    if places_on:
        try:
            place_payload = bundle["places"].get_nearby(anchor["lat"], anchor["lng"], search_radius, "eatery")
        except AppError as error:
            notices.append(error.message)

    summary = summarize_traffic(traffic_payload) if traffic_payload else None
    features = (traffic_payload or {}).get("features") or []
    toll_rows = (toll_payload or {}).get("tolls") or []
    place_rows = (place_payload or {}).get("places") or []
    selected = next((item for item in features if item["id"] == params.get("segment")), None)

    frame = folium.Map(location=[focus["lat"], focus["lng"]], zoom_start=13, control_scale=True)
    frame.fit_bounds([[bbox["south"], bbox["west"]], [bbox["north"], bbox["east"]]])
    if nearby_mode and origin:
        folium.Circle(
            [origin["lat"], origin["lng"]],
            radius=radius_m,
            color="#1d4e89",
            weight=2,
            fill=True,
            fill_opacity=0.05,
        ).add_to(frame)
    route_state = _route_state(features, driving["line"]) if driving and driving["line"] else "clear"
    route_color = {"traffic": "#d64545", "medium": "#e09a1a"}.get(route_state, "#0b6b4f")
    if driving and driving["line"]:
        label = {"traffic": "Traffic on this route", "medium": "Medium traffic on this route"}.get(route_state, "Route")
        folium.PolyLine(driving["line"], color=route_color, weight=7, opacity=0.95, popup=label).add_to(frame)
        frame.fit_bounds(driving["line"])
    if not driving:
        for feature in features:
            points = [[point[1], point[0]] for point in feature["geometry"]["coordinates"]]
            _name, color = _traffic_mark(feature.get("congestionLevel"))
            if not color:
                continue
            folium.PolyLine(
                points,
                color=color,
                weight=6 if selected and selected["id"] == feature["id"] else 5,
                opacity=0.9,
                popup=folium.Popup(_segment_popup(feature), max_width=320),
            ).add_to(frame)
    for toll in toll_rows:
        folium.Marker(
            [toll["lat"], toll["lng"]],
            icon=_pin("T", "#c45c12"),
            popup=_plain(toll.get("name") or "Toll plaza", toll.get("kind"), toll.get("operator")),
        ).add_to(frame)
    for place in place_rows:
        folium.Marker(
            [place["lat"], place["lng"]],
            icon=_pin("E", "#0f7f78"),
            popup=_plain(place.get("name") or "Eatery", place.get("category"), f"{place.get('distanceMeters')} m"),
        ).add_to(frame)
    if origin:
        folium.CircleMarker(
            [origin["lat"], origin["lng"]],
            radius=8,
            color="#ffffff",
            weight=3,
            fill=True,
            fill_color="#16324f",
            popup=f"Your location: {_plain(origin_label)}",
        ).add_to(frame)
    if destination:
        folium.CircleMarker(
            [destination["lat"], destination["lng"]],
            radius=8,
            color="#ffffff",
            weight=3,
            fill=True,
            fill_color="#9a3412",
            popup=f"Destination: {_plain(destination.get('label') or destination_query)}",
        ).add_to(frame)

    map_html = frame.get_root().render()

    if embed:
        # Map-only document for embedding in the Next.js frontend iframe.
        return (
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            "<style>html,body{margin:0;height:100%}"
            ".folium-map,iframe{width:100%!important;height:100vh!important;border:0}</style>"
            f"</head><body>{map_html}</body></html>"
        )

    return _page({
        "origin_label": origin_label,
        "origin": origin,
        "destination_query": destination_query,
        "destination": destination,
        "trip_km": trip_km,
        "driving": driving,
        "center": focus,
        "radius_km": radius_m / 1000,
        "nearby_mode": nearby_mode,
        "ask_location": origin is None,
        "traffic_on": traffic_on,
        "tolls_on": tolls_on,
        "places_on": places_on,
        "notices": notices,
        "results": (destination_results or origin_results)[:5],
        "summary": summary,
        "features": features,
        "selected": selected,
        "tolls": toll_rows,
        "places": place_rows[:20],
        "map_html": map_html,
        "traffic_meta": traffic_payload,
    })


def _radius_meters(value):
    if value is None or value == "":
        return 3000, None
    try:
        kilometers = float(value)
    except (TypeError, ValueError):
        return 3000, "Enter the radius as a number of kilometers."
    if kilometers <= 0:
        return 3000, "Enter a radius greater than 0 km."
    if kilometers > MAX_RADIUS_KM:
        return MAX_RADIUS_KM * 1000, f"Radius is limited to {MAX_RADIUS_KM} km so the request can finish."
    return int(kilometers * 1000), None


def _coords(lat, lng, notices, label):
    if not lat or not lng:
        return None
    try:
        return {"lat": float(lat), "lng": float(lng)}
    except ValueError:
        notices.append(f"{label} is not a valid coordinate.")
        return None


def _lookup(geocoder, query, label, notices):
    try:
        found = geocoder.search(query)
    except AppError as error:
        notices.append(error.message)
        return None, []
    results = found.get("results") or []
    if not results:
        notices.append(f"No match was returned for {label.lower()}.")
        return None, []
    first = results[0]
    return {
        "lat": first["lat"],
        "lng": first["lng"],
        "label": first.get("label") or first.get("name") or query,
    }, results


def _place_label(geocoder, point, notices):
    try:
        found = geocoder.reverse(point["lat"], point["lng"])
    except AppError as error:
        notices.append(error.message)
        found = None
    result = (found or {}).get("result") or {}
    return result.get("label") or result.get("name") or f"{point['lat']:.5f}, {point['lng']:.5f}"


def _cover(points, radius_m):
    boxes = [_bbox_around(point["lat"], point["lng"], radius_m) for point in points]
    return {
        "west": min(box["west"] for box in boxes),
        "south": min(box["south"] for box in boxes),
        "east": max(box["east"] for box in boxes),
        "north": max(box["north"] for box in boxes),
    }


def _bbox_around(lat, lng, radius_m):
    delta_lat = radius_m / 111_320
    delta_lng = radius_m / (111_320 * max(math.cos(math.radians(lat)), 0.2))
    return {
        "west": max(-180, lng - delta_lng),
        "south": max(-90, lat - delta_lat),
        "east": min(180, lng + delta_lng),
        "north": min(90, lat + delta_lat),
    }


def _segment_popup(feature):
    rows = [
        ("Road", feature.get("name") or "Unnamed segment"),
        ("Level", _traffic_mark(feature.get("congestionLevel"))[0] or "No traffic"),
        ("Observed speed", _unit(feature.get("observedSpeed"), "km/h")),
        ("Free-flow speed", _unit(feature.get("freeFlowSpeed"), "km/h")),
        ("Delay", _unit(feature.get("delay"), "s") if feature.get("delayEstimated") else "Not available"),
        ("Jam factor", feature.get("jamFactor") if feature.get("jamFactor") is not None else "Not available"),
    ]
    body = "".join(f"<div><strong>{html.escape(label)}:</strong> {html.escape(str(value))}</div>" for label, value in rows)
    return body


def _traffic_mark(level):
    if level == "heavy":
        return "Traffic", "#d64545"
    if level == "moderate":
        return "Medium", "#e09a1a"
    return None, None


def _route_state(features, line):
    state = "clear"
    samples = line[:: max(1, len(line) // 40)]
    for feature in features:
        name, _color = _traffic_mark(feature.get("congestionLevel"))
        if not name:
            continue
        coordinates = feature.get("geometry", {}).get("coordinates") or []
        picked = coordinates[:: max(1, len(coordinates) // 6)]
        for lng, lat in picked:
            for route_lat, route_lng in samples:
                if haversine_meters({"lat": lat, "lng": lng}, {"lat": route_lat, "lng": route_lng}) <= 150:
                    if name == "Traffic":
                        return "traffic"
                    state = "medium"
                    break
    return state


def _pin(letter, color):
    return folium.DivIcon(
        icon_size=(28, 28),
        icon_anchor=(14, 14),
        html=(
            f'<div style="width:26px;height:26px;border-radius:50%;background:{color};color:white;'
            f'font:700 13px sans-serif;line-height:26px;text-align:center;border:2px solid white;'
            f'box-shadow:0 1px 4px rgba(0,0,0,.35)">{letter}</div>'
        ),
    )


def _plain(*parts):
    return " · ".join(html.escape(str(part)) for part in parts if part)


def _unit(value, unit):
    return "Not available" if value is None else f"{value} {unit}"


def _page(view):
    def checked(flag):
        return "checked" if flag else ""

    result_html = "".join(
        f"<li>{html.escape(item.get('name') or 'Unnamed')} — {html.escape(item.get('label') or '')}</li>"
        for item in view["results"]
    )
    driving = view["driving"]
    trip = ""
    if driving:
        distance = "Not available" if driving["distance_km"] is None else f"{driving['distance_km']} km"
        minutes = "Not available" if driving["duration_min"] is None else f"{driving['duration_min']} min"
        steps = "".join(f"<li>{html.escape(step)}</li>" for step in driving["steps"]) or "<li>The route has no turn list.</li>"
        trip = f"""<section class="card"><h2>Driving route</h2>
        <p>{distance} · about {minutes}</p>
        <ol>{steps}</ol></section>"""
    elif view["trip_km"] is not None:
        trip = f"<p class='notice'>Straight-line distance is {view['trip_km']} km. Choose Start route to follow the roads.</p>"
    origin_lat = "" if not view["origin"] else view["origin"]["lat"]
    origin_lng = "" if not view["origin"] else view["origin"]["lng"]
    notice_html = "".join(f"<p class='notice'>{html.escape(text)}</p>" for text in view["notices"])
    summary = view["summary"]
    if summary:
        distribution = summary["distribution"]
        summary_html = f"""
        <p>{distribution['heavy']} roads with traffic · {distribution['moderate']} medium.</p>
        <p>Average speed {_unit(summary['averageObservedSpeedKmh'], 'km/h')} · Average delay {_unit(summary['averageDelaySeconds'], 's')}</p>
        """
    else:
        summary_html = "<p>Summary appears after live traffic loads for this area.</p>"
    marked = []
    for item in view["features"]:
        label, _color = _traffic_mark(item.get("congestionLevel"))
        if label:
            marked.append((item, label))
    roads = "".join(
        f"<li><a href='?segment={html.escape(item['id'])}&lat={origin_lat}&lng={origin_lng}&radius={view['radius_km']}&layers=1&traffic=1&destination={html.escape(view['destination_query'])}'>{html.escape(item.get('name') or 'Unnamed segment')}</a> — {html.escape(label)}, {_unit(item.get('observedSpeed'), 'km/h')}</li>"
        for item, label in marked[:12]
    ) or "<li>No traffic or medium slowdown in this view.</li>"
    selected = view["selected"]
    if selected:
        selected_html = _segment_popup(selected)
    else:
        selected_html = "<p>Open a road name to read the values returned for that segment.</p>"
    places = "".join(
        f"<li>{html.escape(item.get('name') or 'Unnamed')} · {html.escape(item.get('category') or 'eatery')} · {item.get('distanceMeters')} m</li>"
        for item in view["places"]
    ) or (
        "<li>Set a radius and turn on eateries to see food near you.</li>"
        if view["nearby_mode"]
        else "<li>Turn on eateries to see food near the destination.</li>"
    )
    toll_count = len(view["tolls"])
    meta = view["traffic_meta"] or {}
    retrieved = meta.get("fetchedAt") or "Not available"
    observed = meta.get("observedAt") or "Not available"
    stale = "Stale result. " + (meta.get("staleReason") or "") if meta.get("stale") else ""
    auto_locate = "1" if view["ask_location"] else "0"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Traffic IQ</title>
  <style>
    :root {{ color-scheme: light; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Segoe UI", system-ui, sans-serif; color: #172033; background: #e8eef5; }}
    header {{
      display: flex; justify-content: space-between; align-items: center; gap: 16px;
      padding: 16px 22px; color: white;
      background: linear-gradient(120deg, #0e2744, #1d4e89);
    }}
    header strong {{ font-size: 1.25rem; letter-spacing: 0.02em; }}
    header p {{ margin: 4px 0 0; color: #d5e4f5; }}
    main {{ display: grid; grid-template-columns: 400px 1fr; min-height: calc(100vh - 74px); }}
    aside {{ padding: 16px; overflow: auto; }}
    form, .card {{
      background: white; border-radius: 16px; padding: 16px;
      box-shadow: 0 10px 30px rgba(20, 40, 70, 0.08);
    }}
    form {{ display: grid; gap: 12px; }}
    label {{ display: grid; gap: 6px; font-size: 0.82rem; font-weight: 650; color: #3d4d63; }}
    input {{
      width: 100%; font: inherit; font-weight: 450; color: #172033;
      padding: 11px 12px; border: 1px solid #d5deea; border-radius: 10px; background: #f8fafc;
    }}
    input:focus {{ outline: 2px solid #b9d0ea; border-color: #1d4e89; }}
    .actions {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
    #start-route {{ grid-column: 1 / -1; background: #0b6b4f; }}
    button {{
      font: inherit; font-weight: 650; padding: 11px 12px; border: 0; border-radius: 10px;
      background: #1d4e89; color: white; cursor: pointer;
    }}
    button.secondary {{ background: #e8eef6; color: #1d4e89; }}
    .radius-box {{ padding: 12px; border-radius: 12px; background: #f3f7fc; border: 1px solid #d7e4f3; }}
    .radius-box p {{ margin: 0 0 8px; font-weight: 450; color: #3d4d63; }}
    .layers {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .layers label {{
      display: flex; align-items: center; gap: 6px; padding: 8px 10px;
      border-radius: 999px; background: #f4f7fb; border: 1px solid #d5deea; font-weight: 600;
    }}
    .layers input {{ width: auto; }}
    .map {{ min-height: 640px; background: #d7e0ea; }}
    .map iframe, .folium-map {{ width: 100%; height: 100%; min-height: 640px; border: 0; }}
    .notice {{ margin: 0; background: #fff6e8; color: #6a4b16; border-radius: 10px; padding: 10px; }}
    .suggest {{ position: relative; }}
    #destination-suggestions {{
      position: absolute; z-index: 30; left: 0; right: 0; top: calc(100% - 2px);
      margin: 0; padding: 6px; list-style: none; background: white;
      border: 1px solid #d5deea; border-radius: 12px; max-height: 240px; overflow: auto;
      box-shadow: 0 12px 24px rgba(20, 40, 70, 0.12);
    }}
    #destination-suggestions button {{
      display: block; width: 100%; text-align: left; background: white; color: #172033;
      border: 0; border-radius: 8px; font-weight: 500;
    }}
    #destination-suggestions button:hover, #destination-suggestions button.active {{ background: #e7f0fa; }}
    .stack {{ display: grid; gap: 12px; margin-top: 12px; }}
    .card h2 {{ margin: 0 0 8px; font-size: 0.95rem; }}
    .card p, .card li {{ color: #3d4d63; line-height: 1.45; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 0; padding: 0; list-style: none; }}
    .legend li {{ display: flex; align-items: center; gap: 6px; }}
    .swatch {{ width: 12px; height: 12px; border-radius: 99px; display: inline-block; }}
    @media (max-width: 900px) {{
      main {{ grid-template-columns: 1fr; }}
      .actions {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <strong>Traffic IQ</strong>
      <p>Nearby places, or a trip to a destination.</p>
    </div>
  </header>
  <main>
    <aside>
      <form id="map-form" method="get">
        <label>Your location<input id="origin" name="origin" value="{html.escape(view['origin_label'])}" placeholder="Use my location or type a place"></label>
        <input type="hidden" name="lat" value="{origin_lat}">
        <input type="hidden" name="lng" value="{origin_lng}">
        <div class="suggest">
          <label>Destination<input id="destination" name="destination" autocomplete="off" value="{html.escape(view['destination_query'])}" placeholder="Optional. Where are you going?"></label>
          <ul id="destination-suggestions" hidden></ul>
        </div>
        <input type="hidden" name="dest_lat" value="{'' if not view['destination'] else view['destination']['lat']}">
        <input type="hidden" name="dest_lng" value="{'' if not view['destination'] else view['destination']['lng']}">
        <div id="radius-field" class="radius-box">
          <p>No destination yet. Choose how far to look around you for food, traffic, and tolls.</p>
          <label>Radius (km)<input id="radius" name="radius" type="number" min="0.1" step="0.1" value="{view['radius_km']}" required></label>
        </div>
        <input type="hidden" name="layers" value="1">
        <div class="layers">
          <label><input type="checkbox" name="traffic" value="1" {checked(view['traffic_on'])}> Traffic</label>
          <label><input type="checkbox" name="tolls" value="1" {checked(view['tolls_on'])}> Toll plazas</label>
          <label><input type="checkbox" name="places" value="1" {checked(view['places_on'])}> Eateries</label>
        </div>
        <div class="actions">
          <button type="submit">Update map</button>
          <button type="button" class="secondary" id="locate" data-auto="{auto_locate}">Use my location</button>
          <button type="submit" name="route" value="1" id="start-route">Start route</button>
        </div>
        <p id="location-status" class="notice" hidden></p>
      </form>
      <div class="stack">
        {notice_html}
        {trip}
        <section class="card"><h2>Place matches</h2><ul>{result_html or '<li>Type a destination, or leave it empty and set a radius.</li>'}</ul></section>
        <section class="card"><h2>Area summary</h2>{summary_html}<p>Retrieved {html.escape(str(retrieved))}. Provider time {html.escape(str(observed))}. {html.escape(stale)}</p></section>
        <section class="card"><h2>Roads</h2><ul>{roads}</ul></section>
        <section class="card"><h2>Selected road</h2>{selected_html}</section>
        <section class="card"><h2>Toll plazas</h2><p>{toll_count} in this view.</p></section>
        <section class="card"><h2>Nearby eateries</h2><p>Teal E marks are eateries. Orange T marks are toll plazas. A red route has traffic, an amber route is medium, and a green route has no traffic.</p><ul>{places}</ul></section>
      </div>
    </aside>
    <div class="map">{view['map_html']}</div>
  </main>
  <script>
    var destinationInput = document.getElementById('destination');
    var suggestionList = document.getElementById('destination-suggestions');
    var suggestionTimer = null;
    var suggestionRequest = null;
    var activeSuggestion = -1;
    function hideSuggestions() {{
      suggestionList.hidden = true;
      suggestionList.innerHTML = '';
      activeSuggestion = -1;
    }}
    function chooseSuggestion(place) {{
      destinationInput.value = place.label || place.name || '';
      document.querySelector('[name=dest_lat]').value = place.lat;
      document.querySelector('[name=dest_lng]').value = place.lng;
      hideSuggestions();
      syncRadius();
      document.getElementById('map-form').requestSubmit();
    }}
    function loadSuggestions(query) {{
      if (suggestionRequest) suggestionRequest.abort();
      suggestionRequest = new AbortController();
      fetch('/api/geocode?q=' + encodeURIComponent(query), {{ signal: suggestionRequest.signal }})
        .then(function (response) {{ return response.json(); }})
        .then(function (payload) {{
          var results = payload.results || [];
          suggestionList.innerHTML = '';
          suggestionList.hidden = false;
          if (!results.length) {{
            var empty = document.createElement('li');
            empty.textContent = 'No matching places';
            suggestionList.appendChild(empty);
            return;
          }}
          results.forEach(function (place) {{
            var item = document.createElement('li');
            var button = document.createElement('button');
            button.type = 'button';
            button.textContent = place.label || place.name || 'Unnamed place';
            button.addEventListener('mousedown', function (event) {{
              event.preventDefault();
              chooseSuggestion(place);
            }});
            item.appendChild(button);
            suggestionList.appendChild(item);
          }});
        }})
        .catch(function (error) {{
          if (error.name !== 'AbortError') hideSuggestions();
        }});
    }}
    destinationInput.addEventListener('input', function () {{
      document.querySelector('[name=dest_lat]').value = '';
      document.querySelector('[name=dest_lng]').value = '';
      syncRadius();
      window.clearTimeout(suggestionTimer);
      var query = destinationInput.value.trim();
      if (query.length < 2) {{
        hideSuggestions();
        return;
      }}
      suggestionTimer = window.setTimeout(function () {{ loadSuggestions(query); }}, 400);
    }});
    destinationInput.addEventListener('keydown', function (event) {{
      var buttons = suggestionList.querySelectorAll('button');
      if (suggestionList.hidden || !buttons.length) return;
      if (event.key === 'ArrowDown') {{
        event.preventDefault();
        activeSuggestion = Math.min(buttons.length - 1, activeSuggestion + 1);
      }} else if (event.key === 'ArrowUp') {{
        event.preventDefault();
        activeSuggestion = Math.max(0, activeSuggestion - 1);
      }} else if (event.key === 'Enter' && activeSuggestion >= 0) {{
        event.preventDefault();
        buttons[activeSuggestion].dispatchEvent(new MouseEvent('mousedown'));
        return;
      }} else if (event.key === 'Escape') {{
        hideSuggestions();
        return;
      }} else {{
        return;
      }}
      buttons.forEach(function (button, index) {{
        button.classList.toggle('active', index === activeSuggestion);
      }});
    }});
    document.addEventListener('click', function (event) {{
      if (!event.target.closest('.suggest')) hideSuggestions();
    }});
    document.getElementById('origin').addEventListener('input', function () {{
      document.querySelector('[name=lat]').value = '';
      document.querySelector('[name=lng]').value = '';
    }});
    function syncRadius() {{
      var hasDestination = destinationInput.value.trim().length > 0;
      var box = document.getElementById('radius-field');
      var input = document.getElementById('radius');
      box.hidden = hasDestination;
      input.required = !hasDestination;
      input.disabled = hasDestination;
    }}
    syncRadius();
    function showLocationStatus(text) {{
      var status = document.getElementById('location-status');
      status.hidden = !text;
      status.textContent = text;
    }}
    function useCoordinates(lat, lng) {{
      var params = new URLSearchParams(new FormData(document.getElementById('map-form')));
      params.set('lat', lat);
      params.set('lng', lng);
      params.set('origin', '');
      location.href = '/?' + params.toString();
    }}
    function useNetworkLocation() {{
      showLocationStatus('The browser did not return a position. Checking your network location.');
      fetch('https://get.geojs.io/v1/ip/geo.json')
        .then(function (response) {{ return response.json(); }})
        .then(function (data) {{
          if (!data.latitude || !data.longitude) {{
            throw new Error('missing');
          }}
          useCoordinates(data.latitude, data.longitude);
        }})
        .catch(function () {{
          showLocationStatus('Location could not be read. Allow location for this browser in system settings, or type your place.');
        }});
    }}
    function useMyLocation() {{
      showLocationStatus('Fetching your location…');
      if (!navigator.geolocation) {{
        useNetworkLocation();
        return;
      }}
      navigator.geolocation.getCurrentPosition(function (pos) {{
        useCoordinates(pos.coords.latitude, pos.coords.longitude);
      }}, function () {{
        useNetworkLocation();
      }}, {{ enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 }});
    }}
    document.getElementById('locate').onclick = useMyLocation;
    if (document.getElementById('locate').getAttribute('data-auto') === '1') {{
      useMyLocation();
    }}
  </script>
</body>
</html>"""
