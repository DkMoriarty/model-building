# Alien Becker Style Bible

A **living** reference for how our figures are built, how they move and how
fights read. Every number here is a target the code implements. When you study
a new reference video, add a row to the source log (§9), update the rules it
changes, and bump the version.

**Version 1.0 · 2026-10-13**

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

\*Measured from reference material (§9). The traveller is deliberately outside
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
| anticipation (crouch, wind-up) | 3–8 (fast) · 18 (big swing) | 0.05–0.3 | always before jumps, swings, pulls |
| strike to contact | 6–11 | 0.10–0.18 | ease-in (accelerate into the hit) |
| **contact hold** | **2–4** | 0.03–0.07 | freeze on the hit before recoil reads |
| recoil coast | 30–36 | 0.5–0.6 | linear: impulse, then constant velocity |
| peak-pose hold before/after a burst | 2–4 | | punctuation |
| "discovery" / reaction hold | 12–24 | 0.2–0.4 | idle drift, head tilt |
| heavy push step | 12–16 per step | | torso leaning 30–45° |
| landing squash | 1–2 | | head may flatten slightly; knees compress |

**Feel**
- Fast acceleration into actions, cushioned (ease-out) arrival on key poses.
- Springs only with a settle tolerance and damping ratio around 0.6; cut
  tails at the next beat (`playUntil`).
- **Smears:** fast swings leave a swept-area trail, the last 3 frames of the
  blade filled at up to 22% opacity, scaled by tip speed. Slow moves leave
  none. Heavier trails read as solid wedges and clutter the hit.
- Weight: the heavier body recoils less (momentum split by mass), and leaning
  sells effort.

## 4. Fight grammar

- **Rhythm:** bursts of 1–2 s of action, then 0.5–1 s pauses so the audience
  registers the new state.
- **Every hit reads in four layers:**
  1. Contact on the cue frame, verified geometrically (`checkContact`).
  2. A 2–4 frame hold.
  3. Sparks: a white flash and straight streaks.
  4. Shake: 4 single-frame jolts of about 8 px, scaled by hit strength.
- **White-out flash** (2 frames) only on the biggest hits: about 1 per 20 s.
- **Escalation:** each exchange introduces one new idea, from simple clashes
  up to a set-piece finale.
- **Staging:** profile or semi-profile on a clean line, with opponents facing
  each other. Contact points are explicit, at blade crossings or the hilt,
  never "near".

## 5. Camera and layout

- 1920 × 1080, with a **96 px safe margin** for all text and HUD.
- Push in for intensity (flurry, lock), pull out to establish or resolve.
- Track the action's centre (the fight frame is the centre of mass, so the
  camera never jitters).
- Environment and diagram lines are 50–65% of the figure stroke, in neutral
  white or grey, with thin labels in sans or mono.
- Labels annotate; they don't present. Use small type and a thin gold rule,
  never boxes or slides.

## 6. Colour

- About 90% of the frame is near-black space plus neutral greys.
- Characters each get one saturated colour: the keeper red `#e63946`, the
  traveller green `#3ddc97`. No two characters share a hue.
- Gold `#ffd166` is reserved for payoffs: physics tags, measurement, collapse.
- White is for impact only: sparks and flashes.

## 7. Story without words

- Beats: barrier → curiosity (head tilt, pause) → manipulation → breakthrough.
- Body language: exhaustion is a dropped head and a slumped torso; triumph is
  an upright torso with arms out.
- Escalate ideas in steps (in our duel: classical, then relativistic, then
  quantum).

## 8. Sound

- One timeline: every hit sound is placed at the same cue the picture uses.
- Palette: metallic inharmonic clash, whoosh on smears, deep boom for big
  shifts, clicks for locking or measuring.
- Music swells at transformations and drops to drones during quiet beats.
  Duck the music under dialogue.

## 9. Source log

| date | source | method | key findings adopted |
| --- | --- | --- | --- |
| 2026-10-13 | "Animation vs. Geometry", Alan Becker channel (YouTube `VEJWE6cpqw0`, 9:02) | vidIQ visual analysis (no download) | figure 4.5–5 H; torso 1.3–1.5 H; limb segments 1.0–1.2 H; stroke 12–15% H; open-ring head; round caps; 3–8 f anticipation; 2–4 f holds; flash frames; 2–4 f shake at 5–10 px; environment lines 30–50% thinner; gold for climaxes; no dialogue |

**To add a source:** analyse a video for *technique* (proportions, timing,
staging, effects), then add a row here. Update §2–§8 where it changes a rule,
and bump the version below.

## 10. Changelog

- **1.0** (2026-10-13): first version. Head-unit spec, motion timing table,
  fight grammar, hierarchy and colour rules. Applied to `space_duel`.
