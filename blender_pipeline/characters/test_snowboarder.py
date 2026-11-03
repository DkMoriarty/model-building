"""Checks for CH_Snowboarder (run with Blender's Python or the bpy module).

    blender -b -P blender_pipeline/characters/test_snowboarder.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402

import snowboarder as sb  # noqa: E402
import toonkit as tk  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


bpy.ops.wm.read_factory_settings(use_empty=True)
s = bpy.context.scene
rig, art, board = sb.build()
names = [l.name for l in art.data.layers]
check("every layer exists, in draw order", names == [n for n, _ in sb.LAYERS], f"{len(names)} layers")
check("every layer is bound to its bone", all(b in art.vertex_groups for _, b in sb.LAYERS))
check("eyes draw over the goggle lens", names.index("Eyes") > names.index("Goggles"))
shd = [l for l in art.data.layers if l.name.endswith("_Shd")]
check("cel shadows: Multiply layers at 45%", len(shd) == len(sb.SHADED) and
      all(l.blend_mode == "MULTIPLY" and abs(l.opacity - 0.45) < 1e-3 for l in shd), f"{len(shd)} layers")
radii = [p.radius for st in art.data.layers["Hair_Over"].frames[0].drawing.strokes for p in st.points]
check("brush lines: hair locks pinch at the tips and swell at the base", max(radii) / min(radii) > 4,
      f"thickest/thinnest = {max(radii) / min(radii):.1f}")

check("collar draws over the chin", names.index("Collar") > names.index("Face"))
check("mouth library: 9 visemes + GRIT + SMIRK", len(art.data.layers["Mouth"].frames) == 11)
check("eye library: 4 expressions", len(art.data.layers["Eyes"].frames) == len(sb.EXPRESSIONS))
for side in "LR":
    rest = rig.matrix_world @ rig.data.bones[f"Leg_Lower_{side}"].tail_local
    drift = (rig.matrix_world @ rig.pose.bones[f"Leg_Lower_{side}"].tail - rest).length
    check(f"IK {side}: rest pose kept", drift < 1e-3, f"{drift:.5f}")

keys = sb.walk(rig)
s.frame_set(keys[2])  # right foot at its highest
knee_r = (rig.matrix_world @ rig.pose.bones["Leg_Lower_R"].head).x
hip_r = (rig.matrix_world @ rig.pose.bones["Leg_Upper_R"].head).x
foot_r = (rig.matrix_world @ rig.pose.bones["IK_Target_R"].head).z
foot_l = (rig.matrix_world @ rig.pose.bones["IK_Target_L"].head).z
check("walk: right foot lifts, left stays planted", foot_r > 0.1 and abs(foot_l - sb.P(0, 1835)[1]) < 0.01,
      f"R {foot_r:.3f}, L {foot_l:.3f}")
check("walk: lifted knee bends outward (front view)", knee_r < hip_r - 0.05, f"knee {knee_r:.3f} < hip {hip_r:.3f}")
s.frame_set(keys[0])
t0 = (rig.matrix_world @ rig.pose.bones["Torso"].head).z
s.frame_set(keys[2])
t1 = (rig.matrix_world @ rig.pose.bones["Torso"].head).z
check("walk: body dips on contact, rises on the pass", t1 > t0 + 0.01, f"{t0:.3f} < {t1:.3f}")
frames = sb.talk(art, [(0.0, "REST"), (0.5, "MBP")])
s.frame_set(frames[1])
check("talk: MBP on its frame", art.modifiers["Mouth Swap"].offset == tk.VISEMES.index("MBP") + 1)

# Rubber-hose knee: with the right knee bent, points near it land between
# where a pure thigh and a pure shin would carry them (no hinge).
s.frame_set(keys[2])
dg = bpy.context.evaluated_depsgraph_get()
rest = [p.position.copy() for st in art.data.layers["Leg_R"].frames[0].drawing.strokes for p in st.points]
ev = art.evaluated_get(dg)
bent = [p.position.copy() for st in ev.data.layers["Leg_R"].frames[0].drawing.strokes for p in st.points]
M = {b: rig.pose.bones[b].matrix @ rig.data.bones[b].matrix_local.inverted() for b in ("Leg_Upper_R", "Leg_Lower_R")}
blended = sum(1 for p0, pe in zip(rest, bent)
              if min((M["Leg_Upper_R"] @ p0 - pe).length, (M["Leg_Lower_R"] @ p0 - pe).length) > 0.004)
check("rubber-hose knee: points near the knee blend thigh and shin (no hinge)", blended >= 4, f"{blended} blended points")


def jacket_width(frame):
    s.frame_set(frame)
    ev = art.evaluated_get(bpy.context.evaluated_depsgraph_get())
    xs = [p.position.x for st in ev.data.layers["Jacket"].frames[0].drawing.strokes for p in st.points]
    return max(xs) - min(xs)
w_contact, w_pass = jacket_width(keys[0]), jacket_width(keys[2])
check("puffer lattice: the jacket squashes wide on contact, slims on the pass", w_contact > w_pass * 1.03,
      f"{w_contact:.3f} vs {w_pass:.3f}")
sb.express(art, 30, eyes="SQUINT", mouth="GRIT")
s.frame_set(30)
check("express: squint + gritted grin on its frame",
      art.modifiers["Eye Swap"].offset == 4 and art.modifiers["Mouth Swap"].offset == 10)
bpy.ops.wm.read_factory_settings(use_empty=True)
rig2, art2, _ = sb.build(look="sheet2")
check("sheet2 look builds with its own materials",
      any(m.name.startswith("SB_sheet2_Metal") for m in bpy.data.materials) and len(art2.data.layers) == len(sb.LAYERS))

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
