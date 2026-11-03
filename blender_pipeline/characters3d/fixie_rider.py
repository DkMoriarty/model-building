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
    "skin": hx("#a96a47"), "skin_dark": hx("#7d4a30"), "lip": hx("#5a2a22"),
    "hair": hx("#1f1613"), "eye_white": hx("#f3efe9"), "iris": hx("#120c0a"),
    "shirt": hx("#8ea383"), "shirt_seam": hx("#6f8566"),
    "shorts": hx("#2c2c31"), "sock": hx("#f1efea"), "shoe": hx("#e7e1d3"), "sole": hx("#b88654"),
    "lace": hx("#f7f5f0"), "cap": hx("#c0582b"), "cap_seam": hx("#9a4220"),
    "mouth_dark": hx("#3b1a17"), "liner": hx("#0e0a0a"), "blush_toon": hx("#e46a5c"), "lip_toon": hx("#d0675d"),
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


def smirk_line(x, smirk=1.0):
    """Height of the mouth crease across the face (rises into the right cheek)."""
    return -0.54 + smirk * 0.075 * max(0.0, x - 0.1) + 0.02 * x * x


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
    d += 0.045 * nose * _g(x, 0, 0.05) * max(0.0, min(1.0, (0.2 - z) / 0.15)) * _g(z, -0.05, 0.22)   # bridge
    d += 0.15 * nose * _g(x, 0, 0.075) * _g(z, -0.235, 0.065)                                      # button tip
    for sx in (1, -1):
        d += 0.04 * nose * _g(x, sx * 0.1, 0.045) * _g(z, -0.27, 0.04)                            # nostril wings
        d += 0.05 * _g(x, sx * 0.5, 0.17) * _g(z, -0.08, 0.14)                                     # high cheeks
    d -= 0.02 * _g(x, 0, 0.05) * _g(z, -0.36, 0.03)                                                # under-nose dip
    zl = smirk_line(x, smirk * 0.5)
    top = zl + 0.065 * lips - 0.02 * _g(x, 0, 0.03) + 0.008 * (_g(x, 0.06, 0.035) + _g(x, -0.06, 0.035))   # cupid's bow
    up = _plateau(z - (zl + top) / 2, (top - zl) / 2, 0.014) * _g(x, 0, 0.2 * lips ** 0.5) ** 0.6
    low = _plateau(z - (zl - 0.045 * lips), 0.04 * lips, 0.016) * _g(x, 0, 0.16 * lips ** 0.5) ** 0.6
    d += 0.045 * lips * up + 0.065 * lips * low
    d -= 0.024 * _plateau(x, 0.28 * lips ** 0.5, 0.05) * _tent(z - zl, 0.016)                     # parting line
    d += 0.07 * chin * _g(x, 0, 0.13) * _g(z, -0.84, 0.1)                                          # soft chin
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
    rough.inputs["To Min"].default_value = 0.55
    rough.inputs["To Max"].default_value = 0.22
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(lipa.outputs["Fac"], rough.inputs["Value"])
    nt.links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    if "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = 0.35
        bsdf.inputs["Subsurface Radius"].default_value = (0.9, 0.35, 0.2)
        if "Subsurface Scale" in bsdf.inputs:
            bsdf.inputs["Subsurface Scale"].default_value = 0.012
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.35
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
        if z < 0:                                   # a hard V jaw tapering to a triangular chin
            k = 1 - 0.4 * jaw * (-z) ** 1.2
            x *= max(0.12, k)
            y = y * (1 - 0.1 * (-z)) if y > 0 else y
        d = 0.0                                     # forward displacement (toward -Y)
        for ex in (0.37, -0.37):
            d -= 0.16 * _g(x, ex, 0.15) * _g(z, 0.1, 0.12) * f                    # deep eye sockets
            d += 0.06 * cheek * _g(x, ex * 1.45, 0.14) * _g(z, -0.14, 0.14) * f    # cheekbones
        d += 0.07 * _g(z, 0.31, 0.07) * (_g(x, 0.34, 0.22) + _g(x, -0.34, 0.22)) * f  # brow ridge
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
            bw = (sum(_g(x, e, 0.17) for e in (0.48, -0.48)) * _g(z, -0.17, 0.15) * 0.85
                  + 0.7 * _g(x, 0, 0.09) * _g(z, -0.22, 0.08)) * fr_
            c = skin_c.lerp(Vector(blush_c), min(0.85, bw * 1.1))
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


def head_surface(hc, size, ux, uz, **kw):
    """World point on the sculpted head's front at unit coords (ux, uz)."""
    sx, sy, sz = size
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
    "SMIRK": ("Smile", "Dimple"),
    "GRIN": ("MouthGrinDark", "MouthGrinTeeth", "MouthGrinLine"),
    "O": ("MouthORim", "MouthO"),
    "GASP": ("MouthGasp", "MouthGaspTeeth"),
    "FLAT": ("MouthFlat",),
}


def build_mouths(add, hc, size, lip_col, prefix):
    """The alternative mouths, sculpted in place on the face and hidden
    (scale ~0) until an expression swaps them in."""
    dark = mat("mouth_dark", 0.6)
    teeth = mat("teeth", 0.35)
    lip = mat(lip_col, 0.5)

    def at(ux, uz, fwd=0.0):
        return head_surface(hc, size, ux, uz) + Vector((0, -0.002 - fwd, 0))
    grin = [at(ux, -0.53 + 0.16 * ux * ux) for ux in (-0.34, -0.17, 0.0, 0.17, 0.34)]
    made = []
    made.append(tube(f"{prefix}MouthGrinDark", [p + Vector((0, 0.001, -0.007)) for p in grin], [0.003, 0.009, 0.011, 0.009, 0.003],
                     dark, side=Vector((0, 1, 0)), subdiv=1))
    made.append(tube(f"{prefix}MouthGrinTeeth", [p + Vector((0, -0.001, -0.0035)) for p in grin[1:-1]], [0.005, 0.0058, 0.005],
                     teeth, side=Vector((0, 1, 0)), subdiv=1))
    made.append(tube(f"{prefix}MouthGrinLine", grin, [0.002, 0.0035, 0.004, 0.0035, 0.002], lip, side=Vector((0, 1, 0)), subdiv=1))
    c = at(0.02, -0.53, 0.001)
    made.append(blob(f"{prefix}MouthORim", c + Vector((0, 0.002, 0)), (0.0165, 0.006, 0.021), lip, subdiv=1))
    made.append(blob(f"{prefix}MouthO", c, (0.012, 0.006, 0.016), dark, subdiv=1))
    made.append(blob(f"{prefix}MouthGasp", c + Vector((0, 0, -0.004)), (0.017, 0.007, 0.026), dark, subdiv=1))
    made.append(blob(f"{prefix}MouthGaspTeeth", c + Vector((0, -0.003, 0.016)), (0.011, 0.004, 0.0045), teeth, subdiv=1))
    made.append(tube(f"{prefix}MouthFlat", [at(-0.18, -0.52), at(0.0, -0.53), at(0.2, -0.515)], [0.0025, 0.0035, 0.0025], lip,
                     side=Vector((0, 1, 0)), subdiv=1))
    for ob in made:
        recenter(ob)
        add(ob, "Head")
        ob.scale = ob.scale * 0.001
        ob["hidden_mouth"] = True


def build_toon_face(add, hc, size, skin, iris_col, brow_col, lip_col, prefix, nose, chin, jaw, eye_r, lashes, smirk, lips,
                    paint, brows):
    """The feature-film face: soft forms, painted blush and lips, big
    almond eyes with winged liner, sharply arched brows."""
    skin_m = skin_paint_material(f"{prefix}SkinPaint", *paint) if paint else skin
    cols = (COL[paint[0]], COL[paint[1]], COL[paint[2]], COL[paint[3]] if paint[3] else None) if paint else None
    add(sculpt_head(f"{prefix}Head", hc, size, skin_m, nose=nose, chin=chin, jaw=jaw, smirk=smirk, style="toon", lips=lips,
                    paint=cols), "Head")
    liner = mat("liner", 0.4)
    skin_flat = skin
    for sx in (1, -1):
        surf = head_surface(hc, size, sx * 0.34, 0.05)
        eye = surf + Vector((0, eye_r * 0.4, 0))
        toon_eye(add, prefix, sx, eye, eye_r, skin_flat, iris_col, liner, lashes)
        # Brows: thick tapered swoosh. 'arch' peaks two-thirds out; 'angry' dives to the nose.
        if brows == "angry":
            spec = ((0.12, 0.17), (0.28, 0.25), (0.44, 0.31), (0.6, 0.27))
            radii = [0.009, 0.01, 0.008, 0.003]
        else:
            spec = ((0.13, 0.27), (0.29, 0.33), (0.45, 0.36), (0.62, 0.29))
            radii = [0.0045, 0.006, 0.0052, 0.0016]
        pts = [head_surface(hc, size, sx * ux, uz) + Vector((0, -0.006, 0)) for ux, uz in spec]
        add(recenter(tube(f"{prefix}Brow{sx}", pts, radii, mat(brow_col, 0.6), subdiv=1)), "Head")
        for part in ear_shell(f"{prefix}Ear{sx}", hc + Vector((sx * size[0] * 0.85, 0.015, -size[2] * 0.06)), size[2] * 0.62, sx,
                              skin_flat):
            add(part, "Head")
    pts = [head_surface(hc, size, ux, smirk_line(ux, smirk * 0.5)) + Vector((0, -0.003, 0))
           for ux in (-0.27, -0.13, 0.0, 0.14, 0.28)]
    add(tube(f"{prefix}Smile", pts, [0.001, 0.002, 0.0022, 0.002, 0.001], mat("mouth_dark", 0.5), side=Vector((0, 1, 0)),
             subdiv=1), "Head")
    add(tube(f"{prefix}Dimple", [pts[-1], pts[-1] + Vector((0.003, 0.0, 0.003))], [0.001, 0.0006], mat("mouth_dark", 0.5),
             subdiv=0, ring=6), "Head")
    build_mouths(add, hc, size, lip_col, prefix)
    build_face_extras(add, hc, size, prefix)
    FACE_INFO[prefix] = dict(hc=hc.copy(), size=size, eye_r=eye_r)


def build_face_extras(add, hc, size, prefix):
    """Cartoon accents an expression can dial in: blush, eye sparkles, a sweat drop."""
    blush = mat("blush_fx", 0.6)
    for sx in (1, -1):
        b = blob(f"{prefix}Blush{sx}", head_surface(hc, size, sx * 0.56, -0.2) + Vector((0, -0.004, 0)), (0.024, 0.004, 0.013),
                 blush, subdiv=1)
        add(b, "Head")
        b.scale = b.scale * 0.001
    sweat = blob(f"{prefix}Sweat", head_surface(hc, size, -0.7, 0.35) + Vector((-0.012, -0.01, 0)), (0.007, 0.005, 0.011),
                 mat("sweat", 0.15), subdiv=1)
    add(sweat, "Head")
    sweat.scale = sweat.scale * 0.001


def toon_eye(add, prefix, sx, eye, r, skin, iris_col, liner, lashes):
    """Feature-film eye: a white eyeball, a big dark iris with a large pupil
    and two highlights, a lid that wraps it, a thick black liner along the
    upper lid that sweeps into a wing (it rides the lid), a fine lower line."""
    add(blob(f"{prefix}Eye{sx}", eye, (r * 1.35, r, r * 0.95), mat("eye_white", 0.15), subdiv=1, segments=32), "Head")
    front = eye + Vector((0, -r * 0.94, 0))
    add(blob(f"{prefix}Iris{sx}", front + Vector((-sx * r * 0.05, 0, -r * 0.08)), (r * 0.6, r * 0.1, r * 0.64), mat(iris_col, 0.15),
             subdiv=1, segments=24), "Head")
    add(blob(f"{prefix}Pupil{sx}", front + Vector((-sx * r * 0.05, -r * 0.05, -r * 0.08)), (r * 0.36, r * 0.06, r * 0.38),
             mat("iris", 0.1), subdiv=1), "Head")
    add(blob(f"{prefix}Glint{sx}", front + Vector((-sx * r * 0.3, -r * 0.12, r * 0.28)), (r * 0.17, r * 0.05, r * 0.17),
             mat("eye_white", 0.02), subdiv=1, segments=12), "Head")
    add(blob(f"{prefix}Glint2{sx}", front + Vector((sx * r * 0.22, -r * 0.11, -r * 0.3)), (r * 0.07, r * 0.03, r * 0.07),
             mat("eye_white", 0.02), subdiv=0, segments=8), "Head")
    lid = lid_shell(f"{prefix}Lid{sx}", eye, r * 1.04, 22, True, skin, liner)   # covers the top of the iris
    lid.modifiers["Thick"].thickness = r * 0.08          # thin: the liner, not the lid, carries the line
    lid.scale = (1.3, 1.0, 1.0)                          # as wide as the almond eyeball
    add(lid, "Head")
    low = lid_shell(f"{prefix}LidLow{sx}", eye, r * 1.03, 12, False, skin, skin)
    low.scale = (1.3, 1.0, 1.0)
    low.modifiers["Thick"].thickness = r * 0.05
    add(low, "Head")
    # Liner: from the inner corner over the top of the eye to a wing past the outer corner.
    def on_eye(ax, az, out=1.12):
        return eye + Vector((sx * ax * r * out * 1.33, -math.sqrt(max(0.0, 1 - ax * ax - az * az)) * r * out, az * r * out))
    # Along the upper lid's edge: low at the inner corner, a flat-ish top over the iris, out into the wing.
    pts = [on_eye(-0.95, -0.12), on_eye(-0.6, 0.35), on_eye(-0.05, 0.5), on_eye(0.5, 0.46), on_eye(0.9, 0.18),
           eye + Vector((sx * r * 1.75, -r * 0.45, r * 0.5))]
    lo = tube(f"{prefix}LidLiner{sx}", pts, [r * 0.06, r * 0.12, r * 0.16, r * 0.17, r * 0.13, r * 0.015], liner, subdiv=1,
              ring=10)
    lo.data.transform(Matrix.Translation(-eye))
    lo.location = eye                                     # pivot at the eye: it rotates with the lid
    add(lo, "Head")
    low = [on_eye(-0.85, -0.3, 1.05), on_eye(0.0, -0.6, 1.05), on_eye(0.85, -0.25, 1.05)]
    add(tube(f"{prefix}LowLiner{sx}", low, [r * 0.02, r * 0.045, r * 0.02], liner, subdiv=1, ring=8), "Head")
    if lashes:
        for k in range(4):
            a = 0.35 + 0.18 * k
            base = on_eye(a, 0.8 - 0.25 * k)
            add(tube(f"{prefix}Lash{sx}{k}", [base, base + Vector((sx * r * 0.35, -r * 0.18, r * 0.32 - 0.06 * k * r))],
                     [r * 0.06, r * 0.01], liner, subdiv=0, ring=6), "Head")


def build_face(add, hc, size, skin, iris_col, brow_col, lip_col, prefix="", nose=1.0, chin=1.0, cheek=1.0,
               jaw=1.0, eye_r=0.022, lashes=False, smirk=1.0, style="planes", lips=1.0, paint=None, brows="cocky"):
    if style == "toon":
        return build_toon_face(add, hc, size, skin, iris_col, brow_col, lip_col, prefix, nose, chin, jaw, eye_r, lashes, smirk,
                               lips, paint, brows)
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
        add(blob(f"{prefix}Pupil{sx}", front + Vector((-sx * 0.002, -eye_r * 0.06, -0.001)), (eye_r * 0.3, eye_r * 0.08, eye_r * 0.32),
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

HEAD_Z = 1.67   # head centre (raised on a longer neck)


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
    add(tube("Neck", [(0, 0.01, 1.42), (0, 0.0, 1.565)], [0.043, 0.04], skin), "Neck")   # longer neck
    hc = Vector((0, -0.01, HEAD_Z))
    build_face(add, hc, (0.112, 0.124, 0.15), skin, "iris", "hair", "lip_toon", nose=1.05, chin=0.8, cheek=1.0, jaw=0.85,
               eye_r=0.031, smirk=1.0, style="toon", lips=0.85, paint=("skin", "blush_toon", "lip_toon", "stubble"),
               brows="angry")
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
    "COOL":    dict(lid=0.85, lid_low=0.15, brow_l=0.0, brow_r=0.004, ang_l=0, ang_r=-8, mouth="SMIRK"),
    "HAPPY":   dict(lid=1.0, lid_low=0.55, brow_l=0.003, brow_r=0.004, ang_l=-4, ang_r=4, mouth="GRIN"),
    "NOTICE":  dict(lid=1.15, lid_low=0.0, brow_l=0.002, brow_r=0.007, ang_l=0, ang_r=-6, mouth="FLAT", gaze=(0.35, 0.0)),
    "SHOCK":   dict(lid=1.5, lid_low=0.0, brow_l=0.011, brow_r=0.011, ang_l=12, ang_r=-12, mouth="GASP", pupil=0.55,
                    sweat=1.0),
    "STRUCK":  dict(lid=0.95, lid_low=0.3, brow_l=0.007, brow_r=0.007, ang_l=10, ang_r=-10, mouth="O", pupil=1.45,
                    sparkle=1.0, blush=1.0),
    "DAZED":   dict(lid=0.7, lid_low=0.4, brow_l=0.005, brow_r=0.005, ang_l=8, ang_r=-8, mouth="GRIN", pupil=1.3,
                    sparkle=0.7, blush=1.0, gaze=(0.0, 0.25)),
    "SMUG":    dict(lid=0.88, lid_low=0.3, brow_l=-0.002, brow_r=-0.002, ang_l=-10, ang_r=10, mouth="GRIN",
                    gaze=(0.0, 0.05)),
    # hers
    "CALM":    dict(lid=0.95, lid_low=0.1, mouth="SMIRK"),
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
        for sx in (1, -1):
            side = "l" if sx > 0 else "r"
            self._set(f"Lid{sx}", axis=(1, 0, 0), angle=math.radians(60) * (1 - c["lid"]))
            self._set(f"LidLow{sx}", move=(0, 0, r * 0.55 * c["lid_low"]))
            self._set(f"Brow{sx}", move=(0, 0, c[f"brow_{side}"]), axis=(0, -1, 0), angle=math.radians(sx * c[f"ang_{side}"]))
            for part in ("Iris", "Pupil", "Glint", "Glint2"):
                k = f"{part}{sx}"
                if k in self.obs:
                    bs = self.base_scale[k]
                    sc = (bs.x * c["pupil"], bs.y, bs.z * c["pupil"]) if not part.startswith("Glint") else bs
                    self._set(k, move=(gx * r * 0.35, 0, gz * r * 0.35), scale=sc)
            for k in (f"Sparkle{sx}0", f"Sparkle{sx}1"):
                self._set(k, move=(gx * r * 0.35, 0, gz * r * 0.35), scale=self.base_scale[k] * max(1e-3, c["sparkle"]))
            self._set(f"Blush{sx}", scale=self.base_scale[f"Blush{sx}"] * max(1e-3, c["blush"]))
        self._set("Sweat", scale=self.base_scale["Sweat"] * max(1e-3, c["sweat"]))
        for name, parts in MOUTHS.items():
            for part in parts:
                if part in self.obs:
                    self._set(part, scale=self.base_scale[part] * (1.0 if name == c["mouth"] else 1e-3))

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
