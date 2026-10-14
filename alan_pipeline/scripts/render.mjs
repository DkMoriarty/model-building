#!/usr/bin/env node
// Parallel headless renderer.
//
//   npm run render -- [--project=space_duel] [--concurrency=4] [--lossless]
//                     [--keep-frames] [--strict] [--frames=A-B] [--at=t1,t2,...]
//                     [--audio=audio/master_track.wav] [--name=opening_fight]
//
// 1. Boots the Vite dev server (Motion Canvas plugin) in-process.
// 2. Probes the project length in a headless Chromium page.
// 3. Splits the frame range into N contiguous chunks and renders each chunk in
//    its own Chromium process, so N CPU cores rasterise in parallel.
// 4. Stitches the PNG sequence + master audio into output_renders/ with ffmpeg.
import {spawn} from 'node:child_process';
import {existsSync, readdirSync, rmSync} from 'node:fs';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright-core';
import {createServer} from 'vite';

// The Motion Canvas plugin requires() Vite; silence the CJS deprecation notice.
process.env.VITE_CJS_IGNORE_WARNING = 'true';

const root = fileURLToPath(new URL('..', import.meta.url));
const require = createRequire(import.meta.url);

const args = Object.fromEntries(
  process.argv.slice(2).map(arg => {
    const [key, value] = arg.replace(/^--/, '').split('=');
    return [key, value ?? true];
  }),
);
const concurrency = Math.max(1, Number(args.concurrency ?? 4));
// Per-project defaults: master audio and output video name.
const PROJECTS = {
  alan_pipeline: {audio: 'audio/master_track.wav', video: 'opening_fight'},
  space_duel: {audio: 'audio/space_duel/master.wav', video: 'space_duel'},
  first_light: {audio: 'audio/first_light/master.wav', video: 'first_light'},
  first_game: {audio: 'audio/first_game/master.wav', video: 'first_game'},
};
const projectName = String(args.project ?? 'alan_pipeline');
if (!PROJECTS[projectName]) {
  console.error(`unknown --project=${projectName} (have: ${Object.keys(PROJECTS).join(', ')})`);
  process.exit(1);
}
const outputDir = path.join(root, 'output_renders');
const framesDir = path.join(outputDir, projectName);
const audioPath = path.resolve(root, String(args.audio ?? PROJECTS[projectName].audio));
const videoName = String(args.name ?? PROJECTS[projectName].video);
// Partial renders (for checking a few frames) never stitch a video.
const partial = Boolean(args.frames || args.at);

function resolveFfmpeg() {
  if (process.env.FFMPEG_PATH) return process.env.FFMPEG_PATH;
  try {
    return require('@ffmpeg-installer/ffmpeg').path;
  } catch {
    return 'ffmpeg';
  }
}

async function launchBrowser() {
  const base = {
    headless: true,
    // CPU rasterization (no GPU): identical output on every machine and driver,
    // and ~3x faster for 2D canvas than SwiftShader's emulated GPU.
    // Override with RENDER_BROWSER_ARGS="..." if needed.
    args: (process.env.RENDER_BROWSER_ARGS ?? '--disable-gpu --mute-audio').split(' '),
  };
  const candidates = [
    process.env.CHROME_PATH && {executablePath: process.env.CHROME_PATH},
    {}, // Playwright-managed Chromium (PLAYWRIGHT_BROWSERS_PATH)
    {channel: 'chrome'},
    {channel: 'msedge'},
  ].filter(Boolean);
  let lastError;
  for (const candidate of candidates) {
    try {
      return await chromium.launch({...base, ...candidate});
    } catch (e) {
      lastError = e;
    }
  }
  throw new Error(
    `Could not launch Chromium. Set CHROME_PATH or run "npx playwright install chromium".\n${lastError}`,
  );
}

// Late-beat warnings from syncTo(); --strict turns them into a failed render.
const timingWarnings = [];

async function runPage(browser, url, label) {
  const page = await browser.newPage();
  page.on('console', msg => {
    // Scene meta autosave races between parallel workers; it is editor-only
    // state and does not affect rendered frames, so drop that notice.
    if (msg.text().includes('Connection timeout when updating metadata')) return;
    if (msg.text().startsWith('[warn]')) {
      if (!label.startsWith('probe')) return; // reported once, by the probe
      timingWarnings.push(msg.text());
    }
    if (process.env.DEBUG || msg.type() === 'error' || msg.text().startsWith('[warn]')) {
      console.error(`[${label}] ${msg.text()}`);
    }
  });
  page.on('pageerror', e => console.error(`[${label}] ${e.message}`));
  await page.goto(url);
  await page.waitForFunction(() => window.__render?.done, null, {timeout: 0, polling: 250});
  const result = await page.evaluate(() => window.__render);
  await page.close();
  if (!result.ok) throw new Error(`[${label}] render failed: ${result.error ?? 'see console'}`);
  return result;
}

function ffmpeg(argv) {
  return new Promise((resolve, reject) => {
    const proc = spawn(resolveFfmpeg(), argv, {stdio: ['ignore', 'inherit', 'inherit']});
    proc.on('error', reject);
    proc.on('exit', code => (code === 0 ? resolve() : reject(new Error(`ffmpeg exited ${code}`))));
  });
}

const started = performance.now();
console.log(`cpu: ${os.cpus().length} threads | workers: ${concurrency}`);

const server = await createServer({
  root,
  configFile: path.join(root, 'vite.config.js'),
  logLevel: 'warn',
  server: {port: 0, host: '127.0.0.1'},
});
await server.listen();
const base = server.resolvedUrls.local[0].replace(/\/$/, '');
const browsers = [];

try {
  rmSync(framesDir, {recursive: true, force: true});

  const probeBrowser = await launchBrowser();
  browsers.push(probeBrowser);
  const {frames} = await runPage(probeBrowser, `${base}/scripts/render.html?project=${projectName}&probe`, 'probe');
  const fps = Number(args.fps ?? 60);
  const lastFrame = frames;
  console.log(`project: ${frames + 1} frames @ ${fps} fps`);
  if (args.strict && timingWarnings.length) {
    throw new Error(`--strict: ${timingWarnings.length} beat(s) land off their audio marker`);
  }

  let first = 0;
  let last = lastFrame;
  if (args.frames) {
    [first, last] = String(args.frames).split('-').map(Number);
    last = Math.min(lastFrame, last ?? first);
  }
  const total = last - first + 1;
  const chunks = [];
  if (args.at) {
    // Individual stills at the given times (seconds).
    for (const t of String(args.at).split(',')) {
      const f = Math.min(lastFrame, Math.round(Number(t) * fps));
      chunks.push([f, f]);
    }
  } else {
    const size = Math.ceil(total / concurrency);
    for (let from = first; from <= last; from += size) {
      chunks.push([from, Math.min(last, from + size - 1)]);
    }
  }

  const workers = Math.min(concurrency, chunks.length);
  for (let i = 1; i < workers; i++) browsers.push(await launchBrowser());
  const queue = chunks.map((chunk, i) => ({chunk, i}));
  await Promise.all(
    browsers.slice(0, workers).map(async browser => {
      for (let job = queue.shift(); job; job = queue.shift()) {
        const [from, to] = job.chunk;
        const label = `worker ${job.i + 1}/${chunks.length} frames ${from}-${to}`;
        console.log(label);
        await runPage(browser, `${base}/scripts/render.html?project=${projectName}&from=${from}&to=${to}`, label);
      }
    }),
  );

  const written = readdirSync(framesDir).filter(f => f.endsWith('.png')).length;
  if (!partial && written !== total) {
    throw new Error(`expected ${total} frames, found ${written} in ${framesDir}`);
  }
  console.log(`rendered ${written} frames in ${((performance.now() - started) / 1000).toFixed(1)}s`);

  if (!args['no-video'] && !partial) {
    const seconds = (total / fps).toFixed(6);
    const input = ['-y', '-loglevel', 'error', '-thread_queue_size', '512', '-framerate', String(fps), '-i', path.join(framesDir, '%06d.png')];
    const audio = existsSync(audioPath) ? ['-i', audioPath, '-af', 'apad', '-t', seconds] : ['-t', seconds];
    const out = args.lossless
      ? ['-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'bgr0', '-c:a', 'pcm_s24le', `${videoName}_master.mkv`]
      : ['-c:v', 'libx264', '-preset', 'slow', '-crf', '12', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-c:a', 'aac', '-b:a', '320k', `${videoName}.mp4`];
    const file = path.join(outputDir, out.pop());
    await ffmpeg([...input, ...audio, ...out, file]);
    console.log(`video: ${path.relative(root, file)}`);
    if (!args['keep-frames']) rmSync(framesDir, {recursive: true, force: true});
  }
} finally {
  await Promise.all(browsers.map(b => b.close()));
  await server.close();
}
