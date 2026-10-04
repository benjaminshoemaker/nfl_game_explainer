import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    fontSize: {
      xs: ['var(--type-caption)', { lineHeight: '1.35' }],
      sm: ['var(--type-label)', { lineHeight: '1.4' }],
      base: ['var(--type-body)', { lineHeight: 'var(--leading-body)' }],
      lg: ['var(--type-subheading)', { lineHeight: '1.35' }],
      xl: ['var(--type-heading-sm)', { lineHeight: '1.25' }],
      '2xl': ['var(--type-heading-md)', { lineHeight: '1.2' }],
      '3xl': ['var(--type-heading-lg)', { lineHeight: '1.15' }],
      '4xl': ['var(--type-title)', { lineHeight: '1.1' }],
      '5xl': ['var(--type-stat-xl)', { lineHeight: '1.05' }],
      '6xl': ['var(--type-stat-2xl)', { lineHeight: '1.05' }],
      '7xl': ['var(--type-stat-3xl)', { lineHeight: '1.05' }],
      '8xl': ['var(--type-stat-4xl)', { lineHeight: '1.05' }],
    },
    extend: {
      colors: {
        // Background colors
        'bg-deep': '#f5f7f7',
        'bg-card': '#ffffff',
        'bg-elevated': '#edf5f5',
        'bg-hover': '#e5f0f0',
        // Border colors
        'border-subtle': '#dbe5e6',
        'border-medium': '#aac3c6',
        // Text colors
        'text-primary': '#202b2e',
        'text-secondary': '#526b70',
        'text-muted': '#65777b',
        // Status colors
        'positive': '#315e65',
        'negative': '#c44c4a',
        'neutral': '#65777b',
        // Accent colors
        'gold': '#4f8991',
        'silver': '#aac3c6',
      },
      fontFamily: {
        'display': ['var(--font-family-ui)'],
        'condensed': ['var(--font-family-ui)'],
        'body': ['var(--font-family-ui)'],
        'mono': ['var(--font-family-mono)'],
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
