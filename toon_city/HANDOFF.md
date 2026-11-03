# HANDOFF — state at the end of the cloud session

## What the user is making

An animated short in the **Ink Industries** look (references 03–09): stylised
3D characters with matte vinyl/clay surfaces, sculpted planar faces, huge
expressive eyes, ribbon-lock hair, hard golden-hour light with a hot rim,
AgX grade, shallow depth of field.

The story beat (CROSSWALK): **a young guy cruising on a fixie; a girl
suddenly steps onto the crosswalk; he slams the brakes, almost falls on her
(stoppie), stops nose to nose and is completely struck by her looks.**

The user's order of work (they were firm about it):

1. **Finalise the faces first** — his, then hers. ("First face should finalise.")
2. Then facial **expressions and key frames**. ("Those are imp.")
3. Then push for the **video** (CROSSWALK render + soundtrack).

## Where we are

| | Status |
|---|---|
| **Him** (fixie rider) | Face rebuilt to the tennis-boy reference (08) by measured layout; user said **"Doable"** → treat as provisionally approved. Ribbon hair, wedge→bushy brows, tan skin, near-black matte hair, heavy lids. |
| **Her** | Several reference switches; current target is reference **09** ("Thanks" girl). Latest: *shield* head (wide flat upper face → small chin), big up-slanted almond eyes, thin high brows, small lips, long thin neck, centre-part low ponytail, blue knit + white collar, silver hoops. Turntable symmetry fixed. **Not approved** — the user keeps saying it is not like her. Local session 2026-11-03 (user's Blender 3.3.1, live via MCP): bigger irises (`iris=1.0`), near-black iris, big flared soft ears at eye level (`ear_x/ear_flare/ear_soft`), hoops hung from the lobes, fuller lips (`lip_t`, `pout=0.8`), narrower chin taper, lower brows, stronger nose and blush; hair: no scalp showing (user: "her scalp should not be visible", "hair can be more"), symmetric cap down over the temples to the ears, lower hairline, curtain strands framing the forehead, more combs and loose strands. User said "Closer"; still not final. |
| Local session 2026-11-03/04 (round 2) | User: "face just now done" (hers). **Him:** lighter bushy brows (`brow_k`), ragged fringe over the forehead (`wild_fringe`, finer cap mesh, no skin gaps), bigger irises, heavier liner, COOL = heavy lids + sideways glance. **Outfits (user's ask):** him in a white ribbed baniyan, muscular build (V torso, traps, thick neck, shaped arms via `ARM_RADII`) and faded jeans with a belt; her in a black strappy crop top with a bare midriff over her high-waist jeans; tapered neck (user: "should not be straight bar"). Both: real hands (`build_hand`, fingers + knuckles), smooth one-piece arms (`arm_path`), collarbones and neck muscles. **His body skin is cel-shaded** (`cel_skin`) with ink muscle lines (`arm_anatomy(ink=True)`), after the user sent an anime strongman ref — user chose "sharp lines, his build" (not bulking up). **CROSSWALK** builds inside the UI (`ss.build(40, reset=False)`, ~100 s) with the new outfits; golden-hour street look (low warm sun, violet shade, gradient sky, GTAO/bloom). Stills in `renders/crosswalk_stills/` (not committed); full video not rendered. |
| Expressions | `FaceRig` + `EXPRESSIONS` exist for both (COOL, HAPPY, NOTICE, SHOCK, STRUCK, DAZED, SMUG, SIDEEYE / CALM, STARTLED, AMUSED) but were tuned on older faces — re-check on the new faces. |
| CROSSWALK video | Fully coded (`street_scene.py`, 312 frames, 7 shots, physics, acting keys, audio). Not rendered at final quality — waiting on faces. |
| User's Blender | **3.3.1** → our 5.0 `.blend` files fail ("not a blend file"). Use `blender/RUN_IN_BLENDER.py` to build inside their version. It now runs on 3.3 (modifier move, MixRGB, Filmic fallback, `Specular` input name, softer rim without AgX). |

## Do this first (local agent)

1. Open the user's Blender, **Scripting tab → Open → `toon_city/blender/RUN_IN_BLENDER.py` → Run Script**.
   It builds both characters in their Blender version (no factory reset, the UI stays).
   Note what breaks on their version (the code was only tested on 5.0.1) and fix it.
2. **Save As** `characters.blend` so the user has a file their Blender opens.
3. Put her next to **references/09_HER_thanks_girl_FACE_REF.jpg** and fix the face
   with the user watching — this is where the cloud session kept missing.
   Sculpt with **X-mirror on**, then port the shape back into code
   (`HER_LAYOUT`, `sculpt_head(... shield ...)`), or keep the sculpt as a
   shape key/applied mesh and load it in the build. Ask the user what they prefer.
4. Then expressions (`FaceRig`, `EXPRESSIONS` in `fixie_rider.py`), then the video.

## User preferences and rules (learned the hard way)

- Wants it **in Blender**; rejected switching tools ("Nope").
- Reacts to **renders**, not descriptions: always show a side-by-side with the reference.
- Very sensitive to: looking **old** (wants young/energetic), looking **scary**
  (staring eyes, white all round the iris), **asymmetry** across the vertical
  axis (they caught it on a turntable), features too **small/clustered**.
- When they paste a "sculpt guide" (Grab/Scrape/Pinch...), implement the
  intent as concrete geometry changes and show the result.
- Git: commit + push to `claude/toon-city-animation-pipeline-uzxbgn`; commit
  messages end with the Co-Authored-By/Claude-Session lines used in the log;
  **don't commit** `output_renders/`, `master.wav`, renders or `.blend` exports
  (`output_blend/` is git-ignored). No PR unless asked.

## Open issues (her face) — next fixes

- Chin still slightly broad/round vs the reference's small soft point; jaw outline is set in
  `sculpt_head` under `shield` (`x *= wt * (1 - 0.75 t^2.2) / sw`).
- Upper liner floats a little above the eyeball mid-lid; inner eye corners are
  round (reference: pinched point dipping toward the nose).
- Iris edge shows a faint white speckle (eyeball poking through).
- Sweater shoulders read puffy; blue washes pale in warm light.
- Hair top reads as a dark cap; reference is flatter with a visible parting line.
- Ears mostly hidden behind the face-framing strands (reference: big, visible, at eye level).
- She has no 3D look-dev on the street set yet.

## Known code facts that bite

- `fr.build(pct, reset=True)` factory-resets — **inside the UI use `reset=False`** (RUN_IN_BLENDER does).
- `pose_stand(rig)` resets `rig.location` — place the rig **after** posing.
- Face parts are rigid objects bound to the `Head` bone; `FaceRig` animates them by
  object transforms (no shape keys). Mouth swaps are scale ≈0 ↔ 1.
- `bind()` keeps world placement: read world positions/scales from `matrix_world`
  after binding, not `location`/`scale`.
- Features are placed by ray-casting the sculpted head (`head_surface`, `_HEAD_BVH`);
  rebuild the BVH when the head changes.
- Hair `conform()` keeps ribbons outside the real sculpted head — keep it when reshaping heads.
- EEVEE only in the cloud (no Cycles); software EGL warnings were harmless.
