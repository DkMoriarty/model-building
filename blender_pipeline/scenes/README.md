# Scenes

## SNOW RUN (`snow_run.py`)

CH_Snowboarder rides a mountain in five shots, 14 s at 24 fps. Original
staging and music, in the spirit of a short stylised snowboarding clip:

| shot | frames | what happens |
|---|---|---|
| 1 LEDGE | 1-48 | pops off a snowy rock ledge into a pink dusk sky, knees tucked, grabbing the board |
| 2 CARVE | 49-132 | carves down a steep slope past pines, snow spray off the tail, a long evening shadow |
| 3 RAIL | 133-204 | low and close: boardslides a wooden rail, the board chatters, sparks fly |
| 4 SUNSET | 205-264 | a full backflip against a radial sunset glow, warmly backlit |
| 5 LAND | 265-336 | drops onto the run-out, squash and a burst of snow, rides off with a smirk |

How it works:
- **One set of numbers drives everything.** `ride_state(f)` gives her position,
  tilt and pose for every frame (ballistic arcs under one gravity, constant
  slope angles), and the spray, the shadow on the snow and the camera all read
  the same numbers, so they agree.
- **The board is a bone.** Her feet (IK targets) ride on the rig's `Board` bone:
  lifting it tucks her knees, tilting it angles the board in a grab.
- **Particles** are drawn per frame (snow chunks fall slower than sparks).
- **Acting:** expressions per shot (happy in the air, glare while carving,
  side-smirk on the rail and the ride-off, squint and gritted grin on the
  landing); the puffer lattices inflate in the air and squash on the landing.
- **Sound** (`snow_run_audio.py`): an original swing-jazz loop (walking bass,
  ride and brushes, electric-piano comping, a vibraphone motif) plus snow
  swish, takeoff puff, landing thump, rail scrape and wind on the picture's
  frames; 73% of the energy is in the 300 Hz - 4 kHz phone band.

```bash
blender -b -P blender_pipeline/scenes/snow_run.py -- --out renders/snow_run --stills 12,90,170,236,300   # check shots
blender -b -P blender_pipeline/scenes/snow_run.py -- --out renders/snow_run                              # all frames
python3 blender_pipeline/scenes/snow_run_audio.py --out renders/snow_run                                 # music + sfx + MP4
```
Frames can be split across processes with `--frames A-B`.
