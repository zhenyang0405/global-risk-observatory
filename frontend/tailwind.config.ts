import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0a0d12",
        bg: "#06080c",
        panel: "#0e131b",
        line: "#1c2230",
        fg: "#d6dbe5",
        muted: "#6f7889",
        accent: "#7c9cff",
        violet: "#a78bfa",
      },
      fontFamily: {
        display: [
          "-apple-system",
          "BlinkMacSystemFont",
          "SF Pro Display",
          "Inter",
          "system-ui",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
