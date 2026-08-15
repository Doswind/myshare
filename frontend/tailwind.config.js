/** @type {import('tailwindcss').Config} */
import typography from "@tailwindcss/typography";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontSize: {
        xs: ["11px", "14px"],
        sm: ["13px", "18px"],
      },
      colors: {
        up: "#dc2626",     // A 股红涨
        down: "#16a34a",   // A 股绿跌
      },
    },
  },
  plugins: [typography],
};
