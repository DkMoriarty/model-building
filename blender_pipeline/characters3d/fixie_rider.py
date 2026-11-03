"""CH_FixieRider: an original stylised 3D character on a fixed-gear bike.

Look: soft 3D-render character design - very long thin legs, oversized boxy
streetwear (sage work shirt, baggy charcoal shorts, tall white socks, chunky
cream sneakers), a rust cap over short twists, a crossbody bag; studio-white
backdrop with soft shadows.

Built entirely in code (Blender 4.3+/5.0):
- every body and clothing part is a lofted tube (`tube`) or a scaled sphere,
  smoothed with Subdivision Surface, and parented to one bone of the rig;
- the bike is tubes and tori; its crank turns, and the rider's feet (IK
  targets) ride the pedals, hands (IK) hold the bars, so pedalling is real.

    blender -b -P blender_pipeline/characters3d/fixie_rider.py -- --out renders/fixie --views sheet,ride,loop
"""

import argparse
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

# ---------------------------------------------------------------------------
# Palette (sRGB hex -> linear)
# ---------------------------------------------------------------------------


def hx(c, a=1.0):
    c = c.lstrip("#")
    v = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in v) + (a,)


COL = {
    "skin": hx("#a96a47"), "skin_dark": hx("#7d4a30"), "lip": hx("#8e4b3a"),
    "hair": hx("#1f1613"), "eye_white": hx("#f3efe9"), "iris": hx("#2a1b14"),
    "shirt": hx("#8ea383"), "shirt_seam": hx("#6f8566"),
    "shorts": hx("#2c2c31"), "sock": hx("#f1efea"), "shoe": hx("#e7e1d3"), "sole": hx("#b88654"),
    "lace": hx("#f7f5f0"), "cap": hx("#c0582b"), "bag": hx("#1e1e21"), "strap": hx("#2d2d31"),
    "frame": hx("#2f4a6b"), "rim": hx("#151518"), "tire": hx("#1c1c1e"), "metal": hx("#b9bcc4"),
    "saddle": hx("#2a2320"), "tape": hx("#d9cfbf"), "chain": hx("#5d6068"),
    "floor": hx("#d9d6d1"), "bg": hx("#e2dfda"),
}
_MAT = {}


def mat(name, roughness=0.6, sheen=0.0, metallic=0.0, sss=0.0):
    """Soft, slightly matte materials like a clay-toy render."""
    if name in _MAT:
        return _MAT[name]
    m = bpy.data.materials.new(f"FR_{name}")
    if getattr(m, "node_tree", None) is None and hasattr(m, "use_nodes"):
        m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = COL[name]
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = sheen
    if sss and "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = sss
        bsdf.inputs["Subsurface Radius"].default_value = (0.08, 0.03, 0.02)
        if "Subsurface Scale" in bsdf.inputs:
            bsdf.inputs["Subsurface Scale"].default_value = 0.05
    m.diffuse_color = COL[name]
    _MAT[name] = m
    return m


# ---------------------------------------------------------------------------
# Geometry builders
# ---------------------------------------------------------------------------

COLL = None


def _link(ob):
    (COLL or bpy.context.scene.collection).objects.link(ob)
    return ob


def tube(name, path, radii, material, ring=12, caps=True, side=Vector((1, 0, 0)), subdiv=2):
    """Loft a closed tube along `path` (list of 3D points). radii: a list of
    r or (r_side, r_front) per path point - elliptical rings for boxy clothes.
    Smooth-shaded with Subdivision Surface."""
    pts = [Vector(p) for p in path]
    verts, faces = [], []
    n = len(pts)
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        u = (side - t * side.dot(t))
        if u.length < 1e-4:
            u = Vector((0, 1, 0)) - t * t.y
        u.normalize()
        v = t.cross(u)
        r = radii[i]
        ru, rv = (r, r) if not isinstance(r, (tuple, list)) else r
        for k in range(ring):
            a = 2 * math.pi * k / ring
            verts.append(p + u * (ru * math.cos(a)) + v * (rv * math.sin(a)))
    for i in range(n - 1):
        for k in range(ring):
            a, b = i * ring + k, i * ring + (k + 1) % ring
            faces.append((a, b, b + ring, a + ring))
    if caps:
        c0 = len(verts)
        verts.append(pts[0] - (pts[1] - pts[0]).normalized() * 0.002)
        verts.append(pts[-1] + (pts[-1] - pts[-2]).normalized() * 0.002)
        for k in range(ring):
            faces.append((c0, (k + 1) % ring, k))
            faces.append((c0 + 1, (n - 1) * ring + k, (n - 1) * ring + (k + 1) % ring))
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.materials.append(material)
    ob = _link(bpy.data.objects.new(name, me))
    _smooth(ob, subdiv)
    return ob


def blob(name, center, scale, material, rot=(0, 0, 0), subdiv=2, segments=16):
    me = bpy.data.meshes.new(name)
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=segments // 2, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    ob = _link(bpy.data.objects.new(name, me))
    ob.location, ob.scale, ob.rotation_euler = center, scale, rot
    _smooth(ob, subdiv)
    return ob


def box(name, center, size, material, bevel=0.02, rot=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    ob = _link(bpy.data.objects.new(name, me))
    ob.location, ob.scale, ob.rotation_euler = center, size, rot
    m = ob.modifiers.new("Bevel", "BEVEL")
    m.width, m.segments = bevel, 4
    m.affect = "EDGES"
    if hasattr(m, "use_clamp_overlap"):
        m.use_clamp_overlap = False
    for p in me.polygons:
        p.use_smooth = True
    return ob


def torus(name, center, major, minor, material, axis="X", seg=48):
    me = bpy.data.meshes.new(name)
    verts, faces = [], []
    ring = 10
    for i in range(seg):
        a = 2 * math.pi * i / seg
        for k in range(ring):
            b = 2 * math.pi * k / ring
            r = major + minor * math.cos(b)
            verts.append((r * math.cos(a), r * math.sin(a), minor * math.sin(b)))
    for i in range(seg):
        for k in range(ring):
            a, b = i * ring + k, i * ring + (k + 1) % ring
            c, d = ((i + 1) % seg) * ring + (k + 1) % ring, ((i + 1) % seg) * ring + k
            faces.append((a, b, c, d))
    me.from_pydata(verts, [], faces)
    me.materials.append(material)
    for p in me.polygons:
        p.use_smooth = True
    ob = _link(bpy.data.objects.new(name, me))
    ob.location = center
    ob.rotation_euler = {"X": (0, math.radians(90), 0), "Y": (math.radians(90), 0, 0), "Z": (0, 0, 0)}[axis]
    return ob


def disc(name, center, radius, depth, material, axis="X", verts=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=center)
    ob = bpy.context.object
    for c in ob.users_collection:
        c.objects.unlink(ob)
    _link(ob)
    ob.name = name
    ob.data.materials.append(material)
    ob.rotation_euler = {"X": (0, math.radians(90), 0), "Y": (math.radians(90), 0, 0), "Z": (0, 0, 0)}[axis]
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def _smooth(ob, levels):
    for p in ob.data.polygons:
        p.use_smooth = True
    if levels:
        m = ob.modifiers.new("Subsurf", "SUBSURF")
        m.levels = m.render_levels = levels


def arc(p0, p1, bulge=Vector((0, 0, 0)), n=6):
    """Points from p0 to p1 bowing by `bulge` at the middle."""
    p0, p1 = Vector(p0), Vector(p1)
    return [p0.lerp(p1, i / (n - 1)) + bulge * math.sin(math.pi * i / (n - 1)) for i in range(n)]


# ---------------------------------------------------------------------------
# Rig (Z up, the rider faces -Y; the bike runs along Y, front = -Y)
# ---------------------------------------------------------------------------

J = {  # joint positions in the standing rest pose (metres)
    "hip": (0, 0, 1.00), "chest": (0, 0, 1.40), "neck": (0, 0.0, 1.47), "head": (0, -0.01, 1.78),
    "hip_L": (0.095, 0, 0.98), "knee_L": (0.105, -0.01, 0.53), "ankle_L": (0.11, 0.02, 0.10), "toe_L": (0.115, -0.15, 0.04),
    "sho_L": (0.20, 0.0, 1.37), "elb_L": (0.26, 0.02, 1.10), "wri_L": (0.28, 0.0, 0.86), "hand_L": (0.285, -0.01, 0.77),
}
for k in list(J):
    if k.endswith("_L"):
        x, y, z = J[k]
        J[k[:-2] + "_R"] = (-x, y, z)

BONES = [  # name, head joint, tail joint, parent
    ("Root", (0, 0, 0), (0, 0, 0.2), None),
    ("Pelvis", "hip", (0, 0, 1.12), "Root"),
    ("Spine", (0, 0, 1.12), "chest", "Pelvis"),
    ("Neck", "chest", "neck", "Spine"),
    ("Head", "neck", "head", "Neck"),
]
for s in "LR":
    BONES += [(f"Thigh_{s}", f"hip_{s}", f"knee_{s}", "Pelvis"), (f"Shin_{s}", f"knee_{s}", f"ankle_{s}", f"Thigh_{s}"),
              (f"Foot_{s}", f"ankle_{s}", f"toe_{s}", f"Shin_{s}"),
              (f"UpperArm_{s}", f"sho_{s}", f"elb_{s}", "Spine"), (f"Forearm_{s}", f"elb_{s}", f"wri_{s}", f"UpperArm_{s}"),
              (f"Hand_{s}", f"wri_{s}", f"hand_{s}", f"Forearm_{s}")]


def jp(j):
    return Vector(J[j]) if isinstance(j, str) else Vector(j)


def build_rig(name="FR_Rig"):
    arm = bpy.data.armatures.new(name)
    rig = _link(bpy.data.objects.new(name, arm))
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones
    for name, h, t, par in BONES:
        b = eb.new(name)
        b.head, b.tail = jp(h), jp(t)
        if par:
            b.parent = eb[par]
            b.use_connect = (eb[par].tail - b.head).length < 1e-4
    for s, sx in (("L", 1), ("R", -1)):
        # IK controls: foot target at the ankle, pole in front of the knee;
        # hand target at the wrist, pole behind the elbow.
        t = eb.new(f"IK_Foot_{s}")
        t.head, t.tail = jp(f"ankle_{s}"), jp(f"ankle_{s}") + Vector((0, -0.12, 0))
        t.parent = eb["Root"]
        p = eb.new(f"Pole_Knee_{s}")
        p.head = jp(f"knee_{s}") + Vector((0, -0.5, 0))
        p.tail = p.head + Vector((0, -0.05, 0))
        p.parent = eb["Root"]
        h = eb.new(f"IK_Hand_{s}")
        h.head, h.tail = jp(f"wri_{s}"), jp(f"wri_{s}") + Vector((0, -0.08, 0))
        h.parent = eb["Root"]
        e = eb.new(f"Pole_Elbow_{s}")
        e.head = jp(f"elb_{s}") + Vector((sx * 0.2, 0.45, 0))
        e.tail = e.head + Vector((0, 0.05, 0))
        e.parent = eb["Root"]
    bpy.ops.object.mode_set(mode="OBJECT")
    for s in "LR":
        for bone, tgt, pole, chain in ((f"Shin_{s}", f"IK_Foot_{s}", f"Pole_Knee_{s}", 2),
                                       (f"Forearm_{s}", f"IK_Hand_{s}", f"Pole_Elbow_{s}", 2)):
            c = rig.pose.bones[bone].constraints.new("IK")
            c.target, c.subtarget = rig, tgt
            c.pole_target, c.pole_subtarget = rig, pole
            c.chain_count = chain
            c.pole_angle = _solve_pole(rig, bone, c)
        # The foot keeps the target's orientation (flat on the pedal).
        cr = rig.pose.bones[f"Foot_{s}"].constraints.new("COPY_ROTATION")
        cr.target, cr.subtarget = rig, f"IK_Foot_{s}"
        cr.mix_mode = "BEFORE" if hasattr(cr, "mix_mode") else cr.mix_mode
        cr.influence = 0.0  # enabled only while riding
    rig.show_in_front = True
    rig.hide_render = True
    return rig


def _solve_pole(rig, bone, c):
    """Pole angle that keeps the chain in its rest pose (measured)."""
    pb = rig.pose.bones[bone]
    chain = [pb] + [pb.parent]
    rest = [rig.data.bones[b.name].tail_local.copy() for b in chain]

    def err(a):
        c.pole_angle = a
        bpy.context.view_layer.update()
        return sum((b.tail - r).length for b, r in zip(chain, rest))
    best = min((math.radians(d) for d in range(-180, 180, 10)), key=err)
    a = best - math.radians(10)
    while a <= best + math.radians(10):
        if err(a) < err(best):
            best = a
        a += math.radians(1)
    c.pole_angle = best
    return best


def skin_chain(ob, rig, bones, blend=0.05):
    """Deform one continuous limb mesh along a chain of bones, weights
    blending smoothly across each joint (no wooden-doll hinge). Armature
    deform runs before the subdivision, so the bend stays round."""
    heads = [rig.data.bones[b].head_local for b in bones] + [rig.data.bones[bones[-1]].tail_local]
    seg = [(heads[i + 1] - heads[i]).length for i in range(len(bones))]
    joints = [sum(seg[:i]) for i in range(1, len(bones))]
    groups = [ob.vertex_groups.new(name=b) for b in bones]
    for v in ob.data.vertices:
        p = v.co
        best, s_best, acc = None, 0.0, 0.0
        for i in range(len(bones)):
            a, b = heads[i], heads[i + 1]
            ab = b - a
            t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
            d = (a + ab * t - p).length
            if best is None or d < best:
                best, s_best = d, acc + t * seg[i]
            acc += seg[i]
        w = [1.0] + [0.0] * (len(bones) - 1)
        for k, js in enumerate(joints):
            u = max(0.0, min(1.0, (s_best - js + blend) / (2 * blend)))
            f = u * u * (3 - 2 * u)
            w[k + 1] += w[k] * f
            w[k] *= 1 - f
        for g, wi in zip(groups, w):
            if wi > 1e-4:
                g.add([v.index], wi, "REPLACE")
    m = ob.modifiers.new("Rig", "ARMATURE")
    m.object = rig
    ob.modifiers.move(len(ob.modifiers) - 1, 0)
    ob.parent = rig
    return ob


def bind(ob, rig, bone):
    """Rigid bind: the part rides its bone (keeps its world placement)."""
    bpy.context.view_layer.update()  # apply location/scale set just before
    mw = ob.matrix_world.copy()
    ob.parent, ob.parent_type, ob.parent_bone = rig, "BONE", bone
    bpy.context.view_layer.update()
    ob.matrix_world = mw
    return ob


# ---------------------------------------------------------------------------
# The character
# ---------------------------------------------------------------------------

def build_character(rig):
    parts = []

    def add(ob, bone):
        bind(ob, rig, bone)
        parts.append(ob)
        return ob

    skin = mat("skin", 0.55, sss=0.25)
    # Legs: very long and thin, a little knob at the knee, bare between shorts and socks.
    for s in "LR":
        hip, knee, ank = jp(f"hip_{s}"), jp(f"knee_{s}"), jp(f"ankle_{s}")
        leg = arc(hip, knee, n=5)[:-1] + [knee] + arc(knee, ank, Vector((0, 0.012, 0)), n=6)[1:]
        radii = [0.058, 0.052, 0.047, 0.042, 0.04, 0.041, 0.039, 0.033, 0.028, 0.026]
        parts.append(skin_chain(tube(f"Leg_{s}", leg, radii, skin), rig, [f"Thigh_{s}", f"Shin_{s}"], blend=0.06))
        # Tall ribbed socks.
        sock_top = ank.lerp(knee, 0.42)
        add(tube(f"Sock_{s}", arc(ank + Vector((0, 0, -0.02)), sock_top, n=4), [0.033, 0.031, 0.034, 0.037],
                 mat("sock", 0.9, sheen=0.4)), f"Shin_{s}")
        add(tube(f"SockCuff_{s}", [sock_top - Vector((0, 0, 0.012)), sock_top + Vector((0, 0, 0.012))], [0.039, 0.039],
                 mat("sock", 0.9, sheen=0.4), subdiv=1), f"Shin_{s}")
        for k in range(2):  # two sport stripes on the sock
            zz = sock_top - (sock_top - ank) * (0.12 + 0.1 * k)
            add(tube(f"SockStripe_{s}{k}", [zz - Vector((0, 0, 0.005)), zz + Vector((0, 0, 0.005))], [0.0365, 0.0365],
                     mat("frame", 0.6), caps=False, subdiv=1), f"Shin_{s}")
        # Chunky sneaker: lofted upper, a thick gum sole, a tongue and laces.
        x = jp(f"ankle_{s}").x
        upper = [(x, 0.09, 0.075), (x, 0.06, 0.085), (x, 0.0, 0.08), (x, -0.07, 0.065), (x, -0.14, 0.05), (x, -0.185, 0.04)]
        add(tube(f"Shoe_{s}", upper, [(0.055, 0.04), (0.06, 0.05), (0.064, 0.05), (0.066, 0.045), (0.06, 0.035),
                                      (0.04, 0.025)], mat("shoe", 0.7), side=Vector((1, 0, 0))), f"Foot_{s}")
        add(tube(f"Sole_{s}", [(x, 0.105, 0.03), (x, 0.0, 0.026), (x, -0.12, 0.022), (x, -0.2, 0.024)],
                 [(0.058, 0.022), (0.066, 0.02), (0.066, 0.02), (0.042, 0.018)], mat("sole", 0.8)), f"Foot_{s}")
        # Side swoosh-free stripe and a heel tab.
        add(tube(f"ShoeStripe_{s}", [(x + (0.064 if x > 0 else -0.064), 0.05, 0.06), (x + (0.066 if x > 0 else -0.066), -0.02, 0.07),
                                     (x + (0.062 if x > 0 else -0.062), -0.1, 0.055)], [0.008] * 3, mat("cap", 0.6), subdiv=1),
            f"Foot_{s}")
        add(box(f"HeelTab_{s}", (x, 0.11, 0.1), (0.035, 0.015, 0.05), mat("cap", 0.6), bevel=0.006), f"Foot_{s}")
        for k in range(4):
            yy = -0.005 - 0.03 * k
            add(box(f"Lace_{s}{k}", (x, yy, 0.118 - 0.012 * k), (0.06, 0.008, 0.008), mat("lace", 0.8), bevel=0.003,
                    rot=(math.radians(-25), 0, 0)), f"Foot_{s}")
    # Baggy shorts: wide legs to just above the knee, a soft waistband.
    sh = mat("shorts", 0.85, sheen=0.2)
    add(blob("Hips", (0, 0.005, 0.985), (0.17, 0.12, 0.12), sh), "Pelvis")
    for sx in (1, -1):  # drawstrings hanging below the shirt hem
        add(tube(f"Drawstring{sx}", [(sx * 0.03, -0.12, 0.9), (sx * 0.035, -0.125, 0.84), (sx * 0.03, -0.12, 0.8)],
                 [0.005] * 3, mat("lace", 0.6), subdiv=1), "Pelvis")
    for s in "LR":
        hip, knee = jp(f"hip_{s}"), jp(f"knee_{s}")
        hem = hip.lerp(knee, 0.62)
        add(tube(f"ShortLeg_{s}", arc(hip + Vector((0, 0, 0.03)), hem, n=4), [(0.1, 0.1), (0.105, 0.1), (0.108, 0.098),
                                                                             (0.104, 0.094)], sh, caps=False, subdiv=1),
            f"Thigh_{s}")
        add(tube(f"ShortHem_{s}", [hem + Vector((0, 0, -0.01)), hem + Vector((0, 0, 0.02))], [(0.107, 0.097), (0.107, 0.097)],
                 mat("strap", 0.85), caps=False, subdiv=1), f"Thigh_{s}")
    # Boxy oversized work shirt: wide dropped shoulders, short wide sleeves, a collar.
    shirt = mat("shirt", 0.8, sheen=0.3)
    body = [(0, 0.01, 0.9), (0, 0.01, 1.0), (0, 0.0, 1.15), (0, 0.0, 1.3), (0, 0.0, 1.4), (0, 0.0, 1.45)]
    add(tube("Shirt", body, [(0.22, 0.155), (0.235, 0.16), (0.235, 0.155), (0.235, 0.15), (0.21, 0.13), (0.1, 0.08)],
             shirt), "Spine")
    add(tube("ShirtHem", [(0, 0.01, 0.885), (0, 0.01, 0.905)], [(0.226, 0.16), (0.226, 0.16)], shirt, subdiv=1), "Pelvis")
    add(tube("Collar", [(0, 0.0, 1.43), (0, 0.005, 1.475)], [(0.075, 0.065), (0.07, 0.06)], mat("shirt_seam", 0.8),
             caps=False, subdiv=1), "Spine")
    add(tube("Placket", [(0, -0.155, 0.92), (0, -0.152, 1.42)], [0.012, 0.012], mat("shirt_seam", 0.8), subdiv=1), "Spine")
    for k in range(4):
        add(blob(f"Button{k}", (0, -0.165, 1.0 + 0.11 * k), (0.008, 0.004, 0.008), mat("lace", 0.4), subdiv=1), "Spine")
    # Detailing: a chest pocket with a flap and pen, collar points, side seams.
    add(box("Pocket", (-0.09, -0.158, 1.27), (0.075, 0.008, 0.085), mat("shirt", 0.8, sheen=0.3), bevel=0.006), "Spine")
    add(box("PocketFlap", (-0.09, -0.166, 1.31), (0.08, 0.01, 0.025), mat("shirt_seam", 0.8), bevel=0.006), "Spine")
    add(tube("Pen", [(-0.07, -0.165, 1.29), (-0.07, -0.166, 1.35)], [0.006, 0.006], mat("cap", 0.4), subdiv=1), "Spine")
    for sx in (1, -1):
        add(box(f"CollarPt{sx}", (sx * 0.04, -0.06, 1.445), (0.06, 0.012, 0.035), mat("shirt_seam", 0.8), bevel=0.006,
                rot=(math.radians(-30), 0, math.radians(sx * 25))), "Spine")
    for s, sx in (("L", 1), ("R", -1)):
        sho, elb = jp(f"sho_{s}"), jp(f"elb_{s}")
        end = sho.lerp(elb, 0.75)
        add(tube(f"Sleeve_{s}", arc(sho + Vector((-sx * 0.04, 0, 0.0)), end, n=4), [(0.11, 0.1), (0.115, 0.105),
                                                                                    (0.112, 0.102), (0.105, 0.098)],
                 shirt, caps=False), f"UpperArm_{s}")
        # Rolled sleeve cuff.
        d = (end - sho).normalized()
        add(tube(f"Cuff_{s}", [end - d * 0.01, end + d * 0.025], [(0.112, 0.104), (0.11, 0.102)], mat("shirt_seam", 0.8),
                 caps=False, subdiv=1), f"UpperArm_{s}")
        # Thin arms, mitten hands with a thumb.
        wri, hand = jp(f"wri_{s}"), jp(f"hand_{s}")
        armpts = arc(sho.lerp(elb, 0.3), elb, n=3)[:-1] + [elb] + arc(elb, wri, n=4)[1:]
        parts.append(skin_chain(tube(f"Arm_{s}", armpts, [0.036, 0.034, 0.032, 0.033, 0.03, 0.026], skin), rig,
                                [f"UpperArm_{s}", f"Forearm_{s}"], blend=0.05))
        add(blob(f"Hand_{s}", wri.lerp(hand, 0.55), (0.03, 0.022, 0.055), skin), f"Hand_{s}")
        add(blob(f"Thumb_{s}", wri.lerp(hand, 0.35) + Vector((0, -0.026, 0)), (0.011, 0.011, 0.026), skin,
                 rot=(math.radians(-25), 0, 0)), f"Hand_{s}")
    # Crossbody bag: strap from the right shoulder to the left hip, bag at the hip.
    add(tube("Strap", [(-0.16, 0.0, 1.43), (-0.13, -0.13, 1.33), (0.0, -0.165, 1.16), (0.13, -0.168, 1.0),
                       (0.2, -0.13, 0.93)], [0.012] * 5, mat("strap", 0.7), side=Vector((0, 1, 0)), subdiv=1), "Spine")
    add(tube("StrapBack", [(-0.16, 0.0, 1.43), (-0.1, 0.13, 1.3), (0.05, 0.16, 1.1), (0.2, 0.12, 0.95)], [0.012] * 4,
             mat("strap", 0.7), side=Vector((0, 1, 0)), subdiv=1), "Spine")
    add(box("Bag", (0.22, -0.11, 0.9), (0.075, 0.2, 0.13), mat("bag", 0.55, sheen=0.2), bevel=0.03,
            rot=(0, 0, math.radians(-20))), "Pelvis")
    add(box("BagZip", (0.258, -0.12, 0.93), (0.006, 0.17, 0.008), mat("metal", 0.3, metallic=0.8), bevel=0.003,
            rot=(0, 0, math.radians(-20))), "Pelvis")
    # Neck and head: an oval head, big ears, a broad nose, big eyes, a grin.
    add(tube("Neck", [(0, 0.01, 1.42), (0, 0.0, 1.53)], [0.045, 0.043], skin), "Neck")
    hc = Vector((0, -0.01, 1.64))
    add(blob("Head", hc, (0.118, 0.125, 0.148), skin), "Head")
    add(blob("Jaw", hc + Vector((0, -0.03, -0.075)), (0.088, 0.085, 0.07), skin), "Head")
    for sx in (1, -1):
        add(blob(f"Ear{sx}", hc + Vector((sx * 0.118, 0.01, -0.005)), (0.022, 0.03, 0.04), skin), "Head")
        # Big, friendly eyes set into the face, below the brim's shadow.
        eye = hc + Vector((sx * 0.05, -0.105, -0.004))
        add(blob(f"Eye{sx}", eye, (0.032, 0.016, 0.03), mat("eye_white", 0.3), subdiv=1), "Head")
        add(blob(f"Iris{sx}", eye + Vector((-sx * 0.003, -0.012, -0.002)), (0.019, 0.007, 0.022), mat("iris", 0.2),
                 subdiv=1), "Head")
        add(blob(f"Glint{sx}", eye + Vector((-sx * 0.009, -0.02, 0.008)), (0.005, 0.002, 0.005), mat("eye_white", 0.1),
                 subdiv=0, segments=8), "Head")
        add(tube(f"Lid{sx}", [eye + Vector((-sx * 0.033, -0.006, 0.006)), eye + Vector((0, -0.016, 0.03)),
                              eye + Vector((sx * 0.033, -0.006, 0.01))], [0.004, 0.005, 0.004], mat("hair", 0.6),
                 subdiv=1), "Head")
        add(tube(f"Brow{sx}", [eye + Vector((-sx * 0.026, -0.008, 0.048)), eye + Vector((sx * 0.004, -0.012, 0.058)),
                               eye + Vector((sx * 0.03, -0.004, 0.052))], [0.006, 0.008, 0.005], mat("hair", 0.7),
                 subdiv=1), "Head")
    add(blob("Nose", hc + Vector((0, -0.13, -0.035)), (0.022, 0.02, 0.022), skin), "Head")
    smile = [hc + Vector((x, -0.112 + 6 * x * x, -0.075 + 14 * x * x)) for x in (-0.045, -0.025, 0.0, 0.025, 0.045)]
    add(tube("Smile", smile, [0.004, 0.007, 0.008, 0.007, 0.004], mat("lip", 0.5), side=Vector((0, 1, 0)), subdiv=1),
        "Head")
    # Short twists peeking out under the cap.
    import random
    rnd = random.Random(3)
    for i in range(22):
        a = math.radians(-112 + i * 224 / 21)       # back and sides only (a=0 is the back of the head)
        r = 0.122
        base = hc + Vector((r * math.sin(a), r * math.cos(a) * 1.02, 0.045 + rnd.uniform(-0.01, 0.01)))
        tip = base + Vector((0.55 * (base.x - hc.x), 0.55 * (base.y - hc.y), -0.05 - rnd.uniform(0, 0.02)))
        add(tube(f"Twist{i}", [base, base.lerp(tip, 0.5), tip], [0.016, 0.014, 0.008], mat("hair", 0.7), subdiv=1),
            "Head")
    # Rust cap: crown and a curved brim.
    add(blob("CapCrown", hc + Vector((0, 0.005, 0.072)), (0.128, 0.134, 0.09), mat("cap", 0.75, sheen=0.3)), "Head")
    add(box("CapBand", hc + Vector((0, 0.005, 0.06)), (0.25, 0.26, 0.03), mat("cap", 0.75, sheen=0.3), bevel=0.012),
        "Head").hide_render = True
    add(blob("CapBrim", hc + Vector((0, -0.16, 0.05)), (0.1, 0.07, 0.012), mat("cap", 0.75, sheen=0.3),
             rot=(math.radians(-8), 0, 0)), "Head")
    add(blob("CapButton", hc + Vector((0, 0.005, 0.162)), (0.012, 0.012, 0.008), mat("cap", 0.75), subdiv=1), "Head")
    return parts


# ---------------------------------------------------------------------------
# The fixed-gear bike (along Y, front wheel at -Y)
# ---------------------------------------------------------------------------

BIKE = {
    "rear": Vector((0, 0.52, 0.34)), "front": Vector((0, -0.5, 0.34)), "bb": Vector((0, 0.06, 0.29)),
    "seat_top": Vector((0, 0.22, 0.86)), "head_top": Vector((0, -0.36, 0.86)), "head_bot": Vector((0, -0.4, 0.71)),
    "saddle": Vector((0, 0.25, 0.92)), "bar": Vector((0, -0.47, 0.98)), "crank": 0.17, "wheel_r": 0.34,
}


def build_bike():
    obs = {}
    fr = mat("frame", 0.35, metallic=0.2)
    B = BIKE
    def t(name, a, b, r, m=fr):
        obs[name] = tube(name, [a, (a + b) / 2, b], [r, r, r], m, subdiv=1)
    t("TopTube", B["seat_top"], B["head_top"], 0.016)
    t("DownTube", B["bb"], B["head_bot"], 0.019)
    t("SeatTube", B["bb"], B["seat_top"] + Vector((0, 0.01, 0.03)), 0.017)
    t("HeadTube", B["head_bot"] + Vector((0, 0.008, -0.04)), B["head_top"] + Vector((0, -0.006, 0.03)), 0.02)
    for sx in (1, -1):
        off = Vector((sx * 0.035, 0, 0))
        t(f"ChainStay{sx}", B["bb"] + off * 0.5, B["rear"] + off, 0.011)
        t(f"SeatStay{sx}", B["seat_top"] + off * 0.4 + Vector((0, 0, -0.03)), B["rear"] + off, 0.009)
        t(f"Fork{sx}", B["head_bot"] + off * 0.6 + Vector((0, 0, -0.04)), B["front"] + off + Vector((0, -0.02, 0)), 0.012)
    # Stem and a flat riser bar with tan grips.
    t("Stem", B["head_top"] + Vector((0, 0, 0.03)), B["bar"] + Vector((0, 0.03, -0.01)), 0.014, mat("metal", 0.3, metallic=0.9))
    obs["Bar"] = tube("Bar", [B["bar"] + Vector((-0.26, 0.03, 0.02)), B["bar"] + Vector((-0.08, 0, 0)), B["bar"],
                              B["bar"] + Vector((0.08, 0, 0)), B["bar"] + Vector((0.26, 0.03, 0.02))], [0.012] * 5,
                      mat("metal", 0.3, metallic=0.9), side=Vector((0, 1, 0)), subdiv=1)
    for sx in (1, -1):
        g = B["bar"] + Vector((sx * 0.22, 0.026, 0.017))
        obs[f"Grip{sx}"] = tube(f"Grip{sx}", [g - Vector((sx * 0.05, 0, 0)), g + Vector((sx * 0.05, 0, 0))], [0.017, 0.017],
                                mat("tape", 0.8), side=Vector((0, 1, 0)), subdiv=1)
    # Saddle and post.
    t("SeatPost", B["seat_top"], B["saddle"] + Vector((0, 0.0, -0.02)), 0.012, mat("metal", 0.3, metallic=0.9))
    obs["Saddle"] = tube("Saddle", [B["saddle"] + Vector((0, 0.08, 0.005)), B["saddle"], B["saddle"] + Vector((0, -0.12, -0.005))],
                         [(0.07, 0.022), (0.05, 0.02), (0.02, 0.016)], mat("saddle", 0.5), side=Vector((1, 0, 0)), subdiv=2)
    # Wheels: deep black rims, tyres, hubs and a few spokes.
    for name, c in (("Rear", B["rear"]), ("Front", B["front"])):
        w = bpy.data.objects.new(f"Wheel{name}", None)
        _link(w)
        w.location = c
        parts = [torus(f"Tire{name}", (0, 0, 0), B["wheel_r"] - 0.012, 0.016, mat("tire", 0.9), axis="X"),
                 torus(f"Rim{name}", (0, 0, 0), B["wheel_r"] - 0.045, 0.024, mat("rim", 0.4, metallic=0.3), axis="X"),
                 disc(f"Hub{name}", (0, 0, 0), 0.03, 0.08, mat("metal", 0.3, metallic=0.9), axis="X")]
        for k in range(8):
            a = 2 * math.pi * k / 8
            p = Vector((0, math.cos(a), math.sin(a))) * (B["wheel_r"] - 0.06)
            parts.append(tube(f"Spoke{name}{k}", [Vector((0, 0, 0)), p], [0.0025, 0.0025], mat("metal", 0.3, metallic=0.9),
                              side=Vector((1, 0, 0)), subdiv=0, ring=6))
        for p in parts:
            p.parent = w
        obs[f"Wheel{name}"] = w
    # Crank: chainring, arms and pedals on an empty that turns.
    crank = bpy.data.objects.new("Crank", None)
    _link(crank)
    crank.location = B["bb"]
    ring = torus("Chainring", (0.045, 0, 0), 0.1, 0.008, mat("metal", 0.3, metallic=0.9), axis="X")
    ring.parent = crank
    cog = torus("Cog", B["rear"] + Vector((0.045, 0, 0)), 0.035, 0.006, mat("metal", 0.3, metallic=0.9), axis="X")
    obs["Cog"] = cog
    obs["Chain"] = tube("Chain", [B["bb"] + Vector((0.045, 0, 0.1)), B["rear"] + Vector((0.045, 0, 0.035))], [0.004, 0.004],
                        mat("chain", 0.5, metallic=0.6), subdiv=0, ring=6)
    obs["Chain2"] = tube("Chain2", [B["bb"] + Vector((0.045, 0, -0.1)), B["rear"] + Vector((0.045, 0, -0.035))], [0.004, 0.004],
                         mat("chain", 0.5, metallic=0.6), subdiv=0, ring=6)
    for sx, a in ((1, 0.0), (-1, math.pi)):
        arm_end = Vector((sx * 0.07, B["crank"] * math.sin(a), -B["crank"] * math.cos(a)))
        arm = tube(f"CrankArm{sx}", [Vector((sx * 0.06, 0, 0)), arm_end], [0.012, 0.01], mat("metal", 0.3, metallic=0.9),
                   subdiv=1)
        arm.parent = crank
        pedal = bpy.data.objects.new(f"Pedal{sx}", None)
        _link(pedal)
        pedal.parent = crank
        pedal.location = arm_end + Vector((sx * 0.04, 0, 0))
        pb = box(f"PedalBody{sx}", (0, 0, 0), (0.08, 0.1, 0.02), mat("rim", 0.5), bevel=0.006)
        pb.parent = pedal
        obs[f"Pedal{sx}"] = pedal
    obs["Crank"] = crank
    return obs


# ---------------------------------------------------------------------------
# Poses and motion
# ---------------------------------------------------------------------------

def set_ik(rig, bone, world_pos):
    pb = rig.pose.bones[bone]
    rest = rig.data.bones[bone].head_local
    pb.location = rig.data.bones[bone].matrix_local.to_3x3().inverted() @ (rig.matrix_world.inverted() @ world_pos - rest)


def rot_bone(rig, bone, axis, deg):
    pb = rig.pose.bones[bone]
    pb.rotation_mode = "XYZ"
    e = [0.0, 0.0, 0.0]
    e["XYZ".index(axis)] = math.radians(deg)
    pb.rotation_euler = e


def pose_stand(rig):
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0, 0, 0)
    for s in "LR":
        rig.pose.bones[f"Foot_{s}"].constraints[0].influence = 0.0
    rig.location = (0, 0, 0)
    # Relaxed: a slight hip shift, head tilt, cocky lean.
    rot_bone(rig, "Spine", "Y", 3)
    rot_bone(rig, "Head", "Y", -5)
    bpy.context.view_layer.update()


def pose_ride(rig, bike, crank_deg=0.0):
    """Seat her on the bike: hips over the saddle, torso leaning to the bar,
    hands on the grips (IK), feet on the pedals (IK) at this crank angle."""
    B = BIKE
    hip_rest = jp("hip")
    seat = B["saddle"] + Vector((0, 0.02, 0.07))
    rig.location = seat - hip_rest
    bike["Crank"].rotation_euler = (math.radians(crank_deg), 0, 0)
    for w in ("WheelRear", "WheelFront"):
        bike[w].rotation_euler = (math.radians(crank_deg * 2.6), 0, 0)  # fixed gear: wheels turn with the cranks
    bpy.context.view_layer.update()
    rot_bone(rig, "Spine", "X", 48)      # lean forward over the bar (toward -Y)
    rot_bone(rig, "Neck", "X", -24)
    rot_bone(rig, "Head", "X", -20)      # eyes up the road
    for s, sx in (("L", 1), ("R", -1)):
        grip = B["bar"] + Vector((sx * 0.22, 0.03, 0.02))
        set_ik(rig, f"IK_Hand_{s}", grip)
        pedal = bike[f"Pedal{sx}"].matrix_world.translation
        set_ik(rig, f"IK_Foot_{s}", pedal + Vector((0, 0.0, 0.085)))
        rig.pose.bones[f"Foot_{s}"].constraints[0].influence = 0.0
    bpy.context.view_layer.update()


# ---------------------------------------------------------------------------
# Studio, camera, render
# ---------------------------------------------------------------------------

def studio(scene, pct):
    tk_world = bpy.data.worlds.new("Studio")
    scene.world = tk_world
    if getattr(tk_world, "node_tree", None) is None and hasattr(tk_world, "use_nodes"):
        tk_world.use_nodes = True
    bg = next(n for n in tk_world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = COL["bg"]
    bg.inputs["Strength"].default_value = 0.55
    # A cyclorama: floor curving up into the wall, so there is no horizon line.
    verts, faces = [], []
    prof = [(y, 0.0) for y in (-6, -3, 0, 1.5)] + [(1.5 + 0.8 * math.sin(a), 0.8 - 0.8 * math.cos(a))
                                                   for a in (0.4, 0.8, 1.2, 1.5708)] + [(2.3, 4.0)]
    for i, (y, z) in enumerate(prof):
        verts += [(-6, y, z), (6, y, z)]
        if i:
            faces.append((2 * i - 2, 2 * i - 1, 2 * i + 1, 2 * i))
    me = bpy.data.meshes.new("Cyc")
    me.from_pydata(verts, [], faces)
    me.materials.append(mat("floor", 0.95))
    for p in me.polygons:
        p.use_smooth = True
    _link(bpy.data.objects.new("Cyc", me))
    # Big soft key, a fill and a rim, like a product-shoot set-up.
    for name, kind, loc, rot, energy, size in (
        ("Key", "AREA", (-2.2, -2.4, 3.2), (55, 0, -40), 420, 2.5),
        ("Fill", "AREA", (2.8, -2.0, 1.8), (70, 0, 50), 110, 3.0),
        ("Rim", "AREA", (1.0, 2.5, 2.8), (-50, 0, 160), 220, 1.5),
    ):
        d = bpy.data.lights.new(name, kind)
        d.energy, d.size = energy, size
        o = _link(bpy.data.objects.new(name, d))
        o.location, o.rotation_euler = loc, [math.radians(a) for a in rot]
    r = scene.render
    engines = [e.identifier for e in r.bl_rna.properties["engine"].enum_items]
    r.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    r.resolution_percentage = pct
    scene.view_settings.view_transform = "Standard"   # keep the palette's colours
    if hasattr(scene, "eevee"):
        ev = scene.eevee
        for attr, val in (("use_shadows", True), ("taa_render_samples", 32), ("use_raytracing", False)):
            if hasattr(ev, attr):
                setattr(ev, attr, val)


def camera(scene, loc, target, lens=60):
    d = bpy.data.cameras.new("Cam")
    d.lens = lens
    cam = _link(bpy.data.objects.new("Cam", d))
    cam.location = loc
    direction = Vector(target) - Vector(loc)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    return cam


def aim(cam, loc, target, lens=None):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    if lens:
        cam.data.lens = lens


def shoot(scene, path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("rendered", path, flush=True)


def build(pct=50):
    global COLL
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    COLL = scene.collection
    rig = build_rig()
    build_character(rig)
    bike = build_bike()
    studio(scene, pct)
    return scene, rig, bike


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="renders/fixie")
    ap.add_argument("--views", default="sheet,ride")
    ap.add_argument("--pct", type=int, default=50)
    ap.add_argument("--frames", type=int, default=24)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    scene, rig, bike = build(a.pct)
    views = a.views.split(",")
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1440
    cam = camera(scene, (0, -6, 1.2), (0, 0, 0.95), lens=60)
    if "sheet" in views:
        pose_stand(rig)
        for b in bike.values():
            b.hide_render = True
            for c in b.children_recursive:
                c.hide_render = True
        for o in bpy.data.objects:
            if o.name.startswith(("TopTube", "DownTube", "SeatTube", "HeadTube", "ChainStay", "SeatStay", "Fork", "Stem",
                                  "Bar", "Grip", "SeatPost", "Saddle", "Cog", "Chain")):
                o.hide_render = True
        for name, loc in (("front", (0.0, -4.4, 1.0)), ("three_quarter", (2.7, -3.5, 1.15)), ("side", (4.4, 0.0, 1.0))):
            aim(cam, loc, (0, 0, 0.93), lens=70)
            shoot(scene, os.path.join(a.out, f"fixie_{name}.png"))
        for o in bpy.data.objects:
            o.hide_render = o.name in ("FR_Rig", "CapBand")
    if "ride" in views or "loop" in views:
        scene.render.resolution_x, scene.render.resolution_y = 1440, 1080
        pose_ride(rig, bike, 30)
        aim(cam, (-2.6, -2.9, 1.15), (0, -0.05, 0.78), lens=50)
        if "ride" in views:
            shoot(scene, os.path.join(a.out, "fixie_ride.png"))
        if "loop" in views:
            os.makedirs(os.path.join(a.out, "loop"), exist_ok=True)
            for f in range(a.frames):
                pose_ride(rig, bike, 30 + 360 * f / a.frames)
                shoot(scene, os.path.join(a.out, "loop", f"f{f:03d}.png"))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
