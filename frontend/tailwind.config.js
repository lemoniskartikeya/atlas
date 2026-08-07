/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "rgb(var(--canvas) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        panel: "rgb(var(--panel) / <alpha-value>)",
        border: "rgb(var(--border) / <alpha-value>)",
        ink: {
          DEFAULT: "rgb(var(--ink) / <alpha-value>)",
          muted: "rgb(var(--ink-muted) / <alpha-value>)",
          faint: "rgb(var(--ink-faint) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--accent) / <alpha-value>)",
          soft: "rgb(var(--accent) / 0.14)",
        },
        success: {
          DEFAULT: "rgb(var(--success) / <alpha-value>)",
          soft: "rgb(var(--success) / 0.14)",
        },
        warn: "rgb(var(--warn) / <alpha-value>)",
        danger: {
          DEFAULT: "rgb(var(--danger) / <alpha-value>)",
          soft: "rgb(var(--danger) / 0.12)",
        },
      },
      borderRadius: { xl: "1rem", "2xl": "1.25rem", "3xl": "1.75rem" },
      fontFamily: {
        // UI chrome — whatever the OS considers its interface face.
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI Variable Text"',
          '"Segoe UI"',
          "Inter",
          "Roboto",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
        // Display/editorial type. System serifs only — the app ships offline,
        // so no webfont may be fetched at runtime.
        display: [
          '"Iowan Old Style"',
          '"Palatino Linotype"',
          "Palatino",
          '"Book Antiqua"',
          "Georgia",
          '"Times New Roman"',
          "serif",
        ],
      },
      transitionTimingFunction: {
        "out-soft": "cubic-bezier(0.22, 1, 0.36, 1)",
        spring: "cubic-bezier(0.34, 1.56, 0.64, 1)",
      },
    },
  },
  plugins: [],
};
