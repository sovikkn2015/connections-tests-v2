import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#1e40af",
          light: "#3b82f6",
          dark: "#1e3a8a",
        },
        success: {
          DEFAULT: "#15803d",
          light: "#22c55e",
        },
        danger: {
          DEFAULT: "#b91c1c",
          light: "#ef4444",
        },
        warning: {
          DEFAULT: "#a16207",
          light: "#eab308",
        },
        mnpi: {
          DEFAULT: "#7c3aed",
          light: "#a78bfa",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
