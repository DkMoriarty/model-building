import {defineConfig} from 'vite';
import motionCanvasPlugin from '@motion-canvas/vite-plugin';
import ffmpegPlugin from '@motion-canvas/ffmpeg';

// CommonJS/ESM interop workaround: the Motion Canvas plugins ship as CommonJS
// (`exports.default = ...`). Under `"type": "module"` Node hands us the whole
// `module.exports` object, so unwrap `.default` when it is present.
const unwrap = mod => (typeof mod === 'function' ? mod : mod.default);
const motionCanvas = unwrap(motionCanvasPlugin);
const ffmpeg = unwrap(ffmpegPlugin);

export default defineConfig({
  plugins: [
    motionCanvas({
      project: ['./src/project.ts', './src/space_duel.ts', './src/first_light.ts'],
      // Uncompressed PNG frames land here (fast NVMe frame cache).
      output: './output_renders',
    }),
    ffmpeg(),
  ],
  server: {
    port: Number(process.env.PORT ?? 9000),
    strictPort: false,
  },
});
