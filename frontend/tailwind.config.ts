import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        soc: {
          bg: "#0f1419",
          panel: "#1a2332",
          border: "#2d3a4f",
          accent: "#3b82f6",
        },
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
