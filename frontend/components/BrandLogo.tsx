"use client";

import Link from "next/link";

export function BrandMark({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block shrink-0 overflow-hidden rounded-[11px] bg-coal-900 ${className}`}
    >
      <svg
        viewBox="0 0 48 48"
        className="block h-full w-full"
        role="img"
        aria-label="CoalSutra logo"
      >
        {/* coal strata */}
        <rect x="9" y="14" width="30" height="4" rx="2" className="fill-coal-300" />
        <rect x="13" y="21" width="22" height="4" rx="2" className="fill-coal-400" />
        <rect x="11" y="28" width="26" height="4" rx="2" className="fill-coal-500" />
        <rect x="8" y="35" width="32" height="4" rx="2" className="fill-coal-600" />
        {/* sutra thread — threads the strata, rises to insight */}
        <path
          d="M 2 15 C 8 13, 12 17, 15 19 C 20 23, 22 24, 26 24 C 31 24, 32 30, 36 30 C 40 30, 41 20, 44 14"
          fill="none"
          strokeWidth="3"
          strokeLinecap="round"
          className="stroke-amber-500"
        />
        {/* knowledge spark */}
        <path
          d="M44 9.9 L45.15 11.25 L47.6 13.5 L45.15 15.75 L44 17.1 L42.85 15.75 L40.4 13.5 L42.85 11.25 Z"
          className="fill-amber-300"
        />
      </svg>
    </span>
  );
}

export default function BrandLogo({
  subtitle = "CMPDI Reporting Assistant",
  onClick,
  markClassName = "h-8 w-8",
}: {
  subtitle?: string;
  onClick?: () => void;
  markClassName?: string;
}) {
  return (
    <Link href="/" onClick={onClick} className="flex items-center gap-2.5">
      <BrandMark className={markClassName} />
      <span className="leading-tight">
        <span className="block text-[15px] font-extrabold tracking-tight text-coal-950 dark:text-slate-50">
          Coal<span className="text-amber-600 dark:text-amber-500">Sutra</span>
        </span>
        <span className="block text-[11px] font-medium text-coal-400 dark:text-slate-500">
          {subtitle}
        </span>
      </span>
    </Link>
  );
}