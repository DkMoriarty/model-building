"""Build the anime / illustrated character inside YOUR Blender (tested headless on
5.0; written to also run on 3.3 - tell the agent what breaks).

1. Put this file next to fixie_rider.py, street_scene.py and anime_char.py.
2. Blender -> Scripting tab -> Open -> RUN_ANIME_IN_BLENDER.py -> Run Script (Alt+P).
3. Wait ~1-2 minutes. Look through the camera (Numpad 0), Z -> Rendered, F12 to render.
4. File -> Save As -> anime_character.blend (saved in your version).

Change the options below and run again.
"""
import os
import sys

OUTFIT = "vest"          # "vest" | "bare" | "jacket"
HAND = "relaxed"         # "relaxed" | "fist" | "open"
FACE = "anime"           # "anime" (our anime face, default) | "illustrated" (reference study)
EXPRESSION = "COOL"      # COOL, HAPPY, SMUG, NOTICE, SHOCK, STRUCK, DAZED, SIDEEYE
FOLDER = r"C:\Users\Dhiraj Office\Downloads\toon_chars"

import bpy  # noqa: E402
for _t in bpy.data.texts:                      # opened from disk in the Text editor: use its own folder
    if _t.name.startswith("RUN_ANIME") and _t.filepath:
        FOLDER = os.path.dirname(bpy.path.abspath(_t.filepath))
if "__file__" in globals() and os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "anime_char.py")):
    FOLDER = os.path.dirname(os.path.abspath(__file__))
if FOLDER not in sys.path:
    sys.path.insert(0, FOLDER)
for m in ("fixie_rider", "street_scene", "anime_char"):
    sys.modules.pop(m, None)
from mathutils import Vector  # noqa: E402
import fixie_rider as fr      # noqa: E402
import anime_char as ac       # noqa: E402

scene, rig, bike = ac.build_anime(100, reset=False, outfit=OUTFIT, hand=HAND, face=FACE)
for o in bpy.data.objects:     # character only (the bike is hidden)
    if o.name.startswith(("TopTube", "DownTube", "SeatTube", "HeadTube", "ChainStay", "SeatStay", "Fork", "Stem", "Bar",
                          "Grip", "SeatPost", "Saddle", "Cog", "Chain", "Wheel", "Tire", "Rim", "Hub", "Spoke", "Crank",
                          "Pedal")):
        o.hide_render = True
        o.hide_viewport = True
fr.pose_stand(rig)
ac.pose_a(rig)
fr.FaceRig(rig, "").pose(EXPRESSION)
cam = fr.camera(scene, (0.9, -4.6, 1.05), (0, 0, 0.95), lens=50)
ac.anime_look(scene, cam, Vector((0, 0, 1.4)))
scene.render.resolution_x, scene.render.resolution_y = 1080, 1620
print("Done: anime character built (outfit=%s, hand=%s, face=%s). File -> Save As to keep it." % (OUTFIT, HAND, FACE))
