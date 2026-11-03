# 3D characters

## CH_FixieRider (`fixie_rider.py`)

An original stylised 3D character in the soft "3D-render character design"
look: very long thin legs, oversized boxy streetwear (sage work shirt with
buttons, baggy charcoal shorts, tall white socks, chunky cream sneakers with
gum soles), a rust cap over short twists, a crossbody bag, big friendly eyes
and a grin; on a fixed-gear bike in a soft grey studio.

![turnaround and ride](previews/fixie_sheet.png)

How it is built (all code, Blender 4.3+/5.0):
- **Shapes:** every part is a lofted tube (`tube`, elliptical rings for boxy
  clothes) or a scaled sphere (`blob`), smoothed with Subdivision Surface.
- **Rig:** a skeleton with IK legs and arms (pole angles solved so the rest
  pose doesn't move). Clothes, head and shoes ride their bones; the bare legs
  and arms are single meshes skinned along the chain (`skin_chain`), blending
  across the knee and elbow so they bend smoothly.
- **Bike:** tubes, tori and discs; the crank turns and, as on a fixie, the
  wheels turn with it. Her feet (IK) ride the pedals and the hands hold the
  grips, so `pose_ride(rig, bike, crank_deg)` is a real pedal stroke.
- **Studio:** a curved cyclorama with key, fill and rim area lights.

```bash
blender -b -P blender_pipeline/characters3d/fixie_rider.py -- --out renders/fixie --views sheet,ride,loop --frames 24
```
