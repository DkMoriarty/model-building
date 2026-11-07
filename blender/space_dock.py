"""
Space Dock - interstellar departure and docking scene for Blender (3.6 / 4.x).

Builds and animates a full 30-second sequence (720 frames at 24 fps):

  1-240    Passengers walk out of the gate tunnel, cross the landing pad
           of an orbital station and board a shuttle up its rear ramp.
  240-320  Ramp closes, engines ignite, lift-off, landing gear retracts.
  320-600  The shuttle leaves the station and flies about 2.4 km
           to a 1 km-long mothership, banking on the way.
  600-720  Final approach: the shuttle docks nose-first into the
           mothership's docking collar, clamps close, lights go green.

Environment: procedural starfield and nebula, a planet with atmosphere,
a distant star, and bloom on all lights. Five cameras switch automatically.

Detail: panel-line hull shaders, thousands of greebles, window strips,
running lights, antennas, solar arrays, landing-pad markings.

Run inside Blender:
    Scripting tab -> Open this file -> Run Script -> Space to play,
    Ctrl+F12 to render the animation, F12 for a still.

Headless:
    blender -b -P space_dock.py -- --save space_dock.blend
    blender -b -P space_dock.py -- --render-frame 560 --out shot.png
    blender -b -P space_dock.py -- --render-anim --out //render/frame_

Built for EEVEE. Cycles works too (slower, more realistic light).
"""

import math
import random
import sys

import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

FPS = 24
FRAME_END = 720
SEED = 7

# Key places (metres, Z up)
STATION = Vector((0, 0, 0))
PAD_TOP_Z = 0.0
RING_Z = 60.0                                 # habitat ring height: well above the departure lane
SHUTTLE_REST = Vector((0, -145, 3.6))          # on the pad, nose pointing -Y
MOTHERSHIP = Vector((0, -2600, 200))
DOCK_LOCAL = Vector((0, 168, -40))            # docking collar, mothership space
SHUTTLE_DOCKED = MOTHERSHIP + DOCK_LOCAL + Vector((0, 17.5, 0))

COLORS = {
    "shuttle_hull": "#C9CED6", "shuttle_panel": "#B4BAC4", "shuttle_line": "#5A616C",
    "accent": "#E8602A", "dark_metal": "#2B2F36", "glass": "#0E1B2B",
    "mother_hull": "#5A6270", "mother_panel": "#4C5361", "mother_line": "#262A31",
    "station_hull": "#D8DCE2", "station_panel": "#C4C9D1", "station_line": "#6A707A",
    "pad": "#3A3F47", "pad_line": "#1E2126", "solar": "#1B2A4A",
    "window": "#FFC874", "engine": "#7FD4FF", "nav_red": "#FF2A2A",
    "nav_green": "#2AFF6A", "strobe": "#FFFFFF", "pad_mark": "#FFC21A",
    "hangar": "#9AD8FF", "dock_red": "#FF3030", "dock_green": "#30FF70",
}

PASSENGER_SUITS = ["#E8602A", "#2EC4B6", "#F4F4F4", "#FFD23F",
                   "#7A6FC4", "#FF4F5E", "#3A86FF", "#8AC926"]


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def srgb(h, a=1.0):
    h = h.lstrip("#")
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4)) + (a,)


def set_input(node, names, value):
    for n in names:
        sock = node.inputs.get(n)
        if sock is not None:
            sock.default_value = value
            return sock
    return None


_COLL = {}


def coll(name):
    if name not in _COLL:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
        _COLL[name] = c
    return _COLL[name]


def link(obj, collection):
    coll(collection).objects.link(obj)
    return obj


def empty(name, loc=(0, 0, 0), collection="Scene", parent=None):
    o = bpy.data.objects.new(name, None)
    o.location = loc
    if parent is not None:
        o.parent = parent
    return link(o, collection)


# --------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------
_MATS = {}


def _new_mat(name, preview, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    m.diffuse_color = srgb(preview)
    m["preview"] = preview          # used by the test renderer only
    m["emit"] = float(emit)
    _MATS[name] = m
    return m


def hull_mat(name, base, panel, line, scale, metallic=0.6, rough=0.42):
    """Painted metal with two layers of panel lines (Brick textures) and bump."""
    if name in _MATS:
        return _MATS[name]
    m = _new_mat(name, base)
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    tc = N.new("ShaderNodeTexCoord")
    big = N.new("ShaderNodeTexBrick")
    small = N.new("ShaderNodeTexBrick")
    noise = N.new("ShaderNodeTexNoise")
    rr = N.new("ShaderNodeValToRGB")
    mx = N.new("ShaderNodeMath")
    bump = N.new("ShaderNodeBump")
    out.location, bsdf.location = (600, 0), (300, 0)

    for b, s, ms in ((big, scale, 0.012), (small, scale * 3.1, 0.02)):
        L.new(tc.outputs["Object"], b.inputs["Vector"])
        b.inputs["Scale"].default_value = s
        b.inputs["Mortar Size"].default_value = ms
        b.inputs["Color1"].default_value = srgb(base)
        b.inputs["Color2"].default_value = srgb(panel)
        b.inputs["Mortar"].default_value = srgb(line)
    big.offset = 0.37
    small.offset = 0.5

    L.new(big.outputs["Color"], bsdf.inputs["Base Color"])
    mx.operation = "MAXIMUM"
    L.new(big.outputs["Fac"], mx.inputs[0])
    L.new(small.outputs["Fac"], mx.inputs[1])
    bump.inputs["Strength"].default_value = 0.35
    L.new(mx.outputs["Value"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    L.new(tc.outputs["Object"], noise.inputs["Vector"])
    noise.inputs["Scale"].default_value = scale * 0.6
    rr.color_ramp.elements[0].color = (rough - 0.12,) * 3 + (1,)
    rr.color_ramp.elements[1].color = (rough + 0.15,) * 3 + (1,)
    L.new(noise.outputs["Fac"], rr.inputs["Fac"])
    L.new(rr.outputs["Color"], bsdf.inputs["Roughness"])

    bsdf.inputs["Metallic"].default_value = metallic
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def plain_mat(name, color, metallic=0.2, rough=0.5):
    if name in _MATS:
        return _MATS[name]
    m = _new_mat(name, color)
    N = m.node_tree.nodes
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = srgb(color)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    m.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def glass_mat(name, color):
    if name in _MATS:
        return _MATS[name]
    m = _new_mat(name, color, 0.4)
    N = m.node_tree.nodes
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = srgb(color)
    bsdf.inputs["Metallic"].default_value = 0.9
    bsdf.inputs["Roughness"].default_value = 0.04
    set_input(bsdf, ("Emission Color", "Emission"), srgb("#4FA3D9"))
    set_input(bsdf, ("Emission Strength",), 0.4)
    m.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def emit_mat(name, color, strength):
    """Pure light. Returns the material; its Emission node is m['node']."""
    if name in _MATS:
        return _MATS[name]
    m = _new_mat(name, color, strength)
    N = m.node_tree.nodes
    out = N.new("ShaderNodeOutputMaterial")
    em = N.new("ShaderNodeEmission")
    em.name = "Emission"
    em.inputs["Color"].default_value = srgb(color)
    em.inputs["Strength"].default_value = strength
    m.node_tree.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def glow_shell_mat(name, color, strength, edge=True):
    """Emission that fades at the silhouette (plumes) or at the centre (atmosphere)."""
    if name in _MATS:
        return _MATS[name]
    m = _new_mat(name, color, strength * 0.5)
    N, L = m.node_tree.nodes, m.node_tree.links
    out = N.new("ShaderNodeOutputMaterial")
    lw = N.new("ShaderNodeLayerWeight")
    ramp = N.new("ShaderNodeValToRGB")
    tr = N.new("ShaderNodeBsdfTransparent")
    em = N.new("ShaderNodeEmission")
    mix = N.new("ShaderNodeMixShader")
    em.name = "Emission"
    em.inputs["Color"].default_value = srgb(color)
    em.inputs["Strength"].default_value = strength
    lw.inputs["Blend"].default_value = 0.4
    # Facing is 0 where the surface faces the camera, 1 at the silhouette
    a, b = ((0, 0, 0, 1), (1, 1, 1, 1)) if edge else ((1, 1, 1, 1), (0, 0, 0, 1))
    ramp.color_ramp.elements[0].color = a
    ramp.color_ramp.elements[1].color = b
    L.new(lw.outputs["Facing"], ramp.inputs["Fac"])
    L.new(ramp.outputs["Color"], mix.inputs["Fac"])
    L.new(tr.outputs["BSDF"], mix.inputs[1])
    L.new(em.outputs["Emission"], mix.inputs[2])
    L.new(mix.outputs["Shader"], out.inputs["Surface"])
    for attr, val in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED"),
                      ("shadow_method", "NONE")):
        try:
            setattr(m, attr, val)
        except (AttributeError, TypeError):
            pass
    return m


def plume_mat(name, color, strength):
    """Additive see-through exhaust: white-hot at the nozzle, engine colour further out,
    faded to nothing before the tip and soft at the silhouette. Uses Generated Z, which
    runs 0 at the nozzle to 1 at the tip on the cones built by cone()."""
    if name in _MATS:
        return _MATS[name]
    m = _new_mat(name, color, strength * 0.5)
    N, L = m.node_tree.nodes, m.node_tree.links
    out = N.new("ShaderNodeOutputMaterial")
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Generated"], sep.inputs[0])
    # Length fade: 1 at the nozzle, gone by 75% of the length
    lr = N.new("ShaderNodeValToRGB")
    lr.color_ramp.interpolation = "EASE"
    e = lr.color_ramp.elements
    e[0].position, e[0].color = 0.0, (1, 1, 1, 1)
    e[1].position, e[1].color = 0.75, (0, 0, 0, 1)
    mid = e.new(0.2)
    mid.color = (0.18, 0.18, 0.18, 1)
    L.new(sep.outputs["Z"], lr.inputs["Fac"])
    # Core fade: bright where the surface faces the camera, soft to 0 at the silhouette
    lw = N.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.interpolation = "EASE"
    c = cr.color_ramp.elements
    c[0].position, c[0].color = 0.0, (1, 1, 1, 1)
    c[1].position, c[1].color = 0.85, (0, 0, 0, 1)
    L.new(lw.outputs["Facing"], cr.inputs["Fac"])
    mul = N.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    L.new(lr.outputs["Color"], mul.inputs[0])
    L.new(cr.outputs["Color"], mul.inputs[1])
    st = N.new("ShaderNodeMath")
    st.operation = "MULTIPLY"
    st.inputs[1].default_value = strength
    L.new(mul.outputs[0], st.inputs[0])
    # Colour: white-hot near the nozzle, engine colour further out
    pw = N.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 3.0
    L.new(lr.outputs["Color"], pw.inputs[0])
    try:  # Blender 3.4+: generic Mix node
        cm = N.new("ShaderNodeMix")
        cm.data_type = "RGBA"
        a_in, b_in, fac_in, res = cm.inputs[6], cm.inputs[7], cm.inputs[0], cm.outputs[2]
    except RuntimeError:  # older: MixRGB
        cm = N.new("ShaderNodeMixRGB")
        a_in, b_in, fac_in, res = cm.inputs[1], cm.inputs[2], cm.inputs[0], cm.outputs[0]
    a_in.default_value = srgb(color)
    b_in.default_value = (1, 1, 1, 1)
    L.new(pw.outputs[0], fac_in)
    em = N.new("ShaderNodeEmission")
    em.name = "Emission"
    L.new(res, em.inputs["Color"])
    L.new(st.outputs[0], em.inputs["Strength"])
    tr = N.new("ShaderNodeBsdfTransparent")
    add = N.new("ShaderNodeAddShader")
    L.new(tr.outputs["BSDF"], add.inputs[0])
    L.new(em.outputs["Emission"], add.inputs[1])
    L.new(add.outputs["Shader"], out.inputs["Surface"])
    for attr, val in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED"),
                      ("shadow_method", "NONE"), ("show_transparent_back", False),
                      ("use_transparency_overlap", False)):
        try:
            setattr(m, attr, val)
        except (AttributeError, TypeError):
            pass
    return m


def planet_mat():
    m = _new_mat("Planet", "#2F6B8F")
    N, L = m.node_tree.nodes, m.node_tree.links
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    tc = N.new("ShaderNodeTexCoord")
    noise = N.new("ShaderNodeTexNoise")
    ramp = N.new("ShaderNodeValToRGB")
    L.new(tc.outputs["Object"], noise.inputs["Vector"])
    noise.inputs["Scale"].default_value = 0.00035
    noise.inputs["Detail"].default_value = 12
    cr = ramp.color_ramp
    stops = [(0.0, "#0B2545"), (0.46, "#1B4F72"), (0.5, "#3C6E47"),
             (0.58, "#8C7A4B"), (0.66, "#C9B98F"), (0.72, "#F2F4F7")]
    cr.elements[0].position, cr.elements[0].color = stops[0][0], srgb(stops[0][1])
    cr.elements[1].position, cr.elements[1].color = stops[1][0], srgb(stops[1][1])
    for p, c in stops[2:]:
        e = cr.elements.new(p)
        e.color = srgb(c)
    L.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    L.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.7
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


# --------------------------------------------------------------------------
# Mesh builders (bmesh only)
# --------------------------------------------------------------------------
def mesh_obj(name, bm, mat, collection, loc=(0, 0, 0), rot=None, parent=None, smooth=False):
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
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    o.location = loc
    if rot is not None:
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = rot
    if parent is not None:
        o.parent = parent
    return link(o, collection)


def add_box(bm, center, size):
    M = Matrix.Translation(center) @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
    bmesh.ops.create_cube(bm, size=1.0, matrix=M)


def box(name, mat, collection, center, size, parent=None):
    bm = bmesh.new()
    add_box(bm, center, size)
    return mesh_obj(name, bm, mat, collection, parent=parent)


def sphere(name, mat, collection, loc, r, scale=(1, 1, 1), seg=32, ring=16, parent=None,
           keep=None, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=1.0)
    if keep is not None:
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not keep(v.co)], context="VERTS")
    bmesh.ops.transform(bm, matrix=Matrix.Diagonal((r * scale[0], r * scale[1], r * scale[2], 1)),
                        verts=bm.verts)
    return mesh_obj(name, bm, mat, collection, loc, parent=parent, smooth=smooth)


def cone(name, mat, collection, base, direction, length, r1, r2=0.0, seg=24, parent=None,
         cap=True, smooth=True):
    """Cone/cylinder from base along direction. Object origin = base, local Z = axis."""
    d = Vector(direction).normalized()
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=seg, radius1=r1,
                          radius2=r2, depth=length, matrix=Matrix.Translation((0, 0, length / 2)))
    return mesh_obj(name, bm, mat, collection, Vector(base), d.to_track_quat("Z", "Y"),
                    parent, smooth)


def tube(name, mat, collection, a, b, r, parent=None, seg=16):
    a, b = Vector(a), Vector(b)
    return cone(name, mat, collection, a, b - a, (b - a).length, r, r, seg, parent)


def torus(name, mat, collection, loc, R, r, rot=None, maj=64, mnr=16, parent=None):
    bm = bmesh.new()
    rings = []
    for i in range(maj):
        a = 2 * math.pi * i / maj
        ring = []
        for j in range(mnr):
            b = 2 * math.pi * j / mnr
            ring.append(bm.verts.new(((R + r * math.cos(b)) * math.cos(a),
                                      (R + r * math.cos(b)) * math.sin(a), r * math.sin(b))))
        rings.append(ring)
    for i in range(maj):
        for j in range(mnr):
            bm.faces.new((rings[i][j], rings[(i + 1) % maj][j],
                          rings[(i + 1) % maj][(j + 1) % mnr], rings[i][(j + 1) % mnr]))
    return mesh_obj(name, bm, mat, collection, loc, rot, parent, smooth=True)


def prism(name, mat, collection, pts, parent=None):
    """8-point hexahedron: 4 root corners then 4 tip corners (LE-top, TE-top, TE-bot, LE-bot)."""
    bm = bmesh.new()
    v = [bm.verts.new(p) for p in pts]
    for f in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        bm.faces.new([v[i] for i in f])
    return mesh_obj(name, bm, mat, collection, parent=parent)


# Lofted hulls: superellipse cross-sections along an axis ---------------------
def _superellipse(n, e):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        pts.append((math.copysign(abs(c) ** (2 / e), c), math.copysign(abs(s) ** (2 / e), s)))
    return pts


def loft(name, mat, collection, sections, axis="Y", n=32, e=2.6, parent=None):
    """sections: (station, half_width, half_height, z_centre). axis 'Y' or 'X'."""
    bm = bmesh.new()
    prof = _superellipse(n, e)
    rings = []
    for s, w, h, zc in sections:
        ring = []
        for u, v in prof:
            p = (u * w, s, zc + v * h) if axis == "Y" else (s, u * w, zc + v * h)
            ring.append(bm.verts.new(p))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    return mesh_obj(name, bm, mat, collection, parent=parent, smooth=True)


def section_at(sections, s):
    for (s0, w0, h0, z0), (s1, w1, h1, z1) in zip(sections, sections[1:]):
        if s0 <= s <= s1:
            t = (s - s0) / (s1 - s0)
            return w0 + (w1 - w0) * t, h0 + (h1 - h0) * t, z0 + (z1 - z0) * t
    return sections[-1][1:]


def top_z(w, h, zc, lat, e):
    return zc + h * max(0.0, 1 - abs(lat / w) ** e) ** (1 / e)


def side_y(w, h, zc, z, e):
    return w * max(0.0, 1 - abs((z - zc) / h) ** e) ** (1 / e)


# --------------------------------------------------------------------------
# Environment: sky, planet, star, sun
# --------------------------------------------------------------------------
def build_world(scene):
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    N, L = world.node_tree.nodes, world.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputWorld")
    tc = N.new("ShaderNodeTexCoord")
    vor = N.new("ShaderNodeTexVoronoi")
    star_map = N.new("ShaderNodeMapRange")
    twinkle = N.new("ShaderNodeTexNoise")
    mul = N.new("ShaderNodeMath")
    neb = N.new("ShaderNodeTexNoise")
    neb_ramp = N.new("ShaderNodeValToRGB")
    bg_stars = N.new("ShaderNodeBackground")
    bg_neb = N.new("ShaderNodeBackground")
    add = N.new("ShaderNodeAddShader")

    # Stars: tiny Voronoi cells on the view direction, brightness varied by noise
    L.new(tc.outputs["Generated"], vor.inputs["Vector"])
    vor.inputs["Scale"].default_value = 520
    L.new(vor.outputs["Distance"], star_map.inputs["Value"])
    star_map.inputs["From Min"].default_value = 0.0
    star_map.inputs["From Max"].default_value = 0.045
    star_map.inputs["To Min"].default_value = 1.0
    star_map.inputs["To Max"].default_value = 0.0
    L.new(tc.outputs["Generated"], twinkle.inputs["Vector"])
    twinkle.inputs["Scale"].default_value = 40
    mul.operation = "MULTIPLY"
    L.new(star_map.outputs["Result"], mul.inputs[0])
    L.new(twinkle.outputs["Fac"], mul.inputs[1])
    L.new(mul.outputs["Value"], bg_stars.inputs["Strength"])
    bg_stars.inputs["Color"].default_value = (1, 1, 1, 1)

    # Nebula: soft coloured noise clouds
    L.new(tc.outputs["Generated"], neb.inputs["Vector"])
    neb.inputs["Scale"].default_value = 1.6
    neb.inputs["Detail"].default_value = 10
    cr = neb_ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.42, (0, 0, 0, 1)
    cr.elements[1].position, cr.elements[1].color = 0.75, srgb("#7A2E8A")
    e = cr.elements.new(0.62)
    e.color = srgb("#14324F")
    L.new(neb.outputs["Fac"], neb_ramp.inputs["Fac"])
    L.new(neb_ramp.outputs["Color"], bg_neb.inputs["Color"])
    bg_neb.inputs["Strength"].default_value = 0.35

    L.new(bg_stars.outputs["Background"], add.inputs[0])
    L.new(bg_neb.outputs["Background"], add.inputs[1])
    L.new(add.outputs["Shader"], out.inputs["Surface"])


STAR_POS = Vector((42000, 70000, 26000))      # behind the cameras: lights the docking flank
PLANET_POS = Vector((-9000, -32000, -11000))


def build_environment():
    C = "Environment"
    sphere("Planet", planet_mat(), C, PLANET_POS, 12000, seg=96, ring=48)
    sphere("Planet_atmosphere", glow_shell_mat("Atmosphere", "#6FB7FF", 4.0, edge=True), C,
           PLANET_POS, 12450, seg=96, ring=48)
    sphere("Moon", plain_mat("Moon", "#9A9AA0", 0, 0.9), C,
           PLANET_POS + Vector((17000, 9000, 6500)), 1800, seg=48, ring=24)
    sphere("Star", emit_mat("Star", "#FFF1D6", 60), C, STAR_POS, 1500, seg=32, ring=16)
    sphere("Star_corona", glow_shell_mat("Corona", "#FFB36B", 8, edge=False), C,
           STAR_POS, 2600, seg=32, ring=16)

    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = 4.5
    sun_data.color = (1.0, 0.95, 0.88)
    try:
        sun_data.angle = math.radians(0.6)
    except AttributeError:
        pass
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_mode = "QUATERNION"
    sun.rotation_quaternion = (-STAR_POS).normalized().to_track_quat("-Z", "Y")
    link(sun, C)

    fill = bpy.data.lights.new("Planet_bounce", "SUN")
    fill.energy = 0.35
    fill.color = (0.45, 0.65, 1.0)
    fill.use_shadow = False
    f = bpy.data.objects.new("Planet_bounce", fill)
    f.rotation_mode = "QUATERNION"
    f.rotation_quaternion = (-PLANET_POS).normalized().to_track_quat("-Z", "Y")
    link(f, C)


# --------------------------------------------------------------------------
# Orbital station with landing pad
# --------------------------------------------------------------------------
def build_station(rng):
    C = "Station"
    root = empty("Station", STATION, C)
    hull = hull_mat("Station_hull", COLORS["station_hull"], COLORS["station_panel"],
                    COLORS["station_line"], 0.35)
    dark = plain_mat("Dark_metal", COLORS["dark_metal"], 0.8, 0.35)
    win = emit_mat("Windows", COLORS["window"], 6)

    # Hub
    cone("Hub", hull, C, (0, 0, -80), (0, 0, 1), 160, 40, 40, 48, root)
    cone("Hub_cap_top", hull, C, (0, 0, 80), (0, 0, 1), 18, 40, 22, 48, root)
    cone("Hub_cap_bottom", hull, C, (0, 0, -80), (0, 0, -1), 18, 40, 22, 48, root)
    tube("Spire", dark, C, (0, 0, 98), (0, 0, 160), 1.2, root)
    sphere("Spire_light", emit_mat("Strobe", COLORS["strobe"], 0), C, (0, 0, 161), 1.6, parent=root)

    # Rotating habitat ring with spokes and solar arrays
    ring = empty("Station_ring", STATION, C)
    torus("Habitat_ring", hull, C, (0, 0, RING_Z), 180, 14, maj=128, mnr=20, parent=ring)
    bm = bmesh.new()
    for i in range(128 * 3):  # window lights around the ring
        a = 2 * math.pi * i / (128 * 3)
        if rng.random() < 0.35:
            continue
        p = Vector((math.cos(a) * 193.5, math.sin(a) * 193.5, RING_Z + rng.choice((-4, 0, 4))))
        add_box(bm, p, (1.2, 1.2, 1.4))
    mesh_obj("Habitat_windows", bm, win, C, parent=ring)
    for k in range(6):
        a = 2 * math.pi * k / 6
        d = Vector((math.cos(a), math.sin(a), 0))
        tube(f"Spoke{k}", dark, C, d * 38 + Vector((0, 0, RING_Z)), d * 168 + Vector((0, 0, RING_Z)), 3.2, ring)
        for side in (-1, 1):
            c = d * 110 + Vector((0, 0, RING_Z + side * 22))
            pm = box(f"Solar{k}_{side}", plain_mat("Solar", COLORS["solar"], 0.6, 0.15), C, c,
                     (abs(d.x) * 70 + abs(d.y) * 2 + 2, abs(d.y) * 70 + abs(d.x) * 2 + 2, 0.4), ring)

    # Hub greebles and window bands
    bm, bw = bmesh.new(), bmesh.new()
    for _ in range(900):
        a = rng.uniform(0, 2 * math.pi)
        z = rng.uniform(-75, 75)
        size = (rng.uniform(1, 6), rng.uniform(1, 6), rng.uniform(1, 8))
        add_box(bm, (math.cos(a) * 40.5, math.sin(a) * 40.5, z), size)
    for band in (-50, -20, 45):
        for i in range(160):
            a = 2 * math.pi * i / 160
            if rng.random() < 0.25:
                continue
            add_box(bw, (math.cos(a) * 40.3, math.sin(a) * 40.3, band), (1.0, 1.0, 1.6))
    mesh_obj("Hub_greebles", bm, hull, C, parent=root)
    mesh_obj("Hub_windows", bw, win, C, parent=root)

    # Docking arm and landing pad (top at z = 0)
    box("Arm", hull, C, (0, -75, -2), (16, 70, 8), root)
    tube("Arm_pipe_L", dark, C, (-9, -38, -4), (-9, -110, -4), 1.2, root)
    tube("Arm_pipe_R", dark, C, (9, -38, -4), (9, -110, -4), 1.2, root)
    pad_mat = hull_mat("Pad", COLORS["pad"], "#343840", COLORS["pad_line"], 0.25, 0.4, 0.6)
    box("Pad", pad_mat, C, (0, -140, -1.5), (70, 60, 3), root)
    box("Pad_under", dark, C, (0, -140, -6), (50, 44, 6), root)
    for sx in (-1, 1):
        tube(f"Pad_strut{sx}", dark, C, (sx * 6, -100, -6), (sx * 22, -158, -8), 1.5, root)

    # Pad markings: landing circle and taxi lines, glowing yellow
    mark = emit_mat("Pad_marking", COLORS["pad_mark"], 4)
    bm = bmesh.new()
    for i in range(48):
        a = 2 * math.pi * i / 48
        if i % 2:
            continue
        add_box(bm, (math.cos(a) * 14, -145 + math.sin(a) * 14, 0.03), (1.6, 1.6, 0.06))
    for y in range(-168, -113, 4):
        add_box(bm, (-4.5, y, 0.03), (0.3, 2.4, 0.06))
        add_box(bm, (4.5, y, 0.03), (0.3, 2.4, 0.06))
    mesh_obj("Pad_markings", bm, mark, C, parent=root)

    # Edge lights: alternate red/green around the pad rim
    br, bg = bmesh.new(), bmesh.new()
    for i, x in enumerate(range(-34, 35, 4)):
        for y in (-110.5, -169.5):
            add_box(br if (i % 2) else bg, (x, y, 0.4), (0.6, 0.6, 0.8))
    for i, y in enumerate(range(-168, -111, 4)):
        for x in (-34.5, 34.5):
            add_box(br if (i % 2) else bg, (x, y, 0.4), (0.6, 0.6, 0.8))
    mesh_obj("Pad_lights_red", br, emit_mat("Nav_red", COLORS["nav_red"], 12), C, parent=root)
    mesh_obj("Pad_lights_green", bg, emit_mat("Nav_green", COLORS["nav_green"], 12), C, parent=root)

    # Boarding gate: open arch with a glass canopy, joined to the arm by a tunnel
    gate_glass = glass_mat("Gate_glass", "#16324A")
    box("Gate_canopy", gate_glass, C, (0, -118.5, 3.45), (5.6, 7, 0.15), root)
    for x in (-2.6, 2.6):
        box(f"Gate_rail{x:+.0f}", emit_mat("Gate_frame", "#9AD8FF", 10), C,
            (x, -117.5, 1.0), (0.12, 7, 0.12), root)
    frame = emit_mat("Gate_frame", "#9AD8FF", 10)
    for x in (-2.6, 2.6):
        box(f"Gate_post{x:+.0f}", frame, C, (x, -122.1, 1.6), (0.25, 0.25, 3.3), root)
    box("Gate_lintel", frame, C, (0, -122.1, 3.3), (5.4, 0.25, 0.25), root)
    tube("Gate_tunnel", hull, C, (0, -112, 1.6), (0, -119, 1.6), 2.2, root)

    # Service gantry beside the pad
    for z in range(0, 18, 3):
        box(f"Gantry_deck{z}", dark, C, (-22, -140, z + 0.2), (6, 8, 0.4), root)
    for dx in (-2.8, 2.8):
        for dy in (-3.8, 3.8):
            tube(f"Gantry_leg{dx:+.0f}{dy:+.0f}", dark, C, (-22 + dx, -140 + dy, 0),
                 (-22 + dx, -140 + dy, 18), 0.25, root)
    sphere("Gantry_beacon", emit_mat("Strobe", COLORS["strobe"], 0), C, (-22, -140, 18.8), 0.6,
           parent=root)

    # Flood lights so EEVEE has local light on the pad
    for i, (x, y) in enumerate(((-30, -115), (30, -115), (-30, -165), (30, -165))):
        ld = bpy.data.lights.new(f"Pad_flood{i}", "POINT")
        ld.energy = 25000
        ld.color = (0.85, 0.92, 1.0)
        try:
            ld.shadow_soft_size = 2.0
        except AttributeError:
            pass
        lo = bpy.data.objects.new(f"Pad_flood{i}", ld)
        lo.location = (x, y, 14)
        link(lo, C)
    return ring


# --------------------------------------------------------------------------
# Shuttle (32 m, nose +Y in its own space)
# --------------------------------------------------------------------------
SHUTTLE_SECTIONS = [(-16, 2.6, 2.0, 0.3), (-12, 3.0, 2.4, 0.2), (-6, 3.2, 2.6, 0.0),
                    (0, 3.2, 2.6, 0.0), (6, 2.9, 2.3, -0.1), (11, 2.2, 1.7, -0.3),
                    (14, 1.4, 1.1, -0.4), (16, 0.35, 0.3, -0.5)]
RAMP_HINGE = Vector((0, -15.5, -1.6))
RAMP_LEN = 5.0
RAMP_OPEN = math.radians(23.6)     # end rests on the pad
RAMP_CLOSED = math.radians(-90)


def build_shuttle(rng):
    C = "Shuttle"
    ship = empty("Shuttle", (0, 0, 0), C)
    hull = hull_mat("Shuttle_hull", COLORS["shuttle_hull"], COLORS["shuttle_panel"],
                    COLORS["shuttle_line"], 0.9, 0.55, 0.38)
    accent = hull_mat("Shuttle_accent", COLORS["accent"], "#D45524", "#7A2E12", 0.9, 0.3, 0.4)
    dark = plain_mat("Dark_metal", COLORS["dark_metal"], 0.8, 0.35)
    e = 2.6

    loft("Shuttle_fuselage", hull, C, SHUTTLE_SECTIONS, "Y", 40, e, ship)

    # Cockpit canopy (upper half of a squashed sphere)
    sphere("Shuttle_canopy", glass_mat("Canopy", COLORS["glass"]), C, (0, 9.2, 1.45), 1.0,
           (1.45, 3.4, 0.95), 32, 16, ship, keep=lambda co: co.z > -0.15)

    # Delta wings with accent tips and wingtip fins
    for s in (-1, 1):
        pts = [(s * 2.9, 4.0, 0.0), (s * 2.9, -11.0, 0.0), (s * 2.9, -11.0, -0.7), (s * 2.9, 4.0, -0.7),
               (s * 12.5, -7.0, -0.35), (s * 12.5, -12.5, -0.35), (s * 12.5, -12.5, -0.6),
               (s * 12.5, -7.0, -0.6)]
        prism(f"Wing{s:+d}", hull, C, pts, ship)
        tip = [(s * 12.4, -7.2, -0.3), (s * 12.4, -12.6, -0.3), (s * 12.4, -12.6, -0.65),
               (s * 12.4, -7.2, -0.65), (s * 13.1, -9.4, 2.4), (s * 13.1, -12.8, 2.4),
               (s * 13.1, -12.8, 2.1), (s * 13.1, -9.4, 2.1)]
        prism(f"Wing_fin{s:+d}", accent, C, tip, ship)
        nav = emit_mat("Nav_red" if s < 0 else "Nav_green",
                       COLORS["nav_red"] if s < 0 else COLORS["nav_green"], 12)
        sphere(f"Nav_light{s:+d}", nav, C, (s * 13.15, -9.4, 2.55), 0.18, parent=ship)

        # Canted tail fins
        cant = s * 0.32
        fin = [(s * 1.6, -9.0, 1.9), (s * 1.6, -15.8, 1.9), (s * 1.9, -15.8, 1.9), (s * 1.9, -9.0, 1.9),
               (s * (1.6 + 4 * cant), -13.4, 6.0), (s * (1.6 + 4 * cant), -16.4, 6.0),
               (s * (1.8 + 4 * cant), -16.4, 6.0), (s * (1.8 + 4 * cant), -13.4, 6.0)]
        prism(f"Tail_fin{s:+d}", accent, C, [fin[0], fin[1], fin[2], fin[3], fin[4], fin[5], fin[6], fin[7]], ship)

        # Engine nacelles with nozzle, glowing core and exhaust plume
        x = s * 4.6
        cone(f"Nacelle{s:+d}", hull, C, (x, -16.0, 0.0), (0, 1, 0), 10, 1.35, 1.1, 32, ship)
        cone(f"Nacelle_intake{s:+d}", dark, C, (x, -6.0, 0.0), (0, 1, 0), 1.2, 1.1, 0.75, 32, ship)
        cone(f"Nozzle{s:+d}", dark, C, (x, -16.0, 0.0), (0, -1, 0), 1.4, 1.35, 1.6, 32, ship,
             cap=False)
        cone(f"Engine_core{s:+d}", emit_mat("Engine_core", COLORS["engine"], 0), C,
             (x, -16.2, 0.0), (0, -1, 0), 0.1, 1.25, 1.25, 32, ship)
        cone(f"Plume{s:+d}", plume_mat("Plume", COLORS["engine"], 8), C,
             (x, -16.4, 0.0), (0, -1, 0), 14, 1.3, 0.1, 32, ship, cap=False)

    # Centre engine
    cone("Nozzle_main", dark, C, (0, -16.0, 0.6), (0, -1, 0), 1.2, 1.4, 1.75, 32, ship, cap=False)
    cone("Engine_core_main", emit_mat("Engine_core", COLORS["engine"], 0), C,
         (0, -16.2, 0.6), (0, -1, 0), 0.1, 1.35, 1.35, 32, ship)
    cone("Plume_main", plume_mat("Plume", COLORS["engine"], 8), C,
         (0, -16.4, 0.6), (0, -1, 0), 18, 1.5, 0.1, 32, ship, cap=False)
    sphere("Tail_strobe", emit_mat("Strobe", COLORS["strobe"], 0), C, (0, -16.3, 2.4), 0.2,
           parent=ship)

    # Rear ramp (pivot at its hinge) and the lit cabin behind it
    ramp_pivot = empty("Ramp_pivot", RAMP_HINGE, C, ship)
    bm = bmesh.new()
    add_box(bm, (0, -RAMP_LEN / 2, -0.15), (3.4, RAMP_LEN, 0.3))
    for i in range(6):  # tread strips
        add_box(bm, (0, -0.5 - i * 0.8, 0.02), (3.2, 0.12, 0.08))
    mesh_obj("Ramp", bm, hull, C, parent=ramp_pivot)
    box("Cabin_glow", emit_mat("Cabin", "#FFE2B0", 3), C, (0, -15.9, 0.2), (3.2, 0.1, 3.0), ship)

    # Landing gear (origins at the top so scaling retracts them upward)
    gear_mat = dark
    gear = []
    for gx, gy in ((0, 9.5), (-2.4, -8.5), (2.4, -8.5)):
        g = empty(f"Gear{gx:+.0f}{gy:+.0f}", (gx, gy, -2.45), C, ship)
        tube(f"Gear_strut{gx:+.0f}{gy:+.0f}", gear_mat, C, (0, 0, 0), (0, 0, -0.95), 0.18, g)
        box(f"Gear_pad{gx:+.0f}{gy:+.0f}", gear_mat, C, (0, 0, -1.0), (0.9, 1.3, 0.12), g)
        gear.append(g)

    # Greebles: hatches, vents and blocks along the spine and flanks
    bm = bmesh.new()
    for _ in range(260):
        y = rng.uniform(-14.5, 7.5)
        w, h, zc = section_at(SHUTTLE_SECTIONS, y)
        if rng.random() < 0.6:
            lat = rng.uniform(-0.75, 0.75) * w
            z = top_z(w, h, zc, lat, e)
            add_box(bm, (lat, y, z), (rng.uniform(0.15, 0.7), rng.uniform(0.2, 1.4), rng.uniform(0.05, 0.25)))
        else:
            s = rng.choice((-1, 1))
            z = zc + rng.uniform(-0.6, 0.6) * h
            add_box(bm, (s * side_y(w, h, zc, z, e), y, z),
                    (rng.uniform(0.05, 0.2), rng.uniform(0.3, 1.6), rng.uniform(0.15, 0.6)))
    mesh_obj("Shuttle_greebles", bm, hull, C, parent=ship)

    # Cabin windows along both flanks
    bm = bmesh.new()
    for s in (-1, 1):
        for y in range(-10, 5, 2):
            w, h, zc = section_at(SHUTTLE_SECTIONS, y)
            z = zc + 0.55 * h
            add_box(bm, (s * side_y(w, h, zc, z, e), y, z), (0.12, 0.9, 0.45))
    mesh_obj("Shuttle_windows", bm, emit_mat("Windows", COLORS["window"], 6), C, parent=ship)

    # Antenna, RCS blocks, accent stripe
    tube("Antenna", dark, C, (0, 2.0, 2.55), (0, -1.5, 3.9), 0.05, ship)
    for s in (-1, 1):
        for y in (12.0, -13.0):
            w, h, zc = section_at(SHUTTLE_SECTIONS, y)
            box(f"RCS{s:+d}{y:+.0f}", dark, C, (s * (w - 0.05), y, zc + 0.3), (0.35, 0.6, 0.35), ship)
        box(f"Stripe{s:+d}", accent, C, (s * 3.18, -2.0, -0.6), (0.06, 16.0, 0.35), ship)
    return ship, ramp_pivot, gear


# --------------------------------------------------------------------------
# Mothership (1 km, nose +X) with docking arm on its +Y flank
# --------------------------------------------------------------------------
MOTHER_SECTIONS = [(-500, 110, 70, 0), (-420, 130, 82, 0), (-200, 132, 82, 0),
                   (0, 126, 76, 0), (200, 112, 66, -5), (350, 82, 46, -10),
                   (450, 42, 26, -12), (500, 8, 6, -12)]


def build_mothership(rng):
    C = "Mothership"
    root = empty("Mothership", MOTHERSHIP, C)
    hull = hull_mat("Mother_hull", COLORS["mother_hull"], COLORS["mother_panel"],
                    COLORS["mother_line"], 0.045, 0.7, 0.45)
    dark = plain_mat("Dark_metal", COLORS["dark_metal"], 0.8, 0.35)
    win = emit_mat("Windows", COLORS["window"], 6)
    e = 3.0
    loft("Mother_hull", hull, C, MOTHER_SECTIONS, "X", 48, e, root)

    # Command tower and bridge
    box("Tower_base", hull, C, (-260, 0, 95), (120, 70, 30), root)
    box("Tower_mid", hull, C, (-270, 0, 120), (80, 50, 24), root)
    box("Bridge", hull, C, (-262, 0, 140), (56, 80, 14), root)
    bm = bmesh.new()
    for y in range(-38, 39, 3):
        add_box(bm, (-233.5, y, 141), (1.0, 2.0, 4.0))
    mesh_obj("Bridge_windows", bm, win, C, parent=root)
    for i, (y, hgt) in enumerate(((-20, 60), (0, 85), (22, 50))):
        tube(f"Mast{i}", dark, C, (-275, y, 147), (-275, y, 147 + hgt), 1.4, root)
        sphere(f"Mast_light{i}", emit_mat("Nav_red", COLORS["nav_red"], 12), C,
               (-275, y, 148 + hgt), 2.2, parent=root)
    sphere("Radar_dish", dark, C, (-300, 0, 160), 18, (1, 1, 0.3), 32, 16, root,
           keep=lambda co: co.z > 0)

    # Engine block: five big nozzles with plumes
    for i, (y, z) in enumerate(((0, 0), (-60, 30), (60, 30), (-60, -30), (60, -30))):
        cone(f"M_nozzle{i}", dark, C, (-500, y, z), (-1, 0, 0), 40, 26, 34, 48, root, cap=False)
        cone(f"M_core{i}", emit_mat("M_engine_core", COLORS["engine"], 25), C,
             (-505, y, z), (-1, 0, 0), 1, 25, 25, 48, root)
        cone(f"M_plume{i}", plume_mat("M_plume", COLORS["engine"], 5), C,
             (-510, y, z), (-1, 0, 0), 160, 26, 4, 48, root, cap=False)

    # Greebles: thousands of blocks over the top, belly and flanks; trenches; windows
    bg, bw = bmesh.new(), bmesh.new()
    for _ in range(2600):
        x = rng.uniform(-480, 430)
        w, h, zc = section_at(MOTHER_SECTIONS, x)
        r = rng.random()
        big = rng.random() < 0.12
        sx, sy, sz = ((rng.uniform(8, 30), rng.uniform(8, 30), rng.uniform(3, 14)) if big else
                      (rng.uniform(1.5, 9), rng.uniform(1.5, 9), rng.uniform(0.8, 5)))
        if r < 0.45:
            lat = rng.uniform(-0.85, 0.85) * w
            add_box(bg, (x, lat, top_z(w, h, zc, lat, e)), (sx, sy, sz))
        elif r < 0.6:
            lat = rng.uniform(-0.85, 0.85) * w
            add_box(bg, (x, lat, 2 * zc - top_z(w, h, zc, lat, e)), (sx, sy, sz))
        else:
            s = rng.choice((-1, 1))
            z = zc + rng.uniform(-0.8, 0.8) * h
            add_box(bg, (x, s * side_y(w, h, zc, z, e), z), (sx, sz, sy))
    for s in (-1, 1):
        for row in range(6):
            z = -40 + row * 14
            for x in range(-470, 380, 6):
                if rng.random() < 0.3:
                    continue
                w, h, zc = section_at(MOTHER_SECTIONS, x)
                if abs(z - zc) > 0.85 * h:
                    continue
                add_box(bw, (x, s * (side_y(w, h, zc, z, e) + 0.3), z), (3.0, 0.8, 1.6))
    mesh_obj("Mother_greebles", bg, hull, C, parent=root)
    mesh_obj("Mother_windows", bw, win, C, parent=root)
    for s in (-1, 1):
        for z in (-55, 55):
            tube(f"Trench_pipe{s:+d}{z:+d}", dark, C, (-480, s * 128, z * 0.9), (300, s * 113, z * 0.8),
                 2.5, root)

    # Hangar bay glowing on the +Y flank
    box("Hangar_glow", emit_mat("Hangar", COLORS["hangar"], 5), C, (-120, 130.2, 0), (130, 1, 52), root)
    for z in (-28, 28):
        box(f"Hangar_frame{z:+d}", dark, C, (-120, 133, z), (140, 4, 4), root)
    for x in (-188, -52):
        box(f"Hangar_post{x:+d}", dark, C, (x, 133, 0), (4, 4, 60), root)

    # Docking arm, collar, clamps and status lights
    D = DOCK_LOCAL
    box("Dock_arm", hull, C, (D.x, (112 + D.y - 3) / 2, D.z), (14, D.y - 3 - 112, 12), root)
    torus("Dock_collar", dark, C, D, 3.6, 0.9, rot=Quaternion((1, 0, 0), math.radians(90)),
          parent=root)
    clamps = []
    for k in range(3):
        a = 2 * math.pi * k / 3 + math.pi / 2
        pivot = empty(f"Clamp_pivot{k}", D + Vector((math.cos(a) * 4.2, 0, math.sin(a) * 4.2)), C, root)
        pivot.rotation_mode = "XYZ"
        arm = Vector((0, 6.0, 0))
        tube(f"Clamp{k}", dark, C, (0, 0, 0), arm, 0.6, pivot)
        box(f"Clamp_jaw{k}", dark, C, arm + Vector((-math.cos(a) * 0.9, 0, -math.sin(a) * 0.9)),
            (1.4, 1.2, 1.4), pivot)
        pivot["open_axis"] = (math.sin(a), 0, -math.cos(a))
        clamps.append((pivot, a))
    dock_light = emit_mat("Dock_light", COLORS["dock_red"], 15)
    for k in range(6):
        a = 2 * math.pi * k / 6
        sphere(f"Dock_light{k}", dock_light, C, D + Vector((math.cos(a) * 6.5, 0.5, math.sin(a) * 6.5)),
               0.5, parent=root)

    # Running lights along the hull edges
    bm = bmesh.new()
    for x in range(-480, 460, 20):
        w, h, zc = section_at(MOTHER_SECTIONS, x)
        for s in (-1, 1):
            add_box(bm, (x, s * (w + 0.5), zc), (1.5, 1.5, 1.5))
    mesh_obj("Running_lights", bm, emit_mat("Strobe", COLORS["strobe"], 0), C, parent=root)
    return root, clamps, dock_light


# --------------------------------------------------------------------------
# Passengers
# --------------------------------------------------------------------------
GATE_Y = -122.0
# The shuttle is turned 180°, so its local -Y (tail) points to world +Y
RAMP_FOOT = SHUTTLE_REST + Vector((0, -RAMP_HINGE.y + RAMP_LEN * math.cos(RAMP_OPEN), 0))
HINGE_WORLD = SHUTTLE_REST + Vector((0, -RAMP_HINGE.y, RAMP_HINGE.z))
WALK_SPEED = 2.6 / FPS   # metres per frame (brisk boarding walk)


def passenger_paths():
    """Per passenger: list of (frame, location). Walk queue -> gate -> ramp -> cabin."""
    paths = []
    for i, suit in enumerate(PASSENGER_SUITS):
        start = 12 + i * 9
        q = Vector(((-0.6 if i % 2 else 0.6), GATE_Y + 1.0 + i * 0.8, 0))
        pts = [q, Vector((q.x * 0.5, GATE_Y - 0.5, 0)), Vector((0, RAMP_FOOT.y, 0)),
               Vector((0, HINGE_WORLD.y, HINGE_WORLD.z)), Vector((0, HINGE_WORLD.y - 3.0, HINGE_WORLD.z))]
        keys, f = [(1, pts[0]), (start, pts[0])], start
        for a, b in zip(pts, pts[1:]):
            f += max(1, round((b - a).length / WALK_SPEED))
            keys.append((f, b))
        paths.append(keys)
    return paths


def build_passengers():
    C = "Passengers"
    out = []
    for i, (suit, path) in enumerate(zip(PASSENGER_SUITS, passenger_paths())):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=12, radius1=0.22,
                              radius2=0.26, depth=1.3, matrix=Matrix.Translation((0, 0, 0.75)))
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.14,
                                  matrix=Matrix.Translation((0, 0, 1.6)))
        o = mesh_obj(f"Passenger{i}", bm, plain_mat(f"Suit{i}", suit, 0.1, 0.6), C,
                     loc=path[0][1], smooth=True)
        out.append((o, path))
    return out


# --------------------------------------------------------------------------
# Animation
# --------------------------------------------------------------------------
# Engine plume length over time (frame, scale) and landing-gear retraction window
PLUME_KEYS = [(1, 0.01), (252, 0.01), (270, 0.6), (322, 1.0), (420, 2.2),
              (600, 1.6), (660, 0.5), (700, 0.01)]
GEAR_UP = (285, 310)

# Shuttle flight: (frame, location, rotation XYZ in radians). Nose is local +Y,
# so rotation z = pi points it toward -Y (away from the station).
PI = math.pi
SHUTTLE_KEYS = [
    (1,   SHUTTLE_REST,                         (0.0, 0.0, PI)),
    (274, SHUTTLE_REST,                         (0.0, 0.0, PI)),
    (322, Vector((0, -150, 18)),                (0.08, 0.0, PI)),
    (350, Vector((0, -168, 26)),                (0.12, 0.0, PI)),
    (420, Vector((0, -430, 42)),                (0.03, 0.0, PI)),
    (470, Vector((60, -820, 80)),               (0.0, 0.32, PI - 0.12)),
    (520, Vector((110, -1300, 125)),            (0.0, 0.18, PI - 0.05)),
    (600, Vector((40, -2150, 165)),             (0.0, -0.12, PI + 0.03)),
    (660, SHUTTLE_DOCKED + Vector((0, 32, 2)),  (0.0, 0.0, PI)),
    (700, SHUTTLE_DOCKED,                       (0.0, 0.0, PI)),
    (720, SHUTTLE_DOCKED,                       (0.0, 0.0, PI)),
]

CAMERAS = [
    # name, first frame, location, target ('Shuttle' or a point), lens, parent
    ("Cam_boarding", 1,   Vector((15, -111, 6.5)),   Vector((0, -126, 1.5)), 28, None),
    ("Cam_liftoff",  200, Vector((45, -212, 5)),     "Shuttle", 35, None),
    ("Cam_chase",    350, Vector((7, -48, 11)),      "Shuttle", 40, "Shuttle"),
    ("Cam_wide",     505, Vector((-450, -1100, 260)), "Shuttle", 28, None),
    ("Cam_docking",  600, MOTHERSHIP + Vector((150, 300, 15)), "Shuttle", 45, None),
]


def key(obj, path, value, frame):
    setattr(obj, path, value)
    obj.keyframe_insert(path, frame=frame)


def key_socket(sock, value, frame):
    sock.default_value = value
    sock.keyframe_insert("default_value", frame=frame)


def emission_node(mat):
    return mat.node_tree.nodes.get("Emission")


def animate(ship, ramp, gear, ring, passengers, clamps, dock_light):
    for f, loc, rot in SHUTTLE_KEYS:
        key(ship, "location", loc, f)
        key(ship, "rotation_euler", rot, f)

    # Ramp: open while boarding, closes after the last passenger is in
    last_in = max(p[-1][0] for _, p in passengers)
    ramp.rotation_mode = "XYZ"
    key(ramp, "rotation_euler", (RAMP_OPEN, 0, 0), 1)
    key(ramp, "rotation_euler", (RAMP_OPEN, 0, 0), last_in + 4)
    key(ramp, "rotation_euler", (RAMP_CLOSED, 0, 0), last_in + 34)

    # Gear retracts after lift-off
    for g in gear:
        key(g, "scale", (1, 1, 1), GEAR_UP[0])
        key(g, "scale", (0.01, 0.01, 0.01), GEAR_UP[1])

    # Engines: off -> ignite -> cruise -> throttle down -> off at dock
    plumes = [o for o in bpy.data.objects if o.name.startswith("Plume")]
    for p in plumes:
        for f, s in PLUME_KEYS:
            key(p, "scale", (1, 1, s), f)
    core = emission_node(bpy.data.materials["Engine_core"])
    for f, s in ((1, 0.0), (252, 0.0), (270, 40.0), (660, 25.0), (700, 0.0)):
        key_socket(core.inputs["Strength"], s, f)

    # Blinking strobes (all strobe-material lights): 2 frames on, every second
    strobe = emission_node(bpy.data.materials["Strobe"])
    for f in range(1, FRAME_END + 1, FPS):
        key_socket(strobe.inputs["Strength"], 0.0, f)
        key_socket(strobe.inputs["Strength"], 60.0, f + 1)
        key_socket(strobe.inputs["Strength"], 60.0, f + 3)
        key_socket(strobe.inputs["Strength"], 0.0, f + 4)

    # Habitat ring turns slowly
    ring.rotation_mode = "XYZ"
    key(ring, "rotation_euler", (0, 0, 0), 1)
    key(ring, "rotation_euler", (0, 0, math.radians(40)), FRAME_END)

    # Passengers walk, then vanish inside the cabin
    for o, path in passengers:
        for f, loc in path:
            key(o, "location", loc, f)
        key(o, "scale", (1, 1, 1), path[-1][0])
        key(o, "scale", (0.001, 0.001, 0.001), path[-1][0] + 1)

    # Docking: clamps swing shut, status lights red -> green
    for pivot, a in clamps:
        ax = Vector(pivot["open_axis"])
        open_q = Quaternion(ax, math.radians(55))
        pivot.rotation_mode = "QUATERNION"
        key(pivot, "rotation_quaternion", open_q, 1)
        key(pivot, "rotation_quaternion", open_q, 690)
        key(pivot, "rotation_quaternion", Quaternion((1, 0, 0, 0)), 708)
    dl = emission_node(dock_light)
    key_socket(dl.inputs["Color"], srgb(COLORS["dock_red"]), 1)
    key_socket(dl.inputs["Color"], srgb(COLORS["dock_red"]), 704)
    key_socket(dl.inputs["Color"], srgb(COLORS["dock_green"]), 708)


def build_cameras(scene, ship):
    C = "Cameras"
    for name, start, loc, target, lens, parent in CAMERAS:
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cd.clip_start = 0.1
        cd.clip_end = 200000
        cam = bpy.data.objects.new(name, cd)
        cam.location = loc
        if parent == "Shuttle":
            cam.parent = ship
        link(cam, C)
        if target == "Shuttle":
            tgt = ship
        else:
            tgt = empty(name + "_target", target, C)
        con = cam.constraints.new("TRACK_TO")
        con.target = tgt
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"
        m = scene.timeline_markers.new(name, frame=start)
        m.camera = cam
        if start == 1:
            scene.camera = cam


# --------------------------------------------------------------------------
# Render settings and bloom
# --------------------------------------------------------------------------
def setup_render(scene):
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    r = scene.render
    r.resolution_x, r.resolution_y = 1920, 1080
    r.fps = FPS
    scene.frame_start, scene.frame_end = 1, FRAME_END
    for target, attr, val in ((r, "use_motion_blur", True), (scene.eevee, "use_motion_blur", True),
                              (scene.eevee, "use_bloom", True), (scene.eevee, "bloom_intensity", 0.08),
                              (scene.eevee, "taa_render_samples", 64),
                              (scene.eevee, "use_gtao", True)):
        try:
            setattr(target, attr, val)
        except (AttributeError, TypeError):
            pass
    for vt in ("AgX", "Filmic"):
        try:
            scene.view_settings.view_transform = vt
            break
        except TypeError:
            continue

    # Bloom for EEVEE Next and Cycles: a Glare node in the compositor
    try:
        scene.use_nodes = True
        tree = scene.node_tree
    except AttributeError:
        return  # newer Blender: add a Glare node in the Compositor by hand if wanted
    tree.nodes.clear()
    rl = tree.nodes.new("CompositorNodeRLayers")
    comp = tree.nodes.new("CompositorNodeComposite")
    tree.links.new(rl.outputs["Image"], comp.inputs["Image"])  # always a working output
    try:
        glare = tree.nodes.new("CompositorNodeGlare")
        for attr, val in (("glare_type", "FOG_GLOW"), ("threshold", 1.0), ("size", 8)):
            try:
                setattr(glare, attr, val)
            except (AttributeError, TypeError):
                pass
        tree.links.new(rl.outputs["Image"], glare.inputs["Image"])
        tree.links.new(glare.outputs["Image"], comp.inputs["Image"])
    except (AttributeError, TypeError, KeyError, RuntimeError):
        pass


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def reset_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for blocks in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
        for b in list(blocks):
            if b.users == 0:
                blocks.remove(b)
    for c in list(bpy.context.scene.collection.children):
        bpy.context.scene.collection.children.unlink(c)
    bpy.context.scene.timeline_markers.clear()


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {}
    for i, a in enumerate(argv):
        if a in ("--save", "--out", "--render-frame"):
            opts[a] = argv[i + 1]
        elif a == "--render-anim":
            opts[a] = True
    return opts


def main():
    scene = bpy.context.scene
    reset_scene()
    rng = random.Random(SEED)
    build_world(scene)
    build_environment()
    ring = build_station(rng)
    ship, ramp, gear = build_shuttle(rng)
    mother, clamps, dock_light = build_mothership(rng)
    passengers = build_passengers()
    animate(ship, ramp, gear, ring, passengers, clamps, dock_light)
    build_cameras(scene, ship)
    setup_render(scene)
    scene.frame_set(1)

    opts = parse_args()
    if "--save" in opts:
        bpy.ops.wm.save_as_mainfile(filepath=bpy.path.abspath(opts["--save"]))
    if "--out" in opts:
        scene.render.filepath = opts["--out"]
    if "--render-frame" in opts:
        scene.frame_set(int(opts["--render-frame"]))
        bpy.ops.render.render(write_still=True)
    elif "--render-anim" in opts:
        bpy.ops.render.render(animation=True)
    print("Space Dock built:", len(bpy.data.objects), "objects")


if __name__ == "__main__":
    main()
