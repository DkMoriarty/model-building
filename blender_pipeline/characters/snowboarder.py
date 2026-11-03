"""CH_Snowboarder: the spunky snowboarder from the user's model sheet, as a
rigged Grease Pencil cut-out puppet (Blender 4.3+).

Every shape is traced in *sheet pixels* from the model sheet
(`blender_pipeline/characters/ref/snowboarder_sheet.jpg`, 1792 x 2400) and
converted to Blender units: X = (px - 590) / 1000, Z = (2250 - py) / 1000,
so the ground under her boots is Z = 0 and she stands about 2.1 units tall.
The rest pose has the arms hanging; `pose_sheet()` recreates the sheet's
hand-on-hip pose.

Style rules from the sheet:
- flat fills, no lighting; one soft lavender shade on white cloth, one darker
  tone on skin and hair
- dark brown-black ink (not black), with a brushy line that tapers and swells
- palette: the six swatches on the sheet, plus derived shades
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import toonkit as tk  # noqa: E402

S, CX, GROUND = 1000.0, 590.0, 2250.0


def hx(c):
    c = c.lstrip("#")
    srgb = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in srgb]
    return (*lin, 1.0)


def alpha(c, a):
    return (*c[:3], a)


# Swatches sampled from the sheet, plus shades derived from them.
COL = {
    "ink": hx("#2c1e1e"),
    "white": hx("#f5f8fd"),
    "cloth_shade": hx("#cdd3e6"),
    "hair": hx("#4a2a22"),
    "hair_dark": hx("#2f1b18"),
    "hair_light": hx("#7b4d36"),
    "skin": hx("#d9a27c"),
    "skin_shade": hx("#b8795a"),
    "blush": hx("#d98a72"),
    "shorts": hx("#2a2328"),
    "shorts_light": hx("#4d454d"),
    "slate": hx("#43424c"),
    "cuff": hx("#e4ca8d"),
    "cuff_shade": hx("#c99a70"),
    "lens": hx("#9b8a80"),
    "lens_light": hx("#c6c0bc"),
    "eye_white_tint": hx("#d8cdc4"),
    "iris_tint": hx("#3a2620"),
    "brow_tint": hx("#2f1e1a"),
    "nose_tip": hx("#e59a86"),
    # Cel-shadow colours, laid on Multiply layers (dark, desaturated).
    "shd_cloth": hx("#5d6596"),
    "shd_skin": hx("#7a3f30"),
    "shd_hair": hx("#2a1410"),
    "shd_boot": hx("#6e6656"),
    "lens_glint": alpha(hx("#ffffff"), 0.35),
    "eye_white": hx("#f4efe8"),
    "iris": hx("#5a3a2a"),
    "pupil": hx("#1e1414"),
    "mouth": hx("#5a1f22"),
    "tongue": hx("#c75a5a"),
    "board_white": hx("#e7e3ea"),
    "board_dark": hx("#2f2b33"),
    "board_stripe": hx("#bdbcc6"),
}


# Looks: the same character in each model sheet's costume. Only colours and a
# few costume shapes differ; the rig, layers and animation are shared.
BASE_COL = dict(COL)
LOOKS = {
    "sheet1": {},  # white puffer, white boots with yellow cuffs (first sheet)
    "sheet2": {    # blue-grey puffer with metal tube cuffs, cream/tan boots (second sheet)
        "ink": hx("#261a1b"),
        "white": hx("#d9dee4"),
        "cloth_shade": hx("#9ea7bb"),
        "sheen": hx("#f3f5f2"),
        "metal": hx("#c9ced3"),
        "metal_dark": hx("#2b2b30"),
        "shorts": hx("#2d2f3a"),
        "shorts_light": hx("#4a4e60"),
        "boot": hx("#ebe3cf"),
        "boot_shade": hx("#c9bfa8"),
        "boot_panel": hx("#c49a68"),
        "cuff": hx("#c49a68"),
        "cuff_shade": hx("#9a7350"),
        "skin": hx("#d39066"),
        "skin_shade": hx("#b0714f"),
        "paper": hx("#e1d7cb"),
    },
}
LOOK = "sheet1"


def use_look(name):
    """Switch the palette (and costume details) before drawing."""
    global LOOK
    if name not in LOOKS:
        raise ValueError(f"unknown look {name!r}; have {list(LOOKS)}")
    LOOK = name
    COL.clear()
    COL.update(BASE_COL)
    COL.setdefault("boot", BASE_COL["white"])
    COL.setdefault("boot_shade", BASE_COL["cloth_shade"])
    COL.setdefault("paper", hx("#f4efe6"))
    COL.update(LOOKS[name])
    _MATS.clear()


def P(px, py):
    """Sheet pixel -> picture-plane (x, z) in Blender units."""
    return ((px - CX) / S, (GROUND - py) / S)


# ---------------------------------------------------------------------------
# Line tools: smooth curves and a brushy, tapered ink line
# ---------------------------------------------------------------------------

def catmull(pts, closed=True, per_seg=8):
    """Smooth a control polygon (sheet px) with a Catmull-Rom spline."""
    n = len(pts)
    out = []
    segs = n if closed else n - 1
    for i in range(segs):
        p0 = pts[(i - 1) % n] if closed else pts[max(i - 1, 0)]
        p1, p2 = pts[i], pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if closed else pts[min(i + 2, n - 1)]
        for k in range(per_seg):
            t = k / per_seg
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    if not closed:
        out.append(pts[-1])
    return out


def _wobble(i, n, seed):
    """Low-frequency 'brush pressure' in 0..1, deterministic per stroke."""
    t = i / max(n - 1, 1)
    return 0.5 + 0.25 * math.sin(2 * math.pi * (1.3 * t + seed * 0.37)) + 0.25 * math.sin(2 * math.pi * (3.1 * t + seed * 1.7))


def stroke(ob, layer, pts, mat, width=7.0, closed=True, taper=False, smooth=True, per_seg=8, seed=0, frame=1):
    """Draw one stroke from sheet-px control points.

    width is the ink width in sheet px; closed shapes swell between 70% and
    130% of it, open lines also taper to a point at both ends (brush ink)."""
    curve = catmull(pts, closed, per_seg) if smooth and len(pts) > 2 else list(pts)
    xz = [P(*p) for p in curve]
    st = tk.draw_stroke(ob, layer, frame, xz, radius=width / S / 2, material=mat, cyclic=closed)
    for p, r in zip(st.points, line_profile(curve, closed, seed, taper)):
        p.radius = width / S / 2 * r
    return st


SHADOW_DIR = (0.6, 0.8)  # light from the top-left: lines and shadows fall down-right


def _smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def line_profile(curve, closed, seed=0, taper=False):
    """Thick-to-thin ink like the sheet's brush: lines pinch to a point at
    sharp corners (hair tips, collar points), run thin on the lit top-left of
    a shape and heavy on its shadow side, with a little pressure wobble;
    open lines also taper at both ends."""
    n = len(curve)
    if n < 3:
        return [1.0] * n
    area = sum(curve[i][0] * curve[(i + 1) % n][1] - curve[(i + 1) % n][0] * curve[i][1] for i in range(n))
    out = []
    for i in range(n):
        a = curve[(i - 2) % n] if closed else curve[max(i - 2, 0)]
        b = curve[(i + 2) % n] if closed else curve[min(i + 2, n - 1)]
        p = curve[i]
        v1, v2 = (p[0] - a[0], p[1] - a[1]), (b[0] - p[0], b[1] - p[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        turn = 0.0
        if l1 > 1e-6 and l2 > 1e-6:
            c = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)))
            turn = math.acos(c)
        r = 1.0 - 0.85 * _smooth(math.radians(55), math.radians(145), turn)  # pinch at tips
        if closed:
            tx, ty = b[0] - a[0], b[1] - a[1]
            tl = math.hypot(tx, ty) or 1.0
            nx, ny = (ty / tl, -tx / tl) if area > 0 else (-ty / tl, tx / tl)  # outward normal
            shade = nx * SHADOW_DIR[0] + ny * SHADOW_DIR[1]
            r *= 0.62 + 0.38 * (shade + 1)  # 0.62 on the lit side .. 1.38 in shadow
        r *= 0.88 + 0.24 * _wobble(i, n, seed)
        if taper:
            t = i / (n - 1)
            r *= min(1.0, 4 * t, 4 * (1 - t)) ** 0.8 + 0.05
        out.append(max(r, 0.06))
    return out


_MATS = {}


def mat(name, fill=None, line=True, line_color=None):
    """Materials are cached by name: 'Jacket' = white fill + ink line, etc."""
    if name not in _MATS:
        _MATS[name] = tk.gp_material(f"SB_{LOOK}_{name}", stroke=(line_color or COL["ink"]) if line else None, fill=fill)
    return _MATS[name]


def shape(ob, layer, pts, fill, name, width=7.0, seed=0, line=True, frame=1, smooth=True):
    return stroke(ob, layer, pts, mat(name, fill, line), width=width, closed=True, seed=seed, frame=frame,
                  smooth=smooth)


def shade(ob, layer, pts, tone="cloth", frame=1, smooth=True):
    """A crisp cel-shadow shape on the part's Multiply shadow layer."""
    return stroke(ob, f"{layer}_Shd", pts, mat(f"Shd_{tone}", COL[f"shd_{tone}"], False), closed=True,
                  frame=frame, smooth=smooth)


def lock(root_a, root_b, tip, bend=0.0, n=8):
    """One hair lock: two curved sides meeting at a sharp tip (not smoothed,
    so the line profile pinches it). bend pushes the lock sideways."""
    (ax, ay), (bx, by), (tx, ty) = root_a, root_b, tip
    mx, my = (ax + bx) / 2, (ay + by) / 2
    dx, dy = tx - mx, ty - my
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / L, dx / L
    ctrl = (mx + dx * 0.5 + nx * bend * L, my + dy * 0.5 + ny * bend * L)

    def q(p0, p1, p2, t):
        return ((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
    ca = (ctrl[0] + (ax - mx) * 0.5, ctrl[1] + (ay - my) * 0.5)
    cb = (ctrl[0] + (bx - mx) * 0.5, ctrl[1] + (by - my) * 0.5)
    side_a = [q(root_a, ca, tip, i / n) for i in range(n + 1)]
    side_b = [q(tip, cb, root_b, i / n) for i in range(1, n + 1)]
    return side_a + side_b


def x_span(poly, y):
    """Left and right x of a closed (smoothed) outline at height y."""
    c = catmull(poly, True)
    xs = []
    for i in range(len(c)):
        (x0, y0), (x1, y1) = c[i], c[(i + 1) % len(c)]
        if (y0 - y) * (y1 - y) <= 0 and y0 != y1:
            xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
    return (min(xs), max(xs)) if xs else (None, None)


def band_shadow(poly, y0, y1, inset=6, wave=6, n=10):
    """Shadow on the lower part of one quilted puffer band (y0..y1), clipped
    to the outline, with a soft wavy top edge."""
    l0, r0 = x_span(poly, y0)
    l1, r1 = x_span(poly, y1)
    if l0 is None or l1 is None:
        return None
    top = [(l0 + inset + (r0 - l0 - 2 * inset) * i / n, y0 + wave * math.sin(i * 1.7)) for i in range(n + 1)]
    bot = [(l1 + inset + (r1 - l1 - 2 * inset) * i / n, y1 - 2) for i in range(n, -1, -1)]
    return top + bot


def ink(ob, layer, pts, width=5.0, seed=0, color=None, name="Ink", frame=1):
    m = mat(name, None, True, color)
    return stroke(ob, layer, pts, m, width=width, closed=False, taper=True, seed=seed, frame=frame)


def crescent(outline, frac=(0.55, 0.95), inset=0.78, center=None, bias=(0, 0)):
    """A shade crescent inside a closed outline: the outline arc between
    `frac` (0..1 around the polygon), and the same arc pulled toward the
    centre by `inset`, shifted by `bias`. Stays inside convex-ish shapes."""
    curve = catmull(outline, True)
    n = len(curve)
    c = center or (sum(p[0] for p in curve) / n, sum(p[1] for p in curve) / n)
    a, b = int(frac[0] * n), int(frac[1] * n)
    arc = [curve[i % n] for i in range(a, b + 1)]
    inner = [(c[0] + (p[0] - c[0]) * inset + bias[0], c[1] + (p[1] - c[1]) * inset + bias[1]) for p in reversed(arc)]
    return arc[::2] + inner[::2]


def spikes(root, tips, valley=0.55, base=()):
    """A hair clump: spike tips fanned around a root; each valley sits
    between two tips, `valley` of the way out from the root, so the clump
    keeps its mass instead of reading as a star."""
    rx, ry = root
    pts = []
    for i, (tx, ty) in enumerate(tips):
        pts.append((tx, ty))
        if i + 1 < len(tips):
            mx, my = (tx + tips[i + 1][0]) / 2, (ty + tips[i + 1][1]) / 2
            pts.append((rx + (mx - rx) * valley, ry + (my - ry) * valley))
    return [*base[:1], *pts, *base[1:]]


def mirror(pts, axis=595.0):
    return [(2 * axis - x, y) for x, y in pts]


# ---------------------------------------------------------------------------
# The rig (traced joints, sheet px)
# ---------------------------------------------------------------------------

JOINTS = [
    # name, head, tail, parent, deform, connect
    ("Root", (590, 2250), (590, 2150), None, False, False),
    ("Torso", (590, 1290), (590, 830), "Root", True, False),
    ("Neck", (590, 830), (598, 700), "Torso", True, True),
    ("Head", (598, 700), (590, 380), "Neck", True, True),
    ("Ponytail", (485, 355), (380, 220), "Head", True, False),
    ("Arm_Upper_R", (440, 860), (395, 1085), "Torso", True, False),
    ("Arm_Lower_R", (395, 1085), (362, 1290), "Arm_Upper_R", True, True),
    ("Hand_R", (362, 1290), (355, 1395), "Arm_Lower_R", True, True),
    ("Arm_Upper_L", (750, 860), (795, 1085), "Torso", True, False),
    ("Arm_Lower_L", (795, 1085), (828, 1290), "Arm_Upper_L", True, True),
    ("Hand_L", (828, 1290), (835, 1395), "Arm_Lower_L", True, True),
    ("Leg_Upper_R", (520, 1330), (472, 1600), "Torso", True, False),
    ("Leg_Lower_R", (472, 1600), (437, 1835), "Leg_Upper_R", True, True),
    ("Leg_Upper_L", (660, 1330), (700, 1600), "Torso", True, False),
    ("Leg_Lower_L", (700, 1600), (732, 1835), "Leg_Upper_L", True, True),
]


def build_rig(collection=None):
    bones = [(n, P(*h), P(*t), par, d, c) for n, h, t, par, d, c in JOINTS]
    rig = tk.build_armature_from_joints("CH_Snowboarder_Rig", bones, collection)
    # Front-view legs: each knee bends outward (pole outside the knee).
    tk.add_leg_ik(rig, "L", pole_dir=1)
    tk.add_leg_ik(rig, "R", pole_dir=-1)
    # The boots ride on the IK targets, so the targets must deform.
    for s in "LR":
        rig.data.bones[f"IK_Target_{s}"].use_deform = True
    return rig


# ---------------------------------------------------------------------------
# Artwork, back to front. Each layer is bound to one bone.
# ---------------------------------------------------------------------------

BASE_LAYERS = [  # (layer, bone) in draw order, back to front
    ("Ponytail", "Ponytail"), ("Hair_Back", "Head"),
    ("Leg_R", "Leg_Upper_R"), ("Leg_L", "Leg_Upper_L"),          # one rubber-hose shape per leg
    ("Shorts", "Torso"), ("Shorts_R", "Leg_Upper_R"), ("Shorts_L", "Leg_Upper_L"),
    ("Boot_R", "IK_Target_R"), ("Boot_L", "IK_Target_L"),
    ("Jacket", "Torso"),
    ("Face", "Head"), ("Mouth", "Head"), ("Hair_Front", "Head"), ("Goggles", "Head"), ("Eyes", "Head"),
    ("Goggle_Glint", "Head"), ("Hair_Over", "Head"),
    ("Collar", "Torso"), ("Hair_Locks", "Head"),
    ("Hand_R", "Hand_R"), ("Arm_Lower_R", "Arm_Lower_R"), ("Arm_Upper_R", "Arm_Upper_R"),
    ("Hand_L", "Hand_L"), ("Arm_Lower_L", "Arm_Lower_L"), ("Arm_Upper_L", "Arm_Upper_L"),
]
# Parts that get a Multiply cel-shadow layer drawn right above them.
SHADED = {"Ponytail", "Hair_Back", "Leg_R", "Leg_L", "Shorts", "Boot_R", "Boot_L", "Jacket", "Face", "Hair_Front",
          "Collar", "Hand_R", "Arm_Lower_R", "Arm_Upper_R", "Hand_L", "Arm_Lower_L", "Arm_Upper_L"}
LAYERS = [x for l, b in BASE_LAYERS for x in ([(l, b), (f"{l}_Shd", b)] if l in SHADED else [(l, b)])]
# Rubber-hose chains: (layer, bones) blended smoothly across each joint.
SMOOTH_CHAINS = [("Leg_R", ["Leg_Upper_R", "Leg_Lower_R", "IK_Target_R"]),
                 ("Leg_L", ["Leg_Upper_L", "Leg_Lower_L", "IK_Target_L"]),
                 ("Shorts_R", ["Torso", "Leg_Upper_R"]), ("Shorts_L", ["Torso", "Leg_Upper_L"])]


def draw_hair(ob):
    # Ponytail: a fan of spikes from the tie (455, 340).
    back = spikes((485, 345), [(290, 440), (215, 300), (300, 200), (380, 120), (470, 120)],
                  valley=0.6, base=[(500, 320), (480, 380)])
    shape(ob, "Ponytail", back, COL["hair_dark"], "HairDark", width=7, seed=0)
    pony = spikes((485, 345), [(330, 410), (240, 340), (255, 250), (330, 170), (420, 115), (505, 150), (575, 240)],
                  valley=0.55, base=[(500, 330), (478, 375)])
    shape(ob, "Ponytail", pony, COL["hair"], "Hair", width=7, seed=1)
    for a, b in (((440, 340), (320, 330)), ((440, 310), (330, 260)), ((450, 290), (390, 200)),
                 ((465, 280), (462, 175)), ((480, 300), (525, 220))):
        ink(ob, "Ponytail", [a, ((a[0] + b[0]) / 2 + 8, (a[1] + b[1]) / 2), b], width=6, color=COL["hair_light"], name="HairLight")
    shape(ob, "Ponytail", [(462, 340), (492, 330), (505, 360), (474, 372)], COL["slate"], "Tie", width=5)

    shade(ob, "Ponytail", [(470, 350), (420, 330), (330, 410), (420, 380)], "hair")

    # Back hair mass behind the face.
    back = [(450, 420), (470, 350), (560, 315), (660, 310), (730, 345), (768, 420), (758, 490), (728, 565),
            (505, 565), (476, 640), (446, 560)]
    shape(ob, "Hair_Back", back, COL["hair_dark"], "HairDark", width=7, seed=2)

    # Front hair: a cap over the crown, then pointed locks (sheet: long bangs
    # falling onto the goggles, flicks out to the right, locks down the cheeks).
    # The crown ends high at the centre, so forehead shows between the bangs.
    cap = [(452, 470), (462, 380), (515, 332), (600, 316), (680, 324), (738, 362), (772, 432), (728, 468),
           (700, 432), (660, 404), (620, 398), (585, 406), (548, 428), (505, 462)]
    shape(ob, "Hair_Front", cap, COL["hair"], "Hair", width=8, seed=3)
    H = COL["hair"]
    for ra, rb, tip, bend in (((585, 335), (650, 328), (690, 262), -0.2),    # spike up-right
                              ((505, 352), (570, 330), (500, 292), 0.25),    # spike up-left
                              ((665, 336), (735, 362), (795, 340), -0.15),   # flicks out to the right
                              ((712, 378), (765, 420), (818, 438), -0.12),
                              ((728, 425), (770, 470), (796, 545), 0.05),
                              ((724, 470), (752, 500), (760, 600), 0.1),
                              ((462, 405), (540, 392), (488, 488), 0.2)):    # left fringe
        shape(ob, "Hair_Front", lock(ra, rb, tip, bend), H, "Hair", width=7, smooth=False)
    shade(ob, "Hair_Front", [(470, 455), (560, 440), (650, 446), (725, 462), (700, 470), (600, 462), (500, 470)],
          "hair")
    for pts in (((540, 345), (575, 390), (590, 440)), ((640, 335), (660, 390), (665, 440)),
                ((705, 365), (735, 410), (750, 450))):
        ink(ob, "Hair_Front", list(pts), width=6, color=COL["hair_light"], name="HairLight", seed=4)
    # Bangs over the goggles' top edge.
    # Chunky, overlapping bangs over the goggles' top edge (wide roots, curved).
    for ra, rb, tip, bend in (((508, 392), (604, 376), (560, 486), 0.18), ((580, 384), (668, 390), (620, 474), -0.08),
                              ((640, 388), (722, 418), (698, 480), -0.2)):
        shape(ob, "Hair_Over", lock(ra, rb, tip, bend), H, "Hair", width=8, smooth=False)
    for pts in (((560, 400), (566, 440), (562, 470)), ((630, 402), (626, 440), (620, 462))):
        ink(ob, "Hair_Over", list(pts), width=5, color=COL["hair_light"], name="HairLight")
    # Long locks down the cheeks, falling over the collar.
    for ra, rb, tip, bend in (((470, 560), (498, 568), (498, 712), 0.08), ((712, 560), (738, 545), (742, 655), -0.05),
                              ((726, 600), (746, 590), (736, 705), 0.1)):
        shape(ob, "Hair_Locks", lock(ra, rb, tip, bend), H, "Hair", width=7, smooth=False)


def draw_head(ob):
    # Neck in shadow inside the collar opening.
    shape(ob, "Face", [(545, 640), (650, 640), (655, 735), (540, 735)], COL["skin_shade"], "SkinShade", width=6)
    ear = [(456, 535), (426, 522), (404, 545), (402, 588), (424, 612), (458, 606)]
    shape(ob, "Face", ear, COL["skin"], "Skin", width=7, seed=7)
    ink(ob, "Face", [(442, 545), (420, 566), (434, 592)], width=6)
    ink(ob, "Face", [(446, 562), (436, 578)], width=4)
    # Face: cheek under the goggles, a pointed chin, jaw rising to the right.
    face = [(470, 440), (540, 405), (630, 392), (705, 410), (726, 470), (722, 565), (702, 602), (680, 632), (646, 662),
            (610, 676), (592, 682), (572, 674), (540, 660), (512, 634), (494, 598), (472, 562)]
    shape(ob, "Face", face, COL["skin"], "Skin", width=8, seed=6)
    # Cel shadows: under the goggles, left cheek, under the jaw line.
    # Shadow cast by the goggles across both cheeks (clear of the nose tip),
    # under the hairline, and down the left jaw.
    shade(ob, "Face", [(490, 592), (598, 596), (604, 606), (640, 610), (660, 600), (712, 596), (700, 622), (668, 626),
                       (640, 618), (600, 616), (560, 622), (512, 620)], "skin")
    shade(ob, "Face", [(520, 420), (700, 410), (712, 445), (640, 432), (560, 440), (522, 452)], "skin")
    shade(ob, "Face", [(494, 598), (512, 610), (528, 640), (556, 664), (590, 682), (560, 676), (520, 650), (500, 620)],
          "skin")
    # Rosy cheek, pointed nose with a pink tip, nostril.
    shape(ob, "Face", [(668, 612), (700, 604), (706, 624), (676, 632)], COL["blush"], "Blush", line=False)
    nose = [(606, 572), (630, 574), (642, 596), (630, 607), (609, 604)]
    shape(ob, "Face", nose, COL["skin"], "Skin", width=6, seed=8)
    shape(ob, "Face", [(622, 588), (639, 594), (632, 604), (619, 600)], COL["nose_tip"], "NoseTip", line=False)
    ink(ob, "Face", [(604, 600), (616, 605)], width=5)
    draw_eyes(ob)


EXPRESSIONS = ("GLARE", "HAPPY", "SIDE", "SQUINT")  # eye library frames 1-4


def draw_eyes(ob):
    for i, e in enumerate(EXPRESSIONS, start=1):
        draw_eye_set(ob, e, i)
    mod = ob.modifiers.new("Eye Swap", "GREASE_PENCIL_TIME")
    mod.mode = "FIX"
    mod.tree_node_filter = "Eyes"
    mod.offset = 1
    return mod


def draw_eye_set(ob, expr, frame):
    """Eyes and brows seen through the tinted lens (colours pre-tinted, drawn
    over the lens). GLARE: the cocky scowl-grin. HAPPY: wide, brows up.
    SIDE: half-lidded sideways glance (the smirk head). SQUINT: shut tight
    in a laugh (the gritted-grin head)."""
    E = dict(frame=frame)
    if expr == "SQUINT":
        for cx, cy, d in ((545, 535, 1), (664, 546, -1)):
            ink(ob, "Eyes", [(cx - 26 * d, cy - 15), (cx + 16 * d, cy), (cx - 26 * d, cy + 13)], width=10, **E)
        ink(ob, "Eyes", [(508, 506), (560, 512), (602, 530)], width=14, color=COL["brow_tint"], name="Brow", **E)
        ink(ob, "Eyes", [(632, 530), (662, 514), (692, 508)], width=13, color=COL["brow_tint"], name="Brow", **E)
        return
    lid = {"GLARE": 1.0, "HAPPY": 1.25, "SIDE": 0.6}[expr]
    look = 11 if expr == "SIDE" else 0
    for cx, cy, rx, ry in ((543, 535, 38, 25), (664, 546, 26, 21)):
        ry *= lid
        cy0 = cy + (ry * (1 - lid) if lid < 1 else 0)
        eye = [(cx - rx, cy + 4), (cx - rx * 0.4, cy0 - ry), (cx + rx * 0.5, cy0 - ry * 0.9), (cx + rx, cy - 2),
               (cx + rx * 0.3, cy + 20 * 0.85), (cx - rx * 0.5, cy + 20 * 0.8)]
        shape(ob, "Eyes", eye, COL["eye_white_tint"], "EyeWhite", width=5, **E)
        ir = (19 if rx > 30 else 16) * (1 if lid >= 1 else 0.85)
        shape(ob, "Eyes", tk.circle_points(cx + 3 + look, cy + 2, ir, 14), COL["iris_tint"], "Iris", width=3, **E)
        shape(ob, "Eyes", tk.circle_points(cx + 4 + look, cy + 3, ir * 0.45, 10), COL["pupil"], "Pupil", line=False, **E)
        shape(ob, "Eyes", tk.circle_points(cx - 4 + look, cy - 4, ir * 0.28, 8), COL["eye_white_tint"], "Glint",
              line=False, **E)
        ink(ob, "Eyes", [(cx - rx - 5, cy - 1), (cx - rx * 0.3, cy0 - ry - 3), (cx + rx * 0.6, cy0 - ry), (cx + rx + 5, cy - 4)],
            width=10, **E)  # heavy upper lid
        ink(ob, "Eyes", [(cx - rx * 0.6, cy + ry * 0.8), (cx + rx * 0.5, cy + ry * 0.75)], width=3, **E)  # lower lid
    if expr == "HAPPY":
        ink(ob, "Eyes", [(506, 494), (545, 482), (586, 494)], width=11, color=COL["brow_tint"], name="Brow", **E)
        ink(ob, "Eyes", [(636, 502), (664, 490), (692, 498)], width=10, color=COL["brow_tint"], name="Brow", **E)
        return
    if expr == "SIDE":
        ink(ob, "Eyes", [(506, 502), (550, 506), (594, 518)], width=12, color=COL["brow_tint"], name="Brow", **E)
        ink(ob, "Eyes", [(634, 512), (664, 500), (694, 492)], width=11, color=COL["brow_tint"], name="Brow", **E)
        return
    _glare_brows(ob, E)


def _glare_brows(ob, E):
    # The sheet's hard V scowl: brows dive toward the nose.
    ink(ob, "Eyes", [(504, 494), (558, 503), (604, 526)], width=15, color=COL["brow_tint"], name="Brow", **E)
    ink(ob, "Eyes", [(632, 526), (662, 508), (694, 500)], width=13, color=COL["brow_tint"], name="Brow", **E)


def draw_goggles(ob):
    # Strap behind the ear, frame, tinted lens over the eyes, glint.
    shape(ob, "Goggles", [(400, 470), (478, 468), (478, 530), (402, 525)], COL["slate"], "Slate", width=6)
    frame = [(466, 466), (590, 455), (722, 470), (733, 540), (712, 598), (650, 602), (622, 576), (592, 590),
             (498, 598), (466, 560)]
    shape(ob, "Goggles", frame, COL["slate"], "Slate", width=7, seed=8)
    lens = [(492, 487), (590, 475), (712, 488), (718, 540), (700, 578), (652, 582), (612, 560), (575, 582),
            (510, 580), (490, 550)]
    shape(ob, "Goggles", lens, COL["lens"], "Lens", width=4, seed=9)
    shape(ob, "Goggles", [(650, 484), (712, 488), (718, 540), (700, 578), (652, 582), (640, 530)], COL["lens_light"],
          "LensLight", line=False)
    glint = mat("LensGlint", alpha(hx("#efe6df"), 1.0), line=False)
    # Thin streaks at the lens's outer edge, clear of the eye.
    stroke(ob, "Goggle_Glint", [(694, 492), (706, 494), (690, 540), (681, 538)], glint, closed=True)
    stroke(ob, "Goggle_Glint", [(711, 500), (716, 501), (704, 532), (700, 531)], glint, closed=True)


def draw_jacket(ob):
    body = [(430, 780), (590, 800), (720, 780), (800, 850), (815, 1000), (790, 1180), (740, 1265), (590, 1290),
            (450, 1265), (395, 1180), (375, 1000), (390, 850)]
    shape(ob, "Jacket", body, COL["white"], "Cloth", width=8, seed=10)
    for y0, y1 in ((880, 930), (1015, 1070), (1135, 1190), (1240, 1286)):  # under each quilted band
        band = band_shadow(body, y0, y1)
        if band:
            shade(ob, "Jacket", band)
    shade(ob, "Jacket", [(560, 800), (630, 800), (612, 860), (575, 860)])  # under the collar
    # Quilting seams, zip and pocket slits.
    for y in (930, 1070, 1190):
        ink(ob, "Jacket", [(410, y), (500, y + 12), (590, y + 16), (680, y + 12), (785, y)], width=4, seed=y)
    ink(ob, "Jacket", [(592, 800), (594, 1000), (592, 1285)], width=4)
    ink(ob, "Jacket", [(470, 1080), (500, 1120)], width=5)
    if LOOK == "sheet2":
        for pts in (((470, 860), (520, 850), (560, 858)), ((640, 870), (690, 862), (730, 875)),
                    ((480, 1000), (530, 995))):
            ink(ob, "Jacket", list(pts), width=12, color=COL["sheen"], name="Sheen")
    ink(ob, "Jacket", [(715, 1080), (690, 1120)], width=5)

    collar = [(400, 640), (455, 618), (520, 650), (575, 700), (612, 712), (660, 690), (705, 655), (728, 672),
              (725, 760), (650, 805), (590, 815), (520, 805), (420, 775), (390, 705)]
    shape(ob, "Collar", collar, COL["white"], "Cloth", width=8, seed=11)
    # Inside the collar rim, and its lower right side.
    shade(ob, "Collar", [(520, 655), (575, 704), (612, 716), (660, 694), (700, 662), (690, 690), (640, 722), (600, 735),
                         (560, 722), (515, 680)])
    shade(ob, "Collar", [(705, 700), (724, 690), (722, 760), (650, 805), (600, 812), (660, 770)])
    ink(ob, "Collar", [(612, 712), (600, 760), (594, 812)], width=4)
    ink(ob, "Collar", [(430, 715), (520, 750), (585, 760)], width=4)


def draw_arm(ob, side):
    """Hanging puffer sleeve: big upper puff, lower puff with cuff, mitt hand."""
    m = (lambda pts: pts) if side == "R" else mirror
    upper = m([(465, 815), (360, 815), (255, 890), (225, 1010), (265, 1110), (380, 1135), (470, 1070), (495, 930)])
    lower = m([(285, 1050), (240, 1150), (250, 1250), (300, 1305), (420, 1310), (465, 1240), (470, 1140), (440, 1060)])
    cuff = m([(305, 1268), (425, 1272), (418, 1312), (310, 1308)])
    hand = m([(330, 1290), (400, 1290), (410, 1340), (395, 1395), (360, 1410), (330, 1385), (315, 1340), (300, 1310)])
    shape(ob, f"Hand_{side}", hand, COL["skin"], "Skin", width=6, seed=12)
    ink(ob, f"Hand_{side}", m([(345, 1350), (350, 1395)]), width=3)
    ink(ob, f"Hand_{side}", m([(370, 1350), (372, 1400)]), width=3)
    shape(ob, f"Arm_Lower_{side}", lower, COL["white"], "Cloth", width=8, seed=13)
    shade(ob, f"Arm_Lower_{side}", crescent(lower, (0.05, 0.45), 0.72, bias=(0, 6)))
    if LOOK == "sheet2":  # metal tube cuff with a dark opening
        tube = m([(318, 1255), (412, 1255), (418, 1325), (312, 1325)])
        shape(ob, f"Arm_Lower_{side}", tube, COL["metal"], "Metal", width=6)
        shape(ob, f"Arm_Lower_{side}", m([(322, 1312), (408, 1312), (402, 1330), (328, 1330)]), COL["metal_dark"],
              "MetalDark", width=4)
        ink(ob, f"Arm_Lower_{side}", m([(330, 1270), (334, 1305)]), width=5, color=COL["sheen"], name="Sheen")
    else:
        shape(ob, f"Arm_Lower_{side}", cuff, COL["white"], "Cloth", width=6)
    ink(ob, f"Arm_Lower_{side}", m([(250, 1185), (360, 1205), (465, 1190)]), width=4)
    shape(ob, f"Arm_Upper_{side}", upper, COL["white"], "Cloth", width=8, seed=14)
    shade(ob, f"Arm_Upper_{side}", crescent(upper, (0.25, 0.62), 0.72, bias=(0, 10)))
    shade(ob, f"Hand_{side}", crescent(hand, (0.15, 0.5), 0.6), "skin")
    ink(ob, f"Arm_Upper_{side}", m([(232, 960), (360, 990), (490, 975)]), width=4)
    if LOOK == "sheet2":  # nylon sheen
        ink(ob, f"Arm_Upper_{side}", m([(300, 870), (350, 850), (410, 852)]), width=12, color=COL["sheen"], name="Sheen")
        ink(ob, f"Arm_Lower_{side}", m([(275, 1110), (285, 1160)]), width=10, color=COL["sheen"], name="Sheen")


def draw_legs(ob):
    # One continuous shape per leg (hem to ankle), bound as a rubber hose so
    # the knee curves instead of hinging.
    for side, leg, shd, knee in (
        ("R", [(458, 1360), (568, 1370), (532, 1480), (502, 1590), (497, 1630), (490, 1680), (472, 1770), (468, 1850),
               (405, 1850), (418, 1720), (440, 1612), (442, 1480)],
         [(540, 1372), (568, 1370), (532, 1480), (502, 1590), (497, 1630), (490, 1680), (472, 1770), (468, 1850),
          (452, 1850), (458, 1760), (476, 1660), (488, 1590), (515, 1480)], 472),
        ("L", [(622, 1370), (718, 1360), (730, 1480), (740, 1600), (752, 1700), (766, 1850), (702, 1850), (695, 1770),
               (680, 1665), (678, 1612), (655, 1480)],
         [(700, 1362), (718, 1360), (730, 1480), (740, 1600), (752, 1700), (766, 1850), (746, 1850), (734, 1720),
          (722, 1610), (708, 1480)], 708),
    ):
        shape(ob, f"Leg_{side}", leg, COL["skin"], "Skin", width=6, seed=15)
        shade(ob, f"Leg_{side}", shd, "skin")
        ink(ob, f"Leg_{side}", [(knee - 14, 1596), (knee, 1610), (knee + 12, 1600)], width=4)
    hips = [(440, 1225), (745, 1225), (722, 1330), (590, 1335), (460, 1330)]
    shape(ob, "Shorts", hips, COL["shorts"], "Shorts", width=7, seed=17)
    shade(ob, "Shorts", [(440, 1225), (745, 1225), (740, 1250), (440, 1250)], "hair")  # under the jacket hem
    shape(ob, "Shorts_R", [(450, 1300), (590, 1310), (565, 1395), (455, 1385)], COL["shorts"], "Shorts", width=7)
    shape(ob, "Shorts_L", [(595, 1310), (725, 1300), (715, 1388), (620, 1398)], COL["shorts"], "Shorts", width=7)
    ink(ob, "Shorts_R", [(480, 1320), (490, 1380)], width=6, color=COL["shorts_light"], name="ShortsLight")
    ink(ob, "Shorts_L", [(700, 1320), (695, 1380)], width=6, color=COL["shorts_light"], name="ShortsLight")


def draw_boots(ob):
    for side, cuff, boot, sole, crease in (
        ("R", [(315, 1805), (500, 1795), (518, 1835), (505, 1935), (330, 1940), (312, 1840)],
         [(305, 1925), (505, 1925), (520, 2060), (520, 2180), (500, 2250), (280, 2252), (190, 2235), (185, 2150),
          (260, 2080), (305, 2010)],
         [(188, 2205), (300, 2220), (515, 2215)], [(300, 2010), (420, 2040), (515, 2060)]),
        ("L", [(640, 1800), (825, 1800), (838, 1840), (830, 1935), (655, 1940), (640, 1840)],
         [(650, 1925), (840, 1925), (860, 2020), (960, 2090), (995, 2160), (990, 2235), (860, 2255), (650, 2245),
          (630, 2160), (640, 2040)],
         [(640, 2205), (850, 2220), (992, 2200)], [(660, 2050), (780, 2060), (900, 2070)]),
    ):
        layer = f"Boot_{side}"
        shape(ob, layer, boot, COL["boot"], "Boot", width=8, seed=18)
        shade(ob, layer, crescent(boot, (0.25, 0.6), 0.75, bias=(0, 10)), "boot")
        if LOOK == "sheet2":  # tan toe cap and ankle strap
            cap = ([(255, 2088), (278, 2150), (286, 2240), (198, 2230), (190, 2158)] if side == "R" else
                   [(905, 2078), (962, 2097), (988, 2162), (984, 2228), (900, 2242), (884, 2150)])
            shape(ob, layer, cap, COL["boot_panel"], "BootPanel", width=5)
            bx = (boot[0][0] + boot[1][0]) / 2
            shape(ob, layer, [(bx - 100, 1985), (bx + 100, 1985), (bx + 105, 2030), (bx - 100, 2030)], COL["boot_panel"],
                  "BootPanel", width=5)
        ink(ob, layer, sole, width=5)
        ink(ob, layer, crease, width=4)
        shape(ob, layer, cuff, COL["cuff"], "Cuff", width=7, seed=19)
        shade(ob, layer, crescent(cuff, (0.3, 0.75), 0.65), "boot")
        cx = (cuff[0][0] + cuff[1][0]) / 2
        shape(ob, layer, [(cx - 45, 1810), (cx + 45, 1808), (cx + 40, 1830), (cx - 40, 1832)], COL["shorts"], "Shorts",
              width=4)  # the leg opening


# ---------------------------------------------------------------------------
# Mouth library in this style (9 visemes on frames 1-9 of the Mouth layer)
# ---------------------------------------------------------------------------

MOUTH_C = (592, 622)
# viseme: (width px, open px, roundness 0..1, teeth: 'top' | 'both' | None, tongue)
VISEME_SHAPES = {
    "A_I": (112, 44, 0.2, "top", False),
    "E": (118, 26, 0.0, "both", False),
    "O": (66, 48, 0.9, None, True),
    "U": (44, 30, 1.0, None, False),
    "MBP": (96, 0, 0.0, None, False),
    "LDT": (100, 36, 0.3, "top", True),
    "WQ": (38, 22, 1.0, None, False),
    "FV": (96, 14, 0.0, "top", False),
    "REST": (122, 24, 0.0, "both", False),  # her signature toothy smirk
    "GRIT": (130, 34, 0.0, "grit", False),  # gritted laugh (frame 10)
    "SMIRK": (96, 0, 0.0, None, False),     # closed side smirk (frame 11)
}
MOUTH_EXTRAS = ("GRIT", "SMIRK")


def mouth_curves(w, h, rnd, smirk=10, n=13):
    """Top and bottom lip curves (sheet px), corners curling up into a smirk
    (the right corner higher, as on the sheet)."""
    cx, cy = MOUTH_C
    top, bot = [], []
    for i in range(n):
        t = -1 + 2 * i / (n - 1)
        x = cx + t * w / 2
        curl = -smirk * (t ** 2) * (1 - rnd) + 11 * t  # corners up; the sheet's grin rises to her right cheek
        y_top = cy + curl - (h * 0.25) * (1 - t * t) * rnd
        y_bot = cy + curl + h * (1 - t * t) ** (0.8 if rnd < 0.5 else 0.5)
        top.append((x, y_top))
        bot.append((x, y_bot))
    return top, bot


def draw_mouth(ob, viseme, frame):
    w, h, rnd, teeth, tongue = VISEME_SHAPES[viseme]
    top, bot = mouth_curves(w, h, rnd, smirk=14 if viseme in ("REST", "E", "A_I", "GRIT") else 8)
    if viseme == "SMIRK":
        top = [(x, y - 0.6 * max(0, x - MOUTH_C[0])) for x, y in top]  # one corner pulled up
        ink(ob, "Mouth", top, width=7, frame=frame)
        ink(ob, "Mouth", [top[-1], (top[-1][0] + 8, top[-1][1] - 10)], width=4, frame=frame)
        return
    if h == 0:
        ink(ob, "Mouth", top, width=6, frame=frame)
        return
    if teeth == "grit":  # teeth fill the mouth, a zig-zag bite line
        shape(ob, "Mouth", top + bot[::-1], COL["white"], "Teeth", width=7, frame=frame)
        mid = [(x, (yt + yb) / 2 + (4 if i % 2 else -4)) for i, ((x, yt), (_, yb)) in enumerate(zip(top, bot))]
        ink(ob, "Mouth", mid[1:-1], width=3, frame=frame)
        for (x, yt), (_, yb) in list(zip(top, bot))[2:-2:2]:
            ink(ob, "Mouth", [(x, yt + 3), (x, yb - 3)], width=2, frame=frame)
        return
    shape(ob, "Mouth", top + bot[::-1], COL["mouth"], "Mouth", width=6, frame=frame)
    if tongue:
        tb = [(x, y - min(10, h * 0.3)) for x, y in bot[3:-3]]
        shape(ob, "Mouth", bot[3:-3] + tb[::-1], COL["tongue"], "Tongue", line=False, frame=frame)
    if viseme in ("REST", "E", "A_I"):  # the deep curled corner of her grin
        ink(ob, "Mouth", [(top[0][0] + 6, top[0][1] + 6), (top[0][0] - 6, top[0][1] - 2), (top[0][0] - 4, top[0][1] - 12)],
            width=6, frame=frame)
    if teeth:
        th = min(h * 0.62, 18)
        lower = [(x, min(y + th, yb - 2)) for (x, y), (_, yb) in zip(top, bot)]
        # Teeth start right at the lip line (no dark band above them).
        shape(ob, "Mouth", top + lower[::-1], COL["white"], "Teeth", width=3, frame=frame, smooth=False)
        if teeth == "both" and h > 18:
            upper_b = [(x, max(yb - th * 0.7, yt + th + 2)) for (x, yt), (_, yb) in zip(top, bot)]
            shape(ob, "Mouth", upper_b[2:-2] + bot[2:-2][::-1], COL["white"], "Teeth", width=3, frame=frame)
        for x, y in top[3:-3:2]:
            ink(ob, "Mouth", [(x, y + 2), (x + 1, y + th - 2)], width=2, frame=frame)


def build_mouth_library(ob):
    for i, v in enumerate(tk.VISEMES + MOUTH_EXTRAS, start=1):
        draw_mouth(ob, v, i)
    mod = ob.modifiers.new("Mouth Swap", "GREASE_PENCIL_TIME")
    mod.mode = "FIX"
    mod.tree_node_filter = "Mouth"
    mod.offset = tk.VISEMES.index("REST") + 1
    return mod


# ---------------------------------------------------------------------------
# Snowboard prop (her signature prop, a separate object)
# ---------------------------------------------------------------------------

def build_board(collection=None):
    ob = tk.new_gp_object("Prop_Snowboard", collection)
    ob.location.y = 0.05  # behind her boots, as on the sheet
    top_c, bot_c, half = Vector((1010, 1000)), Vector((830, 2235)), 92
    axis = (bot_c - top_c).normalized()
    nrm = Vector((-axis.y, axis.x))

    def at(t, s):
        p = top_c.lerp(bot_c, t) + nrm * (s * half)
        return (p.x, p.y)

    outline = [at(0.0, -0.75), at(-0.03, 0), at(0.0, 0.75), at(0.04, 1), at(0.96, 1), at(1.0, 0.75), at(1.03, 0),
               at(1.0, -0.75), at(0.96, -1), at(0.04, -1)]
    shape(ob, "Board", outline, COL["board_white"], "Board", width=8, seed=20)
    dark = [at(0.3, -1), at(0.42, 1), at(0.96, 1), at(1.0, 0.75), at(1.03, 0), at(1.0, -0.75), at(0.96, -1)]
    shape(ob, "Board", dark, COL["board_dark"], "BoardDark", width=4, seed=21)
    for t in (0.62, 0.68):
        shape(ob, "Board", [at(t, -0.98), at(t + 0.035, 0.98), at(t + 0.05, 0.98), at(t + 0.015, -0.98)],
              COL["board_stripe"], "BoardStripe", line=False)
    for t, s, r in ((0.33, 0.2, 14), (0.4, 0.45, 16)):
        x, y = at(t, s)
        shape(ob, "Board", tk.circle_points(x, y, r, 10), COL["board_dark"], "BoardDark", line=False)
    return ob


# ---------------------------------------------------------------------------
# Assembly and poses
# ---------------------------------------------------------------------------

def build(collection=None, with_board=True, look="sheet1"):
    """Build the rig and the drawing, bind them, add the mouth and eye
    libraries. look: 'sheet1' (white) or 'sheet2' (blue-grey, tube cuffs,
    cream/tan boots). Returns (rig, art, board)."""
    use_look(look)
    rig = build_rig(collection)
    coll = rig.users_collection[0]
    art = tk.new_gp_object("CH_Snowboarder_Art", coll)
    for layer, _ in LAYERS:  # create in back-to-front order
        tk.gp_layer(art, layer)
    draw_hair(art)
    draw_head(art)
    draw_goggles(art)
    draw_jacket(art)
    draw_arm(art, "R")
    draw_arm(art, "L")
    draw_legs(art)
    draw_boots(art)
    build_mouth_library(art)
    tk.bind_layers_to_bones(art, rig, dict(LAYERS))
    for layer, bones in SMOOTH_CHAINS:
        for lay in (layer, f"{layer}_Shd"):  # a part's shadow bends exactly like the part
            if lay in art.data.layers and len(art.data.layers[lay].frames):
                tk.bind_smooth_chain(art, lay, rig, bones, blend=0.045)
    for layer, _ in LAYERS:
        if layer.endswith("_Shd"):
            tk.shadow_layer(art, layer, 0.45)
    # Puffer volume: a lattice per jacket part, animated with shape keys.
    global LATTICES
    LATTICES = {layer: tk.add_puff_lattice(art, layer, rig, bone, name=f"LAT_{layer}")
                for layer, bone in (("Jacket", "Torso"), ("Arm_Upper_R", "Arm_Upper_R"), ("Arm_Lower_R", "Arm_Lower_R"),
                                    ("Arm_Upper_L", "Arm_Upper_L"), ("Arm_Lower_L", "Arm_Lower_L"))}
    for lat in LATTICES.values():
        for layer in (f"{lat.name[4:]}_Shd",):  # the part's shadow layer deforms with it
            if layer in art.data.layers:
                m = art.modifiers.new(f"Puff {layer}", "GREASE_PENCIL_LATTICE")
                m.object = lat
                m.tree_node_filter = layer
    tk.light_layers(art, False)  # flat cel colours, like the sheet
    board = build_board(coll) if with_board else None
    if board:
        tk.light_layers(board, False)
    return rig, art, board


def reset_pose(rig):
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def pose_sheet(rig):
    """The model sheet's pose: near hand on hip (elbow out), far forearm
    resting on the board, head cocked, weight on the near leg."""
    reset_pose(rig)
    tk.rotate_bone_2d(rig, "Arm_Upper_R", math.radians(-40))   # elbow out to screen-left
    tk.rotate_bone_2d(rig, "Arm_Lower_R", math.radians(75))    # forearm folds back to the hip
    tk.rotate_bone_2d(rig, "Hand_R", math.radians(30))
    tk.rotate_bone_2d(rig, "Arm_Upper_L", math.radians(55))    # arm out over the board
    tk.rotate_bone_2d(rig, "Arm_Lower_L", math.radians(25))
    tk.rotate_bone_2d(rig, "Head", math.radians(-6))           # cocky tilt
    tk.rotate_bone_2d(rig, "Ponytail", math.radians(-10))


LATTICES = {}


def walk(rig, start=1, length=24):
    """She is drawn from the front, so she walks in place toward camera:
    alternating knee lifts, a bounce, small arm swings, ponytail trailing.
    The puffer squashes on each contact and re-inflates (sleeves 2 frames
    behind the body: overlapping action)."""
    reset_pose(rig)
    keys = tk.walk_front(rig, start=start, length=length, H=0.32)
    h = length // 2
    for f0 in (start, start + h, start + length):
        for name, lat in LATTICES.items():
            lag = 0 if name == "Jacket" else 2
            tk.key_puff(lat, f0 + lag, puff=0.0, squash=0.55)
            tk.key_puff(lat, min(f0 + h // 2 + lag, start + length + lag), puff=0.6, squash=-0.35)
    return keys


def express(art, frame, eyes=None, mouth=None):
    """Key an expression: eyes in EXPRESSIONS, mouth a viseme or GRIT/SMIRK.
    Constant interpolation, so faces swap like drawings."""
    if eyes:
        art.modifiers["Eye Swap"].offset = EXPRESSIONS.index(eyes) + 1
        art.keyframe_insert('modifiers["Eye Swap"].offset', frame=frame)
    if mouth:
        art.modifiers["Mouth Swap"].offset = (tk.VISEMES + MOUTH_EXTRAS).index(mouth) + 1
        art.keyframe_insert('modifiers["Mouth Swap"].offset', frame=frame)
    for fc in tk.fcurves(art):
        for k in fc.keyframe_points:
            k.interpolation = "CONSTANT"


def talk(art, line_cues, fps=24):
    """Lip-sync a line: [(seconds, viseme), ...]."""
    return tk.key_visemes(art, line_cues, fps=fps, lead_frames=1)
