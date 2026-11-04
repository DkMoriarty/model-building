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

NO_OUTLINE = ("SerratusLine", "Clavicle", "ClavLine", "ClavHollow", "ClavNotch", "PecLine", "SternumLine", "VestRib", "Collar", "Iris", "Pupil", "Glint", "LidLiner", "LowLiner", "LashSweep", "Lash", "Brow", "Smile", "Dimple",
              "Pout", "Mouth", "Blush", "Sparkle", "Sweat", "Hair_Profile", "GH_", "Sun", "Cyc", "Eye")


def build_anime(pct=100, reset=True, outfit="vest"):
    """outfit: 'vest' (white ribbed vest), 'bare' (bare torso: abs, obliques, back inked), 'jacket' (open anime jacket over the vest)."""
    for k, v in ANIME_COL.items():
        fr.COL[k] = fr.hx(v)
    fr.HAIR = "ribbons"
    # Broad anime-male frame: shoulder joints (and so the arms) moved out.
    saved_j = dict(fr.J)
    for side, sx in (("L", 1), ("R", -1)):
        for j, dx in (("sho", 0.04), ("elb", 0.045), ("wri", 0.045), ("hand", 0.045)):
            x, y, z = fr.J[f"{j}_{side}"]
            fr.J[f"{j}_{side}"] = (x + sx * dx, y, z)
    try:
        scene, rig, bike = fr.build(pct, reset=reset)
    finally:
        pass                                 # J stays widened while this character is posed; restored by restore_frame()
    global _SAVED_J
    _SAVED_J = saved_j
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
    # A slimmer anime neck that tapers the right way: slim under the jaw,
    # flaring at the base into the traps; its two diagonal muscles sit inside
    # the silhouette (behind the ears -> the notch above the breastbone).
    body_skin = next((o.data.materials[0] for o in bpy.data.objects if o.name == "Neck" and o.data.materials), skin)
    for o in [o for o in bpy.data.objects if o.name == "Neck" or o.name.startswith("NeckMuscle")]:
        bpy.data.objects.remove(o)
    add(fr.tube("Neck", [(0, 0.012, 1.395), (0, 0.006, 1.45), (0, 0.002, 1.52), (0, 0.0, fr.HEAD_Z - 0.08)],
                [0.068, 0.046, 0.037, 0.034], body_skin), "Neck")
    for sx in (1, -1):
        add(fr.tube(f"NeckMuscle{sx}", [(sx * 0.026, 0.004, fr.HEAD_Z - 0.1), (sx * 0.022, -0.026, 1.5),
                                        (sx * 0.011, -0.046, 1.43)],
                    [0.0065, 0.0075, 0.0055], body_skin, subdiv=1, ring=10), "Neck")
    build_chest(add, body_skin, outfit=outfit)
    build_shoulders(add, body_skin)
    if outfit == "jacket":
        build_jacket(add, rig)
    return scene, rig, bike


def pose_a(rig, spread=0.085, lift=0.03, fwd=-0.02):
    """Relaxed A-pose: the hands (IK targets) eased out and slightly up and forward,
    so the arms hang away from the body and the shoulder width reads."""
    for s_, sx in (("L", 1), ("R", -1)):
        w = fr.jp(f"wri_{s_}")
        fr.set_ik(rig, f"IK_Hand_{s_}", w + Vector((sx * spread, fwd, lift)))
    bpy.context.view_layer.update()


_SAVED_J = None


def restore_frame():
    """Put the shared rig joints back (only needed if other characters are built after this one)."""
    if _SAVED_J:
        fr.J.clear()
        fr.J.update(_SAVED_J)


def _pecs(ob, depth=0.022, cz=1.3, cx=0.075, top=0.065, under=0.045):
    """Push two pectoral masses out of a torso/vest loft (vertices in world space):
    broad and soft above, ending in a crisp horizontal shelf underneath, with a
    shallow valley down the sternum between them."""
    for v in ob.data.vertices:
        x, y, z = v.co
        if y > 0.02:
            continue
        front = min(1.0, max(0.0, (-y - 0.02) / 0.06))
        w = 0.0
        for c in (cx, -cx):
            gx = math.exp(-((x - c) / 0.068) ** 2)
            if z >= cz:
                gz = math.exp(-((z - cz) / top) ** 2)
            else:                                   # the under-pec shelf: holds full, then drops fast
                gz = max(0.0, min(1.0, (z - (cz - under)) / 0.014)) * (1.0 if z > cz - under + 0.014 else 1.0)
            w = max(w, gx * gz)
        v.co.y -= depth * w * front


def _abs_back(ob, depth=1.0):
    """Sculpt the core and back into a torso loft (world-space vertices):
    a six-pack (3 rows x 2 blocks, the linea alba groove between), obliques
    swelling at the flanks above the hips with the Adonis V groove running
    down-in toward the groin; at the back two shoulder blades and the groove of
    the spine between the long back muscles. depth scales it (a vest shows less)."""
    def plate(a, half, soft):
        return max(0.0, min(1.0, (half - abs(a)) / soft))
    for v in ob.data.vertices:
        x, y, z = v.co
        d = 0.0
        if y < 0.0:                                            # front
            fr_ = min(1.0, -y / 0.05)
            for cx in (0.034, -0.034):
                for cz in (1.215, 1.15, 1.085):              # rounded blocks: they step out in the side profile
                    bx = plate(x - cx, 0.025, 0.012)
                    bz = plate(z - cz, 0.022, 0.011)
                    d += 0.03 * (bx * bz) ** 0.6 * fr_
            # obliques: a soft swell at the flanks, cut by the V line down-in to the groin
            for sx in (1, -1):
                ob_ = math.exp(-((x - sx * 0.12) / 0.035) ** 2) * math.exp(-((z - 1.1) / 0.06) ** 2)
                vline = abs((x - sx * 0.11) * 0.85 + sx * (z - 1.06) * 0.6)
                d += 0.008 * ob_ * fr_ - 0.006 * math.exp(-(vline / 0.006) ** 2) * (1.0 if 0.96 < z < 1.08 else 0.0) * fr_
            v.co.y -= d * depth
        else:                                                  # back
            bk = min(1.0, y / 0.05)
            for sx in (1, -1):                                 # shoulder blades: raised flat triangles
                u = (x - sx * 0.085)
                tri = plate(u + sx * (z - 1.33) * 0.35, 0.045, 0.012) * plate(z - 1.31, 0.06, 0.015)
                d += 0.012 * tri * bk
            d -= 0.008 * math.exp(-(x / 0.012) ** 2) * (1.0 if 1.0 < z < 1.42 else 0.0) * bk     # spine groove
            for sx in (1, -1):                                 # the long back muscles either side of it
                d += 0.006 * math.exp(-((x - sx * 0.035) / 0.02) ** 2) * (1.0 if 1.0 < z < 1.3 else 0.0) * bk
            v.co.y += d * depth


def _surface_bvh(objs):
    """BVH of the surface as RENDERED (after subdivision, which pulls a loft inward),
    so strokes and ridges laid on it sit on the skin instead of floating off it."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys, off = [], [], 0
    for o in objs:
        saved = [(md, md.show_viewport) for md in o.modifiers if md.type == "SOLIDIFY"]
        for md, _ in saved:
            md.show_viewport = False
        dg.update()
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        verts += [o.matrix_world @ v.co for v in me.vertices]
        polys += [tuple(i + off for i in p.vertices) for p in me.polygons]
        off += len(me.vertices)
        ev.to_mesh_clear()
        for md, vis in saved:
            md.show_viewport = vis
    return BVHTree.FromPolygons(verts, polys)


def _jacked_outline(ob, depth=1.0):
    """Give the torso a muscular silhouette, pushing the sides out horizontally
    (world-space vertices): lats flaring wide under the armpits, the serratus
    'fingers' along the ribs, a pinch at the waist, then the obliques swelling
    over the hips before the V cuts in. Seen from the front the outline is no
    longer a straight plane; seen from the side the abs step out (_abs_back)."""
    for v in ob.data.vertices:
        x, y, z = v.co
        r = math.hypot(x, y)
        if r < 1e-6:
            continue
        side = abs(x) / r                                    # 1 at the flanks, 0 at the middle front/back
        out = 0.0
        out += 0.04 * math.exp(-((z - 1.26) / 0.05) ** 2) * side ** 2 * (1.0 if y > -0.06 else 0.6)     # lats
        out -= 0.014 * math.exp(-((z - 1.16) / 0.03) ** 2) * side ** 2                                  # waist pinch
        out += 0.028 * math.exp(-((z - 1.075) / 0.032) ** 2) * side ** 3 * (1.0 if y < 0.04 else 0.5)   # obliques
        if y < 0.0:                                          # serratus fingers on the front-side of the ribs
            for cz in (1.24, 1.21, 1.18):
                out += 0.006 * math.exp(-((z - cz) / 0.009) ** 2) * math.exp(-((side - 0.82) / 0.1) ** 2)
        k = 1.0 + out * depth / r
        v.co.x *= k
        v.co.y *= k


def _ink_on(target, name, pts_xz, widths, add, bone="Spine", back=False):
    """An ink stroke laid on a reshaped surface (ray-cast from the front or back)."""
    bpy.context.view_layer.update()
    bvh = _surface_bvh([target])
    pts = []
    for x, z in pts_xz:
        o, d = (Vector((x, 1.0, z)), Vector((0, -1, 0))) if back else (Vector((x, -1.0, z)), Vector((0, 1, 0)))
        hit = bvh.ray_cast(o, d)
        if hit[0] is None:
            return None
        pts.append(hit[0] + (Vector((0, 0.0012, 0)) if back else Vector((0, -0.0012, 0))))
    return add(fr.tube(name, pts, widths, fr.mat("liner", 0.4), subdiv=1, ring=6), bone)


def build_chest(add, skin, outfit="vest"):
    """A broad V-shaped chest: wide at the pecs and lats, tapering to a narrower
    waist; two pectoral masses with a crisp shelf underneath (the cel shading
    throws a hard shadow line under each pec, through the vest too)."""
    vest_mat = None
    for name in ("Vest", "Torso"):
        o = bpy.data.objects.get(name)
        if o:
            if name == "Vest":
                vest_mat = o.data.materials[0] if o.data.materials else None
            bpy.data.objects.remove(o)
    for o in [o for o in bpy.data.objects if o.name.startswith("VestRib")]:
        bpy.data.objects.remove(o)
    zs = [0.95, 1.01, 1.07, 1.15, 1.22, 1.28, 1.33, 1.37, 1.395]
    body = [(0.132, 0.096), (0.138, 0.1), (0.142, 0.104), (0.158, 0.108), (0.19, 0.118), (0.214, 0.124),
            (0.218, 0.122), (0.205, 0.112), (0.19, 0.104)]
    ys = [0.012, 0.01, 0.008, 0.004, 0.0, -0.004, -0.004, 0.0, 0.004]
    torso = fr.tube("Torso", [(0, y, z) for y, z in zip(ys, zs)], [(a * 0.97, b * 0.97) for a, b in body], skin,
                    ring=40, rows=34, subdiv=2)
    _pecs(torso, depth=0.03)
    _abs_back(torso, 1.0)
    _jacked_outline(torso, 1.0)
    add(torso, "Spine")
    if outfit == "bare":
        for o in [o for o in bpy.data.objects if o.name.startswith("VestStrap")]:
            bpy.data.objects.remove(o)
        # Anime musculature in ink: pec shelves, sternum, abs, obliques' V, shoulder blades, spine.
        for sx in (1, -1):
            _ink_on(torso, f"PecLine{sx}", [(sx * x, z) for x, z in ((0.028, 1.262), (0.06, 1.252), (0.095, 1.256),
                                                                     (0.125, 1.272), (0.145, 1.292))],
                    [0.0008, 0.0022, 0.0026, 0.002, 0.0006], add)
            for k, cz in enumerate((1.183, 1.118)):
                _ink_on(torso, f"AbLine{sx}{k}", [(sx * 0.014, cz + 0.002), (sx * 0.034, cz), (sx * 0.054, cz + 0.003)],
                        [0.0006, 0.0014, 0.0005], add)
            for k, cz in enumerate((1.235, 1.205, 1.175)):       # serratus fingers
                _ink_on(torso, f"SerratusLine{sx}{k}", [(sx * 0.15, cz + 0.006), (sx * 0.162, cz - 0.002), (sx * 0.17, cz - 0.01)],
                        [0.0005, 0.0013, 0.0004], add)
            _ink_on(torso, f"VLine{sx}", [(sx * 0.125, 1.1), (sx * 0.1, 1.05), (sx * 0.07, 1.0)], [0.0005, 0.0016, 0.0005], add)
            _ink_on(torso, f"BladeLine{sx}", [(sx * 0.05, 1.36), (sx * 0.045, 1.31), (sx * 0.07, 1.26), (sx * 0.12, 1.28)],
                    [0.0005, 0.0016, 0.0016, 0.0005], add, back=True)
        _ink_on(torso, "SternumLine", [(0.0, 1.335), (0.0, 1.3), (0.0, 1.27)], [0.0006, 0.0016, 0.0006], add)
        _ink_on(torso, "AbCentre", [(0.0, 1.24), (0.0, 1.15), (0.0, 1.06)], [0.0006, 0.0014, 0.0006], add)
        _ink_on(torso, "SpineLine", [(0.0, 1.4), (0.0, 1.25), (0.0, 1.08)], [0.0006, 0.0016, 0.0006], add, back=True)
        return
    if vest_mat is not None:
        vest = fr.tube("Vest", [(0, y, z) for y, z in zip(ys[:-1], zs[:-1])], [(a * 1.035, b * 1.035) for a, b in body[:-1]],
                       vest_mat, caps=False,
                       ring=40, rows=32, subdiv=2)
        _pecs(vest, depth=0.032)
        _abs_back(vest, 1.0)                                # fitted knit: follows the core and blades (never cut by the skin)
        _jacked_outline(vest, 1.0)
        add(vest, "Spine")
        # Anime chest lines inked on the vest: the curve under each pec and a short
        # stroke down the breastbone (placed by ray-casting the reshaped vest).
        bpy.context.view_layer.update()
        bvh = _surface_bvh([vest])
        liner = fr.mat("liner", 0.4)

        def on_vest(x, z):
            hit = bvh.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)))
            return (hit[0] + Vector((0, -0.0025, 0))) if hit[0] is not None else Vector((x, -0.13, z))
        for sx in (1, -1):
            pts = [on_vest(sx * xx, zz) for xx, zz in ((0.028, 1.262), (0.06, 1.252), (0.095, 1.256), (0.125, 1.272),
                                                      (0.145, 1.292))]
            add(fr.tube(f"PecLine{sx}", pts, [0.0008, 0.0022, 0.0026, 0.002, 0.0006], liner, subdiv=1, ring=6), "Spine")
        add(fr.tube("SternumLine", [on_vest(0.0, 1.335), on_vest(0.0, 1.3), on_vest(0.0, 1.27)], [0.0006, 0.0016, 0.0006],
                    liner, subdiv=1, ring=6), "Spine")
        # Knit ribs down the front panel, following the new chest.
        for k in range(9):
            xk = -0.12 + 0.03 * k
            path = []
            for z in (1.0, 1.1, 1.2, 1.29):
                i = min(range(len(zs)), key=lambda n: abs(zs[n] - z))
                rx, ry = body[i]
                y = -ry * math.sqrt(max(0.0, 1 - (xk / rx) ** 2)) + ys[i] - 0.0015
                path.append((xk, y, z))
            rib = fr.tube(f"VestRib{k}", path, [0.0022] * 4, vest_mat, subdiv=0, ring=6)
            _pecs(rib, depth=0.022)
            add(rib, "Spine")


def build_jacket(add, rig):
    """An open anime jacket over the vest: a dark body with the front left open
    (lapels turned back in the red lining colour), a tall stand collar open at the
    throat, sleeves that bend with the arms (skinned to the arm bones) ending in
    red-trimmed cuffs, and a hem band."""
    import bmesh
    fr.COL["jacket"] = fr.hx("#1f2236")
    fr.COL["jacket_trim"] = fr.hx("#c8313a")
    jm, tm = fr.mat("jacket", 0.85), fr.mat("jacket_trim", 0.7)
    zs = [0.96, 1.07, 1.17, 1.26, 1.33, 1.385, 1.425]
    rr = [(0.165, 0.125), (0.172, 0.13), (0.2, 0.138), (0.232, 0.142), (0.238, 0.14), (0.222, 0.128), (0.16, 0.112)]
    ys = [0.012, 0.006, 0.0, -0.004, -0.004, 0.0, 0.004]
    body = fr.tube("Jacket", [(0, y, z) for y, z in zip(ys, zs)], [(a * 1.04, b * 1.04) for a, b in rr], jm, caps=False,
                   ring=48, rows=30, subdiv=2)
    _pecs(body, depth=0.016)
    _jacked_outline(body, 1.0)                          # follows the lats/waist/obliques underneath
    bm = bmesh.new()
    bm.from_mesh(body.data)
    gone = [f for f in bm.faces if f.calc_center_median().y < -0.05
            and abs(f.calc_center_median().x) < 0.045 + 0.06 * max(0.0, (1.3 - f.calc_center_median().z) / 0.35)]
    bmesh.ops.delete(bm, geom=gone, context="FACES")
    bm.to_mesh(body.data)
    bm.free()
    m = body.modifiers.new("Thick", "SOLIDIFY")
    m.thickness, m.offset = 0.008, 1.0
    if hasattr(m, "material_offset_rim"):
        pass
    add(body, "Spine")
    for sx in (1, -1):                                  # lapels folded back, red lining showing
        add(fr.tube(f"Lapel{sx}", [(sx * 0.05, -0.145, 1.39), (sx * 0.075, -0.15, 1.31), (sx * 0.095, -0.15, 1.2),
                                   (sx * 0.1, -0.145, 1.1)],
                    [(0.004, 0.022), (0.004, 0.03), (0.004, 0.024), (0.003, 0.012)], tm, side=Vector((0, 1, 0)), subdiv=1),
            "Spine")
    collar = fr.tube("JacketCollar", [(0, 0.008, 1.415), (0, 0.006, 1.475)], [(0.088, 0.078), (0.078, 0.07)], jm,
                     caps=False, ring=40, subdiv=1)
    bm = bmesh.new()
    bm.from_mesh(collar.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().y < -0.04
                                and abs(f.calc_center_median().x) < 0.035], context="FACES")
    bm.to_mesh(collar.data)
    bm.free()
    cm = collar.modifiers.new("Thick", "SOLIDIFY")
    cm.thickness, cm.offset = 0.006, 1.0
    add(collar, "Neck")
    hem = fr.tube("JacketHem", [(0, 0.012, 0.955), (0, 0.012, 0.985)], [(0.17, 0.13), (0.17, 0.13)], tm, caps=False,
                  ring=40, subdiv=1)
    bm = bmesh.new()
    bm.from_mesh(hem.data)                              # open at the front like the jacket
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().y < -0.05
                                and abs(f.calc_center_median().x) < 0.105], context="FACES")
    bm.to_mesh(hem.data)
    bm.free()
    add(hem, "Spine")
    # Shoulder yoke: the jacket over the shoulder girdle and the deltoids (copies of
    # those forms pushed out along their normals), so no skin shows at the shoulders.
    for src_name, bone in (("Shoulders", "Spine"), ("DeltCap_L", "UpperArm_L"), ("DeltCap_R", "UpperArm_R")):
        src = bpy.data.objects.get(src_name)
        if src is None:
            continue
        me = src.data.copy()
        me.materials.clear()
        me.materials.append(jm)
        ob = fr._link(bpy.data.objects.new(f"Jacket{src_name}", me))
        ob.matrix_world = src.matrix_world.copy()
        for v in me.vertices:
            v.co += v.normal * (0.016 / max(1e-6, sum(src.matrix_world.to_scale()) / 3))
        for md in src.modifiers:
            if md.type == "SUBSURF":
                ob.modifiers.new("Subdivision", "SUBSURF").levels = md.levels
        ob.parent = None
        add(ob, bone)
    for s_, sx in (("L", 1), ("R", -1)):
        sho, elb, wri, hand = fr.jp(f"sho_{s_}"), fr.jp(f"elb_{s_}"), fr.jp(f"wri_{s_}"), fr.jp(f"hand_{s_}")
        path = fr.arm_path(s_, sho, elb, wri, hand)[:-1]
        radii = [(a * 1.12 + 0.01, b * 1.12 + 0.01) for a, b in fr.arm_radii(1.0)[:-1]]
        radii[-1] = (radii[-1][0] + 0.006, radii[-1][1] + 0.006)          # a slightly flared sleeve end
        sl = fr.tube(f"Sleeve_{s_}", path, radii, jm, caps=False, ring=24)
        fr.skin_chain(sl, rig, [f"UpperArm_{s_}", f"Forearm_{s_}"], blend=0.05)
        add(fr.tube(f"Cuff_{s_}", [wri + (elb - wri).normalized() * 0.05, wri + (elb - wri).normalized() * 0.02],
                    [0.046, 0.044], tm, caps=False, ring=20, subdiv=1), f"Forearm_{s_}")


def build_shoulders(add, skin):
    """One continuous shoulder girdle instead of a flat plate: a loft running
    across the body (left shoulder cap -> trapezius slope -> neck base -> right),
    its top line rising from the round deltoid caps up the traps to the neck,
    deepest front-to-back over the traps, rounded at both ends where the arms
    come out. The torso's top is widened so chest and girdle blend; the separate
    trapezius blobs and the harsh collarbone tubes it replaces are removed."""
    for o in [o for o in bpy.data.objects if o.name.startswith(("Trap_", "Clavicle", "DeltLine", "BicepLine", "BicepFront",
                                                                   "ForearmLine", "ElbowCrease", "Vein_"))]:
        bpy.data.objects.remove(o)          # the scratchy arm ink strokes read as noise in the anime render
    # (the torso itself is built - and sculpted - by build_chest; nothing to rebuild here)
    # Top-line samples across the body: (|x|, top z, vertical half-size, depth half-size, y offset)
    spec = [(0.0, 1.47, 0.08, 0.07, 0.012), (0.05, 1.465, 0.078, 0.08, 0.012), (0.1, 1.45, 0.074, 0.095, 0.012),
            (0.16, 1.428, 0.068, 0.098, 0.008), (0.21, 1.408, 0.064, 0.088, 0.004), (0.25, 1.385, 0.06, 0.07, 0.0),
            (0.28, 1.355, 0.05, 0.05, 0.0)]
    pts, radii = [], []
    for sgn in (-1, 1):
        rows = spec if sgn > 0 else list(reversed(spec))
        for ax, top, rz, ry, yo in rows:
            if sgn < 0 and ax == 0.0:
                continue
            pts.append((sgn * ax, yo, top - rz))
            radii.append((rz, ry))
    pts = [pts[i] for i in sorted(range(len(pts)), key=lambda i: pts[i][0])]
    radii_sorted = []
    for x, y, z in pts:
        ax = abs(x)
        row = min(spec, key=lambda r: abs(r[0] - ax))
        radii_sorted.append((row[2], row[3]))
    add(fr.tube("Shoulders", [Vector(p) for p in pts], radii_sorted, skin, ring=24, side=Vector((0, 0, 1)), subdiv=2),
        "Spine")
    # Deltoid caps: a round ball of muscle over each shoulder joint, wider than the
    # girdle, so the shoulders read broad and strong (anime male: ~2.5 heads wide).
    for s_, sx in (("L", 1), ("R", -1)):
        sho = fr.jp(f"sho_{s_}")
        elb = fr.jp(f"elb_{s_}")
        # A teardrop that flows down the arm: full at the top of the shoulder, tapering
        # into the upper arm a third of the way to the elbow (no ball sitting on top).
        d = (elb - sho).normalized()
        path = [sho + Vector((-sx * 0.02, 0.0, 0.03)), sho + Vector((sx * 0.012, 0.0, 0.006)),
                sho + d * 0.07 + Vector((sx * 0.012, 0, 0)), sho + d * 0.14]
        add(fr.tube(f"DeltCap_{s_}", path, [(0.042, 0.05), (0.058, 0.062), (0.056, 0.06), (0.046, 0.052)], skin,
                    side=Vector((1, 0, 0)), ring=20, subdiv=2), f"UpperArm_{s_}")
    build_collarbones(add, skin)


def build_collarbones(add, skin):
    """Collarbones: an S-curved bony ridge each side, from the notch at the base of
    the throat out to the point of the shoulder - bowing forward near the middle,
    sweeping back toward the shoulder, rising slightly at its outer end. Laid on
    the real surface (ray-cast onto the girdle/torso), with an ink stroke along its
    lower edge, a faint stroke in the hollow above, and the V of the throat notch."""
    bpy.context.view_layer.update()
    bvh = _surface_bvh([o for o in (bpy.data.objects.get("Shoulders"), bpy.data.objects.get("Torso")) if o])

    def on(x, z, lift=0.0):
        """Surface point at (x, z); if the ray misses (above the shoulder line) slide down until it lands."""
        for dz in (0.0, -0.004, -0.008, -0.012, -0.016, -0.02):
            hit = bvh.ray_cast(Vector((x, -1.0, z + dz)), Vector((0, 1, 0)))
            if hit[0] is not None and hit[0].y < -0.03:          # a front-facing hit, not the top of the girdle
                return hit[0] + Vector((0, -lift, 0))
        return None

    def strip(pts):
        return [p for p in pts if p is not None]
    liner = fr.mat("liner", 0.4)
    # (x, z) along the bone: inner end by the notch -> forward bow -> outer end at the shoulder point
    line = [(0.022, 1.414), (0.05, 1.419), (0.085, 1.422), (0.12, 1.421), (0.155, 1.415), (0.185, 1.405), (0.205, 1.395)]
    for sx in (1, -1):
        bow = [0.002, 0.004, 0.0045, 0.0035, 0.002, 0.001, 0.0]          # forward bow of the S, strongest inside
        ridge = strip([on(sx * x, z, 0.004 + b) for (x, z), b in zip(line, bow)])
        if len(ridge) >= 3:
            n = len(ridge)
            add(fr.tube(f"Clavicle{sx}", ridge, [0.0045 + 0.004 * math.sin(math.pi * (i + 0.5) / n) for i in range(n)],
                        skin, subdiv=1, ring=10), "Spine")
        under = strip([on(sx * x, z - 0.009, 0.0025 + b * 0.6) for (x, z), b in zip(line, bow)])
        if len(under) >= 3:
            n = len(under)
            add(fr.tube(f"ClavLine{sx}", under, [0.0006 + 0.002 * math.sin(math.pi * (i + 0.5) / n) for i in range(n)],
                        liner, subdiv=1, ring=6), "Spine")
        hollow = strip([on(sx * x, z + 0.012, 0.0015) for x, z in ((0.06, 1.42), (0.095, 1.424), (0.13, 1.42))])
        if len(hollow) >= 2:
            add(fr.tube(f"ClavHollow{sx}", hollow, [0.0004, 0.001, 0.0004][:len(hollow)], liner, subdiv=1, ring=6), "Spine")
        notch = strip([on(sx * 0.016, 1.42, 0.003), on(sx * 0.005, 1.407, 0.003)])
        if len(notch) == 2:
            add(fr.tube(f"ClavNotch{sx}", notch, [0.0011, 0.0005], liner, subdiv=0, ring=6), "Spine")


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
    ap.add_argument("--outfit", default="vest", choices=("vest", "bare", "jacket"))
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    scene, rig, bike = build_anime(100, outfit=a.outfit)
    for o in bpy.data.objects:          # character only
        if o.name.startswith(("TopTube", "DownTube", "SeatTube", "HeadTube", "ChainStay", "SeatStay", "Fork", "Stem",
                              "Bar", "Grip", "SeatPost", "Saddle", "Cog", "Chain", "Wheel", "Tire", "Rim", "Hub",
                              "Spoke", "Crank", "Pedal")):
            o.hide_render = True
    fr.pose_stand(rig)
    pose_a(rig)
    face = fr.FaceRig(rig, "")
    head = Vector((0, -0.01, fr.HEAD_Z - 0.03))
    chest = Vector((0, 0, 1.25))
    cam = fr.camera(scene, (0, -1, 1), (0, 0, 1), lens=85)
    fr.aim(cam, head + Vector((0.35, -1.2, 0.02)), head, lens=85)
    anime_look(scene, cam, head)
    W = a.size
    shots = [("portrait_3q", "COOL", head + Vector((0.38, -1.15, 0.02)), head, 85, (W, int(W * 1.15))),
             ("torso_front", "COOL", chest + Vector((0.0, -2.2, 0.05)), chest, 60, (W, int(W * 1.1))),
             ("torso_3q", "SMUG", chest + Vector((1.2, -1.85, 0.08)), chest, 60, (W, int(W * 1.1))),
             ("torso_back", "COOL", chest + Vector((0.9, 2.0, 0.1)), chest, 60, (W, int(W * 1.1))),
             ("full_body", "COOL", Vector((0.9, -4.6, 1.05)), Vector((0, 0, 0.95)), 50, (W, int(W * 1.5)))]
    for name, expr, loc, tgt, lens, (w, h) in shots:
        face.pose(expr)
        scene.render.resolution_x, scene.render.resolution_y = w, h
        fr.aim(cam, loc, tgt, lens=lens)
        fr.shoot(scene, os.path.join(a.out, f"{a.outfit}_{name}.png"))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
