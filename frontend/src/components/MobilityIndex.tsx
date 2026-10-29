"use client";

import React, { useMemo } from "react";
import { Icon } from "./Icons";

interface MobilityIndexProps {
  distribution?: Record<string, number>;
  segmentCount?: number;
  congestedCount?: number;
  isDark?: boolean;
  sourceLabel?: string;
  updatedAt?: string | null;
  isLive?: boolean;
}

const CONGESTION_CONFIG: Record<
  string,
  { label: string; color: string; darkColor: string; bg: string; dot: string }
> = {
  "free-flow": {
    label: "Free Flow",
    color: "text-emerald-500",
    darkColor: "text-emerald-400",
    bg: "bg-emerald-500",
    dot: "bg-emerald-500",
  },
  light: {
    label: "Light Flow",
    color: "text-yellow-500",
    darkColor: "text-yellow-400",
    bg: "bg-yellow-400",
    dot: "bg-yellow-400",
  },
  moderate: {
    label: "Moderate",
    color: "text-orange-500",
    darkColor: "text-orange-400",
    bg: "bg-orange-500",
    dot: "bg-orange-500",
  },
  heavy: {
    label: "Heavy Jam",
    color: "text-rose-500",
    darkColor: "text-rose-400",
    bg: "bg-rose-500",
    dot: "bg-rose-500",
  },
  unknown: {
    label: "Unsampled",
    color: "text-slate-400",
    darkColor: "text-slate-500",
    bg: "bg-slate-300 dark:bg-slate-700",
    dot: "bg-slate-400",
  },
};

export default function MobilityIndex({
  distribution = {},
  segmentCount = 0,
  congestedCount = 0,
  isDark = false,
  sourceLabel = "TomTom Traffic",
  updatedAt,
  isLive = true,
}: MobilityIndexProps) {
  // Mobility Health Score: 0 to 100
  // Free-flow = 1.0, Light = 0.8, Moderate = 0.45, Heavy = 0.1
  const score = useMemo(() => {
    if (!segmentCount) return null;
    const free = distribution["free-flow"] ?? 0;
    const light = distribution["light"] ?? 0;
    const mod = distribution["moderate"] ?? 0;
    const heavy = distribution["heavy"] ?? 0;
    const evaluated = free + light + mod + heavy;
    if (!evaluated) return null;

    const weighted = free * 100 + light * 80 + mod * 45 + heavy * 10;
    return Math.round(weighted / evaluated);
  }, [distribution, segmentCount]);

  const scoreMeta = useMemo(() => {
    if (score == null) {
      return {
        label: "Standby",
        color: "text-slate-400",
        ring: "#94a3b8",
        desc: "Awaiting route analysis",
      };
    }
    if (score >= 80) {
      return {
        label: "Excellent",
        color: "text-emerald-500",
        ring: "#10b981",
        desc: "Smooth velocity, low resistance",
      };
    }
    if (score >= 60) {
      return {
        label: "Good Flow",
        color: "text-yellow-500",
        ring: "#eab308",
        desc: "Mild traffic along key arterial lines",
      };
    }
    if (score >= 40) {
      return {
        label: "Congested",
        color: "text-orange-500",
        ring: "#f97316",
        desc: "Substantial pinch points present",
      };
    }
    return {
      label: "Critical Gridlock",
      color: "text-rose-500",
      ring: "#f43f5e",
      desc: "Severe stoppages on major lanes",
    };
  }, [score]);

  const totalEvaluated = useMemo(() => {
    return Object.values(distribution).reduce((a, b) => a + b, 0);
  }, [distribution]);

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border p-4 backdrop-blur-xl transition-all duration-300 ${
        isDark
          ? "border-slate-800/80 bg-gradient-to-b from-slate-900/90 to-slate-950/90 text-white shadow-[0_12px_40px_-15px_rgba(0,0,0,0.6)]"
          : "border-slate-200/80 bg-gradient-to-b from-white/95 to-slate-50/95 text-slate-900 shadow-[0_12px_40px_-20px_rgba(15,23,42,0.15)]"
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <span
            className={`grid h-7 w-7 place-items-center rounded-lg ${
              isDark ? "bg-indigo-500/10 text-indigo-400" : "bg-indigo-50 text-indigo-600"
            }`}
          >
            <Icon name="gauge" size={15} />
          </span>
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Mobility Health Index
          </h4>
        </div>

        <div className="flex items-center gap-1.5">
          <span
            className={`h-2 w-2 rounded-full ${
              isLive ? "bg-emerald-500 animate-pulse" : "bg-amber-400"
            }`}
          />
          <span className="text-[10px] font-semibold text-slate-400">
            {sourceLabel}
          </span>
        </div>
      </div>

      {/* Main Score & Radial Indicator */}
      <div className="flex items-center justify-between gap-4 py-1">
        <div className="space-y-1">
          <div className="flex items-baseline gap-2">
            <span
              className={`text-4xl font-black tracking-tight ${
                isDark ? "text-white" : "text-slate-900"
              }`}
            >
              {score != null ? score : "—"}
            </span>
            <span className="text-sm font-semibold text-slate-400">/ 100</span>
          </div>
          <p className={`text-xs font-bold ${scoreMeta.color}`}>{scoreMeta.label}</p>
          <p className="text-[11px] text-slate-400 leading-tight">{scoreMeta.desc}</p>
        </div>

        {/* Circular Progress Ring */}
        <div className="relative h-20 w-20 shrink-0">
          <svg className="h-full w-full -rotate-90 transform" viewBox="0 0 72 72">
            <circle
              cx="36"
              cy="36"
              r="30"
              fill="none"
              stroke={isDark ? "#1e293b" : "#e2e8f0"}
              strokeWidth="6"
            />
            {score != null && (
              <circle
                cx="36"
                cy="36"
                r="30"
                fill="none"
                stroke={scoreMeta.ring}
                strokeWidth="6"
                strokeDasharray={2 * Math.PI * 30}
                strokeDashoffset={
                  2 * Math.PI * 30 - (2 * Math.PI * 30 * score) / 100
                }
                strokeLinecap="round"
                className="transition-all duration-1000 ease-out"
              />
            )}
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <Icon name="sparkles" size={16} className={scoreMeta.color} />
          </div>
        </div>
      </div>

      {/* Spectrum Distribution Bar */}
      <div className="mt-4">
        <div className="flex justify-between text-[11px] font-semibold text-slate-400 mb-1.5">
          <span>Flow Distribution</span>
          <span>
            {congestedCount} bottleneck{congestedCount === 1 ? "" : "s"} of {segmentCount}
          </span>
        </div>

        <div className="flex h-2.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800 p-0.5 gap-0.5">
          {(["free-flow", "light", "moderate", "heavy"] as const).map((level) => {
            const count = distribution[level] ?? 0;
            if (!count) return null;
            const pct = totalEvaluated ? (count / totalEvaluated) * 100 : 0;
            return (
              <div
                key={level}
                className={`h-full rounded-full transition-all duration-500 ${CONGESTION_CONFIG[level].bg}`}
                style={{ width: `${pct}%` }}
                title={`${CONGESTION_CONFIG[level].label}: ${count} segments (${Math.round(pct)}%)`}
              />
            );
          })}
        </div>

        {/* Legend */}
        <div className="mt-2.5 grid grid-cols-2 gap-2 text-[10px] font-medium text-slate-400 sm:grid-cols-4">
          {(["free-flow", "light", "moderate", "heavy"] as const).map((level) => {
            const count = distribution[level] ?? 0;
            return (
              <div key={level} className="flex items-center gap-1.5">
                <span className={`h-2 w-2 rounded-full shrink-0 ${CONGESTION_CONFIG[level].dot}`} />
                <span className="truncate">
                  {CONGESTION_CONFIG[level].label}:{" "}
                  <strong className={isDark ? "text-slate-200" : "text-slate-700"}>
                    {count}
                  </strong>
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {updatedAt && (
        <div className="mt-3 flex items-center justify-between border-t border-slate-100 dark:border-slate-800/80 pt-2 text-[10px] text-slate-400">
          <span className="flex items-center gap-1">
            <Icon name="clock" size={12} />
            Telemetry updated: {updatedAt}
          </span>
          <span className="font-mono text-[9px] uppercase tracking-wider text-emerald-500">
            Realtime
          </span>
        </div>
      )}
    </div>
  );
}
