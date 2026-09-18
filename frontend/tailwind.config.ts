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
          400: "#94907e",
          500: "#7a7563",
          600: "#625e50",
          700: "#504d42",
          800: "#444139",
          900: "#3b3933",
          950: "#242320",
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
        card: "0 1px 2px 0 rgb(20 22 24 / 0.06), 0 1px 3px 0 rgb(20 22 24 / 0.08)",
        drawer:
          "-12px 0 32px -12px rgb(20 22 24 / 0.25)",
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