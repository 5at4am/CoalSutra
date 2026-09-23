"use client";

import Image from "next/image";
import Link from "next/link";

import logoOnly from "@/app/public/logo-only.png";

export function BrandMark({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex shrink-0 items-center justify-center overflow-hidden ${className}`}>
      <Image
        src={logoOnly}
        alt="CoalSutra logo"
        priority
        className="h-full w-full object-contain"
      />
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
        <span className="block text-[11px] font-medium text-ink-muted dark:text-slate-500">
          {subtitle}
        </span>
      </span>
    </Link>
  );
}