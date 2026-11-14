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
        'bg-deep': 'var(--bg-deep)',
        'bg-card': 'var(--bg-card)',
        'bg-elevated': 'var(--bg-elevated)',
        'bg-hover': 'var(--bg-hover)',
        // Border colors
        'border-subtle': 'var(--border-subtle)',
        'border-medium': 'var(--border-medium)',
        // Text colors
        'text-primary': 'var(--text-primary)',
        'text-secondary': 'var(--text-secondary)',
        'text-muted': 'var(--text-muted)',
        // Status colors
        'positive': 'var(--positive)',
        'negative': 'var(--negative)',
        'neutral': 'var(--neutral)',
        // Accent colors
        'gold': 'var(--gold)',
        'silver': 'var(--silver)',
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
