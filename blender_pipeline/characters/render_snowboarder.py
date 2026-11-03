"""Render model-sheet stills of CH_Snowboarder.

    blender -b -P blender_pipeline/characters/render_snowboarder.py -- --out renders/ [--views rest,sheet,walk,mouths] [--pct 50]
"""

import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402

import snowboarder as sb  # noqa: E402
import toonkit as tk  # noqa: E402

PAPER = sb.hx("#f4efe6")

# "Let's ride!" broken into mouth shapes (seconds, viseme).
LETS_RIDE = [(0.0, "REST"), (0.20, "LDT"), (0.28, "E"), (0.40, "LDT"), (0.48, "E"), (0.60, "REST"),
             (0.72, "WQ"), (0.82, "A_I"), (0.98, "LDT"), (1.10, "REST")]


def scene_setup(pct, paper=PAPER):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    tk.setup_project(s, 1080, 1440, 24, 48)  # portrait, like the sheet
    engines = [e.identifier for e in s.render.bl_rna.properties["engine"].enum_items]
    s.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    s.render.resolution_percentage = pct
    s.view_settings.view_transform = "Standard"  # swatch colours render exactly
    s.world = bpy.data.worlds.new("Paper")
    s.world.color = paper[:3]
    if getattr(s.world, "node_tree", None) is None and hasattr(s.world, "use_nodes"):
        s.world.use_nodes = True
    bg = next(n for n in s.world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = paper
    s.render.film_transparent = False
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("Cam", cam_data)
    s.collection.objects.link(cam)
    cam.rotation_euler = (math.radians(90), 0, 0)
    s.camera = cam
    return s, cam


def frame_on(cam, x, z, height):
    cam.location = (x, -10, z)
    cam.data.ortho_scale = height  # portrait: ortho scale spans the long (vertical) side


def shoot(s, path):
    s.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("rendered", path)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="renders")
    ap.add_argument("--views", default="rest,sheet,walk,mouths")
    ap.add_argument("--pct", type=int, default=50)
    ap.add_argument("--look", default="sheet1", choices=list(sb.LOOKS))
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    sb.use_look(a.look)
    s, cam = scene_setup(a.pct, sb.COL["paper"])
    rig, art, board = sb.build(look=a.look)
    tag = "" if a.look == "sheet1" else f"_{a.look}"
    views = a.views.split(",")

    if "rest" in views:
        sb.reset_pose(rig)
        board.hide_render = True
        frame_on(cam, 0.05, 1.12, 2.45)
        shoot(s, os.path.join(a.out, f"snowboarder_rest{tag}.png"))
    if "sheet" in views:
        sb.pose_sheet(rig)
        board.hide_render = False
        frame_on(cam, 0.12, 1.12, 2.45)
        shoot(s, os.path.join(a.out, f"snowboarder_sheet_pose{tag}.png"))
    if "walk" in views:
        board.hide_render = True
        keys = sb.walk(rig)
        frame_on(cam, 0.05, 1.12, 2.45)
        for f in (1, 4, 7, 13, 19):
            s.frame_set(f)
            shoot(s, os.path.join(a.out, f"snowboarder_walk_{f:02d}.png"))
    if "anim" in views:
        # Two walk loops while she says "Let's ride!", then a smirk.
        board.hide_render = True
        sb.walk(rig, start=1, length=24)
        tk.walk_front(rig, start=25, length=24, H=0.32)
        sb.talk(art, LETS_RIDE)
        frame_on(cam, 0.05, 1.12, 2.45)
        frames_dir = os.path.join(a.out, "anim_frames")
        os.makedirs(frames_dir, exist_ok=True)
        for f in range(1, 49):
            s.frame_set(f)
            shoot(s, os.path.join(frames_dir, f"f{f:03d}.png"))
    if "faces" in views:
        sb.reset_pose(rig)
        board.hide_render = True
        s.render.resolution_x = s.render.resolution_y = 600
        frame_on(cam, *sb.P(590, 540), 0.5)
        for eyes, mouth in (("GLARE", "REST"), ("HAPPY", "A_I"), ("SIDE", "SMIRK"), ("SQUINT", "GRIT")):
            art.modifiers["Eye Swap"].offset = sb.EXPRESSIONS.index(eyes) + 1
            art.modifiers["Mouth Swap"].offset = (tk.VISEMES + sb.MOUTH_EXTRAS).index(mouth) + 1
            shoot(s, os.path.join(a.out, f"snowboarder_face_{eyes}{tag}.png"))
    if "mouths" in views:
        sb.reset_pose(rig)
        board.hide_render = True
        s.render.resolution_x = s.render.resolution_y = 600
        frame_on(cam, *sb.P(590, 540), 0.5)
        for i, v in enumerate(tk.VISEMES, start=1):
            art.modifiers["Mouth Swap"].offset = i
            shoot(s, os.path.join(a.out, f"snowboarder_mouth_{i}_{v}.png"))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
