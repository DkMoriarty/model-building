"""SHARP ANIME CHARACTER: an original anime-style boy built on the fixie
rider's rig and body, with an anime face, spiky ribbon hair and an anime
render look.

    blender -b -P blender_pipeline/characters3d/anime_char.py -- --out renders/anime

The anime look (`anime_look`):
- Cel shading: every material becomes flat colour x a two-band light ramp
  (Shader to RGB -> constant colour ramp): one lit tone, one cool shadow tone,
  a hard terminator, no gradients.
- Ink outlines: an inverted hull (Solidify, flipped normals, black backface-
  culled material) on every body part, thinner on the face, none on the small
  eye/mouth parts that are already drawn in ink.
- Light: one hard sun (crisp cast shadows), a flat sky, Standard view
  transform so the colours stay clean and saturated (no filmic roll-off).

The face (`ANIME_LAYOUT`): a shield head tapering to a sharp V chin, huge
almond eyes set low with a thick upper lash line, a tall iris with two
highlights, sharp thin brows, a tiny nose, a small mouth; spiky ribbon hair
with bangs falling between the eyes.
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

# Palette: clean anime colours (Standard view transform keeps them as picked).
ANIME_COL = {
    "skin": "#f6d3bd", "blush_toon": "#f3b4a6", "lip_toon": "#d97b78",
    "skin_cel_lit": "#f6d3bd", "skin_cel_shadow": "#d9a495", "skin_cel_rim": "#fff1e6",   # body = face skin
    "anime_iris": "#2f74d0", "hair": "#20223a", "eye_white": "#ffffff", "iris": "#0e1020", "liner": "#141522",
    "shirt": "#f4f4f6", "shirt_seam": "#c9cbd6", "shorts": "#27304f", "sock": "#f4f4f6", "shoe": "#ececf0",
    "sole": "#3a3f55", "cap": "#c8313a", "cap_seam": "#9a2229", "bag": "#2a2b33",
}

ANIME_LAYOUT = dict(eye_ux=0.43, eye_uz=-0.2, nose_z=-0.5, mouth_z=-0.7, chin_z=-1.0, ear_uz=-0.22, ear_h=0.55,
                    mouth_w=0.14, almond_h=1.0, liner=1.6, iris=1.3, soft=1.0, brow_drop=-0.02,
                    eye_k=(0.62, 1.15, 0.45), eye_sink=0.3, iris_x=0.06, shield=1.0, slit=1.0, iris_tall=1.35, inner_dip=0.35)

NO_OUTLINE = ("Iris", "Pupil", "Glint", "LidLiner", "LowLiner", "LashSweep", "Lash", "Brow", "Smile", "Dimple",
              "Pout", "Mouth", "Blush", "Sparkle", "Sweat", "Hair_Profile", "GH_", "Sun", "Cyc", "Eye")


def build_anime(pct=100, reset=True):
    for k, v in ANIME_COL.items():
        fr.COL[k] = fr.hx(v)
    fr.HAIR = "ribbons"
    scene, rig, bike = fr.build(pct, reset=reset)
    # Replace his face with the anime face: remove everything on the Head bone, rebuild.
    for o in [o for o in bpy.data.objects if o.parent == rig and o.parent_bone == "Head"]:
        bpy.data.objects.remove(o)
    parts = []

    def add(ob, bone):
        fr.bind(ob, rig, bone)
        parts.append(ob)
        return ob
    hc = Vector((0, -0.01, fr.HEAD_Z))
    size = (0.105, 0.11, 0.14)
    skin = fr.mat("skin", 0.6)
    fr.build_face(add, hc, size, skin, "anime_iris", "hair", "lip_toon", nose=0.35, chin=0.4, cheek=0.6, jaw=0.75,
                  eye_r=0.036, smirk=0.15, style="toon", lips=0.2,
                  paint=("skin", "blush_toon", "lip_toon", None), brows="sharp", wing=0.6, eye_shape="almond",
                  layout=ANIME_LAYOUT)
    fr.ribbon_hair(add, hc, size, fr.matte_hair_material(fr.COL["hair"]), seed=21, style="anime")
    # A slimmer anime neck.
    for o in [o for o in bpy.data.objects if o.name == "Neck"]:
        bpy.data.objects.remove(o)
    add(fr.tube("Neck", [(0, 0.01, 1.42), (0, 0.0, fr.HEAD_Z - 0.08)], [0.04, 0.036], skin), "Neck")
    return scene, rig, bike


# ---------------------------------------------------------------------------
# The anime render look
# ---------------------------------------------------------------------------

def _base_colour_source(nt, bsdf):
    """The socket feeding Base Color (attribute paint, image...) or None."""
    links = [lk for lk in nt.links if lk.to_socket == bsdf.inputs["Base Color"]]
    return links[0].from_socket if links else None


def cel_material(m, shadow=0.62, terminator=0.3):
    """Turn a Principled material into a two-tone cel material."""
    if not getattr(m, "node_tree", None):
        return
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    if bsdf is None or out is None or m.name.startswith("ANIME_"):
        return
    src = _base_colour_source(nt, bsdf)
    col = None
    if src is None:
        rgb = nt.nodes.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = bsdf.inputs["Base Color"].default_value
        col = rgb.outputs[0]
    else:
        col = src
    glossy = bsdf.inputs["Roughness"].default_value < 0.2 and not src      # eyes, glints: keep them bright and flat
    diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    e0, e1 = ramp.color_ramp.elements
    e0.position, e1.position = 0.0, terminator
    e0.color = (shadow * 0.92, shadow * 0.9, shadow * 1.08, 1)                # cool shadow tone
    e1.color = (1, 1, 1, 1)
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    if hasattr(bpy.types, "ShaderNodeMix"):                                  # Blender 3.4+
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        a_in, b_in, out_ = mul.inputs[6], mul.inputs[7], mul.outputs[2]
    else:                                                                    # Blender 3.3 (the user's)
        mul = nt.nodes.new("ShaderNodeMixRGB")
        a_in, b_in, out_ = mul.inputs[1], mul.inputs[2], mul.outputs[0]
    mul.blend_type = "MULTIPLY"
    mul.inputs[0].default_value = 0.0 if glossy else 1.0
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(diff.outputs[0], s2r.inputs[0])
    nt.links.new(s2r.outputs[0], bw.inputs[0])
    nt.links.new(bw.outputs[0], ramp.inputs[0])
    nt.links.new(col, a_in)
    nt.links.new(ramp.outputs[0], b_in)
    nt.links.new(out_, em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])


def outline_material():
    m = bpy.data.materials.get("ANIME_Outline")
    if m:
        return m
    m = bpy.data.materials.new("ANIME_Outline")
    if getattr(m, "node_tree", None) is None and hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = fr.hx("#151520")
    nt.links.new(em.outputs[0], next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL").inputs["Surface"])
    m.use_backface_culling = True
    if hasattr(m, "use_backface_culling_shadow"):
        m.use_backface_culling_shadow = True
    return m


def add_outline(ob, width):
    """Inverted hull: a flipped, outward-pushed shell in ink, backface-culled."""
    if ob.type not in ("MESH", "CURVE") or ob.hide_render or ob.name.startswith(NO_OUTLINE):
        return
    key = ob.name.split(".")[0]
    for pre in ("G_",):
        if key.startswith(pre):
            key = key[len(pre):]
    if key.startswith(NO_OUTLINE):
        return
    sc = ob.matrix_world.to_scale()
    s = max(1e-6, (abs(sc.x) + abs(sc.y) + abs(sc.z)) / 3)
    om = outline_material()
    if om.name not in [mm.name for mm in ob.data.materials if mm]:
        ob.data.materials.append(om)
    try:
        mod = ob.modifiers.new("Outline", "SOLIDIFY")
    except (RuntimeError, TypeError):
        return
    mod.thickness = -width / s
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.material_offset = len(ob.data.materials) - 1


def anime_look(scene, cam, subject, outline=0.0022, face_outline=0.0012):
    """Cel shading + ink outlines + one hard sun + flat sky + Standard view."""
    for m in list(bpy.data.materials):
        # Anime faces: shaded only by cast shadows (hair), not by every sculpted bump.
        cel_material(m, terminator=0.08 if "SkinPaint" in m.name else 0.3)
    for ob in list(bpy.data.objects):
        on_head = ob.parent_type == "BONE" and ob.parent_bone == "Head"
        if ob.name == "Head":
            continue                     # the face silhouette comes from a separate thin hull (below)
        add_outline(ob, face_outline if on_head else outline)
    head = bpy.data.objects.get("Head")
    if head:
        add_outline(head, 0.0006)
    for o in list(bpy.data.objects):
        if o.type == "LIGHT" or o.name in ("Cyc",):
            o.hide_render = True
    sun = bpy.data.lights.new("ANIME_Sun", "SUN")
    sun.energy, sun.angle = 2.2, math.radians(0.5)
    so = fr._link(bpy.data.objects.new("ANIME_Sun", sun))
    to_cam = (cam.location - Vector(subject)).normalized()
    side = to_cam.cross(Vector((0, 0, 1))).normalized()
    p = Vector(subject) + side * 2.0 + to_cam * 2.2 + Vector((0, 0, 2.6))
    so.rotation_euler = (Vector(subject) - p).to_track_quat("-Z", "Y").to_euler()
    world = scene.world
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    nt = world.node_tree
    bg.inputs["Color"].default_value = (0.55, 0.6, 0.75, 1)          # dim cool ambient: shadows stay in the shadow band
    bg.inputs["Strength"].default_value = 0.12
    sky = nt.nodes.new("ShaderNodeBackground")
    sky.inputs["Color"].default_value = fr.hx("#cfe3f4")
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    wout = next(n for n in nt.nodes if n.type == "OUTPUT_WORLD")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(sky.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], wout.inputs["Surface"])
    vs = scene.view_settings
    vs.view_transform = "Standard"
    if "None" in [i.identifier for i in vs.bl_rna.properties["look"].enum_items]:
        vs.look = "None"
    if hasattr(scene, "eevee"):
        for attr, val in (("use_shadows", True), ("shadow_ray_count", 1), ("shadow_step_count", 6),
                          ("taa_render_samples", 32)):
            if hasattr(scene.eevee, attr):
                setattr(scene.eevee, attr, val)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="renders/anime")
    ap.add_argument("--size", type=int, default=900)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    scene, rig, bike = build_anime(100)
    for o in bpy.data.objects:          # character only
        if o.name.startswith(("TopTube", "DownTube", "SeatTube", "HeadTube", "ChainStay", "SeatStay", "Fork", "Stem",
                              "Bar", "Grip", "SeatPost", "Saddle", "Cog", "Chain", "Wheel", "Tire", "Rim", "Hub",
                              "Spoke", "Crank", "Pedal")):
            o.hide_render = True
    fr.pose_stand(rig)
    bpy.context.view_layer.update()
    face = fr.FaceRig(rig, "")
    head = Vector((0, -0.01, fr.HEAD_Z - 0.03))
    cam = fr.camera(scene, (0, -1, 1), (0, 0, 1), lens=85)
    fr.aim(cam, head + Vector((0.35, -1.2, 0.02)), head, lens=85)
    anime_look(scene, cam, head)
    shots = [("portrait_3q", "COOL", head + Vector((0.38, -1.15, 0.02)), head, 85, (a.size, int(a.size * 1.15))),
             ("portrait_front", "SMUG", head + Vector((0.0, -1.2, 0.0)), head, 85, (a.size, int(a.size * 1.15))),
             ("full_body", "COOL", Vector((0.9, -4.6, 1.05)), Vector((0, 0, 0.95)), 50, (a.size, int(a.size * 1.5)))]
    for name, expr, loc, tgt, lens, (w, h) in shots:
        face.pose(expr)
        scene.render.resolution_x, scene.render.resolution_y = w, h
        fr.aim(cam, loc, tgt, lens=lens)
        fr.shoot(scene, os.path.join(a.out, f"{name}.png"))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
