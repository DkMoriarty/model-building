# alan_pipeline

A deterministic, code-driven vector animation studio built on
[Motion Canvas](https://motioncanvas.io/) and strict TypeScript. It produces
Alan Becker-style stick-figure fights and desktop-UI gags with no generative
video: every frame is a pure function of code + time.

See [`ALAN_BECKER_PIPELINE_HANDOVER.md`](./ALAN_BECKER_PIPELINE_HANDOVER.md) for the original spec.

## Quick start

```bash
npm install
npm run doctor        # validate this machine (Node, CPU, RAM, disk, ffmpeg, Chromium, types)
npm start             # editor + live preview at http://localhost:9000
npm run serve         # same, exposed on the LAN (vite --host)
npm run render        # headless parallel render -> output_renders/opening_fight.mp4
```

### Render options

```bash
npm run render -- --concurrency=4          # worker processes (default 4, Legion 5 target)
npm run render -- --lossless               # FFV1 + 24-bit PCM master .mkv instead of H.264
npm run render -- --keep-frames            # keep the PNG sequence in output_renders/alan_pipeline/
npm run render -- --no-video               # PNG frames only
npm run render -- --audio=audio/other.wav --name=take2
```

`scripts/render.mjs` boots Vite in-process, probes the project length in a
headless Chromium page, splits the frame range into N contiguous chunks,
renders each chunk in its own Chromium process, and stitches the PNGs plus the
master audio with ffmpeg. Frame numbers are absolute, so chunks never collide.
Parallel output is verified **byte-identical** to a single-worker render.

Browser lookup order: `CHROME_PATH` → Playwright's Chromium → installed Chrome
→ installed Edge. On Windows the installed Chrome/Edge is usually picked up
automatically; otherwise run `npx playwright install chromium`. ffmpeg comes
bundled via `@ffmpeg-installer/ffmpeg` (override with `FFMPEG_PATH`).

## Layout

```
src/
  components/StickFigure.ts   hierarchical kinematic rig, joints exposed as signals
  components/UIWindow.ts      vector dialog window with spring pop-in / shake / press
  scenes/opening_fight.ts     test scene (function* generators, audio-synced)
  project.ts                  project config (scenes + master audio)
  project.meta                render settings: 1920x1080, 60 fps, PNG sequence
  styles.ts                   colours, strokes, typography, spring presets
  sync.ts                     syncTo(marker) - lock beats to audio transients
audio/
  master_track.wav            master audio (placeholder - replace with the real mix)
  master_track.markers.json   transient marker times in seconds
scripts/
  render.mjs                  parallel headless renderer + ffmpeg stitch
  render.html / render-entry.ts  in-browser render worker
  doctor.mjs                  environment validation
  make-placeholder-audio.mjs  regenerates the placeholder track from the markers
output_renders/               frames and videos (git-ignored)
vite.config.js                Motion Canvas + ffmpeg plugins, CJS/ESM interop fix
```

## Engineering rules

1. **Signal-driven reactivity.** Animate signals from generator functions
   (`yield* fig.joints.rightShoulder(-90, 0.2)`), never hand-placed keyframes.
2. **Hierarchical kinematics.** `StickFigure` nests one `Node` per bone, so a
   pose is just ten local angles and children inherit the parent transform
   exactly. No absolute coordinates are stored, so nothing drifts.
3. **Springs over linear easing.** Impacts, recoils and window arrivals go
   through `spring()` (`fig.springPose(Springs.recoil, {...})`,
   `dialog.popIn()`). Tune the presets in `styles.ts`; damping ratio
   ζ = d / (2·√(k·m)) ≈ 0.6 gives one overshoot and a quick settle. Always pass a
   settle tolerance (pixels/degrees), or a spring can run for seconds while it
   creeps toward the target by sub-pixel amounts.
4. **Audio is the clock.** Put transient times in `master_track.markers.json`
   and use `yield* syncTo('impact', lead)` so retiming one beat never shifts the
   rest.

### StickFigure API

```ts
const fig = new StickFigure({x: -400, color: Colors.accent, pose: {rightShoulder: -30}});
fig.y(GROUND_Y - fig.legLength);

yield* fig.walkTo(200);                                    // procedural gait
yield* fig.pose({rightShoulder: 120, rightElbow: 70}, 0.3); // eased, parallel joints
yield* fig.springPose(StrikeSpring, {rightShoulder: -90});  // physics-driven
fig.bones.rightFist.absolutePosition();                     // attach FX / props
```

Joints: `torso, head, left/rightShoulder, left/rightElbow, left/rightHip,
left/rightKnee`. Angles are in degrees, local to the parent bone, and 0 means
the limb hangs straight down.

### Note on `.ts` vs `.tsx`

The spec names components `.ts`, so the nodes are built with constructors
(`new Line({...})`) instead of JSX. The Vite plugin's JSX setup is still active,
so any new file can be `.tsx`. Note that `ref:` only works in JSX. With
constructors, keep the instance in a variable instead.
