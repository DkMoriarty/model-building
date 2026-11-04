# Blender: toon-anime characters

`kai_toon.py` builds **Kai**, an original cel-shaded character with bold black outlines and a flat cartoon city behind him. The whole scene is built from code, so you change the look by editing numbers and colours, not by sculpting.

## Run it

Blender 3.6 or 4.x:

- **In Blender:** go to the Scripting tab, open `kai_toon.py` and click Run Script, then press F12 to render.
- **From a terminal:**
  ```
  blender -b -P blender/kai_toon.py -- --save kai.blend --render kai.png
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
- `STYLE["outline_width"]`: about 0.01 is thin and about 0.02 is chunky, like 90s TV cartoons.
- `STYLE["shadow_amount"]` / `band_split`: how dark the shadow band is and where it starts.
- `STYLE["highlight"]`: turns the third, brighter band on or off.
- `STYLE["backdrop"]`: turns the city on or off.

To add a character, copy `build_head()` / `build_body()` and reuse the helpers: `sphere`, `cone`, `tube`, `limb`, `torus`, `box`, `on_head`. Each helper gives its shape an outline automatically.

## Not included yet

The character isn't rigged, so the pose is fixed in code. To animate him, add an armature (Rigify works) and parent the parts to it with automatic weights.
