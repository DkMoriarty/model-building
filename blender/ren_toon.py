"""
Ren - adult anime character builder for Blender (3.6 / 4.x).

An original character with adult anime proportions (about 7.5 heads tall):
narrow jaw, sharp almond eyes, messy swept-back hair, long belted coat.
Cel-shaded with bold inverted-hull outlines, on a flat cartoon city.

Run inside Blender:
    Scripting tab -> Open this file -> Run Script -> F12

Or headless:
    blender -b -P ren_toon.py -- --save ren.blend --render ren.png

Render with EEVEE: the cel bands come from the "Shader to RGB" node.
Change the look in PALETTE / STYLE / CAMERA below.
"""

import math
import sys

import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

# --------------------------------------------------------------------------
# Style knobs
# --------------------------------------------------------------------------
PALETTE = {
    "skin": "#F7D9C4",
    "hair": "#232B45",
    "eye_white": "#FFFFFF",
    "iris": "#E0A100",
    "pupil": "#2A1A08",
    "line": "#1C1626",       # lashes, brows, mouth
    "coat": "#34364F",
    "coat_dark": "#25263A",
    "shirt": "#F2F0EE",
    "tie": "#C1121F",
    "belt": "#5A3E2B",
    "pants": "#3E4263",
    "boots": "#3B2A20",
    "sole": "#1C1626",
    "outline": "#1C1626",
    "building": "#7A6FC4",
    "window": "#FFE27A",
    "ground": "#E9B98A",
    "sun": "#FFB25C",
    "sky": "#FFD9A8",
}

# Hand-picked shadow colours; anything not listed gets an automatic one
PALETTE_SHADOW = {
    "skin": "#E9B49E",
}

STYLE = {
    "outline_width": 0.005,   # body outline, metres (character is 1.9 m)
    "detail_width": 0.0025,   # outline on eyes and small parts
    "shadow_amount": 0.72,    # 1.0 = no shadow band, lower = darker shadow
    "shadow_hue_shift": 0.06, # pushes shadows slightly cooler/purple
    "band_split": 0.35,       # where light turns to shadow (0..1)
    "highlight": True,        # third, brighter band on big shapes
    "backdrop": True,         # cartoon city behind the character
}

CAMERA = {"lens": 70, "location": (0.0, -4.6, 1.05), "target": (0.0, 0.0, 0.97)}

HEAD_C = Vector((0.0, 0.0, 1.72))
HEAD_A, HEAD_B, HEAD_H = 0.095, 0.11, 0.12   # half width, half depth, half height


# --------------------------------------------------------------------------
# Colour helpers
# --------------------------------------------------------------------------
def _srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgba(h, mul=1.0, cool=0.0):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    r, g, b = r * mul, g * mul, b * (mul + cool)
    r = max(0.0, r - cool * 0.5)
    return (_srgb_to_linear(min(r, 1)), _srgb_to_linear(min(g, 1)),
            _srgb_to_linear(min(b, 1)), 1.0)


# --------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------
_MATS = {}


def toon_mat(key, highlight=None):
    """Cel shader: Diffuse -> Shader to RGB -> constant ColorRamp -> Emission."""
    hl = STYLE["highlight"] if highlight is None else highlight
    name = "Toon_" + key + ("" if hl else "_flat")
    if name in _MATS:
        return _MATS[name]
    base = PALETTE[key]

    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    emit = nt.nodes.new("ShaderNodeEmission")
    diff.location, s2r.location, ramp.location = (-700, 0), (-500, 0), (-300, 0)
    emit.location, out.location = (50, 0), (250, 0)

    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    cr.elements[0].position = 0.0
    cr.elements[0].color = (hex_rgba(PALETTE_SHADOW[key]) if key in PALETTE_SHADOW else
                            hex_rgba(base, STYLE["shadow_amount"], STYLE["shadow_hue_shift"]))
    cr.elements[1].position = STYLE["band_split"]
    cr.elements[1].color = hex_rgba(base)
    if hl:
        e = cr.elements.new(0.92)
        e.color = hex_rgba(base, 1.12)

    nt.links.new(diff.outputs["BSDF"], s2r.inputs["Shader"])
    nt.links.new(s2r.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    m.diffuse_color = hex_rgba(base)
    m["palette_key"] = key
    m["toon_highlight"] = bool(hl)
    _MATS[name] = m
    return m


def flat_mat(key):
    """Unshaded flat colour (eyes, lashes, windows, sun)."""
    name = "Flat_" + key
    if name in _MATS:
        return _MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = hex_rgba(PALETTE[key])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    m.diffuse_color = hex_rgba(PALETTE[key])
    m["palette_key"] = key
    _MATS[name] = m
    return m


def outline_mat():
    if "Outline" in _MATS:
        return _MATS["Outline"]
    m = bpy.data.materials.new("Outline")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = hex_rgba(PALETTE["outline"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    m.diffuse_color = hex_rgba(PALETTE["outline"])
    m.use_backface_culling = True
    for attr, val in (("shadow_method", "NONE"),
                      ("use_backface_culling_shadow", True)):
        try:
            setattr(m, attr, val)
        except (AttributeError, TypeError):
            pass
    _MATS["Outline"] = m
    return m


# --------------------------------------------------------------------------
# Geometry helpers (bmesh only, so nothing depends on operator context)
# --------------------------------------------------------------------------
_COLL = None


def finish(name, bm, mat, loc=(0, 0, 0), rot=None, outline=True, width=None, smooth=True):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        try:
            me.shade_smooth()
        except AttributeError:
            for p in me.polygons:
                p.use_smooth = True
    obj = bpy.data.objects.new(name, me)
    obj.location = loc
    if rot is not None:
        obj.rotation_mode = "QUATERNION"
        obj.rotation_quaternion = rot
    me.materials.append(mat)
    if outline:
        me.materials.append(outline_mat())
        mod = obj.modifiers.new("Outline", "SOLIDIFY")
        mod.thickness = width if width is not None else STYLE["outline_width"]
        mod.offset = 1.0
        mod.use_flip_normals = True
        mod.use_rim = False
        mod.material_offset = 1
    _COLL.objects.link(obj)
    return obj


def sphere(name, mat, loc, scale=(1, 1, 1), r=1.0, rot=None, seg=32, ring=16,
           outline=True, width=None, keep=None, deform=None):
    """UV sphere. keep(co) trims verts, deform(co) reshapes; both see the unit sphere."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=r)
    if keep is not None:
        dead = [v for v in bm.verts if not keep(v.co)]
        bmesh.ops.delete(bm, geom=dead, context="VERTS")
    if deform is not None:
        for v in bm.verts:
            deform(v.co)
    bmesh.ops.transform(bm, matrix=Matrix.Diagonal((scale[0], scale[1], scale[2], 1.0)),
                        verts=bm.verts)
    return finish(name, bm, mat, loc, rot, outline, width)


def cone(name, mat, base, direction, length, r1, r2=0.0, seg=16, outline=True, width=None):
    d = Vector(direction).normalized()
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                          radius1=r1, radius2=r2, depth=length,
                          matrix=Matrix.Translation((0, 0, length / 2)))
    return finish(name, bm, mat, Vector(base), d.to_track_quat("Z", "Y"), outline, width)


def tube(name, mat, p1, p2, r1, r2=None):
    p1, p2 = Vector(p1), Vector(p2)
    return cone(name, mat, p1, p2 - p1, (p2 - p1).length, r1, r1 if r2 is None else r2, 20)


def limb(name, mat, points, radii):
    """Tapered capsule chain: one tube per segment, a sphere at every joint."""
    for i in range(len(points) - 1):
        tube(f"{name}_seg{i}", mat, points[i], points[i + 1], radii[i], radii[i + 1])
    for i, p in enumerate(points):
        sphere(f"{name}_joint{i}", mat, p, r=radii[i], seg=20, ring=10)


def torus(name, mat, loc, R, r, rot=None, scale=(1, 1, 1), maj=48, mnr=12,
          outline=True, width=None):
    bm = bmesh.new()
    rings = []
    for i in range(maj):
        a = 2 * math.pi * i / maj
        ring = []
        for j in range(mnr):
            b = 2 * math.pi * j / mnr
            x = (R + r * math.cos(b)) * math.cos(a) * scale[0]
            y = (R + r * math.cos(b)) * math.sin(a) * scale[1]
            ring.append(bm.verts.new((x, y, r * math.sin(b) * scale[2])))
        rings.append(ring)
    for i in range(maj):
        for j in range(mnr):
            bm.faces.new((rings[i][j], rings[(i + 1) % maj][j],
                          rings[(i + 1) % maj][(j + 1) % mnr], rings[i][(j + 1) % mnr]))
    return finish(name, bm, mat, loc, rot, outline, width)


def box(name, mat, loc, size, outline=True, width=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.transform(bm, matrix=Matrix.Diagonal((*size, 1.0)), verts=bm.verts)
    return finish(name, bm, mat, loc, None, outline, width, smooth=False)


def roll(deg):
    """Rotation in the picture plane (about the depth axis)."""
    return Quaternion((0, 1, 0), math.radians(deg))


# --------------------------------------------------------------------------
# Head shape: an ellipsoid with a tapered jaw and pointed chin
# --------------------------------------------------------------------------
def _jaw(k):
    return 1 - 0.42 * k ** 1.6


def deform_head(co):
    if co.z < 0:
        k = -co.z
        co.x *= _jaw(k)
        co.y *= (1 - 0.35 * k) if co.y > 0 else (1 - 0.08 * k)
    elif co.y > 0:
        co.y *= 1.05  # fuller skull at the back


def on_face(x, dz, lift=0.0):
    """Point on the front of the (deformed) head, and a rotation facing outward."""
    uz = max(-0.999, min(0.999, dz / HEAD_H))
    k = -uz if uz < 0 else 0.0
    ux = (x / HEAD_A) / _jaw(k)
    uy = -math.sqrt(max(1 - ux * ux - uz * uz, 1e-6)) * (1 - 0.08 * k)
    p = Vector((x, uy * HEAD_B, dz))
    n = Vector((x / HEAD_A ** 2, p.y / HEAD_B ** 2, dz / HEAD_H ** 2)).normalized()
    return HEAD_C + p + n * lift, n.to_track_quat("-Y", "Z")


# --------------------------------------------------------------------------
# Character
# --------------------------------------------------------------------------
def build_head():
    skin, W = toon_mat("skin"), STYLE["detail_width"]
    sphere("Head", skin, HEAD_C, (HEAD_A, HEAD_B, HEAD_H), seg=48, ring=32,
           deform=deform_head)
    tube("Neck", skin, (0, 0.012, 1.50), (0, 0.004, 1.64), 0.038)
    for s in (-1, 1):
        sphere(f"Ear_{s:+d}", skin, (s * 0.093, 0.012, 1.715), (0.012, 0.022, 0.033),
               seg=16, ring=10, width=W)

    # Eyes: almond whites, tall amber irises, heavy upper lash line
    for s in (-1, 1):
        ex, ez, tilt = s * 0.040, 0.0, -s * 10
        p, q = on_face(ex, ez, 0.0)
        sphere(f"Eye_white_{s:+d}", flat_mat("eye_white"), p, (0.027, 0.006, 0.016),
               rot=q @ roll(tilt), seg=24, ring=12, width=W)
        p, q = on_face(ex + s * 0.002, ez - 0.001, 0.004)
        sphere(f"Eye_iris_{s:+d}", flat_mat("iris"), p, (0.013, 0.005, 0.0165),
               rot=q, seg=20, ring=10, outline=False)
        p, q = on_face(ex + s * 0.002, ez - 0.002, 0.007)
        sphere(f"Eye_pupil_{s:+d}", flat_mat("pupil"), p, (0.0055, 0.004, 0.010),
               rot=q, seg=12, ring=8, outline=False)
        p, q = on_face(ex - 0.004, ez + 0.006, 0.009)
        sphere(f"Eye_shine_{s:+d}", flat_mat("eye_white"), p, (0.0042, 0.003, 0.0042),
               rot=q, seg=10, ring=6, outline=False)
        p, q = on_face(ex + s * 0.002, ez + 0.0145, 0.004)
        sphere(f"Lash_{s:+d}", flat_mat("line"), p, (0.031, 0.004, 0.0042),
               rot=q @ roll(tilt), seg=16, ring=8, outline=False)
        p, q = on_face(ex + s * 0.027, ez + 0.0155, 0.004)
        sphere(f"Lash_wing_{s:+d}", flat_mat("line"), p, (0.008, 0.004, 0.0028),
               rot=q @ roll(-s * 22), seg=12, ring=6, outline=False)
        p, q = on_face(ex + s * 0.003, ez - 0.0145, 0.003)
        sphere(f"Lash_low_{s:+d}", flat_mat("line"), p, (0.016, 0.003, 0.0018),
               rot=q @ roll(tilt), seg=12, ring=6, outline=False)
        p, q = on_face(s * 0.045, 0.038, 0.004)
        sphere(f"Brow_{s:+d}", flat_mat("line"), p, (0.030, 0.004, 0.0045),
               rot=q @ roll(-s * 12), seg=16, ring=8, outline=False)

    p, q = on_face(0.0, -0.030, 0.002)
    sphere("Nose", skin, p, (0.007, 0.012, 0.016), rot=q, seg=12, ring=8, outline=False)
    p, q = on_face(0.003, -0.068, 0.002)
    sphere("Mouth", flat_mat("line"), p, (0.018, 0.003, 0.0022), rot=q @ roll(-4),
           seg=12, ring=6, outline=False)

    # Hair: trimmed cap, swept-back spikes, sharp bangs, side locks
    hair = toon_mat("hair")
    hc = HEAD_C + Vector((0, 0.006, 0.008))
    ha, hb, hh = 0.103, 0.12, 0.13
    sphere("Hair_cap", hair, hc, (ha, hb, hh), seg=48, ring=24,
           keep=lambda co: co.z >= 0.05 - 0.5 * co.y)

    n_spike = 0
    for elev in (80, 55, 30, 5, -20):
        for az in range(0, 360, 90 if elev >= 80 else 30):
            n = Vector((math.cos(math.radians(elev)) * math.sin(math.radians(az)),
                        math.cos(math.radians(elev)) * math.cos(math.radians(az)),
                        math.sin(math.radians(elev))))
            if n.y < -0.3 and elev < 70:
                continue  # face stays clear
            if elev <= 5 and n.y < 0.15:
                continue  # low spikes only at the back
            sweep = Vector((0, 0.3, -0.7)) if elev <= 5 else Vector((0, 0.75, -0.1))
            base = hc + Vector((n.x * ha, n.y * hb, n.z * hh)) * 0.86
            length = 0.11 + 0.035 * ((n_spike * 5) % 3)
            cone(f"Hair_spike{n_spike:02d}", hair, base, n * 0.8 + sweep, length, 0.036)
            n_spike += 1

    for i, (x, length) in enumerate(((-0.062, 0.050), (-0.032, 0.062), (0.0, 0.070),
                                     (0.03, 0.060), (0.06, 0.048))):
        cone(f"Hair_bang{i}", hair, HEAD_C + Vector((x, -0.093, 0.088)),
             (x * 1.6, -0.28, -1.0), length, 0.022)
    for s in (-1, 1):
        cone(f"Hair_side{s:+d}", hair, (s * 0.094, -0.035, 1.785),
             (s * 0.12, -0.12, -1.0), 0.10, 0.026)


def build_body():
    coat, dark, W = toon_mat("coat"), toon_mat("coat_dark", False), STYLE["detail_width"]

    # Upper body
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32,
                          radius1=0.130, radius2=0.168, depth=0.44,
                          matrix=Matrix.Diagonal((1, 0.66, 1, 1)))
    finish("Torso", bm, coat, (0, 0.005, 1.24))
    sphere("Chest_top", coat, (0, 0.005, 1.455), (0.172, 0.112, 0.075))
    sphere("Shirt", toon_mat("shirt", False), (0, -0.104, 1.38), (0.04, 0.012, 0.125),
           width=W)
    sphere("Tie_knot", flat_mat("tie"), (0, -0.111, 1.46), (0.012, 0.006, 0.01),
           outline=False)
    sphere("Tie", toon_mat("tie", False), (0, -0.112, 1.37), (0.013, 0.005, 0.085),
           width=W)
    for s in (-1, 1):
        sphere(f"Lapel_{s:+d}", dark, (s * 0.045, -0.107, 1.40), (0.026, 0.007, 0.10),
               rot=roll(s * 20), width=W)
    torus("Collar", dark, (0, 0.012, 1.525), 0.058, 0.016, scale=(1, 1, 1.8))
    torus("Belt", toon_mat("belt", False), (0, 0.005, 1.02), 0.12, 0.014,
          scale=(1.08, 0.78, 1.0))

    # Long coat skirt: open-bottomed, slightly flattened cone
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, cap_tris=False, segments=32,
                          radius1=0.19, radius2=0.13, depth=0.60,
                          matrix=Matrix.Diagonal((1, 0.75, 1, 1)))
    finish("Coat_skirt", bm, coat, (0, 0.01, 0.72))

    # Arms hang relaxed
    for s in (-1, 1):
        sphere(f"Shoulder_{s:+d}", coat, (s * 0.178, 0.005, 1.445), r=0.05, seg=20, ring=10)
        pts = [(s * 0.19, 0.005, 1.44), (s * 0.24, 0.02, 1.17), (s * 0.27, 0.0, 0.93)]
        limb(f"Arm_{s:+d}", coat, pts, (0.046, 0.042, 0.038))
        wrist_dir = Vector(pts[2]) - Vector(pts[1])
        torus(f"Cuff_{s:+d}", dark, pts[2], 0.040, 0.010,
              rot=wrist_dir.to_track_quat("Z", "Y"))
        sphere(f"Hand_{s:+d}", toon_mat("skin"), (s * 0.276, -0.004, 0.88),
               (0.028, 0.020, 0.050), seg=20, ring=10)

    # Legs and boots
    for s in (-1, 1):
        limb(f"Leg_{s:+d}", toon_mat("pants"),
             [(s * 0.080, 0.005, 0.98), (s * 0.085, -0.005, 0.52), (s * 0.088, 0.01, 0.20)],
             (0.062, 0.048, 0.042))
        tube(f"Boot_shaft_{s:+d}", toon_mat("boots"), (s * 0.088, 0.01, 0.05),
             (s * 0.088, 0.01, 0.22), 0.047)
        sphere(f"Boot_{s:+d}", toon_mat("boots"), (s * 0.088, -0.03, 0.045),
               (0.050, 0.11, 0.050), seg=24, ring=12)
        sphere(f"Sole_{s:+d}", toon_mat("sole", False), (s * 0.088, -0.03, 0.012),
               (0.052, 0.112, 0.014), seg=24, ring=8)


def build_backdrop():
    sphere("Ground", toon_mat("ground", False), (0, 2, -0.01), (5, 4, 0.01), seg=48, ring=8,
           outline=False)
    bmat, wmat = toon_mat("building", False), flat_mat("window")
    blocks = [(-2.2, 0.8, 3.4), (-1.3, 0.7, 4.4), (-0.5, 0.6, 2.6),
              (0.6, 0.7, 3.8), (1.4, 0.6, 5.0), (2.2, 0.8, 3.0)]
    y = 3.0
    for i, (x, w, h) in enumerate(blocks):
        box(f"Building{i}", bmat, (x, y, h / 2), (w, 0.6, h), width=0.02)
        for row in range(int((h - 0.3) / 0.5)):
            for col in (-1, 1):
                if (i + row + col) % 3 == 0:
                    continue
                box(f"Window{i}_{row}_{col}", wmat,
                    (x + col * w * 0.22, y - 0.31, 0.4 + row * 0.5),
                    (0.12, 0.02, 0.16), outline=False)
    sphere("Sun", flat_mat("sun"), (0.9, 5.0, 2.3), r=0.5, outline=False)


# --------------------------------------------------------------------------
# Scene
# --------------------------------------------------------------------------
def reset_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for blocks in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                   bpy.data.cameras):
        for b in list(blocks):
            if b.users == 0:
                blocks.remove(b)


def new_collection(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(c)
    return c


def setup_render(scene):
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1350
    scene.view_settings.view_transform = "Standard"
    try:
        scene.view_settings.look = "None"
    except TypeError:
        pass
    scene.render.film_transparent = False

    # Sky colour is seen by the camera only; it does not light the scene,
    # so the sun alone decides where the cel shadow bands fall.
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    wn = world.node_tree.nodes
    wn.clear()
    sky = wn.new("ShaderNodeBackground")
    sky.inputs["Color"].default_value = hex_rgba(PALETTE["sky"])
    dark = wn.new("ShaderNodeBackground")
    dark.inputs["Color"].default_value = (0, 0, 0, 1)
    path = wn.new("ShaderNodeLightPath")
    mix = wn.new("ShaderNodeMixShader")
    wout = wn.new("ShaderNodeOutputWorld")
    wl = world.node_tree.links
    wl.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    wl.new(dark.outputs["Background"], mix.inputs[1])
    wl.new(sky.outputs["Background"], mix.inputs[2])
    wl.new(mix.outputs["Shader"], wout.inputs["Surface"])

    sun = bpy.data.lights.new("Key", "SUN")
    sun.energy = 3.0
    sun.use_shadow = False
    key = bpy.data.objects.new("Key", sun)
    key.rotation_euler = (math.radians(50), 0, math.radians(-35))
    _COLL.objects.link(key)

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = CAMERA["lens"]
    cam = bpy.data.objects.new("Camera", cam_data)
    cam.location = CAMERA["location"]
    target = Vector(CAMERA["target"])
    cam.rotation_euler = (target - Vector(CAMERA["location"])).to_track_quat("-Z", "Y").to_euler()
    _COLL.objects.link(cam)
    scene.camera = cam


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {}
    for flag in ("--render", "--save"):
        if flag in argv:
            opts[flag] = bpy.path.abspath(argv[argv.index(flag) + 1])
    return opts


def main():
    global _COLL
    reset_scene()
    _COLL = new_collection("Ren")
    build_head()
    build_body()
    if STYLE["backdrop"]:
        build_backdrop()
    setup_render(bpy.context.scene)

    opts = parse_args()
    if "--save" in opts:
        bpy.ops.wm.save_as_mainfile(filepath=opts["--save"])
    if "--render" in opts:
        bpy.context.scene.render.filepath = opts["--render"]
        bpy.ops.render.render(write_still=True)
    print(f"Ren built: {len(_COLL.objects)} objects")


if __name__ == "__main__":
    main()
