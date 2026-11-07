"""
Jet Assembly - animated build of a twin-engine jet airliner (Blender 3.6 / 4.x).

ACT 1  (frames 1-400)   The big components arrive on the assembly floor and
                        join: fuselage, wings, engines, tail, landing gear.
ACT 2  (400-1660)       Each component in turn breaks into its parts, then
                        reassembles step by step with captions:
                          Engine   pylon, shaft, 6 compressor stages, combustor,
                                   4 turbine stages, core casing, fan, spinner,
                                   fan case, cowl halves, inlet lip, nozzle, plug
                          Wing     spars, 11 ribs, lower and upper skins, slats,
                                   flaps, aileron, winglet
                          Fuselage frames, keel and floor, stringers, lower and
                                   upper skin panels, nose and tail cones,
                                   windows, windshield, doors
                          Tail     fin, horizontal stabilisers, rudder, elevators
                          Gear     strut, piston, side brace, torque links, axle,
                                   brakes, hubs, tyres, door
FINALE (1660-1740)      The finished jet, fans spinning.

Generic design, about 38 m long and 37 m span. Nose points +X, left wing +Y,
up is +Z, the floor is z = 0.

Run in Blender: Scripting tab -> Open -> Run Script -> Space to play.
Headless:
    blender -b -P jet_assembly.py -- --save jet.blend
    blender -b -P jet_assembly.py -- --render-frame 900 --out still.png
    blender -b -P jet_assembly.py -- --render-anim --out //render/jet_
"""

import math
import sys

import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

FPS = 24
FZ = 4.8              # fuselage axis height above the floor
ANIM = {}             # name -> [(frame, path, value)]; mirrors every keyframe (used by tools/)
PARTS = []            # every animated sub-part: dict(obj, comp, group, explode, home)
CAPTIONS = []         # (start, end, title, subtitle)

COLORS = {
    "paint": "#E9ECEF", "paint_blue": "#1F4E8C", "skin_grey": "#CDD3DA",
    "control": "#AEB6BF", "primer": "#7FA36B", "alu": "#A7B0BA", "floor_panel": "#6B7480",
    "glass": "#16222F", "door": "#D7DCE1", "titanium": "#8D939A", "case": "#3A3F45",
    "compressor": "#B5BCC4", "copper": "#B87333", "turbine": "#7A5C48", "nozzle": "#6E7378",
    "chrome": "#D9DDE1", "tyre": "#1A1A1A", "hub": "#9AA0A6", "brake": "#5A5F66",
    "floor": "#2A2E35", "floor_line": "#3A404A", "bay_line": "#E8B21A", "caption": "#FFFFFF",
}


# --------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------
def srgb(h, a=1.0):
    h = h.lstrip("#")
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4)) + (a,)


_MATS = {}


def mat(key, metallic=0.0, rough=0.45, emit=0.0):
    name = f"{key}_{metallic:.1f}_{rough:.2f}"
    if name in _MATS:
        return _MATS[name]
    m = bpy.data.materials.new(key)
    m.use_nodes = True
    N = m.node_tree.nodes
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    if emit > 0:
        sh = N.new("ShaderNodeEmission")
        sh.inputs["Color"].default_value = srgb(COLORS[key])
        sh.inputs["Strength"].default_value = emit
        m.node_tree.links.new(sh.outputs["Emission"], out.inputs["Surface"])
    else:
        sh = N.new("ShaderNodeBsdfPrincipled")
        sh.inputs["Base Color"].default_value = srgb(COLORS[key])
        sh.inputs["Metallic"].default_value = metallic
        sh.inputs["Roughness"].default_value = rough
        m.node_tree.links.new(sh.outputs["BSDF"], out.inputs["Surface"])
    m.diffuse_color = srgb(COLORS[key])
    m["preview"] = COLORS[key]
    m["emit"] = float(emit)
    _MATS[name] = m
    return m


def M_(key):
    """Material presets by role."""
    presets = {
        "paint": (0.0, 0.3), "paint_blue": (0.0, 0.3), "skin_grey": (0.3, 0.35),
        "control": (0.4, 0.35), "primer": (0.0, 0.6), "alu": (0.9, 0.3),
        "floor_panel": (0.2, 0.5), "glass": (0.0, 0.05), "door": (0.0, 0.3),
        "titanium": (1.0, 0.25), "case": (0.7, 0.4), "compressor": (1.0, 0.2),
        "copper": (1.0, 0.3), "turbine": (0.9, 0.45), "nozzle": (0.8, 0.4),
        "chrome": (1.0, 0.08), "tyre": (0.0, 0.8), "hub": (0.9, 0.3), "brake": (0.8, 0.5),
    }
    me, ro = presets[key]
    return mat(key, me, ro)


# --------------------------------------------------------------------------
# Scene plumbing
# --------------------------------------------------------------------------
_COLL = {}


def link(obj, collection):
    if collection not in _COLL:
        c = bpy.data.collections.new(collection)
        bpy.context.scene.collection.children.link(c)
        _COLL[collection] = c
    _COLL[collection].objects.link(obj)
    return obj


def empty(name, loc=(0, 0, 0), collection="Rig", parent=None):
    o = bpy.data.objects.new(name, None)
    o.location = loc
    if parent is not None:
        o.parent = parent
    return link(o, collection)


def key(obj, path, value, frame):
    """Set + keyframe, and mirror the key into ANIM for the preview tools."""
    setattr(obj, path, value)
    obj.keyframe_insert(path, frame=frame)
    ANIM.setdefault(obj.name, []).append((frame, path, tuple(value)))


def mesh_obj(name, bm, material, collection, loc=(0, 0, 0), rot=None, parent=None, smooth=True):
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
    me.materials.append(material)
    o = bpy.data.objects.new(name, me)
    o.location = loc
    if rot is not None:
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = rot
    if parent is not None:
        o.parent = parent
    return link(o, collection)


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------
def add_box(bm, center, size, rot=None):
    M = Matrix.Translation(center)
    if rot is not None:
        M = M @ rot
    M = M @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
    bmesh.ops.create_cube(bm, size=1.0, matrix=M)


def box(name, material, coll, center, size, parent=None):
    bm = bmesh.new()
    add_box(bm, center, size)
    return mesh_obj(name, bm, material, coll, parent=parent, smooth=False)


def sphere(name, material, coll, loc, r, scale=(1, 1, 1), seg=24, ring=12, parent=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=1.0)
    bmesh.ops.transform(bm, matrix=Matrix.Diagonal((r * scale[0], r * scale[1], r * scale[2], 1)),
                        verts=bm.verts)
    return mesh_obj(name, bm, material, coll, loc, parent=parent)


def cone(name, material, coll, base, direction, length, r1, r2=0.0, seg=32, parent=None, cap=True):
    """Origin at base; local Z along direction."""
    d = Vector(direction).normalized()
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=seg, radius1=r1, radius2=r2,
                          depth=length, matrix=Matrix.Translation((0, 0, length / 2)))
    return mesh_obj(name, bm, material, coll, Vector(base), d.to_track_quat("Z", "Y"), parent)


def tube(name, material, coll, a, b, r, parent=None, seg=16, cap=True):
    a, b = Vector(a), Vector(b)
    return cone(name, material, coll, a, b - a, (b - a).length, r, r, seg, parent, cap)


def torus_bm(bm, R, r, maj=48, mnr=12):
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


AXIS_X = Quaternion((0, 1, 0), math.radians(90))   # turns local Z onto +X
AXIS_Y = Quaternion((1, 0, 0), math.radians(-90))  # turns local Z onto +Y


def torus(name, material, coll, loc, R, r, rot=None, parent=None, maj=48, mnr=12):
    bm = bmesh.new()
    torus_bm(bm, R, r, maj, mnr)
    return mesh_obj(name, bm, material, coll, loc, rot, parent)


def lerp(a, b, t):
    return a + (b - a) * t


# Fuselage: circular sections (x, radius, z offset from FZ) ----------------
FUSE = [(-19.0, 0.35, 1.15), (-17.0, 0.8, 0.95), (-15.0, 1.25, 0.7), (-12.0, 1.7, 0.35),
        (-8.0, 2.0, 0.0), (12.0, 2.0, 0.0), (14.0, 1.85, -0.1), (16.0, 1.5, -0.25),
        (17.8, 1.0, -0.4), (18.8, 0.45, -0.5), (19.2, 0.05, -0.55)]


def fuse_at(x):
    for (x0, r0, z0), (x1, r1, z1) in zip(FUSE, FUSE[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            return lerp(r0, r1, t), FZ + lerp(z0, z1, t)
    return FUSE[-1][1], FZ + FUSE[-1][2]


def fuse_shell(name, material, coll, x0, x1, a0=0.0, a1=2 * math.pi, dr=0.0, nx=10, na=48,
               cap0=False, cap1=False):
    """Surface of the fuselage between x0..x1 and angles a0..a1 (0 = +Y side, pi/2 = top)."""
    bm = bmesh.new()
    full = abs(a1 - a0 - 2 * math.pi) < 1e-6
    na_pts = na if full else na + 1
    rows = []
    for i in range(nx + 1):
        x = lerp(x0, x1, i / nx)
        r, zc = fuse_at(x)
        r += dr
        row = []
        for j in range(na_pts):
            a = lerp(a0, a1, j / na)
            row.append(bm.verts.new((x, math.cos(a) * r, zc + math.sin(a) * r)))
        rows.append(row)
    for i in range(nx):
        for j in range(na if full else na):
            j2 = (j + 1) % na_pts
            if not full and j == na_pts - 1:
                continue
            bm.faces.new((rows[i][j], rows[i][j2], rows[i + 1][j2], rows[i + 1][j]))
    if cap0 and full:
        bm.faces.new(list(reversed(rows[0])))
    if cap1 and full:
        bm.faces.new(rows[-1])
    return mesh_obj(name, bm, material, coll)


# Lifting surfaces: wing, fin, stabilisers, winglet -------------------------
def half_thick(c, t):
    """NACA 4-digit half-thickness for unit chord."""
    return 5 * t * (0.2969 * math.sqrt(max(c, 0)) - 0.126 * c - 0.3516 * c ** 2
                    + 0.2843 * c ** 3 - 0.1036 * c ** 4)


class Surface:
    """root/tip: (leading-edge x, span position, vertical position, chord).
    orient 'H': span along Y (sign picks the side); 'V': span along Z at lateral y0."""

    def __init__(self, root, tip, t=0.11, orient="H", sign=1, y0=0.0):
        self.root, self.tip, self.t, self.orient, self.sign, self.y0 = root, tip, t, orient, sign, y0

    def at(self, s):
        return tuple(lerp(a, b, s) for a, b in zip(self.root, self.tip))

    def pt(self, s, c, side):
        le, span, vert, chord = self.at(s)
        x = le - c * chord
        th = side * half_thick(c, self.t) * chord
        if self.orient == "H":
            return Vector((x, self.sign * span, vert + th))
        return Vector((x, self.y0 + th, span))


def _cs(c0, c1, n):
    return [c0 + (c1 - c0) * (1 - math.cos(math.pi * i / n)) / 2 for i in range(n + 1)]


def surf_skin(name, material, coll, S, c0, c1, s0, s1, side, nc=14, ns=8):
    bm = bmesh.new()
    cs, ss = _cs(c0, c1, nc), [lerp(s0, s1, i / ns) for i in range(ns + 1)]
    g = [[bm.verts.new(S.pt(s, c, side)) for c in cs] for s in ss]
    for i in range(ns):
        for j in range(nc):
            bm.faces.new((g[i][j], g[i][j + 1], g[i + 1][j + 1], g[i + 1][j]))
    return mesh_obj(name, bm, material, coll)


def surf_solid(name, material, coll, S, c0, c1, s0, s1, nc=10, ns=6):
    bm = bmesh.new()
    cs, ss = _cs(c0, c1, nc), [lerp(s0, s1, i / ns) for i in range(ns + 1)]
    U = [[bm.verts.new(S.pt(s, c, 1)) for c in cs] for s in ss]
    L = [[bm.verts.new(S.pt(s, c, -1)) for c in cs] for s in ss]
    for i in range(ns):
        for j in range(nc):
            bm.faces.new((U[i][j], U[i][j + 1], U[i + 1][j + 1], U[i + 1][j]))
            bm.faces.new((L[i][j], L[i + 1][j], L[i + 1][j + 1], L[i][j + 1]))
        for j in (0, nc):
            bm.faces.new((U[i][j], U[i + 1][j], L[i + 1][j], L[i][j]))
    for i in (0, ns):
        bm.faces.new(U[i] + list(reversed(L[i])))
    return mesh_obj(name, bm, material, coll)


def surf_spar(name, material, coll, S, c, s0, s1, ns=8):
    bm = bmesh.new()
    ss = [lerp(s0, s1, i / ns) for i in range(ns + 1)]
    U = [bm.verts.new(S.pt(s, c, 1)) for s in ss]
    L = [bm.verts.new(S.pt(s, c, -1)) for s in ss]
    for i in range(ns):
        bm.faces.new((U[i], U[i + 1], L[i + 1], L[i]))
    return mesh_obj(name, bm, material, coll, smooth=False)


def surf_rib(bm, S, s, c0, c1, n=10):
    cs = _cs(c0, c1, n)
    pts = [S.pt(s, c, 1) for c in cs] + [S.pt(s, c, -1) for c in reversed(cs)]
    bm.faces.new([bm.verts.new(p) for p in pts])


# --------------------------------------------------------------------------
# Parts registry
# --------------------------------------------------------------------------
def part(obj, comp, group, explode):
    obj.parent = COMP_ROOTS[comp]
    PARTS.append(dict(obj=obj, comp=comp, group=group, explode=Vector(explode),
                      home=Vector(obj.location)))
    return obj


COMP_ROOTS = {}


# --------------------------------------------------------------------------
# Components
# --------------------------------------------------------------------------
def build_fuselage():
    C, comp = "Fuselage", "fuselage"
    paint, primer, alu = M_("paint"), M_("primer"), M_("alu")

    # Frames: rings at every station, spread like an accordion when exploded
    x = -16.5
    while x <= 17.6:
        r, zc = fuse_at(x)
        f = torus(f"Frame{x:+05.1f}", primer, C, Vector((x, 0, zc)), r - 0.1, 0.06, rot=AXIS_X)
        part(f, comp, "Frames", (x * 0.45, 0, 0))
        x += 1.5

    # Keel beam and cabin floor
    part(box("Keel_beam", alu, C, (2.0, 0, FZ - 1.75), (20, 0.5, 0.3)), comp, "Keel and floor",
         (0, 0, -2.2))
    part(box("Cabin_floor", M_("floor_panel"), C, (2.0, 0, FZ - 0.5), (20, 3.5, 0.06)), comp,
         "Keel and floor", (0, 0, 3.0))

    # Stringers around the constant section
    for k in range(16):
        a = 2 * math.pi * (k + 0.5) / 16
        d = Vector((0, math.cos(a), math.sin(a)))
        a_pt = Vector((-8.0, 0, FZ)) + d * 1.86
        b_pt = Vector((12.0, 0, FZ)) + d * 1.86
        part(tube(f"Stringer{k:02d}", alu, C, a_pt, b_pt, 0.035, seg=8), comp, "Stringers", d * 2.2)

    # Skin panels: lower then upper halves of three barrel sections, plus cones
    for i, (x0, x1) in enumerate(((-8, -3), (-3, 5), (5, 12))):
        part(fuse_shell(f"Skin_lower{i}", paint, C, x0, x1, math.pi, 2 * math.pi), comp,
             "Lower skin panels", (0, 0, -3.6))
        part(fuse_shell(f"Skin_upper{i}", paint, C, x0, x1, 0, math.pi), comp,
             "Upper skin panels", (0, 0, 7.0))
    part(fuse_shell("Nose_cone", paint, C, 12, 19.2, nx=14, cap1=True), comp, "Nose and tail cones",
         (7, 0, 0))
    part(fuse_shell("Tail_cone", paint, C, -19.0, -8, nx=14, cap0=True), comp, "Nose and tail cones",
         (-8, 0, 1.2))

    # Cabin windows (merged per side), windshield, doors
    for side in (1, -1):
        bm = bmesh.new()
        a = math.radians(18)
        x = -7.0
        while x <= 11.0:
            if not (9.8 < x < 11.2 or -7.0 < x < -5.8):
                p = Vector((x, side * math.cos(a) * 2.01, FZ + math.sin(a) * 2.01))
                add_box(bm, p, (0.3, 0.06, 0.42))
            x += 0.9
        part(mesh_obj(f"Windows_{'L' if side > 0 else 'R'}", bm, M_("glass"), C, smooth=False),
             comp, "Windows, windshield, doors", (0, side * 2.6, 1.0))
    part(fuse_shell("Windshield", M_("glass"), C, 15.4, 17.2, math.radians(25), math.radians(155),
                    dr=0.02, nx=4, na=12), comp, "Windows, windshield, doors", (2.5, 0, 2.0))
    for i, x in enumerate((10.5, -6.4)):
        for side in (1, -1):
            part(box(f"Door{i}_{'L' if side > 0 else 'R'}", M_("door"), C,
                     (x, side * 2.0, FZ + 0.2), (1.0, 0.07, 1.9)),
                 comp, "Windows, windshield, doors", (0, side * 2.6, 0))


WING = {}


def wing_surface(sign):
    return Surface((3.0, 1.2, FZ - 1.2, 7.0), (-4.25, 17.5, FZ - 1.2 + 1.36, 1.8), 0.115, "H", sign)


def wing_at(S, y):
    """Leading-edge x, chord, mid-height z and span fraction at lateral distance y."""
    s = (abs(y) - S.root[1]) / (S.tip[1] - S.root[1])
    le, _, z, chord = S.at(s)
    return le, chord, z, s


def build_wing(sign):
    side = "L" if sign > 0 else "R"
    C, comp = f"Wing_{side}", f"wing_{side}"
    S = wing_surface(sign)
    WING[side] = S
    skin, primer, ctrl = M_("skin_grey"), M_("primer"), M_("control")
    s_eng = wing_at(S, 6.2)[3]

    part(surf_spar(f"Spar_front_{side}", primer, C, S, 0.15, 0.0, 0.98), comp, "Spars", (0, 0, 1.6))
    part(surf_spar(f"Spar_rear_{side}", primer, C, S, 0.65, 0.0, 0.98), comp, "Spars", (0, 0, 1.6))
    for k in range(11):
        s = 0.03 + 0.92 * k / 10
        bm = bmesh.new()
        surf_rib(bm, S, s, 0.15, 0.65)
        part(mesh_obj(f"Rib{k:02d}_{side}", bm, primer, C, smooth=False), comp, "Ribs",
             (0, sign * s * 2.0, 3.0 + 0.15 * k))
    part(surf_skin(f"Skin_lower_{side}", skin, C, S, 0.12, 0.75, 0.0, 1.0, -1), comp, "Lower skin",
         (0, 0, -2.8))
    part(surf_skin(f"Skin_upper_{side}", skin, C, S, 0.12, 0.75, 0.0, 1.0, 1), comp, "Upper skin",
         (0, 0, 5.5))
    part(surf_solid(f"Slat_inner_{side}", ctrl, C, S, 0.0, 0.12, 0.02, s_eng - 0.04), comp,
         "Leading-edge slats", (3.0, 0, 0.6))
    part(surf_solid(f"Slat_outer_{side}", ctrl, C, S, 0.0, 0.12, s_eng + 0.04, 0.98), comp,
         "Leading-edge slats", (3.0, 0, 0.6))
    part(surf_solid(f"Flap_inner_{side}", ctrl, C, S, 0.75, 1.0, 0.0, 0.30), comp, "Flaps",
         (-3.0, 0, -1.0))
    part(surf_solid(f"Flap_outer_{side}", ctrl, C, S, 0.75, 1.0, 0.32, 0.62), comp, "Flaps",
         (-3.0, 0, -1.0))
    part(surf_solid(f"Aileron_{side}", ctrl, C, S, 0.75, 1.0, 0.64, 0.98), comp, "Aileron",
         (-3.0, 0, -0.4))
    tip_le, _, tip_z, tip_chord = S.at(1.0)
    W = Surface((tip_le + 0.05, tip_z, 0, tip_chord * 0.95), (tip_le - 1.45, tip_z + 2.3, 0, 0.7),
                0.09, "V", y0=sign * 17.45)
    part(surf_solid(f"Winglet_{side}", M_("paint_blue"), C, W, 0.0, 1.0, 0.0, 1.0), comp, "Winglet",
         (0, sign * 2.5, 1.2))


def blade_ring(bm, cx, r_in, r_out, n, chord, thick, twist_deg, offset=0.0):
    """n twisted blades around the X axis at x = cx (engine-local)."""
    mid = (r_in + r_out) / 2
    for k in range(n):
        a = 2 * math.pi * (k + offset) / n
        M = (Matrix.Rotation(a, 4, "X") @ Matrix.Translation((cx, mid, 0))
             @ Matrix.Rotation(math.radians(twist_deg), 4, "Y"))
        add_box(bm, (0, 0, 0), (chord, r_out - r_in, thick), rot=M)


def build_engine(sign):
    side = "L" if sign > 0 else "R"
    C, comp = f"Engine_{side}", f"engine_{side}"
    S = WING[side]
    le, chord, wz, s = wing_at(S, 6.2)
    wing_lower = wz - half_thick(0.3, S.t) * chord
    E = Vector((le + 2.4 - 2.3, sign * 6.2, wing_lower - 1.25 - 0.4))
    ENGINE_CENTERS[side] = E
    X = Vector((1, 0, 0))

    def P(x, y=0.0, z=0.0):
        return E + Vector((x, y, z))

    # Pylon: tapered box from the nacelle top up into the wing
    bm = bmesh.new()
    top = wing_lower + 0.15 - E.z
    pts = [(-1.4, -0.17, 1.1), (2.0, -0.17, 1.1), (2.0, 0.17, 1.1), (-1.4, 0.17, 1.1),
           (-2.2, -0.15, top), (1.0, -0.15, top), (1.0, 0.15, top), (-2.2, 0.15, top)]
    v = [bm.verts.new(P(*p)) for p in pts]
    for f in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        bm.faces.new([v[i] for i in f])
    part(mesh_obj(f"Pylon_{side}", bm, M_("paint"), C, smooth=False), comp, "Pylon", (0, sign * 2.6, 0.4))

    part(tube(f"Shaft_{side}", M_("alu"), C, P(-2.4), P(1.8), 0.07), comp, "Shaft", (0, 0, -1.6))
    for k in range(6):
        cx = 1.2 - k * 0.24
        bm = bmesh.new()
        rd = 0.36 - k * 0.012
        rb = 0.58 - k * 0.022
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32, radius1=rd, radius2=rd,
                              depth=0.08, matrix=Matrix.Translation((cx, 0, 0)) @ Matrix.Rotation(math.pi / 2, 4, "Y"))
        blade_ring(bm, cx, rd, rb, 30, 0.12, 0.012, 35, offset=0.3 * k)
        o = mesh_obj(f"Compressor{k}_{side}", bm, M_("compressor"), C)
        o.location = E
        part(o, comp, "Compressor stages", (2.2 + k * 0.75, 0, 0))
    o = torus(f"Combustor_{side}", M_("copper"), C, P(-0.35), 0.45, 0.14, rot=AXIS_X)
    part(o, comp, "Combustor", (0, sign * 1.8, 0))
    for k in range(4):
        cx = -0.8 - k * 0.24
        bm = bmesh.new()
        rd = 0.34 + k * 0.01
        rb = 0.52 + k * 0.035
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32, radius1=rd, radius2=rd,
                              depth=0.08, matrix=Matrix.Translation((cx, 0, 0)) @ Matrix.Rotation(math.pi / 2, 4, "Y"))
        blade_ring(bm, cx, rd, rb, 36, 0.1, 0.012, -40, offset=0.5 * k)
        o = mesh_obj(f"Turbine{k}_{side}", bm, M_("turbine"), C)
        o.location = E
        part(o, comp, "Turbine stages", (-2.6 - k * 0.75, 0, 0))
    part(cone(f"Core_casing_{side}", M_("case"), C, P(-1.8), X, 3.1, 0.66, 0.62, cap=False), comp,
         "Core casing", (-4.6, 0, -1.3))

    # Fan: hub + 22 wide blades; origin on the axis so it can spin
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32, radius1=0.32, radius2=0.32,
                          depth=0.3, matrix=Matrix.Rotation(math.pi / 2, 4, "Y"))
    blade_ring(bm, 0.0, 0.3, 1.04, 22, 0.42, 0.035, 38)
    fan = mesh_obj(f"Fan_{side}", bm, M_("titanium"), C, loc=P(1.6))
    fan.rotation_mode = "XYZ"
    part(fan, comp, "Fan", (5.6, 0, 0))
    part(cone(f"Spinner_{side}", M_("chrome"), C, P(1.75), X, 0.7, 0.32, 0.0), comp, "Spinner",
         (7.2, 0, 0))
    part(cone(f"Fan_case_{side}", M_("case"), C, P(0.9), X, 1.45, 1.12, 1.12, seg=48, cap=False),
         comp, "Fan case", (4.2, 0, 2.6))

    # Cowl halves (split left/right), inlet lip, exhaust
    for half, (a0, a1) in (("out", (-math.pi / 2, math.pi / 2)), ("in", (math.pi / 2, 3 * math.pi / 2))):
        bm = bmesh.new()
        prof = [(-1.6, 1.0), (-0.6, 1.2), (0.6, 1.26), (2.2, 1.22)]
        n = 24
        rows = []
        for x, r in prof:
            rows.append([bm.verts.new(P(x, math.cos(lerp(a0, a1, j / n)) * r,
                                        math.sin(lerp(a0, a1, j / n)) * r)) for j in range(n + 1)])
        for i in range(len(rows) - 1):
            for j in range(n):
                bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
        lift = 3.0 if a0 < 0 else 5.6  # cowl halves stack above the engine, clear of the camera
        part(mesh_obj(f"Cowl_{half}_{side}", bm, M_("paint"), C), comp, "Cowl halves", (0.8, 0, lift))
    part(torus(f"Inlet_lip_{side}", M_("alu"), C, P(2.25), 1.16, 0.13, rot=AXIS_X, maj=64), comp,
         "Inlet lip", (8.6, 0, 0))
    part(cone(f"Nozzle_{side}", M_("nozzle"), C, P(-1.6), -X, 1.4, 0.8, 0.56, cap=False), comp,
         "Exhaust nozzle and plug", (-5.6, 0, 0))
    part(cone(f"Plug_{side}", M_("nozzle"), C, P(-2.4), -X, 1.3, 0.42, 0.0), comp,
         "Exhaust nozzle and plug", (-7.2, 0, 0))
    FANS.append(fan)


ENGINE_CENTERS = {}
FANS = []

FIN = Surface((-11.5, 6.35, 0, 6.0), (-15.85, 12.6, 0, 2.4), 0.10, "V", y0=0.0)


def build_tail():
    C, comp = "Tail", "tail"
    blue, grey, ctrl = M_("paint_blue"), M_("skin_grey"), M_("control")
    part(surf_solid("Fin", blue, C, FIN, 0.0, 0.7, 0.0, 1.0), comp, "Vertical fin", (0, 0, 4.5))
    part(surf_solid("Rudder", blue, C, FIN, 0.7, 1.0, 0.05, 0.95), comp, "Rudder", (-3.0, 0, 4.5))
    for sign in (1, -1):
        side = "L" if sign > 0 else "R"
        H = Surface((-14.4, 0.4, FZ + 0.62, 4.2), (-17.8, 6.5, FZ + 0.62 + 0.64, 1.6), 0.10, "H", sign)
        part(surf_solid(f"Stabiliser_{side}", grey, C, H, 0.0, 0.7, 0.0, 1.0), comp,
             "Horizontal stabilisers", (0, sign * 4.0, 0.5))
        part(surf_solid(f"Elevator_{side}", ctrl, C, H, 0.7, 1.0, 0.12, 0.95), comp, "Elevators",
             (-2.2, sign * 4.0, 0.5))


GEAR_X, GEAR_Y = -1.2, 3.4


def build_main_gear(sign, comp):
    side = "L" if sign > 0 else "R"
    C = f"Gear_{side}"
    x, y = GEAR_X, sign * GEAR_Y
    chrome, dark = M_("chrome"), M_("brake")
    part(tube(f"Strut_{side}", chrome, C, (x, y, 3.5), (x, y, 1.6), 0.16), comp, "Main strut", (-1.6, 0, 0.3))
    part(tube(f"Piston_{side}", chrome, C, (x, y, 1.62), (x, y, 0.62), 0.11), comp, "Piston", (-2.8, 0, 0.4))
    part(tube(f"Side_brace_{side}", dark, C, (x + 0.1, y + sign * 1.2, 3.45), (x, y, 2.1), 0.06), comp,
         "Side brace and torque links", (0, sign * 1.6, 0.6))
    bm = bmesh.new()
    add_box(bm, (x - 0.22, y, 1.45), (0.35, 0.08, 0.06))
    add_box(bm, (x - 0.22, y, 1.05), (0.35, 0.08, 0.06))
    add_box(bm, (x - 0.38, y, 1.25), (0.06, 0.08, 0.45))
    part(mesh_obj(f"Torque_links_{side}", bm, dark, C, smooth=False), comp,
         "Side brace and torque links", (-3.8, 0, 0.5))
    part(tube(f"Axle_{side}", chrome, C, (x, y - 0.62, 0.62), (x, y + 0.62, 0.62), 0.06), comp, "Axle",
         (-4.8, 0, 0.6))
    for w in (-1, 1):
        wy = y + w * 0.45
        part(cone(f"Brake_{side}{w:+d}", dark, C, (x, wy - w * 0.17, 0.62), (0, w, 0), 0.12, 0.33, 0.33),
             comp, "Brakes", (0, w * 1.0, 0))
        part(cone(f"Hub_{side}{w:+d}", M_("hub"), C, (x, wy - 0.15, 0.62), (0, 1, 0), 0.3, 0.3, 0.3),
             comp, "Wheel hubs", (0, w * 1.9, 0))
        part(torus(f"Tyre_{side}{w:+d}", M_("tyre"), C, Vector((x, wy, 0.62)), 0.42, 0.18, rot=AXIS_Y),
             comp, "Tyres", (0, w * 2.9, 0))
    part(box(f"Gear_door_{side}", M_("paint"), C, (x, y + sign * 0.3, 2.45), (0.95, 0.05, 2.0)), comp,
         "Gear door", (0, sign * 2.2, 0))


def build_nose_gear(comp):
    C = "Gear_nose"
    x = 14.2
    r, zc = fuse_at(x)
    top = zc - r + 0.15
    part(tube("Nose_strut", M_("chrome"), C, (x, 0, top), (x, 0, 0.45), 0.1), comp, "Nose gear", (0, 0, 0))
    part(tube("Nose_axle", M_("chrome"), C, (x, -0.42, 0.45), (x, 0.42, 0.45), 0.05), comp, "Nose gear",
         (0, 0, 0))
    for w in (-1, 1):
        part(torus(f"Nose_tyre{w:+d}", M_("tyre"), C, Vector((x, w * 0.3, 0.45)), 0.3, 0.13, rot=AXIS_Y),
             comp, "Nose gear", (0, 0, 0))


# --------------------------------------------------------------------------
# Studio
# --------------------------------------------------------------------------
def build_studio(scene):
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg is not None:
        bg.inputs["Color"].default_value = srgb("#1C2128")
        bg.inputs["Strength"].default_value = 0.6

    m = bpy.data.materials.new("Floor")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    tc = N.new("ShaderNodeTexCoord")
    grid = N.new("ShaderNodeTexBrick")
    L.new(tc.outputs["Object"], grid.inputs["Vector"])
    grid.offset = 0.0
    grid.inputs["Scale"].default_value = 0.5
    grid.inputs["Mortar Size"].default_value = 0.01
    grid.inputs["Brick Width"].default_value = 1.0
    grid.inputs["Row Height"].default_value = 1.0
    grid.inputs["Color1"].default_value = srgb(COLORS["floor"])
    grid.inputs["Color2"].default_value = srgb("#2D323A")
    grid.inputs["Mortar"].default_value = srgb(COLORS["floor_line"])
    L.new(grid.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.35
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    m["preview"] = COLORS["floor"]
    m["emit"] = 0.0
    bm = bmesh.new()
    add_box(bm, (0, 0, -0.05), (160, 160, 0.1))
    mesh_obj("Floor", bm, m, "Studio", smooth=False)

    # Painted assembly-bay outline
    bm = bmesh.new()
    for (cx, cy, sx, sy) in ((0, 21, 46, 0.25), (0, -21, 46, 0.25), (23, 0, 0.25, 42), (-23, 0, 0.25, 42)):
        add_box(bm, (cx, cy, 0.005), (sx, sy, 0.01))
    mesh_obj("Bay_lines", bm, mat("bay_line", 0, 0.5, emit=1.5), "Studio", smooth=False)

    for name, loc, energy, size, color in (("Key", (24, -26, 30), 60000, 14, (1.0, 0.96, 0.9)),
                                           ("Fill", (-30, -20, 18), 25000, 18, (0.8, 0.88, 1.0)),
                                           ("Rim", (-10, 34, 26), 45000, 14, (0.9, 0.95, 1.0))):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = size
        ld.color = color
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        lo.rotation_mode = "QUATERNION"
        lo.rotation_quaternion = (Vector((0, 0, 3)) - Vector(loc)).to_track_quat("-Z", "Y")
        link(lo, "Studio")


# --------------------------------------------------------------------------
# Timeline
# --------------------------------------------------------------------------
ACT1 = [  # component, arrival offset, start, end, caption
    ("fuselage", (0, 0, 14), 1, 70, "1  Fuselage"),
    ("wing_L", (0, 24, 0), 70, 130, "2  Wings"),
    ("wing_R", (0, -24, 0), 90, 150, "2  Wings"),
    ("engine_L", (10, 14, -0.5), 150, 210, "3  Engines"),
    ("engine_R", (10, -14, -0.5), 165, 225, "3  Engines"),
    ("tail", (-20, 0, 9), 225, 285, "4  Tail"),
    ("gear", (0, 0, -6), 285, 335, "5  Landing gear"),
]
ACT1_END = 400

# component, title, duration, camera position, camera target
ACT2 = [
    ("engine_L", "Engine: turbofan", 260, (10.9, 19.2, 5.6), (1.4, 6.2, 2.6)),
    ("wing_L", "Wing", 260, (14, 24, 16), (-1.0, 9.5, 4.5)),
    ("fuselage", "Fuselage", 300, (8, -44, 15), (0, 0, 5.0)),
    ("tail", "Tail", 240, (-34, -24, 15), (-15.5, 0, 9.0)),
    ("gear", "Main landing gear", 240, (-12.5, 10.5, 1.8), (-3.3, 3.4, 1.2)),
]
FINALE = 80

ACT1_CAMERA = [(1, (34, -40, 20)), (130, (14, -46, 13)), (240, (-24, -40, 15)),
               (335, (-38, -8, 14)), (ACT1_END, (-28, 30, 15))]
ACT1_TARGET = (0, 0, 4)


def schedule():
    """Frame windows for act 2: list of (comp, title, start, end, cam, target)."""
    out, f = [], ACT1_END
    for comp, title, dur, cam, tgt in ACT2:
        out.append((comp, title, f, f + dur, cam, tgt))
        f += dur
    return out, f


def caption(start, end, title, sub=""):
    CAPTIONS.append((start, end, title, sub))


def animate(cam, target):
    # Act 1: component roots fly in
    for comp, off, s, e, cap in ACT1:
        root = COMP_ROOTS[comp]
        key(root, "location", off, 1)
        key(root, "location", off, s)
        key(root, "location", (0, 0, 0), e)
    for cap in sorted({c[4] for c in ACT1}):
        s = min(c[2] for c in ACT1 if c[4] == cap)
        e = max(c[3] for c in ACT1 if c[4] == cap)
        caption(s, e, "Act 1: major components", cap)
    caption(336, ACT1_END, "Assembled", "Twin-engine jet, 38 m long, 37 m span")
    for f, p in ACT1_CAMERA:
        key(cam, "location", p, f)
        key(target, "location", ACT1_TARGET, f)

    # Act 2: each component explodes, then reassembles group by group
    sched, end = schedule()
    for comp, title, F, E, cpos, ctgt in sched:
        key(cam, "location", cpos, F + 40)
        key(target, "location", ctgt, F + 40)
        key(cam, "location", cpos, E - 1)
        key(target, "location", ctgt, E - 1)
        parts = [p for p in PARTS if p["comp"] == comp and p["explode"].length > 0]
        groups = []
        for p in parts:
            if p["group"] not in groups:
                groups.append(p["group"])
        t0, t1 = F + 80, E - 30
        slot = (t1 - t0) / len(groups)
        caption(F, F + 80, f"Act 2: {title}", "Exploded view")
        for gi, g in enumerate(groups):
            gs, ge = round(t0 + gi * slot), round(t0 + (gi + 1) * slot)
            caption(gs, ge, f"Act 2: {title}", f"Step {gi + 1}/{len(groups)}  {g}")
            members = [p for p in parts if p["group"] == g]
            for k, p in enumerate(members):
                stagger = round(min(0.5 * (ge - gs), 3 * k)) if len(members) > 1 else 0
                a, b = gs + stagger, min(ge, gs + stagger + max(10, round(0.6 * (ge - gs))))
                home, out = p["home"], p["home"] + p["explode"]
                key(p["obj"], "location", home, F)
                key(p["obj"], "location", out, F + 50)
                key(p["obj"], "location", out, a)
                key(p["obj"], "location", home, b)
        caption(E - 30, E, f"Act 2: {title}", "Assembled")

    # Finale: wide shot, fans spinning
    caption(end, end + FINALE, "Complete", "Ready for roll-out")
    key(cam, "location", (30, -34, 14), end + 30)
    key(target, "location", ACT1_TARGET, end + 30)
    key(cam, "location", (36, -24, 11), end + FINALE)
    key(target, "location", ACT1_TARGET, end + FINALE)
    for fan in FANS:
        key(fan, "rotation_euler", (0, 0, 0), end)
        key(fan, "rotation_euler", (8 * math.pi, 0, 0), end + FINALE)
    return end + FINALE


def build_camera(scene):
    cd = bpy.data.cameras.new("Camera")
    cd.lens = 35
    cd.clip_end = 1000
    cam = bpy.data.objects.new("Camera", cd)
    link(cam, "Rig")
    target = empty("Cam_target", ACT1_TARGET, "Rig")
    con = cam.constraints.new("TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    scene.camera = cam
    return cam, target


def build_captions(cam):
    """Text objects fixed in the camera view; each one is visible only in its window."""
    tm = mat("caption", 0, 0.5, emit=1.0)
    for i, (s, e, title, sub) in enumerate(CAPTIONS):
        for j, (txt, size, y) in enumerate(((title, 0.05, -0.33), (sub, 0.034, -0.385))):
            if not txt:
                continue
            cu = bpy.data.curves.new(f"Caption{i}_{j}", "FONT")
            cu.body = txt
            cu.size = size
            o = bpy.data.objects.new(f"Caption{i}_{j}", cu)
            o.data.materials.append(tm)
            o.parent = cam
            o.location = (-0.74, y, -1.5)
            link(o, "Captions")
            if s > 1:
                key(o, "scale", (0, 0, 0), s - 1)
            key(o, "scale", (1, 1, 1), s)
            key(o, "scale", (1, 1, 1), e - 1)
            key(o, "scale", (0, 0, 0), e)
            set_constant(o)


def set_constant(obj):
    """Hard on/off for captions (no fade). Skipped quietly where the API differs."""
    try:
        for fc in obj.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
    except (AttributeError, TypeError):
        pass


def setup_render(scene, end):
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    r = scene.render
    r.resolution_x, r.resolution_y = 1920, 1080
    r.fps = FPS
    scene.frame_start, scene.frame_end = 1, end
    for target, attr, val in ((scene.eevee, "use_gtao", True), (scene.eevee, "use_ssr", True),
                              (scene.eevee, "use_raytracing", True),
                              (scene.eevee, "taa_render_samples", 64),
                              (scene.eevee, "use_soft_shadows", True)):
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


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def reset_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for blocks in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
                   bpy.data.curves):
        for b in list(blocks):
            if b.users == 0:
                blocks.remove(b)
    for c in list(bpy.context.scene.collection.children):
        bpy.context.scene.collection.children.unlink(c)


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
    for comp in ("fuselage", "wing_L", "wing_R", "engine_L", "engine_R", "tail", "gear"):
        COMP_ROOTS[comp] = empty(f"COMP_{comp}", (0, 0, 0), "Rig")
    build_studio(scene)
    build_fuselage()
    build_wing(1)
    build_wing(-1)
    build_engine(1)
    build_engine(-1)
    build_tail()
    build_main_gear(1, "gear")
    n = len(PARTS)
    build_main_gear(-1, "gear")
    for p in PARTS[n:]:          # only the left main gear is taken apart in act 2
        p["explode"] = Vector((0, 0, 0))
    build_nose_gear("gear")
    cam, target = build_camera(scene)
    end = animate(cam, target)
    build_captions(cam)
    setup_render(scene, end)
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
    print("Jet Assembly built:", len(bpy.data.objects), "objects,", len(PARTS), "parts,", end, "frames")


if __name__ == "__main__":
    main()
