---
name: toon-city-pipeline
description: "Run an episode through a Toon City-style industrial animation pipeline using one specialist agent per department (pre-production/animatic, rigging, layout, backgrounds, physics, key animation, in-between/clean-up, lip sync, compositing/VFX, sound post, QC review, render/delivery) with locked hand-offs, a shot board and sequential review notes. Use when the user asks for the studio pipeline, department agents, a production board, a review pass, retakes, or wants a large episode split across departments; for a plain storyline-to-film request, storyline-to-film remains the method and this skill organises who does each step."
---

# Toon City pipeline (department agents)

Toon City (Manila) is a service studio. Clients send script, voices, designs and an
animatic. Departments then rig, lay out, paint, animate, clean up, lip-sync and
composite, with director notes passed down in sequence until QC passes and the
layers ship. This skill runs the same assembly line in `alan_pipeline/`, with one
Claude Code agent per department (`.claude/agents/`).

`storyline-to-film` is still **the method** (its rules and non-negotiables all
apply). This skill is **the org chart**: who owns each step, what they hand over,
and how notes flow.

## Departments → agents
| Toon City department | agent | owns in this repo |
|---|---|---|
| Production management | `production-coordinator` | `docs/production/<ep>/board.md`, routing, gates |
| Client hand-off: script, VO, animatic | `story-animatic-lead` | `docs/episodes/<ep>.md`, `shots.md`, `tools/<ep>_timeline.py`, `story.json` |
| Character rigging (TD) | `character-rigger` | `figureSpec.ts`, `StickFigure.ts`, pose/prop libraries, `reach`/`plant` |
| Layout / cinematography | `layout-artist` | camera blocks and marks in acts, audit exemptions |
| Background design & painting | `background-artist` | world/room/set components, palette, depth layers |
| CG/FX TD (physics) | `physics-td` | `tools/<ep>_plans.py`, asserts, plan data |
| Key animation | `key-animator` | key poses on cues in `acts/` |
| In-between & clean-up | `inbetween-cleanup-artist` | spacing, arcs, overlap, on-model checks |
| Lip sync | `lipsync-animator` | visemes/accents data, mouth library or talk acting |
| Compositing & VFX | `compositor-vfx` | layer order, Fx, glow, shakes, parallax |
| Sound post (client side at Toon City) | `sound-designer` | score, sfx, ducks, mix |
| Director review & QC | `qc-reviewer` | `docs/production/<ep>/notes.md`, verdicts |
| Final render & delivery | `render-delivery` | strict render, phone master, commit/push |

The craft each department brings, and the Blender/Harmony equivalents, are in
`references/departments.md`.

## How to run it
1. Start with `production-coordinator` (or act as it yourself): open the board
   from `references/handoffs.md`.
2. **Lock in order:** story → timeline/audio → animatic. Nothing is animated on an
   unlocked timeline.
3. **Parallel where safe:** rigging ∥ physics, then layout ∥ backgrounds.
4. **Animation chain per shot:** key → in-between/clean-up → lip sync → composite.
5. **Sound** once picture is locked for a sequence.
6. **QC pass.** Each note goes to its earliest owning department. Re-run the chain
   downward for those shots only, then QC again.
7. **Deliver** only after `APPROVED`.

Each agent starts cold. A work order must name the episode, the shot ids, the
input files, the output files and the gate command (template in `references/handoffs.md`).

## Gates (a shot cannot move on until its gate passes)
- Timeline: `build_space_audio.py --episode <ep>` succeeds with no line overruns.
- Rig: `npm run typecheck`, plus pose stills read in both facings.
- Layout/animation: `node scripts/render.mjs --project=<ep> --at=...` prints no
  `late`, `contact … miss`, F1s or F3s lines.
- Final: `npm run render:<x>` (strict) and `python tools/frame_audit.py --episode <ep>`
  exit 0 with 0 hard flags.

## Lessons
Department lessons go in `alan_pipeline/docs/LEARNING_LOG.md`. When a rule
becomes permanent, promote it into the owning agent's file.
