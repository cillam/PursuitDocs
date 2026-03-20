/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          50: '#f6f7f9',
          100: '#eceef2',
          200: '#d5d9e2',
          300: '#b1b9c9',
          400: '#8793ab',
          500: '#687691',
          600: '#535f78',
          700: '#444d62',
          800: '#3b4253',
          900: '#343a47',
          950: '#1e222b',
        },
        brass: {
          50: '#fdf9ef',
          100: '#f9f0d4',
          200: '#f2dea5',
          300: '#eac96d',
          400: '#e4b443',
          500: '#db9a28',
          600: '#c2791f',
          700: '#a1591c',
          800: '#84471e',
          900: '#6d3b1c',
          950: '#3d1d0b',
        },
      },
      fontFamily: {
        display: ['"DM Serif Display"', 'Georgia', 'serif'],
        body: ['"Source Sans 3"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}
