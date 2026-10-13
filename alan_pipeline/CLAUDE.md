# Alien Becker studio (alan_pipeline)

Code-driven, deterministic Alan Becker-style animation on Motion Canvas.
**Read `ALIEN_BECKER_HANDOVER.md` first.** It has setup, architecture, the
engineering rules, current state and next steps.

Non-negotiables (details in the handover, §6):
- Every action anchors to an absolute cue with `syncTo(cue, lead)`. A
  `[warn] ... late` or `contact ... miss` line is a bug. Render with `--strict`.
- Rig sign convention, authored facing +x: hip/shoulder negative = forward,
  knee positive = flex, elbow negative = flex. Left-facing = `scale.x < 0`.
- Springs need a settle tolerance; cut tails with `playUntil`; lead contact
  springs by `springContactTime`.
- Never fire-and-forget with a bare `yield task`; use `stage.spawn(task)`.
- Fight blades meet via `solveContactSep` / `checkContact`, never eyeballed.
- `audio/<episode>/story.json` is the timing source of truth; rebuild audio
  with `npm run audio:space`. Never hand-edit `cues.json`.
- Check work with stills (`node scripts/render.mjs --project=space_duel --at=80,125`)
  before full renders.

Checks before any commit: `npm run typecheck`, and a probe/render with
`--strict` for any project you touched.
Never commit `audio/space_duel/master.wav` or `output_renders/`.
