"""Expression sheet for the fixie rider and the girl: every named expression
of the face rig, rendered close up in the studio and labelled.

    blender -b -P blender_pipeline/characters3d/expression_sheet.py -- --out renders/expressions
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
import street_scene as ss  # noqa: E402

HIS = ["COOL", "HAPPY", "NOTICE", "SHOCK", "STRUCK", "DAZED"]
HERS = ["CALM", "STARTLED", "AMUSED"]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="renders/expressions")
    ap.add_argument("--size", type=int, default=420)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    scene, rig, bike = fr.build(100)
    for o in list(bpy.data.objects):          # studio only: no bike
        if o.name in ("CapBand",) or any(o.name.startswith(n) for n in (
                "TopTube", "DownTube", "SeatTube", "HeadTube", "ChainStay", "SeatStay", "Fork", "Stem", "Bar", "Grip",
                "SeatPost", "Saddle", "Cog", "Chain", "Wheel", "Tire", "Rim", "Hub", "Spoke", "Crank", "Pedal")):
            o.hide_render = True
    fr.pose_stand(rig)
    g_rig, _ = ss.build_girl()
    g_rig.location = (1.6, 0.0, 0.0)
    his, hers = fr.FaceRig(rig, ""), fr.FaceRig(g_rig, "G_")
    scene.render.resolution_x = scene.render.resolution_y = a.size
    cam = fr.camera(scene, (0, -1, 1), (0, 0, 1), lens=85)
    paths = []
    for who, face, names, head in (("his", his, HIS, Vector((0.0, -0.01, fr.HEAD_Z - 0.02))),
                                   ("hers", hers, HERS, Vector((1.6, -0.005, fr.HEAD_Z * 0.95 - 0.02)))):
        for name in names:
            face.pose(name)
            for other in (his, hers):
                if other is not face:
                    other.pose("COOL" if other is his else "CALM")
            bpy.context.view_layer.update()
            fr.aim(cam, head + Vector((0.32, -1.25, 0.03)), head, lens=90)
            p = os.path.join(a.out, f"{who}_{name}.png")
            fr.shoot(scene, p)
            fr.film_grain(p)
            paths.append((name, p))
    # Contact sheet with labels.
    try:
        from PIL import Image, ImageDraw
        tiles = [(n, Image.open(p).convert("RGB")) for n, p in paths]
        w, h = tiles[0][1].size
        cols = 3
        rows = math.ceil(len(tiles) / cols)
        sheet = Image.new("RGB", (w * cols, (h + 34) * rows), (236, 234, 230))
        d = ImageDraw.Draw(sheet)
        for i, (n, im) in enumerate(tiles):
            x, y = (i % cols) * w, (i // cols) * (h + 34)
            sheet.paste(im, (x, y))
            d.text((x + 12, y + h + 8), n, fill=(40, 40, 40))
        sheet.save(os.path.join(a.out, "expression_sheet.png"))
        print("sheet", os.path.join(a.out, "expression_sheet.png"))
    except ImportError:
        pass


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
