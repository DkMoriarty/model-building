# Anime face - feature definitions (baseline to refine from)

Default face of the anime character (`blender_pipeline/characters3d/anime_char.py`,
`FACE_STYLES["anime"]` + `ANIME_LAYOUT`). Units: head units (x: half face width,
z: from head centre, + up). Every feature is a drawn shape laid on the face surface.
Tell the agent "feature N: change X" and it edits the matching value.

| # | Feature | Definition now | Where (anime_char.py) |
|---|---|---|---|
| 1 | Head | narrow, long: size (0.096, 0.11, 0.145) m; shallow eye sockets | `size`, `socket` |
| 2 | Face outline | full cheekbone -> soft jaw angle at mouth level -> straight line -> narrow pointed chin, chin forward of the neck, inked 1.6 mm | `face_w`, `chin_drop`, `chin_fwd`, `add_outline(head, 0.0016)` |
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
| 14 | Ears | small, at z = -0.12, mostly behind the side hair | `ear_uz`, `ear_h` |

Expressions (FaceRig): COOL, HAPPY, SMUG, NOTICE, SHOCK, STRUCK, DAZED, SIDEEYE.
`--face illustrated` keeps the reference-study variant (not the default).
