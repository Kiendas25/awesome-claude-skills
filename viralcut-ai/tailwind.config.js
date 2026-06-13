/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0b0b12',
        panel: '#14141f',
        panel2: '#1c1c2b',
        edge: '#2a2a3d',
        brand: {
          DEFAULT: '#7c5cff',
          glow: '#a78bfa',
        },
        accent: '#22d3ee',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
