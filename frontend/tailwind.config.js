/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'nova-dark': '#0f172a',
        'nova-primary': '#6366f1',
        'nova-accent': '#22d3ee',
        'nova-surface': '#1e293b',
        'nova-border': '#334155',
      },
    },
  },
  plugins: [],
}
