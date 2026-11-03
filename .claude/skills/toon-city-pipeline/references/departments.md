# Departments: craft, tools and equivalents

This file records how each Toon City department works and how it maps onto this
studio (Motion Canvas + Python), with the Blender and Harmony equivalents for
anyone who builds the same pipeline in those tools.

| stage | Toon City (studio standard) | here | Blender (free) | other alternatives |
|---|---|---|---|---|
| Animatic / timing lock | client animatic, Storyboard Pro | `story.json` → `cues.json`, stills via `--at` | Video Sequencer + Grease Pencil boards | OpenToonz, Krita |
| Rigging | Harmony deformers, pegs, drawing substitutions | `figureSpec.ts`, `StickFigure` joints, `reach`/`plant` | Armature + Grease Pencil, vertex groups, IK constraints | Moho, Adobe Animate |
| Layout / camera | Harmony camera, field guide | eased `camera` tweens, safe margin, auditor | Camera + Image-as-Planes multiplane, DoF | After Effects 3D layers |
| Backgrounds | Photoshop / Painter | vector set components, tiered strokes | Grease Pencil or painted planes | Krita, GIMP, Clip Studio |
| Key animation | senior animators, pose-to-pose | `pose` / `springPose` on `syncTo` cues | Pose Mode + Auto-Key, Dope Sheet | Harmony, Moho |
| In-between / clean-up | juniors + clean-up on model sheets | easing, breakdowns, overlap, on-model checks | Graph Editor curves, interpolation modes | CACANi (auto in-betweens) |
| Lip sync | phoneme charts, mouth swaps | viseme/accent data from the voice clip | Time Offset modifier, Fixed Frame mouth library | Papagayo-NG, Rhubarb Lip Sync |
| Compositing / VFX | Harmony / After Effects | scene-graph layering, `Fx.ts`, glow, shake tiers | Compositor nodes, Glare, Defocus | Natron, DaVinci Fusion |
| Sound | client post house | `build_space_audio.py` (synthesized) | Video Sequencer audio strips | DaVinci Fairlight, Audacity |
| Render & delivery | render farm → client | `render.mjs --strict` → ffmpeg phone master | Output Properties → FFmpeg H.264 | DaVinci Resolve |

## Experience each department needs (summary)

- **Pre-production.** Story structure (9 beats, set-up/pay-off), boarding for
  clarity, frame-accurate timing, voice direction. Lock before labour.
- **Rigging.** Model sheets and turnarounds, joint hierarchy and pivots, overlap
  caps at joints, FK vs IK, swap libraries, deformation limits, animator-friendly controls.
- **Layout.** Field sizes, composition (ground line, lead room, negative space),
  camera language and easing, staging for clarity, multiplane depth.
- **Backgrounds.** Values before colour, palette discipline, line-weight tiers,
  silhouette before detail, depth layers, living sets.
- **Physics.** Named constants, asserted outcomes, frame-step integration, seeded
  timing search, one shared definition per motion.
- **Key animation.** The 12 principles, house frame counts, readable silhouettes,
  acting for the want, walk/run keys, fight grammar.
- **In-between / clean-up.** Spacing charts, breakdowns on arcs, overlap and
  settle, springs, smears, on-model checks, entry/exit rules.
- **Lip sync.** Viseme set (A/I, E, O, U, MBP, L/D/T, W/Q, F/V, Rest), reading the
  track, a 1-2 frame lead, closed plosives, and body accents on stressed syllables.
- **Compositing.** Layer order, grounding shadows, bloom behind sharp edges, impact
  layers and shake tiers, energy vs solid growth.
- **Sound.** ±1 f sync, a continuous phone-band score, contrast via ducking,
  physical and vocal realism, silence before the climax.
- **QC.** Review in pipeline order, actionable notes with an owner and a severity,
  automated gates plus an audience's eye.
- **Delivery.** Render from a committed state, spec'd masters, verify with ffprobe,
  remux instead of re-rendering.

Each agent file in `.claude/agents/` holds the full version of its department's
experience, plus its procedure in this repo.
