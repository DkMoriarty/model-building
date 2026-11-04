"""
Kai - toon-anime character builder for Blender (3.6 / 4.x).

Builds an original cel-shaded character with bold black outlines
(inverted-hull method), a flat cartoon city backdrop, lighting and camera.

Run inside Blender:
    Scripting tab -> Open this file -> Run Script

Or headless from a terminal:
    blender -b -P kai_toon.py -- --render kai.png
    blender -b -P kai_toon.py -- --save kai.blend --render kai.png

Render with EEVEE: the cel bands come from the "Shader to RGB" node,
which only EEVEE supports. Cycles will show soft shading instead.

Change the look in PALETTE / STYLE below; everything else follows.
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
    "skin": "#FFE0C6",
    "hair": "#2EC4B6",
    "headband": "#FFD23F",
    "hoodie": "#FF7A3D",
    "hoodie_dark": "#E8602A",
    "pants": "#2B3A67",
    "shoes": "#F4F4F4",
    "sole": "#FF4F5E",
    "eye_white": "#FFFFFF",
    "iris": "#1E7F9E",
    "pupil": "#0E2A38",
    "mouth": "#B8323A",
    "blush": "#FF9AA2",
    "string": "#FFFFFF",
    "outline": "#1C1626",
    "building": "#7A6FC4",
    "window": "#FFE27A",
    "ground": "#E9B98A",
    "sun": "#FFB25C",
    "sky": "#FFD9A8",
}

STYLE = {
    "outline_width": 0.014,   # world units; ~0.01 thin, ~0.02 chunky
    "shadow_amount": 0.72,    # 1.0 = no shadow band, lower = darker shadow
    "shadow_hue_shift": 0.06, # pushes shadows slightly cooler/purple
    "band_split": 0.45,       # where light turns to shadow (0..1)
    "highlight": True,        # third, brighter band on big shapes
    "backdrop": True,         # cartoon city behind the character
}

HEAD_C = Vector((0.0, 0.0, 1.75))
HEAD_R = 0.38


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
    name = "Toon_" + key
    if name in _MATS:
        return _MATS[name]
    base = PALETTE[key]
    hl = STYLE["highlight"] if highlight is None else highlight

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
    cr.elements[0].color = hex_rgba(base, STYLE["shadow_amount"], STYLE["shadow_hue_shift"])
    cr.elements[1].position = STYLE["band_split"]
    cr.elements[1].color = hex_rgba(base)
    if hl:
        e = cr.elements.new(0.92)
        e.color = hex_rgba(base, 1.12)

    nt.links.new(diff.outputs["BSDF"], s2r.inputs["Shader"])
    nt.links.new(s2r.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    m.diffuse_color = hex_rgba(base)  # viewport solid colour
    _MATS[name] = m
    return m


def flat_mat(key):
    """Unshaded flat colour (eyes, mouth, windows, sun)."""
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
    for attr, val in (("shadow_method", "NONE"),        # EEVEE legacy
                      ("use_backface_culling_shadow", True)):  # EEVEE Next
        try:
            setattr(m, attr, val)
        except (AttributeError, TypeError):
            pass
    _MATS["Outline"] = m
    return m


# --------------------------------------------------------------------------
# Geometry helpers (bmesh, so nothing depends on operator context)
# --------------------------------------------------------------------------
_COLL = None


def _link(obj):
    _COLL.objects.link(obj)


def finish(name, bm, mat, loc=(0, 0, 0), rot=None, outline=True, width=None, smooth=True):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)  # outward, for the outline shell
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
    _link(obj)
    return obj


def sphere(name, mat, loc, scale=(1, 1, 1), r=1.0, rot=None, seg=32, ring=16,
           outline=True, width=None, keep=None):
    bm = bmesh.new()
    S = Matrix.Diagonal((scale[0], scale[1], scale[2], 1.0))
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=r)
    if keep is not None:  # keep(vertex_co) -> bool, trims before scaling
        dead = [v for v in bm.verts if not keep(v.co)]
        bmesh.ops.delete(bm, geom=dead, context="VERTS")
    bmesh.ops.transform(bm, matrix=S, verts=bm.verts)
    return finish(name, bm, mat, loc, rot, outline, width)


def cone(name, mat, base, direction, length, r1, r2=0.0, seg=16, outline=True):
    d = Vector(direction).normalized()
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                          radius1=r1, radius2=r2, depth=length,
                          matrix=Matrix.Translation((0, 0, length / 2)))
    return finish(name, bm, mat, Vector(base), d.to_track_quat("Z", "Y"), outline)


def tube(name, mat, p1, p2, r, outline=True):
    p1, p2 = Vector(p1), Vector(p2)
    return cone(name, mat, p1, p2 - p1, (p2 - p1).length, r, r, 20, outline)


def limb(name, mat, points, r):
    """Capsule chain through points: tubes plus round joints."""
    objs = []
    for i in range(len(points) - 1):
        objs.append(tube(f"{name}_seg{i}", mat, points[i], points[i + 1], r))
    for i, p in enumerate(points):
        objs.append(sphere(f"{name}_joint{i}", mat, p, r=r, seg=20, ring=10))
    return objs


def torus(name, mat, loc, R, r, rot=None, maj=48, mnr=12, outline=True, width=None):
    bm = bmesh.new()
    rings = []
    for i in range(maj):
        a = 2 * math.pi * i / maj
        ring = []
        for j in range(mnr):
            b = 2 * math.pi * j / mnr
            x = (R + r * math.cos(b)) * math.cos(a)
            y = (R + r * math.cos(b)) * math.sin(a)
            ring.append(bm.verts.new((x, y, r * math.sin(b))))
        rings.append(ring)
    for i in range(maj):
        for j in range(mnr):
            bm.faces.new((rings[i][j], rings[(i + 1) % maj][j],
                          rings[(i + 1) % maj][(j + 1) % mnr], rings[i][(j + 1) % mnr]))
    bm.normal_update()
    return finish(name, bm, mat, loc, rot, outline, width)


def box(name, mat, loc, size, outline=True, width=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.transform(bm, matrix=Matrix.Diagonal((*size, 1.0)), verts=bm.verts)
    return finish(name, bm, mat, loc, None, outline, width, smooth=False)


def on_head(x, dz, lift=0.0):
    """Point on the front of the head sphere, and a rotation facing outward."""
    y = -math.sqrt(max(HEAD_R ** 2 - x ** 2 - dz ** 2, 1e-6))
    n = Vector((x, y, dz)).normalized()
    return HEAD_C + n * (HEAD_R + lift), n.to_track_quat("-Y", "Z")


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


def build_head():
    skin = toon_mat("skin")
    sphere("Head", skin, HEAD_C, r=HEAD_R, seg=48, ring=24)

    # Hair cap: sphere trimmed by a slanted plane (high at forehead, low at back)
    hr = 0.41
    hair_c = HEAD_C + Vector((0, 0.02, 0.03))
    sphere("Hair_cap", toon_mat("hair"), hair_c, r=hr, seg=48, ring=24,
           keep=lambda co: co.z >= -0.09 - 0.21 * (co.y / hr))

    # Spikes radiating from the cap (top, sides, back; none over the face)
    spikes = []
    for elev in (85, 60, 35, 12):
        for az in range(0, 360, 30 if elev < 80 else 120):
            n = Vector((math.cos(math.radians(elev)) * math.sin(math.radians(az)),
                        math.cos(math.radians(elev)) * math.cos(math.radians(az)),
                        math.sin(math.radians(elev))))
            if n.y < -0.25 and elev < 60:
                continue  # keep the face and fringe line clear
            if elev == 12 and n.y < 0.2:
                continue  # low ring only at the back
            spikes.append(n)
    hair = toon_mat("hair")
    for i, n in enumerate(spikes):
        tilt = (n + Vector((0, 0.25, 0.35))).normalized()  # swept up and back
        length = 0.28 + 0.08 * ((i * 7) % 3)
        cone(f"Hair_spike{i:02d}", hair, hair_c + n * hr * 0.82, tilt, length, 0.10)
    # Front fringe spikes sweeping up over the headband
    for i, x in enumerate((-0.22, -0.08, 0.08, 0.22)):
        base = hair_c + Vector((x, -0.30, 0.20))
        cone(f"Hair_fringe{i}", hair, base, (x * 0.8, -0.35, 1.0), 0.24, 0.085)

    # Headband: ring tilted so the front sits on the forehead
    torus("Headband", toon_mat("headband", False), Vector((0, 0, 1.80)), 0.40, 0.035,
          rot=Quaternion((1, 0, 0), math.radians(-11)))

    # Ears
    for s in (-1, 1):
        sphere(f"Ear_{'L' if s < 0 else 'R'}", skin, (s * 0.37, 0.02, 1.70),
               scale=(0.05, 0.08, 0.10), seg=20, ring=10)

    # Big anime eyes: white, iris, pupil, two highlights
    for s in (-1, 1):
        side = "L" if s < 0 else "R"
        ex, ez = s * 0.14, -0.07
        p, q = on_head(ex, ez, 0.0)
        sphere(f"Eye_white_{side}", flat_mat("eye_white"), p, (0.095, 0.025, 0.125),
               rot=q, seg=24, ring=12, width=0.008)
        p, q = on_head(ex + s * 0.005, ez - 0.01, 0.012)
        sphere(f"Eye_iris_{side}", flat_mat("iris"), p, (0.068, 0.02, 0.095),
               rot=q, seg=24, ring=12, outline=False)
        p, q = on_head(ex + s * 0.006, ez - 0.02, 0.022)
        sphere(f"Eye_pupil_{side}", flat_mat("pupil"), p, (0.035, 0.012, 0.052),
               rot=q, seg=16, ring=8, outline=False)
        p, q = on_head(ex - 0.025, ez + 0.035, 0.032)
        sphere(f"Eye_shine_{side}", flat_mat("eye_white"), p, (0.022, 0.01, 0.022),
               rot=q, seg=12, ring=6, outline=False)
        p, q = on_head(ex + 0.02, ez - 0.05, 0.03)
        sphere(f"Eye_shine2_{side}", flat_mat("eye_white"), p, (0.011, 0.008, 0.011),
               rot=q, seg=10, ring=5, outline=False)

        # Brows
        p, q = on_head(s * 0.15, 0.085, 0.01)
        sphere(f"Brow_{side}", flat_mat("outline"), p, (0.075, 0.012, 0.014),
               rot=q @ Quaternion((0, 1, 0), s * math.radians(8)),
               seg=16, ring=8, outline=False)

        # Blush
        p, q = on_head(s * 0.23, -0.17, 0.004)
        sphere(f"Blush_{side}", flat_mat("blush"), p, (0.05, 0.008, 0.025),
               rot=q, seg=16, ring=8, outline=False)

    # Nose and open smile (lower half of an ellipsoid -> D shape)
    p, q = on_head(0.0, -0.13, 0.0)
    sphere("Nose", skin, p, (0.02, 0.018, 0.02), rot=q, seg=12, ring=6, outline=False)
    p, q = on_head(0.0, -0.21, 0.0)
    sphere("Mouth", flat_mat("mouth"), p, (0.075, 0.02, 0.05), rot=q, seg=24, ring=12,
           width=0.008, keep=lambda co: co.z <= 0.05)


def build_body():
    skin, hood, dark = toon_mat("skin"), toon_mat("hoodie"), toon_mat("hoodie_dark", False)

    tube("Neck", skin, (0, 0.02, 1.28), (0, 0.02, 1.45), 0.085)
    sphere("Hoodie_body", hood, (0, 0, 1.0), (0.36, 0.26, 0.40))
    torus("Hood", dark, Vector((0, 0.04, 1.36)), 0.17, 0.07,
          rot=Quaternion((1, 0, 0), math.radians(12)))
    sphere("Pocket", dark, (0, -0.236, 0.86), (0.20, 0.03, 0.075), seg=24, ring=12,
           width=0.008)
    for s in (-1, 1):
        tube(f"Drawstring_{s:+d}", toon_mat("string", False),
             (s * 0.06, -0.19, 1.28), (s * 0.07, -0.25, 1.08), 0.012)
        sphere(f"Drawstring_tip_{s:+d}", toon_mat("string", False),
               (s * 0.07, -0.25, 1.07), r=0.022, seg=12, ring=6, width=0.006)

    # Arms: right arm up in a wave, left arm relaxed
    limb("Arm_R", hood, [(0.32, 0.0, 1.25), (0.55, -0.04, 1.40), (0.62, -0.06, 1.66)], 0.07)
    sphere("Hand_R", skin, (0.63, -0.07, 1.75), (0.075, 0.06, 0.09), seg=20, ring=10)
    sphere("Thumb_R", skin, (0.56, -0.09, 1.73), (0.025, 0.025, 0.04), seg=12, ring=6)
    limb("Arm_L", hood, [(-0.32, 0.0, 1.25), (-0.45, 0.0, 1.0), (-0.50, -0.02, 0.80)], 0.07)
    sphere("Hand_L", skin, (-0.51, -0.03, 0.72), (0.065, 0.06, 0.085), seg=20, ring=10)

    # Legs and shoes
    pants = toon_mat("pants")
    for s, side in ((-1, "L"), (1, "R")):
        limb(f"Leg_{side}", pants, [(s * 0.13, 0, 0.72), (s * 0.14, -0.02, 0.40),
                                    (s * 0.14, 0, 0.14)], 0.09)
        sphere(f"Shoe_{side}", toon_mat("shoes"), (s * 0.14, -0.06, 0.09),
               (0.11, 0.18, 0.085), seg=24, ring=12)
        sphere(f"Sole_{side}", toon_mat("sole", False), (s * 0.14, -0.06, 0.03),
               (0.115, 0.185, 0.03), seg=24, ring=8)


def build_backdrop():
    sphere("Ground", toon_mat("ground", False), (0, 2, -0.02), (7, 5, 0.02), seg=48, ring=8,
           outline=False)
    bmat, wmat = toon_mat("building", False), flat_mat("window")
    blocks = [(-3.6, 1.0, 3.2), (-2.6, 0.9, 4.2), (-1.7, 0.8, 2.8),
              (1.6, 0.9, 3.6), (2.5, 0.8, 4.6), (3.5, 0.9, 3.0)]
    for i, (x, w, h) in enumerate(blocks):
        y = 3.5
        box(f"Building{i}", bmat, (x, y, h / 2), (w, 0.8, h), width=0.03)
        for row in range(int(h / 0.6)):
            for col in (-1, 1):
                if (i + row + col) % 3 == 0:
                    continue
                box(f"Window{i}_{row}_{col}", wmat,
                    (x + col * w * 0.22, y - 0.41, 0.5 + row * 0.6),
                    (0.16, 0.02, 0.2), outline=False)
    sphere("Sun", flat_mat("sun"), (1.9, 6.0, 3.6), r=0.9, outline=False)


def setup_render(scene):
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1350
    scene.view_settings.view_transform = "Standard"  # keep palette colours exact
    try:
        scene.view_settings.look = "None"
    except TypeError:
        pass
    scene.render.film_transparent = False

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    # Sky colour is seen by the camera only; it does not light the scene,
    # so the sun alone decides where the cel shadow bands fall.
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
    sun.use_shadow = False  # clean cel bands, no cast-shadow noise
    key = bpy.data.objects.new("Key", sun)
    key.rotation_euler = (math.radians(50), 0, math.radians(-35))
    _link(key)

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 55
    cam = bpy.data.objects.new("Camera", cam_data)
    cam.location = (0.0, -6.2, 1.25)
    target = Vector((0.0, 0.0, 1.12))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    _link(cam)
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
    _COLL = new_collection("Kai")
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
    print(f"Kai built: {len(_COLL.objects)} objects")


if __name__ == "__main__":
    main()
