"""Clay check: render the head in grey clay under a raking light, front,
3/4 and profile - the MatCap/cavity test. Every plane, cut and ridge must
read without colour.

    blender -b -P blender_pipeline/characters3d/clay_check.py -- --out renders/clay [--who his|hers]
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import fixie_rider as fr  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="renders/clay")
    ap.add_argument("--who", default="his")
    ap.add_argument("--size", type=int, default=520)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    scene, rig, bike = fr.build(100)
    head_x = 0.0
    if a.who == "hers":
        import street_scene as ss
        g, _ = ss.build_girl()
        g.location = (2.0, 0, 0)
        head_x = 2.0
    clay = bpy.data.materials.new("Clay")
    if getattr(clay, "node_tree", None) is None and hasattr(clay, "use_nodes"):
        clay.use_nodes = True
    b = next(n for n in clay.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1)
    b.inputs["Roughness"].default_value = 0.45
    for o in bpy.data.objects:
        if o.type == "MESH":
            for i in range(len(o.data.materials)):
                o.data.materials[i] = clay
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.data.energy *= 0.25
    d = bpy.data.lights.new("Rake", "AREA")
    d.energy, d.size = 60, 0.08
    rk = fr._link(bpy.data.objects.new("Rake", d))
    rk.location = (head_x - 1.0, -0.9, fr.HEAD_Z + 0.7)
    rk.rotation_euler = (Vector((head_x, 0, fr.HEAD_Z)) - rk.location).to_track_quat("-Z", "Y").to_euler()
    for o in bpy.data.objects:
        if o.name.startswith(("Cap", "Twist", "G_Hair", "G_Bangs")):
            o.hide_render = True      # see the skull and face planes
    scene.render.resolution_x = scene.render.resolution_y = a.size
    hz = fr.HEAD_Z * (0.95 if a.who == "hers" else 1.0) - 0.03
    cam = fr.camera(scene, (0, -1, 1), (0, 0, 1), lens=100)
    for name, off in (("front", (0.0, -1.2, 0.02)), ("three_quarter", (0.7, -0.98, 0.04)), ("profile", (1.2, 0.0, 0.02))):
        tgt = Vector((head_x, -0.01, hz))
        fr.aim(cam, tgt + Vector(off), tgt, lens=100)
        fr.shoot(scene, os.path.join(a.out, f"{a.who}_clay_{name}.png"))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
