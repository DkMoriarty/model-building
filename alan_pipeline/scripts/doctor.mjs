#!/usr/bin/env node
// Validates the local machine against the pipeline's requirements.
//   npm run doctor
import {spawnSync} from 'node:child_process';
import {existsSync, statfsSync} from 'node:fs';
import {createRequire} from 'node:module';
import os from 'node:os';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const require = createRequire(import.meta.url);
let failures = 0;
const ok = (msg) => console.log(`  ✓ ${msg}`);
const warn = (msg) => console.log(`  ! ${msg}`);
const fail = (msg) => (failures++, console.log(`  ✗ ${msg}`));

console.log('alan_pipeline doctor\n');

const [major, minor] = process.versions.node.split('.').map(Number);
major > 18 || (major === 18 && minor >= 18)
  ? ok(`Node ${process.versions.node}`)
  : fail(`Node ${process.versions.node} (need >= 18.18)`);

const threads = os.availableParallelism?.() ?? os.cpus().length;
threads >= 4
  ? ok(`${threads} CPU threads (${os.cpus()[0]?.model.trim()}) - render --concurrency=4 fits`)
  : warn(`${threads} CPU threads - use --concurrency=${Math.max(1, threads - 1)}`);

const ramGb = os.totalmem() / 1024 ** 3;
// Each worker is a full Chromium process holding 1080p canvases: ~0.6-1 GB.
ramGb >= 8 ? ok(`${ramGb.toFixed(1)} GB RAM`) : warn(`${ramGb.toFixed(1)} GB RAM - lower --concurrency`);

try {
  const {bavail, bsize} = statfsSync(root);
  const freeGb = (bavail * bsize) / 1024 ** 3;
  // 1080p PNG frames run ~0.1-0.3 MB each: one minute @ 60fps is ~0.5-1 GB.
  freeGb >= 20 ? ok(`${freeGb.toFixed(0)} GB free for frame cache`) : warn(`only ${freeGb.toFixed(1)} GB free`);
} catch {
  warn('could not read free disk space');
}

for (const pkg of ['@motion-canvas/core', '@motion-canvas/2d', '@motion-canvas/ui', '@motion-canvas/vite-plugin', 'vite', 'playwright-core']) {
  try {
    ok(`${pkg}@${require(`${pkg}/package.json`).version}`);
  } catch {
    fail(`${pkg} missing - run npm install`);
  }
}

let ffmpeg = process.env.FFMPEG_PATH;
try {
  ffmpeg ??= require('@ffmpeg-installer/ffmpeg').path;
} catch {
  ffmpeg ??= 'ffmpeg';
}
const ff = spawnSync(ffmpeg, ['-hide_banner', '-encoders'], {encoding: 'utf8'});
if (ff.status === 0) {
  ok(`ffmpeg (${ffmpeg})`);
  for (const enc of ['libx264', 'ffv1']) {
    ff.stdout.includes(` ${enc} `) ? ok(`  encoder ${enc}`) : fail(`  encoder ${enc} missing`);
  }
} else {
  fail('ffmpeg not found (set FFMPEG_PATH)');
}

try {
  const {chromium} = await import('playwright-core');
  const tries = [
    process.env.CHROME_PATH && {executablePath: process.env.CHROME_PATH},
    {},
    {channel: 'chrome'},
    {channel: 'msedge'},
  ].filter(Boolean);
  let launched = null;
  for (const opts of tries) {
    try {
      const browser = await chromium.launch({headless: true, ...opts});
      launched = `${browser.browserType().name()} ${browser.version()}`;
      await browser.close();
      break;
    } catch {}
  }
  launched
    ? ok(`headless browser: ${launched}`)
    : fail('no Chromium found - install Chrome/Edge, set CHROME_PATH, or run "npx playwright install chromium"');
} catch (e) {
  fail(`playwright-core: ${e.message}`);
}

existsSync(`${root}/audio/master_track.wav`)
  ? ok('audio/master_track.wav present')
  : warn('audio/master_track.wav missing - run npm run audio:placeholder');

const tsc = spawnSync(process.execPath, [require.resolve('typescript/bin/tsc'), '--noEmit', '-p', root], {encoding: 'utf8'});
tsc.status === 0 ? ok('TypeScript strict typecheck') : fail(`typecheck failed:\n${tsc.stdout}`);

console.log(failures ? `\n${failures} problem(s) found.` : '\nAll checks passed.');
process.exit(failures ? 1 : 0);
