// tailwind.config.cjs
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./pages/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
    // adjust if you have ts/tsx
  ],
  theme: {
    extend: {
      // you can add extra colors, etc if needed
    }
  },
  plugins: [],
};
