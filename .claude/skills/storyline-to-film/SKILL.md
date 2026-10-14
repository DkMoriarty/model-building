---
name: storyline-to-film
description: Turn a short storyline from the user into a finished, production-ready 2D stick-figure animated film in the Alan Becker style (Motion Canvas, alan_pipeline): refine the story, plan real physics, build the timeline, animate, design the sound, verify every frame, render, and deliver a video that plays on a phone. Use whenever the user gives a storyline, plot, idea or "next episode" for a Spark film (or any new animated short in this repo), asks for a new episode, or asks to change an existing episode's story, picture or sound.
---

# Storyline to finished film

The user gives a storyline, often a few loose lines. You deliver a
finished film at the quality of FIRST GAME v4 (`alan_pipeline/src/first_game`),
which the user called "a perfect video". Everything below is what got it there.
Nothing ships until every check passes.

Work in `alan_pipeline/`. Read `alan_pipeline/CLAUDE.md`, `docs/STYLE_BIBLE.md`
(sections 5, 7, 8, 9) and `docs/LEARNING_LOG.md` before starting; they hold the
rules this skill refers to. FIRST GAME is the worked example of every step:
when in doubt, read how it was done there.

## The non-negotiables (from the user's own feedback)

1. **The audience always knows what the character wants.** Every want is an
   object on screen (C1-C10, style bible §7). If a beat is ambiguous, it is wrong.
2. **Everything works exactly like the real world, in 2D.** Jumps, falls,
   collisions, braking, ball flights and code are computed, never eyeballed.
   Code on screen is real code that does what we show (K1-K6).
3. **Perfect sync.** Every action lands on its cue (`syncTo`), every impact
   has a sound on the same frame, no late beats, no dead air.
4. **Every pixel counted.** The frame audit and the subject audit pass with
   0 hard flags. Declared exceptions carry a reason.
5. **Sound tells the story too:** a continuous score that a phone speaker can
   play, a sound for every hit and fall, dramatic beds for danger, human
   vocal reactions (laugh, oof, sigh), engines and mechanisms that follow
   their real physics. Comfortable to hear: nothing shrill.
6. **Keep what the user approved.** When the user approves part of a film,
   never change that part; extend from its last beat.
7. **Original characters and designs only.** Study references for technique;
   never download or copy videos, characters or music.

## Workflow (do every step, in order)

### 1. Refine the storyline (`references/story.md`)
- Restate the user's storyline as beats. Keep every beat they named, in their
  order. Fill gaps only with what the story needs to be clear.
- Apply the 9-beat framework and C1-C10: for each beat write want / goal object
  in frame / what we see / reaction. Find set-ups and pay-offs (rule of three,
  callbacks, the bookend).
- Write it to `docs/episodes/<episode>.md` (beat table + set-ups/pay-offs +
  anything changed from the user's text and why) and commit it.
- Only ask the user if a beat is truly contradictory; otherwise decide and say so.

### 2. Plan the physics (`references/pipeline.md` §Physics)
- Every motion with a real-world law gets a Python planner in `tools/`
  (see `tools/pong.py`, `tools/first_game_plans.py`): constants named,
  outcomes asserted (the jump clears, the car can't stop, no two bodies overlap),
  event times returned.
- Search parameters (seeded random walk) until the story outcome follows from the physics.

### 3. Build the timeline
- `tools/<episode>_timeline.py` writes `audio/<episode>/story.json`: events
  (unique names; `ev()` asserts this), sfx, music sections, music melody,
  silences, ducks, audit impacts/holds/declared, plus code/physics/plans data.
- `python tools/build_space_audio.py --episode <episode>` writes `master.wav`
  and `cues.json`. Never hand-edit `cues.json`. Rebuild after every timeline change.

### 4. Animate (`references/pipeline.md` §Scene)
- One act file per story section under `src/<episode>/acts/`, components under
  `components/`, the scene in `scenes/`. Register the project (vite config,
  render-entry, render.mjs PROJECTS, package.json scripts, .gitignore for master.wav).
- Every beat: `yield* syncTo('cue', lead)`. Fire-and-forget with `s.spawn`.
  Drive physics frame by frame from the plan data in `cues.ts`.
- Frame the subject inside the safe margin; declare deliberate exits in the
  scene's `frameAuditor` exemptions.

### 5. Design the sound (`references/audio.md`)
- Score: continuous sections covering the whole film, a melody in the
  phone band, low-passed at 4 kHz, ducked under moments a sound must own.
- Effects: one per impact, plus drama (panic/alarm beds, falling whistles,
  oof, laugh, sigh, crashes, screeches, engines from the speed curve).
- Measure the mix in the 300 Hz-4 kHz band; nothing important below -24 dB there.

### 6. Verify, then render (`references/qa.md`)
- `npm run typecheck`, stills with `--at=` across every act (read them!),
  fix, then `npm run render:<ep>` (`--strict`), then
  `python tools/frame_audit.py --episode <ep>`: 0 hard flags, sync 0, dead air 0.
- Audio-only changes: remux `master.wav` onto the rendered video; no re-render.

### 7. Deliver
- Make a phone-safe MP4: H.264 Main, yuv420p, AAC-LC 44.1 kHz stereo,
  `-movflags +faststart`, 1280 wide. Send it with SendUserFile as `attach`
  (the in-app preview may play muted; tell the user to download and play it).
- Commit (with the session's attribution lines) and push to the working branch.
  Never commit `output_renders/` or `master.wav`.
- Tell the user what they'll see and hear, beat by beat, and anything you changed from their storyline.

### 8. Learn
- Add every new lesson (from feedback or a bug) to `docs/LEARNING_LOG.md`,
  and promote lasting rules into the style bible or this skill.
