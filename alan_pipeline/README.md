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
npm run render -- --strict                 # fail if any beat lands late (CI / n8n)
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

## Projects

| project | what | render |
| --- | --- | --- |
| `alan_pipeline` | `opening_fight`: 5 s stick-figure test scene | `npm run render` |
| `space_duel` | **The Entangled Blade**: a 3 min 20 s narrated sword fight in space | `npm run render -- --project=space_duel` |

The editor (`npm start`) lists both projects.

### space_duel: The Entangled Blade

A relay keeper near the Moon is challenged by a traveller who arrives at 0.8c,
and they fight for one half of an entangled pair of blades. Each physics idea
on screen is computed, not hand-drawn:

| on screen | physics | where |
| --- | --- | --- |
| Ship shortened to 0.60 L₀ | Lorentz contraction, `1/γ` | `components/Ship.ts` |
| IR beacon seen as violet; hull lights redden, then vanish | relativistic Doppler `√((1+β)/(1−β))` + wavelength→colour | `physics.ts`, `Ship.ts` |
| Wavefronts bunch ahead of the ship | light emitted from past positions, growing at c | `Effects.ts: wavefronts` |
| "IMAGE ARRIVES" just before the ship | arrival time `d/c` vs `d/v` | `acts/arrival.ts` |
| Twin clocks: 5 years vs 3 | `dτ = dt/γ`, integrated each frame | `acts/arrival.ts` |
| Camera never moves during the fight | centre-of-mass frame: no external force | `stage.ts: bindToCentreOfMass` |
| Lighter keeper recoils 1.5× farther | `m₁Δv₁ = −m₂Δv₂` | `stage.ts`, `acts/fight.ts` |
| Tuck → faster spin, live ω readout | `ω = L / I(pose)`, I from joint positions each frame | `stage.ts: inertia`, `acts/fight.ts: spin` |
| Blade as a cloud of ghost angles | superposition weighted by `|ψ|²` | `components/Blade.ts` |
| Contact makes the ghosts vanish | measurement collapse | `acts/fight.ts` |
| Small wave packet passes the barrier | tunnelling `T ≈ e^(−2κd)` | `physics.ts`, `acts/fight.ts: tunnelling` |
| Keeper reads ↑, the other blade shows ↓ | singlet anti-correlation, no signalling | `acts/fight.ts: finale` |
| Sparks fly straight; the lost blade drifts and spins forever | Newton I, conserved angular momentum | `Effects.ts`, `acts/fight.ts` |
| Stars do not twinkle | no atmosphere | `components/Starfield.ts` |
| Sound "through steel, glove and bone" | vacuum carries no sound | narration |

**How everything lands on time:**
- **One timing file.** `audio/space_duel/story.json` holds all narration,
  events and sound effects.
- **Audio builder.** `tools/build_space_audio.py` synthesizes the narration,
  measures each clip, and fails if a line overruns its slot. It renders the
  music and effects at the same times, and writes `cues.json` for the scene.
- **Late beats.** Every action waits on `syncTo(cue)` and warns if it is late;
  `--strict` turns any warning into a failed render.
- **Blade contact.** Every clash is solved geometrically. Before each
  exchange, both strike poses are tried in place, and the exact separation at
  which the blades cross is found. On the contact frame the blade gap is
  measured, and it warns on a miss.
- **Fire-and-forget effects** (sparks, exhaust, shake) run on a
  scene-lifetime runner (`stage.spawn`). A bare `yield` fork would be
  cancelled when its parent returns, freezing an effect half-drawn.

```bash
npm run audio:space                                  # rebuild master.wav + cues.json
npm run render -- --project=space_duel --strict      # ~12,000 frames -> output_renders/space_duel.mp4
npm run render -- --project=space_duel --at=80,125   # just a few stills, for checking
```

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
4. **Audio is the clock.** Put transient times (and `bpm`) in
   `master_track.markers.json`, and anchor every action to them:
   - `yield* syncTo('impact', lead)` waits for a marker. If the timeline is
     already past it, it logs `syncTo("…") reached N ms late`. The renderer
     prints that, and `--strict` fails the render on it.
   - `springContactTime(spring, from, to)` is the lead that makes a spring
     *connect* on the marker (the fist hits on the drum, and the overshoot
     plays after it).
   - `playUntil('land', 0.25, ...reactions)` plays reactions in the background
     and cuts them off when the next beat needs the body. Without this, a
     ringing spring tail could push every later beat late.
   - Give each performer its own track (`function* redTrack()`, `blueTrack()`,
     …) and run them with `all()`, so one character's timing can never shift
     another's.

### StickFigure API

```ts
const fig = new StickFigure({x: -400, color: Colors.accent, pose: {rightShoulder: -30}});
fig.y(GROUND_Y - fig.legLength);

yield* fig.walkTo(200);                                    // turns to face, walks forward
yield* fig.walkTo(-200, {mode: 'backward', steps: 2, duration: 0.4}); // back-pedal
yield* fig.walkTo(40, {steps: 6, arriveAt: at('windup')}); // footfalls on the beat grid
yield* fig.pose({rightShoulder: 120, rightElbow: 70}, 0.3); // eased, parallel joints
yield* fig.springPose(StrikeSpring, {rightShoulder: -90});  // physics-driven
fig.bones.rightFist.absolutePosition();                     // attach FX / props
```

Joints: `torso, head, left/rightShoulder, left/rightElbow, left/rightHip,
left/rightKnee`. Angles are in degrees, local to the parent bone, and 0 means
the limb hangs straight down.

**Direction convention.** The rig is authored facing right (+x):

| joint | negative | positive |
| --- | --- | --- |
| hip / shoulder | swing forward | swing back |
| knee | (hyperextend, avoid) | flex: the shin folds back |
| elbow | flex: the forearm folds forward | (hyperextend, avoid) |
| torso / head | lean back | lean forward |

A left-facing figure is the same rig with `scale.x < 0` (`fig.face(-1)`), so
poses and gaits read correctly both ways.

**Gait.** `walkTo` does not tween legs on a clock. Each joint is computed from
how far the pelvis has travelled. The planted foot moves back relative to the
pelvis by exactly the distance the pelvis moves forward, so it never slides.
The stance leg stays straight, and the pelvis rides on it (a natural bob). The
swinging knee flexes to clear the ground. Steps are spaced evenly up to
`arriveAt`, so with eighth-note spacing every footfall lands on the beat.
Modes: `auto` (default) turns to face the target and walks forward; `forward`
does the same; `backward` keeps facing the same way and back-pedals with the
cycle reversed.

### Note on `.ts` vs `.tsx`

The spec names components `.ts`, so the nodes are built with constructors
(`new Line({...})`) instead of JSX. The Vite plugin's JSX setup is still active,
so any new file can be `.tsx`. Note that `ref:` only works in JSX. With
constructors, keep the instance in a variable instead.
