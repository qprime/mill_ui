/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./internal/views/**/*.go",
    "./cmd/server/**/*.go",
    "./web/static/**/*.html",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [require("@tailwindcss/forms"), require("@tailwindcss/typography")],
};
