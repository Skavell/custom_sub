import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#080d12',
        surface: '#0d1520',
        accent: {
          DEFAULT: '#06b6d4',
          hover: '#0891b2',
        },
        text: {
          primary: '#e2e8f0',
          secondary: '#94a3b8',
          muted: '#475569',
        },
        border: {
          accent: 'rgba(6,182,212,0.15)',
          neutral: 'rgba(255,255,255,0.07)',
        },
      },
      borderRadius: {
        card: '14px',
        input: '10px',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

export default config
