import { build } from 'esbuild';
await build({ entryPoints: ['frontend/worksheet.js'], bundle: true, minify: true,
  outdir: 'tdp_system/static/worksheet-bundle', format: 'iife', target: ['chrome110'],
  define: { 'process.env.NODE_ENV': '"production"' }, legalComments: 'linked' });
