# Scenes

## SNOW RUN — delivered

`blender_pipeline/scenes/snow_run.py` + `snow_run_audio.py`. CH_Snowboarder
(Grease Pencil cut-out) rides a mountain in five shots, 14 s at 24 fps: LEDGE,
CARVE, RAIL, SUNSET backflip, LAND. One `ride_state(f)` drives pose, spray,
shadow and camera; the board is a bone; original swing-jazz soundtrack +
effects, mixed for phone speakers. See `blender_pipeline/scenes/README.md`.

## CROSSWALK — coded, not final-rendered

`blender/street_scene.py` (copy of `blender_pipeline/characters3d/street_scene.py`)
+ `street_scene_audio.py`. 312 frames (13 s), seven shots: establishing wide,
tracking, POV reveal, close-up push-in, side wide for the action, slow two-shot
push-in, dazed close-up.

- **Story:** he cruises at 4.2 m/s; she steps out from behind a parked car;
  he locks up (7 m/s² skid), 34° stoppie, `STOP_AT = 1.3` m from her, lunge,
  her body turns; he is struck.
- **Acting:** `ACTING_HIS` / `ACTING_HERS` keyframe the `FaceRig` expressions
  (`act_faces`) — COOL → NOTICE → SHOCK → STRUCK → DAZED / CALM → STARTLED → AMUSED.
- **Set:** road, lane/centre lines, zebra, kerbs, sidewalks, pastel facades,
  shopfronts, awnings, lamps, trees, crossing signal, parked hatchback, hydrant,
  bench; low warm sun.
- **Sound:** city air (rumble, breeze, birds), a lo-fi groove that cuts dead on
  the skid, chain whir, tyre screech, her gasp, heartbeat, chime glissando,
  heart sparkles. `python3 street_scene_audio.py --out renders/crosswalk` muxes the MP4.

Run: `blender -b -P blender_pipeline/characters3d/street_scene.py -- --out renders/crosswalk`
(see the script's argparse for frame ranges/preview options).

**Blocked on:** final faces (user's order: faces → expressions/keyframes → video).
After faces change, re-check the acting keys (eye openness/gaze ranges were tuned
on the old faces) and her new outfit/hair in every shot.

## SHARP ANIME CHARACTER — first pass

`blender/anime_char.py` (canonical: `blender_pipeline/characters3d/anime_char.py`).
An original anime boy on the shared rig and the new body (white baniyan, jeans):
shield head to a V chin, big almond eyes with tall irises and a heavy lash line,
sharp brows, spiky ribbon hair (`ribbon_hair(style="anime")`: pointed bangs stopping
at the brows, crown spikes that flick out, side locks, back spikes, an ahoge),
slimmer neck, body cel skin recoloured to the anime face tone.
`anime_look()` turns any scene into the anime render: two-tone cel materials
(Shader to RGB -> constant ramp, cool shadow tone; faces lit only by cast shadows),
inverted-hull ink outlines (thin on the face, none on the drawn eye/mouth parts), one
hard sun, a dim cool ambient with a flat sky for the camera, Standard view transform.
Blender 3.3 safe (MixRGB fallback).

    blender -b -P blender_pipeline/characters3d/anime_char.py -- --out renders/anime --outfit vest|bare|jacket

Body (anime only, the base body is untouched): wider frame (shoulder/arm joints out
4 cm), one continuous shoulder girdle with teardrop deltoids, V-shaped chest with pecs
(`_pecs`), sculpted six-pack, obliques and Adonis V, shoulder blades and spine groove
(`_abs_back`), ink strokes laid on the surface (`_ink_on`); relaxed A-pose (`pose_a`,
moves the IK hand targets). Outfits: `bare`, `vest` (knit shows the forms softly),
`jacket` (open dark jacket, red lapels/lining, stand collar, skinned sleeves, cuffs,
shoulder yoke).

### Face styles (`--face illustrated | anime`)

`illustrated` (default) is studied from the user's feature-illustration references
(umbrella/rose shorts, reels): long angular face, a long triangular wedge nose that
reads in profile (`wedge_nose`), narrow heavy-lidded eyes with small dark irises and
one catch-light, thick angular brows close to the eyes, warm tan skin, brown hair,
blush strokes, pointed chin forward of the neck. `anime` keeps the big blue anime eyes.
Both draw the features on the face surface (`build_anime_face`), driven by `FACE_STYLES`.
