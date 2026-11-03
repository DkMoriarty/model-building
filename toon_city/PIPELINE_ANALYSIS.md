# Toon City pipeline — analysis and the department agents

The user's first ask: *analyse the Toon City animation production pipeline,
create an agent for each work, and acquire the skill experience.*

## The analysis

Toon City (Manila) is a service studio: the client sends script, voices,
designs and an animatic; departments rig, lay out, paint backgrounds, animate,
clean up, lip-sync and composite, with director notes passed down in sequence
until QC passes and the layers ship. The repo reproduces that assembly line:

- **Order of locks:** story → timeline/audio → animatic. Nothing is animated on an unlocked timeline.
- **Parallel where safe:** rigging ∥ physics, then layout ∥ backgrounds.
- **Per-shot animation chain:** key → in-between/clean-up → lip sync → composite.
- **Sound** after picture lock; **QC** routes each note to the earliest owning
  department, the chain re-runs downward for those shots only; **delivery** only after APPROVED.

## Agents (`.claude/agents/`)

| Department | Agent |
|---|---|
| Production management | `production-coordinator` |
| Script / VO / animatic | `story-animatic-lead` |
| Character rigging (TD) | `character-rigger` |
| Layout / cinematography | `layout-artist` |
| Background design & painting | `background-artist` |
| CG/FX TD (physics) | `physics-td` |
| Key animation | `key-animator` |
| In-between & clean-up | `inbetween-cleanup-artist` |
| Lip sync | `lipsync-animator` |
| Compositing & VFX | `compositor-vfx` |
| Sound post | `sound-designer` |
| Director review & QC | `qc-reviewer` |
| Render & delivery | `render-delivery` |

The skill that ties them together: `.claude/skills/toon-city-pipeline/`
(`SKILL.md`, `references/handoffs.md` — work-order + board template,
`references/departments.md` — the craft of each department and the
Blender/Harmony equivalents).

## Blender track

The user then pasted a Blender walkthrough (IK, camera, Grease Pencil, Line
Art, shadows, glow, export, asset library, VSE, camera shake, viewport
performance, startup file). That became a tested toolkit:

- `blender_pipeline/toonkit.py` — helpers for each step.
- `blender_pipeline/build_demo.py` — builds a demo using all of them and runs checks
  (`blender -b -P blender_pipeline/build_demo.py` must report all checks passed).
- `blender_pipeline/docs/BLENDER_GUIDE.md` — the guide, including where common
  tutorials no longer match current Blender.

## Style direction learned from the user

1. "Not stickman" → a rigged Grease Pencil cut-out puppet from the snowboarder
   sheets (refs 01, 02): `blender_pipeline/characters/snowboarder.py`
   (+ face, lattice puffer, tapered lines, joints, multiply shadows, wedge jaw, goggles).
2. Ink Industries grid (ref 03) → **3D** stylised characters (the user chose a
   fixie cyclist and a 3D model).
3. Quality pass the user specified: planar garments, matte vinyl shader (roughness .95,
   no spec, IOR 1.1, clay-grain bump), hard key light, AgX Medium-High Contrast,
   film grain, sculpted planar faces, Ink-style facial features, ribbon hair,
   golden-hour lighting (warm key left, hot cream rim behind, lavender fill),
   shallow DOF.
