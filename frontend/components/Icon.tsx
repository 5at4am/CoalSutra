import type { ReactNode, SVGProps } from "react";

export type IconName =
  | "home"
  | "upload"
  | "chat"
  | "report"
  | "chart"
  | "review"
  | "search"
  | "send"
  | "refresh"
  | "download"
  | "chevron-right"
  | "arrow-left"
  | "close"
  | "check"
  | "check-circle"
  | "alert"
  | "info"
  | "file"
  | "source"
  | "spark"
  | "clock"
  | "layers"
  | "shield"
  | "menu"
  | "filter"
  | "retry"
  | "logout"
  | "sun"
  | "moon";

const PATHS: Record<IconName, ReactNode> = {
  home: <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1v-9.5Z" />,
  upload: <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" />,
  chat: <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5Z" />,
  report: <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8ZM14 2v6h6M16 13H8M16 17H8M10 9H8" />,
  chart: <path d="M3 3v18h18M7 14.5V11m4 3.5V7m4 7.5V9m4 5.5V5" />,
  review: <path d="M9 12l2 2 4-4M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />,
  search: <path d="M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm10 2-4.2-4.2" />,
  send: <path d="m22 2-7 20-4-9-9-4 20-7ZM11 13l11-11" />,
  refresh: <path d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6" />,
  download: <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />,
  "chevron-right": <path d="m9 18 6-6-6-6" />,
  "arrow-left": <path d="M19 12H5m7 7-7-7 7-7" />,
  close: <path d="M18 6 6 18M6 6l12 12" />,
  check: <path d="m5 13 4 4L19 7" />,
  "check-circle": <path d="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-13.6-.7 3.1 3.1 6.1-6.5" />,
  alert: <path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />,
  info: <path d="M12 16v-4m0-4h.01M22 12c0 5.52-4.48 10-10 10S2 17.52 2 12 6.48 2 12 2s10 4.48 10 10Z" />,
  file: <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />,
  source: <path d="M4 4h6a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4a0 0 0 0 1 0 0Zm16 0h-6a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h6a0 0 0 0 1 0 0Z" />,
  spark: <path d="m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9Zm7 9 .9 2.6L22.5 15l-2.6.9L19 18.5l-.9-2.6L15.5 15l2.6-.9ZM5 16l.8 2.2L8 19l-2.2.8L5 22l-.8-2.2L2 19l2.2-.8Z" />,
  clock: <path d="M12 6v6l4 2M22 12c0 5.52-4.48 10-10 10S2 17.52 2 12 6.48 2 12 2s10 4.48 10 10Z" />,
  layers: <path d="m12 2 10 5.5L12 13 2 7.5ZM2 12.5 12 18l10-5.5M2 17.5 12 23l10-5.5" />,
  shield: <path d="M12 22s8-3.5 8-10V5l-8-3-8 3v7c0 6.5 8 10 8 10Z" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  filter: <path d="M4 5h16l-6 7v6l-4 2v-8Z" />,
  retry: <path d="M4 7h11a5 5 0 1 1-5 5M4 7V3m0 4h4" />,
  logout: <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />,
  sun: <path d="M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0-15v2m0 16v2M4.2 4.2l1.4 1.4m12.8 12.8 1.4 1.4M2 12h2m16 0h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" />,
  moon: <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z" />,
};

export default function Icon({
  name,
  size = 16,
  ...rest
}: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {PATHS[name]}
    </svg>
  );
}