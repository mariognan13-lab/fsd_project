import type { ReactNode, SVGProps } from "react";

export type IconName =
  | "alert"
  | "clock"
  | "compass"
  | "food"
  | "gauge"
  | "layers"
  | "locate"
  | "map"
  | "navigation"
  | "pin"
  | "refresh"
  | "route"
  | "search"
  | "toll"
  | "traffic"
  | "x"
  | "sun"
  | "moon"
  | "sparkles"
  | "zap"
  | "trendUp"
  | "trendDown"
  | "chevronRight"
  | "speedometer"
  | "check";

const icons: Record<IconName, ReactNode> = {
  alert: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v4" />
      <path d="M12 16h.01" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  compass: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m15.5 8.5-2 5-5 2 2-5z" />
    </>
  ),
  food: (
    <>
      <path d="M7 3v7" />
      <path d="M4 3v4a3 3 0 0 0 6 0V3" />
      <path d="M7 10v11" />
      <path d="M17 3c-1.7 0-3 2.1-3 5s1.3 5 3 5" />
      <path d="M17 3v18" />
    </>
  ),
  gauge: (
    <>
      <path d="M20.5 14.5a8.5 8.5 0 1 0-17 0" />
      <path d="m12 12 4-4" />
      <circle cx="12" cy="12" r="1.5" />
      <path d="M4 19h16" />
    </>
  ),
  layers: (
    <>
      <path d="m12 3 9 5-9 5-9-5z" />
      <path d="m3 12 9 5 9-5" />
      <path d="m3 16 9 5 9-5" />
    </>
  ),
  locate: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
      <circle cx="12" cy="12" r="7" />
    </>
  ),
  map: (
    <>
      <path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3z" />
      <path d="M9 3v15M15 6v15" />
    </>
  ),
  navigation: (
    <>
      <path d="M21 3 10.5 21l-1.7-7.8L3 10.5z" />
    </>
  ),
  pin: (
    <>
      <path d="M20 10c0 5.5-8 12-8 12S4 15.5 4 10a8 8 0 1 1 16 0Z" />
      <circle cx="12" cy="10" r="2.5" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 7v5h-5" />
      <path d="M4 17v-5h5" />
      <path d="M6.1 9A7 7 0 0 1 18.6 7.7L20 12" />
      <path d="M17.9 15A7 7 0 0 1 5.4 16.3L4 12" />
    </>
  ),
  route: (
    <>
      <circle cx="6" cy="18" r="2.5" />
      <circle cx="18" cy="6" r="2.5" />
      <path d="M8.5 18H15a4 4 0 0 0 0-8H9a4 4 0 0 1 0-8h6.5" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </>
  ),
  toll: (
    <>
      <path d="M4 5h16" />
      <path d="M6 5v4M18 5v4" />
      <path d="M4 9h16" />
      <path d="M7 9v10M17 9v10" />
      <path d="M5 19h4M15 19h4" />
      <path d="M10 14h4" />
    </>
  ),
  traffic: (
    <>
      <rect x="7" y="3" width="10" height="18" rx="3" />
      <circle cx="12" cy="7.5" r="1.2" />
      <circle cx="12" cy="12" r="1.2" />
      <circle cx="12" cy="16.5" r="1.2" />
    </>
  ),
  x: (
    <>
      <path d="m6 6 12 12M18 6 6 18" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
    </>
  ),
  moon: (
    <>
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </>
  ),
  sparkles: (
    <>
      <path d="m12 3 1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6-4.6-1.9 4.6-1.9L12 3z" />
      <path d="M19 16l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9.9-2.1z" />
    </>
  ),
  zap: (
    <>
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </>
  ),
  trendUp: (
    <>
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
      <polyline points="16 7 22 7 22 13" />
    </>
  ),
  trendDown: (
    <>
      <polyline points="22 17 13.5 8.5 8.5 13.5 2 7" />
      <polyline points="16 17 22 17 22 11" />
    </>
  ),
  chevronRight: (
    <>
      <path d="m9 18 6-6-6-6" />
    </>
  ),
  speedometer: (
    <>
      <path d="M12 14v-4" />
      <path d="M3.34 17a10 10 0 1 1 17.32 0" />
    </>
  ),
  check: (
    <>
      <polyline points="20 6 9 17 4 12" />
    </>
  ),
};

interface IconProps extends SVGProps<SVGSVGElement> {
  name: IconName;
  size?: number;
}

export function Icon({ name, size = 18, ...props }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height={size}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={1.8}
      viewBox="0 0 24 24"
      width={size}
      {...props}
    >
      {icons[name]}
    </svg>
  );
}
