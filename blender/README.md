# Blender: toon-anime characters

Two original cel-shaded characters, each built entirely from code, with bold black outlines and a flat cartoon city behind them. You change the look by editing numbers and colours, not by sculpting.

| Script | Character |
|---|---|
| `ren_toon.py` | **Ren**: adult anime proportions (about 7.5 heads), narrow jaw, sharp almond eyes, swept-back spiky hair, long belted coat with a shirt and tie. |
| `kai_toon.py` | **Kai**: chibi proportions, big round eyes, hoodie. |

## Run it

Blender 3.6 or 4.x:

- **In Blender:** go to the Scripting tab, open `ren_toon.py` (or `kai_toon.py`) and click Run Script, then press F12 to render.
- **From a terminal:**
  ```
  blender -b -P blender/ren_toon.py -- --save ren.blend --render ren.png
  ```

Render with **EEVEE** (the script sets it). The hard light/shadow bands come from the *Shader to RGB* node, which only EEVEE supports.

## How the style works

| Piece | Technique |
|---|---|
| Cel shading | Diffuse BSDF → Shader to RGB → ColorRamp (Constant) → Emission. Gives 2–3 flat colour bands. |
| Outlines | Inverted hull: a Solidify modifier with flipped normals pushes a black, back-face-culled shell outward. |
| Flat colours | View transform set to *Standard*, so the palette hex codes render exactly. |
| Anime face | Eyes, mouth, blush and brows are flat-colour shapes laid on the head surface. |

## Making a new style

Everything is set at the top of the script:

- `PALETTE`: every colour (hair, outfit, eyes, outline, background).
- `PALETTE_SHADOW` (Ren): hand-picked shadow colours, e.g. a warm shadow for skin.
- `CAMERA` (Ren): lens, position and aim.
- `STYLE["outline_width"]`: line thickness in metres. For Ren (1.9 m tall) 0.005 is the default; for Kai it's 0.014.
- `STYLE["shadow_amount"]` / `band_split`: how dark the shadow band is and where it starts.
- `STYLE["highlight"]`: turns the third, brighter band on or off.
- `STYLE["backdrop"]`: turns the city on or off.

To add a character, copy `build_head()` / `build_body()` and reuse the helpers: `sphere` (with `keep` to trim and `deform` to reshape), `cone`, `tube`, `limb` (tapered), `torus`, `box`, `on_face` / `on_head`. Each helper gives its shape an outline automatically.

## Not included yet

The characters aren't rigged, so the pose is fixed in code. To animate him, add an armature (Rigify works) and parent the parts to it with automatic weights.

