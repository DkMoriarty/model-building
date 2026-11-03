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
check("collar draws over the chin", names.index("Collar") > names.index("Face"))
check("mouth library has 9 visemes", len(art.data.layers["Mouth"].frames) == 9)
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

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
