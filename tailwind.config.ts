import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Background colors
        'bg-deep': '#0a0a0f',
        'bg-card': '#12121a',
        'bg-elevated': '#1a1a24',
        'bg-hover': '#24242f',
        // Border colors
        'border-subtle': 'rgba(255,255,255,0.06)',
        'border-medium': 'rgba(255,255,255,0.12)',
        // Text colors
        'text-primary': '#f0f4f8',
        'text-secondary': '#9ca3af',
        'text-muted': '#6b7280',
        // Status colors
        'positive': '#10b981',
        'negative': '#ef4444',
        'neutral': '#6b7280',
        // Accent colors
        'gold': '#fbbf24',
        'silver': '#94a3b8',
      },
      fontFamily: {
        'display': ['"Bebas Neue"', 'sans-serif'],
        'condensed': ['"Barlow Condensed"', 'sans-serif'],
        'body': ['Barlow', 'sans-serif'],
      },
      backgroundImage: {
        'grid-pattern': `
          linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)
        `,
      },
      backgroundSize: {
        'grid': '40px 40px',
      },
    },
  },
  plugins: [],
};

export default config;
