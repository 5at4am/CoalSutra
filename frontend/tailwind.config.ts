import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        /* Coal/graphite neutrals — the primary surface scale. */
        coal: {
          50: "#f6f6f4",
          100: "#e7e6e1",
          200: "#d3d1c8",
          300: "#b4b1a3",
          400: "#75705f",
          500: "#615d4d",
          600: "#504d42",
          700: "#403d34",
          800: "#33312b",
          900: "#26241f",
          950: "#16150f",
        },
        /* "Source" accent — evidential, grounded, verified content. */
        source: {
          DEFAULT: "#146c43",
          dark: "#0d4f30",
          light: "#e3f4ec",
          chip: "#cdeede",
        },
        /* "Gap" accent — missing evidence / needs review. */
        gap: {
          DEFAULT: "#9a3412",
          light: "#fde8d8",
        },
        /* Warm off-white application canvas (light) + deep navy-black canvas (dark). */
        canvas: {
          DEFAULT: "#f7f6f1",
          dark: "#0b101e",
        },
        /* Ink — primary text. Near-navy, warm for light mode. */
        ink: {
          DEFAULT: "#1c2333",
          muted: "#546074",
        },
        /* CoalSutra amber accent — used strictly for brand + primary actions. */
        accent: {
          DEFAULT: "#b45309",
          strong: "#92400e",
          faint: "#fef3c7",
          ring: "#d97706",
        },
        /* Info — light-blue informational states. */
        info: {
          DEFAULT: "#2563eb",
          dark: "#1d4ed8",
          soft: "#eff6ff",
          border: "#bfdbfe",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Oxygen",
          "Ubuntu",
          "Cantarell",
          "Fira Sans",
          "Droid Sans",
          "Helvetica Neue",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(28 35 51 / 0.06), 0 1px 3px 0 rgb(28 35 51 / 0.08)",
        panel:
          "-14px 0 32px -12px rgb(11 16 30 / 0.30), 0 8px 32px -8px rgb(11 16 30 / 0.25)",
        pop: "0 4px 16px -2px rgb(11 16 30 / 0.18)",
      },
      maxWidth: {
        chat: "46rem",
      },
      animation: {
        "fade-in": "fadeIn 0.18s ease-out",
        "slide-in-right": "slideInRight 0.22s cubic-bezier(0.16, 1, 0.3, 1)",
        "slide-in-left": "slideInLeft 0.24s cubic-bezier(0.16, 1, 0.3, 1)",
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        slideInRight: {
          from: { transform: "translateX(100%)" },
          to: { transform: "translateX(0)" },
        },
        slideInLeft: {
          from: { transform: "translateX(-100%)" },
          to: { transform: "translateX(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;