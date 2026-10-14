# Teardown: "Animation vs. Coding" (technique only)

- **Source:** Alan Becker channel, YouTube `EFmxPMdBqmU`, 9:27, published 2025-03-01.
- **Method:** vidIQ long-form visual analysis on 2026-10-14. We didn't download
  or keep any copy of the video, and we copied no characters or designs.
- **Confidence:** the numbers below are an AI's estimates from watching the
  video, not pixel measurements. Treat them as ranges. Confirm any rule they
  change against our own renders, or against screenshots measured frame by
  frame. The analysis covers 0:00–8:24. The last minute isn't segmented.

## What the film does, by segment

| time | staging | motion / hits | camera | sound |
| --- | --- | --- | --- | --- |
| 0:00–0:15 | static wide; ground ~0.85 down; one small prop (laptop); ~80% empty | stand-up with 4 f crouch anticipation; wave = 2 f anticipation, 3 f extend, 8 f hold | locked off | typing clicks 1:1 with each glyph appearing |
| 0:15–0:30 | text spawns mid-frame (0.35–0.50 high) | recoil 3 f, settle 12 f; error box pops with no anticipation, 1 f hold | static | error buzz on pop; typing **stops dead for ~0.5 s** to land the error |
| 0:30–0:45 | figure at x ≈ 0.65, text centre-left | 8 f walk cycle (4 f per step); reaction snap 2 f then a **10 f freeze**, no overshoot | static | drag whoosh tracks drag speed |
| 0:45–1:05 | text block left (0.25–0.45), figure right (0.70) | results snap in on a single frame | static | confirm tone exactly on evaluation |
| 1:05–1:25 | wide | recoil jump: 2 f ease-in, 8 f arc; **minor shake ~8 px × 4 f** | static | heavy thud on the contact frame |
| 1:25–1:50 | ground drops to ~0.90; full-width run | exits right at ~12 px/f; 4 f skid with dust at the feet | horizontal tracking pan | rhythmic bursts matched to repeated output |
| 1:50–2:25 | no ground; free 2D space | wall impact: **1 f squash 1.4 × 0.6**, 2 f white flash, 12 px shake × 6 f | crash zoom-out cut, whip pans | pitch ramps up with the recursion |
| 2:25–3:00 | lines drawn across the whole canvas | 2 f anticipation flip; trail smears along paths | **cut on action every 2–4 s**, wide ↔ medium | continuous draw buzz, clicks on each corner |
| 3:00–3:45 | dense vertical mesh, full height | jump: 3 f crouch, 6 f flight, 2 f landing compression | constant-speed auto-scroll | whoosh per thick stroke |
| 3:45–4:40 | chart axes become terrain | ledge grab snaps in 1 f, 4 f swing hold | stepped zooms and pans along the path | render blips synced to each bar pop |
| 4:40–5:20 | floor ~0.80; 3 elements total | push: 45° lean, 8 f loop, friction dust | fixed, with snap cuts | thud on landing |
| 5:20–6:20 | window chrome as set | ball: 2 f squash, **radial shake 15 px × 8 f** | pans up with the dragged window | sub-bass thud on contact |
| 6:20–7:15 | escalation to full-frame blast; figure tiny (~0.08) | **3 f solid white**, then shake 25 px decaying over 40 f | crash zoom from close-up to extreme wide | **~0.5 s of silence before the blast**, then a saturated boom |
| 7:15–8:24 | dense network stage, split layout | radial glow pulses on a 12 f cycle | slow diagonal macro pan | ambient hum with rhythmic pulses |

## Rules it suggests (and what we did with them)

| finding | our current rule | decision |
| --- | --- | --- |
| Anticipation 2–4 f on small moves | 3–8 f | widen to **2–8 f**; 2 f is fine for gestures |
| Reaction / impact freeze 6–12 f | contact hold 2–4 f; discovery hold 12–24 f | add a **6–12 f reaction freeze** between them (a struck or startled figure) |
| Contact squash 1–2 f at about 1.4 : 0.6 | landing squash 1–2 f, no ratio given | adopt the ratio for **props and bodies hitting surfaces**; figures squash to at most 1.2 : 0.8 so they stay "measured" |
| Shake tiers: minor 6–10 px × 4–6 f; medium 12–15 px × 6–8 f; major 20–25 px decaying over 20–40 f, after 2–3 f of white | single tier: 4 jolts × 8 px; white-out 2 f | adopt **three shake tiers**; the major tier is reserved for one moment per act |
| Silence before the biggest impact (~0.5 s) | not specified | adopt as **S6** |
| SFX 1:1 with every element that appears | S-rules cover hits | extend: anything that **spawns** gets a sound, or is declared silent |
| Cut on action every 2–4 s in action | 1.2–2.5 s action shot length (Geometry) | keep; Coding sits slightly longer, so the range is now **1.2–4 s** |
| Ground at 0.80–0.85 of height in desk scenes | two-thirds | episode-dependent: two-thirds for open space, **0.80–0.85 when a floor or desk anchors the scene** |
| Negative space 60–85% in calm shots | 70–80% | widen to **60–85%** |
| Figure 30–35% of height in medium shots, 8–15% in extreme wides | 25–35% / 8–15% | confirmed |
| No raster motion blur; vector smears for 1–2 f only | crisp tip-arc smears | confirmed |
| Head drawn as a solid ring | open-ring head | **keep ours.** This is a house design choice, not a measurement |
| Head about 25% of standing height | about 21% (4.85 H) | **keep ours.** It conflicts with the Geometry pass (4.5–5 H), so a screenshot measurement must settle it before we change anything |
