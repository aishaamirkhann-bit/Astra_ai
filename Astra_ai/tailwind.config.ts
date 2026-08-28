import type { Config } from "tailwindcss";

// ── ASTRA AI design tokens ──────────────────────────────────────────
// base/ink are theme-aware (driven by CSS variables that flip under
// [data-theme="dark"] in globals.css) so every existing utility class
// (bg-base-800, text-ink-100, etc.) automatically restyles for both
// light (default) and dark themes with zero changes to components.
// astra/signal accents stay constant across themes.
const withOpacity = (varName: string) => `rgb(var(${varName}) / <alpha-value>)`;

const config: Config = {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: {
          950: withOpacity("--base-950"),
          900: withOpacity("--base-900"),
          800: withOpacity("--base-800"),
          700: withOpacity("--base-700"),
          600: withOpacity("--base-600"),
          500: withOpacity("--base-500"),
        },
        ink: {
          100: withOpacity("--ink-100"),
          300: withOpacity("--ink-300"),
          500: withOpacity("--ink-500"),
          700: withOpacity("--ink-700"),
        },
        astra: {
          indigo: "#5B6EF5",
          violet: "#9B6BFF",
          cyan: withOpacity("--astra-cyan"),
        },
        signal: {
          good: withOpacity("--signal-good"),
          hold: withOpacity("--signal-hold"),
          reject: withOpacity("--signal-reject"),
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        body: ["var(--font-body)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      backgroundImage: {
        "astra-glow": "var(--astra-glow)",
        "astra-gradient": "linear-gradient(135deg, #5B6EF5 0%, #9B6BFF 100%)",
        "astra-gradient-soft":
          "linear-gradient(135deg, rgba(91,110,245,0.16) 0%, rgba(155,107,255,0.10) 100%)",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(91,110,245,0.25), 0 8px 30px -8px rgba(91,110,245,0.45)",
        card: "var(--card-shadow)",
      },
      borderRadius: {
        xl2: "1.25rem",
      },
      keyframes: {
        pulseDot: {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.4", transform: "scale(0.85)" },
        },
        travel: {
          "0%": { left: "0%" },
          "100%": { left: "100%" },
        },
      },
      animation: {
        pulseDot: "pulseDot 1.6s ease-in-out infinite",
        travel: "travel 3.2s linear infinite",
      },
    },
  },
  plugins: [],
};
export default config;
