/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // TRACE Design System — deep investigative palette
        trace: {
          bg: '#060a13',
          surface: '#0d1321',
          'surface-2': '#151d2e',
          'surface-3': '#1a2438',
          border: '#1e2d44',
          'border-light': '#2a3f5f',
          text: '#e2e8f0',
          'text-muted': '#8896aa',
          'text-dim': '#5a6a80',
          primary: '#3b82f6',
          'primary-hover': '#2563eb',
          'primary-dim': '#1d4ed8',
          accent: '#f59e0b',
          'accent-hover': '#d97706',
          danger: '#ef4444',
          'danger-hover': '#dc2626',
          success: '#10b981',
          'success-hover': '#059669',
        },
        // Entity type colors for graph visualization
        entity: {
          person: '#38bdf8',      // sky-400
          org: '#a78bfa',         // violet-400
          location: '#34d399',    // emerald-400
          phone: '#fb923c',       // orange-400
          vehicle: '#fb7185',     // rose-400
          bank: '#fbbf24',        // amber-400
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'slide-in-up': 'slideInUp 0.3s ease-out',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideInRight: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        slideInUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 5px rgba(59, 130, 246, 0.3)' },
          '50%': { boxShadow: '0 0 20px rgba(59, 130, 246, 0.6)' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}
