import { build } from 'esbuild';
await build({ entryPoints: ['src/analytics-standalone.ts'], bundle: true, minify: true, format: 'iife', target: ['es2020'], outfile: 'public/analytics.js', define: { 'process.env.NODE_ENV': '"production"' } });
