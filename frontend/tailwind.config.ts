import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Tenant brand colours are injected at runtime as CSS variables
        // (white-label theming, docs/architecture/05 §12.4). Defaults below.
        brand: {
          primary: "var(--brand-primary, #0f2742)",
          secondary: "var(--brand-secondary, #2f6fb0)",
        },
      },
    },
  },
  plugins: [],
};

export default config;
