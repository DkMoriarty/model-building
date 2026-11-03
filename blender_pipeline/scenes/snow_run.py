"""SNOW RUN: CH_Snowboarder rides a mountain in five shots (original staging).

    blender -b -P blender_pipeline/scenes/snow_run.py -- --out renders/snow_run [--stills 20,90,170,235,300] [--pct 50]
    # without --stills it renders every frame to <out>/frames/, then:
    python3 blender_pipeline/scenes/snow_run_audio.py --out renders/snow_run   # jazz loop + sfx, muxed to MP4

Shots (24 fps, 336 frames = 14 s)
  1  LEDGE    1-48    pops off a snowy rock ledge into a pink dusk sky, grab
  2  CARVE    49-132  carves down a steep slope past pines, spray and shadow
  3  RAIL     133-204 low and close: boardslides a wooden rail, sparks fly
  4  SUNSET   205-264 backflip against a sunset glow, warm backlight
  5  LAND     265-336 squash landing, burst of snow, rides off with a smirk

Every motion is computed per frame from the shot's path (ballistic arcs with
one gravity, constant-angle slopes), and the spray particles, shadows and
camera read the same numbers, so the board, the snow and the camera agree.
"""

import argparse
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "characters"))
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import snowboarder as sb  # noqa: E402
import toonkit as tk  # noqa: E402

FPS = 24
G = 6.0                  # stylised gravity (units/s^2): floaty, like the reference's hang time
SHOTS = [("LEDGE", 1, 48), ("CARVE", 49, 132), ("RAIL", 133, 204), ("SUNSET", 205, 264), ("LAND", 265, 336)]
SET_X = {"LEDGE": 0.0, "CARVE": 100.0, "RAIL": 200.0, "SUNSET": 300.0, "LAND": 400.0}
hx = sb.hx

PAL = {
    "dusk_top": hx("#9d86a3"), "dusk_bot": hx("#d8a9a8"),
    "eve_top": hx("#7f86ad"), "eve_bot": hx("#c3b4c6"),
    "sun_core": hx("#ffe0c2"), "sun_mid": hx("#f0a99c"), "sun_edge": hx("#a87f9a"),
    "snow": hx("#f3eee9"), "snow_shade": hx("#b9b9d6"), "snow_deep": hx("#8e92bd"),
    "pine": hx("#2f4350"), "pine_far": hx("#6c7b93"),
    "rock": hx("#3d4150"), "rock_light": hx("#5b6175"),
    "wood": hx("#5a3b2a"), "wood_light": hx("#8a5d3e"), "steel": hx("#d9dbe3"),
    "spark": hx("#ffc070"), "spray": hx("#ffffff"), "spray_shade": hx("#c9cbe6"),
    "board": hx("#2b2830"), "board_top": hx("#e9e4ec"),
    "warm": hx("#ff9070"),
}


def shot_at(f):
    for name, a, b in SHOTS:
        if a <= f <= b:
            return name, (f - a) / FPS, (b - a) / FPS
    return SHOTS[-1][0], 0.0, 0.0


# ---------------------------------------------------------------------------
# Materials and shapes for the sets
# ---------------------------------------------------------------------------

def gradient_material(name, stops, radial=False):
    """Unlit sky: a colour ramp across the plane (vertical, or radial glow)."""
    m = bpy.data.materials.new(name)
    if getattr(m, "node_tree", None) is None and hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    grad = nt.nodes.new("ShaderNodeTexGradient")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    em = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if radial:
        # Generated coords run 0..1 across the plane; centre them for a glow.
        grad.gradient_type = "SPHERICAL"
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Location"].default_value = (-1.0, 0.0, -1.0)
        mp.inputs["Scale"].default_value = (2.0, 1.0, 2.0)
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], sep.inputs[0])
        nt.links.new(sep.outputs["X"], comb.inputs["X"])
        nt.links.new(sep.outputs["Z"], comb.inputs["Y"])
        nt.links.new(comb.outputs[0], grad.inputs["Vector"])
    else:
        # Vertical ramp: feed the plane's Generated Z (0 bottom .. 1 top) as X.
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(tc.outputs["Generated"], sep.inputs[0])
        nt.links.new(sep.outputs["Z"], comb.inputs["X"])
        nt.links.new(comb.outputs[0], grad.inputs["Vector"])
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = stops[0]
    els[1].position, els[1].color = stops[-1]
    for pos, col in stops[1:-1]:
        e = els.new(pos)
        e.color = col
    nt.links.new(grad.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def poly_mesh(name, pts_xz, y, mat, coll):
    """A flat polygon (x, z) at depth y with an unlit material."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, y, z) for x, z in pts_xz], [], [list(range(len(pts_xz)))])
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def sky_plane(name, cx, cz, w, h, mat, coll, y=60.0):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(cx - w / 2, y, cz - h / 2), (cx + w / 2, y, cz - h / 2), (cx + w / 2, y, cz + h / 2),
                    (cx - w / 2, y, cz + h / 2)], [], [(0, 1, 2, 3)])
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    # Generated coords span the bounding box, so the ramp fills the plane.
    return ob


def gp_shape(ob, layer, pts, fill, name, width=0.02, line=True, frame=1, y=0.0):
    """A filled, inked GP shape in world units (x, z)."""
    m = tk.gp_material(f"SR_{name}", stroke=sb.COL["ink"] if line else None, fill=fill)
    st = tk.draw_stroke(ob, layer, frame, [(x, y, z) for x, z in pts], radius=width / 2, material=m, cyclic=True)
    prof = sb.line_profile([(x, -z) for x, z in pts], True, seed=len(pts))
    for p, r in zip(st.points, prof):
        p.radius = width / 2 * r
    return st


def pine(ob, layer, x, z, h, col, name):
    """A stylised pine: a trunk and three jagged tiers, tip pinched."""
    w = h * 0.42
    tiers = []
    for k, (zb, ww) in enumerate(((0.18, 1.0), (0.45, 0.78), (0.7, 0.52))):
        zt = zb + (0.55 if k < 2 else 0.42)
        tiers.append([(x - w * ww, z + h * zb), (x - w * ww * 0.35, z + h * (zb + 0.04)), (x, z + h * min(zt, 1.0)),
                      (x + w * ww * 0.35, z + h * (zb + 0.04)), (x + w * ww, z + h * zb)])
    gp_shape(ob, layer, [(x - h * 0.03, z), (x + h * 0.03, z), (x + h * 0.03, z + h * 0.25), (x - h * 0.03, z + h * 0.25)],
             col, name, width=0.012, line=False)
    for t in tiers:
        gp_shape(ob, layer, t, col, name, width=0.012, line=False)


# ---------------------------------------------------------------------------
# The five sets
# ---------------------------------------------------------------------------

CARVE_ANGLE = math.radians(26)   # slope pitch in shot 2
LAND_ANGLE = math.radians(15)    # gentler run-out in shot 5
RAIL_ANGLE = math.radians(6)


def slope_z(x0, z0, ang, x):
    return z0 - math.tan(ang) * (x - x0)


def build_sets(coll):
    flat = tk.flat_material
    rnd = random.Random(7)
    env = tk.new_gp_object("SET_GP", coll)
    env.location.y = 8.0
    for layer in ("far", "mid", "near"):
        tk.gp_layer(env, layer)

    # 1 LEDGE: dusk sky, rock ledge with a snow cap bottom-left, distant pine tips.
    X = SET_X["LEDGE"]
    sky_plane("Sky_Ledge", X, 1.0, 40, 24, gradient_material("Sky_Dusk", [(0.0, PAL["dusk_bot"]), (1.0, PAL["dusk_top"])]),
              coll)
    rock = [(X - 9, -4), (X - 9, -1.2), (X - 6.5, -0.8), (X - 4.6, -0.45), (X - 3.4, -0.6), (X - 3.0, -1.6), (X - 3.4, -4)]
    gp_shape(env, "near", rock, PAL["rock"], "Rock", width=0.05)
    gp_shape(env, "near", [(X - 9, -1.05), (X - 6.4, -0.55), (X - 4.6, -0.18), (X - 3.25, -0.32), (X - 3.5, -0.62),
                           (X - 4.7, -0.5), (X - 6.5, -0.85), (X - 9, -1.25)], PAL["snow"], "SnowCap", width=0.04)
    gp_shape(env, "near", [(X - 4.4, -0.75), (X - 3.4, -0.68), (X - 3.15, -1.5), (X - 3.9, -1.2)], PAL["rock_light"],
             "RockLight", line=False)
    for i in range(7):
        pine(env, "far", X + 1 + i * 1.3 + rnd.uniform(-0.3, 0.3), -3.4, rnd.uniform(0.8, 1.3), PAL["pine_far"], "PineFar")

    # 2 CARVE and 5 LAND: long slopes, a ridge of pines behind, shadow bands.
    for key, ang, top, bot in (("CARVE", CARVE_ANGLE, PAL["eve_top"], PAL["dusk_bot"]),
                               ("LAND", LAND_ANGLE, PAL["eve_top"], PAL["eve_bot"])):
        X = SET_X[key]
        sky_plane(f"Sky_{key}", X, 0, 60, 40, gradient_material(f"Sky_{key}", [(0.0, bot), (1.0, top)]), coll)
        z_at = lambda x, X=X, ang=ang: slope_z(X, 0.0, ang, x)
        xs = [X - 16 + i * 0.5 for i in range(65)]
        snow = [(x, z_at(x)) for x in xs] + [(X + 16, z_at(X + 16) - 12), (X - 16, z_at(X + 16) - 12)]
        poly_mesh(f"Snow_{key}", snow, 0.6, flat(f"Snow_{key}", PAL["snow"]), coll)
        # Broad cel-shadow bands across the snow (from trees and drifts).
        for k, (x0, w) in enumerate(((X - 9, 3.0), (X + 1.5, 4.0), (X + 9, 3.0))):
            band = [(x0, z_at(x0) - 0.08), (x0 + w, z_at(x0 + w) - 0.08), (x0 + w + 2.5, z_at(x0 + w) - 2.2),
                    (x0 + 2.0, z_at(x0) - 2.6)]
            poly_mesh(f"Band_{key}_{k}", band, 0.55, flat(f"BandMat_{key}", (*PAL["snow_shade"][:3], 0.55)), coll)
        # A ridge behind, carrying pines, and far hills.
        ridge = [(x, z_at(x) + 2.6 + 0.3 * math.sin(x * 0.7)) for x in xs] + [(X + 16, -20), (X - 16, -20)]
        poly_mesh(f"Ridge_{key}", ridge, 4.0, flat(f"Ridge_{key}", hx("#dcd6e2")), coll)
        for i in range(16):
            x = X - 14 + i * 1.8 + rnd.uniform(-0.5, 0.5)
            pine(env, "mid", x, z_at(x) + 2.45 + 0.3 * math.sin(x * 0.7), rnd.uniform(1.4, 2.4), PAL["pine"], "Pine")

    # 3 RAIL: evening sky, far snowy hill with pines, a wooden box rail.
    X = SET_X["RAIL"]
    sky_plane("Sky_Rail", X, 0, 40, 24, gradient_material("Sky_Eve", [(0.0, PAL["eve_bot"]), (1.0, PAL["eve_top"])]), coll)
    hill = [(X - 12 + i * 0.5, -0.6 + 0.5 * math.sin(i * 0.23)) for i in range(49)] + [(X + 12, -8), (X - 12, -8)]
    poly_mesh("Hill_Rail", hill, 6.0, flat("Hill_Rail", hx("#e4dce4")), coll)
    for i in range(10):
        x = X - 10 + i * 2.2 + rnd.uniform(-0.4, 0.4)
        pine(env, "far", x, -0.55 + 0.5 * math.sin((x - X + 12) * 2 * 0.23), rnd.uniform(1.0, 1.8), PAL["pine_far"], "PineFar")
    rz = lambda x: rail_top(x)
    top = [(x, rz(x)) for x in (X - 12, X + 12)]
    box = [(X - 12, rz(X - 12)), (X + 12, rz(X + 12)), (X + 12, rz(X + 12) - 1.1), (X - 12, rz(X - 12) - 1.1)]
    gp_shape(env, "near", box, PAL["wood"], "Wood", width=0.05)
    for k in range(1, 6):
        gp_shape(env, "near", [(X - 12, rz(X - 12) - 0.2 * k), (X + 12, rz(X + 12) - 0.2 * k),
                               (X + 12, rz(X + 12) - 0.2 * k - 0.02), (X - 12, rz(X - 12) - 0.2 * k - 0.02)],
                 PAL["wood_light"], "WoodGrain", line=False)
    gp_shape(env, "near", [top[0], top[1], (top[1][0], top[1][1] - 0.07), (top[0][0], top[0][1] - 0.07)], PAL["steel"],
             "Steel", width=0.03)
    poly_mesh("Snow_Rail", [(X - 12, -1.9), (X + 12, -2.6), (X + 12, -9), (X - 12, -9)], 1.0, flat("Snow_RailM", PAL["snow"]),
              coll)

    # 4 SUNSET: radial glow, soft pink hills.
    X = SET_X["SUNSET"]
    glow = sky_plane("Sky_Sun", X, 1.2, 28, 28, gradient_material(
        "Sky_Sun", [(0.0, PAL["sun_edge"]), (0.55, PAL["sun_mid"]), (1.0, PAL["sun_core"])], radial=True), coll)
    hills = [(X - 12 + i * 0.5, -1.75 + 0.3 * math.sin(i * 0.31)) for i in range(49)] + [(X + 12, -9), (X - 12, -9)]
    poly_mesh("Hill_Sun", hills, 5.0, flat("Hill_Sun", hx("#d9a7ad")), coll)
    tk.light_layers(env, False)  # flat colours (set after the layers exist)
    return env


def rail_top(x):
    X = SET_X["RAIL"]
    return -1.0 - math.tan(RAIL_ANGLE) * (x - X)


# ---------------------------------------------------------------------------
# The ride: position, rotation and pose per frame
# ---------------------------------------------------------------------------

def ride_state(f):
    """Return dict: x, z (board contact point), rot (picture-plane tilt, +cw),
    pose params, tail (board tail world point), on_snow, slope angle."""
    shot, t, T = shot_at(f)
    X = SET_X[shot]
    st = dict(shot=shot, t=t, crouch=0.35, lift=0.0, board_tilt=0.0, arms=0.6, grab=0.0, lean=0.0, head=0.0,
              on_snow=False, slope=0.0, speed=0.0, spin=0.0, contact="")
    if shot == "LEDGE":
        vx, vz = 3.4, 4.6
        st.update(x=X - 3.6 + vx * t, z=-0.35 + vz * t - 0.5 * G * t * t)
        st["rot"] = math.radians(-12 + 20 * t)
        st["crouch"] = 0.7
        st["lift"] = 0.35 * min(1, t / 0.3)          # knees tucked
        st["board_tilt"] = math.radians(-30 - 10 * math.sin(t * 2))
        st["grab"] = min(1.0, t / 0.35)
        st["arms"] = 0.9
        st["head"] = math.radians(8)
        st["speed"] = math.hypot(vx, vz - G * t)
        if t < 0.12:
            st["contact"] = "takeoff"
    elif shot in ("CARVE", "LAND"):
        ang = CARVE_ANGLE if shot == "CARVE" else LAND_ANGLE
        if shot == "LAND" and t < 0.55:              # still in the air, dropping in from the left
            tl = t
            x = X - 4.2 + 3.2 * tl
            z_ground = slope_z(X, 0.0, ang, x)
            fall = 0.5 * G * (0.55 ** 2 - (0.55 - tl) ** 2) if False else None
            z = z_ground + 2.2 * (1 - tl / 0.55) ** 2       # parabola meeting the slope at t=0.55
            st.update(x=x, z=z, rot=ang * 0.6, crouch=0.5, lift=0.25 * (1 - tl / 0.55), arms=1.0, on_snow=False)
            st["board_tilt"] = math.radians(10 * (1 - tl / 0.55))
            st["speed"] = 5.0
        else:
            t0 = 0.55 if shot == "LAND" else 0.0
            u = t - t0
            v = 3.2 + (1.6 * u if shot == "CARVE" else -0.4 * u)
            x0 = X - 4.2 + 3.2 * 0.55 if shot == "LAND" else X - 6.0
            x = x0 + v * u * math.cos(ang) * 0.9
            st.update(x=x, z=slope_z(X, 0.0, ang, x), rot=ang, on_snow=True, slope=ang, speed=v)
            carve = math.sin(u * 3.2)
            st["crouch"] = 0.45 + 0.15 * carve
            st["arms"] = 0.55 + 0.2 * carve
            st["lean"] = math.radians(-0.45 * math.degrees(ang) + 6 * carve)
            if shot == "LAND":
                land = max(0.0, 1 - u / 0.35)             # squash on touchdown, then recover
                st["crouch"] = 0.45 + 0.5 * land
                st["contact"] = "land" if u < 0.1 else ""
    elif shot == "RAIL":
        x = X - 5.5 + 3.0 * t
        st.update(x=x, z=rail_top(x), rot=RAIL_ANGLE, crouch=0.4 + 0.1 * math.sin(t * 9), arms=0.85,
                  lean=math.radians(-4 + 5 * math.sin(t * 4.5)), speed=3.0, contact="rail")
        st["board_tilt"] = math.radians(1.5 * math.sin(t * 13))  # chatter on the rail
    elif shot == "SUNSET":
        vx, vz = 1.0, 7.2
        st.update(x=X - 1.2 + vx * t, z=-4.2 + vz * t - 0.5 * G * t * t)
        st["rot"] = -2 * math.pi * _ease(min(1.0, max(0.0, (t - 0.35) / 1.4)))   # one full backflip
        st["crouch"] = 0.8
        st["lift"] = 0.4
        st["grab"] = 1.0
        st["board_tilt"] = math.radians(-70)
        st["arms"] = 1.0
        st["speed"] = math.hypot(vx, vz - G * t)
    return st


def _ease(u):
    return u * u * (3 - 2 * u)


# Picture-plane rotation as a pose basis (no depsgraph updates needed).
_REST = {}


def _rest(rig, bone):
    if bone not in _REST:
        _REST[bone] = rig.data.bones[bone].matrix_local.to_3x3()
    return _REST[bone]


def set_swing(rig, bone, angle):
    """Rotate `bone` by `angle` in the picture plane (+ = tip forward/+X)."""
    R = _rest(rig, bone)
    rot = Matrix.Rotation(-angle, 3, "Y")
    pb = rig.pose.bones[bone]
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = (R.inverted() @ rot @ R).to_quaternion()


def set_offset(rig, bone, delta):
    """Move `bone` by an armature-space delta (x, z) from rest."""
    R = _rest(rig, bone)
    rig.pose.bones[bone].location = R.inverted() @ Vector((delta[0], 0.0, delta[1]))


POSE_BONES = ("Torso", "Board", "Head", "Ponytail", "Arm_Upper_R", "Arm_Lower_R", "Arm_Upper_L", "Arm_Lower_L",
              "Hand_R", "Hand_L", "IK_Target_R", "IK_Target_L")


def apply_state(rig, st, prev):
    c, a, g = st["crouch"], st["arms"], st["grab"]
    set_offset(rig, "Torso", (0.0, -0.22 * c))
    set_swing(rig, "Torso", st["lean"])
    set_offset(rig, "Board", (0.0, 0.32 * st["lift"]))
    set_swing(rig, "Board", st["board_tilt"])
    set_offset(rig, "IK_Target_R", (-0.06, 0.0))           # a slightly wider riding stance
    set_offset(rig, "IK_Target_L", (0.06, 0.0))
    # Arms out for balance; on a grab the near hand reaches down to the board.
    set_swing(rig, "Arm_Upper_R", math.radians(-(25 + 55 * a) * (1 - g) + 20 * g))
    set_swing(rig, "Arm_Lower_R", math.radians(-25 * (1 - g) + 35 * g))
    set_swing(rig, "Arm_Upper_L", math.radians(25 + 60 * a))
    set_swing(rig, "Arm_Lower_L", math.radians(30))
    set_swing(rig, "Head", st["head"] - 0.4 * st["lean"])
    # Ponytail streams opposite the motion (follow-through from speed).
    swing = -0.25 - 0.08 * st["speed"] if prev is None else -0.25 - 0.08 * st["speed"] + 0.3 * (st["z"] - prev["z"]) * FPS * 0.05
    set_swing(rig, "Ponytail", max(-1.1, swing))
    rig.location = (st["x"], 0.0, st["z"])
    rig.rotation_euler = (0.0, st["rot"], 0.0)


def key_all(rig, f):
    for b in POSE_BONES:
        pb = rig.pose.bones[b]
        pb.keyframe_insert("location", frame=f)
        pb.keyframe_insert("rotation_quaternion", frame=f)
    rig.keyframe_insert("location", frame=f)
    rig.keyframe_insert("rotation_euler", frame=f)


# ---------------------------------------------------------------------------
# Snow spray, sparks and shadows (one GP drawing per frame)
# ---------------------------------------------------------------------------

def board_points(st):
    """World tail/centre/nose of the board for state st."""
    c, s = math.cos(st["rot"]), math.sin(st["rot"])
    def w(dx, dz):
        return (st["x"] + dx * c + dz * s, st["z"] - dx * s + dz * c)
    lift = 0.32 * st["lift"]
    return w(-0.55, lift), w(0.0, lift), w(0.55, lift)


def build_fx(coll, states):
    fx = tk.new_gp_object("FX", coll)
    fx.location.y = -0.5
    tk.gp_layer(fx, "Shadow")
    tk.gp_layer(fx, "Particles")
    tk.light_layers(fx, False)
    m_spray = tk.gp_material("FX_Spray", fill=PAL["spray"])
    m_spray_s = tk.gp_material("FX_SprayShade", fill=PAL["spray_shade"])
    m_spark = tk.gp_material("FX_Spark", fill=PAL["spark"])
    m_shadow = tk.gp_material("FX_Shadow", fill=(*PAL["snow_deep"][:3], 0.55))
    rnd = random.Random(42)
    parts = []
    last = SHOTS[-1][2]
    for f in range(1, last + 1):
        st = states[f]
        shot = st["shot"]
        if f > 1 and states[f - 1]["shot"] != shot:
            parts = []                                     # a cut clears the air
        tail, mid, nose = board_points(st)
        dt = 1 / FPS
        # Emit
        if st["on_snow"]:
            ang = st["slope"]
            for _ in range(5):
                sp = rnd.uniform(1.0, 2.6)
                th = math.pi - ang + rnd.uniform(0.35, 1.0)      # back and up from the tail
                parts.append([tail[0], tail[1] + 0.02, sp * math.cos(th), sp * math.sin(th), rnd.uniform(0.35, 0.7),
                              rnd.uniform(0.025, 0.06), rnd.random() < 0.3, "snow"])
        if st["contact"] in ("takeoff", "land"):
            for _ in range(28):
                th = rnd.uniform(0.2, math.pi - 0.2)
                sp = rnd.uniform(1.0, 3.5)
                parts.append([mid[0] + rnd.uniform(-0.4, 0.4), mid[1], sp * math.cos(th), sp * math.sin(th),
                              rnd.uniform(0.4, 0.9), rnd.uniform(0.03, 0.08), rnd.random() < 0.4, "snow"])
        if st["contact"] == "rail":
            for _ in range(4):
                th = math.pi + rnd.uniform(0.1, 0.9)
                sp = rnd.uniform(1.5, 3.5)
                parts.append([mid[0] + rnd.uniform(-0.3, 0.3), mid[1] - 0.02, -abs(sp * math.cos(th)), -sp * math.sin(th) * 0.6,
                              rnd.uniform(0.15, 0.35), rnd.uniform(0.012, 0.022), False, "spark"])
        # Step and draw
        alive = []
        for p in parts:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] -= (G * 0.6 if p[7] == "snow" else G) * dt
            p[2] *= 0.96
            p[4] -= dt
            if p[4] > 0:
                alive.append(p)
        parts = alive
        frame = tk.gp_frame(fx.data.layers["Particles"], f)
        for p in parts:
            r = p[5] * (0.5 + 0.5 * min(1.0, p[4] / 0.3))
            mat = m_spark if p[7] == "spark" else (m_spray_s if p[6] else m_spray)
            tk.draw_stroke(fx, "Particles", f, [(p[0] + r * math.cos(k * 0.785), 0, p[1] + r * math.sin(k * 0.785))
                                                for k in range(8)], radius=0.001, material=mat, cyclic=True)
        sframe = tk.gp_frame(fx.data.layers["Shadow"], f)
        if st["on_snow"]:
            # Long evening shadow cast down-slope (light from up-left).
            ang = st["slope"]
            L, Wd = 1.6, 0.16
            ux, uz = math.cos(-ang), math.sin(-ang)
            cx, cz = mid[0] + 0.55 * ux, mid[1] + 0.55 * uz - 0.03
            pts = [(cx + L / 2 * math.cos(k * math.pi / 8) * ux - Wd * math.sin(k * math.pi / 8) * uz * 0.4,
                    cz + L / 2 * math.cos(k * math.pi / 8) * uz + Wd * math.sin(k * math.pi / 8) * 0.25 - 0.05)
                   for k in range(16)]
            tk.draw_stroke(fx, "Shadow", f, [(x, 0.3, z) for x, z in pts], radius=0.001, material=m_shadow, cyclic=True)
        _ = frame, sframe
    return fx


# ---------------------------------------------------------------------------
# Board prop, camera, warm overlay, expressions
# ---------------------------------------------------------------------------

def build_ride_board(rig, coll):
    ob = tk.new_gp_object("Ride_Board", coll)
    tk.gp_layer(ob, "Board")
    tk.light_layers(ob, False)
    L, T = 0.62, 0.035
    base = [(-L, 0.05), (-L + 0.06, 0.0), (L - 0.06, 0.0), (L, 0.05), (L + 0.01, 0.075), (L - 0.07, 0.03 + T),
            (-L + 0.07, 0.03 + T), (-L - 0.01, 0.075)]
    m = tk.gp_material("SR_Board", stroke=sb.COL["ink"], fill=PAL["board"])
    st = tk.draw_stroke(ob, "Board", 1, [(x, 0, z - 0.035) for x, z in base], radius=0.008, material=m, cyclic=True)
    for p, r in zip(st.points, sb.line_profile([(x, -z) for x, z in base], True)):
        p.radius = 0.008 * r
    top = tk.gp_material("SR_BoardTop", fill=PAL["board_top"])
    tk.draw_stroke(ob, "Board", 1, [(-L + 0.08, 0, 0.0), (L - 0.08, 0, 0.0), (L - 0.09, 0, -0.012), (-L + 0.09, 0, -0.012)],
                   radius=0.001, material=top, cyclic=True)
    # Ride on the Board bone; the bone head sits at the boot soles.
    target = rig.matrix_world @ Matrix.Translation(rig.data.bones["Board"].head_local)
    ob.parent, ob.parent_type, ob.parent_bone = rig, "BONE", "Board"
    bpy.context.view_layer.update()
    ob.matrix_world = target
    ob.location.y += -0.02
    return ob


CAM = {  # shot: (ortho scale, offset of the rider in frame, follow lag)
    "LEDGE": (10.0, (0.0, 1.0), None),
    "CARVE": (8.0, (1.2, 0.3), 0.15),
    "RAIL": (5.5, (0.4, 0.9), 0.1),
    "SUNSET": (7.0, (0.0, 0.0), None),
    "LAND": (8.5, (1.0, 0.4), 0.12),
}


def animate_camera(cam, states):
    pos = None
    for f in sorted(states):
        st = states[f]
        shot = st["shot"]
        scale, (ox, oz), lag = CAM[shot]
        X = SET_X[shot]
        if lag is None:  # locked-off shot
            target = (X + ox, oz)
            pos = target
        else:
            target = (st["x"] + ox, st["z"] + oz)
            if pos is None or (f > 1 and states[f - 1]["shot"] != shot):
                pos = target
            k = 1 - math.exp(-1 / (lag * FPS))
            pos = (pos[0] + (target[0] - pos[0]) * k, pos[1] + (target[1] - pos[1]) * k)
        shake = 0.0
        if st["contact"] == "land":
            shake = 0.06
        cam.location = (pos[0] + random.uniform(-shake, shake), -30.0, pos[1] + random.uniform(-shake, shake))
        cam.data.ortho_scale = scale
        cam.keyframe_insert("location", frame=f)
        cam.data.keyframe_insert("ortho_scale", frame=f)
    for idb in (cam, cam.data):
        for fc in tk.fcurves(idb):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


def warm_overlay(cam, coll):
    """Sunset backlight: a warm wash in front of everything, only in shot 4."""
    me = bpy.data.meshes.new("Warm")
    me.from_pydata([(-20, 0, -12), (20, 0, -12), (20, 0, 12), (-20, 0, 12)], [], [(0, 1, 2, 3)])
    me.materials.append(tk.flat_material("WarmWash", (*PAL["warm"][:3], 0.28)))
    ob = bpy.data.objects.new("Warm_Overlay", me)
    coll.objects.link(ob)
    ob.parent = cam
    ob.location = (0, 0, -5)  # in front of the camera (camera looks down its -Z)
    ob.rotation_euler = (math.radians(-90), 0, 0)
    for name, a, b in SHOTS:
        ob.hide_render = name != "SUNSET"
        ob.keyframe_insert("hide_render", frame=a)
    return ob


def sunset_tint(obs):
    """Backlit by the sunset: a warm tint on her drawings, only in shot 4
    (Grease Pencil draws over transparent meshes, so it is tinted directly)."""
    for ob in obs:
        m = ob.modifiers.new("Sunset Tint", "GREASE_PENCIL_TINT")
        m.color = PAL["warm"][:3]
        for name, a, b in SHOTS:
            m.factor = 0.3 if name == "SUNSET" else 0.0
            ob.keyframe_insert(f'modifiers["{m.name}"].factor', frame=a)
        for fc in tk.fcurves(ob):
            if "Sunset Tint" in fc.data_path:
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"


def act(art, rig):
    """Her face and puffer through the run."""
    for f, eyes, mouth in ((1, "HAPPY", "A_I"), (49, "GLARE", "REST"), (133, "SIDE", "SMIRK"), (205, "HAPPY", "A_I"),
                           (265, "SQUINT", "GRIT"), (290, "GLARE", "REST"), (318, "SIDE", "SMIRK")):
        sb.express(art, f, eyes=eyes, mouth=mouth)
    for name, lat in sb.LATTICES.items():
        lag = 0 if name == "Jacket" else 2
        for f, puff, squash in ((1, 0.8, -0.3), (49, 0.3, 0.2), (133, 0.2, 0.3), (205, 1.0, -0.4), (265, 0.0, 1.0),
                                (275, 0.6, -0.2), (290, 0.3, 0.2)):
            tk.key_puff(lat, f + lag, puff=puff, squash=squash)


# ---------------------------------------------------------------------------

def build(pct=50):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    tk.setup_project(s, 1920, 1080, FPS, SHOTS[-1][2])
    engines = [e.identifier for e in s.render.bl_rna.properties["engine"].enum_items]
    s.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    s.render.resolution_percentage = pct
    s.view_settings.view_transform = "Standard"
    s.world = bpy.data.worlds.new("W")
    coll = s.collection
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = "ORTHO"
    cam_data.clip_end = 200
    cam = bpy.data.objects.new("Cam", cam_data)
    coll.objects.link(cam)
    cam.rotation_euler = (math.radians(90), 0, 0)
    s.camera = cam

    build_sets(coll)
    rig, art, board = sb.build(with_board=False)
    ride_board = build_ride_board(rig, coll)
    states = {f: ride_state(f) for f in range(1, SHOTS[-1][2] + 1)}
    prev = None
    for f in range(1, SHOTS[-1][2] + 1):
        apply_state(rig, states[f], prev)
        key_all(rig, f)
        prev = states[f]
    for idb in (rig,):
        for fc in tk.fcurves(idb):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    act(art, rig)
    sunset_tint([art, ride_board])
    build_fx(coll, states)
    animate_camera(cam, states)
    return s, rig, art, states


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="renders/snow_run")
    ap.add_argument("--stills", default="")
    ap.add_argument("--pct", type=int, default=50)
    ap.add_argument("--frames", default="", help="A-B range to render (default: all)")
    ap.add_argument("--save", default="")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    s, rig, art, states = build(a.pct)
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save))
    if a.stills:
        frames = [int(x) for x in a.stills.split(",")]
        for f in frames:
            s.frame_set(f)
            s.render.filepath = os.path.join(a.out, f"still_{f:03d}.png")
            bpy.ops.render.render(write_still=True)
            print("rendered", s.render.filepath)
        return
    lo, hi = (int(x) for x in a.frames.split("-")) if a.frames else (1, SHOTS[-1][2])
    os.makedirs(os.path.join(a.out, "frames"), exist_ok=True)
    for f in range(lo, hi + 1):
        s.frame_set(f)
        s.render.filepath = os.path.join(a.out, "frames", f"f{f:03d}.png")
        bpy.ops.render.render(write_still=True)
        print("rendered", f, flush=True)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
