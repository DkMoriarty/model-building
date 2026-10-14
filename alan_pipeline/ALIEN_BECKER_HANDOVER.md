# Alien Becker — Handover to Claude Code Desktop

> **For Claude Code:** this is the complete handover for the **Alien Becker** studio:
> code-driven, deterministic vector animation (Alan Becker style) built on
> Motion Canvas. Read it fully before changing anything. It supersedes nothing
> in `ALAN_BECKER_PIPELINE_HANDOVER.md` (the original spec); it records what
> was built, what was learned, and how to continue. **Also read
> `docs/STYLE_BIBLE.md`** before touching any figure, motion or fight code.

**Owner:** Dhiraj · **Repo:** `github.com/DkMoriarty/model-building` · **Project folder:** `alan_pipeline/`
**Target machine:** Lenovo Legion 5 (Windows, 4 GB VRAM, multi-core CPU, NVMe SSD)

---

## 1. Mission

Produce Alan Becker–style stick-figure animation **entirely from code**:
no generative AI video, zero drift, frame-perfect. Every frame is a pure function
of code + time. Picture, dialogue, music and sound effects come from one
timeline, so nothing lands off its beat.

## 2. Current state (as of 2026-10-13)

| item | status |
| --- | --- |
| PR #1: pipeline scaffold, `StickFigure`, `UIWindow`, `opening_fight` (5 s test), parallel renderer, doctor | **merged** into `main` |
| PR #2: `space_duel`, "The Entangled Blade" (3 min 20 s physics-true space sword fight, told visually), shared timeline, audio builder, faster renderer | **open**: https://github.com/DkMoriarty/model-building/pull/2 |
| Revision 2 (in PR #2): explanatory voice-over removed (only a one-line cold open + the traveller's two lines remain); figures rebuilt from a measured head-unit spec; contact holds, flash frames, tight shake, smear trails; quieter physics tags; living style bible | **done**, `--strict` clean |
| Working branch | `claude/motion-canvas-pipeline-init-ky3xh9` (PR #2 head) |
| Last full render | `space_duel.mp4`: 12,001 frames, 1080p60, AAC, 3:20.04, `--strict` clean, rendered in about 12 min on 4 workers |

**Not yet done:** a render on the Legion 5 itself (every render so far ran in a
Linux cloud container).

## 3. First-run setup on the Legion 5 (Windows)

```powershell
# Prerequisites: Git, Node.js 18.18+ (22 LTS recommended), Python 3.10+, Chrome or Edge
git clone https://github.com/DkMoriarty/model-building
cd model-building
git checkout claude/motion-canvas-pipeline-init-ky3xh9   # until PR #2 is merged; then use main
cd alan_pipeline
npm install
npm run doctor            # must end with "All checks passed."
```

**Space-duel soundtrack.** `audio/space_duel/master.wav` is git-ignored (38 MB). Build it once:

```powershell
pip install numpy
npm run audio:space       # rebuilds master.wav + cues.json from story.json and the committed voice clips
```

Piper (the TTS tool) is **only** needed when a spoken line's text changes; see §7.

**Browser for rendering.** The renderer tries `CHROME_PATH`, then
Playwright's Chromium, then installed Chrome, then installed Edge. On Windows,
installed Chrome or Edge is usually found automatically. If not:
`setx CHROME_PATH "C:\Program Files\Google\Chrome\Application\chrome.exe"`,
then open a new terminal.

## 4. Commands

| command | does |
| --- | --- |
| `npm start` | Editor + live preview at http://localhost:9000 (lists both projects) |
| `npm run serve` | Same, exposed on the LAN |
| `npm run typecheck` | Strict TypeScript check |
| `npm run doctor` | Validates Node, CPU, RAM, disk, ffmpeg, Chromium, typecheck |
| `npm run render` | Renders `opening_fight` → `output_renders/opening_fight.mp4` |
| `npm run render:space` | Renders `space_duel` with `--strict` → `output_renders/space_duel.mp4` |
| `npm run audio:space` | Rebuilds the space-duel soundtrack and cue sheet |

**Render flags** (`node scripts/render.mjs …`):

| flag | does |
| --- | --- |
| `--project=NAME` | `alan_pipeline` (default) or `space_duel` |
| `--concurrency=4` | Number of Chromium workers |
| `--strict` | Fail if any beat lands late or a blade contact misses |
| `--at=80,125.5` | Render only the frames at those seconds: fast visual checks |
| `--frames=A-B` | Render only that frame range |
| `--keep-frames` | Keep the PNG sequence |
| `--no-video` | PNG frames only |
| `--lossless` | FFV1 `.mkv` master |

`RENDER_BROWSER_ARGS` overrides the Chromium flags (default `--disable-gpu --mute-audio`).

## 5. Architecture

```
alan_pipeline/
  src/
    timeline.ts            createTimeline(): at / syncTo / playUntil; springContactTime()
    sync.ts                opening_fight's timeline (audio/master_track.markers.json)
    styles.ts              palette, strokes, typography, spring presets
    components/
      StickFigure.ts       hierarchical rig: 10 joint signals, pose/springPose/face/walkTo
      UIWindow.ts          vector dialog: popIn (spring), shake, press
    scenes/opening_fight.ts
    project.ts             project "alan_pipeline"
    space_duel.ts          project "space_duel"
    space_duel/
      cues.ts              timeline from audio/space_duel/cues.json (events + "nX.start/end")
      physics.ts           gamma, Doppler, wavelength→colour, tunnelling, seeded PRNG
      stage.ts             Stage (camera, layers, cast), centre-of-mass binding, inertia(),
                           bladeContact(), everyFrame(), spawn()/runner()
      components/          Starfield, Scenery (Earth/Moon/station), Ship, Blade, Fighters, Hud, Effects
      acts/                arrival.ts (0–77 s), fight.ts (77–178 s), departure.ts (178–200 s)
      scenes/space_duel.ts all(story, subtitles, runner)
  audio/
    master_track.wav + .markers.json        opening_fight
    space_duel/story.json                   SOURCE OF TRUTH: lines, events, sfx, music
    space_duel/cues.json                    generated: resolved times the scene animates to
    space_duel/voice/*.wav + *.key          cached TTS clips (committed): n1, a1, a2
  docs/STYLE_BIBLE.md                       living style guide: measured figures, timing, fight grammar
  src/figureSpec.ts                         head-unit figure system (BIPED, LONG_BIPED)
  tools/build_space_audio.py                TTS + numpy synth + mix + overrun check
  scripts/render.mjs, render-entry.ts, render.html, doctor.mjs
```

**Data flow (space_duel):**
`story.json` → `build_space_audio.py` → (`master.wav`, `cues.json`) →
`cues.ts` → acts use `at()` / `syncTo()` → renderer → mp4 with `master.wav` muxed.

## 6. Engineering rules (follow these exactly)

These are the original spec's rules plus everything learned while building.
Each one exists because breaking it caused a real bug.

### Rig and motion
1. **Signals and generators, not keyframes.** Animate signals inside
   `function*` with `yield*`.
2. **Hierarchical kinematics.** One nested `Node` per bone, and a pose is just
   the joint angles. Never store absolute limb coordinates.
3. **Sign convention.** The rig is authored **facing +x**:
   - hip/shoulder: negative = forward
   - knee: positive = flex
   - elbow: negative = flex
   - torso: positive = lean forward

   A left-facing figure is `scale.x < 0` (`fig.face(-1)`); never mirror angle tables.
4. **Angles past ±180 are fine and meaningful.** A swing from 150 to 235 goes
   over the top. From 150 to −125 it would swing through the bottom.
5. **`walkTo` is distance-derived** (zero foot-slip). Use `mode: 'backward'` to
   back-pedal, `arriveAt` to land the last footfall on a cue, and
   `settle: false` to flow straight into the next action.
6. **No JSX `ref:` in `.ts` files.** Components are built with constructors;
   keep instances in variables.

### Timing
7. **Every action anchors to an absolute cue:** `yield* syncTo('cue', lead)`.
   Never chain durations to reach a beat.
8. **`syncTo` warns when late.** Treat every warning as a bug, and render with
   `--strict`.
9. **Springs settle asymptotically**, on velocity as well as position. Always
   pass a settle tolerance; prefer project presets with damping ratio around
   0.6 (`styles.ts: Springs`). Cut ringing tails with
   `playUntil(nextCue, lead, …)`.
10. **For contact on the beat, lead a spring by `springContactTime(spring, from, to)`.**
    The fist or blade connects on the cue, and the overshoot plays after it.
11. **One track per performer** (`function* redTrack()`, `blueTrack()`, …),
    run with `all()`, so one character's overrun never shifts another's.
12. **Never fire-and-forget with a bare `yield task`.** Forked tasks are
    cancelled when their parent returns, which freezes sparks and puffs
    half-drawn on screen. Use `s.spawn(task)` (scene-lifetime runner).
13. **Background effects must not extend `all()`.** For example, exhaust puffs
    outlive their burn; spawn them.

### Space-duel specifics
14. **Blade contact is solved, never eyeballed.** `solveContactSep()` tries both
    strike poses in place, scans the separation, and restores everything in the
    same frame. `checkContact()` measures the gap on the contact frame. Add
    every new strike through `exchange()` or `quickStrike()`.
15. **Fight positions are in the centre-of-mass frame:** `bindToCentreOfMass()`.
    Move fighters only through `s.sep`, never their positions directly.
16. **Absolute vs world space:** blade tips and contacts are absolute (screen)
    coordinates. Effects placed from them use `node.absolutePosition(p)`.
17. **Physics labels must be true.** Compute numbers in `physics.ts`; never
    hand-type a result.

### Audio
18. **`story.json` is the source of truth.** After editing it, run
    `npm run audio:space`. The build **fails** if a spoken line overruns
    its slot; fix the times, never the check.
19. **Piper TTS is not bit-deterministic.** Cached clips in
    `audio/space_duel/voice/` are the source of truth, and re-synthesis only
    happens when a line's text, voice or speed changes (`.key` hash).
20. **Physics honesty:** vacuum carries no sound (an on-screen tag says audio
    is contact vibration), and entanglement carries no message (the
    no-signalling tag appears after the finale).

### Rendering
21. **CPU rasterization (`--disable-gpu`) is the default.** It is deterministic
    across machines and about 3× faster than SwiftShader for 2D canvas.
22. **Verify with stills before full renders:** `--at=t1,t2,…`, then tile them
    with ffmpeg and look.
23. **Parallel output must stay byte-identical** to single-worker output
    (verified for `opening_fight`).

### Style (see docs/STYLE_BIBLE.md)
24. **Show, don't narrate.** Voice is only for a cold open and character
    dialogue. Never add voice-over that explains what's on screen.
25. **Figures are measured.** Build every figure from `src/figureSpec.ts` (all
    lengths are ratios of H, the stroke is 0.14 H, heads are open rings).
    Size with node `scale`, never by editing ratios. New body types get a new
    spec, documented in the style bible §2.
26. **Every hit has four layers:** contact on the cue frame, a 2–4 frame hold,
    sparks, and a short shake (4 single-frame jolts). White-out flashes only
    on the biggest hits, about 1 per 20 s.
27. **Hierarchy:** characters get the thickest, most saturated lines;
    environment lines are 50–65% of the figure stroke; gold only for payoffs;
    text sits inside the 96 px safe margin.
28. **Originality:** study references for technique only. Our characters are
    original; never recreate another creator's characters or signature designs.
29. **Keep the style bible alive:** after analysing a new reference, add a row
    to its source log and update the rules it changes.

## 7. Changing spoken lines (Piper TTS)

```powershell
pip install -r tools/requirements.txt          # numpy + piper-tts
mkdir tools\voices; cd tools\voices
curl -LO https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-en-us-ryan-high.tar.gz
curl -LO https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-en-gb-alan-low.tar.gz
tar xzf voice-en-us-ryan-high.tar.gz; tar xzf voice-en-gb-alan-low.tar.gz
cd ..\..
npm run audio:space
```

- **Lines in use:** `n1` (cold open), `a1`, `a2` (the traveller). Keep it
  that way: the story is told visually (rule 24).
- **Voices:** narrator `en-us-ryan-high` (length scale 1.08); alien
  `en-gb-alan-low`, slowed and lowered, with ring modulation and a flange.
- **Measured pace:** about 2.9 words per second. Leave at least 0.25 s between
  lines; the build enforces it.
- **To use a human voice:** overwrite `audio/space_duel/voice/<id>.wav` with
  the recording (mono, any sample rate, silence trimmed). **Keep the matching
  `.key` file:** while the key matches the line's text, the builder uses the
  WAV as-is. A missing or stale key makes it re-synthesize and overwrite your
  recording. Then run `npm run audio:space`. A longer recording that overruns
  its slot fails the build; adjust `at` times in `story.json`.

## 8. Recipe: making the next episode

1. **Story first.** Write `audio/<episode>/story.json`: lines, named events
   (one per beat), sfx (anchor to events or `"lineId.end"`), and music
   sections at a fixed bpm.
2. **Build audio.** Generalize `build_space_audio.py` to take the episode
   folder as an argument (see §9), then run it until no overruns remain.
3. **Project file.** Add `src/<episode>.ts` (`makeProject`) and register it in:
   - `vite.config.js` (`project: [...]`)
   - `scripts/render-entry.ts` (`projects` map)
   - `scripts/render.mjs` (`PROJECTS` map: audio + video name)
4. **Stage + acts.** Copy the `space_duel` structure: build nodes once in
   `stage.ts`, and one generator per act, each starting with `syncTo(firstCue)`.
5. **Probe often:** `node scripts/render.mjs --project=<episode> --at=…` and
   read every `[warn]`.
6. **Full render** with `--strict`, then spot-check frames across all acts.
7. **Commit** story, cues, voice clips and code. Never commit `master.wav` or
   `output_renders/`.

## 9. Known limitations and next steps (priority order)

1. **Render on the Legion 5**, then fill in the last PR #2 test-plan box. Check
   `npm run doctor`; try `--concurrency=6` or `8` if there are more cores.
2. **Generalize the audio builder:** `build_space_audio.py --episode <dir>`, a
   `--keep-voices` flag that protects human recordings, and `python3`/`python`
   handling in npm scripts across platforms (the script currently calls
   `python`, which suits Windows).
3. **Shared fight kit:** move `exchange`, `quickStrike`, `solveContactSep`,
   `checkContact`, `burn` and `shake` from `acts/fight.ts` into a reusable
   `src/kit/` so new episodes don't copy them.
4. **Fighter scale:** figures are small in wide fight shots; consider a closer
   default camera (world scale 1.3–1.5) and bigger HUD type for phone viewing.
5. **Better voice:** Piper is decent but robotic. A recorded or premium voice
   drops in through the voice-clip slots (§7).
6. **Thumbnail and Shorts cuts:** add `--at` presets for thumbnail stills and a
   9:16 crop option to the renderer.
7. **n8n hook:** `npm run render:space` already exits non-zero on any timing or
   contact failure, so it is safe to call from an n8n Execute Command node.
   Output lands in `output_renders/`.

## 10. Gotchas already hit (don't repeat them)

| symptom | cause | fix |
| --- | --- | --- |
| Walk looked backwards | hip sign wrong for facing; knee bent the wrong way | sign convention (§6.3), distance-derived gait |
| Beats drifted 0.3–0.5 s late | spring tails inside `all()` delayed the next beat | per-performer tracks, `playUntil`, stiffer springs |
| Probe hung forever | scene threw (`ref:` outside JSX), Player never finished | logger errors fail the probe fast |
| Grey blobs frozen on screen | bare `yield` forks cancelled with their parent | `stage.spawn()` runner |
| ~6 s per frame on 4 workers | SwiftShader emulated GPU | `--disable-gpu` (CPU raster) |
| `NaN` colour crash | `Math.pow` of a negative channel for UV wavelengths | return transparent outside 380–780 nm |
| Disarm missed by 300+ px | strike pose solved before the target pose settled | solve after the pose settles; search arm angle too |
| `pkill -f <pattern>` killed its own shell (Linux) | the pattern matched the command line | kill by PID |
| Figures looked random | loose pixel lengths per character | head-unit spec (`figureSpec.ts`) |
| Smear trails read as solid wedges | 4-frame history at 40% opacity | 3 frames, up to 22%, scaled by speed |
| Video felt like a lecture | explanatory voice-over | cut to cold open + dialogue; small tags |

## 11. Kick-off prompt for Claude Code Desktop

Open a terminal in `model-building/alan_pipeline` and run:

```
claude "Read ALIEN_BECKER_HANDOVER.md and CLAUDE.md. Validate this machine with npm run doctor, build the space-duel soundtrack with npm run audio:space, then render it with npm run render:space and report timing, any [warn] lines, and the output file. Do not change code until the render passes."
```
