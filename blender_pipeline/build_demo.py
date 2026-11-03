"""Build a demo episode with every department's step, check it, and save it.

    blender -b -P blender_pipeline/build_demo.py -- --out demo/demo.blend [--render 1,13,30]
    # or, with the bpy module (Python 3.11): python build_demo.py --out ...

Exits non-zero if any check fails, so it doubles as the toolkit's test.
"""

import argparse
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import toonkit as tk  # noqa: E402

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def world_tail(arm, bone):
    return arm.matrix_world @ arm.pose.bones[bone].tail


def world_head(arm, bone):
    return arm.matrix_world @ arm.pose.bones[bone].head


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "toonkit_demo", "demo.blend"))
    ap.add_argument("--render", default="", help="comma-separated frames to render as PNG stills")
    args = ap.parse_args(argv)
    out_dir = os.path.dirname(os.path.abspath(args.out))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "Shot_01"

    # Production setup
    made = tk.make_studio_tree(os.path.join(out_dir, "Studio"))
    check("studio folder tree", all(os.path.isdir(p) for p in made), f"{len(made)} folders")
    tk.setup_project(scene, fps=24, frame_end=48)
    check("project 1920x1080 @24, frame dropping",
          (scene.render.resolution_x, scene.render.fps, scene.sync_mode) == (1920, 24, "FRAME_DROP"))

    # Rigging
    H = 0.5
    rig = tk.build_biped_armature("CH_Hero_Rig", H=H)
    tk.add_leg_ik(rig, "L")
    tk.add_leg_ik(rig, "R")
    bpy.context.view_layer.update()
    for s in "LR":
        rest = rig.matrix_world @ rig.data.bones[f"Leg_Lower_{s}"].tail_local
        moved = (world_tail(rig, f"Leg_Lower_{s}") - rest).length
        check(f"IK {s}: rest pose unchanged by pole angle", moved < 1e-3,
              f"pole {math.degrees(rig.pose.bones[f'Leg_Lower_{s}'].constraints[0].pole_angle):.0f} deg, drift {moved:.5f}")
    # Squash the torso down: feet must stay planted and the knees bend forward.
    rig.pose.bones["Torso"].location = (0, -0.3 * H, 0)  # bone-local Y = world up
    bpy.context.view_layer.update()
    ankle = world_tail(rig, "Leg_Lower_L")
    knee = world_head(rig, "Leg_Lower_L")
    hip = world_head(rig, "Leg_Upper_L")
    check("IK: foot stays on the floor when the body drops", abs(ankle.z) < 0.01, f"ankle z {ankle.z:.4f}")
    check("IK: knee bends forward (+X), not backwards",
          knee.x > max(hip.x, ankle.x) + 0.02, f"knee x {knee.x:.3f}, hip x {hip.x:.3f}")
    rig.pose.bones["Torso"].location = (0, 0, 0)

    art = tk.draw_stick_character(rig, H=H)
    check("drawing: one layer per deform bone", len(art.data.layers) == len(tk.DEFORM_BONES))
    check("binding: vertex group per layer + armature modifier",
          len(art.vertex_groups) == len(tk.DEFORM_BONES) and art.modifiers["Rig"].object == rig)

    # Lip sync
    head = rig.data.bones["Head"]
    mouth_c = ((head.head_local + head.tail_local) / 2)
    tk.setup_mouth_library(art, center=(mouth_c.x + 0.12 * H, mouth_c.z - 0.15 * H), size=0.12 * H)
    tk.bind_layers_to_bones(art, rig, {"Mouth": "Head"})
    cues = tk.rhubarb_cues({"mouthCues": [
        {"start": 0.0, "end": 0.2, "value": "X"}, {"start": 0.2, "end": 0.35, "value": "D"},
        {"start": 0.35, "end": 0.5, "value": "A"}, {"start": 0.5, "end": 0.7, "value": "F"},
        {"start": 0.7, "end": 1.0, "value": "X"}]})
    frames = tk.key_visemes(art, cues, fps=24, lead_frames=1)
    check("lip sync: 9 viseme drawings on the Mouth layer", len(art.data.layers["Mouth"].frames) == 9)
    scene.frame_set(frames[2])
    check("lip sync: MBP shows on its frame (1-frame lead)",
          art.modifiers["Mouth Swap"].offset == tk.VISEMES.index("MBP") + 1, f"frame {frames[2]}")

    # Key animation: walk cycle through the IK targets
    keys = tk.walk_cycle(rig, start=1, length=24, H=H)
    scene.frame_set(1)
    l1 = world_tail(rig, "Leg_Lower_L")
    scene.frame_set(25)
    l25 = world_tail(rig, "Leg_Lower_L")
    check("walk: left foot forward at contact, back at opposite contact", l1.x > 0.1 > -0.1 > l25.x,
          f"x {l1.x:.2f} -> {l25.x:.2f}")
    scene.frame_set(1)
    hl, hr = world_tail(rig, "Hand_L").x, world_tail(rig, "Hand_R").x
    check("walk: arms oppose legs (left leg forward, left arm back)", hl < hr - 0.1, f"hand L {hl:.2f}, R {hr:.2f}")
    scene.frame_set(keys[1])
    t_down = world_head(rig, "Torso").z
    scene.frame_set(keys[3])
    t_up = world_head(rig, "Torso").z
    check("walk: torso dips on down, rises on up", t_up > t_down + 0.05, f"{t_down:.3f} < {t_up:.3f}")

    # Layout: camera, multiplane, depth of field, moves, shake
    cam = tk.setup_camera(scene, distance=8.0, height=1.3)
    layers = tk.build_multiplane(scene, cam, colors={"BG_Far": (0.55, 0.72, 0.85, 1), "BG_Mid": (0.80, 0.86, 0.80, 0.0),
                                                     "FG_Overlay": (0.10, 0.12, 0.18, 1)})
    floor = bpy.data.meshes.new("Floor")
    floor.from_pydata([(-30, -2, 0), (30, -2, 0), (30, 20, 0), (-30, 20, 0)], [], [(0, 1, 2, 3)])
    floor.materials.append(tk.flat_material("Floor_Paint", (0.86, 0.80, 0.66, 1)))
    layers["BG_Mid"].objects.link(bpy.data.objects.new("Floor", floor))
    for ob in (rig, art):
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        layers["Characters"].objects.link(ob)
    w_far, _ = tk.view_size_at(cam, scene, 40.0)
    card = bpy.data.objects["BG_Far_Card"]
    check("multiplane: far card covers frame plus shake margin", card.dimensions.x >= w_far * 1.1,
          f"{card.dimensions.x:.1f} >= {w_far:.1f}")
    tk.depth_of_field(cam, focus_object=rig, fstop=2.8)
    tk.camera_move(cam, 1, 48, loc1=(1.5, -6.5, 1.3), loc0=(0, -8.0, 1.3), ease="EASE")
    tk.handheld(cam, strength=0.01, scale=30)
    tk.impact_shake(cam, scene, frame=30, tier="medium")

    def cam_x(f):
        scene.frame_set(f)
        return cam.matrix_world.translation.x
    base = {f: cam_x(f) for f in range(26, 42)}
    # Remove noise to compare against the clean move
    noise = [(fc, m) for fc in tk.fcurves(cam) for m in fc.modifiers]
    for _, m in noise:
        m.mute = True
    clean = {f: cam_x(f) for f in base}
    for _, m in noise:
        m.mute = False
    shake = {f: abs(base[f] - clean[f]) for f in base}
    w0, _ = tk.view_size_at(cam, scene, 0.0)
    px = {f: v / w0 * 1920 for f, v in shake.items()}
    pre = max(px[f] for f in range(26, 30))
    peak = max(px[f] for f in range(30, 34))
    tail = px[41]
    check("shake: quiet before the hit (handheld only)", pre < 6, f"{pre:.1f} px")
    check("shake: medium tier peaks 6-20 px on impact", 6 <= peak <= 20, f"{peak:.1f} px")
    check("shake: settled after the tier length", tail < 6, f"{tail:.1f} px at f41")

    # VFX: line art on a 3D prop, lighting, drop shadow, glow, contact shadow, compositor
    props = bpy.data.collections.new("3D_Props")
    scene.collection.children.link(props)
    bpy.ops.mesh.primitive_cube_add(size=0.6, location=(-1.4, 0.5, 0.3))
    cube = bpy.context.object
    for c in list(cube.users_collection):
        c.objects.unlink(cube)
    props.objects.link(cube)
    outl = tk.line_art(props)
    check("line art: modifier reads the 3D_Props collection",
          outl.modifiers["Line Art"].source_collection == props)
    sun = tk.add_key_light()
    tk.light_layers(art)
    tk.drop_shadow_fx(outl, offset_px=(8, -8))
    tk.drop_shadow_fx(art, pivot=sun)
    tk.glow_fx(art, color=(1.0, 0.5, 0.4), size_px=24)
    sh = tk.contact_shadow(rig)
    scene.frame_set(1)
    check("contact shadow sits on the floor under the rig", abs(sh.matrix_world.translation.z) < 1e-4)
    ng = tk.setup_compositor(scene, glare="Bloom")
    check("compositor: render layers -> glare -> output", len(ng.links) == 2)
    bpy.data.worlds.new("World")
    scene.world = bpy.data.worlds["World"]
    scene.world.color = (0.02, 0.02, 0.03)

    # Draft viewport
    tk.draft_viewport(scene, True)
    check("draft viewport: line art hidden in viewport, kept for render",
          not outl.modifiers["Line Art"].show_viewport and outl.modifiers["Line Art"].show_render)
    tk.draft_viewport(scene, False)

    # Shots and editorial
    shot2 = tk.new_shot("Shot_02", [layers["Characters"], layers["BG_Far"], props], frame_end=36, base_scene=scene,
                        camera_distance=4.0)
    master = tk.assemble_master([scene, shot2], out_path=os.path.join(out_dir, "renders", "episode_"))
    strips = list(master.sequence_editor.strips_all if hasattr(master.sequence_editor, "strips_all")
                  else master.sequence_editor.sequences_all)
    check("master edit: shots cut end to end", master.frame_end == 48 + 36 and len(strips) == 2,
          f"{master.frame_end} frames")
    check("output: MPEG-4 / H.264 / AAC",
          (master.render.ffmpeg.format, master.render.ffmpeg.codec, master.render.ffmpeg.audio_codec) == ("MPEG4", "H264", "AAC"))

    # Asset library round trip
    char_coll = layers["Characters"]
    tk.mark_character_asset(char_coll, "Hero rig + drawings")
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.out))
    check("saved demo file", os.path.isfile(args.out), args.out)

    if args.render:
        scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in [
            e.identifier for e in scene.render.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE_NEXT"
        tk.set_output(scene, "final", "")
        scene.render.resolution_percentage = 50
        for f in [int(x) for x in args.render.split(",")]:
            scene.frame_set(f)
            scene.render.filepath = os.path.join(out_dir, f"still_{f:03d}.png")
            try:
                bpy.ops.render.render(write_still=True, scene=scene.name)
                print("rendered", scene.render.filepath)
            except RuntimeError as e:
                print("render skipped:", e)
                break

    # Linking from the library into a fresh episode file
    bpy.ops.wm.read_factory_settings(use_empty=True)
    over = tk.link_character(os.path.abspath(args.out), "Characters")
    rig_o = next((o for o in over.all_objects if o.type == "ARMATURE"), None)
    check("asset link + library override gives an animatable rig",
          rig_o is not None and rig_o.override_library is not None and not rig_o.library)

    failed = [c for c in CHECKS if not c[1]]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    sys.exit(main(argv))
