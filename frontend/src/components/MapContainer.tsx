"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import mapboxgl, { type GeoJSONSource, type Map as MapboxMap } from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

interface MapContainerProps { params: string }
type RoutePayload = { line?: [number, number][] };

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL
  ? (/^[a-z][a-z\d+.-]*:\/\//i.test(process.env.NEXT_PUBLIC_BACKEND_URL)
    ? process.env.NEXT_PUBLIC_BACKEND_URL
    : `https://${process.env.NEXT_PUBLIC_BACKEND_URL}`)
  : process.env.NODE_ENV === "development" ? "http://localhost:5050" : "";
const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN;
const DEFAULT_CENTER: [number, number] = [80.653, 16.5125];

export default function MapContainer({ params }: MapContainerProps) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<MapboxMap | null>(null);
  const [ready, setReady] = useState(false);
  const fallback = useMemo(() => `${BACKEND_URL}/?${params}${params ? "&" : ""}embed=1`, [params]);

  useEffect(() => {
    if (!MAPBOX_TOKEN || !element.current) return;
    mapboxgl.accessToken = MAPBOX_TOKEN;
    const instance = new mapboxgl.Map({ container: element.current, style: "mapbox://styles/mapbox/streets-v12", center: DEFAULT_CENTER, zoom: 13 });
    map.current = instance;
    instance.addControl(new mapboxgl.NavigationControl(), "top-right");
    instance.on("load", () => setReady(true));
    return () => { instance.remove(); map.current = null; setReady(false); };
  }, []);

  useEffect(() => {
    if (!MAPBOX_TOKEN || !ready || !map.current) return;
    const instance = map.current;
    const query = new URLSearchParams(params);
    const originLat = Number(query.get("lat"));
    const originLng = Number(query.get("lng"));
    const destinationLat = Number(query.get("dest_lat"));
    const destinationLng = Number(query.get("dest_lng"));
    const markers: mapboxgl.Marker[] = [];
    const valid = [originLat, originLng, destinationLat, destinationLng].every(Number.isFinite);
    if (valid) {
      markers.push(new mapboxgl.Marker({ color: "#16324f" }).setLngLat([originLng, originLat]).addTo(instance));
      markers.push(new mapboxgl.Marker({ color: "#9a3412" }).setLngLat([destinationLng, destinationLat]).addTo(instance));
      instance.fitBounds([[originLng, originLat], [destinationLng, destinationLat]], { padding: 70, maxZoom: 15 });
    }
    const controller = new AbortController();
    void (async () => {
      if (!valid) return;
      try {
        const routeUrl = `/api/route?origin_lat=${originLat}&origin_lng=${originLng}&dest_lat=${destinationLat}&dest_lng=${destinationLng}`;
        const response = await fetch(routeUrl, { signal: controller.signal });
        if (!response.ok) return;
        const route = await response.json() as RoutePayload;
        const coordinates: [number, number][] = (route.line || []).map(([lat, lng]): [number, number] => [lng, lat]);
        if (coordinates.length < 2) return;
        const data = { type: "Feature" as const, geometry: { type: "LineString" as const, coordinates }, properties: {} };
        const source = instance.getSource("route") as GeoJSONSource | undefined;
        if (source) source.setData(data);
        else {
          instance.addSource("route", { type: "geojson", data });
          instance.addLayer({ id: "route-line", type: "line", source: "route", paint: { "line-color": "#2563eb", "line-width": 6, "line-opacity": 0.9 } });
        }
        const longitudes = coordinates.map(([lng]) => lng);
        const latitudes = coordinates.map(([, lat]) => lat);
        instance.fitBounds([
          Math.min(...longitudes), Math.min(...latitudes),
          Math.max(...longitudes), Math.max(...latitudes),
        ], { padding: 70, maxZoom: 15 });
      } catch (error) {
        if (!(error instanceof Error && error.name === "AbortError")) console.error("Route unavailable", error);
      }
    })();
    return () => {
      controller.abort();
      markers.forEach((marker) => marker.remove());
      if (instance.getLayer("route-line")) instance.removeLayer("route-line");
      if (instance.getSource("route")) instance.removeSource("route");
    };
  }, [params, ready]);

  return (
    <div className="h-full w-full overflow-hidden bg-slate-100">
      {MAPBOX_TOKEN ? (
        <div ref={element} className="h-full w-full" aria-label="Route map" />
      ) : (
        <iframe title="Route map" src={fallback} className="h-full w-full border-0" loading="lazy" />
      )}
    </div>
  );
}
