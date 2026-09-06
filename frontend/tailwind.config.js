/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          900: '#0b0f19',
          800: '#111827',
          700: '#1f293d',
          600: '#374151',
        },
        volt: {
          green: '#10b981',
          cyan: '#06b6d4',
          amber: '#f59e0b',
          purple: '#8b5cf6',
        }
      }
    },
  },
  plugins: [],
}
