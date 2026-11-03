"""Build both characters inside YOUR Blender (any 4.x / 5.x).

1. Unzip this folder to:  C:\\Users\\Dhiraj Office\\Downloads\\toon_chars
   (anywhere works when you open this file from disk; FOLDER below is the fallback)
2. Blender -> Scripting tab -> Open -> RUN_IN_BLENDER.py -> Run Script (Alt+P)
3. Wait ~1 minute. Then File -> Save As -> characters.blend (saved in your version).
"""
import os
import sys

FOLDER = r"C:\Users\Dhiraj Office\Downloads\toon_chars"

import bpy  # noqa: E402
for _t in bpy.data.texts:                      # opened from disk in the Text editor: use its own folder
    if _t.name.startswith("RUN_IN_BLENDER") and _t.filepath:
        FOLDER = os.path.dirname(bpy.path.abspath(_t.filepath))
if "__file__" in globals() and os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixie_rider.py")):
    FOLDER = os.path.dirname(os.path.abspath(__file__))

if FOLDER not in sys.path:
    sys.path.insert(0, FOLDER)
for m in ("fixie_rider", "street_scene"):
    sys.modules.pop(m, None)
import bpy                      # noqa: E402
from mathutils import Vector    # noqa: E402
import fixie_rider as fr        # noqa: E402
fr.HAIR = "ribbons"
import street_scene as ss       # noqa: E402

scene, rig, bike = fr.build(100, reset=False)   # keeps your Blender UI
fr.pose_stand(rig)
g_rig, _ = ss.build_girl()
fr.pose_stand(g_rig)
g_rig.location = (0.75, 0.0, 0.0)
bpy.context.view_layer.update()
fr.FaceRig(rig, "").pose("COOL")
fr.FaceRig(g_rig, "G_").pose("CALM")

BIKE = ("TopTube", "DownTube", "SeatTube", "HeadTube", "ChainStay", "SeatStay", "Fork", "Stem", "Bar", "Grip", "SeatPost",
        "Saddle", "Cog", "Chain", "Wheel", "Tire", "Rim", "Hub", "Spoke", "Crank", "Pedal", "Bike")
bc = bpy.data.collections.new("Bike")
scene.collection.children.link(bc)
for o in list(bpy.data.objects):
    if o.name.startswith(BIKE) or (o.parent and o.parent.name.startswith(BIKE)):
        for c in list(o.users_collection):
            c.objects.unlink(o)
        bc.objects.link(o)
bpy.context.view_layer.layer_collection.children["Bike"].exclude = True

mid = Vector((0.37, 0, 1.0))
cam = fr.camera(scene, (0.37, -5.2, 1.15), mid, lens=50)
fr.golden_hour(scene, cam, mid, fstop=4.0)
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
print("Done: both characters built. File -> Save As to keep them.")
