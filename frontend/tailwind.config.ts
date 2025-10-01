import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "./types/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        background: "#030712",
        foreground: "#f8fafc"
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"]
      },
      boxShadow: {
        elevated: "0 20px 45px -20px rgba(14,165,233,0.45)",
        glow: "0 0 0 1px rgba(148, 163, 184, 0.15)"
      }
    }
  },
  plugins: []
};

export default config;
