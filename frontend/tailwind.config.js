/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Dark terminal theme
        'terminal': {
          'bg': '#0a0e14',
          'surface': '#0d1117',
          'border': '#21262d',
          'text': '#c9d1d9',
          'muted': '#8b949e',
        },
        // Crypto colors
        'bull': {
          DEFAULT: '#00d26a',
          'light': '#4ade80',
          'dark': '#16a34a',
        },
        'bear': {
          DEFAULT: '#ff4757',
          'light': '#f87171',
          'dark': '#dc2626',
        },
        // Prediction cone
        'cone': {
          'fill': 'rgba(59, 130, 246, 0.15)',
          'stroke': '#3b82f6',
          'mid': '#60a5fa',
        },
        // Accent
        'accent': {
          DEFAULT: '#7c3aed',
          'light': '#a78bfa',
        },
      },
      fontFamily: {
        'mono': ['JetBrains Mono', 'Fira Code', 'monospace'],
        'display': ['Space Grotesk', 'system-ui', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(124, 58, 237, 0.5)' },
          '100%': { boxShadow: '0 0 20px rgba(124, 58, 237, 0.8)' },
        },
      },
    },
  },
  plugins: [],
}



