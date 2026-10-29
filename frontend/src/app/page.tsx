
"use client";

import React, {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
} from "react";
import dynamic from "next/dynamic";
import { usePathname } from "next/navigation";
import { Icon, type IconName } from "@/components/Icons";
import SpeedGauge from "@/components/SpeedGauge";
import MobilityIndex from "@/components/MobilityIndex";

const MapContainer = dynamic(() => import("@/components/MapContainer"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-slate-100/50 dark:bg-slate-900/50 backdrop-blur-md">
      <span className="flex items-center gap-2.5 text-sm font-medium text-slate-500 dark:text-slate-400">
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 dark:border-slate-700 border-t-blue-500" />
        Initializing high-precision map…
      </span>
    </div>
  ),
});

const DEFAULT_LOCATION = { lat: 16.5125, lng: 80.653, label: "Kanuru–Vijayawada" };

const MAX_RADIUS_KM = 11.5;
const MIN_RADIUS_KM = 0.5;

const LEVELS = ["free-flow", "light", "moderate", "heavy", "unknown"] as const;

const CITY_HOTSPOTS = [
  { name: "MG Road Central", lat: 12.9756, lng: 77.6066, tag: "Central Hub" },
  { name: "Indiranagar 100ft", lat: 12.9784, lng: 77.6408, tag: "Arterial" },
  { name: "Koramangala 80ft", lat: 12.9352, lng: 77.6245, tag: "Transit Core" },
  { name: "Whitefield ITPL", lat: 12.9698, lng: 77.7499, tag: "Tech Corridor" },
  { name: "Hebbal Flyover", lat: 13.0358, lng: 77.5970, tag: "Expressway" },
  { name: "Electronic City", lat: 12.8399, lng: 77.6770, tag: "Toll Gateway" },
];

const CONGESTION_STYLES: Record<
  string,
  { label: string; dot: string; pill: string; bar: string }
> = {
  "free-flow": {
    label: "Free Flow",
    dot: "bg-emerald-500",
    pill: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20",
    bar: "bg-emerald-500",
  },
  light: {
    label: "Light",
    dot: "bg-yellow-400",
    pill: "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 border border-yellow-500/20",
    bar: "bg-yellow-400",
  },
  moderate: {
    label: "Moderate",
    dot: "bg-orange-500",
    pill: "bg-orange-500/10 text-orange-600 dark:text-orange-400 border border-orange-500/20",
    bar: "bg-orange-500",
  },
  heavy: {
    label: "Heavy",
    dot: "bg-rose-500",
    pill: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20",
    bar: "bg-rose-500",
  },
  unknown: {
    label: "Unsampled",
    dot: "bg-slate-400",
    pill: "bg-slate-500/10 text-slate-500 dark:text-slate-400 border border-slate-500/20",
    bar: "bg-slate-300 dark:bg-slate-700",
  },
};

interface PointState {
  lat: number | null;
  lng: number | null;
  query: string;
}

interface TrafficFeature {
  id: string;
  name?: string;
  congestionLevel?: string;
  congestionMethod?: string;
  observedSpeed?: number | null;
  freeFlowSpeed?: number | null;
  delay?: number | null;
  delayEstimated?: boolean | null;
  speedRatio?: number | null;
  jamFactor?: number | null;
  confidence?: number | null;
  observationBasis?: string | null;
  roadStatus?: string | null;
  functionalClass?: number | null;
  lengthMeters?: number | null;
  provider?: string | null;
  observedAt?: string | null;
  subSegmentCount?: number | null;
}

interface NearbyPlace {
  id?: string;
  name?: string;
  category?: string;
  cuisine?: string;
  distanceMeters?: number | null;
}

interface TollPlaza {
  id?: string;
  name?: string;
  kind?: string;
  operator?: string;
  road?: string;
}

interface AreaSummary {
  source?: string | null;
  fetchedAt?: string | null;
  stale?: boolean;
  staleReason?: string | null;
  segmentCount?: number;
  congestedCount?: number;
  distribution?: Record<string, number>;
  averageObservedSpeedKmh?: number | null;
  averageDelaySeconds?: number | null;
  attribution?: string | null;
  omittedCount?: number;
  coverageNote?: string | null;
}

async function requestJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal, cache: "no-store" });
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    // Graceful fallback
  }
  if (!response.ok) {
    const message = (payload as { error?: { message?: string } } | null)?.error
      ?.message;
    throw new Error(message || `Request failed (${response.status}).`);
  }
  return payload as T;
}

function congestionStyle(level?: string) {
  return CONGESTION_STYLES[level ?? "unknown"] ?? CONGESTION_STYLES.unknown;
}

function formatDistance(meters?: number | null) {
  if (meters == null || !Number.isFinite(meters)) return "—";
  return meters < 1000 ? `${meters} m` : `${(meters / 1000).toFixed(1)} km`;
}

function formatDelay(seconds?: number | null) {
  if (seconds == null || !Number.isFinite(seconds)) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  return `${Math.round(seconds / 60)} min`;
}

function formatTime(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function clampRadius(value: number) {
  if (!Number.isFinite(value)) return 3;
  return Math.min(MAX_RADIUS_KM, Math.max(MIN_RADIUS_KM, value));
}

function bboxAround(lat: number, lng: number, radiusMeters: number) {
  const latRad = (lat * Math.PI) / 180;
  const deltaLat = radiusMeters / 111320;
  const deltaLng =
    radiusMeters / (111320 * Math.max(Math.cos(latRad), 0.2));

  return {
    west: lng - deltaLng,
    south: lat - deltaLat,
    east: lng + deltaLng,
    north: lat + deltaLat,
  };
}

function LayerToggle({
  label,
  icon,
  checked,
  onChange,
  isDark,
}: {
  label: string;
  icon: IconName;
  checked: boolean;
  onChange: (checked: boolean) => void;
  isDark: boolean;
}) {
  return (
    <label
      className={`relative flex cursor-pointer flex-col items-center gap-1.5 rounded-xl border px-2 py-2.5 transition-all duration-200 select-none ${
        checked
          ? isDark
            ? "border-blue-500/40 bg-blue-500/15 text-blue-300 shadow-[0_0_15px_-3px_rgba(59,130,246,0.3)]"
            : "border-blue-200 bg-blue-50/90 text-blue-700 shadow-sm"
          : isDark
            ? "border-slate-800 bg-slate-800/40 text-slate-400 hover:border-slate-700 hover:bg-slate-800/80"
            : "border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:bg-slate-50"
      }`}
    >
      <input
        type="checkbox"
        className="sr-only"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <Icon name={icon} size={17} />
      <span className="text-[11px] font-semibold">{label}</span>
      <span
        aria-hidden="true"
        className={`absolute right-2 top-2 h-1.5 w-1.5 rounded-full transition-all duration-300 ${
          checked ? "bg-blue-500 ring-2 ring-blue-400/40" : "bg-slate-400/40"
        }`}
      />
    </label>
  );
}

function StatCard({
  label,
  value,
  unit,
  icon,
  subtext,
  isDark,
  accentColor = "blue",
}: {
  label: string;
  value: string | number;
  unit?: string;
  icon: IconName;
  subtext?: string;
  isDark: boolean;
  accentColor?: "blue" | "emerald" | "amber" | "rose";
}) {
  const accentGlow = {
    blue: "text-blue-500 dark:text-blue-400",
    emerald: "text-emerald-500 dark:text-emerald-400",
    amber: "text-amber-500 dark:text-amber-400",
    rose: "text-rose-500 dark:text-rose-400",
  }[accentColor];

  return (
    <div
      className={`group relative overflow-hidden rounded-xl border p-3.5 transition-all duration-300 hover:-translate-y-0.5 ${
        isDark
          ? "border-slate-800/80 bg-slate-900/60 hover:border-slate-700 hover:bg-slate-900/90 shadow-[0_4px_20px_-8px_rgba(0,0,0,0.5)]"
          : "border-slate-200/80 bg-white/90 hover:border-slate-300 hover:bg-white shadow-[0_4px_20px_-10px_rgba(15,23,42,0.1)]"
      } backdrop-blur-md`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
          {label}
        </span>
        <span
          className={`grid h-6 w-6 place-items-center rounded-lg ${
            isDark ? "bg-slate-800 text-slate-400" : "bg-slate-100 text-slate-500"
          } transition-colors group-hover:text-blue-500`}
        >
          <Icon name={icon} size={13} />
        </span>
      </div>
      <p className="mt-1.5 flex items-baseline gap-1 text-2xl font-black tracking-tight text-slate-900 dark:text-white">
        {value}
        {unit && (
          <span className="text-xs font-semibold text-slate-400">{unit}</span>
        )}
      </p>
      {subtext && (
        <p className={`mt-1 text-[10px] font-medium ${accentGlow}`}>
          {subtext}
        </p>
      )}
    </div>
  );
}

function BottleneckRow({
  feature,
  index,
  isDark,
  isSelected = false,
}: {
  feature: TrafficFeature;
  index: number;
  isDark: boolean;
  isSelected?: boolean;
}) {
  const style = congestionStyle(feature.congestionLevel);
  const isHeavy = feature.congestionLevel === "heavy";
  const speedDelta =
    feature.freeFlowSpeed && feature.observedSpeed
      ? Math.round(feature.observedSpeed - feature.freeFlowSpeed)
      : null;

  return (
    <div
      className={`group flex items-center justify-between gap-3 rounded-xl p-2.5 transition-all duration-200 ${
        isSelected
          ? isDark
            ? "bg-blue-500/10 border border-blue-500/40 ring-1 ring-blue-500/20"
            : "bg-blue-50 border border-blue-200 ring-1 ring-blue-300/50"
          : isDark
            ? "bg-slate-900/40 hover:bg-slate-800/70 border border-slate-800/50"
            : "bg-white/70 hover:bg-slate-50 border border-slate-100"
      }`}
    >
      <div className="flex min-w-0 items-center gap-3">
        <span
          className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg font-mono text-xs font-bold ${
            isSelected
              ? "bg-blue-500/20 text-blue-500 dark:text-blue-400"
              : isHeavy
                ? "bg-rose-500/15 text-rose-500 dark:text-rose-400"
                : isDark
                  ? "bg-slate-800 text-slate-400"
                  : "bg-slate-100 text-slate-600"
          }`}
        >
          #{index + 1}
        </span>
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold text-slate-800 dark:text-slate-200">
            {feature.name || `Arterial Segment ${index + 1}`}
          </p>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
            <span>
              {feature.observedSpeed != null
                ? `${feature.observedSpeed} km/h`
                : "Speed unavail."}
            </span>
            {feature.freeFlowSpeed && (
              <span className="text-slate-400/60">
                / {feature.freeFlowSpeed} km/h normal
              </span>
            )}
            {speedDelta !== null && speedDelta < 0 && (
              <span className="font-semibold text-rose-500 dark:text-rose-400">
                {speedDelta} km/h
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {feature.delay ? (
          <span className="font-mono text-xs font-bold text-rose-500 dark:text-rose-400">
            +{formatDelay(feature.delay)}
          </span>
        ) : null}
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${style.pill}`}
        >
          {style.label}
        </span>
        {isSelected && (
          <span className="hidden text-[10px] font-bold text-blue-500 dark:text-blue-400 sm:block">
            ▲ Details
          </span>
        )}
      </div>
    </div>
  );
}

function EmptyState({
  icon,
  title,
  detail,
  isDark,
}: {
  icon: IconName;
  title: string;
  detail: string;
  isDark: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border border-dashed p-6 text-center transition-all ${
        isDark
          ? "border-slate-800 bg-slate-900/30 text-slate-400"
          : "border-slate-200 bg-slate-50/60 text-slate-500"
      }`}
    >
      <span
        className={`mx-auto grid h-10 w-10 place-items-center rounded-xl shadow-sm ${
          isDark ? "bg-slate-800 text-slate-300" : "bg-white text-slate-500"
        }`}
      >
        <Icon name={icon} size={18} />
      </span>
      <p className="mt-3 text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
        {title}
      </p>
      <p className="mx-auto mt-1 max-w-[260px] text-xs leading-relaxed text-slate-400">
        {detail}
      </p>
    </div>
  );
}

function ProviderBadge({ source, isDark }: { source?: string | null; isDark: boolean }) {
  if (!source) return null;
  const isTomTom = source === "tomtom";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${
        isTomTom
          ? isDark
            ? "border-cyan-500/30 bg-cyan-500/10 text-cyan-400"
            : "border-cyan-600/25 bg-cyan-50 text-cyan-700"
          : isDark
            ? "border-indigo-500/30 bg-indigo-500/10 text-indigo-400"
            : "border-indigo-500/20 bg-indigo-50 text-indigo-700"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${isTomTom ? "bg-cyan-400" : "bg-indigo-400"}`} />
      {isTomTom ? "TomTom Flow" : source === "here" ? "HERE v7" : source}
    </span>
  );
}

const FRC_LABELS: Record<number, string> = {
  0: "Motorway",
  1: "Motorway",
  2: "Major Road",
  3: "Secondary Road",
  4: "Local Road",
  5: "Local Street",
};

function ConfidenceBar({ value, isDark }: { value?: number | null; isDark: boolean }) {
  if (value == null || !Number.isFinite(value)) return null;
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  const color = pct >= 80 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="flex items-center gap-2">
      <div className={`h-1.5 flex-1 rounded-full ${isDark ? "bg-slate-800" : "bg-slate-200"}`}>
        <div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 shrink-0 text-right font-mono text-[10px] font-bold">{pct}%</span>
    </div>
  );
}

function SegmentDetailCard({
  segment,
  isDark,
  onClose,
}: {
  segment: TrafficFeature;
  isDark: boolean;
  onClose: () => void;
}) {
  const style = congestionStyle(segment.congestionLevel);
  return (
    <div
      className={`rounded-2xl border p-4 transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 ${
        isDark
          ? "border-slate-700/80 bg-slate-900/90 shadow-[0_16px_50px_-12px_rgba(0,0,0,0.7)]"
          : "border-slate-200/90 bg-white shadow-[0_12px_40px_-12px_rgba(15,23,42,0.2)]"
      }`}
    >
      {/* Header */}
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-bold text-slate-900 dark:text-white">
              {segment.name || "Road Segment"}
            </h4>
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${style.pill}`}>
              {style.label}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            {segment.provider && (
              <ProviderBadge source={segment.provider} isDark={isDark} />
            )}
            {segment.functionalClass != null && (
              <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                isDark ? "border-slate-700 text-slate-400" : "border-slate-200 text-slate-500"
              }`}>
                {FRC_LABELS[segment.functionalClass] ?? `FRC ${segment.functionalClass}`}
              </span>
            )}
            {segment.roadStatus && segment.roadStatus !== "open" && (
              <span className="rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-bold text-rose-500 capitalize">
                {segment.roadStatus.replace(/-/g, " ")}
              </span>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close segment detail"
          className={`shrink-0 rounded-lg p-1.5 transition-colors ${
            isDark ? "hover:bg-slate-800 text-slate-400" : "hover:bg-slate-100 text-slate-500"
          }`}
        >
          <Icon name="x" size={14} />
        </button>
      </div>

      {/* Speed Metrics Row */}
      <div className="mb-3 grid grid-cols-2 gap-2">
        <div className={`rounded-xl p-3 ${isDark ? "bg-slate-800/60" : "bg-slate-50"}`}>
          <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Current Speed</p>
          <p className="mt-1 text-xl font-black text-slate-900 dark:text-white">
            {segment.observedSpeed != null ? (
              <>{segment.observedSpeed}<span className="ml-1 text-xs font-semibold text-slate-400">km/h</span></>
            ) : "—"}
          </p>
        </div>
        <div className={`rounded-xl p-3 ${isDark ? "bg-slate-800/60" : "bg-slate-50"}`}>
          <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Free-Flow Speed</p>
          <p className="mt-1 text-xl font-black text-slate-900 dark:text-white">
            {segment.freeFlowSpeed != null ? (
              <>{segment.freeFlowSpeed}<span className="ml-1 text-xs font-semibold text-slate-400">km/h</span></>
            ) : "—"}
          </p>
        </div>
      </div>

      {/* Detail Rows */}
      <div className={`space-y-2.5 rounded-xl p-3 ${isDark ? "bg-slate-800/40" : "bg-slate-50/80"}`}>
        {segment.delay != null && (
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] text-slate-400">Delay</span>
            <span className={`font-mono text-xs font-bold ${segment.delay > 0 ? "text-rose-500" : "text-emerald-500"}`}>
              {segment.delay > 0 ? "+" : ""}{formatDelay(segment.delay)}
            </span>
          </div>
        )}
        {segment.speedRatio != null && (
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] text-slate-400">Speed Ratio</span>
            <span className="font-mono text-xs font-bold">
              {(segment.speedRatio * 100).toFixed(0)}%
            </span>
          </div>
        )}
        {segment.lengthMeters != null && (
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] text-slate-400">Segment Length</span>
            <span className="font-mono text-xs font-bold">
              {formatDistance(segment.lengthMeters)}
            </span>
          </div>
        )}
        {segment.congestionMethod && (
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] text-slate-400">Detection Method</span>
            <span className="text-[11px] font-semibold capitalize text-slate-600 dark:text-slate-300">
              {segment.congestionMethod.replace(/-/g, " ")}
            </span>
          </div>
        )}
        {segment.jamFactor != null && (
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] text-slate-400">Jam Factor</span>
            <span className={`font-mono text-xs font-bold ${
              segment.jamFactor >= 8 ? "text-rose-500" :
              segment.jamFactor >= 5 ? "text-orange-500" :
              segment.jamFactor >= 3 ? "text-yellow-500" : "text-emerald-500"
            }`}>
              {segment.jamFactor.toFixed(1)} / 10
            </span>
          </div>
        )}
        {segment.confidence != null && (
          <div>
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="text-[11px] text-slate-400">Data Confidence</span>
              <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                {segment.observationBasis ?? "Measured"}
              </span>
            </div>
            <ConfidenceBar value={segment.confidence} isDark={isDark} />
          </div>
        )}
        {segment.subSegmentCount != null && (
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] text-slate-400">Sub-Segments</span>
            <span className="font-mono text-xs font-bold">{segment.subSegmentCount}</span>
          </div>
        )}
      </div>

      {/* Segment ID footer */}
      <p className="mt-2.5 truncate font-mono text-[9px] text-slate-400/60">
        ID: {segment.id}
      </p>
    </div>
  );
}

export default function Home() {
  const pathname = usePathname();

  // Dark/Light Theme state
  const [isDark, setIsDark] = useState<boolean>(false);

  useEffect(() => {
    const savedTheme = localStorage.getItem("traffic_iq_theme");

    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initialDark = savedTheme === "dark" || (!savedTheme && prefersDark);
    document.documentElement.classList.toggle("dark", initialDark);
    queueMicrotask(() => setIsDark(initialDark));
  }, []);

  const toggleTheme = () => {
    const nextDark = !isDark;
    setIsDark(nextDark);
    document.documentElement.classList.toggle("dark", nextDark);
    localStorage.setItem("traffic_iq_theme", nextDark ? "dark" : "light");
  };

  const [origin, setOrigin] = useState<PointState>({
    lat: DEFAULT_LOCATION.lat,
    lng: DEFAULT_LOCATION.lng,
    query: DEFAULT_LOCATION.label,
  });
  const [destination, setDestination] = useState<PointState>({
    lat: null,
    lng: null,
    query: "",
  });
  const [radius, setRadius] = useState(3);
  const [traffic, setTraffic] = useState(true);
  const [tolls, setTolls] = useState(false);
  const [places, setPlaces] = useState(false);
  const [route, setRoute] = useState(false);

  const [features, setFeatures] = useState<TrafficFeature[]>([]);
  const [summary, setSummary] = useState<AreaSummary | null>(null);
  const [tollList, setTollList] = useState<TollPlaza[]>([]);
  const [placeList, setPlaceList] = useState<NearbyPlace[]>([]);
  const [status, setStatus] = useState("");
  const [loadingTraffic, setLoadingTraffic] = useState(false);
  const [loadingTolls, setLoadingTolls] = useState(false);
  const [loadingPlaces, setLoadingPlaces] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [locating, setLocating] = useState(false);
  const [activeTab, setActiveTab] = useState<"pulse" | "bottlenecks" | "extras">("pulse");
  const [selectedSegment, setSelectedSegment] = useState<TrafficFeature | null>(null);


  const [view, setView] = useState({
    lat: DEFAULT_LOCATION.lat as number | null,
    lng: DEFAULT_LOCATION.lng as number | null,
    destLat: null as number | null,
    destLng: null as number | null,
  });
  const [hydrated, setHydrated] = useState(false);

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const num = (key: string): number | null => {
      const raw = params.get(key);
      if (raw === null || raw === "") return null;
      const value = parseFloat(raw);
      return Number.isFinite(value) ? value : null;
    };
    const lat = num("lat") ?? DEFAULT_LOCATION.lat;
    const lng = num("lng") ?? DEFAULT_LOCATION.lng;
    const destLat = num("dest_lat");
    const destLng = num("dest_lng");

    setOrigin({ lat, lng, query: params.get("origin") || DEFAULT_LOCATION.label });
    setDestination({
      lat: destLat,
      lng: destLng,
      query: params.get("destination") || "",
    });
    setView({ lat, lng, destLat, destLng });

    const radiusParam = num("radius");
    if (radiusParam) setRadius(clampRadius(radiusParam));
    if (params.has("traffic")) setTraffic(params.get("traffic") === "1");
    if (params.has("tolls")) setTolls(params.get("tolls") === "1");
    if (params.has("places")) setPlaces(params.get("places") === "1");
    if (params.has("route")) setRoute(params.get("route") === "1");
    setHydrated(true);
  }, []);

  const activeDestination = view.destLat !== null && view.destLng !== null;
  const nearbyMode = !activeDestination;

  const anchor = useMemo(() => {
    if (view.lat !== null && view.lng !== null) {
      return { lat: view.lat, lng: view.lng };
    }
    if (view.destLat !== null && view.destLng !== null) {
      return { lat: view.destLat, lng: view.destLng };
    }
    return DEFAULT_LOCATION;
  }, [view]);

  const hasAnchor =
    (view.lat !== null && view.lng !== null) ||
    (view.destLat !== null && view.destLng !== null);

  const searchRadius = activeDestination ? 1500 : Math.round(radius * 1000);
  const bbox = useMemo(
    () => bboxAround(anchor.lat, anchor.lng, searchRadius),
    [anchor, searchRadius]
  );
  const bboxString = `${bbox.west},${bbox.south},${bbox.east},${bbox.north}`;

  useEffect(() => {
    if (!hydrated) return;
    const params = new URLSearchParams();
    if (origin.lat !== null) params.set("lat", String(origin.lat));
    if (origin.lng !== null) params.set("lng", String(origin.lng));
    if (origin.query) params.set("origin", origin.query);
    if (destination.query) params.set("destination", destination.query);
    if (destination.lat !== null) params.set("dest_lat", String(destination.lat));
    if (destination.lng !== null) params.set("dest_lng", String(destination.lng));

    params.set("radius", String(radius));
    params.set("traffic", traffic ? "1" : "0");
    params.set("tolls", tolls ? "1" : "0");
    params.set("places", places ? "1" : "0");
    params.set("route", route ? "1" : "0");

    window.history.replaceState({}, "", `${pathname}?${params.toString()}`);
  }, [
    hydrated,
    origin,
    destination,
    radius,
    traffic,
    tolls,
    places,
    route,
    pathname,
  ]);

  const mapParams = useMemo(() => {
    const params = new URLSearchParams();
    if (view.lat !== null) params.set("lat", String(view.lat));
    if (view.lng !== null) params.set("lng", String(view.lng));
    if (view.destLat !== null) params.set("dest_lat", String(view.destLat));
    if (view.destLng !== null) params.set("dest_lng", String(view.destLng));

    params.set("radius", String(radius));
    params.set("layers", "1");
    params.set("traffic", traffic ? "1" : "0");
    params.set("tolls", tolls ? "1" : "0");
    params.set("places", places ? "1" : "0");
    if (route) params.set("route", "1");

    return params.toString();
  }, [view, radius, traffic, tolls, places, route]);

  const mapParamsDeferred = useDeferredValue(mapParams);

  useEffect(() => {
    if (!traffic || !hasAnchor) {
      setFeatures([]);
      setSummary(null);
      setSelectedSegment(null);
      setLoadingTraffic(false);
      return;
    }

    const controller = new AbortController();
    setLoadingTraffic(true);

    Promise.all([
      requestJson<{ features?: TrafficFeature[] }>(
        `/api/traffic?bbox=${bboxString}`,
        controller.signal
      ),
      requestJson<AreaSummary>(
        `/api/summary?bbox=${bboxString}`,
        controller.signal
      ),
    ])
      .then(([trafficData, summaryData]) => {
        setFeatures(
          Array.isArray(trafficData?.features) ? trafficData.features : []
        );
        setSummary(summaryData ?? null);
      })
      .catch((error: Error) => {
        if (controller.signal.aborted) return;
        setFeatures([]);
        setSummary(null);
        setStatus(`Traffic could not be loaded. ${error.message}`);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingTraffic(false);
      });

    return () => controller.abort();
  }, [traffic, hasAnchor, bboxString]);

  useEffect(() => {
    if (!tolls || !hasAnchor) {
      setTollList([]);
      setLoadingTolls(false);
      return;
    }

    const controller = new AbortController();
    setLoadingTolls(true);

    requestJson<{ tolls?: TollPlaza[] }>(
      `/api/tolls?bbox=${bboxString}`,
      controller.signal
    )
      .then((data) => setTollList(Array.isArray(data?.tolls) ? data.tolls : []))
      .catch((error: Error) => {
        if (controller.signal.aborted) return;
        setTollList([]);
        setStatus(`Toll plazas could not be loaded. ${error.message}`);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingTolls(false);
      });

    return () => controller.abort();
  }, [tolls, hasAnchor, bboxString]);

  useEffect(() => {
    if (!places || !hasAnchor) {
      setPlaceList([]);
      setLoadingPlaces(false);
      return;
    }

    const controller = new AbortController();
    setLoadingPlaces(true);

    requestJson<{ places?: NearbyPlace[] }>(
      `/api/places/nearby?lat=${anchor.lat}&lng=${anchor.lng}&radius=${searchRadius}&category=eatery`,
      controller.signal
    )
      .then((data) =>
        setPlaceList(Array.isArray(data?.places) ? data.places : [])
      )
      .catch((error: Error) => {
        if (controller.signal.aborted) return;
        setPlaceList([]);
        setStatus(`Nearby eateries could not be loaded. ${error.message}`);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingPlaces(false);
      });

    return () => controller.abort();
  }, [places, hasAnchor, anchor, searchRadius]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const resolvePoint = useCallback(async (query: string) => {
    const data = await requestJson<{
      results?: Array<{ lat: number; lng: number; label?: string; name?: string }>;
    }>(`/api/geocode?q=${encodeURIComponent(query)}`);
    const first = data?.results?.[0];

    return first
      ? {
          lat: first.lat,
          lng: first.lng,
          label: first.label || first.name || query,
        }
      : null;
  }, []);

  const handleUseMyLocation = useCallback(() => {
    setStatus("");
    setLocating(true);

    if (!navigator.geolocation) {
      setStatus("Geolocation is not supported by this browser.");
      setLocating(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const lat = position.coords.latitude;
        const lng = position.coords.longitude;
        setOrigin({ lat, lng, query: "" });
        setView((previous) => ({ ...previous, lat, lng }));
        setLocating(false);
      },
      () => {
        setStatus("Location permission was denied. Type a place or pick a preset.");
        setLocating(false);
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 }
    );
  }, []);

  const handleSelectHotspot = useCallback((spot: typeof CITY_HOTSPOTS[0]) => {
    setOrigin({ lat: spot.lat, lng: spot.lng, query: spot.name });
    setView((previous) => ({ ...previous, lat: spot.lat, lng: spot.lng }));
  }, []);

  const handleSubmit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      if (submitting) return;

      setStatus("");
      setSubmitting(true);
      const messages: string[] = [];
      let nextView = { ...view };

      try {
        if (origin.lat === null) {
          if (origin.query.trim()) {
            const resolved = await resolvePoint(origin.query.trim());
            if (resolved) {
              setOrigin((previous) => ({
                ...previous,
                lat: resolved.lat,
                lng: resolved.lng,
              }));
              nextView = { ...nextView, lat: resolved.lat, lng: resolved.lng };
            } else {
              messages.push(`No match found for "${origin.query.trim()}".`);
              nextView = { ...nextView, lat: null, lng: null };
            }
          } else {
            nextView = { ...nextView, lat: null, lng: null };
          }
        }

        if (destination.lat === null) {
          if (destination.query.trim()) {
            const resolved = await resolvePoint(destination.query.trim());
            if (resolved) {
              setDestination((previous) => ({
                ...previous,
                lat: resolved.lat,
                lng: resolved.lng,
              }));
              nextView = {
                ...nextView,
                destLat: resolved.lat,
                destLng: resolved.lng,
              };
            } else {
              messages.push(
                `No match found for "${destination.query.trim()}".`
              );
              nextView = { ...nextView, destLat: null, destLng: null };
            }
          } else {
            nextView = { ...nextView, destLat: null, destLng: null };
          }
        }
      } catch (error) {
        messages.push(`Search failed. ${(error as Error).message}`);
      }

      setView(nextView);
      if (nextView.destLat === null || nextView.destLng === null) {
        setRoute(false);
      }
      setSubmitting(false);
      if (messages.length) setStatus(messages.join(" "));
    },
    [origin, destination, view, resolvePoint, submitting]
  );

  const originLabel =
    origin.lat !== null && origin.lng !== null
      ? `Pinned: ${origin.lat.toFixed(4)}, ${origin.lng.toFixed(4)}`
      : origin.query || "Your location";

  const areaLabel = activeDestination
    ? `${origin.query || "Start"} → ${destination.query || "Destination"}`
    : origin.query ||
      (origin.lat !== null && origin.lng !== null
        ? originLabel
        : `${DEFAULT_LOCATION.label} · Live View`);

  const distribution = summary?.distribution ?? {};
  const avgSpeed = summary?.averageObservedSpeedKmh;
  const updatedAt = formatTime(summary?.fetchedAt);
  const canRoute =
    view.lat !== null && view.lng !== null && activeDestination;
  const trafficSourceLabel =
    summary?.source === "tomtom"
      ? "TomTom Traffic Flow"
      : summary?.source === "here"
        ? "HERE Traffic v7"
        : "Live Telemetry";

  // Sorted bottlenecks (congested or highest delay)
  const sortedBottlenecks = useMemo(() => {
    return [...features]
      .sort((a, b) => {
        const delayA = a.delay ?? 0;
        const delayB = b.delay ?? 0;
        return delayB - delayA;
      })
      .slice(0, 10);
  }, [features]);

  // Overall primary congestion status
  const predominantLevel = useMemo(() => {
    if (!summary?.distribution) return "free-flow";
    const { heavy = 0, moderate = 0, light = 0, "free-flow": free = 0 } = summary.distribution;
    if (heavy > 0) return "heavy";
    if (moderate > 0) return "moderate";
    if (light > free) return "light";
    return "free-flow";
  }, [summary]);

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDark ? "bg-[#090d16] text-slate-100" : "bg-[#f8fafc] text-slate-900"}`}>
      {/* Ambient background glows */}
      <div
        aria-hidden="true"
        className={`pointer-events-none fixed inset-0 -z-10 transition-opacity duration-700 ${
          isDark
            ? "bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(59,130,246,0.15),rgba(255,255,255,0))] opacity-100"
            : "bg-[radial-gradient(circle_at_12%_0%,rgba(59,130,246,0.12),transparent_34%),radial-gradient(circle_at_88%_18%,rgba(20,184,166,0.08),transparent_28%)] opacity-100"
        }`}
      />

      {/* Top Navigation Header */}
      <header
        className={`sticky top-0 z-40 border-b backdrop-blur-xl transition-all duration-300 ${
          isDark
            ? "border-slate-800/80 bg-slate-950/80 shadow-[0_4px_30px_rgba(0,0,0,0.5)]"
            : "border-slate-200/80 bg-white/85 shadow-sm"
        }`}
      >
        <div className="mx-auto flex h-[72px] max-w-[1600px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          {/* Logo & Product Title */}
          <div className="flex min-w-0 items-center gap-3">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-500 text-white shadow-lg shadow-blue-500/25">
              <Icon name="route" size={20} />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-black tracking-tight">
                  Traffic<span className="text-blue-500">IQ</span>
                </h1>
                <span className="hidden rounded-full border border-blue-500/30 bg-blue-500/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-blue-500 sm:inline-block">
                  v2.0 Pro
                </span>
              </div>
              <p className="truncate text-[10px] font-medium tracking-wider text-slate-400">
                City Velocity & Mobility Telemetry
              </p>
            </div>
          </div>

          {/* Right Action Bar: Status Pill & Theme Switcher */}
          <div className="flex items-center gap-3">
            {/* Live Data Badge */}
            <div
              className={`hidden items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold sm:inline-flex ${
                isDark
                  ? "border-slate-800 bg-slate-900/80 text-slate-300"
                  : "border-slate-200 bg-white text-slate-700 shadow-sm"
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  traffic ? "bg-emerald-500 animate-pulse" : "bg-slate-400"
                }`}
              />
              <span className="text-[11px] font-medium">
                {traffic ? trafficSourceLabel : "Telemetry Paused"}
              </span>
            </div>

            {/* Dark / Light Toggle Button */}
            <button
              id="theme-toggle-btn"
              type="button"
              onClick={toggleTheme}
              aria-label="Toggle dark/light mode"
              className={`flex h-10 w-10 items-center justify-center rounded-xl border transition-all duration-200 ${
                isDark
                  ? "border-slate-800 bg-slate-900 text-yellow-400 hover:border-slate-700 hover:bg-slate-800 shadow-sm"
                  : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-100 shadow-sm"
              }`}
            >
              <Icon name={isDark ? "sun" : "moon"} size={17} />
            </button>
          </div>
        </div>
      </header>

      {/* Main App Layout */}
      <main className="mx-auto max-w-[1600px] px-4 pb-12 pt-6 sm:px-6 lg:px-8">
        {/* Hero Section & City Presets */}
        <div className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-2 w-2 rounded-full bg-blue-500 animate-ping" />
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-blue-500">
                Live Urban Intelligence
              </p>
            </div>
            <h2 className="mt-1 text-2xl font-black tracking-tight sm:text-3xl lg:text-4xl">
              Realtime Traffic Velocity
            </h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400 max-w-xl">
              High-frequency flow telemetry, dynamic speed metrics, toll plazas, and corridor bottlenecks.
            </p>
          </div>

          {/* Quick Location Pills */}
          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Quick Telemetry Hotspots
            </span>
            <div className="flex flex-wrap gap-1.5">
              {CITY_HOTSPOTS.map((spot) => (
                <button
                  key={spot.name}
                  type="button"
                  onClick={() => handleSelectHotspot(spot)}
                  className={`rounded-full border px-3 py-1 text-[11px] font-semibold transition-all duration-200 ${
                    origin.query === spot.name
                      ? "border-blue-500 bg-blue-500 text-white shadow-md shadow-blue-500/25"
                      : isDark
                        ? "border-slate-800 bg-slate-900/70 text-slate-300 hover:border-slate-700 hover:bg-slate-800"
                        : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50 shadow-sm"
                  }`}
                >
                  {spot.name}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Global Error Banner */}
        {status && (
          <div
            role="status"
            aria-live="polite"
            className="mb-6 flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-300 shadow-sm backdrop-blur-md"
          >
            <Icon
              name="alert"
              size={18}
              className="mt-0.5 shrink-0 text-amber-500"
            />
            <p className="flex-1 leading-relaxed text-xs">{status}</p>
            <button
              type="button"
              aria-label="Dismiss message"
              onClick={() => setStatus("")}
              className="rounded-lg p-1 text-amber-500 transition hover:bg-amber-500/20"
            >
              <Icon name="x" size={15} />
            </button>
          </div>
        )}

        {/* Dashboard 2-Column Grid */}
        <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
          {/* Left Control Sidebar */}
          <aside className="space-y-5">
            {/* Control Panel Card */}
            <form
              onSubmit={handleSubmit}
              className={`rounded-2xl border p-5 backdrop-blur-xl transition-all duration-300 ${
                isDark
                  ? "border-slate-800/80 bg-slate-900/70 shadow-[0_12px_40px_-15px_rgba(0,0,0,0.6)]"
                  : "border-slate-200/80 bg-white/90 shadow-[0_12px_40px_-20px_rgba(15,23,42,0.15)]"
              }`}
            >
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="grid h-7 w-7 place-items-center rounded-lg bg-blue-500/10 text-blue-500">
                    <Icon name="compass" size={16} />
                  </span>
                  <div>
                    <h3 className="text-sm font-bold tracking-tight">
                      Navigation & Scope
                    </h3>
                  </div>
                </div>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                    nearbyMode
                      ? "bg-blue-500/10 text-blue-500 border border-blue-500/20"
                      : "bg-indigo-500/10 text-indigo-500 border border-indigo-500/20"
                  }`}
                >
                  {nearbyMode ? "Radius Mode" : "Corridor Route"}
                </span>
              </div>

              {/* Input Fields */}
              <div className="space-y-3.5">
                {/* Starting Point Input */}
                <div>
                  <label
                    htmlFor="origin"
                    className="mb-1.5 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-400"
                  >
                    <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
                    Starting Point
                  </label>
                  <div className="relative">
                    <Icon
                      name="search"
                      size={15}
                      className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                    />
                    <input
                      id="origin"
                      className={`h-11 w-full rounded-xl border pl-9 pr-3 text-sm outline-none transition-all ${
                        isDark
                          ? "border-slate-800 bg-slate-950/80 text-white placeholder:text-slate-500 focus:border-blue-500 focus:ring-4 focus:ring-blue-500/15"
                          : "border-slate-200 bg-slate-50/80 text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-500/10"
                      }`}
                      placeholder="Search point or use hotspot..."
                      autoComplete="off"
                      value={
                        origin.query ||
                        (origin.lat !== null ? originLabel : "")
                      }
                      onChange={(event) =>
                        setOrigin({
                          lat: null,
                          lng: null,
                          query: event.target.value,
                        })
                      }
                    />
                  </div>
                </div>

                {/* Destination Input */}
                <div>
                  <div className="mb-1.5 flex items-center justify-between">
                    <label
                      htmlFor="destination"
                      className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-400"
                    >
                      <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
                      Destination
                    </label>
                    <span className="text-[10px] font-medium text-slate-400">
                      Optional Route
                    </span>
                  </div>
                  <div className="relative">
                    <Icon
                      name="pin"
                      size={15}
                      className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                    />
                    <input
                      id="destination"
                      className={`h-11 w-full rounded-xl border pl-9 pr-3 text-sm outline-none transition-all ${
                        isDark
                          ? "border-slate-800 bg-slate-950/80 text-white placeholder:text-slate-500 focus:border-blue-500 focus:ring-4 focus:ring-blue-500/15"
                          : "border-slate-200 bg-slate-50/80 text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-500/10"
                      }`}
                      placeholder="Destination for driving route..."
                      autoComplete="off"
                      value={destination.query}
                      onChange={(event) =>
                        setDestination({
                          lat: null,
                          lng: null,
                          query: event.target.value,
                        })
                      }
                    />
                  </div>
                </div>

                {/* Radius Slider (Only in Nearby Mode) */}
                {nearbyMode && (
                  <div
                    className={`rounded-xl border p-3.5 transition-all ${
                      isDark
                        ? "border-slate-800/80 bg-slate-950/60"
                        : "border-slate-200 bg-slate-50/80"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <label
                        htmlFor="radius"
                        className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-400"
                      >
                        <Icon name="compass" size={13} />
                        Coverage Radius
                      </label>
                      <span
                        className={`rounded-md px-2 py-0.5 text-xs font-black ${
                          isDark
                            ? "bg-slate-800 text-blue-400"
                            : "bg-white text-blue-600 shadow-sm"
                        }`}
                      >
                        {radius.toFixed(1)} km
                      </span>
                    </div>
                    <input
                      id="radius"
                      type="range"
                      min={MIN_RADIUS_KM}
                      max={MAX_RADIUS_KM}
                      step="0.5"
                      value={radius}
                      onChange={(event) =>
                        setRadius(clampRadius(Number(event.target.value)))
                      }
                      className="mt-3 h-1.5 w-full cursor-pointer appearance-none rounded-full bg-slate-300 dark:bg-slate-700 accent-blue-600"
                    />
                    <div className="mt-1 flex justify-between text-[10px] font-medium text-slate-400">
                      <span>{MIN_RADIUS_KM} km</span>
                      <span>{MAX_RADIUS_KM} km</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Layer Toggles */}
              <div className="mt-4">
                <p className="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  <Icon name="layers" size={12} />
                  Active Telemetry Layers
                </p>
                <div className="grid grid-cols-3 gap-2">
                  <LayerToggle
                    label="Traffic Flow"
                    icon="traffic"
                    checked={traffic}
                    onChange={setTraffic}
                    isDark={isDark}
                  />
                  <LayerToggle
                    label="Toll Plazas"
                    icon="toll"
                    checked={tolls}
                    onChange={setTolls}
                    isDark={isDark}
                  />
                  <LayerToggle
                    label="Eateries"
                    icon="food"
                    checked={places}
                    onChange={setPlaces}
                    isDark={isDark}
                  />
                </div>
              </div>

              {/* Action Buttons */}
              <div className="mt-4 grid grid-cols-2 gap-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-4 text-xs font-bold uppercase tracking-wider text-white shadow-lg shadow-blue-500/25 transition-all duration-200 hover:from-blue-700 hover:to-indigo-700 active:scale-[0.98] disabled:opacity-50"
                >
                  {submitting ? (
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                  ) : (
                    <Icon name="refresh" size={15} />
                  )}
                  {submitting ? "Updating…" : "Sync Map"}
                </button>

                <button
                  type="button"
                  onClick={handleUseMyLocation}
                  disabled={locating}
                  className={`inline-flex h-11 items-center justify-center gap-2 rounded-xl border px-4 text-xs font-bold uppercase tracking-wider transition-all duration-200 active:scale-[0.98] ${
                    isDark
                      ? "border-slate-800 bg-slate-900 text-slate-300 hover:border-slate-700 hover:bg-slate-800"
                      : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50 shadow-sm"
                  }`}
                >
                  {locating ? (
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-400 border-t-slate-700 dark:border-t-slate-300" />
                  ) : (
                    <Icon name="locate" size={15} />
                  )}
                  {locating ? "Locating…" : "My GPS"}
                </button>
              </div>

              {/* Route Toggle Button */}
              <button
                type="button"
                disabled={!canRoute}
                onClick={() => setRoute((value) => !value)}
                className={`mt-2.5 inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all duration-200 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40 ${
                  route && canRoute
                    ? "border-rose-500/30 bg-rose-500/15 text-rose-500 dark:text-rose-400 hover:bg-rose-500/20"
                    : "border-emerald-500/30 bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/20"
                }`}
              >
                <Icon name="route" size={15} />
                {route && canRoute ? "Hide Corridor Route" : "Preview Driving Route"}
              </button>
            </form>

            {/* Dynamic Speed Gauge */}
            <SpeedGauge
              speedKmh={avgSpeed}
              delaySeconds={summary?.averageDelaySeconds}
              congestionLevel={predominantLevel}
              isDark={isDark}
            />

            {/* Mobility Health Index */}
            <MobilityIndex
              distribution={distribution}
              segmentCount={summary?.segmentCount ?? 0}
              congestedCount={summary?.congestedCount ?? 0}
              isDark={isDark}
              sourceLabel={trafficSourceLabel}
              updatedAt={updatedAt}
              isLive={traffic && !loadingTraffic}
            />

            {/* Quick Stats Grid */}
            <div className="grid grid-cols-2 gap-2.5">
              <StatCard
                label="Congested"
                value={summary?.congestedCount ?? 0}
                unit="segments"
                icon="traffic"
                subtext={
                  summary?.congestedCount
                    ? `${summary.congestedCount} bottleneck zones`
                    : "Zero major stalls"
                }
                isDark={isDark}
                accentColor={summary?.congestedCount ? "rose" : "emerald"}
              />
              <StatCard
                label="Avg Delay"
                value={formatDelay(summary?.averageDelaySeconds)}
                icon="clock"
                subtext="per road segment"
                isDark={isDark}
                accentColor={
                  (summary?.averageDelaySeconds ?? 0) > 60 ? "amber" : "blue"
                }
              />
            </div>
          </aside>

          {/* Right Map & Detailed Analytics Section */}
          <section className="flex flex-col space-y-5">
            {/* Embedded Folium Interactive Map Container */}
            <div
              className={`flex flex-col overflow-hidden rounded-2xl border backdrop-blur-xl transition-all duration-300 ${
                isDark
                  ? "border-slate-800/80 bg-slate-900/80 shadow-[0_12px_50px_-15px_rgba(0,0,0,0.7)]"
                  : "border-slate-200/80 bg-white/95 shadow-[0_12px_50px_-20px_rgba(15,23,42,0.15)]"
              }`}
            >
              {/* Map Bar Header */}
              <div
                className={`flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3.5 transition-colors ${
                  isDark ? "border-slate-800/80" : "border-slate-200/80"
                }`}
              >
                <div className="flex min-w-0 items-center gap-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-gradient-to-tr from-slate-900 to-slate-800 text-white shadow-md">
                    <Icon name="map" size={17} />
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-bold text-slate-800 dark:text-slate-100">
                        {areaLabel}
                      </p>
                      {loadingTraffic && (
                        <span className="flex h-2 w-2 rounded-full bg-blue-500 animate-ping" />
                      )}
                    </div>
                    <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                      Center: {anchor.lat.toFixed(4)}, {anchor.lng.toFixed(4)}
                    </p>
                  </div>
                </div>

                {/* Layer Badges */}
                <div className="flex flex-wrap items-center gap-1.5">
                  {traffic && (
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-500/20 bg-rose-500/10 px-2.5 py-1 text-[10px] font-bold text-rose-500 dark:text-rose-400">
                      <Icon name="traffic" size={11} />
                      Traffic Flow
                    </span>
                  )}
                  {tolls && (
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-orange-500/20 bg-orange-500/10 px-2.5 py-1 text-[10px] font-bold text-orange-500 dark:text-orange-400">
                      <Icon name="toll" size={11} />
                      Tolls
                    </span>
                  )}
                  {places && (
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-teal-500/20 bg-teal-500/10 px-2.5 py-1 text-[10px] font-bold text-teal-600 dark:text-teal-400">
                      <Icon name="food" size={11} />
                      Eateries
                    </span>
                  )}
                  {route && canRoute && (
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-2.5 py-1 text-[10px] font-bold text-indigo-500">
                      <Icon name="route" size={11} />
                      Corridor Active
                    </span>
                  )}
                </div>
              </div>

              {/* Map Iframe Body */}
              <div className="relative h-[540px] w-full min-h-0 sm:h-[600px] xl:h-[680px]">
                <MapContainer params={mapParamsDeferred} />
              </div>

              {/* Map Bar Footer */}
              <div
                className={`flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t px-5 py-3 text-[11px] font-medium transition-colors ${
                  isDark
                    ? "border-slate-800/80 bg-slate-950/40 text-slate-400"
                    : "border-slate-200/80 bg-slate-50/50 text-slate-500"
                }`}
              >
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  {LEVELS.slice(0, 4).map((level) => (
                    <span key={level} className="inline-flex items-center gap-1.5">
                      <span
                        className={`h-2 w-2 rounded-full ${CONGESTION_STYLES[level].dot}`}
                      />
                      <span className="capitalize">{CONGESTION_STYLES[level].label}</span>
                    </span>
                  ))}
                </div>
                <p className="text-[10px] text-slate-400">
                  © OpenStreetMap Contributors · {trafficSourceLabel}
                </p>
                {summary?.attribution && (
                  <span className="hidden text-[10px] text-slate-400 sm:block">
                    {summary.attribution}
                  </span>
                )}
              </div>
            </div>

            {/* Bottom Tabbed Detail Section: Bottlenecks / Tolls / Eateries */}
            <div
              className={`rounded-2xl border p-5 backdrop-blur-xl transition-all duration-300 ${
                isDark
                  ? "border-slate-800/80 bg-slate-900/70 shadow-[0_12px_40px_-15px_rgba(0,0,0,0.6)]"
                  : "border-slate-200/80 bg-white/90 shadow-[0_12px_40px_-20px_rgba(15,23,42,0.15)]"
              }`}
            >
              {/* Tab Navigation */}
              <div className="flex items-center justify-between gap-4 border-b pb-4 border-slate-200/80 dark:border-slate-800">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setActiveTab("pulse")}
                    className={`flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-bold uppercase tracking-wider transition-all ${
                      activeTab === "pulse"
                        ? "bg-blue-500 text-white shadow-md shadow-blue-500/25"
                        : isDark
                          ? "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                          : "text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    <Icon name="gauge" size={14} />
                    Bottlenecks ({sortedBottlenecks.length})
                  </button>

                  {tolls && (
                    <button
                      type="button"
                      onClick={() => setActiveTab("extras")}
                      className={`flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-bold uppercase tracking-wider transition-all ${
                        activeTab === "extras"
                          ? "bg-orange-500 text-white shadow-md shadow-orange-500/25"
                          : isDark
                            ? "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                            : "text-slate-600 hover:bg-slate-100"
                      }`}
                    >
                      <Icon name="toll" size={14} />
                      Toll Plazas ({tollList.length})
                    </button>
                  )}

                  {places && (
                    <button
                      type="button"
                      onClick={() => setActiveTab("bottlenecks")}
                      className={`flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-bold uppercase tracking-wider transition-all ${
                        activeTab === "bottlenecks"
                          ? "bg-teal-500 text-white shadow-md shadow-teal-500/25"
                          : isDark
                            ? "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                            : "text-slate-600 hover:bg-slate-100"
                      }`}
                    >
                      <Icon name="food" size={14} />
                      Eateries ({placeList.length})
                    </button>
                  )}
                </div>

                <span className="text-[11px] font-mono text-slate-400">
                  {features.length} segments analyzed
                </span>
              </div>

              {/* Tab Contents */}
              <div className="pt-4">
                {activeTab === "pulse" && (
                  <div className="space-y-3">
                    {/* Selected Segment Detail Card */}
                    {selectedSegment && (
                      <SegmentDetailCard
                        segment={selectedSegment}
                        isDark={isDark}
                        onClose={() => setSelectedSegment(null)}
                      />
                    )}

                    {/* Coverage / stale notice */}
                    {summary?.coverageNote && !selectedSegment && (
                      <div className={`flex items-start gap-2.5 rounded-xl border px-3.5 py-2.5 text-[11px] ${
                        isDark
                          ? "border-cyan-500/20 bg-cyan-500/5 text-cyan-400/80"
                          : "border-cyan-600/20 bg-cyan-50 text-cyan-700"
                      }`}>
                        <svg className="mt-0.5 h-3.5 w-3.5 shrink-0" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z" clipRule="evenodd" />
                        </svg>
                        <p className="leading-relaxed">{summary.coverageNote}</p>
                      </div>
                    )}

                    {/* Stale data warning */}
                    {summary?.stale && summary.staleReason && (
                      <div className="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3.5 py-2.5 text-[11px] text-amber-600 dark:text-amber-400">
                        <Icon name="alert" size={14} className="shrink-0" />
                        <p>{summary.staleReason}</p>
                      </div>
                    )}

                    {loadingTraffic ? (
                      <div className="space-y-2 animate-pulse">
                        {[0, 1, 2, 3].map((item) => (
                          <div
                            key={item}
                            className="h-12 rounded-xl bg-slate-200/50 dark:bg-slate-800/50"
                          />
                        ))}
                      </div>
                    ) : sortedBottlenecks.length > 0 ? (
                      <ul className="grid gap-2 sm:grid-cols-2">
                        {sortedBottlenecks.map((feature, idx) => (
                          <li
                            key={feature.id || idx}
                            onClick={() => setSelectedSegment(
                              selectedSegment?.id === feature.id ? null : feature
                            )}
                            className="cursor-pointer"
                          >
                            <BottleneckRow
                              feature={feature}
                              index={idx}
                              isDark={isDark}
                              isSelected={selectedSegment?.id === feature.id}
                            />
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <EmptyState
                        icon="traffic"
                        title="Free-flowing corridor"
                        detail="No critical bottlenecks or major slowdowns detected within this radius."
                        isDark={isDark}
                      />
                    )}

                    {/* Summary metadata footer */}
                    {summary && !loadingTraffic && features.length > 0 && (
                      <div className={`flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-t pt-3 text-[10px] font-medium ${
                        isDark ? "border-slate-800 text-slate-500" : "border-slate-100 text-slate-400"
                      }`}>
                        <div className="flex items-center gap-3">
                          <ProviderBadge source={summary.source} isDark={isDark} />
                          {summary.omittedCount != null && summary.omittedCount > 0 && (
                            <span>{summary.omittedCount} segments omitted (incomplete data)</span>
                          )}
                        </div>
                        {summary.fetchedAt && (
                          <span>Updated {formatTime(summary.fetchedAt)}</span>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {activeTab === "extras" && (
                  <div>
                    {loadingTolls ? (
                      <div className="space-y-2 animate-pulse">
                        {[0, 1].map((item) => (
                          <div
                            key={item}
                            className="h-12 rounded-xl bg-slate-200/50 dark:bg-slate-800/50"
                          />
                        ))}
                      </div>
                    ) : tollList.length > 0 ? (
                      <ul className="grid gap-2 sm:grid-cols-2">
                        {tollList.map((toll, idx) => (
                          <li
                            key={toll.id || idx}
                            className={`flex items-center gap-3 rounded-xl p-3 border transition-all ${
                              isDark
                                ? "border-slate-800/60 bg-slate-900/40"
                                : "border-slate-100 bg-white"
                            }`}
                          >
                            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-orange-500/15 font-bold text-orange-500 text-xs">
                              T
                            </span>
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-xs font-bold">
                                {toll.name || "Toll Plaza"}
                              </p>
                              <p className="truncate text-[11px] text-slate-400 capitalize">
                                {[toll.kind, toll.operator || toll.road]
                                  .filter(Boolean)
                                  .join(" · ") || "OpenStreetMap Plaza"}
                              </p>
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <EmptyState
                        icon="toll"
                        title="No toll plazas"
                        detail="No highway toll barriers found within the current map viewport."
                        isDark={isDark}
                      />
                    )}
                  </div>
                )}

                {activeTab === "bottlenecks" && (
                  <div>
                    {loadingPlaces ? (
                      <div className="space-y-2 animate-pulse">
                        {[0, 1, 2].map((item) => (
                          <div
                            key={item}
                            className="h-12 rounded-xl bg-slate-200/50 dark:bg-slate-800/50"
                          />
                        ))}
                      </div>
                    ) : placeList.length > 0 ? (
                      <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                        {placeList.slice(0, 9).map((place, idx) => (
                          <li
                            key={place.id || idx}
                            className={`flex items-center gap-3 rounded-xl p-3 border transition-all ${
                              isDark
                                ? "border-slate-800/60 bg-slate-900/40"
                                : "border-slate-100 bg-white"
                            }`}
                          >
                            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-teal-500/15 text-xs font-bold text-teal-500">
                              {(place.name || "E").charAt(0).toUpperCase()}
                            </span>
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-xs font-bold">
                                {place.name || "Eatery"}
                              </p>
                              <p className="truncate text-[11px] text-slate-400 capitalize">
                                {[place.cuisine, place.category].filter(Boolean).join(" · ") || "Restaurant"}
                              </p>
                            </div>
                            <span className="font-mono text-[10px] font-bold text-slate-400">
                              {formatDistance(place.distanceMeters)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <EmptyState
                        icon="food"
                        title="No eateries nearby"
                        detail="Expand the search radius to locate dining spots and highway stops."
                        isDark={isDark}
                      />
                    )}
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
