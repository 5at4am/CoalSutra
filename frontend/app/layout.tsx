import type { Metadata } from "next";
import SidebarLayout from "@/components/SidebarLayout";
import "./globals.css";

export const metadata: Metadata = {
  title: "CoalSutra · CMPDI Reporting Assistant",
  description:
    "CoalSutra — AI platform for the Ministry of Coal. Ingest geological & mining documents into structured, traceable, queryable data with cited answers, auto reports and corpus analysis.",
};

const THEME_INIT = `(function(){try{var t=localStorage.getItem('cmpdi-theme');var d=t?t==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.classList.toggle('dark',d);document.documentElement.style.colorScheme=d?'dark':'light';}catch(e){}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
      </head>
      <body className="min-h-screen bg-slate-100 text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-100">
        <SidebarLayout>{children}</SidebarLayout>
      </body>
    </html>
  );
}