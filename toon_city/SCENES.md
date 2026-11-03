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
