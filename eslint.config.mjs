import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';


export default defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    // The React Compiler is not enabled in this project. These compiler-only
    // rules reject established state synchronization and memoization patterns.
    rules: {
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/preserve-manual-memoization': 'off',
    },
  },
  globalIgnores([
    '.next/**',
    'out/**',
    'build/**',
    'next-env.d.ts',
    '.venv/**',
    '.claude/**',
  ]),
]);
