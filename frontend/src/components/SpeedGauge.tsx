"use client";

import React, { useMemo } from "react";
import { Icon } from "./Icons";

interface SpeedGaugeProps {
  speedKmh?: number | null;
  maxSpeedKmh?: number;
  delaySeconds?: number | null;
  congestionLevel?: string;
  isDark?: boolean;
}

export default function SpeedGauge({
  speedKmh,
  maxSpeedKmh = 80,
  delaySeconds,
  congestionLevel = "free-flow",
  isDark = false,
}: SpeedGaugeProps) {
  const currentSpeed = speedKmh != null && Number.isFinite(speedKmh) ? Math.max(0, speedKmh) : null;
  const ratio = currentSpeed != null ? Math.min(1, Math.max(0, currentSpeed / maxSpeedKmh)) : 0;

  // Gauge geometry: 240-degree arc from 150deg to 390deg (or -210 to 30)
  const radius = 64;
  const circumference = 2 * Math.PI * radius;
  const arcLength = circumference * (240 / 360);
  const strokeDashoffset = arcLength - arcLength * ratio;

  // Congestion rating metadata
  const statusMeta = useMemo(() => {
    switch (congestionLevel) {
      case "heavy":
        return {
          title: "Heavy Traffic",
          desc: "Severe slowdowns detected",
          badgeColor: isDark ? "bg-rose-500/20 text-rose-300 border-rose-500/30" : "bg-rose-50 text-rose-700 border-rose-200",
          glowColor: "rgba(244, 63, 94, 0.35)",
          gradientId: "gaugeGradHeavy",
          ringColor: "#f43f5e",
        };
      case "moderate":
        return {
          title: "Moderate Flow",
          desc: "Noticeable stop-and-go",
          badgeColor: isDark ? "bg-amber-500/20 text-amber-300 border-amber-500/30" : "bg-amber-50 text-amber-700 border-amber-200",
          glowColor: "rgba(245, 158, 11, 0.35)",
          gradientId: "gaugeGradMod",
          ringColor: "#f59e0b",
        };
      case "light":
        return {
          title: "Light Volume",
          desc: "Minor pace reductions",
          badgeColor: isDark ? "bg-yellow-500/20 text-yellow-300 border-yellow-500/30" : "bg-yellow-50 text-yellow-700 border-yellow-200",
          glowColor: "rgba(234, 179, 8, 0.35)",
          gradientId: "gaugeGradLight",
          ringColor: "#eab308",
        };
      case "free-flow":
      default:
        return {
          title: "Fluid Flow",
          desc: "Cruising at expected speeds",
          badgeColor: isDark ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30" : "bg-emerald-50 text-emerald-700 border-emerald-200",
          glowColor: "rgba(16, 185, 129, 0.35)",
          gradientId: "gaugeGradFree",
          ringColor: "#10b981",
        };
    }
  }, [congestionLevel, isDark]);

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border transition-all duration-300 ${
        isDark
          ? "border-slate-800/80 bg-gradient-to-b from-slate-900/90 to-slate-950/90 text-white shadow-[0_12px_40px_-15px_rgba(0,0,0,0.6)]"
          : "border-slate-200/80 bg-gradient-to-b from-white/95 to-slate-50/95 text-slate-900 shadow-[0_12px_40px_-20px_rgba(15,23,42,0.15)]"
      } p-4 backdrop-blur-xl`}
    >
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-2">
          <span
            className={`grid h-7 w-7 place-items-center rounded-lg ${
              isDark ? "bg-blue-500/10 text-blue-400" : "bg-blue-50 text-blue-600"
            }`}
          >
            <Icon name="speedometer" size={15} />
          </span>
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Live Velocity Gauge
            </h4>
          </div>
        </div>

        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-semibold transition-all ${statusMeta.badgeColor}`}
        >
          <span
            className="h-1.5 w-1.5 rounded-full animate-ping"
            style={{ backgroundColor: statusMeta.ringColor }}
          />
          {statusMeta.title}
        </span>
      </div>

      <div className="relative flex flex-col items-center justify-center pt-2">
        {/* SVG Speedometer Dial */}
        <div className="relative h-44 w-44">
          <svg className="h-full w-full rotate-[150deg] transform" viewBox="0 0 160 160">
            <defs>
              <linearGradient id="gaugeGradFree" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#06b6d4" />
                <stop offset="100%" stopColor="#10b981" />
              </linearGradient>
              <linearGradient id="gaugeGradLight" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#3b82f6" />
                <stop offset="100%" stopColor="#eab308" />
              </linearGradient>
              <linearGradient id="gaugeGradMod" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#eab308" />
                <stop offset="100%" stopColor="#f97316" />
              </linearGradient>
              <linearGradient id="gaugeGradHeavy" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#f97316" />
                <stop offset="100%" stopColor="#f43f5e" />
              </linearGradient>
              <filter id="gaugeGlow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Background Track */}
            <circle
              cx="80"
              cy="80"
              r={radius}
              fill="none"
              stroke={isDark ? "#1e293b" : "#e2e8f0"}
              strokeWidth="11"
              strokeDasharray={`${arcLength} ${circumference}`}
              strokeLinecap="round"
            />

            {/* Glowing Active Arc */}
            {currentSpeed != null && (
              <circle
                cx="80"
                cy="80"
                r={radius}
                fill="none"
                stroke={`url(#${statusMeta.gradientId})`}
                strokeWidth="11"
                strokeDasharray={`${arcLength} ${circumference}`}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                className="transition-all duration-1000 ease-out"
                filter="url(#gaugeGlow)"
              />
            )}
          </svg>

          {/* Speed Center Readout */}
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
              Avg Speed
            </span>
            <div className="flex items-baseline gap-1 mt-0.5">
              <span
                className={`text-4xl font-extrabold tracking-tight ${
                  isDark ? "text-white" : "text-slate-900"
                }`}
              >
                {currentSpeed != null ? Math.round(currentSpeed) : "—"}
              </span>
              <span className="text-xs font-bold text-slate-400">km/h</span>
            </div>
            <p className="text-[10px] text-slate-400 mt-0.5">{statusMeta.desc}</p>
          </div>
        </div>

        {/* Bottom Sub-Metrics */}
        <div className="mt-2 grid w-full grid-cols-2 gap-2 border-t pt-3 border-slate-100 dark:border-slate-800">
          <div
            className={`flex flex-col items-center rounded-xl p-2 ${
              isDark ? "bg-slate-800/50" : "bg-slate-50"
            }`}
          >
            <span className="text-[10px] font-medium text-slate-400">Delay Factor</span>
            <span
              className={`text-xs font-bold ${
                delaySeconds && delaySeconds > 60
                  ? "text-rose-500"
                  : isDark
                    ? "text-slate-200"
                    : "text-slate-700"
              }`}
            >
              {delaySeconds != null && delaySeconds > 0
                ? `+${Math.round(delaySeconds)}s`
                : "Minimal"}
            </span>
          </div>

          <div
            className={`flex flex-col items-center rounded-xl p-2 ${
              isDark ? "bg-slate-800/50" : "bg-slate-50"
            }`}
          >
            <span className="text-[10px] font-medium text-slate-400">Pace Efficiency</span>
            <span
              className={`text-xs font-bold ${
                ratio >= 0.8
                  ? "text-emerald-500"
                  : ratio >= 0.5
                    ? "text-amber-500"
                    : "text-rose-500"
              }`}
            >
              {currentSpeed != null ? `${Math.round(ratio * 100)}%` : "—"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
