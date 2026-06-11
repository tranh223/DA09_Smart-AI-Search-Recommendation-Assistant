/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { light: "#60a5fa", DEFAULT: "#3b82f6", dark: "#2563eb" },
      },
    },
  },
  plugins: [],
};
