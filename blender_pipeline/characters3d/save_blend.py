"""Save both characters (posed, faces on, golden-hour lights, camera) to a .blend you can open in Blender.

    blender -b -P blender_pipeline/characters3d/save_blend.py -- characters.blend
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixie_rider as fr
fr.HAIR = "ribbons"
import street_scene as ss
import bpy
from mathutils import Vector
scene, rig, bike = fr.build(100)
fr.pose_stand(rig)
g_rig, _ = ss.build_girl()
fr.pose_stand(g_rig)
g_rig.location = (0.75, 0.0, 0.0)          # pose_stand resets location: place her after
bpy.context.view_layer.update()
fr.FaceRig(rig, "").pose("COOL"); fr.FaceRig(g_rig, "G_").pose("CALM")
# bike: put in its own collection, hidden (toggle it on in the outliner)
BIKE = ("TopTube","DownTube","SeatTube","HeadTube","ChainStay","SeatStay","Fork","Stem","Bar","Grip","SeatPost","Saddle","Cog","Chain","Wheel","Tire","Rim","Hub","Spoke","Crank","Pedal","Bike")
bc = bpy.data.collections.new("Bike"); scene.collection.children.link(bc)
for o in list(bpy.data.objects):
    if o.name.startswith(BIKE) or (o.parent and o.parent.name.startswith(BIKE)):
        for c in list(o.users_collection): c.objects.unlink(o)
        bc.objects.link(o)
lc = bpy.context.view_layer.layer_collection.children["Bike"]
lc.exclude = True
mid = Vector((0.37, 0, 1.0))
cam = fr.camera(scene, (0.37, -5.2, 1.15), mid, lens=50)
fr.golden_hour(scene, cam, mid, focus=None, fstop=4.0)
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
bpy.ops.file.pack_all() if hasattr(bpy.ops.file, "pack_all") else None
p = os.path.abspath(sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "characters.blend")
bpy.ops.wm.save_as_mainfile(filepath=p, compress=True)
print("saved", p, os.path.getsize(p))
