# Anime face - feature definitions (baseline to refine from)

**Status: all 14 features approved (2 corrected).**

Default face of the anime character (`blender_pipeline/characters3d/anime_char.py`,
`FACE_STYLES["anime"]` + `ANIME_LAYOUT`). Units: head units (x: half face width,
z: from head centre, + up). Every feature is a drawn shape laid on the face surface.
Tell the agent "feature N: change X" and it edits the matching value.

| # | Feature | Definition now | Where (anime_char.py) |
|---|---|---|---|
| 1 | Head | narrow, long: size (0.096, 0.11, 0.145) m; shallow eye sockets | `size`, `socket` |
| 2 | Face outline | FINAL: full cheekbone, gentle curve into straight jaw lines meeting in a sharp V chin (linear profile, no notches), chin forward of the neck, inked 1.6 mm | `face_w`, `face_lin`, `chin_drop`, `chin_fwd`, `add_outline(head, 0.0016)` |
| 3 | Eye placement | centres at x = +/-0.43, z = -0.20 | `eye_ux`, `eye_uz` |
| 4 | Eye shape | half-width 0.22; upper lid rises steeply from the inner corner, runs flat, drops to a sharp outer corner; shallow lower lid; height x1.4 | `EYE_TOP`, `EYE_BOT`, `EYE_HW`, `EYE_VZ` |
| 5 | Iris | tall blue (#2f74d0) ellipse 0.44 x 0.128, cut by the upper lid; lighter lens low (#5aa3ef) | `iris`, `iris_lo` |
| 6 | Pupil + highlights | dark pupil 0.18 x 0.066; big catch-light upper-outer, small one lower-inner | `pupil`, `glint`, `glint2` |
| 7 | Lash line | heavy upper line, thin at the inner corner, thickest over the outer half, flick past the corner; fine lower line on the outer half; lid crease | `LidLiner`, `LowLiner`, `Crease` |
| 8 | Brows | sharp, angled toward the nose, heavy inner end to a fine point, drawn over the bangs | `brow`, `brow_w` |
| 9 | Nose | small ink stroke on the shadow side + tip tick + faint shadow; no bump | `NoseLine`, `NoseTip`, `NoseShadow` |
| 10 | Mouth | drawn set: smirk line with corner tick (COOL), flat (NOTICE), grin with teeth + tongue (HAPPY/SMUG), O (STRUCK), gasp (SHOCK) | `Smile`, `MouthGrin*`, `MouthO`, `MouthGasp`, `MouthFlat` |
| 11 | Blush | three short pink strokes per cheek + soft painted cheek colour | `BlushLine`, `blush_toon` |
| 12 | Shading | flat face (cel terminator 0.015), one painted shadow band under the bangs, hair casts no shadow on the face | `cel_material`, `BangShadow` |
| 13 | Colours | skin #f6d3bd, hair #20223a, iris #2f74d0, ink #141522 | `ANIME_COL` |
| 15 | Side profile | brow ridge, eyes set back, small pointed nose, dip under it, lips, recess, chin forward to a point; crisp jaw underside back to the ear | `profile`, `jaw_plane` |
| 14 | Ears | small, at z = -0.12, set out from the skull so they show in 3/4 and profile | `ear_uz`, `ear_h`, `ear_x`, `ear_flare` |

Expressions (FaceRig): COOL, HAPPY, SMUG, NOTICE, SHOCK, STRUCK, DAZED, SIDEEYE.
`--face illustrated` keeps the reference-study variant (not the default).


## Techniques learned from a studied hand-modelled anime model (applied)

| Technique | Applied as |
|---|---|
| Hair as few big smooth chunks over a cap (clean silhouette) | `ribbon_hair(style="shell")`: 6 bangs, 9 crown, 2+2 sides, 6 back, ahoge |
| Anime hair shine | `anime_hair_material`: a light band with a wavy lower edge across the crown |
| Soft painted shading under the ink | `soft_face_paint`: face colour warms/darkens toward the sides and under the jaw |
| Expressions as shape keys | `bake_expression_shapekeys`: one mesh "FaceFeatures", keys HAPPY/SMUG/NOTICE/SHOCK/STRUCK/DAZED/SIDEEYE (basis COOL) |
| Finger-level rig | `add_finger_bones`: 3 bones per finger + thumb, fingers skinned to them; `curl_fingers(rig, deg)` |

The studied model itself (a fan model of a copyrighted character) is not used or copied.
