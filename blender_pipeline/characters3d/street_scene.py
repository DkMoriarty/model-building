"""CROSSWALK: the fixie rider meets a girl on a city street (original scene).

    blender -b -P blender_pipeline/characters3d/street_scene.py -- --out renders/crosswalk --stills 40,90,120,140,170,230,290
    blender -b -P blender_pipeline/characters3d/street_scene.py -- --out renders/crosswalk --frames 1-312
    python3 blender_pipeline/characters3d/street_scene_audio.py --out renders/crosswalk

Story (24 fps, 312 frames = 13 s). Layout follows the studio rules: an
establishing wide, cut on action, push in for intensity, hold after the
turning point, one action at a time.

  A  1-72     WIDE      Golden-hour street. He cruises toward us down the bike lane, grinning.
  B  73-108   TRACK     Medium tracking alongside him: pedalling, carefree, head bobbing.
  C  109-132  REVEAL    His POV, long lens: she steps out from behind a parked car onto the crosswalk.
  D  133-150  CLOSE     His face: eyes snap wide.
  E  151-198  SKID      Side wide: he locks his legs, the rear wheel skids, the bike pitches onto
                        its front wheel (a stoppie); he lurches over the bar and stops nose to nose with her.
  F  199-276  AWE       Two-shot, slow push-in: frozen. Sparkling eyes, blush, jaw drops, hearts float up.
                        She looks at him, a small smile, tucks her hair, walks on.
  G  277-312  DAZED     Close on him, still frozen, hearts drifting; she has gone; the bike wobbles.
"""

import argparse
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fixie_rider as fr  # noqa: E402

FPS = 24
SHOTS = [("WIDE", 1, 72), ("TRACK", 73, 108), ("REVEAL", 109, 132), ("CLOSE", 133, 150), ("SKID", 151, 198),
         ("AWE", 199, 276), ("DAZED", 277, 312)]
LAST = SHOTS[-1][2]
hx = fr.hx

fr.COL.update({
    # Her palette: black bob, mustard cardigan, white tee, light-wash wide jeans, red bag, gold hoops.
    "g_skin": hx("#c4825c"), "g_hair": hx("#18141a"), "g_hair_sheen": hx("#3a3542"), "g_iris": hx("#2c180e"),
    "g_lip": hx("#c46a62"), "g_blush": hx("#e79a8c"), "cardigan": hx("#4b66ab"), "cardigan_rib": hx("#425b9c"), "silver": hx("#d9dbe0"),
    "tee": hx("#f4f1ea"), "jeans": hx("#8fa9c9"), "jeans_seam": hx("#6f89ab"), "g_shoe": hx("#f3f1ec"),
    "g_sole": hx("#e6e2da"), "g_bag": hx("#b8352d"), "gold": hx("#d8b25a"),
    # Street.
    "asphalt": hx("#55565c"), "asphalt_dark": hx("#46474c"), "paint": hx("#f1efe8"), "paint_yellow": hx("#e2b84a"),
    "sidewalk": hx("#bdb8b0"), "curb": hx("#a7a29a"), "glass": hx("#5b6b7d"), "frame_w": hx("#efe9de"),
    "trunk": hx("#6b4c38"), "leaf": hx("#7f9b5c"), "leaf2": hx("#6c8a4e"), "pole": hx("#3c4048"), "lamp": hx("#fff1cf"),
    "car": hx("#3f8f8a"), "car_glass": hx("#2c3a46"), "tyre": hx("#1d1d20"), "awning1": hx("#b5523d"),
    "awning2": hx("#f1e6d0"), "sign_red": hx("#c8413a"), "sign_green": hx("#5dbb72"),
    "heart": hx("#ff6f8f"), "sparkle": hx("#fffbea"), "blush": hx("#ff8f8f"), "mouth": hx("#4a2020"),
    "smoke": hx("#cfcac2"),
})
FACADES = ["#d7a07f", "#e9dcc4", "#a9bfa0", "#9fb3c8", "#e4b9a3", "#c9c0d6", "#efd9a6"]


def emission_mat(name, col, strength=2.0):
    m = bpy.data.materials.new(f"EM_{name}")
    if getattr(m, "node_tree", None) is None and hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = col
    em.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


# ---------------------------------------------------------------------------
# Her: an original character in the same long-legged 3D style
# ---------------------------------------------------------------------------

def build_girl():
    rig = fr.build_rig("GR_Rig")
    jp = fr.jp
    tube, blob, box, bind, skin_chain, mat, arc = fr.tube, fr.blob, fr.box, fr.bind, fr.skin_chain, fr.mat, fr.arc
    parts = []

    def add(ob, bone):
        bind(ob, rig, bone)
        parts.append(ob)
        return ob

    skin = mat("g_skin", 0.5, sss=0.3)
    jeans = mat("jeans", 0.85, sheen=0.2)
    for s in "LR":
        hip, knee, ank = jp(f"hip_{s}"), jp(f"knee_{s}"), jp(f"ankle_{s}")
        # Wide-leg jeans from hip to shoe, bending smoothly at the knee.
        leg = arc(hip + Vector((0, 0, 0.04)), knee, n=4)[:-1] + [knee] + arc(knee, ank + Vector((0, 0, -0.03)), n=5)[1:]
        r = [(0.085, 0.082), (0.08, 0.078), (0.074, 0.072), (0.072, 0.07), (0.078, 0.074), (0.088, 0.082), (0.1, 0.09),
             (0.112, 0.098)]
        parts.append(skin_chain(tube(f"Jeans_{s}", leg, r, jeans, caps=False, ring=16, crease=0.7, facet=0.03, seed=6), rig,
                                [f"Thigh_{s}", f"Shin_{s}"], blend=0.07))
        seam = [p + Vector((0.08 if s == "L" else -0.08, 0, 0)) for p in leg]
        # Chunky white platform sneakers.
        x = ank.x
        upper = [(x, 0.09, 0.09), (x, 0.06, 0.1), (x, 0.0, 0.095), (x, -0.07, 0.08), (x, -0.13, 0.065), (x, -0.17, 0.055)]
        add(tube(f"Shoe_{s}", upper, [(0.052, 0.04), (0.056, 0.048), (0.058, 0.046), (0.058, 0.042), (0.052, 0.033),
                                      (0.036, 0.024)], mat("g_shoe", 0.7)), f"Foot_{s}")
        add(tube(f"Sole_{s}", [(x, 0.1, 0.03), (x, 0.0, 0.028), (x, -0.12, 0.026), (x, -0.18, 0.03)],
                 [(0.056, 0.03), (0.064, 0.028), (0.062, 0.028), (0.04, 0.026)], mat("g_sole", 0.8)), f"Foot_{s}")
        _ = seam
    add(blob("G_Hips", (0, 0.005, 0.99), (0.15, 0.11, 0.11), jeans), "Pelvis")
    add(tube("G_Belt", [(0, 0.0, 1.03), (0, 0.0, 1.055)], [(0.152, 0.112), (0.152, 0.112)], mat("g_bag", 0.5), caps=False,
             subdiv=1), "Pelvis")
    # A chunky blue cable-knit crewneck over a white collared shirt, a fine silver chain.
    card = mat("cardigan", 0.95, sheen=0.6)
    add(tube("Sweater", [(0, 0.0, 0.93), (0, 0.0, 1.15), (0, 0.0, 1.33), (0, 0.0, 1.41)],
             [(0.2, 0.15), (0.19, 0.14), (0.2, 0.135), (0.13, 0.085)], card, ring=20, crease=0.3, facet=0.03, seed=8), "Spine")
    for k in range(5):                                   # knit cables running down the front
        x = -0.1 + 0.05 * k
        add(tube(f"Cable{k}", [(x, -0.14, 0.98), (x, -0.146, 1.15), (x, -0.13, 1.33)], [0.008, 0.009, 0.008], card,
                 subdiv=1, ring=8), "Spine")
    add(fr.torus("SweaterNeck", Vector((0, 0.0, 1.405)), 0.085, 0.012, mat("cardigan_rib", 0.95), axis="Z"), "Spine")
    shirt = mat("tee", 0.7)
    for sx in (1, -1):                                   # white shirt collar points over the crewneck
        add(tube(f"Collar{sx}", [(sx * 0.03, -0.055, 1.44), (sx * 0.08, -0.075, 1.415), (sx * 0.14, -0.07, 1.37)],
                 [(0.004, 0.03), (0.004, 0.034), (0.003, 0.014)], shirt, side=Vector((0, 1, 0)), subdiv=1), "Spine")
    chain = [Vector((0.03 * math.sin(a_) * 1.0, -0.024 - 0.01 * math.cos(a_), 1.47 - 0.035 * math.cos(a_ / 2) ** 0.5))
             for a_ in [-math.pi / 2 + math.pi * i / 10 for i in range(11)]]
    add(tube("Necklace", chain, [0.0014] * len(chain), mat("silver", 0.2, metallic=1.0), subdiv=0, ring=6), "Neck")
    for s, sx in (("L", 1), ("R", -1)):
        sho, elb, wri, hand = jp(f"sho_{s}"), jp(f"elb_{s}"), jp(f"wri_{s}"), jp(f"hand_{s}")
        # Long, slouchy sleeves to the wrist (bend with the elbow), ribbed cuffs.
        slv = arc(sho + Vector((-sx * 0.03, 0, 0.02)), elb, n=4)[:-1] + [elb] + arc(elb, wri, n=4)[1:]
        parts.append(skin_chain(tube(f"CardSleeve_{s}", slv, [(0.09, 0.085), (0.095, 0.09), (0.092, 0.088), (0.088, 0.085),
                                                               (0.084, 0.082), (0.072, 0.07), (0.06, 0.058)], card,
                                     caps=False), rig, [f"UpperArm_{s}", f"Forearm_{s}"], blend=0.06))
        add(tube(f"CardCuff_{s}", [wri + Vector((0, 0, 0.03)), wri - Vector((0, 0, 0.005))], [0.05, 0.048],
                 mat("cardigan_rib", 0.9), caps=False, subdiv=1), f"Forearm_{s}")
        add(blob(f"G_Hand_{s}", wri.lerp(hand, 0.55), (0.026, 0.02, 0.05), skin), f"Hand_{s}")
        add(blob(f"G_Thumb_{s}", wri.lerp(hand, 0.35) + Vector((0, -0.022, 0)), (0.01, 0.01, 0.022), skin,
                 rot=(math.radians(-25), 0, 0)), f"Hand_{s}")
    # Red shoulder bag on a thin strap.
    add(tube("G_Strap", [(0.15, 0.0, 1.43), (0.17, -0.06, 1.25), (0.2, -0.05, 1.08)], [0.008] * 3, mat("g_bag", 0.5),
             side=Vector((0, 1, 0)), subdiv=1), "Spine")
    add(box("G_Bag", (0.21, -0.03, 1.03), (0.06, 0.16, 0.11), mat("g_bag", 0.45, sheen=0.2), bevel=0.025), "Pelvis")
    add(tube("G_BagFlap", [(0.24, -0.1, 1.07), (0.24, 0.04, 1.07)], [0.006, 0.006], mat("gold", 0.3, metallic=0.8),
             subdiv=1), "Pelvis")
    # Neck, head: oval face, big lashed eyes, small nose, soft lips.
    add(tube("G_Neck", [(0, 0.01, 1.38), (0, 0.0, 1.6)], [0.025, 0.022], skin), "Neck")   # long, thin, elegant
    hc = Vector((0, -0.005, 1.70))
    size = (0.118, 0.118, 0.15)         # shield head: wide upper face; the jaw outline is set in sculpt_head (shield)
    # Sculpted face: a delicate nose, sharper chin, lashed eyes, a soft closed smile.
    # Face measured from the reference: a long narrow oval with a small rounded
    # chin, wide-set dark almond eyes with a light liner, thin high arched
    # brows, a small upturned rosy nose, small parted lips, strong blush.
    fr.build_face(add, hc, size, skin, "g_iris", "g_hair", "lip_toon", prefix="G_", nose=1.0, chin=0.5, cheek=1.0,
                  jaw=0.75, eye_r=0.04, lashes=True, smirk=0.0, style="toon", lips=0.4,
                  paint=("g_skin", "blush_toon", "lip_toon", None), brows="thin", wing=0.35, eye_shape="almond",
                  layout=fr.HER_LAYOUT)
    silver = mat("silver", 0.2, metallic=1.0)
    for sx in (1, -1):   # round silver hoops hanging from the lobes
        c = hc + Vector((sx * size[0] * 1.02, 0.004, size[2] * (fr.HER_LAYOUT["ear_uz"] - 0.5)))
        add(fr.torus(f"G_Earring{sx}", c, 0.016, 0.0024, silver, axis="X"), "Head")
    # Black hair parted in the centre, pulled back into a low ponytail, loose strands framing the face.
    fr.ribbon_hair(add, hc, size, fr.matte_hair_material(fr.hx("#07060a")), seed=5, style="ponytail", prefix="G_")
    rig.scale = (0.95, 0.95, 0.95)
    return rig, parts


# Reference-face look-dev: paint a reference face image onto her sculpted head.
# Landmarks are measured in the image's pixels (the tennis-street "Thanks"
# still: 1199 x 716): her cheek edges at eye level, chin tip, hairline centre.
REF_FACE_LANDMARKS = {"cheek_l": (918, 285), "cheek_r": (697, 285), "chin": (808, 415), "hairline": (808, 140)}
REF_FACE_OVAL = (808, 280, 110, 140)            # face area kept from the image (cx, cy, rx, ry)
REF_FACE_SKIN = (220, 132, 102)                 # fill colour sampled from her cheek


def impose_reference_face(g_rig, image_path, landmarks=None, oval=None, skin=None):
    """Cut the face out of a reference image, impose it on her head (front
    projection fitted to the head outline), fill the rest with the sampled skin
    tone and hide the 3D eyes/brows/mouth it replaces. A still-frame look:
    the painted face does not animate expressions."""
    return fr.project_face_image(g_rig, "G_", image_path, landmarks or REF_FACE_LANDMARKS, oval or REF_FACE_OVAL,
                                 skin_rgb=skin or REF_FACE_SKIN)


# ---------------------------------------------------------------------------
# The street (road runs along Y; he rides toward -Y; she crosses along -X)
# ---------------------------------------------------------------------------

ROAD_W = 7.0          # kerb to kerb
WALK_Y = (-1.6, 1.6)  # crosswalk band
LANE_X = 1.3          # his line
CAR = Vector((2.75, 3.6, 0))


def build_street():
    mat, box, blob, tube, disc, torus = fr.mat, fr.box, fr.blob, fr.tube, fr.disc, fr.torus
    rnd = random.Random(11)
    hw = ROAD_W / 2
    box("Road", (0, 0, -0.05), (ROAD_W + 0.2, 120, 0.1), mat("asphalt", 0.92), bevel=0.0)
    for y in range(-58, 60, 4):  # dashed centre line (skip the crosswalk)
        if WALK_Y[0] - 1 < y < WALK_Y[1] + 1:
            continue
        box(f"Dash{y}", (0, y, 0.002), (0.12, 2.0, 0.006), mat("paint_yellow", 0.7), bevel=0.0)
    for k in range(9):  # zebra stripes along the road direction
        x = -hw + 0.55 + k * 0.8
        box(f"Zebra{k}", (x, 0, 0.003), (0.45, WALK_Y[1] - WALK_Y[0], 0.006), mat("paint", 0.7), bevel=0.0)
    for y0 in (WALK_Y[0] - 0.35, WALK_Y[1] + 0.35):  # stop lines
        box(f"StopLine{y0}", (0, y0, 0.003), (ROAD_W - 0.4, 0.18, 0.006), mat("paint", 0.7), bevel=0.0)
    for sx in (1, -1):  # bike-lane edge lines
        box(f"LaneLine{sx}", (sx * 2.25, 0, 0.003), (0.1, 120, 0.006), mat("paint", 0.7), bevel=0.0)
        box(f"Sidewalk{sx}", (sx * (hw + 1.6), 0, 0.075), (3.2, 120, 0.15), mat("sidewalk", 0.95), bevel=0.01)
        box(f"Curb{sx}", (sx * (hw + 0.08), 0, 0.08), (0.16, 120, 0.16), mat("curb", 0.9), bevel=0.02)
        for y in range(-58, 60, 2):  # paving joints
            box(f"Joint{sx}{y}", (sx * (hw + 1.6), y, 0.152), (3.1, 0.02, 0.004), mat("curb", 0.9), bevel=0.0)
        # Buildings: a row of pastel facades with windows, doors, awnings, cornices.
        y = -58.0
        i = 0
        while y < 58:
            w = rnd.uniform(5.5, 8.5)
            h = rnd.uniform(7, 13)
            col = FACADES[(i + (0 if sx > 0 else 3)) % len(FACADES)]
            fr.COL[f"facade{sx}{i}"] = hx(col)
            fx = sx * (hw + 3.2 + 0.5)
            box(f"Bldg{sx}_{i}", (fx + sx * 0.5, y + w / 2, h / 2), (1.0, w - 0.1, h), mat(f"facade{sx}{i}", 0.9), bevel=0.02)
            box(f"Cornice{sx}_{i}", (fx - sx * 0.05, y + w / 2, h - 0.15), (0.25, w - 0.05, 0.3), mat("frame_w", 0.8),
                bevel=0.03)
            for floor in range(1, int(h / 2.8)):
                for wi in range(int(w / 1.6)):
                    wy = y + 0.9 + wi * 1.6
                    if wy > y + w - 0.7:
                        break
                    box(f"Win{sx}_{i}_{floor}_{wi}", (fx - sx * 0.02, wy, 1.3 + floor * 2.8), (0.08, 0.9, 1.4),
                        mat("glass", 0.15, metallic=0.2), bevel=0.02)
                    box(f"Sill{sx}_{i}_{floor}_{wi}", (fx - sx * 0.07, wy, 0.55 + floor * 2.8), (0.12, 1.05, 0.08),
                        mat("frame_w", 0.8), bevel=0.015)
            # Shopfront: big window, door, striped awning.
            box(f"Shop{sx}_{i}", (fx - sx * 0.03, y + w / 2 - 0.6, 1.4), (0.08, w * 0.55, 1.9), mat("glass", 0.15, metallic=0.2),
                bevel=0.02)
            box(f"Door{sx}_{i}", (fx - sx * 0.03, y + w * 0.82, 1.15), (0.1, 1.0, 2.2), mat("pole", 0.6), bevel=0.02)
            for k in range(8):
                ak = f"awning{1 + k % 2}"
                box(f"Awning{sx}_{i}_{k}", (fx - sx * 0.55, y + w / 2 - 0.6 - w * 0.3 + k * w * 0.6 / 8 + w * 0.0375, 2.75),
                    (1.0, w * 0.6 / 8, 0.06), mat(ak, 0.8), bevel=0.005, rot=(0, sx * math.radians(-18), 0))
            y += w
            i += 1
        # Street furniture: lamps and trees every few metres.
        for y in range(-50, 52, 9):
            px = sx * (hw + 0.6)
            tube(f"Lamp{sx}{y}", [(px, y, 0.15), (px, y, 3.8), (px - sx * 0.5, y, 4.2)], [0.06, 0.05, 0.04], mat("pole", 0.5),
                 subdiv=1)
            blob(f"LampHead{sx}{y}", (px - sx * 0.7, y, 4.15), (0.2, 0.12, 0.07), mat("pole", 0.5), subdiv=1)
            blob(f"LampGlow{sx}{y}", (px - sx * 0.7, y, 4.08), (0.14, 0.08, 0.03), mat("lamp", 0.2), subdiv=1)
            ty = y + 4.5
            tube(f"Trunk{sx}{y}", [(px + sx * 0.6, ty, 0.15), (px + sx * 0.6, ty, 2.4)], [0.1, 0.07], mat("trunk", 0.9), subdiv=1)
            for k in range(4):
                blob(f"Leaf{sx}{y}{k}", (px + sx * 0.6 + rnd.uniform(-0.4, 0.4), ty + rnd.uniform(-0.4, 0.4), 2.8 + rnd.uniform(-0.2, 0.5)),
                     [rnd.uniform(0.6, 0.85)] * 3, mat("leaf" if k % 2 else "leaf2", 0.85), subdiv=1)
    # Traffic signal at the crosswalk, pedestrian light green.
    px = hw + 0.4
    tube("SignalPole", [(px, WALK_Y[1] + 0.6, 0.15), (px, WALK_Y[1] + 0.6, 3.4)], [0.07, 0.06], mat("pole", 0.5), subdiv=1)
    box("SignalBox", (px - 0.05, WALK_Y[1] + 0.6, 3.0), (0.25, 0.25, 0.75), mat("pole", 0.5), bevel=0.04)
    for k, c in enumerate(("sign_red", "paint_yellow", "sign_green")):
        blob(f"SignalLamp{k}", (px - 0.05, WALK_Y[1] + 0.47, 3.25 - 0.22 * k), (0.07, 0.03, 0.07),
             emission_mat(c, fr.COL[c], 4.0 if c == "sign_green" else 0.4), subdiv=1)
    box("WalkBox", (px - 0.05, WALK_Y[1] + 0.47, 2.2), (0.2, 0.08, 0.2), mat("pole", 0.5), bevel=0.02)
    blob("WalkMan", (px - 0.05, WALK_Y[1] + 0.42, 2.2), (0.05, 0.01, 0.07), emission_mat("walk", fr.COL["paint"], 3.0),
         subdiv=1)
    # Parked car: a rounded teal hatchback beside the kerb, hiding her until she steps out.
    c = CAR
    box("CarBody", (c.x, c.y, 0.62), (1.75, 4.0, 0.75), mat("car", 0.25, metallic=0.4), bevel=0.25)
    box("CarCabin", (c.x, c.y + 0.25, 1.22), (1.55, 2.2, 0.62), mat("car", 0.25, metallic=0.4), bevel=0.25)
    box("CarGlass", (c.x, c.y + 0.25, 1.25), (1.58, 2.0, 0.48), mat("car_glass", 0.05, metallic=0.3), bevel=0.2)
    for sx in (1, -1):
        for sy in (1, -1):
            w = torus(f"CarTyre{sx}{sy}", (c.x + sx * 0.82, c.y + sy * 1.3, 0.34), 0.25, 0.1, mat("tyre", 0.9), axis="X")
            disc(f"CarHub{sx}{sy}", (c.x + sx * 0.86, c.y + sy * 1.3, 0.34), 0.17, 0.05, mat("metal", 0.3, metallic=0.9),
                 axis="X")
        blob(f"CarLight{sx}", (c.x + sx * 0.6, c.y - 1.98, 0.75), (0.18, 0.04, 0.09), mat("lamp", 0.2), subdiv=1)
    # Hydrant and a bench for scale.
    tube("Hydrant", [(hw + 0.7, -4.0, 0.15), (hw + 0.7, -4.0, 0.75)], [0.12, 0.1], mat("sign_red", 0.5), subdiv=1)
    blob("HydrantCap", (hw + 0.7, -4.0, 0.78), (0.11, 0.11, 0.07), mat("sign_red", 0.5), subdiv=1)
    box("Bench", (-(hw + 1.2), -5.0, 0.5), (0.5, 1.8, 0.08), mat("trunk", 0.8), bevel=0.02)
    box("BenchBack", (-(hw + 1.4), -5.0, 0.85), (0.08, 1.8, 0.5), mat("trunk", 0.8), bevel=0.02)


def golden_hour(scene, pct):
    w = bpy.data.worlds.new("Sky")
    scene.world = w
    if getattr(w, "node_tree", None) is None and hasattr(w, "use_nodes"):
        w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = hx("#b9cde0")
    bg.inputs["Strength"].default_value = 0.9
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy, sun.angle = 3.6, math.radians(1.2)   # small sun disc: crisp, graphic shadows
    sun.color = (1.0, 0.86, 0.68)
    o = fr._link(bpy.data.objects.new("Sun", sun))
    o.rotation_euler = (math.radians(58), 0, math.radians(-125))   # low, warm, raking across the street
    r = scene.render
    engines = [e.identifier for e in r.bl_rna.properties["engine"].enum_items]
    r.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    r.resolution_x, r.resolution_y, r.resolution_percentage = 1920, 1080, pct
    r.fps = FPS
    scene.frame_start, scene.frame_end = 1, LAST
    fr.grade(scene)
    if hasattr(scene, "eevee"):
        for attr, val in (("taa_render_samples", 16), ("use_raytracing", False), ("use_shadows", True)):
            if hasattr(scene.eevee, attr):
                setattr(scene.eevee, attr, val)


# ---------------------------------------------------------------------------
# Motion
# ---------------------------------------------------------------------------

V_RIDE = 4.2                 # m/s cruising
T_BRAKE = (151 - 1) / FPS    # he locks up on the first frame of shot E
SKID_DECEL = 7.0             # m/s^2 (skid + front grab: fast but survivable)
# He must come to rest with the front tyre just short of her: final front
# contact y = 1.14 (her body at y 0.35, a hand's gap), so
# Y_START = 1.64 + V*T_BRAKE + V^2/(2*decel).
STOP_AT = 1.3   # final rider_y: front contact at 0.8, the tyre just short of her shins
Y_START = STOP_AT + 4.2 * ((151 - 1) / 24) + 4.2 ** 2 / (2 * 7.0)


def rider_y(t):
    """His bike's front-contact y over time: cruise, then a hard stop."""
    if t <= T_BRAKE:
        return Y_START - V_RIDE * t
    tb = min(t - T_BRAKE, V_RIDE / SKID_DECEL)
    return Y_START - V_RIDE * T_BRAKE - (V_RIDE * tb - 0.5 * SKID_DECEL * tb * tb)


STOP_Y = rider_y(99.0)       # where he ends up (front wheel at the crosswalk)
T_STOP = T_BRAKE + V_RIDE / SKID_DECEL


def pitch(t):
    """Stoppie: the bike pivots onto its front wheel during the skid, the
    rear rising to ~24 deg at the stop, then drops back with a small bounce."""
    if t < T_BRAKE:
        return 0.0
    u = (t - T_BRAKE) / (T_STOP - T_BRAKE)
    if u <= 1.0:
        return math.radians(34) * (u ** 1.4)          # rear wheel climbs as the front bites
    d = t - T_STOP
    return math.radians(34) * max(0.0, math.cos(min(d / 0.5, 1.0) * math.pi / 2)) + \
        math.radians(3) * math.exp(-d * 4) * math.sin(d * 18) * (d > 0.45)


def crank_angle(t):
    """Fixed gear: the crank turns with the rear wheel (2.6 wheel turns per
    crank turn); when he locks his legs the crank (and rear wheel) stop."""
    dist = Y_START - rider_y(min(t, T_BRAKE))
    return math.degrees(dist / (2 * math.pi * fr.BIKE["wheel_r"]) * 2 * math.pi / 2.6) + 40


# Her: she walks out from behind the car across the crosswalk, stops, looks, walks on.
G_START = Vector((4.3, 0.35, 0.15))   # on the kerb, hidden behind the parked car from his side
V_WALK = 1.15
T_REACH = 6.45                        # she is in his lane as he skids
X_STOP = 1.63
T_STEP_OUT = T_REACH - (G_START.x - X_STOP) / V_WALK


def girl_x(t):
    """Her x along the crosswalk (she walks toward -X)."""
    t_stop = T_REACH              # startled by the skid, she stops in his path
    t_go = 10.4                   # walks on after the moment
    x_stop = X_STOP
    if t < T_STEP_OUT:
        return G_START.x
    if t < t_stop:
        return G_START.x - V_WALK * (t - T_STEP_OUT)
    if t < t_go:
        return x_stop
    return x_stop - V_WALK * (t - t_go)


def girl_walking(t):
    return girl_x(t + 1 / FPS) != girl_x(t)


def foot_cycle(c, stride, lift):
    """One foot over a step cycle c in [0,1): stance (planted, sliding back
    under the body) for 60%, then swing forward with a lift."""
    if c < 0.6:
        u = c / 0.6
        return -stride / 2 + stride * u, 0.0
    u = (c - 0.6) / 0.4
    return stride / 2 - stride * u, lift * math.sin(math.pi * u)


def set_ik_local(rig, bone, local_offset):
    """Move an IK control by an offset in the rig's own space (its rest pose)."""
    pb = rig.pose.bones[bone]
    R = rig.data.bones[bone].matrix_local.to_3x3()
    pb.location = R.inverted() @ Vector(local_offset)


def rot(rig, bone, x=0.0, y=0.0, z=0.0):
    pb = rig.pose.bones[bone]
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = (math.radians(x), math.radians(y), math.radians(z))


# ---------------------------------------------------------------------------
# Face controls: his awe, her glance
# ---------------------------------------------------------------------------

class Face:
    """Animatable facial parts on his head (objects bound to the Head bone).
    Stores each part's base transform so keys are relative."""

    def __init__(self, rig):
        self.rig = rig
        self.base = {}
        for o in bpy.data.objects:
            if o.parent == rig and o.parent_bone == "Head":
                self.base[o.name] = (o.location.copy(), o.scale.copy(), o.rotation_euler.copy())
        hc = Vector((0, -0.01, 1.67))
        size = (0.112, 0.124, 0.15)
        self.extra = {}
        # Hidden until the awe: sparkles in the eyes, blush, an open mouth, hearts.
        spark = emission_mat("sparkle", fr.COL["sparkle"], 6.0)
        for sx in (1, -1):
            bpy.context.view_layer.update()
            iris = bpy.data.objects[f"Iris{sx}"].matrix_world.translation.copy()   # sparkle sits on the iris
            for k, (sx2, sz2) in enumerate(((0.011, 0.0022), (0.0022, 0.011))):
                o = fr.blob(f"Sparkle{sx}{k}", iris + Vector((-sx * 0.003, -0.006, 0.002)), (sx2, 0.002, sz2), spark,
                            subdiv=1)
                fr.bind(o, rig, "Head")
                self.extra[o.name] = o
            o = fr.blob(f"BlushAwe{sx}", fr.head_surface(hc, size, sx * 0.56, -0.18) + Vector((0, -0.004, 0)),
                        (0.026, 0.005, 0.014), fr.mat("blush", 0.6), subdiv=1)
            fr.bind(o, rig, "Head")
            self.extra[o.name] = o
        o = fr.blob("MouthO", fr.head_surface(hc, size, 0.03, -0.53) + Vector((0, -0.002, 0)), (0.017, 0.008, 0.022),
                    fr.mat("mouth", 0.5), subdiv=1)
        fr.bind(o, rig, "Head")
        self.extra[o.name] = o
        for o in self.extra.values():
            self.base[o.name] = (o.location.copy(), o.scale.copy(), o.rotation_euler.copy())

    def key(self, f, eyes=1.0, iris=1.0, awe=0.0, brow=0.0, mouth_open=0.0):
        """eyes: >1 opens the upper lids wider (shock/awe); iris: pupil/iris
        scale; awe 0..1 shows sparkles and blush; brow: lift in metres;
        mouth_open 0..1 swaps the smirk for an 'o'."""
        for name, (loc, sc, rot0) in self.base.items():
            o = bpy.data.objects[name]
            k = 1.0
            o.rotation_euler = rot0.copy()
            if name.startswith("Lid") and not name.startswith("LidLow"):
                o.rotation_euler.x = rot0.x - math.radians(100) * (eyes - 1)  # lid lifts off the eyeball
                o.keyframe_insert("rotation_euler", frame=f)
            elif name.startswith("Eye"):
                k = 1.0
            elif name.startswith(("Iris", "Glint", "Pupil")):
                k = iris
            elif name.startswith(("Sparkle", "BlushAwe")):
                k = max(1e-3, awe)
            elif name == "MouthO":
                k = max(1e-3, mouth_open)
            elif name in ("Smile", "Dimple"):
                k = max(1e-3, 1 - mouth_open)
            if name.startswith(("Iris", "Glint", "Pupil")):
                # Grow in width and height only, so whites never bulge over the irises.
                o.scale = (sc.x * k, sc.y, sc.z * k)
            else:
                o.scale = sc * k
            o.location = loc.copy()
            if name.startswith("Brow"):
                o.location = loc + Vector((0, 0, brow))
            o.keyframe_insert("scale", frame=f)
            o.keyframe_insert("location", frame=f)


# ---------------------------------------------------------------------------
# Acting: expression keys on the story beats (holds, then quick changes)
# ---------------------------------------------------------------------------

STRUCK_AT = int((T_BRAKE + 4.2 / 7.0 + 0.55) * 24) + 1   # just after he stops

ACTING_HIS = [  # (frame, expression, overrides)
    (1, "HAPPY", {}),
    (104, "HAPPY", {}),
    (110, "NOTICE", {"gaze": (0.45, 0.0)}),       # something to his left: her, past the car
    (132, "NOTICE", {"gaze": (0.45, 0.0)}),
    (134, "SHOCK", {}),                            # snaps on the cut to the close-up
    (STRUCK_AT - 3, "SHOCK", {}),
    (STRUCK_AT, "STRUCK", {}),                     # the moment: pupils bloom, sparkles, blush, jaw drops
    (276, "STRUCK", {}),
    (278, "DAZED", {}),
]
ACTING_HERS = [
    (1, "CALM", {}),
    (151, "CALM", {}),
    (154, "STARTLED", {}),                         # the screech
    (190, "STARTLED", {}),
    (196, "AMUSED", {}),                           # she reads the situation, a sidelong smile
    (312, "AMUSED", {}),
]


def act_faces(face, g_face):
    for f, name, over in ACTING_HIS:
        face.key(f, name, **over)
    for f, name, over in ACTING_HERS:
        g_face.key(f, name, **over)


# ---------------------------------------------------------------------------
# Hearts (rise, sway, pop)
# ---------------------------------------------------------------------------

def build_hearts(rig):
    m = emission_mat("heart", fr.COL["heart"], 2.5)
    hearts = []
    for i in range(4):
        root = bpy.data.objects.new(f"Heart{i}", None)
        fr._link(root)
        for sx in (1, -1):
            lobe = fr.blob(f"HeartLobe{i}{sx}", (sx * 0.028, 0, 0.012), (0.034, 0.012, 0.034), m, subdiv=1)
            lobe.parent = root
        tip = fr.blob(f"HeartTip{i}", (0, 0, -0.022), (0.04, 0.012, 0.04), m, subdiv=1, rot=(0, math.radians(45), 0))
        tip.parent = root
        root.scale = (0.001, 0.001, 0.001)
        hearts.append(root)
    return hearts


# ---------------------------------------------------------------------------
# Assembly and per-frame animation
# ---------------------------------------------------------------------------

def shot_of(f):
    for name, a, b in SHOTS:
        if a <= f <= b:
            return name, a, b
    return SHOTS[-1]


def build(pct=40):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    fr.COLL = scene.collection
    golden_hour(scene, pct)
    build_street()

    # Him and his bike, grouped under one root so the whole rig can roll and pitch.
    before = set(bpy.data.objects)
    rig = fr.build_rig("FR_Rig")
    fr.build_character(rig)
    bike = fr.build_bike()
    bike_root = bpy.data.objects.new("BikeRoot", None)
    fr._link(bike_root)
    for o in set(bpy.data.objects) - before:
        if o.parent is None and o is not bike_root:
            o.parent = bike_root
    hearts = build_hearts(rig)

    g_rig, _ = build_girl()
    g_rig.rotation_euler = (0, 0, math.radians(-90))   # faces -X, her walking direction
    bpy.context.view_layer.update()
    face = fr.FaceRig(rig, "")
    g_face = fr.FaceRig(g_rig, "G_")

    animate(scene, rig, bike, bike_root, face, hearts, g_rig)
    act_faces(face, g_face)
    cam = build_camera(scene, rig, g_rig)
    animate_camera(scene, cam, rig, g_rig, bike_root)
    return scene


def animate(scene, rig, bike, bike_root, face, hearts, g_rig):
    B = fr.BIKE
    contact_local = Vector((0, -0.5, 0.0))   # front tyre's contact patch in bike space
    hip_rest = fr.jp("hip")
    seat_local = B["saddle"] + Vector((0, 0.02, 0.07))
    for f in range(1, LAST + 1):
        t = (f - 1) / FPS
        scene.frame_set(f)
        # --- the bike: roll along -Y in the lane, pitch about the front contact in the stoppie
        p = pitch(t)
        R = Matrix.Rotation(p, 4, "X")
        contact_world = Vector((LANE_X, rider_y(t) - 0.5, 0.0))
        bike_root.matrix_world = Matrix.Translation(contact_world - (R @ contact_local)) @ R
        ca = crank_angle(t)
        bike["Crank"].rotation_euler = (math.radians(ca), 0, 0)
        bike["WheelRear"].rotation_euler = (math.radians(ca * 2.6), 0, 0)
        front_turn = (Y_START - rider_y(t)) / B["wheel_r"]
        bike["WheelFront"].rotation_euler = (front_turn, 0, 0)
        for o in (bike_root, bike["Crank"], bike["WheelRear"], bike["WheelFront"]):
            o.keyframe_insert("location", frame=f)
            o.keyframe_insert("rotation_euler", frame=f)
        bpy.context.view_layer.update()
        # --- him: seated, leaning to the bar; in the skid he lurches forward and up
        brake = 0.0 if t < T_BRAKE else min(1.0, (t - T_BRAKE) / (T_STOP - T_BRAKE))
        frozen = t > T_STOP + 0.4
        lurch = brake * (1.0 if not frozen else 0.85)
        # Momentum throws him forward over the bars, toward her face.
        rig.location = seat_local - hip_rest + Vector((0, -0.28 * lurch, 0.12 * lurch))
        bob = 0.0 if t >= T_BRAKE else math.sin(math.radians(ca) * 2) * 2.0
        rot(rig, "Spine", x=48 + 22 * lurch)
        rot(rig, "Neck", x=-24 - 8 * lurch)
        look_up = 0.0 if t < (T_STOP + 0.3) else min(1.0, (t - T_STOP - 0.3) / 0.6)
        rot(rig, "Head", x=-20 + bob - 18 * look_up, z=0)
        for s, sx in (("L", 1), ("R", -1)):
            grip = bike_root.matrix_world @ (B["bar"] + Vector((sx * 0.22, 0.03, 0.02)))
            fr.set_ik(rig, f"IK_Hand_{s}", grip)
            pedal = bike[f"Pedal{sx}"].matrix_world.translation
            fr.set_ik(rig, f"IK_Foot_{s}", pedal + Vector((0, 0, 0.085)))
        for b in ("Spine", "Neck", "Head"):
            rig.pose.bones[b].keyframe_insert("rotation_euler", frame=f)
        for s in "LR":
            rig.pose.bones[f"IK_Hand_{s}"].keyframe_insert("location", frame=f)
            rig.pose.bones[f"IK_Foot_{s}"].keyframe_insert("location", frame=f)
        rig.keyframe_insert("location", frame=f)
        # --- her: walk cycle with planted feet, stop, look, smile, walk on
        gx = girl_x(t)
        walking = girl_walking(t)
        cyc_dist = G_START.x - gx
        stride = 0.72
        c = (cyc_dist / (2 * stride / 0.6 * 0.6)) % 1.0 if walking else 0.0
        g_rig.location = (gx, G_START.y, 0.15 if gx > (ROAD_W / 2) else 0.0)
        g_rig.location.z += (-0.02 * math.cos(4 * math.pi * c)) if walking else 0.0
        for s, off in (("L", 0.0), ("R", 0.5)):
            if walking:
                fy, fz = foot_cycle((c + off) % 1.0, stride, 0.09)
            else:
                fy, fz = (0.0 if s == "L" else 0.0), 0.0
            set_ik_local(g_rig, f"IK_Foot_{s}", (0, fy, fz))
            g_rig.pose.bones[f"IK_Foot_{s}"].keyframe_insert("location", frame=f)
        swing = 14 * math.sin(2 * math.pi * c) if walking else 0.0
        # Arms: hands relaxed at the sides, swinging against the legs.
        for s, sgn in (("L", 1), ("R", -1)):
            wri = fr.jp(f"wri_{s}")
            set_ik_local(g_rig, f"IK_Hand_{s}", (0, -0.12 * math.sin(math.radians(swing * sgn)), 0.01))
            g_rig.pose.bones[f"IK_Hand_{s}"].keyframe_insert("location", frame=f)
            _ = wri
        # Her look: startled turn toward him (+Y) at the skid, a smile, then on her way.
        turn = 0.0
        if 6.2 < t < 10.6:
            turn = min(1.0, (t - 6.2) / 0.3) * (1 - max(0.0, min(1.0, (t - 10.2) / 0.4)))
        # Twist about the bones' own (vertical) axis: negative turns her to her right, toward him.
        rot(g_rig, "Head", y=-12 * turn, x=-6 * turn)   # the body does the turning now; a slight head tilt down to him
        rot(g_rig, "Spine", y=0)
        for b in ("Head", "Spine"):
            g_rig.pose.bones[b].keyframe_insert("rotation_euler", frame=f)
        face_him = min(1.0, max(0.0, (t - 6.3) / 0.35)) * (1 - min(1.0, max(0.0, (t - 10.05) / 0.35)))
        g_rig.rotation_euler = (0, 0, math.radians(-90 - 80 * face_him))   # turns to her right, toward him
        g_rig.keyframe_insert("location", frame=f)
        g_rig.keyframe_insert("rotation_euler", frame=f)
    sf = lambda sec: int(sec * FPS) + 1
    # --- hearts rise from above his head after the moment
    head = rig.pose.bones["Head"]
    for i, h in enumerate(hearts):
        t0 = T_STOP + 0.8 + i * 0.6
        for k in range(0, 60, 2):
            f = sf(t0) + k
            if f > LAST:
                break
            u = k / 60
            scene.frame_set(f)
            base = rig.matrix_world @ head.tail
            h.location = base + Vector((0.12 * math.sin(u * 7 + i) + (i - 1.5) * 0.08, -0.05, 0.12 + 0.55 * u))
            sc = min(1.0, k / 8) * (1 - max(0.0, (u - 0.8) / 0.2)) * (1.1 + 0.15 * math.sin(k * 0.8))
            h.scale = (max(sc, 1e-3),) * 3
            h.rotation_euler = (0, 0.25 * math.sin(u * 6 + i), 0)
            h.keyframe_insert("location", frame=f)
            h.keyframe_insert("scale", frame=f)
            h.keyframe_insert("rotation_euler", frame=f)
        h.scale = (1e-3,) * 3
        h.keyframe_insert("scale", frame=max(1, sf(t0) - 1))


# ---------------------------------------------------------------------------
# Cameras (layout): one per shot, cuts on action
# ---------------------------------------------------------------------------

def build_camera(scene, rig, g_rig):
    d = bpy.data.cameras.new("Cam")
    cam = fr._link(bpy.data.objects.new("Cam", d))
    scene.camera = cam
    d.dof.use_dof = True
    d.dof.aperture_fstop = 2.8
    d.clip_end = 250
    return cam


def animate_camera(scene, cam, rig, g_rig, bike_root):
    for f in range(1, LAST + 1):
        t = (f - 1) / FPS
        scene.frame_set(f)
        name, a, b = shot_of(f)
        u = (f - a) / max(1, b - a)
        hb = rig.pose.bones["Head"]
        his_head = rig.matrix_world @ hb.head.lerp(hb.tail, 0.45)        # his face, not the top of his cap
        his_chest = rig.matrix_world @ rig.pose.bones["Spine"].tail
        gb = g_rig.pose.bones["Head"]
        her_head = g_rig.matrix_world @ gb.head.lerp(gb.tail, 0.45)
        bike = bike_root.matrix_world.translation
        if name == "WIDE":       # low on the left kerb, looking up the street; he rides toward us
            loc = Vector((-2.4, 9.0 - 2.0 * u, 0.6))
            tgt = his_chest.lerp(Vector((LANE_X, 14, 1.4)), 0.25)
            lens, focus = 35, (his_chest - loc).length
        elif name == "TRACK":    # alongside him, matching his speed, 3/4 front
            loc = Vector((LANE_X - 2.4, bike.y - 1.9, 1.15))
            tgt = his_chest + Vector((0, -0.2, -0.1))
            lens, focus = 45, (his_chest - loc).length
        elif name == "REVEAL":   # his POV, long lens over the bar: she steps out past the car
            loc = Vector((LANE_X - 0.35, bike.y - 0.4, 1.95))   # over his shoulder, above the car roof
            tgt = her_head + Vector((0.1, 0, -0.35))
            lens, focus = 70, (her_head - loc).length
        elif name == "CLOSE":    # his face, push in
            loc = his_head + Vector((-0.4 + 0.08 * u, -1.15 + 0.25 * u, 0.02))
            tgt = his_head
            lens, focus = 60, (his_head - loc).length
        elif name == "SKID":     # side wide, everything in frame: bike, him, her
            mid = (bike + Vector((G_START.x * 0, 0, 0))).lerp(Vector((LANE_X, 0.4, 0.9)), 0.5)
            loc = Vector((-5.6, mid.y - 0.6, 1.2))
            tgt = Vector((LANE_X, mid.y, 0.95))
            lens, focus = 35, (tgt - loc).length
        elif name == "AWE":      # two-shot profile, slow push-in to their faces
            mid = his_head.lerp(her_head, 0.5)
            loc = mid + Vector((-3.2 + 1.2 * u * u * (3 - 2 * u), -0.25, -0.05))
            tgt = mid + Vector((0, 0, -0.08))
            lens, focus = 45, (mid - loc).length
        else:                    # DAZED: close on him; she has walked away
            loc = his_head + Vector((-0.6, -1.1, 0.08))
            tgt = his_head + Vector((0, 0, 0.12))   # headroom for the hearts
            lens, focus = 50, (his_head - loc).length
        cam.location = loc
        cam.rotation_euler = (Vector(tgt) - loc).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        cam.data.dof.focus_distance = focus
        cam.data.dof.aperture_fstop = 1.8 if name in ("AWE", "DAZED", "CLOSE") else 3.5
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
        cam.data.keyframe_insert("lens", frame=f)
        cam.data.dof.keyframe_insert("focus_distance", frame=f)
        cam.data.dof.keyframe_insert("aperture_fstop", frame=f)
    for idb in (cam, cam.data):
        for fc in fr_fcurves(idb):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


def fr_fcurves(id_data):
    ad = id_data.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "layers") and getattr(ad, "action_slot", None) is not None:
        from bpy_extras.anim_utils import action_get_channelbag_for_slot
        bag = action_get_channelbag_for_slot(act, ad.action_slot)
        return list(bag.fcurves) if bag else []
    return list(act.fcurves)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="renders/crosswalk")
    ap.add_argument("--stills", default="")
    ap.add_argument("--frames", default="")
    ap.add_argument("--pct", type=int, default=40)
    ap.add_argument("--save", default="")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    scene = build(a.pct)
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save))
    if a.stills:
        for f in [int(x) for x in a.stills.split(",")]:
            scene.frame_set(f)
            scene.render.filepath = os.path.join(a.out, f"still_{f:03d}.png")
            bpy.ops.render.render(write_still=True)
            print("rendered", scene.render.filepath, flush=True)
        return
    lo, hi = (int(x) for x in a.frames.split("-")) if a.frames else (1, LAST)
    os.makedirs(os.path.join(a.out, "frames"), exist_ok=True)
    for f in range(lo, hi + 1):
        scene.frame_set(f)
        scene.render.filepath = os.path.join(a.out, "frames", f"f{f:03d}.png")
        bpy.ops.render.render(write_still=True)
        print("rendered", f, flush=True)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
