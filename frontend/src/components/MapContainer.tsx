"use client";

import React, { useMemo } from "react";

interface MapContainerProps {
  /** Query string (without leading "?") forwarded to the backend dashboard, e.g. lat=..&lng=..&traffic=1 */
  params: string;
}


// Render service references expose the hostname without a scheme. Folium's
// iframe needs an absolute URL when the backend is hosted separately.
const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL
    ? /^[a-z][a-z\d+.-]*:\/\//i.test(process.env.NEXT_PUBLIC_BACKEND_URL)
      ? process.env.NEXT_PUBLIC_BACKEND_URL
      : `https://${process.env.NEXT_PUBLIC_BACKEND_URL}`
    : process.env.NODE_ENV === "development"
      ? "http://localhost:5050"
      : "";

/**
 * Renders the Folium map produced by the FastAPI backend. The backend builds the
 * full interactive map (traffic lines, toll/eatery markers, driving route) and we
 * embed it via an iframe, per the project architecture.
 */
const MapContainer = ({ params }: MapContainerProps) => {
  const src = useMemo(
    () => `${BACKEND_URL}/?${params}${params ? "&" : ""}embed=1`,
    [params]
  );

  return (
    <div className="h-full w-full overflow-hidden bg-slate-100">
      <iframe
        title="Traffic map"
        src={src}
        className="h-full w-full border-0"
        loading="lazy"
      />
    </div>
  );
};

export default MapContainer;
