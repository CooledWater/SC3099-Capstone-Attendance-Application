import { readdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

async function assets(directory, prefix) {
  const entries = await readdir(directory, { withFileTypes: true });
  const groups = await Promise.all(entries.map(entry => entry.isDirectory()
    ? assets(join(directory, entry.name), `${prefix}/${entry.name}`)
    : /\.(js|css|woff2?)$/.test(entry.name) ? [`${prefix}/${entry.name}`] : []));
  return groups.flat();
}

const buildId = (await readFile('.next/BUILD_ID', 'utf8')).trim();
const shell = ['/', '/attendance', '/icon.svg', '/icon-192.png', '/icon-512.png', '/apple-touch-icon.png', '/manifest.webmanifest', ...await assets('.next/static', '/_next/static')];
await writeFile('public/sw-precache.js', `const CACHE = ${JSON.stringify(`saiv-shell-${buildId}`)};\nconst SHELL = ${JSON.stringify(shell.sort())};\n`);
console.log(`Service worker prepared: ${shell.length} shell files (${buildId}).`);
