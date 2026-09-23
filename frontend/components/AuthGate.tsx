"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { fetchAuthConfig, getToken } from "@/lib/auth";

type GateState = "checking" | "open" | "redirecting";

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [gate, setGate] = useState<GateState>("checking");

  useEffect(() => {
    let alive = true;

    (async () => {
      try {
        const config = await fetchAuthConfig();
        if (!alive) return;

        if (config.auth_enabled && !getToken()) {
          if (pathname !== "/login") {
            setGate("redirecting");
            router.replace("/login");
            return;
          }
        }
        setGate("open");
      } catch {
        // auth config unreachable — stay lenient (offline/dev backend)
        setGate("open");
      }
    })();

    return () => {
      alive = false;
    };
  }, [pathname, router]);

  if (gate === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center text-ink-muted dark:text-slate-400">
        Checking access…
      </div>
    );
  }

  return <>{children}</>;
}