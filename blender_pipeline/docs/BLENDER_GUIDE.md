# Blender guide: the Toon City pipeline by hand, with corrections

These are the manual (UI) steps for each department, checked against Blender
5.0.1. Where a common tutorial step no longer matches Blender 4.3+ (Grease Pencil
v3), the **correction** says what to do instead. Each step names the `toonkit`
function that does the same thing in code.

## Corrections at a glance

| tutorial says | in Blender 4.3+ / 5.0 |
|---|---|
| "Shadow / Light Buster modifier" lit by a lamp | No such modifier. For lamp lighting, enable **Use Lights** on each GP layer (Layer properties) and add a Sun/Point light (`light_layers`, `add_key_light`). For a cartoon drop shadow, use the **Shadow visual effect** (Object > Visual Effects), optionally pivoting on an object (`drop_shadow_fx`). |
| Lower the "Viewport Canvas Quality / Texture Resolution" | No such setting. Use **Render > Simplify** (Grease Pencil: Anti-Aliasing off, Modifiers/Shader Effects off while animating), and turn off each heavy modifier's viewport toggle (`draft_viewport`). |
| Compositor: tick **Use Nodes**, wire to **Composite** | 5.0: in the Compositor, click **New** to create a node group; the output is the group's **Group Output** (`setup_compositor`). Glare and Blur settings are node *inputs* now (Type: Bloom / Fog Glow, Size, Threshold). |
| Glare "Fog Glow" | Still there. **Bloom** is the newer, cheaper choice for highlights. |
| Image as Planes add-on must be enabled | Built in since 4.2: **Add > Image > Mesh Plane** (`add_painting`). |
| IK pole angle: "try 90, -90 or 180" | Depends on the bone roll. `solve_pole_angle` measures it, choosing the angle at which the rest pose doesn't move. |
| Ctrl+P > With Empty Groups, then weight paint red | Works, but painting is slow and leaks between parts. For cut-out rigs, assign each layer's points to its bone's group at weight 1.0 (`bind_layers_to_bones`). Paint only where you want soft bends. |
| Noise modifier: key **Influence** 0 → 1 → 0 for impacts | Works (tick **Influence** first). Cleaner: one Noise per impact with **Restrict Frame Range** (start = impact frame, Blend Out = decay) (`impact_shake`). |
| Noise **Strength** "0.05-0.15" for drift | Strength is in Blender units. The noise peaks at about ±0.3 × Strength, so pick it from the shake you want in pixels (`impact_shake` converts style-bible pixels to units at the subject's depth). |
| Line Art "Bake" for performance | Still available (modifier menu > Bake Line Art). It's a context-heavy operator, so do it by hand once the shot is approved. |
| Sync: "Frame Dropping" | Same; in Python `scene.sync_mode = 'FRAME_DROP'`. |
| FFmpeg output | 5.0: set **Media Type: Video** first, then MPEG-4 / H.264 / AAC (`set_output('preview' or 'phone')`). |

## 1. Pre-production (story-animatic-lead)
1. Lock the audio first. In the Video Sequencer, add Sound at frame 1, and set
   **End Frame** to the last frame of dialogue.
2. Time the storyboard panels to the audio (image strips or GP boards). Don't
   animate until the animatic is locked.

## 2. Rigging (character-rigger)
1. **Skeleton.** Add > Armature. In Edit Mode, extrude (E) Torso → Neck → Head, and
   shoulders → Upper/Lower arm → Hand, hips → Upper/Lower leg. Use head-unit
   lengths (`build_biped_armature`). Give elbows and knees a slight forward bend so
   IK knows which way to fold. Turn on Viewport Display > **In Front**.
2. **Drawing.** One GP layer per bone, with the same names. Overlap the caps at the
   joints so bends never show a gap.
3. **Bind.** Select the drawing, then shift-select the armature, Ctrl+P >
   **With Empty Groups**. Assign each layer to its bone (see corrections).
4. **Leg IK.**
   - In Edit Mode, extrude **IK_Target_L** back from the ankle along the floor.
     Parent it to **Root** (not the leg), and untick Deform.
   - Extrude **Pole_Target_L** out in front of the knee, parented to Root.
   - In Pose Mode, select the shin, and add Bone Constraint > **Inverse
     Kinematics**: Target armature / IK_Target_L, Pole armature / Pole_Target_L,
     **Chain Length 2**.
   - Fix the pole angle until the rest pose doesn't move (`add_leg_ik` does all of this).
   - Test: lower the torso. The feet stay on the floor and the knees bend forward.

## 3. Layout & backgrounds (layout-artist, background-artist)
1. Camera looking along +Y. Depth layers: BG_Far (Y +40), BG_Mid (+15),
   Characters (0), FG_Overlay (−5). Scale each card to fill the frame at its depth,
   plus a 15% margin for pans and shake (`build_multiplane`).
2. Painted backgrounds: Add > Image > Mesh Plane. Give them unlit (emission)
   materials so lights don't change the painting (`flat_material`).
3. Depth of field: Camera > Depth of Field, Focus Object = the character rig.

## 4. Lip sync (lipsync-animator)
1. On the **Mouth** layer, draw the 9 visemes on frames 1-9: A/I, E, O, U, MBP,
   L/D/T, W/Q, F/V, Rest.
2. Add Modifier > **Time Offset**: Mode **Fixed Frame**, Layer = Mouth.
3. Key the modifier's Frame value with constant interpolation, landing one frame
   before each sound. Generate the cues automatically with
   [Rhubarb Lip Sync](https://github.com/DanielSWolf/rhubarb-lip-sync)
   (`rhubarb -f json line.wav`), then `rhubarb_cues` and `key_visemes`.

## 5. Animation (key-animator, inbetween-cleanup-artist)
1. Pose Mode, Auto-Key on.
2. Walk (24-frame loop): contact (1), down (6, torso lowest), passing (12), up
   (18, torso highest), opposite contact (24/25). Animate the **IK targets** and the
   torso, not the thighs. The arms swing opposite to the legs, in the picture plane
   (`walk_cycle`).
3. Graph Editor: Bézier for weight, Linear for machine moves, and drag the handles
   for snappier easing (`set_interpolation`, `camera_move(ease=…)`).

## 6. Camera (layout-artist)
- Moves: key Location at the start and end frames. Ease with Bézier, or use Linear
  for a constant pan (`camera_move`).
- Hand-held: Graph Editor > Modifiers > Noise on X and Z Location, with different
  Phase values (`handheld`).
- Impact shake: a Noise per impact with a restricted frame range and blend-out.
  Tiers come from the style bible: minor 8 px, medium 14 px, major 22 px (`impact_shake`).

## 7. Line art, lighting, glow (compositor-vfx)
1. Put the 3D props in a collection (M > New Collection).
2. Add > Grease Pencil > Blank, add an ink material, then Modifier > **Line Art**:
   Source Collection, Target Layer, Target Material; Contour + Crease (`line_art`).
3. Lighting: Layer > **Use Lights**, plus a Sun or Point light. Drop shadow: Visual
   Effects > **Shadow**. Floor shadow: a flat dark ellipse with Copy Location (X/Y)
   to the root bone (`contact_shadow`).
4. Glow: Visual Effects > **Glow** (Mode Color, Glow Under on, so the line stays
   sharp). Bloom over the whole scene goes in the compositor (`setup_compositor`).

## 8. Shots, edit, render (production-coordinator, render-delivery)
1. One scene per shot that **links** the shared collections (no copies) and has its
   own camera (`new_shot`).
2. A **Master_Edit** scene: in the Video Sequencer, add Scene strips end to end on
   channel 1 and the locked audio on channel 2 (`assemble_master`).
3. Output: Media Type **Video**, MPEG-4 / H.264 / AAC for reviews. Use PNG RGBA
   (or multilayer EXR) sequences for finals, since they survive crashes and keep
   alpha (`set_output`).
4. Render > Render Animation (Ctrl+F12). Headless:
   `blender -b master.blend -S Master_Edit -a`.

## 9. Asset library and template (production-coordinator)
1. In each character's master file, put the rig and drawing in a collection
   `CH_<Name>`, then right-click > **Mark as Asset** (`mark_character_asset`).
2. Preferences > File Paths > Asset Libraries > **+**, pointing at `01_Assets`
   (`register_asset_library`).
3. Drag the character from the Asset Browser with Import Method **Link**, then
   Object > Library Override > **Make** (`link_character`).
4. When an empty, optimized setup is ready: File > Defaults > **Save Startup File**.
