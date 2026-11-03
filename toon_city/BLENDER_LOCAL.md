# Working in the user's own Blender

## The version problem

The cloud session ran **Blender 5.0.1** (bpy module). Blender 5.0 writes a new
`.blend` header (`BLENDER17-01v0500`). The user's Blender is older, so every
5.0 file fails with:

```
Loading '...\characters.blend' failed: Failed to read blend file ..., not a blend file
```

Don't send 5.0 `.blend` files. Build inside their Blender instead.

## Build both characters inside Blender (any 4.x/5.x — 4.x untested)

1. Blender → **Scripting** tab → **Open** → `toon_city/blender/RUN_IN_BLENDER.py`.
2. **Run Script** (Alt+P). It finds its own folder (or uses `FOLDER`, default
   `C:\Users\Dhiraj Office\Downloads\toon_chars`), imports `fixie_rider` and
   `street_scene`, clears the open file (`build(reset=False)`, no factory reset),
   builds him and her standing side by side, faces posed (COOL / CALM), golden-hour
   lights, a camera, and puts the bike in a hidden `Bike` collection.
3. **File → Save As** → `characters.blend` (now in their version).

Possible 4.x incompatibilities to watch: EEVEE engine id (`BLENDER_EEVEE` vs
`BLENDER_EEVEE_NEXT`, handled), Principled input names (`Specular IOR Level`,
`Subsurface Weight`, `Sheen Weight` — guarded with `in b.inputs`), `ShaderNodeMix`
(3.4+), `material.use_nodes` deprecation (guarded). Fix whatever their version raises.

Command line alternative: `blender -b -P toon_city/blender/save_blend.py -- characters.blend`.

## What is in the scene and how to edit it

| What | Where | How |
|---|---|---|
| Render | camera `Cam` | Numpad 0; Z → Rendered; F12 |
| Pose | `FR_Rig` (him), `GR_Rig` (her) | Ctrl+Tab → Pose Mode; bones `Head, Neck, Spine, Pelvis, UpperArm_L/R, Forearm_L/R, Hand_L/R, Thigh_L/R, Shin_L/R, Foot_L/R`; I to key |
| Brows | `Brow1`, `Brow-1` (hers `G_…`) | G Z height, R Y angle |
| Eyes | `Eye±1`, `LidLiner±1`, `LowLiner±1` | S Z on `Eye` = openness, move liner with it |
| Gaze | `Iris±1`, `Pupil±1`, `Glint±1` | select the three, G X / G Z |
| Mouth | `Smile`, `PoutUp/PoutLow`, `MouthGrin…`, `MouthO`, `MouthGasp`, `MouthFlat` | swap by scale (≈0 hidden) |
| Head shape | `Head`, `G_Head` | Sculpt Mode, **X-mirror on**; Grab/Smooth/Flatten/Draw Sharp |
| Hair | curves `Hair…` / `G_Hair…`, cap `Hair_Helmet` | Tab: G points, Alt+S thickness, Ctrl+T twist |
| Lights | `GH_Key` warm, `GH_Rim`/`GH_RimHair` edge, `GH_Fill` lavender | Power / Color |
| Background | `GH_SunGlow`, `GH_Fence…`, `GH_Bush…` | hide in Outliner |
| DOF | `Cam` → Depth of Field | F-Stop 4 (1.8 = very blurry) |
| Bike | collection `Bike` | tick in Outliner |

`1` = character's left side (+X), `-1` = right.

## Driving Blender live (optional)

A local agent can run Blender headless on the PC (`blender.exe -b -P script.py`)
and read/write the user's `.blend` files. For live control of the open Blender
window there is the community **Blender MCP** add-on (third-party, review before
installing) used from the Claude desktop app on the PC.

## Porting hand sculpting back into code

If the user sculpts a face by hand, either (a) read the edited `.blend`, measure the
new landmarks/outline and update `HER_LAYOUT` / `sculpt_head`, or (b) save the
sculpted head mesh (e.g. as a `.npy` of vertex positions matching the 128×80 sphere,
same vertex order) and have `sculpt_head` load it when present. (b) is exact; (a)
keeps it parametric. Ask the user.
