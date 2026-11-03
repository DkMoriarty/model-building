"""Toon City-style 2D pipeline helpers for Blender 4.3+ (Grease Pencil v3).

Tested against Blender 5.0.1 (the `bpy` module). Each section belongs to one
department agent in `.claude/agents/`; `docs/BLENDER_GUIDE.md` explains every
step and where the manual (UI) workflow differs.

Use inside Blender (Scripting tab, or `blender -b file.blend -P script.py`):

    import sys; sys.path.append('/path/to/blender_pipeline')
    import toonkit as tk
    tk.setup_project(fps=24)

Coordinate convention: the camera looks along +Y, so 2D art lives in the XZ
plane; depth (multiplane) is Y. Characters are authored facing +X.
"""

from __future__ import annotations

import math
import os
from typing import Iterable, Sequence

import bpy
from mathutils import Vector

# ---------------------------------------------------------------------------
# Production setup and output        (production-coordinator, render-delivery)
# ---------------------------------------------------------------------------

STUDIO_TREE = (
    "01_Assets/Characters",
    "01_Assets/Backgrounds",
    "01_Assets/Props",
    "02_Production/Episode_01/Audio",
    "02_Production/Episode_01/Shots",
    "02_Production/Episode_01/Renders",
)


def make_studio_tree(root: str, episodes: int = 1) -> list[str]:
    """Create the standard folder hierarchy; returns the created paths."""
    made = []
    for rel in STUDIO_TREE:
        for ep in range(1, episodes + 1):
            path = os.path.join(root, rel.replace("Episode_01", f"Episode_{ep:02d}"))
            os.makedirs(path, exist_ok=True)
            if path not in made:
                made.append(path)
    return made


def setup_project(scene=None, width=1920, height=1080, fps=24, frame_end=None):
    """Resolution, frame rate and real-time playback (Frame Dropping)."""
    s = scene or bpy.context.scene
    r = s.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = width, height, 100
    r.fps, r.fps_base = fps, 1.0
    s.frame_start = 1
    if frame_end:
        s.frame_end = frame_end
    s.sync_mode = "FRAME_DROP"
    return s


def set_output(scene, mode: str, path: str):
    """Output presets.

    preview: MPEG-4 / H.264 / AAC, high quality - reviews and web.
    phone:   as preview, but 1280 wide, AAC 44.1 kHz stereo - plays everywhere.
    final:   PNG RGBA image sequence - lossless, crash-safe, keeps alpha.
    exr:     multilayer OpenEXR - every pass for external compositing.
    """
    r = scene.render
    img = r.image_settings
    r.filepath = path
    if mode in ("preview", "phone"):
        if hasattr(img, "media_type"):  # Blender 5.0+
            img.media_type = "VIDEO"
        img.file_format = "FFMPEG"
        r.ffmpeg.format = "MPEG4"
        r.ffmpeg.codec = "H264"
        r.ffmpeg.constant_rate_factor = "HIGH"
        r.ffmpeg.audio_codec = "AAC"
        r.ffmpeg.audio_channels = "STEREO"
        if mode == "phone":
            r.ffmpeg.audio_mixrate = 44100
            r.resolution_percentage = round(100 * 1280 / r.resolution_x)
        else:
            r.resolution_percentage = 100
    elif mode == "final":
        if hasattr(img, "media_type"):
            img.media_type = "IMAGE"
        img.file_format = "PNG"
        img.color_mode = "RGBA"
        r.resolution_percentage = 100
    elif mode == "exr":
        if hasattr(img, "media_type"):
            img.media_type = "MULTI_LAYER_IMAGE"
        img.file_format = "OPEN_EXR_MULTILAYER"
        r.resolution_percentage = 100
    else:
        raise ValueError(f"unknown output mode {mode!r}")
    return r


def draft_viewport(scene=None, on: bool = True):
    """Fast animating: Simplify on, no GP anti-aliasing, heavy modifiers and
    effects hidden in the viewport (renders are unaffected)."""
    s = scene or bpy.context.scene
    r = s.render
    r.use_simplify = on
    r.simplify_subdivision = 0 if on else 6
    r.simplify_gpencil = on
    r.simplify_gpencil_antialiasing = not on
    for ob in s.objects:
        for m in ob.modifiers:
            if m.type in ("LINEART", "SUBSURF"):
                m.show_viewport = not on
        for fx in getattr(ob, "shader_effects", []):
            fx.show_viewport = not on
    return s


# ---------------------------------------------------------------------------
# Palette materials                          (background-artist, rigger)
# ---------------------------------------------------------------------------

PALETTE = {
    "ink": (0.03, 0.03, 0.04, 1.0),
    "hero_red": (0.80, 0.07, 0.10, 1.0),     # #e63946 (linear-ish)
    "ally_green": (0.05, 0.72, 0.31, 1.0),   # #3ddc97
    "payoff_gold": (1.0, 0.64, 0.13, 1.0),   # #ffd166
    "skin": (0.95, 0.80, 0.66, 1.0),
    "shadow": (0.02, 0.02, 0.06, 0.45),
}


def gp_material(name, stroke=None, fill=None):
    """A Grease Pencil material: stroke and/or fill, reusable across files.
    Change the material once and every line drawn with it updates."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if mat.grease_pencil is None:
        bpy.data.materials.create_gpencil_data(mat)
    g = mat.grease_pencil
    g.show_stroke = stroke is not None
    g.show_fill = fill is not None
    if stroke is not None:
        g.color = stroke
    if fill is not None:
        g.fill_color = fill
    return mat


def flat_material(name, color):
    """An unlit 'painted' surface material for background cards and shadows:
    emission in the given colour, mixed with transparency by its alpha."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = color  # viewport (Solid mode) colour
    if getattr(mat, "node_tree", None) is None and hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color[:3], 1.0)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = color[3]
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def ensure_material(ob, mat) -> int:
    """Add `mat` to the object's slots once; return its slot index."""
    for i, slot in enumerate(ob.data.materials):
        if slot == mat:
            return i
    ob.data.materials.append(mat)
    return len(ob.data.materials) - 1


# ---------------------------------------------------------------------------
# Grease Pencil drawing helpers
# ---------------------------------------------------------------------------

def new_gp_object(name, collection=None):
    data = bpy.data.grease_pencils.new(name)
    ob = bpy.data.objects.new(name, data)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def gp_layer(ob, name):
    return ob.data.layers.get(name) or ob.data.layers.new(name)


def gp_frame(layer, frame: int):
    for f in layer.frames:
        if f.frame_number == frame:
            return f
    return layer.frames.new(frame)


def draw_stroke(ob, layer: str, frame: int, points: Sequence, radius=0.02, material=None, cyclic=False):
    """Append one stroke (points in XZ: (x, z) or full (x, y, z))."""
    drawing = gp_frame(gp_layer(ob, layer), frame).drawing
    drawing.add_strokes([len(points)])
    stroke = drawing.strokes[len(drawing.strokes) - 1]
    for p, pt in zip(stroke.points, points):
        p.position = Vector((pt[0], 0.0, pt[1])) if len(pt) == 2 else Vector(pt)
        p.radius = radius
    stroke.cyclic = cyclic
    if material is not None:
        stroke.material_index = ensure_material(ob, material)
    return stroke


def circle_points(cx, cz, r, n=24):
    return [(cx + r * math.cos(2 * math.pi * i / n), cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


# ---------------------------------------------------------------------------
# Rigging                                              (character-rigger)
# ---------------------------------------------------------------------------

# Head-unit proportions (H = head diameter), from alan_pipeline figureSpec BIPED.
BIPED_H = {"head": 1.0, "neck": 0.12, "torso": 1.40, "upper_arm": 1.05,
           "forearm": 1.05, "hand": 0.35, "thigh": 1.15, "shin": 1.15}

DEFORM_BONES = ("Torso", "Neck", "Head",
                "Arm_Upper_L", "Arm_Lower_L", "Hand_L",
                "Arm_Upper_R", "Arm_Lower_R", "Hand_R",
                "Leg_Upper_L", "Leg_Lower_L", "Leg_Upper_R", "Leg_Lower_R")


def _edit(arm_ob):
    bpy.context.view_layer.objects.active = arm_ob
    for ob in bpy.context.view_layer.objects:
        ob.select_set(ob == arm_ob)
    bpy.ops.object.mode_set(mode="EDIT")
    return arm_ob.data.edit_bones


def _object_mode():
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def build_biped_armature(name="CH_Hero_Rig", H=0.5, collection=None):
    """A side-view biped skeleton in head units. Hip height = thigh + shin.

    Root (ground) -> Torso (hips up) -> Neck -> Head; shoulders hang from the
    torso top; legs hang from the hips. Elbows and knees carry a slight
    forward bend so IK always folds them the right way.
    """
    p = {k: v * H for k, v in BIPED_H.items()}
    arm_data = bpy.data.armatures.new(name)
    arm_ob = bpy.data.objects.new(name, arm_data)
    (collection or bpy.context.scene.collection).objects.link(arm_ob)
    arm_ob.show_in_front = True  # bones stay visible over drawings
    eb = _edit(arm_ob)

    def bone(n, head, tail, parent=None, deform=True, connect=False):
        b = eb.new(n)
        b.head, b.tail = Vector(head), Vector(tail)
        if parent:
            b.parent = eb[parent]
            b.use_connect = connect
        b.use_deform = deform
        return b

    hip_z = p["thigh"] + p["shin"]
    top = hip_z + p["torso"]
    bone("Root", (0, 0, 0), (0, 0, 0.3 * H), deform=False)
    bone("Torso", (0, 0, hip_z), (0, 0, top), "Root")
    bone("Neck", (0, 0, top), (0, 0, top + p["neck"]), "Torso", connect=True)
    bone("Head", (0, 0, top + p["neck"]), (0, 0, top + p["neck"] + p["head"]), "Neck", connect=True)
    for s, dx in (("L", 0.02 * H), ("R", -0.02 * H)):
        elbow = (0.08 * H + dx, 0, top - p["upper_arm"])
        wrist = (0.16 * H + dx, 0, top - p["upper_arm"] - p["forearm"])
        bone(f"Arm_Upper_{s}", (dx, 0, top), elbow, "Torso")
        bone(f"Arm_Lower_{s}", elbow, wrist, f"Arm_Upper_{s}", connect=True)
        bone(f"Hand_{s}", wrist, (wrist[0] + 0.05 * H, 0, wrist[2] - p["hand"]), f"Arm_Lower_{s}", connect=True)
        knee = (0.10 * H + dx, 0, p["shin"])
        bone(f"Leg_Upper_{s}", (dx, 0, hip_z), knee, "Torso")
        bone(f"Leg_Lower_{s}", knee, (dx, 0, 0), f"Leg_Upper_{s}", connect=True)
    _object_mode()
    return arm_ob


def build_armature_from_joints(name, bones, collection=None):
    """Build a skeleton from traced joints.

    bones: [(name, head, tail, parent_or_None, deform, connect)], where head
    and tail are (x, z) in the picture plane. Use this for designed characters
    traced from a model sheet; bone names follow `build_biped_armature`
    (Root, Torso, Leg_Upper_L ...) so IK, walk and binding helpers work."""
    arm_data = bpy.data.armatures.new(name)
    arm_ob = bpy.data.objects.new(name, arm_data)
    (collection or bpy.context.scene.collection).objects.link(arm_ob)
    arm_ob.show_in_front = True
    eb = _edit(arm_ob)
    for n, head, tail, parent, deform, connect in bones:
        b = eb.new(n)
        b.head, b.tail = Vector((head[0], 0, head[1])), Vector((tail[0], 0, tail[1]))
        if parent:
            b.parent = eb[parent]
            b.use_connect = connect
        b.use_deform = deform
    _object_mode()
    return arm_ob


def add_leg_ik(arm_ob, side="L", pole_distance=None, auto_pole=True, pole_dir=1):
    """IK for one leg: an unparented foot target at the ankle, a pole target in
    front of the knee, and an IK constraint (chain 2) on the shin. The pole
    angle is solved automatically so the rest pose does not move."""
    shin, thigh = f"Leg_Lower_{side}", f"Leg_Upper_{side}"
    eb = _edit(arm_ob)
    ankle, knee = eb[shin].tail.copy(), eb[shin].head.copy()
    leg_len = eb[thigh].length + eb[shin].length
    t_name, pole_name = f"IK_Target_{side}", f"Pole_Target_{side}"
    t = eb.new(t_name)
    t.head, t.tail = ankle, ankle + Vector((-0.25 * leg_len, 0, 0))  # lies back along the floor
    t.parent, t.use_deform = eb["Root"], False  # follows the character, not the leg
    pole = eb.new(pole_name)
    d = pole_distance or 0.6 * leg_len
    pole.head = knee + Vector((pole_dir * d, 0, 0))  # profile: in front of the knee; front view: outside it
    pole.tail = pole.head + Vector((pole_dir * 0.1 * leg_len, 0, 0))
    pole.parent, pole.use_deform = eb["Root"], False
    _object_mode()

    c = arm_ob.pose.bones[shin].constraints.new("IK")
    c.name = "Leg IK"
    # Use the saved names: edit bones are invalid once we leave Edit Mode.
    c.target, c.subtarget = arm_ob, t_name
    c.pole_target, c.pole_subtarget = arm_ob, pole_name
    c.chain_count = 2  # shin + thigh only; the torso is untouched
    if auto_pole:
        c.pole_angle = solve_pole_angle(arm_ob, shin)
    return c


def _bone_world_heads(arm_ob, names):
    bpy.context.view_layer.update()
    return {n: (arm_ob.matrix_world @ arm_ob.pose.bones[n].head).copy() for n in names}


def solve_pole_angle(arm_ob, bone_name, step_deg=1.0):
    """Find the pole angle at which the IK chain keeps its rest pose (the
    walkthrough's 'try 90, -90 or 180'), by measuring instead of guessing."""
    pb = arm_ob.pose.bones[bone_name]
    c = next(c for c in pb.constraints if c.type == "IK")
    chain = [pb.name] + [p.name for p in pb.parent_recursive[: c.chain_count - 1]]
    rest = {n: (arm_ob.matrix_world @ arm_ob.data.bones[n].tail_local) for n in chain}

    def err(a):
        c.pole_angle = a
        bpy.context.view_layer.update()
        return sum(((arm_ob.matrix_world @ arm_ob.pose.bones[n].tail) - rest[n]).length for n in chain)

    best = min((math.radians(d) for d in range(-180, 180, 15)), key=err)
    span = math.radians(15)
    step = math.radians(step_deg)
    a = best - span
    while a <= best + span:
        if err(a) < err(best):
            best = a
        a += step
    c.pole_angle = best
    bpy.context.view_layer.update()
    return best


def bind_layers_to_bones(gp_ob, arm_ob, mapping: dict[str, str] | None = None):
    """Cut-out binding: every point on a layer is weighted 1.0 to the bone of
    the same name (the 'paint it red' weight-paint step, done exactly).
    Adds the Armature modifier and parents the drawing to the rig."""
    mapping = mapping or {l.name: l.name for l in gp_ob.data.layers if l.name in arm_ob.data.bones}
    for layer_name, bone in mapping.items():
        if bone not in gp_ob.vertex_groups:
            gp_ob.vertex_groups.new(name=bone)
        for frame in gp_ob.data.layers[layer_name].frames:
            d = frame.drawing
            n = sum(len(s.points) for s in d.strokes)
            if n:
                d.set_vertex_weights(bone, list(range(n)), [1.0] * n)
    mod = gp_ob.modifiers.get("Rig") or gp_ob.modifiers.new("Rig", "GREASE_PENCIL_ARMATURE")
    mod.object = arm_ob
    gp_ob.parent = arm_ob
    return mod


def draw_stick_character(arm_ob, name="CH_Hero_Art", color=PALETTE["hero_red"], H=0.5):
    """Draw a stick figure along the rig's bones, one layer per bone, with an
    open-ring head. Lines overlap at the joints (round caps), so bends never gap."""
    gp_ob = new_gp_object(name, arm_ob.users_collection[0])
    line = gp_material(f"{name}_Line", stroke=color)
    r = 0.07 * H  # stroke ~0.14 H
    for b in arm_ob.data.bones:
        if b.name not in DEFORM_BONES or b.name == "Head":
            continue
        h, t = b.head_local, b.tail_local
        draw_stroke(gp_ob, b.name, 1, [(h.x, h.y, h.z), (t.x, t.y, t.z)], radius=r, material=line)
    hb = arm_ob.data.bones["Head"]
    c = (hb.head_local + hb.tail_local) / 2
    draw_stroke(gp_ob, "Head", 1, circle_points(c.x, c.z, 0.5 * H - r), radius=r, material=line, cyclic=True)
    bind_layers_to_bones(gp_ob, arm_ob)
    return gp_ob


# ---------------------------------------------------------------------------
# Lip sync                                             (lipsync-animator)
# ---------------------------------------------------------------------------

VISEMES = ("A_I", "E", "O", "U", "MBP", "LDT", "WQ", "FV", "REST")  # library frames 1..9

# Rhubarb Lip Sync shapes -> our library (https://github.com/DanielSWolf/rhubarb-lip-sync)
RHUBARB_TO_VISEME = {"A": "MBP", "B": "E", "C": "E", "D": "A_I", "E": "O",
                     "F": "WQ", "G": "FV", "H": "LDT", "X": "REST"}


def setup_mouth_library(gp_ob, layer="Mouth", draw_placeholders=True, center=(0.0, 0.0), size=0.1):
    """Mouth swap library: one drawing per viseme on frames 1-9 of `layer`, and
    a Time Offset modifier in Fixed Frame mode limited to that layer, so the
    mouth only changes when you key the modifier's frame."""
    L = gp_layer(gp_ob, layer)
    ink = gp_material("Mouth_Ink", stroke=PALETTE["ink"])
    cx, cz = center
    w = size
    shapes = {  # simple placeholder art; artists redraw these in Draw mode
        "A_I": circle_points(cx, cz, w * 0.5, 16),
        "E": [(cx - w * .6, cz), (cx - w * .3, cz - w * .25), (cx + w * .3, cz - w * .25), (cx + w * .6, cz), (cx, cz + w * .1)],
        "O": circle_points(cx, cz, w * 0.35, 16),
        "U": circle_points(cx, cz, w * 0.18, 12),
        "MBP": [(cx - w * .5, cz), (cx + w * .5, cz)],
        "LDT": [(cx - w * .5, cz), (cx, cz - w * .4), (cx + w * .5, cz), (cx, cz + w * .15)],
        "WQ": circle_points(cx, cz, w * 0.12, 10),
        "FV": [(cx - w * .5, cz), (cx + w * .5, cz), (cx + w * .3, cz - w * .15), (cx - w * .3, cz - w * .15)],
        "REST": [(cx - w * .35, cz), (cx, cz - w * .06), (cx + w * .35, cz)],
    }
    for i, v in enumerate(VISEMES, start=1):
        f = gp_frame(L, i)
        if draw_placeholders and len(f.drawing.strokes) == 0:
            closed = v in ("A_I", "O", "U", "WQ", "E", "LDT", "FV")
            draw_stroke(gp_ob, layer, i, shapes[v], radius=0.012, material=ink, cyclic=closed)
    mod = gp_ob.modifiers.get("Mouth Swap") or gp_ob.modifiers.new("Mouth Swap", "GREASE_PENCIL_TIME")
    mod.mode = "FIX"
    mod.tree_node_filter = layer
    mod.offset = VISEMES.index("REST") + 1
    return mod


def key_visemes(gp_ob, cues: Iterable[tuple[float, str]], fps=24, lead_frames=1, modifier="Mouth Swap"):
    """Key the mouth library from (seconds, viseme) cues. Shapes land
    `lead_frames` early so the eye reads them on the sound. Constant
    interpolation: mouths swap, they never tween."""
    mod = gp_ob.modifiers[modifier]
    path = f'modifiers["{modifier}"].offset'
    frames = []
    for t, v in cues:
        frame = max(1, round(t * fps) + 1 - lead_frames)
        mod.offset = VISEMES.index(v) + 1
        gp_ob.keyframe_insert(path, frame=frame)
        frames.append(frame)
    for fc in fcurves(gp_ob):
        if fc.data_path == path:
            for k in fc.keyframe_points:
                k.interpolation = "CONSTANT"
    return frames


def rhubarb_cues(data: dict) -> list[tuple[float, str]]:
    """Convert Rhubarb JSON output (`rhubarb -f json voice.wav`) to cues."""
    return [(c["start"], RHUBARB_TO_VISEME[c["value"]]) for c in data["mouthCues"]]


# ---------------------------------------------------------------------------
# Animation helpers                       (key-animator, in-between/clean-up)
# ---------------------------------------------------------------------------

def fcurves(id_data):
    """All F-curves of an ID, for both legacy and slotted (4.4+) actions."""
    ad = id_data.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "layers") and getattr(ad, "action_slot", None) is not None:
        from bpy_extras.anim_utils import action_get_channelbag_for_slot
        bag = action_get_channelbag_for_slot(act, ad.action_slot)
        return list(bag.fcurves) if bag else []
    return list(act.fcurves)


def set_interpolation(id_data, mode="BEZIER", easing="AUTO", data_path_prefix=""):
    for fc in fcurves(id_data):
        if fc.data_path.startswith(data_path_prefix):
            for k in fc.keyframe_points:
                k.interpolation = mode
                k.easing = easing


def offset_bone(arm_ob, bone, delta):
    """Move a pose bone by `delta` in armature space (X forward, Z up),
    whatever its roll or rest orientation, and return its local location."""
    pb = arm_ob.pose.bones[bone]
    pb.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    m = pb.matrix.copy()
    m.translation = m.translation + Vector(delta)
    pb.matrix = m
    bpy.context.view_layer.update()
    return pb.location.copy()


def key_offsets(arm_ob, frame, offsets: dict):
    """Key bones at armature-space offsets from their rest positions."""
    for bone, delta in offsets.items():
        offset_bone(arm_ob, bone, delta)
        arm_ob.pose.bones[bone].keyframe_insert("location", frame=frame)


def rotate_bone_2d(arm_ob, bone, angle):
    """Swing a bone in the picture plane by `angle` radians (positive = its
    tip moves forward, toward +X), whatever its roll."""
    from mathutils import Matrix
    pb = arm_ob.pose.bones[bone]
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    m = pb.matrix.copy()
    head = m.translation.copy()
    pb.matrix = Matrix.Translation(head) @ Matrix.Rotation(-angle, 4, "Y") @ Matrix.Translation(-head) @ m
    bpy.context.view_layer.update()


def key_swings(arm_ob, frame, swings: dict):
    """Key picture-plane rotations: {bone: radians, positive = forward}."""
    for bone, a in swings.items():
        rotate_bone_2d(arm_ob, bone, a)
        arm_ob.pose.bones[bone].keyframe_insert("rotation_euler", frame=frame)


def key_pose(arm_ob, frame, pose: dict):
    """pose = {bone: {"loc": (x,y,z), "rot": radians_about_Y}}.

    Rotation is about the bone's local axis that faces the camera (Y), the
    only axis a 2D side-view rig needs."""
    for name, v in pose.items():
        pb = arm_ob.pose.bones[name]
        if "loc" in v:
            pb.location = Vector(v["loc"])
            pb.keyframe_insert("location", frame=frame)
        if "rot" in v:
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = (0.0, v["rot"], 0.0)
            pb.keyframe_insert("rotation_euler", frame=frame)


def walk_cycle(arm_ob, start=1, length=24, stride=None, bob=None, H=0.5):
    """The 4-pose stride (contact, down, passing, up, opposite contact) driven
    through the IK foot targets and the torso, as a loop of `length` frames.

    Feet stay planted because IK places them; the torso dips on the down and
    rises on the up; arms swing opposite to the legs."""
    stride = stride or 1.2 * H
    bob = bob or 0.12 * H
    q = length // 4
    lift = 0.35 * H
    # (foot L x, foot L lift, foot R x, foot R lift, torso dz, arm swing)
    keys = [
        (start,         ( stride / 2, 0.0, -stride / 2, 0.0, 0.0, 0.5)),   # contact: L forward
        (start + q,     ( stride / 4, 0.0, -stride / 4, lift, -bob, 0.3)),  # down: weight on L
        (start + 2 * q, ( 0.0,        0.0,  0.0,        lift, 0.0, 0.0)),   # passing
        (start + 3 * q, (-stride / 4, 0.0,  stride / 4, lift * .5, bob, -0.3)),  # up
        (start + length, (-stride / 2, 0.0, stride / 2, 0.0, 0.0, -0.5)),   # contact: R forward
    ]
    for frame, (lx, ll, rx, rl, dz, arm) in keys:
        key_offsets(arm_ob, frame, {
            "IK_Target_L": (lx, 0, ll),
            "IK_Target_R": (rx, 0, rl),
            "Torso": (0, 0, dz),
        })
        key_swings(arm_ob, frame, {"Arm_Upper_L": -arm, "Arm_Upper_R": arm})  # arms oppose legs
    return [k[0] for k in keys]


def walk_front(arm_ob, start=1, length=24, lift=None, bob=None, H=0.5, swing_deg=10.0,
               follow=("Ponytail",), follow_deg=8.0, follow_lag=2):
    """Walk in place for a character drawn from the front (toward camera):
    each foot lifts in turn (knees bend outward through the IK poles), the
    torso dips on each contact and rises on each pass, the arms swing a
    little against the legs, and `follow` bones (hair, tails) trail the
    bounce by `follow_lag` frames: overlapping action."""
    lift = lift or 0.45 * H
    bob = bob or 0.08 * H
    h = length // 2
    q = h // 2
    # frame offset: (R foot lift, L foot lift, torso dz, arm swing sign)
    beats = [
        (0, 0.0, 0.0, -bob, 0.0),            # contact, weight drops
        (q // 2, lift * 0.6, 0.0, 0.0, 1.0),  # R foot rising
        (q, lift, 0.0, bob, 1.0),            # R passing: highest
        (q + q // 2, lift * 0.5, 0.0, 0.0, 0.5),
        (h, 0.0, 0.0, -bob, 0.0),            # contact
        (h + q // 2, 0.0, lift * 0.6, 0.0, -1.0),
        (h + q, 0.0, lift, bob, -1.0),
        (h + q + q // 2, 0.0, lift * 0.5, 0.0, -0.5),
        (length, 0.0, 0.0, -bob, 0.0),
    ]
    frames = []
    for off, r_up, l_up, dz, arm in beats:
        f = start + off
        key_offsets(arm_ob, f, {"IK_Target_R": (0, 0, r_up), "IK_Target_L": (0, 0, l_up), "Torso": (0, 0, dz)})
        a = math.radians(swing_deg) * arm
        key_swings(arm_ob, f, {"Arm_Upper_R": a, "Arm_Upper_L": a, "Head": -0.25 * a})
        frames.append(f)
    for bone in follow:
        if bone not in arm_ob.pose.bones:
            continue
        for off, *_, in beats:
            dz = next(b[3] for b in beats if b[0] == off)
            key_swings(arm_ob, start + off + follow_lag, {bone: math.radians(follow_deg) * (dz / bob if bob else 0)})
    return frames


# ---------------------------------------------------------------------------
# Layout, multiplane and camera                         (layout-artist)
# ---------------------------------------------------------------------------

MULTIPLANE = (("BG_Far", 40.0), ("BG_Mid", 15.0), ("Characters", 0.0), ("FG_Overlay", -5.0))


def setup_camera(scene=None, distance=12.0, height=1.2, lens=50.0, name="Cam_Main"):
    s = scene or bpy.context.scene
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam = bpy.data.objects.new(name, cam_data)
    s.collection.objects.link(cam)
    cam.location = (0.0, -distance, height)
    cam.rotation_euler = (math.radians(90), 0.0, 0.0)  # look along +Y
    s.camera = cam
    return cam


def view_size_at(cam, scene, depth_y):
    """Width and height (Blender units) the camera sees at world Y = depth_y."""
    d = depth_y - cam.location.y
    r = scene.render
    aspect = r.resolution_x / r.resolution_y
    w = d * cam.data.sensor_width / cam.data.lens
    return w, w / aspect


def build_multiplane(scene, cam, layers=MULTIPLANE, margin=0.15, colors=None):
    """One collection per depth layer, each with a backing plane scaled to fill
    the frame at its depth plus `margin` (headroom for pans and shake)."""
    out = {}
    colors = colors or {}
    for name, y in layers:
        coll = bpy.data.collections.get(name) or bpy.data.collections.new(name)
        if coll.name not in scene.collection.children:
            scene.collection.children.link(coll)
        out[name] = coll
        if name == "Characters":
            continue
        w, h = view_size_at(cam, scene, y)
        mesh = bpy.data.meshes.new(f"{name}_Plane")
        sx, sz = w * (1 + margin) / 2, h * (1 + margin) / 2
        if name == "FG_Overlay":  # a framing pillar at the left, not a full card
            verts = [(-sx, y, -sz), (-sx * 0.7, y, -sz), (-sx * 0.7, y, sz), (-sx, y, sz)]
        else:
            verts = [(-sx, y, -sz), (sx, y, -sz), (sx, y, sz), (-sx, y, sz)]
        mesh.from_pydata([Vector(v) + Vector((cam.location.x, 0, cam.location.z)) for v in verts], [], [(0, 1, 2, 3)])
        ob = bpy.data.objects.new(f"{name}_Card", mesh)
        coll.objects.link(ob)
        mesh.materials.append(flat_material(f"{name}_Paint", colors.get(name, (0.1, 0.1, 0.12, 1))))
    return out


def add_painting(path, collection, depth_y, height):
    """Import a painted background as a plane (built-in since Blender 4.2:
    Add > Image > Mesh Plane) and place it at a depth."""
    before = set(bpy.data.objects)
    d, f = os.path.split(path)
    bpy.ops.image.import_as_mesh_planes(files=[{"name": f}], directory=d, align_axis="-Y")
    ob = next(o for o in bpy.data.objects if o not in before)
    for c in ob.users_collection:
        c.objects.unlink(ob)
    collection.objects.link(ob)
    ob.location.y = depth_y
    ob.scale *= height / ob.dimensions.z
    return ob


def depth_of_field(cam, focus_object=None, fstop=2.8):
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = focus_object
    cam.data.dof.aperture_fstop = fstop


def camera_move(cam, f0, f1, loc1, loc0=None, ease="EASE", lens1=None):
    """Key a move from f0 to f1. ease: 'EASE' (Bezier, slow in/out),
    'LINEAR' (constant machine pan), or 'HEAVY' (cubic: snappier start/stop)."""
    if loc0 is not None:
        cam.location = loc0
    cam.keyframe_insert("location", frame=f0)
    if lens1:
        cam.data.keyframe_insert("lens", frame=f0)
    cam.location = loc1
    cam.keyframe_insert("location", frame=f1)
    if lens1:
        cam.data.lens = lens1
        cam.data.keyframe_insert("lens", frame=f1)
    mode = {"EASE": ("BEZIER", "AUTO"), "LINEAR": ("LINEAR", "AUTO"), "HEAVY": ("CUBIC", "EASE_IN_OUT")}[ease]
    set_interpolation(cam, *mode, data_path_prefix="location")
    return cam


def _location_curves(cam, axes=(0, 2)):
    if not any(fc.data_path == "location" for fc in fcurves(cam)):
        cam.keyframe_insert("location", frame=bpy.context.scene.frame_start)
    return [fc for fc in fcurves(cam) if fc.data_path == "location" and fc.array_index in axes]


def handheld(cam, strength=0.03, scale=30.0):
    """Continuous hand-held drift: slow noise on X and Z with different phases
    (so the drift is never a robotic diagonal)."""
    mods = []
    for i, fc in enumerate(_location_curves(cam)):
        m = fc.modifiers.new("NOISE")
        m.strength, m.scale, m.phase = strength, scale, 1.0 + 7.3 * i
        mods.append(m)
    return mods


# Blender's Noise modifier at scale 1 peaks at about +/-0.3 x strength (measured).
NOISE_PEAK = 0.3

# Shake tiers from the alan_pipeline style bible (pixels at 1920 wide, frames at 60 fps).
SHAKE_TIERS = {"minor": (8, 5), "medium": (14, 7), "major": (22, 30)}


def impact_shake(cam, scene, frame, tier="medium", focus_depth=0.0):
    """A shake that starts on the impact frame and decays to zero. Amplitude
    comes from the style-bible tier in pixels, converted to Blender units at
    the subject's depth; duration scales from 60 fps to the scene's rate."""
    px, frames60 = SHAKE_TIERS[tier]
    w, _ = view_size_at(cam, scene, focus_depth)
    amp = px * w / scene.render.resolution_x
    dur = max(2, round(frames60 * scene.render.fps / 60))
    mods = []
    for i, fc in enumerate(_location_curves(cam)):
        m = fc.modifiers.new("NOISE")
        m.strength = amp / NOISE_PEAK  # peak jolt = tier amplitude
        m.scale = 1.0                 # a jolt every frame
        m.phase = frame * 0.37 + i * 11.0
        m.use_restricted_range = True
        m.frame_start, m.frame_end = frame, frame + dur
        m.blend_in, m.blend_out = 0.0, dur * 0.8  # instant hit, smooth settle
        mods.append(m)
    return mods


# ---------------------------------------------------------------------------
# Line art, shadows, glow, compositing                    (compositor-vfx)
# ---------------------------------------------------------------------------

def line_art(collection, name="Prop_Outlines", thickness=0.025, crease_deg=140.0, contour=True,
             crease=True, material_boundary=False, color=PALETTE["ink"]):
    """Automatic ink outlines for a collection of 3D objects (Line Art)."""
    gp_ob = new_gp_object(name)
    ink = gp_material("Outline_Ink", stroke=color)
    ensure_material(gp_ob, ink)
    layer = gp_layer(gp_ob, "Lines")
    m = gp_ob.modifiers.new("Line Art", "LINEART")
    m.source_type = "COLLECTION"
    m.source_collection = collection
    m.target_layer = layer.name
    m.target_material = ink
    m.radius = thickness
    m.use_contour, m.use_crease, m.use_material = contour, crease, material_boundary
    m.crease_threshold = math.radians(crease_deg)
    return gp_ob


def add_key_light(name="Key_Light", kind="SUN", energy=3.0, angle_deg=(50, 0, -30), location=(0, -4, 6)):
    """A scene light (Sun for even outdoor light, Point for a lamp)."""
    data = bpy.data.lights.new(name, kind)
    data.energy = energy
    ob = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = location
    ob.rotation_euler = [math.radians(a) for a in angle_deg]
    return ob


def light_layers(gp_ob, on=True):
    """Let scene lights shade this drawing (per layer, Grease Pencil v3)."""
    for l in gp_ob.data.layers:
        l.use_lights = on


def drop_shadow_fx(gp_ob, offset_px=(12, -12), color=PALETTE["shadow"], blur_px=6, pivot=None):
    """A flat cartoon drop shadow (Shadow effect). With `pivot` (e.g. a lamp
    empty) the shadow direction follows that object."""
    fx = gp_ob.shader_effects.new("Drop Shadow", "FX_SHADOW")
    fx.offset = offset_px
    fx.shadow_color = color
    fx.blur = (blur_px, blur_px)
    fx.samples = 4
    if pivot is not None:
        fx.use_object, fx.object = True, pivot
    return fx


def glow_fx(gp_ob, color=(0.2, 0.9, 1.0), size_px=30, threshold=0.1, opacity=0.6, samples=8):
    """Soft bloom behind lines; the stroke edge stays sharp (glow under)."""
    fx = gp_ob.shader_effects.new("Glow", "FX_GLOW")
    fx.mode = "COLOR"
    fx.glow_color = color
    fx.size = (size_px, size_px)
    fx.threshold = threshold
    fx.opacity = opacity
    fx.samples = samples
    fx.use_glow_under = True
    return fx


def contact_shadow(arm_ob, bone="Root", width=0.6, depth=0.15, floor_z=0.0):
    """A flat ellipse under the character that tracks it along the floor
    (Copy Location X/Y from the root bone; Z stays on the floor)."""
    mesh = bpy.data.meshes.new("Contact_Shadow")
    n = 24
    verts = [(width / 2 * math.cos(2 * math.pi * i / n), 0.0, depth / 2 * math.sin(2 * math.pi * i / n)) for i in range(n)]
    mesh.from_pydata(verts, [], [list(range(n))])
    ob = bpy.data.objects.new("Contact_Shadow", mesh)
    arm_ob.users_collection[0].objects.link(ob)
    ob.location.z = floor_z
    ob.location.y = 0.01  # just behind the character
    mesh.materials.append(flat_material("Shadow_Flat", PALETTE["shadow"]))
    c = ob.constraints.new("COPY_LOCATION")
    c.target, c.subtarget = arm_ob, bone
    c.use_y = c.use_z = False
    return ob


def setup_compositor(scene, glare="Bloom", threshold=0.8, strength=0.6, size=0.5, blur_px=0):
    """Render Layers -> (Blur) -> Glare (Bloom / Fog Glow) -> output.
    Blender 5.0 compositing is a node group assigned to the scene."""
    ng = bpy.data.node_groups.new(f"{scene.name}_Comp", "CompositorNodeTree")
    if hasattr(scene, "compositing_node_group"):
        scene.compositing_node_group = ng
    else:  # Blender 4.x
        scene.use_nodes = True
        ng = scene.node_tree
        ng.nodes.clear()
    nodes, links = ng.nodes, ng.links
    rl = nodes.new("CompositorNodeRLayers")
    rl.scene = scene
    src = rl.outputs["Image"]
    if blur_px:
        b = nodes.new("CompositorNodeBlur")
        _set_input(b, "Type", "Fast Gaussian")
        _set_input(b, "Size", (blur_px, blur_px))
        links.new(src, b.inputs["Image"])
        src = b.outputs["Image"]
    g = nodes.new("CompositorNodeGlare")
    _set_input(g, "Type", glare)
    _set_input(g, "Threshold", threshold)
    _set_input(g, "Strength", strength)
    _set_input(g, "Size", size)
    links.new(src, g.inputs["Image"])
    out = _comp_output(ng)
    links.new(g.outputs["Image"], out)
    return ng


def _set_input(node, name, value):
    if name in node.inputs:
        node.inputs[name].default_value = value
    else:  # Blender 4.x stored these as node properties
        prop = {"Type": "glare_type" if node.bl_idname.endswith("Glare") else "filter_type"}.get(name, name.lower())
        if isinstance(value, str):
            value = value.upper().replace(" ", "_")
        setattr(node, prop, value)


def _comp_output(ng):
    if bpy.app.version >= (5, 0, 0):
        go = ng.nodes.new("NodeGroupOutput")
        if not ng.interface.items_tree:
            ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        return go.inputs[0]
    return ng.nodes.new("CompositorNodeComposite").inputs["Image"]


# ---------------------------------------------------------------------------
# Shots and editorial                    (production-coordinator, delivery)
# ---------------------------------------------------------------------------

def new_shot(name, shared_collections, frame_end, base_scene=None, camera_distance=12.0):
    """A lightweight shot scene that *links* the shared asset collections (no
    copies) and owns its own camera and timing."""
    base = base_scene or bpy.context.scene
    s = bpy.data.scenes.new(name)
    setup_project(s, base.render.resolution_x, base.render.resolution_y, base.render.fps, frame_end)
    for c in shared_collections:
        s.collection.children.link(c)
    s.world = base.world
    s.render.engine = base.render.engine
    setup_camera(s, distance=camera_distance, name=f"Cam_{name}")
    return s


def assemble_master(shots, name="Master_Edit", sound=None, out_path="//renders/episode_", mode="preview"):
    """Cut the shot scenes end to end on channel 1 of a master edit scene,
    put the locked audio on channel 2, set the range and the output."""
    base = shots[0]
    m = bpy.data.scenes.get(name) or bpy.data.scenes.new(name)
    setup_project(m, base.render.resolution_x, base.render.resolution_y, base.render.fps)
    se = m.sequence_editor_create()
    strips = se.strips if hasattr(se, "strips") else se.sequences
    frame = 1
    for s in shots:
        st = strips.new_scene(s.name, s, channel=1, frame_start=frame)
        st.scene_input = "CAMERA"
        frame += s.frame_end - s.frame_start + 1
    if sound:
        strips.new_sound("Dialogue", sound, channel=2, frame_start=1)
    m.frame_end = frame - 1
    set_output(m, mode, out_path)
    return m


# ---------------------------------------------------------------------------
# Asset library                                (production-coordinator)
# ---------------------------------------------------------------------------

def mark_character_asset(collection, description=""):
    """Mark a character collection (rig + drawings) as a library asset."""
    collection.asset_mark()
    if description:
        collection.asset_data.description = description
    return collection.asset_data


def register_asset_library(name, path):
    libs = bpy.context.preferences.filepaths.asset_libraries
    lib = libs.get(name) or libs.new(name=name, directory=path)
    lib.path = path
    return lib


def link_character(blend_path, collection_name, scene=None):
    """Link a character collection from its master file and make a library
    override, so the rig is animatable here but the source stays protected."""
    s = scene or bpy.context.scene
    with bpy.data.libraries.load(blend_path, link=True) as (src, dst):
        dst.collections = [collection_name]
    coll = dst.collections[0]
    s.collection.children.link(coll)
    return coll.override_hierarchy_create(s, bpy.context.view_layer, do_fully_editable=True)
