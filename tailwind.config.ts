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
        'display': ['Arial', 'Helvetica', 'sans-serif'],
        'condensed': ['Arial', 'Helvetica', 'sans-serif'],
        'body': ['Arial', 'Helvetica', 'sans-serif'],
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
