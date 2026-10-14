# Alien Becker Style Bible

A **living** reference for how our figures are built, how they move and how
fights read. Every number here is a target the code implements. When you study
a new reference video, add a row to the source log (§10), update the rules it
changes, and bump the version.

**Version 1.6 · 2026-10-14**

> **Originality rule.** This file records *technique*: proportion systems, timing,
> staging and effects grammar. It never copies characters. Our cast is
> original: the helmeted keeper, the long-limbed traveller, and anyone we add
> later. Do not recreate another creator's characters, colour schemes, or
> signature designs. Learn how they work, then design our own.

---

## 1. Principles

1. **Measured, not drawn by eye.** Every figure length is a ratio of H, the
   head's outer diameter. No loose pixel numbers in character code.
2. **Show, don't narrate.** Story is carried by poses, staging and timing. Voice
   is for a cold open and character dialogue only, never for explaining what is
   on screen.
3. **Hierarchy.** Characters are the thickest, most saturated lines in frame;
   the environment is thinner and quieter; accents (gold) are reserved for
   payoffs.
4. **Every beat is on a cue.** Actions anchor to absolute times from the
   soundtrack (`syncTo`). A late beat is a bug.

## 2. Figure construction (head-unit system)

`H` = head outer diameter. Implemented in `src/figureSpec.ts`.

| part | BIPED (keeper) | LONG_BIPED (traveller) | reference band* |
| --- | --- | --- | --- |
| head (ring, outer Ø) | 1.00 H | 0.85 × 1.30 H ellipse | 1.0 H ring |
| neck gap | 0.12 H | 0.35 H | small / none |
| torso | 1.40 H | 1.65 H | 1.3–1.5 H |
| upper arm / forearm | 1.05 / 1.05 H | 1.20 / 1.20 H | 1.0–1.2 H each, equal |
| thigh / shin | 1.15 / 1.15 H | 1.25 / 1.40 H | 1.0–1.2 H each |
| **total height** | **4.85 H** | **5.65 H** | 4.5–5 H |
| limb + head stroke | 0.14 H | 0.14 H | 12–15 % of H |

\*Measured from reference material (§10). The traveller is deliberately outside
the human band: it's an alien, and its ratios are still fixed and measured.

**Line rules**
- Round caps and round joins everywhere. Limbs end bluntly: no hands, no feet.
- The head is an **open ring**, the same weight as the limbs. Its outer
  diameter is exactly H, so the path is drawn at `H − stroke`.
- Props are lighter than limbs. The blade edge is 0.85 × the limb stroke;
  helmet and pack outlines are 0.45 ×.
- Prop sizes are in H too: keeper blade 3.2 H, traveller blade 3.6 H, helmet
  ring 1.45 H, pack 0.36 × 0.5 torso.
- **Scale rule:** set a figure's size with the node's `scale`, never by
  editing ratios. Default fight scale is 0.8 (keeper ≈ 217 px before camera zoom).

**Readability**
- Silhouettes must read at a wide-shot size of about 120 px tall: no limb
  thinner than 0.1 H on screen.
- Avoid tangents: limbs shouldn't run exactly along another figure's lines;
  stagger the y of opposing strikes (`sepY`).

## 3. Motion and timing (60 fps)

| action | frames | seconds | notes |
| --- | --- | --- | --- |
| anticipation (crouch, wind-up) | 2–4 (gesture) · 3–8 (fast) · 18 (big swing) | 0.03–0.3 | always before jumps, swings, pulls |
| strike to contact | 6–11 | 0.10–0.18 | ease-in (accelerate into the hit) |
| **contact hold** | **2–4** | 0.03–0.07 | freeze on the hit before recoil reads |
| recoil coast | 30–36 | 0.5–0.6 | linear: impulse, then constant velocity |
| peak-pose hold before/after a burst | 2–4 | | punctuation |
| reaction freeze (struck, startled) | 6–12 | 0.1–0.2 | snap in over 2 f, dead still, no overshoot |
| "discovery" / reaction hold | 12–24 | 0.2–0.4 | idle drift, head tilt |
| heavy push step | 12–16 per step | | torso leaning 30–45° |
| landing squash | 1–2 | | head may flatten slightly; knees compress |
| contact squash (prop or body hits a surface) | 1–2 | | props up to 1.4 : 0.6 (width : height); figures at most 1.2 : 0.8 |
| jump | 3 crouch · 6 flight · 2 landing | | short hops; scale flight with height |

**Feel**
- Fast acceleration into actions, cushioned (ease-out) arrival on key poses.
- Springs only with a settle tolerance and damping ratio around 0.6; cut
  tails at the next beat (`playUntil`).
- **Smears:** fast swings leave a crisp arc traced through the blade tip's last
  5 positions, at up to 55% opacity, scaled by tip speed. Slow moves leave
  none. Never fill the swept area: fast swings sweep 200° in a few frames,
  and the fill turns into a big translucent panel.
- Weight: the heavier body recoils less (momentum split by mass), and leaning
  sells effort.

## 4. Fight grammar

- **Rhythm:** bursts of 1–2 s of action, then 0.5–1 s pauses so the audience
  registers the new state.
- **Every hit reads in four layers:**
  1. Contact on the cue frame, verified geometrically (`checkContact`).
  2. A 2–4 frame hold.
  3. Sparks: a white flash and straight streaks.
  4. Shake, in one of three tiers by hit strength:

     | tier | amplitude | duration | use |
     | --- | --- | --- | --- |
     | minor | 6–10 px | 4–6 single-frame jolts | ordinary clashes |
     | medium | 12–15 px | 6–8 f, radial | heavy hits, body slams |
     | major | 20–25 px | decays over 20–40 f, after 2–3 f of solid white | **one per act**: the climax |
- **White-out flash** (2 frames) only on the biggest hits: about 1 per 20 s.
  The 3-frame solid white belongs to the major tier only.
- **Escalation:** each exchange introduces one new idea, from simple clashes
  up to a set-piece finale.
- **Staging:** profile or semi-profile on a clean line, with opponents facing
  each other. Contact points are explicit, at blade crossings or the hilt,
  never "near".

## 5. Composition, camera and layout

**Frame and placement** (1920 × 1080)
- **Safe margin:** 96 px for all text and HUD.
- **Ground line in calm beats:** two-thirds down the frame in open space, so
  feet sit at y ≈ +180 from centre. Headroom is 33–40% of frame height. When a
  floor or desk anchors the scene, drop it to 0.80–0.85 of the height.
- **Lead room:** a figure moving or facing right sits at 0.38 × width
  (x ≈ −230 from centre), and at 0.62 × width when facing left. Leave about 60%
  of the frame open ahead of it.
- **Calm beats:** keep 60–85% of the frame as negative space around the
  character.
- **Intense beats:** centre the action (the fight frame is the centre of mass)
  or pin it hard to an edge.

**Figure height by shot type** (on-screen, % of frame height)

| shot | figure height | ours |
| --- | --- | --- |
| wide / establishing | 8–15% | station shot, departure |
| medium | 25–35% | fight 24–30% (zoom 1.2–1.5) |
| close-up | 50–70% | (not yet used) |

**Background props** (ships, satellites, debris):
- Detail is layered: a silhouette on the structure tier, then inner plates,
  seams, rivets, vents and lights on the detail tier. Read the silhouette
  first; the detail rewards a second look.
- Every prop is an original design with plausible engineering. A satellite
  has a foil body, solar wings with cell grids, a dish, thrusters and a
  beacon. A ship has a hull, plates, nacelles, fins, a cockpit and running
  lights.
- **Travel lanes:** pass through open sky, never behind another silhouette
  at the same height (no tangents). Crossing behind a big foreground body,
  such as Earth's limb, is encouraged: free depth.
- Motion is constant velocity and spin (vacuum). Beacons blink once per
  second, or on the beat.

**Props relative to the figure:** handles and vertex dots are about 0.15 ×
figure height; small props 0.3–0.8 ×; set-piece objects 4–12 ×.

**Line-weight tiers** (`strokeTiers()` in `src/figureSpec.ts`):
- **Ratio:** figure : structure : detail = **3 : 2 : 1**. At our scale that's
  about 6.3 : 4.2 : 2.1 px on screen.
- **Vertex dots:** radius = 1.35 × the structure stroke.
- **Props at other node scales:** use `propStroke(tier, nodeScale)` so the
  on-screen ratio holds.

**Geometry drawing:** perfect primitives only, no wobble. Right-angle
brackets and arc notches are offset 1.5 × stroke from the corner. Construction
lines draw in with an eased trim from 0 to 100%, or snap in a single frame
when touched.

**Labels:** small sans or mono type, with 12–16 px padding from what they
annotate. Labels annotate, they don't present: a thin gold rule, never boxes or
slides.

**Camera:** heavy cubic ease in and out on pans and zooms (bezier
0.25, 0.1, 0.25, 1), so nothing stops dead. Push in for intensity and pull
out to establish or resolve. Track the action's centre.

**Rhythm**
- **Average shot length:** 4.5–8 s in exposition, 1.2–4 s in action. Cut
  on action: change the framing mid-move, never on a still.
- **Hold after a transformation or reveal:** 1.5–2 s (90–120 frames at
  60 fps) before the next action.
- **Burst:** an anticipation of about 15 frames at 60 fps, the action of
  about 25 frames, the contact in 4 frames, then follow-through.

**Glow:** a soft bloom at about 15–35% core opacity, fading over 80–120 px.
The vector edge itself stays razor sharp: never blur the line, only add
bloom behind it.

## 6. Colour

- About 90% of the frame is near-black space plus neutral greys.
- Characters each get one saturated colour: the keeper red `#e63946`, the
  traveller green `#3ddc97`. No two characters share a hue.
- Gold `#ffd166` is reserved for payoffs: physics tags, measurement, collapse.
- White is for impact only: sparks and flashes.
- **Our palette is our own.** References teach the *structure* of a palette
  (one saturated character colour, a near-black field, a neutral structure
  colour, one payoff accent). We don't adopt another creator's signature
  colours.

## 7. Story without words

**The story framework** (full reasoning: `docs/references/animation_vs_coding_story.md`)

| beat | runtime | job |
| --- | --- | --- |
| 1. Empty stage + simple want | 0–3% | one character, one object, one obvious wish |
| 2. First refusal | 3–8% | the first try fails physically. This is the hook, and it plants the loop the ending closes |
| 3. Sandbox | 8–25% | poke → observe → misuse → small win. Rules are taught by consequence |
| 4. Combination backfire | 25–40% | two things that work alone go wrong together; the tool acts on its own |
| 5. Midpoint arena shift | 40–50% | same rules, new genre or world: the second hook |
| 6. Tool turns on maker, then is turned back | 50–75% | survival, then mastery: the concept that hurt becomes the weapon |
| 7. Over-reach climax | 75–85% | caused by the character's own choice. Silence (S6), then overload |
| 8. Aftermath + synthesis | 85–97% | rebuild from the debris; tempo at least halved |
| 9. Callback + open loop | 97–100% | the first want is granted; a new presence appears |

- **The child rule:** the protagonist never knows more than the audience.
  Every new idea is discovered by trying something, never announced. A
  label may *name* a rule after the audience has seen it work. It never
  introduces one.
- **Cause → effect → new question:** each incident's consequence is the
  next incident's problem. Nothing is introduced for its own sake.
- **Saw tooth:** after every peak, a 2–5 s breather with a small comic or
  human moment, then a higher peak.
- **Concrete translation:** every abstract idea becomes a physical intuition
  a child already has (gravity, magnets, avalanches, dominoes).
- **Bookend:** the last meaningful image answers the first want.

**Clarity rules** (full study: `docs/references/clarity_study.md`). A
wordless film must never leave the audience asking what the character
wants:

| rule | requirement |
| --- | --- |
| **C1 Want = object** | every want is an object on screen, in the same frame as the character (a book, a socket, a switch), never an idea in their head |
| **C2 Gaze → reach → move** | at each new want the character looks at the goal for ≥ 12 f before reaching for it |
| **C3 The loop** | every scene runs want → try → result → **reaction** → new want; the new want grows out of the result |
| **C4 Reaction holds** | ≥ 12–24 f after every result; 1–2 s after a turning point |
| **C5 Rule of three** | the attempts that matter come in threes (fail, fail closer, succeed or overshoot) |
| **C6 Same-shot causality** | while a rule is taught, trigger and consequence share one shot; no cut between them |
| **C7 One action at a time** | while the key action plays, everything else holds still |
| **C8 Tool before use** | an object is seen (in a hand, on a shelf) before it changes the world |
| **C9 Pay-offs** | every set-up has a pay-off, and the final image answers the first want |
| **C10 Pull back to explain** | when something confusing starts, widen the shot to show the whole cause |

- Beats: barrier → curiosity (head tilt, pause) → manipulation → breakthrough.
- Body language: exhaustion is a dropped head and a slumped torso; triumph is
  an upright torso with arms out.
- Escalate ideas in steps (in our duel: classical, then relativistic, then
  quantum).
- **Open small:** start on a character playing with a small object (a nut,
  a pebble, a cursor) in a medium close-up. The toy's motion leads the eye
  to the inciting event, then the camera pulls out. Bookend it if you can
  (our nut drifts away at the start; the blade drifts away at the end).

## 8. Sound

- One timeline: every hit sound is placed at the same cue the picture uses.
- Palette: metallic inharmonic clash, whoosh on smears, deep boom for big
  shifts, clicks for locking or measuring.
- Music swells at transformations and drops to drones during quiet beats.
  Duck the music under dialogue.

## 9. Frame accounting: no frame unaccounted for

Every frame must be explainable: what is on screen, why it is there, where
it sits, how it got there, and what you hear. The rules below are numeric so
they can be checked, and most are checked automatically.

### 9.1 Framing (checked every 0.1 s from the scene graph: `src/space_duel/audit.ts`)

| rule | requirement | scope |
| --- | --- | --- |
| **F3s** safe margin | every subject point (each fighter's head, chest, hands, feet; a drawn blade's tip) stays inside the 96 px safe margin | hard: fails `--strict` |
| **F1s** subject balance | the subjects' centroid stays within ±25% of width and ±20% of height from centre | hard |
| **F2** negative space | 50–97% of the frame is empty (pixel-measured) | hard (`tools/frame_audit.py`) |
| F1 / F3 whole frame | whole-frame balance and border-band weight | info: set dressing may bleed off-frame |

Deliberate exceptions (an entrance, a tumble, the departure) are declared in
`EXEMPT` in `audit.ts`, each with a reason. An undeclared exception is a bug.

### 9.2 Objects: entry, growth, exit

**E1 Entry.** Every object arrives in one of four ways:
- **Along its motion line** from off-frame: satellites, debris, ships.
- **Scale-in from zero** with ease-out, at least 6 frames, overshoot no more
  than 8%: rings, dialogs, glints.
- **Draw-on** (path trim) with ease-out: lines, barriers, blades.
- **Fade**, at least 9 frames, and only for light and information: glows,
  labels, subtitles.

Nothing solid pops in on a single frame. Only impact flashes and sparks may.

**E2 Growth.**
- **Energy** (flashes, rings, wavefronts) expands with ease-out: fast start,
  soft finish.
- **Solid objects** grow with ease-in-out, then hold 2–4 frames at full size
  before anything else happens to them.

**E3 Exit.**
- **Mirror the entry** with an ease-in (accelerate away), no longer than the
  entry took.
- **Or keep going:** leave the frame along the motion line at constant speed
  (vacuum).
- Solid objects never fade out mid-frame unless the story says they vanish.

**E4 One focal entry at a time.** A new focal object enters only after the
previous one has settled, at least 6 frames apart. Background objects may
overlap focal entries.

**E5 Anchored.** Every entry and exit starts on a cue (`syncTo`), never on a
chained duration.

### 9.3 Sound (checked from the timeline: `tools/frame_audit.py`)

| rule | requirement |
| --- | --- |
| **T1 / S1** sync | every visible impact has a sound within ±1 frame, and every sound has a visual event within ±1 frame. No orphans. |
| **T2 / S2** grid | impacts land on the 8th-note grid of the score, within ±1 frame |
| **S3** size match | sound size tracks visual size: bigger sparks and harder shakes get louder hits; flashes get a sub-bass layer |
| **S4** designed silence | music drops under holds and reveals. Impact sounds lead the picture by 0 frames; whooshes may lead by 2–6 frames (anticipation). |
| **S5** vacuum honesty | only contact makes sound. Passing satellites, the comet and debris are silent. |
| **S6** silence before the climax | the major-tier hit is preceded by about 0.5 s (24–36 f) of near-silence: music and SFX duck at least 18 dB, then the hit lands at full scale |
| **S7** spawn sound | anything that appears on a cue (glyph, ring, panel, label) gets a sound on its first frame, or is declared silent in story.json. Ambient props fall under S5. |

### 9.4 Time

- **T3 dead air:** no stretch longer than 4 s with neither a cue (event, line
  or sound) nor visible motion, unless it is a declared hold (`HOLDS` in
  `frame_audit.py`).
- **Ledger:** every second of the film appears in the audit's per-second
  ledger with a named purpose. That is an event, a line, a sound, continuous
  action, or a declared hold.

### 9.5 How to check

```bash
node scripts/render.mjs --project=space_duel --at=1   # probe: F1s/F3s, late beats, contact misses
npm run render:space                                  # full render; --strict fails on any of the above
python tools/frame_audit.py                           # F2, T1-T3 + per-second ledger -> output_renders/audit/
```

The audit exits non-zero on any hard failure, so it can gate a pipeline run
(n8n, CI).

### 9.6 Reference studies

The numbers above are our house standard. Teardowns live in
`docs/references/`, one file per video, and record technique only. The
"Animation vs. Coding" teardown (v1.4) confirmed the 4 f minor shake, the
crisp vector smears and the medium-shot figure size. It added the reaction
freeze, the shake tiers, S6 and S7. Its head-size estimate (~25% of height)
conflicts with the Geometry pass, so it's left open until we measure it
from screenshots.

## 10. Source log

| date | source | method | key findings adopted |
| --- | --- | --- | --- |
| 2026-10-13 | "Animation vs. Geometry", Alan Becker channel (YouTube `VEJWE6cpqw0`, 9:02) | vidIQ visual analysis, pass 1: construction and motion (no download) | figure 4.5–5 H; torso 1.3–1.5 H; limb segments 1.0–1.2 H; stroke 12–15% H; open-ring head; round caps; 3–8 f anticipation; 2–4 f holds; flash frames; 2–4 f shake at 5–10 px; environment lines 30–50% thinner; gold for climaxes; no dialogue |
| 2026-10-13 | same video | vidIQ visual analysis, pass 2: composition and aesthetics | ground at two-thirds height; 33–40% headroom; lead room 0.38 / 0.62 × width; figure 8–15% / 25–35% / 50–70% of frame height (wide / medium / close); line tiers 3 : 2 : 1; vertex dots 1.35 × structure stroke; labels padded 12–16 px; cubic camera easing; average shot length 4.5–6 s (exposition) and 1.2–2.5 s (action); 1.5–2 s holds after reveals; soft bloom with sharp edges |
| 2026-10-14 | "Animation vs. Coding", Alan Becker channel (YouTube `EFmxPMdBqmU`, 9:27) | vidIQ long-form visual analysis (no download); notes in `docs/references/animation_vs_coding.md` | gesture anticipation 2–4 f; 6–12 f reaction freeze; contact squash 1.4 : 0.6 on props; three shake tiers (8 px × 4 f / 15 px × 8 f / 25 px decaying over 40 f after 3 f of white); ~0.5 s silence before the climax; SFX 1:1 with spawned elements; cut on action every 2–4 s; floor at 0.80–0.85 when present; negative space 60–85% |
| 2026-10-14 | same video, story pass | vidIQ visual analysis asked to watch as a viewer; notes in `docs/references/animation_vs_coding_story.md` | hook = the first attempt refused physically; the child loop (poke → observe → misuse → combine → consequence → recover); cause → effect → new question chain; tool turns on its maker; midpoint arena shift; over-reach climax; the ending answers the opening; saw-tooth tension |
| 2026-10-14 | "Animation vs. Math" (`B1J6Ou4q8vE`), "Animation vs. Physics" (`ErMSHiQRnc8`), "Animator vs. Animation" (`npTC6b5-yvM`), "Animation vs. Minecraft" (`GW_fdXHOWp4`) | vidIQ visual analyses for story clarity, as a first-time viewer; notes in `docs/references/clarity_study.md` | clarity rules C1–C10: want = object in frame, gaze → reach → move, the want/try/result/reaction loop, reaction holds, rule of three, same-shot causality, one action at a time, tool before use, pay-offs, pull back to explain |
| next | a fight-focused video; screenshot measurements to settle head size | vidIQ and/or user screenshots measured frame by frame | pending |

**To add a source:** analyse a video for *technique* (proportions, timing,
staging, effects), then add a row here. Update §2–§8 where it changes a rule,
and bump the version below.

## 11. Changelog

- **1.6** (2026-10-14): §7 clarity rules C1–C10 from a four-film clarity
  study. FIRST LIGHT diagnosed against them; v2 script written.
- **1.5** (2026-10-14): §7 story framework: a 9-beat structure with runtime
  percentages, the child rule (labels name rules, never introduce them),
  cause → effect → new question, saw-tooth tension, the bookend.
- **1.4** (2026-10-14): "Animation vs. Coding" teardown. Reaction freeze,
  contact squash ratio, jump timing, three shake tiers, S6 (silence before
  the climax), S7 (spawn sounds), cut-on-action rhythm, floor height when
  present, wider negative-space band. Head size left open.
- **1.3** (2026-10-14): §9 Frame accounting. Subject framing and balance
  (F1s/F3s) measured from the scene graph every 0.1 s; negative space,
  sound sync, beat grid and dead air checked by `tools/frame_audit.py`.
  Entry, growth and exit grammar (E1–E5); sound rules (S1–S5).
- **1.2** (2026-10-14): background-prop rules (layered detail, original
  engineering, travel lanes, depth crossings). Toy-first opening (a small
  object sets the story in motion).
- **1.1** (2026-10-13): composition pass. Placement and headroom, figure
  height by shot type, the 3 : 2 : 1 line tiers (encoded as `strokeTiers`
  and `propStroke`), vertex-dot size, label padding, camera easing, rhythm,
  glow (soft bloom, sharp edge). Smears are now a tip-path arc, not a filled
  swept area.
  Added the palette originality note.
- **1.0** (2026-10-13): first version. Head-unit spec, motion timing table,
  fight grammar, hierarchy and colour rules. Applied to `space_duel`.
