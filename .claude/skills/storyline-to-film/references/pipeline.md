# Build pipeline

All paths are relative to `alan_pipeline/`. FIRST GAME is the reference
implementation of every piece below.

## Data flow

```
tools/<ep>_timeline.py  (uses tools/<ep>_plans.py, tools/pong.py ...)
   -> audio/<ep>/story.json        (source of truth: events, sfx, music, plans)
tools/build_space_audio.py --episode <ep>
   -> audio/<ep>/master.wav + audio/<ep>/cues.json
src/<ep>/cues.ts  (imports cues.json: at, syncTo, duration, typed plan data)
src/<ep>/scenes/<ep>.ts -> acts -> components
scripts/render.mjs --project=<ep> --strict -> output_renders/<ep>.mp4
tools/frame_audit.py --episode <ep> -> output_renders/audit/<ep>_audit.md
```

Anything the scene needs from the plans (code lines, rallies, runner/dodge/
race plans, the villain's lines, engines) is written into story.json and
must be in the builder's pass-through tuple (`for key in ("code", "physics",
"rallies", "shadow")` in `build_space_audio.py`). Add new keys there.

## New episode checklist

1. `docs/episodes/<ep>.md` (story, see story.md).
2. `tools/<ep>_plans.py` (physics), `tools/<ep>_timeline.py` (events).
3. `src/<ep>/cues.ts`, `components/`, `acts/`, `scenes/<ep>.ts`, `src/<ep>.ts` project file.
4. Register: `vite.config.js` (project list), `scripts/render-entry.ts`,
   `scripts/render.mjs` PROJECTS (audio + video name), `package.json`
   (`render:<x>`, `audio:<x>`), `.gitignore` (`audio/<ep>/master.wav`), `CLAUDE.md` episode list.
5. Reuse the shared stage: `src/first_light/stage.ts` (`buildStage`, `reach`
   IK, `attach/detach`, `worldOf`, `plant`), `src/first_light/audit.ts`
   (`frameAuditor`), Spark (`components/Spark.ts`), Fx (`sparkBurst`, `shards`, `smoke`).

## Physics planners (Python)

- Name every constant (G = 1800 u/s^2 in the computer world; pong REACH,
  speeds; JUMP = -900; brake 1400 u/s^2; restitution 0.5).
- Return event times and the numbers the scene needs; assert the story's
  outcomes: a jump clears (h > block + 20), a clip really hits, a car's
  stopping distance exceeds its room, a jump span exceeds the gap, no two cars
  overlap, a falling block never lands on the hero.
- Use a seeded random search when an outcome needs specific timing (pong
  rallies: `pong.find`, seed 1729).
- The TypeScript side evaluates the SAME formulas per frame (e.g. race
  phases: acc / hermite / ease / fly). Keep one definition of each motion.

Worked examples: `pong.py` (per-frame collisions, frame-skip tunnelling,
paddles chasing at their real speed), `first_game_plans.py` (`runner`,
`dodge` with aimed blocks, `race` with two lanes, rams, braking, ramp jump,
plus `phase_state` to sample speeds for engine sounds).

## Scene rules

- `yield* syncTo('cue', lead)`; the lead must cover the action before it, or
  the probe prints `late`. Fix by shortening the action, not by moving cues.
- `s.spawn(task)` for anything that runs alongside; never a bare `yield task`.
- A spawned tween on a signal keeps writing until it ends: make it finish
  before the next act sets that signal (the door zoom that froze the camera
  for 7 s).
- `useTime` only inside threads; signals use `s.time()`.
- Cue names must be unique across the whole film (`ev()` asserts it); a
  duplicate silently moves the first one.
- Rig: hip/shoulder negative = forward, knee positive = flex, elbow negative
  = flex, left-facing = scale.x < 0. Positive rotation is clockwise on screen.
- Characters stand with `standHeight()`; hands touch things with `reach()`.
- Each world/universe lives at its own far x offset (10000, 40000, 50000,
  70000) so backgrounds never overlap.
- Camera: frame the subject inside the 96 px safe margin; the auditor ignores
  feet at zoom >= 1.8 and everything at zoom >= 4 (insert shots).

## Commands

```
python tools/<ep>_timeline.py && python tools/build_space_audio.py --episode <ep>
npm run typecheck
node scripts/render.mjs --project=<ep> --at=t1,t2,...     # stills + probe warnings
npm run render:<x>                                         # full --strict render
python tools/frame_audit.py --episode <ep>
```

Stills land in `output_renders/<ep>/`; tile them into contact sheets (PIL)
and read them. The probe prints every `late` beat, physics mismatch
(`paddle misses ...`) and F3s framing flag before rendering.

Shell gotcha: never `pkill -f` a pattern that also appears in your own
command line (it kills your shell). Use `pgrep` first, or kill by PID.
