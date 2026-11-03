# CHARACTERS — specs, measurements, feedback history

Both are built entirely in code (`blender/fixie_rider.py`, `blender/street_scene.py`).
Units: metres; the head is a dense UV sphere sculpted by vertex displacement.

## How a face is built (shared)

`build_face(add, hc, size, skin, iris, brow, lip, prefix, ..., style="toon", layout=...)`
→ `build_toon_face`:

1. `sculpt_head` — displaces a 128×80 sphere: eye sockets (follow the mapped
   eyes), brow ridge, cheekbones, `soft_features` (nose bridge/tip, nostrils,
   lips, chin) and optional global shapes from the layout:
   `jaw_ref` (his straight long jaw to a broad chin), `oval`, `shield` (hers:
   wide flat upper face, outline-controlled U jaw → small chin), `diamond` (planar nose).
   Skin colour/blush/lips are painted into a `Paint` colour attribute.
2. Features placed by ray-casting the sculpted mesh (`head_surface`):
   `almond_eye` (eyeball, iris, pupil, glints, upper `LidLiner`, `LowLiner`),
   brows (`straight`, `bushy`, `wedge`, `sharp`, `thin`, `arch`, `angry`, `lift`),
   ears (`ear_shell`), mouth set (`Smile`, `Dimple`, `PoutUp/Low`, `MouthGrin…`, `MouthO`, `MouthGasp`, `MouthFlat`), extras (blush, sparkles, sweat).
3. Hair: `ribbon_hair(style=…)` — Bezier ribbons with a flattened "football"
   bevel profile, radius taper, tilt; a dark `Hair_Helmet` cap underneath;
   `matte_hair_material` (roughness .95, spec 0, tiny SSS, noise-600 bump).
   Styles: `messy` (him: crown whorl, fringe, temples, sides, back, breakouts),
   `sleek`, `ponytail` (her: centre part, mirrored combs to a nape tie, tail,
   face-framing strands, flyaways). `conform()` keeps every ribbon outside the real head.

### Layout keys (unit = head size; x: half-width, z: centre→top)

`eye_ux, eye_uz, nose_z, mouth_z, chin_z, ear_uz, ear_h, mouth_w, almond_h,
liner, iris, iris_x, eye_k=(top_flat, bottom_round, outer_tilt), eye_sink,
soft (catch-lights/pupils), brow_drop, hairline, chin_w, pout, slit,
jaw_ref | oval | shield, diamond`.

## HIM — CH_FixieRider (reference 08, tennis boy)

Rig `FR_Rig`; `HEAD_Z = 1.69`; head `hc=(0,-0.01,1.69)`, size `(0.108, 0.118, 0.15)`.

```python
HIS_LAYOUT = dict(eye_ux=0.37, eye_uz=-0.09, nose_z=-0.36, mouth_z=-0.6, chin_z=-1.06,
                  ear_uz=-0.24, ear_h=0.72, jaw_ref=1.0, slit=1.0, mouth_w=0.2)
build_face(... nose=1.45, chin=1.2, cheek=1.0, jaw=0.45, eye_r=0.024, smirk=0.4, lips=0.45,
           brows="bushy", wing=0.35, eye_shape="almond", grin="crescent", layout=HIS_LAYOUT)
```

- Skin `#a9643c` (warm tan), hair `#050406` matte, ribbon hair (`HAIR="ribbons"`).
- Outfit: sage work shirt, charcoal shorts, tall socks, cream sneakers, crossbody bag; fixie bike.
- Feedback history: stick-figure style rejected → 3D; "Pathetic"/"Not matching" on early
  faces → planar sculpt + matte vinyl; "looks old" → young; tennis ref measured
  ("measure it proportion nd all"); "Get proper hairs done" → strands → Bezier ribbons;
  wedge jaw rejected ("No its not good get me perfect oval… elongated jaws") →
  oval → then "Match the refe jaw line" → straight jawline to a broad forward chin;
  skin/hair/lids tuned → user: **"Doable"**.
- Render: `renders/HIM_vs_ref_latest.jpg`.

## HER (street_scene.build_girl) — reference 09, "Thanks" girl

Rig `GR_Rig` (scaled 0.95); head `hc=(0,-0.005,1.70)`, size `(0.118, 0.118, 0.15)`.

```python
HER_LAYOUT = dict(eye_ux=0.47, eye_uz=-0.08, nose_z=-0.47, mouth_z=-0.66, chin_z=-1.0,
                  ear_uz=0.0, ear_h=0.6, mouth_w=0.24, almond_h=0.66, liner=1.2, iris=0.78,
                  soft=1.0, brow_drop=-0.04, hairline=0.74, eye_k=(0.8, 1.05, 0.55),
                  eye_sink=0.4, iris_x=0.12, shield=1.0, slit=1.0, pout=0.55)
fr.build_face(... prefix="G_", nose=1.0, chin=0.5, cheek=1.0, jaw=0.75, eye_r=0.04, lashes=True,
              smirk=0.0, lips=0.4, brows="thin", wing=0.35, eye_shape="almond", layout=fr.HER_LAYOUT)
```

- Skin `#c4825c`, iris `#2c180e`, hair `#07060a`; silver hoops, silver chain,
  blue cable-knit crewneck `#4b66ab` over a white collar (wide, open), long thin neck
  (r 0.025→0.022), jeans, platform sneakers.

### Measurements taken from reference 09 (image 1199×716)

Face-crop grid: `renders/HER_ref_measure_grid.png` (crop (620,60)-(1000,460) at 2×).

| landmark | image px (orig) | unit |
|---|---|---|
| hairline centre | (808, 135–140) | +0.74 |
| eye corners (near eye) | outer (697,270) → inner (770,297) | tilt ≈ 20° outer-up |
| eye corners (far eye, foreshortened) | inner (845,292) → outer (893,256) | 37° (head turn) |
| iris centres | (740,280), (862,272) | Ø ≈ 34 px ≈ 0.47 eye width |
| eye height / width | 40 / 73 px | 0.53 |
| gap between inner corners | ≈ 75 px | ≈ 1 eye width |
| nose tip | (810, 332) | −0.42 |
| mouth centre | (810, 367) | −0.62, width ≈ 0.44 |
| chin tip | (808, 415) | −0.90 |
| cheek edges at eye level | 697 … 918 | half-width ≈ 112 px |
| ears | level with the eyes | big, protruding |
| earrings | hang ≈ 0.42 below centre | silver hoops |

Eye construction that matches: flatter upper lid line **cutting the top of a
round iris**, rounder lower edge, outer corner up, one small catch-light,
light upper liner with a small flick (`renders/HER_eye_axes_measured.jpg`).

### Her feedback history (most recent last)

1. First girl (bob, mustard cardigan) → refs 04/05 → Ink girl with heavy cat-eye, gold squares.
2. User sent ref **09**: "Match her" → centre-part ponytail, blue knit, silver hoops.
3. "She is looking more scary" → softer eyes (lower lids, catch-lights, warm iris, brows lowered).
4. "She is looking aged not young" → shorter rounder face, features lower, fuller cheeks.
5. "Map her face nd do" → measured landmark layout (table above).
6. "Eye position nd shape" / "Check orientation start nd end point the angle" → eye axes measured & matched.
7. "Cut her face nd impose on our body then filled" → `project_face_image()` experiment
   (front-projects the reference onto the head; `renders/HER_projected_face_experiment.jpg`).
   User: **"No its not right find a way to make exactly like her"** + checklist:
   shield head (wide flat upper face → tiny chin), features ~30 % bigger, eyes slanting
   to the temples, long narrow nose, wide flat mouth, long micro-thin neck, wide
   collar, sharp cast shadows → implemented (`shield`, bigger eyes, thin neck, harder key).
8. "The revolve is not uniform its varying across vertical axis" → turntable found
   head poking through hair + unmirrored hair + one-sided smirk → fixed
   (`renders/HER_turntable_latest.jpg`, `renders/HER_symmetry_check.jpg`).

**Not yet approved.** The reference face is a 2D-ish painterly render; matching it
in 3D probably needs hands-on sculpting in the user's Blender (X-mirror), with the
user steering, then baking the result back into code.

## Expressions (`EXPRESSIONS` in fixie_rider.py)

His: COOL, HAPPY, NOTICE, SHOCK, STRUCK, DAZED, SMUG, SIDEEYE. Hers: CALM,
STARTLED, AMUSED. Each sets lid openness, lower lid, brow height/angle per side,
mouth shape, gaze, pupil size, sparkle/blush/sweat. `FaceRig(rig, prefix).pose(name)`
or `.key(frame, name)`. `expression_sheet.py` renders all of them.
