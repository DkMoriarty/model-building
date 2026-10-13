// Writes audio/master_track.wav: a deterministic placeholder track with a low
// drone and a sharp transient at every marker in master_track.markers.json.
// Replace the .wav with the real mix and edit the marker times to match it.
import {readFileSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const audioDir = fileURLToPath(new URL('../audio/', import.meta.url));
const track = JSON.parse(readFileSync(audioDir + 'master_track.markers.json', 'utf8'));
const rate = track.sampleRate;
const length = Math.round(track.duration * rate);
const samples = new Float32Array(length);

// Drone (55 Hz + fifth) with a slow fade in/out.
for (let i = 0; i < length; i++) {
  const t = i / rate;
  const env = Math.min(1, t / 0.5, (track.duration - t) / 0.5);
  samples[i] =
    0.08 * env * (Math.sin(2 * Math.PI * 55 * t) + 0.5 * Math.sin(2 * Math.PI * 82.5 * t));
}

// Transients: decaying noise burst + pitch-dropping thump. Seeded PRNG keeps
// the file byte-identical between runs.
let seed = 1337;
const rand = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32) * 2 - 1;
for (const [name, at] of Object.entries(track.markers)) {
  if (name === 'end' || at <= 0) continue;
  const start = Math.round(at * rate);
  const hit = Math.round(0.25 * rate);
  for (let j = 0; j < hit && start + j < length; j++) {
    const t = j / rate;
    const thump = Math.sin(2 * Math.PI * (40 + 120 * Math.exp(-t * 30)) * t) * Math.exp(-t * 14);
    const click = rand() * Math.exp(-t * 90);
    samples[start + j] += 0.7 * thump + 0.35 * click;
  }
}

const data = Buffer.alloc(length * 2);
for (let i = 0; i < length; i++) {
  data.writeInt16LE(Math.round(Math.max(-1, Math.min(1, samples[i])) * 32767), i * 2);
}
const header = Buffer.alloc(44);
header.write('RIFF', 0);
header.writeUInt32LE(36 + data.length, 4);
header.write('WAVE', 8);
header.write('fmt ', 12);
header.writeUInt32LE(16, 16);
header.writeUInt16LE(1, 20); // PCM
header.writeUInt16LE(1, 22); // mono
header.writeUInt32LE(rate, 24);
header.writeUInt32LE(rate * 2, 28);
header.writeUInt16LE(2, 32);
header.writeUInt16LE(16, 34);
header.write('data', 36);
header.writeUInt32LE(data.length, 40);
writeFileSync(audioDir + track.file, Buffer.concat([header, data]));
console.log(`wrote audio/${track.file} (${track.duration}s, ${Object.keys(track.markers).length} markers)`);
