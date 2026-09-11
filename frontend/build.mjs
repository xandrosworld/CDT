import { build } from 'esbuild';
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { gzipSync } from 'node:zlib';
await build({ entryPoints: ['frontend/worksheet.js'], bundle: true, minify: true,
  outdir: 'tdp_system/static/worksheet-bundle', format: 'iife', target: ['chrome110'],
  define: { 'process.env.NODE_ENV': '"production"' }, legalComments: 'linked' });
const directory = 'tdp_system/static/worksheet-bundle';
const bytes = await readFile(`${directory}/worksheet.js`);
const name = `worksheet-${createHash('sha256').update(bytes).digest('hex').slice(0,16)}.js`;
await writeFile(`${directory}/${name}`, bytes);
await writeFile(`${directory}/${name}.gz`, gzipSync(bytes, {level:9}));
await writeFile(`${directory}/manifest.json`, JSON.stringify({script:name, bytes:bytes.length}));
