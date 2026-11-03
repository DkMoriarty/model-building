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
    "fence": hx("#3b3a38"),
    "lip_pout": hx("#c24e3c"),
    "foliage": hx("#6d7a3a"),
    "skin": hx("#a9643c"), "skin_dark": hx("#7d4a30"), "lip": hx("#5a2a22"),
    "hair": hx("#141116"), "eye_white": hx("#f3efe9"), "iris": hx("#120c0a"),
    "shirt": hx("#8ea383"), "shirt_seam": hx("#6f8566"),
    "shorts": hx("#2c2c31"), "sock": hx("#f1efea"), "shoe": hx("#e7e1d3"), "sole": hx("#b88654"),
    "lace": hx("#f7f5f0"), "cap": hx("#c0582b"), "cap_seam": hx("#9a4220"),
    "mouth_dark": hx("#3b1a17"), "liner": hx("#0e0a0a"), "tongue": hx("#d06a66"), "blush_toon": hx("#e46a5c"), "lip_toon": hx("#d0675d"),
    "stubble": hx("#6e4a38"), "skin_toon": hx("#cf8f66"), "teeth": hx("#f6f2ea"), "sparkle_fx": hx("#ffffff"), "blush_fx": hx("#ff8f8f"), "sweat": hx("#cfe9ff"), "bag": hx("#1e1e21"), "strap": hx("#2d2d31"),
    "frame": hx("#2f4a6b"), "rim": hx("#151518"), "tire": hx("#1c1c1e"), "metal": hx("#b9bcc4"),
    "saddle": hx("#2a2320"), "tape": hx("#d9cfbf"), "chain": hx("#5d6068"),
    "floor": hx("#d9d6d1"), "bg": hx("#e2dfda"),
}
_MAT = {}


VINYL = True  # the matte vinyl-toy look (see `mat`)


def mat(name, roughness=0.6, sheen=0.0, metallic=0.0, sss=0.0):
    """Ultra-matte vinyl-toy surfaces: roughness 0.95, no specular sheen,
    IOR 1.1, plus a microscopic clay grain (noise scale 500 -> bump 0.02)
    so surfaces catch light like a physical object. Glossy parts (eyes,
    metal, roughness < 0.4 on purpose) keep their shine."""
    if name in _MAT:
        return _MAT[name]
    m = bpy.data.materials.new(f"FR_{name}")
    if getattr(m, "node_tree", None) is None and hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    glossy = metallic > 0 or roughness < 0.4
    if VINYL and not glossy:
        roughness = 0.95
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.0
        bsdf.inputs["IOR"].default_value = 1.1
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 500.0
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.02
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
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


def tube(name, path, radii, material, ring=12, caps=True, side=Vector((1, 0, 0)), subdiv=2, crease=0.0, facet=0.0,
         seed=0, profile=None, p_exp=5.0, carve=None, rows=None):
    """Loft a closed tube along `path` (list of 3D points). radii: a list of
    r or (r_side, r_front) per path point - elliptical rings for boxy clothes.
    Smooth-shaded with Subdivision Surface.

    Garments: crease > 0 marks the four corner edges running along the tube
    (and the end rings, the hems) as creases, so subdivision keeps sharp,
    boxy panel boundaries instead of a balloon; facet > 0 jitters each
    ring's corners to make directional fabric planes."""
    import random as _r
    rj = _r.Random(seed + len(name))
    pts = [Vector(p) for p in path]
    if rows and rows > len(pts):          # resample densely so creases can be carved
        def lerp_r(r0, r1, t):
            if isinstance(r0, (tuple, list)):
                return tuple(a + (b - a) * t for a, b in zip(r0, r1))
            return r0 + (r1 - r0) * t
        seglen = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
        total = sum(seglen)
        new_p, new_r = [], []
        for k in range(rows):
            d = total * k / (rows - 1)
            i = 0
            while i < len(seglen) - 1 and d > seglen[i]:
                d -= seglen[i]
                i += 1
            t = min(1.0, d / seglen[i]) if seglen[i] else 0.0
            new_p.append(pts[i].lerp(pts[i + 1], t))
            new_r.append(lerp_r(radii[i], radii[i + 1], t))
        pts, radii = new_p, new_r
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
            a = 2 * math.pi * k / ring + (math.pi / ring if crease else 0.0)
            j = 1 + (rj.uniform(-facet, facet) if facet else 0.0)
            ca, sa = math.cos(a), math.sin(a)
            if profile == "box":   # superellipse: flat panels, tight corners (a carved block, not a balloon)
                ca = math.copysign(abs(ca) ** (2 / p_exp), ca)
                sa = math.copysign(abs(sa) ** (2 / p_exp), sa)
            elif crease:           # push towards a rounded box: corners out, mid-panels flatter
                sq = 1 + 0.18 * abs(math.sin(2 * a))
                ca, sa = ca * sq, sa * sq
            off = u * (ru * j * ca) + v * (rv * j * sa)
            if carve:
                L = off.length or 1e-6
                off = off * ((L + carve(i / max(1, n - 1), a)) / L)
            verts.append(p + off)
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
    if crease:
        _crease(me, ring, n, crease)
    ob = _link(bpy.data.objects.new(name, me))
    _smooth(ob, subdiv)
    return ob


def folds(specs, length, radius):
    """Carving brush for `tube(carve=...)`: each spec (u0, a0, u1, a1, depth,
    width) is a fold line in (along-tube 0..1, angle) space. Points near a
    line are cut into a sharp V-groove (Draw Sharp, inverted) and the lips
    either side are pinched up into ridges (Pinch), so folds have crisp
    apexes and deep shadowed valleys instead of soft bumps."""
    def wrap(x):
        return (x + math.pi) % (2 * math.pi) - math.pi

    def fn(u, a):
        out = 0.0
        for u0, a0, u1, a1, depth, width in specs:
            am = (a0 + a1) / 2
            aa = am + wrap(a - am)
            P = Vector((u * length, aa * radius))
            A, B = Vector((u0 * length, a0 * radius)), Vector((u1 * length, a1 * radius))
            ab = B - A
            t = max(0.0, min(1.0, (P - A).dot(ab) / ab.length_squared)) if ab.length_squared else 0.0
            d = (A + ab * t - P).length
            taper = math.sin(math.pi * t) ** 0.5               # folds fade out at their ends
            out -= depth * taper * max(0.0, 1 - d / width)                                  # sharp valley
            out += depth * 0.45 * taper * max(0.0, 1 - abs(d - 1.15 * width) / (0.45 * width))  # pinched ridge
        return out
    return fn


def _crease(me, ring, n, value):
    """Crease the 4 corner seams along a tube and its two end rings (hems)."""
    me.update(calc_edges=True)
    corners = {k for k in range(ring) if ring >= 8 and k % (ring // 4) == ring // 8}
    layer = me.edge_creases_ensure() if hasattr(me, "edge_creases_ensure") else None
    for e in me.edges:
        a, b = sorted(e.vertices)
        if a >= ring * n or b >= ring * n:
            continue
        ia, ka = divmod(a, ring)
        ib, kb = divmod(b, ring)
        val = 0.0
        if ka == kb and ib == ia + 1 and ka in corners:
            val = value                                   # a panel corner running along the garment
        elif ia == ib and ia in (0, n - 1):
            val = 1.0                                     # crisp hem
        if val and layer is not None:
            layer.data[e.index].value = val


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


def _g(a, mu, s):
    return math.exp(-((a - mu) / s) ** 2)


def _tent(a, w):
    """Linear falloff: a sharp apex / V-groove (no soft bell)."""
    return max(0.0, 1 - abs(a) / w)


def _plateau(a, half, soft):
    """Flat top with crisp edges: 1 inside |a| < half, falling over `soft`."""
    return max(0.0, min(1.0, (half - abs(a)) / soft))


def _seg(px, pz, ax, az, bx, bz):
    """Distance from point to segment, the param along it, and the side."""
    dx, dz = bx - ax, bz - az
    L2 = dx * dx + dz * dz
    t = max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L2))
    cx, cz = ax + dx * t, az + dz * t
    side = (dx * (pz - az) - dz * (px - ax))
    return math.hypot(px - cx, pz - cz), t, side


DEFAULT_LAYOUT = dict(eye_ux=0.34, eye_uz=0.05, nose_z=-0.235, mouth_z=-0.54, chin_z=-0.84, ear_uz=-0.06, ear_h=0.62,
                      brow_style=None)
LAYOUT = dict(DEFAULT_LAYOUT)


def smirk_line(x, smirk=1.0):
    """Height of the mouth crease across the face (rises into the right cheek)."""
    return LAYOUT["mouth_z"] + smirk * 0.075 * max(0.0, x - 0.1) + 0.02 * x * x


def hard_features(x, z, nose=1.0, chin=1.0, smirk=1.0):
    """Facial features cut as hard planes, the code version of Scrape,
    Draw Sharp (inverted), Crease and Clay Strips (unit-sphere coords,
    returns forward displacement):
      nose  - a wedge: flat top bridge, two flat side walls, a flat diamond
              tip facet, flat-topped nostril wings cut out of the cheeks;
      lips  - two raised plates with crisp edges, pinched by a smirk crease;
      folds - a sharp nasolabial groove from the nostril to the mouth corner,
              with the cheek bunched into a ridge above it;
      chin  - a flat-faced trapezoid plate."""
    d = 0.0
    s = nose
    # Nose wedge.
    z_top, z_tip, z_base = 0.17, -0.24, -0.33
    if z_base < z < z_top:
        if z >= z_tip:
            t = (z_top - z) / (z_top - z_tip)
            h, w = (0.025 + 0.14 * t) * s, 0.05 + 0.075 * t
        else:
            t2 = (z - z_base) / (z_tip - z_base)
            h, w = 0.165 * s * t2, 0.125 + 0.02 * (1 - t2)
        h = min(h, 0.15 * s)                               # flat tip facet
        top = 0.3 * w
        d += h * max(0.0, min(1.0, (w - abs(x)) / (w - top)))
    for sx in (1, -1):
        r = math.hypot((x - sx * 0.13) / 0.065, (z + 0.29) / 0.05)
        d += 0.05 * s * max(0.0, min(1.0, (1 - r) / 0.25))                   # nostril wing (flat top)
        if x * sx > 0.07 and z > -0.37:
            d -= 0.035 * _tent(r - 1.18, 0.2)                                 # cut where nostril meets cheek
        # Nasolabial fold + cheek bunching above it (deeper on the smirk side).
        dist, t, side = _seg(x, z, sx * 0.19, -0.27, sx * 0.38, -0.6)
        if 0.02 < t < 0.98:
            k = 1.3 if sx > 0 else 0.8
            d -= 0.02 * k * smirk ** 0.5 * _tent(dist, 0.028)
            if side * sx < 0:                                                 # the cheek side
                d += 0.022 * k * _plateau(dist - 0.06, 0.04, 0.02)
    # Lips: crisp plates split by the smirk crease.
    zl = smirk_line(x, smirk)
    d += 0.022 * _plateau(x, 0.24, 0.03) * _plateau(z - (zl + 0.035), 0.03, 0.01)      # upper lip
    d += 0.028 * _plateau(x, 0.19, 0.03) * _plateau(z - (zl - 0.04), 0.035, 0.01)      # lower lip
    d -= 0.032 * _plateau(x, 0.32, 0.04) * _tent(z - zl, 0.018)                        # the crease
    for px in (0.05, -0.05):                                                            # philtrum ridges
        if -0.47 < z < -0.33:
            d += 0.016 * _tent(x - px, 0.028)
    # Chin plate: a flat-faced trapezoid.
    cw = 0.13 + 0.08 * max(0.0, z + 0.9)
    d += 0.055 * chin * _plateau(x, cw, 0.035) * _plateau(z + 0.82, 0.08, 0.03)
    return d


def soft_features(x, z, nose=1.0, chin=1.0, smirk=1.0, lips=1.0):
    """Feature-film style face (soft, appealing forms): a slim bridge into a
    rounded button tip with small nostril wings, full lips with a defined
    cupid's bow and a fuller lower lip, a soft ball chin, high cheeks.
    Returns (forward displacement, lip mask)."""
    d = 0.0
    L = LAYOUT
    nz, ez = L["nose_z"], L["eye_uz"]
    span = max(0.12, ez - nz)
    if L.get("diamond"):
        # Flattened planes: a knife-edge bridge (tent, not bell) widening into a
        # diamond tip - flat facets meeting in crisp ridges.
        dm = L["diamond"]
        wz = 0.03 + 0.05 * max(0.0, min(1.0, (ez - z) / span))            # bridge widens toward the tip
        d += 0.06 * nose * dm * _tent(x, wz) * max(0.0, min(1.0, (ez + 0.12 - z) / 0.15)) * _plateau(z - (ez + nz) / 2, span * 0.55, 0.06)
        d += 0.15 * nose * dm * _tent(x, 0.09) ** 0.8 * _tent(z - nz, 0.085) ** 0.8
    else:
        d += 0.045 * nose * _g(x, 0, 0.05) * max(0.0, min(1.0, (ez + 0.15 - z) / 0.15)) * _g(z, (ez + nz) / 2, span * 0.75)  # bridge
        d += 0.15 * nose * _g(x, 0, 0.075) * _g(z, nz, 0.065)                                          # rounded tip
    for sx in (1, -1):
        d += 0.04 * nose * _g(x, sx * 0.1, 0.045) * _g(z, nz - 0.035, 0.04)                       # nostril wings
        d += 0.05 * _g(x, sx * 0.5, 0.17) * _g(z, ez - 0.13, 0.14)                                 # high cheeks
    d -= 0.02 * _g(x, 0, 0.05) * _g(z, nz - 0.125, 0.03)                                           # under-nose dip
    zl = smirk_line(x, smirk * 0.5)
    top = zl + 0.065 * lips - 0.02 * _g(x, 0, 0.03) + 0.008 * (_g(x, 0.06, 0.035) + _g(x, -0.06, 0.035))   # cupid's bow
    up = _plateau(z - (zl + top) / 2, (top - zl) / 2, 0.014) * _g(x, 0, 0.2 * lips ** 0.5) ** 0.6
    low = _plateau(z - (zl - 0.045 * lips), 0.04 * lips, 0.016) * _g(x, 0, 0.16 * lips ** 0.5) ** 0.6
    d += 0.045 * lips * up + 0.065 * lips * low
    d -= 0.024 * _plateau(x, 0.28 * lips ** 0.5, 0.05) * _tent(z - zl, 0.016)                     # parting line
    d += 0.07 * chin * _g(x, 0, 0.13 + 0.07 * L.get("jaw_ref", 0) + L.get("chin_w", 0.0)) * _g(z, L["chin_z"], 0.1 + 0.03 * L.get("jaw_ref", 0))   # chin
    return d, max(up, low)


def skin_paint_material(name, skin, blush, lip, stubble=None):
    """Skin with painted colour from the head's 'Paint' attribute (blush on
    cheeks and nose, lips, optional stubble), soft subsurface glow, and
    glossier lips (the 'Lip' attribute lowers roughness)."""
    m = bpy.data.materials.new(name)
    if getattr(m, "node_tree", None) is None and hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    col = nt.nodes.new("ShaderNodeAttribute")
    col.attribute_name = "Paint"
    lipa = nt.nodes.new("ShaderNodeAttribute")
    lipa.attribute_name = "Lip"
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.72
    rough.inputs["To Max"].default_value = 0.22
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(lipa.outputs["Fac"], rough.inputs["Value"])
    nt.links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    if "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = 0.2
        bsdf.inputs["Subsurface Radius"].default_value = (0.8, 0.4, 0.25)
        if "Subsurface Scale" in bsdf.inputs:
            bsdf.inputs["Subsurface Scale"].default_value = 0.012
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.15
    m.diffuse_color = COL[skin]
    return m


def ear_shell(name, center, h, sx, material):
    """An architectural ear: a flat ribbon rim (helix) running round in a C,
    a recessed bowl, a lobe and a tragus."""
    parts = []
    path = []
    for i in range(14):
        a = math.radians(70 + 280 * i / 13)                 # open C toward the face
        path.append(center + Vector((0, -math.cos(a) * h * 0.32, math.sin(a) * h * 0.5)))
    rim = tube(f"{name}Rim", path, [(h * 0.12, h * 0.07)] * 14, material, side=Vector((1, 0, 0)), profile="box",
               p_exp=6.0, ring=16, subdiv=1)
    parts.append(rim)
    bowl = blob(f"{name}Bowl", center + Vector((-sx * h * 0.06, 0.0, 0.0)), (h * 0.07, h * 0.22, h * 0.36), material)
    parts.append(bowl)
    parts.append(blob(f"{name}Lobe", center + Vector((0, -h * 0.05, -h * 0.47)), (h * 0.09, h * 0.16, h * 0.15), material))
    parts.append(blob(f"{name}Tragus", center + Vector((0, -h * 0.28, -h * 0.08)), (h * 0.08, h * 0.07, h * 0.1), material))
    return parts


def sculpt_head(name, hc, size, material, nose=1.0, chin=1.0, cheek=1.0, jaw=1.0, smirk=1.0, style="planes", lips=1.0,
                paint=None):
    """A head sculpted with planes, not a ball: eye sockets pressed in under
    a brow ridge, cheekbones, a nose bridge running into a tip, a philtrum
    and lips, a narrowing jaw ending in a defined chin. Built by displacing a
    dense sphere with smooth bumps (the code version of sculpt strokes)."""
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=128, v_segments=80, radius=1.0)   # dense: hard edges need polygons
    sx, sy, sz = size
    toon = style == "toon"
    paint_cols = []
    import random as _rnd
    rs = _rnd.Random(9)
    for v in bm.verts:
        x, y, z = v.co
        f = max(0.0, -y) ** 1.5                     # frontness (the face looks along -Y)
        # Scrape/flatten: shave the sides of the skull into flat planes from the
        # temples down past the cheeks, leaving a crisp cheekbone ridge where the
        # front of the face turns into the side.
        plane = 0.78 if not toon else 0.86
        if abs(x) > plane and -0.55 < z < 0.45 and y < 0.35:   # temples-to-cheek planes only, not the whole skull
            x = math.copysign(plane + (abs(x) - plane) * (0.5 if not toon else 0.7), x)
        if y < -0.82 and z > 0.15:                  # flat forehead plane
            y = -0.82 + (y + 0.82) * 0.35
        shield = LAYOUT.get("shield", 0.0) if toon else 0.0
        if shield:
            # Shield head: a wide, flat upper face (forehead + cheekbones pulled
            # out sideways, front flattened) tapering in straight lines to a tiny
            # pointed chin pulled down.
            top = LAYOUT["eye_uz"] - 0.1
            if z > top:
                x *= 1 + 0.1 * shield
            else:
                t = min(1.0, (top - z) / (top + 1.0))
                # Outline set directly: full cheeks held down past the mouth, then a
                # convex (U) jaw line closing into a small chin (~30% of cheek width).
                sw = max(0.3, math.sqrt(max(0.0, 1 - z * z)))
                wt = (1 + 0.1 * shield) * math.sqrt(max(0.0, 1 - top * top))
                x *= (wt * (1 - 0.75 * shield * t ** 2.2)) / sw
                z -= 0.03 * shield * t * t
            if y < -0.55:                                     # flat face front, easing out below the cheeks
                fz = max(0.0, min(1.0, (z + 0.75) / 0.4))
                y = -0.55 + (y + 0.55) * (1 - 0.45 * shield * fz)
        oval = LAYOUT.get("oval", 0.0) if toon else 0.0
        jref = LAYOUT.get("jaw_ref", 0.0) if toon else 0.0
        if z < 0 and jref:
            # Reference jaw: full cheeks down to the mouth, then a long STRAIGHT
            # jawline from under the ear to a broad, rounded-square chin
            # (about half the face width) that juts slightly forward.
            zz = -z
            t = max(0.0, min(1.0, (zz - 0.15) / 0.85))
            x *= 1 - 0.4 * t                                    # linear taper = straight jaw lines
            if zz > 0.8 and y < 0.1:                            # chin bottom: flattened, corners stay round
                z = -0.8 - (zz - 0.8) * 0.6
            y = y * (1 - 0.15 * zz) if y > 0 else y
            z = z * (1 + 0.12 * zz)                             # long lower face
        elif z < 0 and oval and not shield:
            # Perfect elongated oval: the lower face is a stretched half-ellipse -
            # no jaw corner, no flat planes, a softly rounded chin at the bottom.
            zz = -z
            x *= math.sqrt(max(0.0, 1 - 0.55 * oval * zz ** 2)) / math.sqrt(max(1e-6, 1 - 0.0 * zz))
            y = y * (1 - 0.12 * zz) if y > 0 else y
            z = z * (1 + 0.16 * oval * zz)                # elongate the jaw downward, more toward the chin
        elif z < 0 and not shield:                                 # jaw tapering to the chin (angular when jaw is low)
            k = 1 - 0.4 * jaw * (-z) ** 1.2
            if jaw < 0.6:                           # keep a squarer jaw corner, then narrow hard to the chin
                k = 1 - 0.18 * (-z) - 0.55 * max(0.0, -z - 0.55) ** 1.1
            x *= max(0.12, k)
            y = y * (1 - 0.1 * (-z)) if y > 0 else y
        wedge = LAYOUT.get("wedge", 0.0) if toon else 0.0
        if wedge:
            # Grab: thin the lower face into an inverted wedge (cheekbone line down to a pointed chin).
            if z < -0.3:
                t = min(1.0, (-0.3 - z) / 0.7)
                x *= 1 - wedge * 0.2 * t
                # pull the chin apex down and to a point
                z -= wedge * 0.07 * t * t * _g(x, 0, 0.22) * max(0.0, -y)
            # Scrape: a flat plane under the jaw, from below the ear (back, high) to the chin (front, low).
            zj = -0.32 - 0.62 * max(0.0, min(1.0, (0.35 - y) / 0.95))
            zj -= 0.18 * max(0.0, 1 - abs(x) / 0.35) * max(0.0, -y)   # the chin keeps its apex
            if z < zj and y < 0.45:
                z = zj + (z - zj) * 0.12
        d = 0.0                                     # forward displacement (toward -Y)
        eux = LAYOUT["eye_ux"] if toon and "hairline" in LAYOUT else 0.37      # mapped faces: sockets follow the eyes
        euz = LAYOUT["eye_uz"] + 0.05 if toon and "hairline" in LAYOUT else 0.1
        for ex in (eux, -eux):
            d -= 0.16 * _g(x, ex, 0.15) * _g(z, euz, 0.12) * f                    # deep eye sockets
            d += 0.06 * cheek * _g(x, ex * 1.45, 0.14) * _g(z, euz - 0.24, 0.14) * f    # cheekbones
        d += 0.07 * _g(z, 0.31, 0.07) * (_g(x, 0.34, 0.22) + _g(x, -0.34, 0.22)) * f  # brow ridge
        if wedge:
            for ex in (1, -1):
                # Scrape a flat diagonal cheek panel under the eye, its lower edge a crisp ridge,
                # and push the pocket below the cheekbone in (the shadow plane).
                u = ex * x * 0.8 + (z - LAYOUT["eye_uz"]) * 0.6          # runs diagonally down-in
                d += wedge * 0.05 * _plateau(ex * x - 0.5, 0.16, 0.05) * _plateau(z - (LAYOUT["eye_uz"] - 0.24), 0.1, 0.04) * f
                d -= wedge * 0.11 * _g(ex * x, 0.64, 0.12) * _g(z, LAYOUT["eye_uz"] - 0.5, 0.13) * f * _tent(u - 0.3, 0.6)
        lipw = 0.0
        if toon:
            fd, lipw = soft_features(x, z, nose, chin, smirk, lips)
            d += fd * (max(0.0, -y) ** 0.5)
            lipw *= max(0.0, -y) ** 2
        else:
            d += hard_features(x, z, nose, chin, smirk) * (max(0.0, -y) ** 0.5)   # planar nose, lips, folds
        if paint:
            skin_c, blush_c, lip_c, stub_c = [Vector(c[:3]) if c else None for c in paint]
            fr_ = max(0.0, -y)
            bw = (sum(_g(x, e, 0.22) for e in (0.5, -0.5)) * _g(z, LAYOUT["eye_uz"] - 0.25, 0.2) * 1.0
                  + 1.1 * _g(x, 0, 0.12) * _g(z, LAYOUT["nose_z"], 0.1)) * fr_
            c = skin_c.lerp(Vector(blush_c), min(0.9, bw * 1.35))
            if stub_c is not None and z < -0.28 and abs(x) < 0.82 and lipw < 0.2:
                sw = min(1.0, (-0.28 - z) / 0.15) * (0.55 + 0.45 * rs.random()) * (1 if rs.random() < 0.55 else 0.3)
                c = c.lerp(Vector(stub_c), 0.45 * sw)
            c = c.lerp(Vector(lip_c), min(1.0, lipw * 2.2))
            paint_cols.append((c, lipw))
        y -= d
        v.co = Vector((hc.x + x * sx, hc.y + y * sy, hc.z + z * sz))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    from mathutils.bvhtree import BVHTree
    _HEAD_BVH[(round(hc.x, 4), round(hc.y, 4), round(hc.z, 4))] = BVHTree.FromPolygons(
        [v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    if paint_cols:
        me.color_attributes.new("Paint", "FLOAT_COLOR", "POINT")
        me.attributes.new("Lip", "FLOAT", "POINT")
        ca, la = me.attributes["Paint"], me.attributes["Lip"]    # fetch after both exist (new() reallocates)
        for i, (c, lw) in enumerate(paint_cols):
            ca.data[i].color = (c.x, c.y, c.z, 1.0)
            la.data[i].value = lw
    me.materials.append(material)
    ob = _link(bpy.data.objects.new(name, me))
    _smooth(ob, 1)
    return ob


_HEAD_BVH = {}


def head_surface(hc, size, ux, uz, **kw):
    """World point on the sculpted head's front at unit coords (ux, uz):
    a ray onto the real sculpted mesh when it exists, so features sit on
    the face (not floating past the jaw)."""
    sx, sy, sz = size
    bvh = _HEAD_BVH.get((round(hc.x, 4), round(hc.y, 4), round(hc.z, 4)))
    if bvh is not None:
        o = Vector((hc.x + ux * sx, hc.y - 1.0, hc.z + uz * sz))
        hit = bvh.ray_cast(o, Vector((0, 1, 0)))
        if hit[0] is not None:
            return hit[0]
    y = -math.sqrt(max(0.0, 1 - ux * ux - uz * uz))
    f = (-y) ** 1.5
    d = -0.16 * sum(_g(ux, ex, 0.15) for ex in (0.37, -0.37)) * _g(uz, 0.1, 0.12) * f
    return Vector((hc.x + ux * sx, hc.y + (y - d) * sy, hc.z + uz * sz))


def lid_shell(name, center, r, open_deg, upper, skin, lash, rot_z=0.0):
    """An eyelid that wraps the eyeball: a spherical cap slightly larger than
    the eye, cut by a plane; its rim ring is the dark lash line. Rotating the
    object about X opens or closes it (animatable)."""
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=20, radius=r)
    cut = r * 0.05 if upper else -r * 0.45
    kill = [v for v in bm.verts if (v.co.z < cut if upper else v.co.z > cut)]
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    rim_z = min(v.co.z for v in bm.verts) if upper else max(v.co.z for v in bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(skin)
    me.materials.append(lash)
    for poly in me.polygons:
        zs = [me.vertices[i].co.z for i in poly.vertices]
        poly.material_index = 1 if min(abs(z - rim_z) for z in zs) < r * 0.12 else 0
        poly.use_smooth = True
    ob = _link(bpy.data.objects.new(name, me))
    ob.location = center
    ob.rotation_euler = (math.radians(open_deg if upper else -open_deg), 0, rot_z)
    m = ob.modifiers.new("Thick", "SOLIDIFY")
    m.thickness = r * (0.38 if upper else 0.2)   # a chunky shelf that shadows the eyeball
    m.offset = 1.0
    return ob


FACE_INFO = {}


def recenter(ob):
    """Move an object's origin to its bounding-box centre (its pivot)."""
    c = sum((Vector(v.co) for v in ob.data.vertices), Vector()) / len(ob.data.vertices)
    ob.data.transform(Matrix.Translation(-c))
    ob.location = ob.location + c
    return ob


MOUTHS = {  # mouth shape -> its parts (names without prefix)
    "SMIRK": ("Smile", "Dimple", "PoutUp", "PoutLow"),
    "GRIN": ("MouthGrinDark", "MouthGrinTeeth", "MouthGrinTongue", "MouthGrinLine"),
    "O": ("MouthORim", "MouthO"),
    "GASP": ("MouthGasp", "MouthGaspTeeth"),
    "FLAT": ("MouthFlat", "PoutUp", "PoutLow"),
}


def build_mouths(add, hc, size, lip_col, prefix, grin="open"):
    """The alternative mouths, sculpted in place on the face and hidden
    (scale ~0) until an expression swaps them in."""
    dark = mat("mouth_dark", 0.6)
    teeth = mat("teeth", 0.35)
    lip = mat(lip_col, 0.5)

    def at(ux, uz, fwd=0.0):
        return head_surface(hc, size, ux, uz) + Vector((0, -0.002 - fwd, 0))
    mz = LAYOUT["mouth_z"] + 0.54                  # shift every mouth shape to this face's mouth line
    # A wide, open grin: the corners lift hard, the opening is a deep D below
    # the line, a row of upper teeth along its top, a tongue at the bottom.
    made = []
    style = grin
    if style == "crescent":
        # Cocky grin: a crescent of upper teeth between a top line and a deeper
        # bottom curve, rising on one side, outlined thin and dark.
        xs = [(-0.34 + 0.68 * i / 8) for i in range(9)]
        xs = [x * 1.15 for x in xs]                                          # wide
        top = [-0.465 + mz + 0.2 * x * x + 0.08 * x for x in xs]
        bot = [t - 0.1 * (1 - (x / 0.41) ** 2) for x, t in zip(xs, top)]
        T = [at(x, z) for x, z in zip(xs, top)]
        B = [at(x, z) for x, z in zip(xs, bot)]
        Mid = [(a + b) / 2 for a, b in zip(T, B)]
        hgt = [max(0.0008, (a.z - b.z) / 2 * 0.98) for a, b in zip(T, B)]
        made.append(tube(f"{prefix}MouthGrinTeeth", Mid, [(0.0016, h) for h in hgt], teeth, side=Vector((0, 1, 0)), subdiv=1))
        made.append(tube(f"{prefix}MouthGrinLine", [p + Vector((0, -0.0012, 0)) for p in T],
                         [0.0014, 0.0022, 0.0026, 0.0028, 0.0028, 0.0028, 0.0026, 0.0022, 0.0014], dark,
                         side=Vector((0, 1, 0)), subdiv=1))
        made.append(tube(f"{prefix}MouthGrinDark", [p + Vector((0, -0.0012, 0)) for p in B],
                         [0.0012, 0.0018, 0.0022, 0.0024, 0.0024, 0.0024, 0.0022, 0.0018, 0.0012], dark,
                         side=Vector((0, 1, 0)), subdiv=1))
        made.append(blob(f"{prefix}MouthGrinTongue", Mid[4], (0.001, 0.001, 0.001), dark, subdiv=0))
    else:
        xs = (-0.36, -0.24, -0.12, 0.0, 0.12, 0.24, 0.36)
        grin = [at(ux, -0.5 + mz + 0.3 * ux * ux) for ux in xs]
    if style != "crescent":
        depth = [0.003, 0.012, 0.019, 0.022, 0.019, 0.012, 0.003]
        # Flat against the face: thin front-to-back (first radius), tall top-to-bottom (second).
        made.append(tube(f"{prefix}MouthGrinDark", [p + Vector((0, 0.0005, -dz * 0.85)) for p, dz in zip(grin, depth)],
                         [(0.0022, dz * 0.85 + 0.001) for dz in depth], dark, side=Vector((0, 1, 0)), subdiv=1))
        made.append(tube(f"{prefix}MouthGrinTeeth", [p + Vector((0, -0.0012, -0.006)) for p in grin[1:-1]],
                         [(0.0018, 0.0045), (0.0018, 0.0058), (0.0018, 0.006), (0.0018, 0.0058), (0.0018, 0.0045)], teeth,
                         side=Vector((0, 1, 0)), subdiv=1))
        made.append(blob(f"{prefix}MouthGrinTongue", grin[3] + Vector((0, -0.0012, -0.026)), (0.016, 0.0018, 0.007),
                         mat("tongue", 0.5), subdiv=1))
        made.append(tube(f"{prefix}MouthGrinLine", grin, [0.0015, 0.0025, 0.003, 0.003, 0.003, 0.0025, 0.0015], lip,
                         side=Vector((0, 1, 0)), subdiv=1))
    c = at(0.02, -0.53 + mz, 0.001)
    made.append(blob(f"{prefix}MouthORim", c + Vector((0, 0.002, 0)), (0.0165, 0.006, 0.021), lip, subdiv=1))
    made.append(blob(f"{prefix}MouthO", c, (0.012, 0.006, 0.016), dark, subdiv=1))
    made.append(blob(f"{prefix}MouthGasp", c + Vector((0, 0, -0.004)), (0.017, 0.007, 0.026), dark, subdiv=1))
    made.append(blob(f"{prefix}MouthGaspTeeth", c + Vector((0, -0.003, 0.016)), (0.011, 0.004, 0.0045), teeth, subdiv=1))
    made.append(tube(f"{prefix}MouthFlat", [at(-0.18, -0.52 + mz), at(0.0, -0.53 + mz), at(0.2, -0.515 + mz)], [0.0025, 0.0035, 0.0025], lip,
                     side=Vector((0, 1, 0)), subdiv=1))
    for ob in made:
        recenter(ob)
        add(ob, "Head")
        ob.scale = ob.scale * 0.001
        ob["hidden_mouth"] = True


def build_toon_face(add, hc, size, skin, iris_col, brow_col, lip_col, prefix, nose, chin, jaw, eye_r, lashes, smirk, lips,
                    paint, brows, wing=1.0, eye_shape="round", grin="open", layout=None):
    """The feature-film face: soft forms, painted blush and lips, big
    almond eyes with winged liner, sharply arched brows. `layout` places
    the features (measured from a reference)."""
    LAYOUT.clear()
    LAYOUT.update(DEFAULT_LAYOUT)
    LAYOUT.update(layout or {})
    L = LAYOUT
    skin_m = skin_paint_material(f"{prefix}SkinPaint", *paint) if paint else skin
    cols = (COL[paint[0]], COL[paint[1]], COL[paint[2]], COL[paint[3]] if paint[3] else None) if paint else None
    add(sculpt_head(f"{prefix}Head", hc, size, skin_m, nose=nose, chin=chin, jaw=jaw, smirk=smirk, style="toon", lips=lips,
                    paint=cols), "Head")
    liner = mat("liner", 0.4)
    skin_flat = skin
    for sx in (1, -1):
        surf = head_surface(hc, size, sx * L["eye_ux"], L["eye_uz"])
        eye = surf + Vector((0, eye_r * L.get("eye_sink", 0.55), 0))
        if eye_shape == "almond":
            almond_eye(add, prefix, sx, eye, eye_r, iris_col, liner, wing, ah=L.get("almond_h"))
        else:
            toon_eye(add, prefix, sx, eye, eye_r, skin_flat, iris_col, liner, lashes, wing)
        # Brows: thick tapered swoosh. 'arch' peaks two-thirds out; 'angry' dives to the nose.
        if brows == "straight":    # thick, nearly level, sitting just above the eyes
            spec = ((0.12, 0.215), (0.27, 0.24), (0.43, 0.245), (0.6, 0.215))
            radii = [(0.005, 0.009), (0.005, 0.0095), (0.0045, 0.008), (0.003, 0.003)]
        elif brows == "lift":
            spec = ((0.12, 0.29), (0.28, 0.36), (0.44, 0.385), (0.6, 0.32))
            radii = [0.0065, 0.009, 0.008, 0.003]
        elif brows == "angry":
            spec = ((0.1, 0.15), (0.25, 0.215), (0.42, 0.265), (0.62, 0.235))  # dive toward the nose, low over the eyes
            radii = [(0.006, 0.013), (0.006, 0.014), (0.005, 0.011), (0.003, 0.004)]
        elif brows == "thin":      # thin, soft, high above the eyes, a gentle arch
            spec = ((0.14, 0.29), (0.28, 0.34), (0.44, 0.36), (0.6, 0.33), (0.72, 0.27))
            radii = [(0.0012, 0.0016), (0.0016, 0.0028), (0.0016, 0.0028), (0.0012, 0.002), (0.0003, 0.0004)]
        elif brows == "sharp":     # thin, dark, low; angled down at the inner end, peaking two-thirds out
            spec = ((0.12, 0.13), (0.26, 0.19), (0.42, 0.235), (0.56, 0.245), (0.7, 0.2))
            radii = [(0.0024, 0.0034), (0.0032, 0.006), (0.003, 0.0056), (0.0022, 0.004), (0.0005, 0.0007)]
        elif brows == "bushy":    # reference: thick, dark, low over the eyes, a soft arch, heavy at the inner end
            spec = ((0.1, 0.17), (0.24, 0.215), (0.4, 0.235), (0.56, 0.22), (0.68, 0.17))
            radii = [(0.0045, 0.008), (0.0055, 0.0105), (0.005, 0.0095), (0.0038, 0.007), (0.001, 0.0015)]
        elif brows == "wedge":     # thin dark wedge: heavy hooked head low by the nose, tilting up and out to a needle tip
            spec = ((0.08, 0.1), (0.13, 0.15), (0.24, 0.2), (0.39, 0.245), (0.54, 0.26), (0.68, 0.23))
            radii = [(0.003, 0.004), (0.004, 0.0085), (0.0038, 0.0075), (0.003, 0.0058), (0.0022, 0.0035), (0.0004, 0.0005)]
        else:
            spec = ((0.13, 0.27), (0.29, 0.33), (0.45, 0.36), (0.62, 0.29))
            radii = [0.0045, 0.006, 0.0052, 0.0016]
        dz = L["eye_uz"] - 0.05 - L.get("brow_drop", 0.0)   # brows ride with the eye line
        pts = [head_surface(hc, size, sx * ux, uz + dz) + Vector((0, -0.006, 0)) for ux, uz in spec]
        add(recenter(tube(f"{prefix}Brow{sx}", pts, radii, mat(brow_col, 0.6), subdiv=1)), "Head")
        for part in ear_shell(f"{prefix}Ear{sx}", hc + Vector((sx * size[0] * 0.88, 0.015, size[2] * L["ear_uz"])),
                              size[2] * L["ear_h"], sx, skin_flat):
            add(part, "Head")
    pts = [head_surface(hc, size, ux, smirk_line(ux, smirk * 0.5)) + Vector((0, -0.003, 0))
           for ux in [u * L.get("mouth_w", 0.28) / 0.28 for u in (-0.27, -0.13, 0.0, 0.14, 0.28)]]
    if L.get("slit"):
        # A crisp, blocky slit (flat ends, even weight) with a short carved crease
        # flicking up at the smirk corner and a faint tuck at the other.
        add(tube(f"{prefix}Smile", pts, [0.0007, 0.0012, 0.0013, 0.0012, 0.0008], mat("mouth_dark", 0.5),
                 side=Vector((0, 1, 0)), subdiv=1, ring=8), "Head")
        c = pts[-1]
        add(tube(f"{prefix}Dimple", [c, c + Vector((0.0025, -0.0005, 0.0018)), c + Vector((0.0045, -0.0008, 0.0055))],
                 [0.0011, 0.0008, 0.0002], mat("mouth_dark", 0.5), subdiv=0, ring=6), "Head")
    else:
        add(tube(f"{prefix}Smile", pts, [0.001, 0.002, 0.0022, 0.002, 0.001], mat("mouth_dark", 0.5), side=Vector((0, 1, 0)),
                 subdiv=1), "Head")
        add(tube(f"{prefix}Dimple", [pts[-1], pts[-1] + Vector((0.003, 0.0, 0.003))], [0.001, 0.0006], mat("mouth_dark", 0.5),
                 subdiv=0, ring=6), "Head")
    if L.get("pout"):
        # Full, pouty coral lips: a cupid's-bow upper lip and a fuller lower lip
        # sitting proud of the face, parted by a short dark line.
        lipm = mat("lip_pout", 0.35)
        pw = L["pout"]
        mz = smirk_line(0.0, smirk * 0.5)
        up = head_surface(hc, size, 0.0, mz + 0.045) + Vector((0, -0.004, 0))
        lo = head_surface(hc, size, 0.0, mz - 0.055) + Vector((0, -0.005, 0))
        add(tube(f"{prefix}PoutUp", [up + Vector((-0.021 * pw, 0.004, -0.004)), up + Vector((-0.008 * pw, 0, 0.0015)),
                                     up + Vector((0, 0.0005, -0.0005)), up + Vector((0.008 * pw, 0, 0.0015)),
                                     up + Vector((0.021 * pw, 0.004, -0.004))],
                 [(0.002, 0.002), (0.0055, 0.005), (0.006, 0.0048), (0.0055, 0.005), (0.002, 0.002)], lipm,
                 side=Vector((0, 1, 0)), subdiv=2, ring=12), "Head")
        add(tube(f"{prefix}PoutLow", [lo + Vector((-0.017 * pw, 0.004, 0.003)), lo + Vector((-0.007 * pw, 0, 0)),
                                      lo + Vector((0.007 * pw, 0, 0)), lo + Vector((0.017 * pw, 0.004, 0.003))],
                 [(0.002, 0.002), (0.007, 0.0065), (0.007, 0.0065), (0.002, 0.002)], lipm, side=Vector((0, 1, 0)),
                 subdiv=2, ring=12), "Head")
    build_mouths(add, hc, size, lip_col, prefix, grin=grin)
    build_face_extras(add, hc, size, prefix)
    FACE_INFO[prefix] = dict(hc=hc.copy(), size=size, eye_r=eye_r, almond=eye_shape == "almond", ah=L.get("almond_h") or ALMOND_H)


def build_face_extras(add, hc, size, prefix):
    """Cartoon accents an expression can dial in: blush, eye sparkles, a sweat drop."""
    blush = mat("blush_fx", 0.6)
    for sx in (1, -1):
        b = blob(f"{prefix}Blush{sx}", head_surface(hc, size, sx * 0.56, LAYOUT["eye_uz"] - 0.25) + Vector((0, -0.004, 0)), (0.024, 0.004, 0.013),
                 blush, subdiv=1)
        add(b, "Head")
        b.scale = b.scale * 0.001
    sweat = blob(f"{prefix}Sweat", head_surface(hc, size, -0.7, 0.35) + Vector((-0.012, -0.01, 0)), (0.007, 0.005, 0.011),
                 mat("sweat", 0.15), subdiv=1)
    add(sweat, "Head")
    sweat.scale = sweat.scale * 0.001


ALMOND_H = 0.62   # almond eye height / width ratio driver (eyeball z-scale)


def almond_eye(add, prefix, sx, eye, r, iris_col, liner, wing, ah=None):
    """A cool, narrow almond eye (feature-film street style): a wide, short
    eyeball (white shows both sides), a dark iris that fills its height, a
    heavy black upper line hugging the top contour into a short flick, a
    fine lower line. Openness is the eyeball's height (see FaceRig)."""
    W, H = 1.3 * r, (ah or ALMOND_H) * r
    eyeball = add(blob(f"{prefix}Eye{sx}", eye, (W, r, H), mat("eye_white", 0.15), subdiv=1, segments=32), "Head")
    front = eye + Vector((0, -r * (0.99 if "eye_k" in LAYOUT else 0.95), 0))   # proud of the white: no speckle
    ix = LAYOUT.get("iris_x", -0.1)                  # iris sideways offset (outer +): centre it in the visible white
    iris_ob = add(blob(f"{prefix}Iris{sx}", front + Vector((sx * r * ix, 0, 0)), (r * 0.6 * LAYOUT.get("iris", 1.0), r * 0.08, (r * 0.6 * LAYOUT.get("iris", 1.0)) if "eye_k" in LAYOUT else H * 0.96), mat(iris_col, 0.15 + 0.35 * LAYOUT.get("soft", 0.0)),
             subdiv=1, segments=24), "Head")
    pk = 1.0 + 0.4 * LAYOUT.get("soft", 0.0)        # bigger, softer pupils
    pupil_ob = add(blob(f"{prefix}Pupil{sx}", front + Vector((sx * r * ix, -r * 0.04, 0)), (r * 0.3 * pk, r * 0.05, (r * 0.3 * pk) if "eye_k" in LAYOUT else H * 0.58 * pk), mat("iris", 0.1),
             subdiv=1), "Head")
    soft = LAYOUT.get("soft", 0.0)                 # warm, friendly eyes: big catch-lights
    gl = r * (0.12 + 0.08 * soft) * (0.6 if "eye_k" in LAYOUT else 1.0)
    gz = H * 0.35 if "eye_k" not in LAYOUT else H * 0.2
    add(blob(f"{prefix}Glint{sx}", front + Vector((sx * r * ix + r * 0.18, -r * 0.12, gz)), (gl, r * 0.04, gl),
             mat("eye_white", 0.02), subdiv=1, segments=12), "Head")
    if soft and "eye_k" not in LAYOUT:
        add(blob(f"{prefix}Glint2{sx}", front + Vector((sx * r * 0.2, -r * 0.1, -H * 0.3)), (r * 0.07, r * 0.03, r * 0.07),
                 mat("eye_white", 0.02), subdiv=0, segments=8), "Head")

    # Eye shape (mapped faces): a flatter upper lid line, a rounder lower edge and
    # an outer corner lifted by `tl` - the eyeball, iris and pupil are reshaped
    # to it (the iris tucks under the upper lid) and both liners follow it.
    tk, bk, tl = LAYOUT.get("eye_k", (1.0, 1.0, 0.0))
    if (tk, bk, tl) != (1.0, 1.0, 0.0):
        for v in eyeball.data.vertices:
            ux, uy, uz = v.co
            v.co.z = uz * (tk if uz > 0 else bk) + tl * sx * ux
        for ob_ in (iris_ob, pupil_ob):
            for v in ob_.data.vertices:              # sit the iris a little high: the upper lid cuts its top
                v.co.z += 0.2 * H / ob_.matrix_world.to_scale().z
            ox = ob_.matrix_world.translation.x - eye.x        # world placement (the part is bone-parented now)
            sc = ob_.matrix_world.to_scale()
            sX, sZ = sc.x, sc.z
            for v in ob_.data.vertices:
                x = ox + v.co.x * sX
                q = math.sqrt(max(0.0, 1 - (x / W) ** 2))
                z = v.co.z * sZ + H * tl * sx * x / W
                z = min(z, H * (tk * q * 0.94 + tl * sx * x / W))
                z = max(z, H * (-bk * q * 0.98 + tl * sx * x / W)) if bk < 1.0 else z
                v.co.z = z / sZ

    def contour(t, k=0.93):          # t in [-1, 1] along the top edge, inner -> outer
        x = t * W * 0.98
        z0 = H * k * math.sqrt(max(0.0, 1 - (x / W) ** 2))
        y = -r * math.sqrt(max(0.0, 1 - (x / W) ** 2 - (z0 / H) ** 2)) - r * 0.06
        return eye + Vector((sx * x, y, z0 * tk + H * tl * x / W))
    pts = [contour(t) for t in (-1.0, -0.6, -0.15, 0.3, 0.75, 1.0)]
    inner = pts[0] + Vector((-sx * r * 0.22, -r * 0.02, -r * 0.16))       # sharp inner point dipping toward the nose
    tip = pts[-1] + Vector((sx * r * 0.45 * wing, -r * 0.05, r * 0.3 * wing))
    lw = LAYOUT.get("liner", 1.0)                   # liner weight (Ink girls: a heavy cat-eye line)
    lo = tube(f"{prefix}LidLiner{sx}", [inner] + pts + [tip],
              [r * 0.01, r * 0.05 * lw, r * 0.11 * lw, r * 0.14 * lw, r * 0.16 * lw, r * 0.16 * lw, r * 0.12 * lw, r * 0.012],
              liner, subdiv=1, ring=10)
    if wing > 0.4:                                  # a second, longer lash sweep off the outer corner
        base = pts[-2]
        spike = tube(f"{prefix}LashSweep{sx}", [base, pts[-1] + Vector((sx * r * 0.2, -r * 0.08, r * 0.12)),
                                                pts[-1] + Vector((sx * r * 0.62 * wing, -r * 0.1, r * 0.06))],
                     [r * 0.08, r * 0.06, r * 0.008], liner, subdiv=1, ring=8)
        lo.data.transform(Matrix.Identity(4))
        bpy.context.view_layer.update()
        me = lo.data
        import bmesh as _bm
        bm = _bm.new()
        bm.from_mesh(me)
        bm.from_mesh(spike.data)
        bm.to_mesh(me)
        bm.free()
        bpy.data.objects.remove(spike)
    lo.data.transform(Matrix.Translation(-eye))
    lo.location = eye
    add(lo, "Head")
    low = [eye + Vector((sx * x * W * 0.9, -r * math.sqrt(max(0.0, 1 - x * x * 0.81 - 0.5)) - r * 0.08,
                         -H * 0.72 * bk * math.sqrt(max(0, 1 - x * x)) + H * tl * x * 0.9))
           for x in (-0.6, -0.1, 0.4, 0.85)] + [pts[-1] + Vector((sx * r * 0.05, 0, -r * 0.05))]   # meets the top line: a closed almond point
    add(tube(f"{prefix}LowLiner{sx}", low, [r * 0.012, r * 0.03, r * 0.04, r * 0.035, r * 0.01], liner, subdiv=1, ring=8), "Head")


def toon_eye(add, prefix, sx, eye, r, skin, iris_col, liner, lashes, wing=1.0):
    """Feature-film eye: a white eyeball, a big dark iris with a large pupil
    and two highlights, a lid that wraps it, a thick black liner along the
    upper lid that sweeps into a wing (it rides the lid), a fine lower line."""
    add(blob(f"{prefix}Eye{sx}", eye, (r * 1.22, r, r * 1.0), mat("eye_white", 0.15), subdiv=1, segments=32), "Head")
    front = eye + Vector((0, -r * 0.94, 0))
    add(blob(f"{prefix}Iris{sx}", front + Vector((-sx * r * 0.05, 0, -r * 0.03)), (r * 0.66, r * 0.1, r * 0.7), mat(iris_col, 0.15),
             subdiv=1, segments=24), "Head")
    pupil_ob = add(blob(f"{prefix}Pupil{sx}", front + Vector((-sx * r * 0.05, -r * 0.05, -r * 0.03)), (r * 0.4, r * 0.06, r * 0.42),
             mat("iris", 0.1), subdiv=1), "Head")
    add(blob(f"{prefix}Glint{sx}", front + Vector((-sx * r * 0.3, -r * 0.12, r * 0.28)), (r * 0.17, r * 0.05, r * 0.17),
             mat("eye_white", 0.02), subdiv=1, segments=12), "Head")
    add(blob(f"{prefix}Glint2{sx}", front + Vector((sx * r * 0.22, -r * 0.11, -r * 0.3)), (r * 0.07, r * 0.03, r * 0.07),
             mat("eye_white", 0.02), subdiv=0, segments=8), "Head")
    lid = lid_shell(f"{prefix}Lid{sx}", eye, r * 1.04, -28, True, skin, liner)  # open and bright at rest
    lid.modifiers["Thick"].thickness = r * 0.08          # thin: the liner, not the lid, carries the line
    lid.scale = (1.2, 1.0, 1.0)                          # as wide as the eyeball
    add(lid, "Head")
    low = lid_shell(f"{prefix}LidLow{sx}", eye, r * 1.03, 30, False, skin, skin)
    low.scale = (1.2, 1.0, 1.0)
    low.modifiers["Thick"].thickness = r * 0.05
    add(low, "Head")
    # Liner: from the inner corner over the top of the eye to a wing past the outer corner.
    def on_eye(ax, az, out=1.12):
        return eye + Vector((sx * ax * r * out * 1.2, -math.sqrt(max(0.0, 1 - ax * ax - az * az)) * r * out, az * r * out))
    # Along the top of the eye: inner corner, over the iris, out into a small lifted flick.
    tip = on_eye(0.92, 0.2).lerp(eye + Vector((sx * r * 1.5, -r * 0.42, r * 0.42)), wing)
    pts = [on_eye(-0.93, -0.08), on_eye(-0.55, 0.62), on_eye(0.0, 0.84), on_eye(0.55, 0.66), on_eye(0.92, 0.2), tip]
    th = 0.6 + 0.4 * wing
    lo = tube(f"{prefix}LidLiner{sx}", pts, [r * 0.05, r * 0.1 * th, r * 0.14 * th, r * 0.15 * th, r * 0.11 * th, r * 0.015],
              liner, subdiv=1, ring=10)
    lo.data.transform(Matrix.Translation(-eye))
    lo.location = eye                                     # pivot at the eye: it rotates with the lid
    add(lo, "Head")
    low = [on_eye(-0.8, -0.45, 1.05), on_eye(0.0, -0.72, 1.05), on_eye(0.8, -0.42, 1.05)]
    add(tube(f"{prefix}LowLiner{sx}", low, [r * 0.02, r * 0.045, r * 0.02], liner, subdiv=1, ring=8), "Head")
    if lashes:
        for k in range(4):
            a = 0.35 + 0.18 * k
            base = on_eye(a, 0.8 - 0.25 * k)
            add(tube(f"{prefix}Lash{sx}{k}", [base, base + Vector((sx * r * 0.35, -r * 0.18, r * 0.32 - 0.06 * k * r))],
                     [r * 0.06, r * 0.01], liner, subdiv=0, ring=6), "Head")


def build_face(add, hc, size, skin, iris_col, brow_col, lip_col, prefix="", nose=1.0, chin=1.0, cheek=1.0,
               jaw=1.0, eye_r=0.022, lashes=False, smirk=1.0, style="planes", lips=1.0, paint=None, brows="cocky",
               wing=1.0, eye_shape="round", grin="open", layout=None):
    if style == "toon":
        return build_toon_face(add, hc, size, skin, iris_col, brow_col, lip_col, prefix, nose, chin, jaw, eye_r, lashes, smirk,
                               lips, paint, brows, wing, eye_shape, grin, layout)
    """Head, sculpted features, eyeballs in their sockets with wrap-around
    lids, heavy shaped brows (one cocked higher) and an asymmetric mouth.
    Part names follow '<prefix>Eye1', '<prefix>Iris-1' ... for face rigs."""
    add(sculpt_head(f"{prefix}Head", hc, size, skin, nose=nose, chin=chin, cheek=cheek, jaw=jaw, smirk=smirk), "Head")
    lash = mat(brow_col, 0.6)
    for sx in (1, -1):
        surf = head_surface(hc, size, sx * 0.37, 0.1)
        eye = surf + Vector((0, eye_r * 0.35, 0))           # set into the socket, front bulging out
        add(blob(f"{prefix}Eye{sx}", eye, (eye_r, eye_r, eye_r), mat("eye_white", 0.25), subdiv=1, segments=24), "Head")
        front = eye + Vector((0, -eye_r * 0.93, 0))
        add(blob(f"{prefix}Iris{sx}", front + Vector((-sx * 0.002, 0, -0.001)), (eye_r * 0.62, eye_r * 0.12, eye_r * 0.66),
                 mat(iris_col, 0.2), subdiv=1), "Head")
        pupil_ob = add(blob(f"{prefix}Pupil{sx}", front + Vector((-sx * 0.002, -eye_r * 0.06, -0.001)), (eye_r * 0.3, eye_r * 0.08, eye_r * 0.32),
                 mat("iris", 0.15), subdiv=1), "Head")
        add(blob(f"{prefix}Glint{sx}", front + Vector((-sx * eye_r * 0.25, -eye_r * 0.14, eye_r * 0.3)),
                 (eye_r * 0.14, eye_r * 0.05, eye_r * 0.14), mat("eye_white", 0.05), subdiv=0, segments=8), "Head")
        add(lid_shell(f"{prefix}Lid{sx}", eye, eye_r * 1.12, -16, True, skin, lash), "Head")   # rest: eye clearly open
        add(lid_shell(f"{prefix}LidLow{sx}", eye, eye_r * 1.08, 14, False, skin, mat(lip_col, 0.6)), "Head")
        # Blocky lash wing at the outer corner (geometry, not a flat strip).
        wing0 = eye + Vector((sx * eye_r * 0.85, -eye_r * 0.55, eye_r * 0.45))
        add(tube(f"{prefix}LashWing{sx}", [wing0, wing0 + Vector((sx * eye_r * 0.55, -eye_r * 0.1, eye_r * 0.32))],
                 [eye_r * 0.2, eye_r * 0.05], lash, subdiv=1, ring=8), "Head")
        if lashes:
            for k in range(3):
                base = eye + Vector((sx * eye_r * (0.6 + 0.2 * k), -eye_r * 0.6, eye_r * (0.75 - 0.2 * k)))
                add(tube(f"{prefix}Lash{sx}{k}", [base, base + Vector((sx * 0.011, -0.004, 0.008))], [0.0025, 0.0008], lash,
                         subdiv=0, ring=6), "Head")
        # Brows: thick, tapered, sitting on the brow ridge; the right one cocked up.
        cock = 0.006 if sx < 0 else 0.0
        b0 = head_surface(hc, size, sx * 0.16, 0.25) + Vector((0, -0.005, cock * 0.3))
        b1 = head_surface(hc, size, sx * 0.36, 0.3) + Vector((0, -0.007, cock))
        b2 = head_surface(hc, size, sx * 0.57, 0.26) + Vector((0, -0.003, cock * 0.6))
        add(recenter(tube(f"{prefix}Brow{sx}", [b0, b1, b2], [0.0095, 0.0085, 0.004], mat(brow_col, 0.7), subdiv=1)),
            "Head")
        for part in ear_shell(f"{prefix}Ear{sx}", hc + Vector((sx * size[0] * 0.8, 0.015, -size[2] * 0.08)),
                              size[2] * 0.55, sx, skin):
            add(part, "Head")
    # Mouth: a crooked line that rises into one cheek, with a dimple.
    pts = []
    for i, ux in enumerate((-0.32, -0.16, 0.0, 0.17, 0.34)):
        pts.append(head_surface(hc, size, ux, smirk_line(ux, smirk)) + Vector((0, -0.0015, 0)))   # sits in the carved crease
    add(tube(f"{prefix}Smile", pts, [0.0015, 0.0028, 0.003, 0.0028, 0.0015], mat("mouth_dark", 0.5), side=Vector((0, 1, 0)),
             subdiv=1), "Head")
    add(tube(f"{prefix}Dimple", [pts[-1] + Vector((0.004, 0.0, 0.006)), pts[-1] + Vector((0.009, 0.002, -0.004))],
             [0.002, 0.0012], mat(lip_col, 0.5), subdiv=0, ring=6), "Head")   # a tucked smirk corner
    build_mouths(add, hc, size, lip_col, prefix)
    build_face_extras(add, hc, size, prefix)
    FACE_INFO[prefix] = dict(hc=hc.copy(), size=size, eye_r=eye_r)


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

HEAD_Z = 1.69   # head centre (on a long, slender neck)
HAIR = "cap"    # "cap" (rust cap over twists) or "messy" (voluminous black hair, no cap)

# His feature layout, measured from the reference frame (head units:
# skull height ~ 285 px; centre at the mid-skull). See README.
# Mapped from the reference (front crop, 1 unit = half face width horizontally,
# skull-top-to-centre vertically): eyes 0.37 below brows, wide-set; nose tip and
# mouth low; small rounded chin; hairline high; ears level with the eyes.
# Ink-style girl, mapped from the reference: a wide flat shield-shaped upper
# face tapering to a tiny pointed chin; huge almond eyes slanting up to the
# temples; a long narrow wedge nose; a wide flat slit mouth.
HER_LAYOUT = dict(eye_ux=0.47, eye_uz=-0.08, nose_z=-0.47, mouth_z=-0.66, chin_z=-1.0, ear_uz=0.0, ear_h=0.6,
                  mouth_w=0.24, almond_h=0.66, liner=1.2, iris=0.78, soft=1.0, brow_drop=-0.04, hairline=0.74,
                  eye_k=(0.8, 1.05, 0.55), eye_sink=0.4, iris_x=0.12, shield=1.0, slit=1.0, pout=0.55)
HIS_LAYOUT = dict(eye_ux=0.37, eye_uz=-0.09, nose_z=-0.36, mouth_z=-0.6, chin_z=-1.06, ear_uz=-0.24, ear_h=0.72,
                  jaw_ref=1.0, slit=1.0, mouth_w=0.2)   # reference: straight long jawline to a broad forward chin   # smooth elongated oval jaw, diamond-plane nose, crisp mouth slit


def messy_hair(add, hc, size, material, n=80, seed=21):
    """Voluminous messy hair: a mass over the crown (lower at the nape), a
    heavy fringe falling to the brows, and wavy tapered clumps flicking out
    in every direction."""
    import bmesh
    import random as _r
    rnd = _r.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=24, radius=1.0)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < 0.3 - 1.0 * max(0.0, v.co.y)], context="VERTS")
    for v in bm.verts:
        v.co = Vector((hc.x + v.co.x * size[0] * 1.16, hc.y + 0.008 + v.co.y * size[1] * 1.14, hc.z + 0.012 + v.co.z * size[2] * 1.12))
    me = bpy.data.meshes.new("HairMass")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    mass = _link(bpy.data.objects.new("HairMass", me))
    sm = mass.modifiers.new("Thick", "SOLIDIFY")
    sm.thickness = 0.012
    _smooth(mass, 1)
    add(mass, "Head")
    brow_z = hc.z + (LAYOUT["eye_uz"] + 0.24) * size[2]
    down = Vector((0, 0, -1))
    for i in range(n):
        th = rnd.uniform(0, 2 * math.pi)                   # around the head (0 = back)
        ph = rnd.uniform(0.25, 0.98)                        # height on the crown
        rr = math.sqrt(1 - ph * ph)
        root = hc + Vector((math.sin(th) * rr * size[0] * 1.12, math.cos(th) * rr * size[1] * 1.12, ph * size[2] * 1.1))
        out = (root - hc).normalized()
        front = math.cos(th) < -0.25 and ph < 0.85
        tdown = down - out * out.dot(down)
        tdown = tdown.normalized() if tdown.length > 1e-3 else Vector((math.sin(th), math.cos(th), 0))
        side = out.cross(tdown).normalized()
        # Locks fall with gravity along the head, lift off it a little, and curl.
        d = (tdown * 0.75 + out * (0.25 if not front else 0.15) + side * rnd.uniform(-0.45, 0.45)).normalized()
        L1 = rnd.uniform(0.07, 0.13)
        curl = rnd.uniform(-1.4, 1.4)
        pts, p, dd = [root], root.copy(), d.copy()
        for k in range(4):
            dd = (dd + side * curl * 0.35 + out * 0.08).normalized()
            p = p + dd * L1 / 4
            if front and p.z < brow_z:                     # the fringe stops at the brows
                p.z = brow_z + rnd.uniform(0.0, 0.006)
            pts.append(p.copy())
        w = rnd.uniform(0.011, 0.02)
        add(tube(f"HairLock{i}", pts, [(w, w * 0.45), (w * 0.95, w * 0.42), (w * 0.75, w * 0.35), (w * 0.45, w * 0.25),
                                       (w * 0.08, w * 0.06)], material, side=side, subdiv=1, ring=8), "Head")
    for i in range(14):                                     # a few flyaway strands catching the light
        th = rnd.uniform(0, 2 * math.pi)
        root = hc + Vector((math.sin(th) * size[0] * 0.6, math.cos(th) * size[1] * 0.6, size[2] * 1.0))
        out = (root - hc).normalized()
        a = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0.2, 1))).normalized()
        pts = [root, root + a * 0.03 + out * 0.02, root + a * 0.06 + out * 0.03 + Vector((0, 0, -0.01)),
               root + a * 0.08 + out * 0.02 + Vector((0, 0, -0.03))]
        add(tube(f"HairFly{i}", pts, [0.002, 0.0018, 0.0014, 0.0006], material, subdiv=1, ring=6), "Head")


def strand_hair(add, hc, size, material, guides=120, per=70, seed=7, scalp=None):
    """Real hair: Blender hair curves, ~5,000 fine strands grown in clumps.

    Guide locks are spread over the scalp (a golden-angle spiral; lower at
    the back and sides, a hairline at the front). Each guide lifts off the
    head for volume, then falls with gravity, waving sideways and curling at
    the end; it is kept outside the skull, and fringe locks stop at the
    brows. Every guide grows a clump of strands around it that gather toward
    the tip (clumping), with fine waves and frizz; a few loose flyaways."""
    import random as _r
    rnd = _r.Random(seed)
    sx, sy, sz = size
    brow_z = hc.z + (LAYOUT["eye_uz"] + 0.22) * sz
    down = Vector((0, 0, -1))

    def outside(p, k=1.07):            # push a point out of the skull ellipsoid
        q = Vector(((p.x - hc.x) / sx, (p.y - hc.y) / sy, (p.z - hc.z) / sz))
        if q.length < k:
            q = q.normalized() * k
            return Vector((hc.x + q.x * sx, hc.y + q.y * sy, hc.z + q.z * sz))
        return p

    guides_pts = []
    golden = math.pi * (3 - math.sqrt(5))
    i = 0
    while len(guides_pts) < guides and i < guides * 6:
        i += 1
        zz = 1 - 1.25 * (i / (guides * 1.6))              # spiral from the crown down
        th = i * golden
        ph = zz
        if ph < -0.35:
            continue
        rr = math.sqrt(max(0.0, 1 - ph * ph))
        n = Vector((math.sin(th) * rr, math.cos(th) * rr, ph))
        front = n.y < -0.35
        if front and ph < 0.45:                             # hairline: no roots on the forehead
            continue
        if abs(n.x) > 0.55 and n.y < 0.2 and ph < -0.05:  # leave the face/temples clear
            continue
        root = Vector((hc.x + n.x * sx * 1.02, hc.y + n.y * sy * 1.02, hc.z + n.z * sz * 1.02))
        out = (root - hc).normalized()
        tdown = down - out * out.dot(down)
        tdown = tdown.normalized() if tdown.length > 1e-3 else Vector((math.sin(th), math.cos(th), 0)).normalized()
        side = out.cross(tdown).normalized()
        crown = ph > 0.75
        sidecut = abs(n.x) > 0.62 and n.y < 0.45            # shorter over the ears so they show
        L = rnd.uniform(0.12, 0.17)
        if front:                                           # fringe: falls down the forehead to the brows
            L = rnd.uniform(0.1, 0.14)
        if sidecut:
            L = rnd.uniform(0.06, 0.09)
        wave = rnd.uniform(0.7, 1.2) * rnd.choice((-1, 1))
        lift = rnd.uniform(0.2, 0.3) if crown else rnd.uniform(0.08, 0.18)    # a little volume on top, hugging at the sides
        pts, p, d = [root], root.copy(), (out * lift + tdown * (1 - lift) + side * rnd.uniform(-0.25, 0.25)).normalized()
        segs = 16
        for k in range(1, segs + 1):
            t = k / segs
            here = (p - hc).normalized()
            tdn = down - here * here.dot(down)              # gravity along the head's surface where the lock is now
            tdn = tdn.normalized() if tdn.length > 1e-3 else tdown
            # Waves: an S along the lock, then a curl that turns back on itself at the end.
            d = (d + tdn * 0.32 * t + side * wave * 0.11 * math.sin(t * 4.5) + here * 0.02).normalized()
            if t > 0.7:                                     # a soft curl at the end
                d = (d + side * wave * 0.16 + here * 0.08).normalized()
            p = outside(p + d * L / segs)
            if front and p.z < brow_z:
                p.z = brow_z + 0.002
            pts.append(p.copy())
        guides_pts.append((pts, side, out, front))

    total = len(guides_pts) * per + 60
    hair = bpy.data.hair_curves.new("HairStrands")
    seg = 17
    hair.add_curves([seg] * total)
    pos, rad = [], []
    for pts, side, out, front in guides_pts:
        up = side.cross(out).normalized()
        for _ in range(per):
            a = rnd.uniform(0, 2 * math.pi)
            r0 = 0.019 * math.sqrt(rnd.random())
            off = side * math.cos(a) * r0 + up * math.sin(a) * r0
            ph1, ph2 = rnd.uniform(0, 6.28), rnd.uniform(0, 6.28)
            for k, gp in enumerate(pts):
                t = k / (len(pts) - 1)
                clump = 1 - 0.75 * t ** 1.3                 # strands gather toward the tip
                frizz = 0.0025 * t * (math.sin(t * 14 + ph1) * side + math.cos(t * 11 + ph2) * up)
                q = gp + off * clump + frizz
                pos.extend(q)
                rad.append(0.0011 * (1 - 0.75 * t) + 0.0002)
    for _ in range(60):                                     # flyaways
        pts, side, out, front = guides_pts[rnd.randrange(len(guides_pts))]
        base = pts[rnd.randrange(2, 5)]
        d = (out + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0, 1)))).normalized()
        for k in range(seg):
            t = k / (seg - 1)
            q = base + d * 0.06 * t + side * 0.02 * math.sin(t * 4) + Vector((0, 0, -0.02 * t * t))
            pos.extend(q)
            rad.append(0.0006 * (1 - 0.7 * t) + 0.0001)
    hair.position_data.foreach_set("vector", pos)
    ra = hair.attributes.get("radius") or hair.attributes.new("radius", "FLOAT", "POINT")
    ra.data.foreach_set("value", rad)
    hair.materials.append(material)
    ob = _link(bpy.data.objects.new("HairStrands", hair))
    add(ob, "Head")
    if scalp is not None:                                   # a dark mass under the strands: no scalp shows through
        import bmesh
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=24, radius=1.0)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < 0.3 - 1.2 * max(0.0, v.co.y)], context="VERTS")
        for v in bm.verts:
            v.co = Vector((hc.x + v.co.x * sx * 1.03, hc.y + v.co.y * sy * 1.03, hc.z + v.co.z * sz * 1.03))
        me = bpy.data.meshes.new("HairScalp")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(scalp)
        so = _link(bpy.data.objects.new("HairScalp", me))
        _smooth(so, 1)
        add(so, "Head")
    return ob


def matte_hair_material(col):
    """Matte vinyl hair: roughness 0.95, no specular, a little warm
    subsurface so rim light glows through the thin tips, and a fine
    clay grain (noise 600 -> bump 0.03)."""
    m = bpy.data.materials.new("Matte_Hair_Clay")
    if getattr(m, "node_tree", None) is None and hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = 0.95
    if "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = 0.0
    if "Subsurface Weight" in b.inputs:
        b.inputs["Subsurface Weight"].default_value = 0.03          # near-black, not brown, in warm light
        b.inputs["Subsurface Radius"].default_value = (0.6, 0.5, 0.5)
    if "Sheen Weight" in b.inputs:                                   # bright cream edge where the rim grazes the locks
        b.inputs["Sheen Weight"].default_value = 0.0
        b.inputs["Sheen Roughness"].default_value = 0.6
        b.inputs["Sheen Tint"].default_value = (1.0, 0.92, 0.8, 1)
        if "Subsurface Scale" in b.inputs:
            b.inputs["Subsurface Scale"].default_value = 0.01
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 600.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.03
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    m.diffuse_color = col
    return m


def ribbon_hair(add, hc, size, material, seed=11, style="messy", prefix=""):
    """Hair from chunky Bezier ribbons, in three layers:
      1. a bumpy dark helmet hugging the skull (no scalp shows, it is the shadow layer);
      2. thick ribbon locks - flattened 'football' profile, fat in the middle,
         pinched to a point, tilted so they overlap - swooping across the
         crown, a fringe sweeping over the brows, sides sweeping back past
         the ears, the back falling to the nape;
      3. a few thin breakout ribbons looping off the head."""
    import bmesh
    import random as _r
    rnd = _r.Random(seed)
    sx, sy, sz = size
    # Profile: a squashed football (wide and flat), used as every lock's bevel.
    prof_data = bpy.data.curves.new("Hair_Profile", "CURVE")
    sp = prof_data.splines.new("POLY")
    pts = [(math.cos(a) * 0.013, math.sin(a) * 0.0032 * (1 - 0.35 * abs(math.cos(a))), 0) for a in
           [2 * math.pi * k / 12 for k in range(12)]]
    sp.points.add(len(pts) - 1)
    for p_, q in zip(sp.points, pts):
        p_.co = (*q, 1.0)
    sp.use_cyclic_u = True
    profile = _link(bpy.data.objects.new("Hair_Profile", prof_data))
    profile.hide_render = True
    profile.hide_viewport = True

    # 1. Helmet: the shadow layer, hairline low on the forehead, temples down to the ears.
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=28, radius=1.0)
    hair_front = LAYOUT.get("hairline") or LAYOUT["eye_uz"] + (0.62 if style in ("sleek", "ponytail") else 0.42)

    def keep(v):
        x, y, z = v.co
        if y > 0.2:                                   # back: down to the nape
            return z > -0.35
        if abs(x) > 0.72:                             # sides: to the top of the ears
            return z > (0.1 if style in ("sleek", "ponytail") else -0.05)
        if style in ("sleek", "ponytail"):            # a soft rounded hairline dipping at the temples
            return z > hair_front - 0.3 * x * x
        return z > hair_front + 0.08 * (abs(x) > 0.45)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not keep(v)], context="VERTS")
    for v in bm.verts:
        bump = 1.0 + 0.03 * math.sin(v.co.x * 9 + 1) * math.sin(v.co.y * 7 + 2) * math.sin(v.co.z * 8)
        v.co = Vector((hc.x + v.co.x * sx * 1.05 * bump, hc.y + v.co.y * sy * 1.05 * bump, hc.z + v.co.z * sz * 1.04 * bump))
    me = bpy.data.meshes.new("Hair_Helmet")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    helmet = _link(bpy.data.objects.new(prefix + "Hair_Helmet", me))
    _smooth(helmet, 1)
    add(helmet, "Head")

    def shell(p, k):
        """Put p on the ellipsoid shell k (unit = head size): locks lie on the head."""
        q = Vector(((p.x - hc.x) / sx, (p.y - hc.y) / sy, (p.z - hc.z) / sz))
        if q.length < 1e-6:
            return p
        q = q.normalized() * k
        return Vector((hc.x + q.x * sx, hc.y + q.y * sy, hc.z + q.z * sz))

    brow_z = hc.z + (LAYOUT["eye_uz"] + 0.17) * sz

    def lock(name, root_n, aim, length, width, k=1.12, puff=0.08, curl=0.0, tilt=0.0, stop_brow=False,
             n=8, free=False, lift=0.0, flick=0.25, path=None):
        """One ribbon: from a root on the head, heading `aim` along the shell
        (puffing out in the middle for volume), curling at the tip; fat
        middle, sharp tip. free=True lets it leave the head (breakouts)."""
        name = prefix + name
        p = shell(Vector(root_n) * 0 + Vector((hc.x + root_n[0] * sx, hc.y + root_n[1] * sy, hc.z + root_n[2] * sz)), k)
        d = Vector(aim).normalized()
        pts = [p.copy()] if path is None else [Vector(q) for q in path]
        for i_ in range(1, n if path is None else 0):
            t = i_ / (n - 1)
            here = Vector(((p.x - hc.x) / sx, (p.y - hc.y) / sy, (p.z - hc.z) / sz)).normalized()
            d = (d - here * here.dot(d)).normalized() if not free else d
            if curl and t > 0.5:
                d = (d + here.cross(d) * curl * 0.45 * t).normalized()
            if free:                                   # loop: keep turning about one axis
                if i_ == 1:
                    axis = here.cross(d).normalized()
                d = (Matrix.Rotation(curl * 0.55, 3, axis) @ d + here * lift * (1 - t)).normalized()
            p = p + d * length / (n - 1)
            if not free:
                p = shell(p, k + puff * math.sin(math.pi * t) + flick * max(0.0, t - 0.55) ** 2 * 5)
            if stop_brow and p.z < brow_z:
                p.z = brow_z
                p = shell(p, k + 0.02) if not free else p
            pts.append(p.copy())
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions = "3D"
        cu.bevel_mode = "OBJECT"
        cu.bevel_object = profile
        cu.use_fill_caps = True
        cu.resolution_u = 8
        cu.twist_mode = "MINIMUM"
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(len(pts) - 1)
        prof = [0.5, 0.95, 1.12, 1.1, 0.9, 0.55, 0.06]
        for i_, (bp, q) in enumerate(zip(sp.bezier_points, pts)):
            bp.co = q
            bp.handle_left_type = bp.handle_right_type = "AUTO"
            bp.radius = width * prof[min(int(i_ * (len(prof) - 1) / max(1, len(pts) - 1) + 0.5), len(prof) - 1)]
            bp.tilt = tilt + 0.3 * math.sin(i_ * 1.3)
        cu.materials.append(material)
        ob = _link(bpy.data.objects.new(name, cu))
        add(ob, "Head")
        return ob

    from mathutils import Matrix
    def unit_path(name, upts, width, tilt=0.0, k=1.07):
        """A ribbon through points given in head units, pushed out onto shell k wherever they would sink into the head."""
        pts = []
        for u in upts:
            q = Vector(u)
            if q.length < k:
                q = q.normalized() * k
            pts.append(Vector((hc.x + q.x * sx, hc.y + q.y * sy, hc.z + q.z * sz)))
        lock(name, (0, 0, 1), (0, 0, -1), 0, width, tilt=tilt, path=pts)

    if style == "ponytail":
        # Centre part; hair combed from the part down both sides and back to a low
        # tie at the nape; a ponytail hanging from it; loose strands from the part
        # falling past the cheeks; a few flyaways on top.
        for sgn in (1, -1):
            for i in range(11):
                t = i / 10
                root = (sgn * 0.04, -0.62 + 1.2 * t, math.sqrt(max(0.0, 1 - 0.0016 - (-0.62 + 1.2 * t) ** 2)))
                lock(f"HairComb{sgn}_{i}", root, (sgn * 1.0, 0.55 + 0.4 * t, -0.45), rnd.uniform(0.24, 0.29),
                     rnd.uniform(1.7, 2.1), k=1.06 + 0.012 * (i % 3), puff=0.05, flick=0.0, curl=sgn * rnd.uniform(0.2, 0.5),
                     tilt=sgn * 0.5)
        tie = Vector((hc.x, hc.y + 0.95 * sy, hc.z - 0.4 * sz))
        add(torus(prefix + "HairTie", tie, 0.016, 0.007, material, axis="Y"), "Head")
        for i in range(9):
            a = i * 2 * math.pi / 9
            off = Vector((math.cos(a) * 0.008, 0.012 + math.sin(a) * 0.006, 0))
            pts = [tie + off, tie + off * 1.6 + Vector((0, 0.03, -0.06)), tie + off * 2.0 + Vector((0, 0.035, -0.13)),
                   tie + off * 1.8 + Vector((0, 0.03, -0.2)), tie + off * 1.2 + Vector((0, 0.02, -0.26))]
            lock(f"HairTail{i}", (0, 0, 1), (0, 0, -1), 0, rnd.uniform(1.5, 1.9), tilt=a, path=pts)
        for sgn in (1, -1):                               # face-framing strands from the part
            for j, (x0, wide, low) in enumerate(((0.1, 0.93, -0.8), (0.18, 0.98, -0.6), (0.26, 1.04, -1.0), (0.14, 0.9, -0.45),
                                                 (0.3, 1.1, -0.85))):
                upts = [(sgn * x0, -0.85, hair_front + 0.12), (sgn * (x0 + 0.25), -0.85, hair_front - 0.05),
                        (sgn * (wide - 0.05), -0.62, LAYOUT["eye_uz"] + 0.1), (sgn * wide, -0.45, LAYOUT["eye_uz"] - 0.25),
                        (sgn * (wide - 0.05), -0.35, low + 0.25), (sgn * (wide + 0.04), -0.3, low)]
                unit_path(f"HairFrame{sgn}_{j}", upts, rnd.uniform(0.55, 0.85), tilt=sgn * 0.4, k=1.06)
        for i, (n_, aim) in enumerate((((-0.75, -0.2, 0.5), (-0.6, 0.3, -0.7)), ((0.8, 0.0, 0.45), (0.5, 0.4, -0.8)))):
            lock(f"HairFly{i}", n_, aim, rnd.uniform(0.07, 0.09), 0.2, k=1.12, curl=rnd.choice((-0.6, 0.6)), free=True, lift=0.1)
        return
    if style == "sleek":
        # Sleek, pulled-back hair: ribbons combed from the hairline straight
        # back over the skull (lying flat, barely any puff), long locks falling
        # down the back past the shoulders, a few loose wisps by the face.
        for i in range(22):
            a = -1.25 + i * (2.5 / 21)                      # around the hairline, temple to temple
            root = (math.sin(a) * 0.92, -math.cos(a) * 0.62, hair_front + 0.06 + 0.25 * abs(math.sin(a)) ** 2)
            lock(f"HairComb{i}", root, (math.sin(a) * 0.15, 1.0, 0.35 - 0.5 * abs(math.sin(a))), rnd.uniform(0.26, 0.32),
                 rnd.uniform(1.5, 1.9), k=1.05 + 0.012 * (i % 3), puff=0.025, flick=0.0, curl=rnd.uniform(-0.2, 0.2),
                 tilt=math.sin(a) * 0.6)
        for i in range(16):
            a = -1.1 + i * (2.2 / 15)
            x0 = math.sin(a) * 0.85
            top = Vector((hc.x + x0 * sx * 1.05, hc.y + 0.75 * sy * 1.05 + 0.01, hc.z + 0.35 * sz))
            pts = [top, top + Vector((x0 * 0.01, 0.035, -0.08)), top + Vector((x0 * 0.03, 0.05, -0.17)),
                   top + Vector((x0 * 0.06, 0.06, -0.27)), top + Vector((x0 * 0.09, 0.055, -0.37)),
                   top + Vector((x0 * 0.1, 0.045, -0.45))]
            lock(f"HairFall{i}", (0, 0, 1), (0, 0, -1), 0, rnd.uniform(1.6, 2.1), tilt=rnd.uniform(-0.3, 0.3), path=pts)
        for i, (x0, sgn) in enumerate(((-0.8, -1), (0.82, 1), (-0.88, -1))):   # loose wisps at the temples
            p0 = Vector((hc.x + x0 * sx, hc.y - 0.45 * sy, hc.z + (hair_front - 0.05) * sz))
            pts = [p0, p0 + Vector((sgn * 0.01, -0.012, -0.04)), p0 + Vector((sgn * 0.022, -0.016, -0.09)),
                   p0 + Vector((sgn * 0.03, -0.012, -0.14)), p0 + Vector((sgn * 0.045, -0.004, -0.19))]
            lock(f"HairWisp{i}", (0, 0, 1), (0, 0, -1), 0, 0.2, tilt=0.0, path=pts)
        return
    # 2a. Crown: big locks from a whorl at the back of the crown, swooping forward and out.
    whorl = (0.1, 0.45, 0.88)
    for i in range(18):
        a = -math.pi * 0.92 + i * (math.pi * 1.84 / 17)
        aim = (math.sin(a), -abs(math.cos(a)) - 0.2, -0.1)
        lock(f"HairCrown{i}", (whorl[0] + rnd.uniform(-0.12, 0.12), whorl[1] + rnd.uniform(-0.1, 0.1), whorl[2]), aim,
             rnd.uniform(0.17, 0.24), rnd.uniform(1.6, 2.1), k=rnd.uniform(1.12, 1.22), puff=rnd.uniform(0.1, 0.22), flick=0.3,
             curl=rnd.uniform(-1.0, 1.0), tilt=rnd.uniform(-0.5, 0.5))
    # 2b. Fringe: chunky locks sweeping down and across the forehead, over the brows.
    for i in range(12):
        x0 = -0.75 + i * 0.135
        side = 1.0 if x0 > -0.35 else -0.6                         # main sweep to his left, a few the other way
        aim = (side * (0.5 + rnd.uniform(-0.2, 0.2)), -0.3, -1.0)
        lock(f"HairFringe{i}", (x0, -0.4, 0.82), aim, rnd.uniform(0.12, 0.16), rnd.uniform(1.4, 1.9),
             k=1.07 + 0.025 * (i % 3), puff=rnd.uniform(0.06, 0.12), curl=side * rnd.uniform(0.6, 1.3),
             tilt=rnd.uniform(-0.4, 0.4), stop_brow=True, flick=0.12)
    # 2b'. Temples: short locks closing the gap between fringe and sides.
    for sgn in (1, -1):
        for i in range(3):
            lock(f"HairTemple{sgn}_{i}", (sgn * (0.62 + 0.08 * i), -0.55 + 0.12 * i, 0.55 - 0.05 * i), (sgn * 0.2, -0.1, -1.0),
                 rnd.uniform(0.09, 0.12), rnd.uniform(1.3, 1.6), k=1.08, puff=0.08, flick=0.2,
                 curl=sgn * rnd.uniform(0.4, 0.9), tilt=sgn * 0.4, stop_brow=True)
    # 2c. Sides: sweeping back and down past the ears, flicking out.
    for sgn in (1, -1):
        for i in range(7):
            zz = 0.7 - i * 0.12
            aim = (sgn * 0.15, 0.6, -1.0)
            lock(f"HairSide{sgn}_{i}", (sgn * 0.75, -0.25 + i * 0.08, zz), aim, rnd.uniform(0.1, 0.15), rnd.uniform(1.3, 1.8),
                 k=rnd.uniform(1.1, 1.18), puff=0.12, flick=0.45, curl=sgn * rnd.uniform(0.5, 1.2), tilt=sgn * rnd.uniform(0.2, 0.6))
    # 2d. Back: falling to the nape, flicking out at the tips.
    for i in range(12):
        a = -1.3 + i * (2.6 / 11)
        lock(f"HairBack{i}", (math.sin(a) * 0.7, 0.8, 0.5 + 0.1 * math.cos(a * 2)), (math.sin(a) * 0.3, 0.25, -1.0),
             rnd.uniform(0.16, 0.22), rnd.uniform(1.5, 2.0), k=rnd.uniform(1.1, 1.18), puff=0.14, flick=0.4,
             curl=rnd.uniform(-1.0, 1.0), tilt=rnd.uniform(-0.4, 0.4))
    # 3. Breakouts: thin ribbons looping off the head.
    for i, (n_, aim) in enumerate((((-0.3, 0.1, 0.95), (-0.7, -0.3, 0.7)), ((0.3, 0.3, 0.95), (0.7, 0.2, 0.8)),
                                   ((0.7, -0.1, 0.7), (1.0, -0.3, 0.2)), ((-0.75, 0.2, 0.6), (-1.0, 0.3, 0.3)),
                                   ((0.0, 0.6, 0.8), (0.1, 0.8, 0.6)))):
        lock(f"HairBreak{i}", n_, aim, rnd.uniform(0.1, 0.14), 0.75, k=1.15, curl=rnd.choice((-1.0, 1.0)), free=True, lift=0.3)


def hair_material(col_root, col_tip):
    """Hair shading: dark at the root, a touch warmer at the tips, soft sheen."""
    m = bpy.data.materials.new("HairStrandMat")
    if getattr(m, "node_tree", None) is None and hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    info = nt.nodes.new("ShaderNodeHairInfo")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = col_root
    ramp.color_ramp.elements[1].color = col_tip
    nt.links.new(info.outputs["Intercept"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.5
    if "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = 0.28
    return m


def cap_crown(name, center, size, material):
    """Cloth crown that collapses against the head: a half-dome slouched at
    the back, slightly asymmetric, with a soft pinch at the front panels."""
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=1.0)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.12], context="VERTS")
    for v in bm.verts:
        x, y, z = v.co
        z -= 0.22 * max(0.0, y) * max(0.0, z)                 # slouch at the back
        x *= 1 + 0.06 * max(0.0, y) * (1 if x > 0 else 0.4)   # asymmetric sag
        z += 0.05 * _g(x, 0.3, 0.25) * _g(y, -0.4, 0.3)       # a lump in one front panel
        z -= 0.03 * _g(x, 0, 0.08) * max(0.0, -y)             # front centre seam dip
        v.co = Vector((center.x + x * size[0], center.y + y * size[1], center.z + z * size[2]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    ob = _link(bpy.data.objects.new(name, me))
    m = ob.modifiers.new("Thick", "SOLIDIFY")
    m.thickness = 0.006
    _smooth(ob, 1)
    return ob


def cap_brim(name, center, r_in, depth, material):
    """Brim: a front half-annulus that bends down at its sides, wrapping
    around the eyes (the 'spunky' curve), tip dipping slightly."""
    verts, faces = [], []
    na, nr = 24, 5
    for i in range(na + 1):
        th = math.radians(-100 + 200 * i / na)               # 0 = straight ahead (-Y)
        for j in range(nr + 1):
            w = j / nr
            reach = depth * (0.25 + 0.75 * math.cos(math.radians(-100 + 200 * i / na) * 0.8) ** 2)
            r = r_in * 0.98 + reach * w
            x, y = r * math.sin(th), -r * math.cos(th)
            z = -0.03 * (th / math.radians(100)) ** 2 * w - 0.008 * w * w
            verts.append((center.x + x, center.y + y, center.z + z))
    for i in range(na):
        for j in range(nr):
            a = i * (nr + 1) + j
            faces.append((a, a + 1, a + nr + 2, a + nr + 1))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.materials.append(material)
    ob = _link(bpy.data.objects.new(name, me))
    m = ob.modifiers.new("Thick", "SOLIDIFY")
    m.thickness = 0.009
    _smooth(ob, 1)
    return ob


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
        F = -math.pi / 2
        sh_folds = folds([(0.78, F - 0.9, 0.74, F + 0.9, 0.01, 0.012), (0.3, F + 0.4, 0.62, F + 1.2, 0.009, 0.012),
                          (0.88, -F - 0.8, 0.84, -F + 0.8, 0.008, 0.011)], length=0.3, radius=0.1)
        add(tube(f"ShortLeg_{s}", arc(hip + Vector((0, 0, 0.03)), hem, n=4), [(0.104, 0.1), (0.108, 0.1), (0.11, 0.098),
                                                                             (0.108, 0.095)], sh, caps=False, subdiv=1,
                 ring=40, rows=14, profile="box", p_exp=4.0, carve=sh_folds),
            f"Thigh_{s}")
        add(tube(f"ShortHem_{s}", [hem + Vector((0, 0, -0.01)), hem + Vector((0, 0, 0.02))], [(0.107, 0.097), (0.107, 0.097)],
                 mat("strap", 0.85), caps=False, subdiv=1), f"Thigh_{s}")
    # Boxy oversized work shirt, carved like architecture: a rigid block whose
    # shoulder line runs flat from the collar out to the sleeves, flat panels,
    # and sharp folds - drags from the armpits, stacked folds at the hem.
    shirt = mat("shirt", 0.8, sheen=0.3)
    F = -math.pi / 2                      # angle of the front (-Y) on a vertical tube
    body = [(0, 0.01, 0.88), (0, 0.01, 1.0), (0, 0.0, 1.15), (0, 0.0, 1.3), (0, 0.0, 1.39), (0, 0.0, 1.44), (0, 0.0, 1.465)]
    shirt_folds = folds([
        (0.86, F + 1.0, 0.42, F + 0.35, 0.024, 0.02), (0.86, F - 1.0, 0.42, F - 0.35, 0.024, 0.02),     # armpit drags
        (0.72, F + 0.65, 0.52, F + 0.12, 0.016, 0.014), (0.72, F - 0.65, 0.52, F - 0.12, 0.016, 0.014),
        (0.13, F - 1.3, 0.1, F + 1.3, 0.016, 0.015), (0.22, F - 0.9, 0.24, F + 0.95, 0.012, 0.012),      # hem stack
        (0.86, -F - 0.7, 0.55, -F + 0.1, 0.012, 0.015),                                                   # back drag
    ], length=0.58, radius=0.2)
    add(tube("Shirt", body, [(0.235, 0.165), (0.245, 0.17), (0.248, 0.168), (0.255, 0.165), (0.27, 0.155),
                             (0.2, 0.12), (0.08, 0.07)], shirt, ring=48, rows=26, profile="box", p_exp=5.0,
             carve=shirt_folds, subdiv=1), "Spine")
    add(tube("ShirtHem", [(0, 0.01, 0.872), (0, 0.01, 0.89)], [(0.238, 0.168), (0.238, 0.168)], shirt, ring=48,
             profile="box", p_exp=5.0, subdiv=1), "Pelvis")
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
        # Sleeve: grows out of the flat shoulder line, then drops as a heavy block.
        # Hang from the shoulder line: the sleeve's top face continues the torso's.
        root = Vector((sx * 0.13, 0.0, 1.3))
        top = Vector((sx * 0.27, 0.0, 1.285))
        drop = Vector((sx * 0.3, 0.01, 1.19))
        cuff_c = Vector((sx * 0.31, 0.01, 1.1))
        inner = math.pi if sx > 0 else 0.0               # the side facing the body
        sl_folds = folds([
            (0.35, inner - 0.7, 0.62, inner + 0.25, 0.02, 0.016), (0.5, inner - 0.9, 0.78, inner + 0.1, 0.016, 0.014),
            (0.45, -inner + 0.5, 0.85, -inner - 0.3, 0.012, 0.014),
        ], length=0.42, radius=0.11)
        add(tube(f"Sleeve_{s}", [root, top, drop, cuff_c], [(0.1, 0.105), (0.115, 0.11), (0.122, 0.112), (0.118, 0.108)],
                 shirt, caps=False, ring=40, rows=20, profile="box", p_exp=4.5, carve=sl_folds, subdiv=1,
                 side=Vector((0, 1, 0))), f"UpperArm_{s}")
        # Rolled, blocky cuff.
        d = (cuff_c - drop).normalized()
        add(tube(f"Cuff_{s}", [cuff_c - d * 0.012, cuff_c + d * 0.022], [(0.124, 0.114), (0.122, 0.112)], mat("shirt_seam", 0.8),
                 caps=False, ring=40, profile="box", p_exp=4.5, subdiv=1, side=Vector((0, 1, 0))), f"UpperArm_{s}")
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
    # Neck and head: a sculpted, planar face (see build_face).
    add(tube("Neck", [(0, 0.01, 1.42), (0, 0.0, HEAD_Z - 0.09)], [0.056, 0.05], skin), "Neck")   # slim but strong neck
    hc = Vector((0, -0.01, HEAD_Z))
    # Young and energetic: a rounder face with full cheeks and a short soft
    # chin, big bright eyes, a small nose, lifted brows, healthy blush, no stubble.
    # Young, cool and cocky (feature-film street style): a longer face with a
    # defined chin, narrow almond eyes under heavy lines, brows diving to the
    # nose, a rosy nose tip and cheeks, a crooked crescent grin.
    # Measured from the reference: a long face, narrow heavy-lidded eyes set
    # below mid-skull, thick level brows, a long nose with a rosy tip, a thin
    # closed smirk, a long defined chin, big low ears.
    build_face(add, hc, (0.108, 0.118, 0.15), skin, "iris", "hair", "lip_toon", nose=1.45, chin=1.2, cheek=1.0, jaw=0.45,
               eye_r=0.024, smirk=0.4, style="toon", lips=0.45, paint=("skin", "blush_toon", "lip_toon", None),
               brows="bushy", wing=0.35, eye_shape="almond", grin="crescent", layout=HIS_LAYOUT)
    if HAIR == "messy":
        messy_hair(add, hc, (0.1, 0.118, 0.15), mat("hair", 0.45, sheen=0.3))
        return parts
    if HAIR == "ribbons":
        ribbon_hair(add, hc, (0.108, 0.118, 0.15), matte_hair_material(hx("#050406")))
        return parts
    if HAIR == "strands":
        strand_hair(add, hc, (0.108, 0.118, 0.15), hair_material(hx("#060508"), hx("#1d1716")),
                    scalp=mat("hair", 0.6))
        return parts
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
    # Rust cap: a slouched, seamed crown and a brim bent down around the eyes.
    capm = mat("cap", 0.75, sheen=0.3)
    add(cap_crown("CapCrown", hc + Vector((0, 0.012, 0.078)), (0.13, 0.136, 0.1), capm), "Head")   # sits back: eyes clear
    add(box("CapBand", hc + Vector((0, 0.005, 0.06)), (0.25, 0.26, 0.03), capm, bevel=0.012), "Head").hide_render = True
    add(cap_brim("CapBrim", hc + Vector((0, 0.008, 0.083)), 0.128, 0.07, capm), "Head")
    add(blob("CapButton", hc + Vector((0, 0.019, 0.176)), (0.012, 0.012, 0.008), capm, subdiv=1), "Head")
    for k in range(6):   # panel seams from the button down the crown
        a = math.radians(-90 + k * 60)
        seam = [hc + Vector((0, 0.019, 0.173)) + Vector((math.cos(a) * r * 0.13, math.sin(a) * r * 0.136, -0.1 * r * r))
                for r in (0.15, 0.5, 0.85, 1.0)]
        add(tube(f"CapSeam{k}", seam, [0.0018] * 4, mat("shirt_seam", 0.7) if False else mat("cap_seam", 0.7), subdiv=0,
                 ring=6), "Head")
    return parts


# ---------------------------------------------------------------------------
# Face rig: named controls -> geometry, and an expression library
# ---------------------------------------------------------------------------

EXPRESSIONS = {
    # his
    "COOL":    dict(lid=0.6, lid_low=0.2, brow_l=-0.001, brow_r=0.004, ang_l=-4, ang_r=-6, mouth="SMIRK"),
    "HAPPY":   dict(lid=1.0, lid_low=0.35, brow_l=0.006, brow_r=0.007, ang_l=-6, ang_r=6, mouth="GRIN"),
    "NOTICE":  dict(lid=1.15, lid_low=0.0, brow_l=0.002, brow_r=0.007, ang_l=0, ang_r=-6, mouth="FLAT", gaze=(0.35, 0.0)),
    "SHOCK":   dict(lid=1.5, lid_low=0.0, brow_l=0.011, brow_r=0.011, ang_l=12, ang_r=-12, mouth="GASP", pupil=0.55,
                    sweat=1.0),
    "STRUCK":  dict(lid=0.95, lid_low=0.3, brow_l=0.007, brow_r=0.007, ang_l=10, ang_r=-10, mouth="O", pupil=1.45,
                    sparkle=1.0, blush=1.0),
    "DAZED":   dict(lid=0.7, lid_low=0.4, brow_l=0.005, brow_r=0.005, ang_l=8, ang_r=-8, mouth="GRIN", pupil=1.3,
                    sparkle=0.7, blush=1.0, gaze=(0.0, 0.25)),
    "SMUG":    dict(lid=0.62, lid_low=0.35, brow_l=-0.003, brow_r=-0.001, ang_l=-10, ang_r=8, mouth="GRIN",
                    gaze=(0.0, 0.05)),
    "SIDEEYE": dict(lid=0.5, lid_low=0.25, brow_l=0.0, brow_r=0.002, ang_l=-3, ang_r=-2, mouth="SMIRK", gaze=(0.55, 0.0)),
    # hers
    "CALM":    dict(lid=0.9, lid_low=0.25, mouth="SMIRK"),
    "STARTLED": dict(lid=1.4, lid_low=0.0, brow_l=0.009, brow_r=0.009, ang_l=10, ang_r=-10, mouth="O", pupil=0.75),
    "AMUSED":  dict(lid=0.8, lid_low=0.35, brow_l=0.007, brow_r=0.0, ang_l=-6, ang_r=0, mouth="SMIRK", blush=0.6,
                    gaze=(-0.3, 0.0)),
}
NEUTRAL = dict(lid=1.0, lid_low=0.0, brow_l=0.0, brow_r=0.0, ang_l=0, ang_r=0, mouth="SMIRK", pupil=1.0, gaze=(0.0, 0.0),
               sparkle=0.0, blush=0.0, sweat=0.0)


class FaceRig:
    """Controls for one face (by part-name prefix). Every control moves
    geometry relative to its rest placement:
      lid (1 = rest, 0 = shut, 1.5 = wide), lid_low (0..1 cheek squint),
      brow_l / brow_r (lift, metres), ang_l / ang_r (tilt in the face plane,
      degrees), gaze (x, z in eye radii), pupil (iris/pupil scale), mouth
      (SMIRK, GRIN, O, GASP, FLAT), sparkle / blush / sweat (0..1).
    Character 'left' (_l, sx=+1) is +X."""

    def __init__(self, rig, prefix=""):
        self.rig, self.p = rig, prefix
        self.R = rig.matrix_world.to_3x3().normalized()   # face space -> world (works when the rig is turned)
        info = FACE_INFO[prefix]
        self.eye_r = info["eye_r"]
        bpy.context.view_layer.update()
        self.obs = {}
        for o in bpy.data.objects:
            if o.parent == rig and o.parent_bone == "Head" and o.name.startswith(prefix):
                key = o.name[len(prefix):]
                if prefix == "" and key.startswith("G_"):
                    continue
                self.obs[key] = (o, o.matrix_basis.copy(), (o.matrix_world @ o.matrix_basis.inverted()).to_3x3())
        # Sparkles ride on the irises.
        spark = mat("sparkle_fx", 0.05)
        for sx in (1, -1):
            iris = self.obs[f"Iris{sx}"][0]
            for k, (a, b) in enumerate(((0.5, 0.1), (0.1, 0.5))):
                ob = blob(f"{prefix}Sparkle{sx}{k}", iris.matrix_world.translation + Vector((-sx * 0.003, -0.006, 0.003)),
                          (self.eye_r * a, 0.001, self.eye_r * b), spark, subdiv=1)
                bind(ob, rig, "Head")
                bpy.context.view_layer.update()
                ob.scale = ob.scale * 0.001
                bpy.context.view_layer.update()
                self.obs[ob.name[len(prefix):]] = (ob, ob.matrix_basis.copy(), (ob.matrix_world @ ob.matrix_basis.inverted()).to_3x3())
        self.base_scale = {k: v[0].scale.copy() for k, v in self.obs.items()}
        for k, (o, mb, pr) in self.obs.items():   # hidden parts: remember their full size
            if k.startswith(("Mouth", "Blush", "Sweat", "Sparkle")):
                self.base_scale[k] = self.base_scale[k] * 1000

    def _set(self, key, move=Vector(), axis=None, angle=0.0, scale=None):
        if key not in self.obs:
            return
        o, mb, parent_rot = self.obs[key]
        M = mb.copy()
        if axis is not None and angle:
            local_axis = (parent_rot @ mb.to_3x3()).inverted() @ (self.R @ Vector(axis))
            M = M @ Matrix.Rotation(angle, 4, local_axis.normalized())
        M.translation = M.translation + parent_rot.inverted() @ (self.R @ Vector(move))
        o.matrix_basis = M
        if scale is not None:
            o.scale = scale

    def pose(self, expr="COOL", **over):
        c = dict(NEUTRAL)
        c.update(EXPRESSIONS.get(expr, {}) if isinstance(expr, str) else expr)
        c.update(over)
        r = self.eye_r
        gx, gz = c["gaze"]
        almond = FACE_INFO[self.p].get("almond")
        for sx in (1, -1):
            side = "l" if sx > 0 else "r"
            if almond:
                lid = max(0.12, c["lid"])
                be = self.base_scale[f"Eye{sx}"]
                self._set(f"Eye{sx}", scale=(be.x, be.y, be.z * lid))
                AH = FACE_INFO[self.p].get("ah", ALMOND_H)
                drop = AH * r * 0.93 * (lid - 1)                 # the top line follows the eye's top edge
                self._set(f"LidLiner{sx}", move=(0, 0, drop))
                self._set(f"LowLiner{sx}", move=(0, 0, -AH * r * 0.7 * (lid - 1) * 0.4 + r * 0.25 * c["lid_low"]))
            else:
                self._set(f"Lid{sx}", axis=(1, 0, 0), angle=math.radians(60) * (1 - c["lid"]))
            self._set(f"LidLow{sx}", move=(0, 0, r * 0.55 * c["lid_low"]))
            self._set(f"Brow{sx}", move=(0, 0, c[f"brow_{side}"]), axis=(0, -1, 0), angle=math.radians(sx * c[f"ang_{side}"]))
            for part in ("Iris", "Pupil", "Glint", "Glint2"):
                k = f"{part}{sx}"
                if k in self.obs:
                    bs = self.base_scale[k]
                    sc = (bs.x * c["pupil"], bs.y, bs.z * c["pupil"]) if not part.startswith("Glint") else bs
                    if almond and part in ("Iris", "Pupil"):          # irises are cut by the narrowed opening
                        sc = (sc[0], sc[1], sc[2] * min(1.0, max(0.12, c["lid"])))
                    self._set(k, move=(gx * r * 0.35, 0, gz * r * 0.35), scale=sc)
            for k in (f"Sparkle{sx}0", f"Sparkle{sx}1"):
                self._set(k, move=(gx * r * 0.35, 0, gz * r * 0.35), scale=self.base_scale[k] * max(1e-3, c["sparkle"]))
            self._set(f"Blush{sx}", scale=self.base_scale[f"Blush{sx}"] * max(1e-3, c["blush"]))
        self._set("Sweat", scale=self.base_scale["Sweat"] * max(1e-3, c["sweat"]))
        shown = set(MOUTHS.get(c["mouth"], ()))          # a part may belong to several mouths
        for part in {q for parts in MOUTHS.values() for q in parts}:
            if part in self.obs:
                self._set(part, scale=self.base_scale[part] * (1.0 if part in shown else 1e-3))

    def key(self, frame, expr="COOL", **over):
        self.pose(expr, **over)
        for o, _, _ in self.obs.values():
            o.keyframe_insert("location", frame=frame)
            o.keyframe_insert("rotation_euler", frame=frame)
            o.keyframe_insert("scale", frame=frame)
            ad = o.animation_data
            if ad and ad.action:
                for fc in _fcurves_of(o):
                    for kp in fc.keyframe_points:
                        if kp.co.x == frame and fc.data_path == "scale":
                            kp.interpolation = "CONSTANT"   # mouths/accents swap, they don't morph


def _fcurves_of(id_data):
    ad = id_data.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "layers") and getattr(ad, "action_slot", None) is not None:
        from bpy_extras.anim_utils import action_get_channelbag_for_slot
        bag = action_get_channelbag_for_slot(act, ad.action_slot)
        return list(bag.fcurves) if bag else []
    return list(act.fcurves)


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
        # Hard key (a tiny source = crisp shadows under chin, sleeves, boots),
        # a soft dim fill, a small rim, and a separate soft light on the
        # backdrop only, for a controlled gradient behind the character.
        ("Key", "AREA", (-2.2, -2.4, 3.2), (55, 0, -40), 520, 0.1),
        ("Fill", "AREA", (2.8, -2.0, 1.8), (70, 0, 50), 90, 3.0),
        ("Rim", "AREA", (1.0, 2.5, 2.8), (-50, 0, 160), 300, 0.15),
        ("Backdrop", "AREA", (0.0, 1.2, 0.4), (-75, 0, 0), 120, 2.5),
    ):
        d = bpy.data.lights.new(name, kind)
        d.energy, d.size = energy, size
        o = _link(bpy.data.objects.new(name, d))
        o.location, o.rotation_euler = loc, [math.radians(a) for a in rot]
    r = scene.render
    engines = [e.identifier for e in r.bl_rna.properties["engine"].enum_items]
    r.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    r.resolution_percentage = pct
    grade(scene)
    if hasattr(scene, "eevee"):
        ev = scene.eevee
        for attr, val in (("use_shadows", True), ("taa_render_samples", 32), ("use_raytracing", False)):
            if hasattr(ev, attr):
                setattr(ev, attr, val)


FACE_FEATURE_PARTS = ("Eye", "Iris", "Pupil", "Glint", "LidLiner", "LowLiner", "LashSweep", "Lash", "Lid", "Brow",
                      "Pout", "Smile", "Dimple", "Blush", "Mouth", "Sparkle", "Sweat")


def project_face_image(rig, prefix, image_path, img_pts, ellipse, skin_rgb=None, hide_features=True):
    """Paint a reference face onto the sculpted head: front-project the image
    onto the head mesh, aligned by matching landmarks, blend the face oval into
    the skin and hide the 3D facial features it replaces.

    img_pts: {"eye_l": (px, py), "eye_r": .., "nose": .., "mouth": ..} in image
    pixels (eye_l = the character's left eye = image right). ellipse: (cx, cy,
    rx, ry) in pixels - the face area kept from the image; it feathers to the
    skin colour outside. skin_rgb: fill colour (0-255) sampled from the image."""
    import numpy as np
    head = bpy.data.objects[f"{prefix}Head"]
    img = bpy.data.images.load(image_path, check_existing=True)
    w, h = img.size
    bpy.context.view_layer.update()

    def wpos(name):
        return bpy.data.objects[f"{prefix}{name}"].matrix_world.translation

    def centre(name):
        ob = bpy.data.objects[f"{prefix}{name}"]
        return sum((ob.matrix_world @ v.co for v in ob.data.vertices), Vector()) / len(ob.data.vertices)
    world = {"eye_l": wpos("Eye1"), "eye_r": wpos("Eye-1"), "mouth": centre("Smile")}
    world["nose"] = (world["eye_l"] + world["eye_r"]) / 2 * 0.5 + world["mouth"] * 0.5
    # Outline landmarks: the head's cheek edges at eye level, chin, hairline.
    vs = [head.matrix_world @ v.co for v in head.data.vertices]
    ez = (world["eye_l"].z + world["eye_r"].z) / 2
    band = [v for v in vs if abs(v.z - ez) < 0.006 and v.y < head.matrix_world.translation.y]
    xc = (world["eye_l"].x + world["eye_r"].x) / 2
    world["cheek_l"] = Vector((max(v.x for v in band), 0, ez))
    world["cheek_r"] = Vector((min(v.x for v in band), 0, ez))
    world["chin"] = Vector((xc, 0, min(v.z for v in vs if abs(v.x - xc) < 0.01 and v.y < head.matrix_world.translation.y)))
    hl = bpy.data.objects.get(f"{prefix}Hair_Helmet")
    if hl:
        hv = [hl.matrix_world @ v.co for v in hl.data.vertices if abs((hl.matrix_world @ v.co).x - xc) < 0.01]
        world["hairline"] = Vector((xc, 0, min(v.z for v in hv if v.y < head.matrix_world.translation.y - 0.03)))
    keys = [k for k in ("eye_l", "eye_r", "nose", "mouth", "cheek_l", "cheek_r", "chin", "hairline") if k in img_pts and k in world]
    A = np.array([[world[k].x, world[k].z, 1.0] for k in keys])
    B = np.array([img_pts[k] for k in keys], dtype=float)
    M, *_ = np.linalg.lstsq(A, B, rcond=None)                     # world (x, z) -> image pixels (affine)
    me = head.data
    uv = me.uv_layers.new(name="RefUV") if "RefUV" not in me.uv_layers else me.uv_layers["RefUV"]
    mw = head.matrix_world
    nm = mw.to_3x3().inverted().transposed()
    cx, cy, rx, ry = ellipse
    wts = []
    for v in me.vertices:
        p = mw @ v.co
        px, py = np.array([p.x, p.z, 1.0]) @ M
        d = math.hypot((px - cx) / rx, (py - cy) / ry)
        n = (nm @ v.normal).normalized()
        front = max(0.0, min(1.0, (-n.y - 0.15) / 0.35))            # only surfaces facing the camera take the paint
        wts.append(max(0.0, min(1.0, (1.0 - d) / 0.18)) * front)
    for loop in me.loops:
        p = mw @ me.vertices[loop.vertex_index].co
        px, py = np.array([p.x, p.z, 1.0]) @ M
        uv.data[loop.index].uv = (px / w, 1.0 - py / h)
    if "FaceMask" not in me.attributes:
        me.attributes.new("FaceMask", "FLOAT", "POINT")
    fm = me.attributes["FaceMask"]
    for i, wt in enumerate(wts):
        fm.data[i].value = wt
    # Material: image inside the oval, the sampled skin outside, matte.
    m = bpy.data.materials.new(f"{prefix}FaceProjected")
    if getattr(m, "node_tree", None) is None and hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "EXTEND"
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "RefUV"
    mask = nt.nodes.new("ShaderNodeAttribute")
    mask.attribute_name = "FaceMask"
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    col = hx("#%02x%02x%02x" % tuple(skin_rgb)) if skin_rgb else COL["skin"]
    mix.inputs[6].default_value = col
    nt.links.new(uvn.outputs["UV"], tex.inputs["Vector"])
    nt.links.new(mask.outputs["Fac"], mix.inputs[0])
    nt.links.new(tex.outputs["Color"], mix.inputs[7])
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    # The painting already carries its own light and shade: let part of it glow
    # through as-is (inside the oval) so the 3D lighting doesn't wash it out.
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    blend = nt.nodes.new("ShaderNodeMath")              # mostly the painting's own shading, a little 3D light on top
    blend.operation = "MULTIPLY"
    blend.inputs[1].default_value = 0.8
    nt.links.new(mask.outputs["Fac"], blend.inputs[0])
    mixsh = nt.nodes.new("ShaderNodeMixShader")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    nt.links.new(blend.outputs[0], mixsh.inputs[0])
    nt.links.new(b.outputs[0], mixsh.inputs[1])
    nt.links.new(em.outputs[0], mixsh.inputs[2])
    nt.links.new(mixsh.outputs[0], out.inputs["Surface"])
    b.inputs["Roughness"].default_value = 0.8
    if "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = 0.1
    me.materials.clear()
    me.materials.append(m)
    if skin_rgb:                                    # ears, neck, hands take the same fill colour
        for mname in ("FR_g_skin", "g_skin"):
            mm = bpy.data.materials.get(mname)
            if mm and mm.node_tree:
                bb = next((n for n in mm.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                if bb:
                    bb.inputs["Base Color"].default_value = col
    if hide_features:
        for o in bpy.data.objects:
            if o.name.startswith(prefix) and o.name[len(prefix):].startswith(FACE_FEATURE_PARTS) and o.parent == rig:
                o.hide_render = True
    return M


def golden_hour(scene, cam, subject, focus=None, fstop=1.8, set_dressing=True):
    """Low-sun 'golden hour' look (replaces the studio set):
      - warm key: a big golden-peach area light off frame left;
      - blinding rim: a hot cream sun behind his right shoulder, pointing
        back at the lens, for the glowing halo on neck, jaw and hair;
      - contrast fill: a dim, cool lavender light on the shadow side;
      - a warm sky, a sun glow and (optionally) a fence grid and foliage
        behind, melted by a shallow depth of field focused on `focus`."""
    subject = Vector(subject)
    for o in list(bpy.data.objects):
        if o.name in ("Key", "Fill", "Rim", "Backdrop", "Cyc"):
            o.hide_render = True
    bg = next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND")
    # The camera sees a bright warm sky; the scene is lit only by a dim cool ambient (deep shadows, no grey wash).
    nt = scene.world.node_tree
    bg.inputs["Color"].default_value = (0.62, 0.6, 0.78, 1)
    bg.inputs["Strength"].default_value = 0.18
    sky = nt.nodes.new("ShaderNodeBackground")
    sky.inputs["Color"].default_value = (1.0, 0.74, 0.5, 1)
    sky.inputs["Strength"].default_value = 1.4
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_WORLD")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(sky.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    to_cam = (cam.location - subject).normalized()
    side = to_cam.cross(Vector((0, 0, 1))).normalized()          # screen-right direction seen from the subject
    def light(name, kind, loc, energy, col, size=1.0, angle=None):
        d = bpy.data.lights.new(name, kind)
        d.energy, d.color = energy, col
        if kind == "AREA":
            d.size = size
        if angle is not None:
            d.angle = math.radians(angle)
        o = _link(bpy.data.objects.new(name, d))
        o.location = loc
        o.rotation_euler = (subject - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return o
    light("GH_Key", "AREA", subject + side * 2.2 + to_cam * 1.0 + Vector((0, 0, 0.5)), 520, (1.0, 0.52, 0.26), size=0.6)
    light("GH_Rim", "AREA", subject + side * 0.4 - to_cam * 0.8 + Vector((0, 0, 0.1)), 2600, (1.0, 0.95, 0.85), size=0.5)
    light("GH_RimHair", "AREA", subject - side * 0.4 - to_cam * 0.8 + Vector((0, 0, 0.55)), 900, (1.0, 0.9, 0.75), size=0.4)
    light("GH_Fill", "AREA", subject - side * 2.0 + to_cam * 1.2, 70, (0.7, 0.68, 0.92), size=3.0)
    if set_dressing:
        back = subject - to_cam * 2.2
        sun = blob("GH_SunGlow", subject - to_cam * 6 + side * 2.2 + Vector((0, 0, 0.9)), (0.9, 0.9, 0.9), emit_mat("sun_glow", (1.0, 0.9, 0.7), 20.0), subdiv=1)
        sun.visible_shadow = False
        # A chain-link fence: a lattice of thin bars on a plane facing the camera.
        right = side
        fence = []
        for i in range(-14, 15):
            for sgn in (1, -1):
                p0 = back + right * (i * 0.22) + Vector((0, 0, -1.6))
                p1 = p0 + right * sgn * 1.6 + Vector((0, 0, 3.2))
                fence.append(tube(f"GH_Fence{i}_{sgn}", [p0, p1], [0.009, 0.009], mat("fence", 0.6), subdiv=0, ring=4, caps=False))
        for o in fence:
            o.visible_shadow = False
        for k in range(22):                       # a hedge line low behind the fence
            p = back - to_cam * 1.5 + right * (-4.0 + k * 0.38) + Vector((0, 0, -0.75 + 0.15 * math.sin(k * 1.7)))
            blob(f"GH_Bush{k}", p, (0.4, 0.3, 0.32), mat("foliage", 0.9), subdiv=1).visible_shadow = False
    d = cam.data
    d.dof.use_dof = True
    d.dof.aperture_fstop = fstop
    if focus is not None:
        d.dof.focus_object = focus
    else:
        d.dof.focus_distance = (cam.location - subject).length


def emit_mat(name, col, strength):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    if getattr(m, "node_tree", None) is None and hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(n)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*col, 1)
    e.inputs["Strength"].default_value = strength
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    nt.links.new(e.outputs["Emission"], out.inputs["Surface"])
    return m


def grade(scene):
    """AgX with a medium-high contrast look: rich colours, rims that roll
    off instead of clipping to white."""
    vs = scene.view_settings
    vs.view_transform = "AgX"
    looks = [i.identifier for i in vs.bl_rna.properties["look"].enum_items]
    for want in ("AgX - Medium High Contrast", "Medium High Contrast"):
        if want in looks:
            vs.look = want
            break


def film_grain(path, amount=0.025, seed=0):
    """Bind the render together with a whisper of colour grain (post)."""
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32) / 255
    rng = np.random.default_rng(seed)
    g = rng.normal(0, amount, im.shape[:2])[..., None] + rng.normal(0, amount * 0.35, im.shape)
    Image.fromarray((np.clip(im + g, 0, 1) * 255).astype(np.uint8)).save(path)


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
