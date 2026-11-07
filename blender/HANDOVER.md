# Blender work: handover for a local agent

Everything here is plain Python run inside Blender. No add-ons are needed. Each script deletes the objects in the current scene and rebuilds its own from scratch, so start from a new or empty file.

## Files

| Path | What it is |
|---|---|
| `space_dock.py` | **Main scene.** 30 s sci-fi sequence: boarding at an orbital station, shuttle lift-off, flight, docking with a 1 km mothership. Sky, planet, five cameras. |
| `ren_toon.py` | Adult toon-anime character (Ren), cel-shaded with outlines. |
| `kai_toon.py` | Chibi toon character (Kai). |
| `README.md` | What each scene contains and how to tune it. |
| `tools/mock_blender.py` | Stand-ins for `bpy`, `bmesh` and `mathutils`, so the scripts can run without Blender (for testing logic). |
| `tools/space_preview.py` | Runs `space_dock.py` on the stand-ins and rasterizes rough test shots per camera. |
| `tools/character_export.py`, `tools/character_raster.py` | The same for the characters: exports meshes to JSON, then renders a rough image. |
| `previews/` | Rough test renders and browser 3D previews of the characters. |

## Status

- **Not yet run in real Blender.** All scripts were checked with the stand-ins (they build: Space Dock 185 objects, Ren 164), and the test renders look right. The first job is to run them in Blender and fix any API errors.
- Targets Blender 3.6 to 4.x with EEVEE. Version differences are wrapped in try/except: EEVEE vs EEVEE Next, Principled socket names, bloom, and compositor access.
- Blender 5.x may need fixes. `scene.node_tree` (the compositor) and some material blend settings changed there.

## Load it

In the Blender UI: Scripting tab → Open `space_dock.py` → Run Script → Space to play.

From a terminal:
```
blender --python blender/space_dock.py                       # opens the UI with the scene built
blender -b -P blender/space_dock.py -- --save space_dock.blend
blender -b -P blender/space_dock.py -- --render-frame 560 --out shot.png
blender -b -P blender/space_dock.py -- --render-anim --out //render/frame_
```

## First checks after running in Blender

1. Check the Info / system console for tracebacks. Fix those first.
2. Scrub the timeline and check each camera switch (frames 1, 200, 350, 505, 600):
   - Passengers walk out of the gate tunnel and up the ramp (1–240), then vanish inside.
   - The ramp closes (about 241–271), the engines ignite (252–270), lift-off at 274, and the gear retracts (285–310).
   - The shuttle clears under the habitat ring (ring at z = 60) and flies to the mothership.
   - It docks nose-first into the collar at frame 700, the clamps close (690–708), and the lights turn red to green.
3. Render a still from each camera and check exposure. Things to tune:
   - `Pad_flood*` light energy (25,000 W) and sun strength (4.5).
   - The emission strengths in the `emit_mat(...)` calls.
   - Bloom: the Glare node in the compositor.
4. Engine plumes and the planet atmosphere use transparent emission. If they render as solid shapes, set the material's blend mode to Blended or Alpha Hashed. On EEVEE Next, set Render Method to Blended.

## How it's organized (`space_dock.py`)

- **Tuning constants** at the top: `COLORS`, `SHUTTLE_REST`, `MOTHERSHIP`, `RING_Z`, `STAR_POS`, `PLANET_POS`.
- **Animation tables**: `SHUTTLE_KEYS` (frame, location, rotation), `PLUME_KEYS`, `GEAR_UP` and `CAMERAS`. Change the timing there; `animate()` reads them.
- **Builders**: `build_world`, `build_environment`, `build_station`, `build_shuttle`, `build_mothership`, `build_passengers`.
- **Geometry**: everything is made with bmesh helpers (`loft`, `box`, `sphere`, `cone`, `tube`, `torus`, `prism`). Greebles are merged into one mesh per object, which keeps the object count low.
- **Determinism**: random layouts use `SEED`, so a re-run gives the same scene.
- **Collections**: Station, Shuttle, Mothership, Passengers, Environment, Cameras.

## Test without Blender

```
python blender/tools/space_preview.py blender/space_dock.py <out_dir> "Cam_boarding:120,Cam_chase:430,Cam_docking:712"
```
This needs numpy and Pillow. It writes one PNG per `camera:frame` pair. These are flat-shaded checks of layout and timing, not final renders.

## Ideas not done yet

- Character rigs (Rigify) for Ren and Kai, and putting Ren in the boarding scene.
- A hangar interior for the mothership, instead of the glowing panel.
- Real exhaust volumes (volume shader) instead of the glow cones.
- Camera shake on lift-off, and depth of field on the boarding shot.
