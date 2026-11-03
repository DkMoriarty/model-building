# TOON CITY — handoff folder

Everything from the cloud session so far, in one place, so a local agent
(running on the user's Windows PC next to Blender) can pick up and continue
**inside Blender**.

Owner: Dhiraj. Repo: `dkmoriarty/model-building`, branch
`claude/toon-city-animation-pipeline-uzxbgn`.

## Read in this order

1. **[HANDOFF.md](HANDOFF.md)** — where we are, what the user wants next, what
   to do first. Start here.
2. **[CHARACTERS.md](CHARACTERS.md)** — both 3D characters: measured face
   layouts, every parameter, the full history of the user's feedback (what
   was rejected and why), known issues.
3. **[BLENDER_LOCAL.md](BLENDER_LOCAL.md)** — running the build in the user's
   own Blender (their version is **older than 5.0**: 5.0 `.blend` files fail
   with "not a blend file"), where everything is in the file, how to edit.
4. **[PIPELINE_ANALYSIS.md](PIPELINE_ANALYSIS.md)** — the original Toon City
   studio-pipeline analysis, the 13 department agents and the skill.
5. **[SCENES.md](SCENES.md)** — the scenes built so far (SNOW RUN delivered;
   CROSSWALK coded, waiting on final faces).

## Folder

```
toon_city/
  README.md  HANDOFF.md  CHARACTERS.md  BLENDER_LOCAL.md  PIPELINE_ANALYSIS.md  SCENES.md
  blender/                 runnable copies of the character + scene scripts
    RUN_IN_BLENDER.py      <- open in Blender's Scripting tab, Run Script: builds both characters
    fixie_rider.py         him + every shared builder (face, eyes, hair, rig, lights)
    street_scene.py        her (build_girl) + the CROSSWALK scene
    street_scene_audio.py  CROSSWALK soundtrack (numpy, no Blender)
    expression_sheet.py    renders every expression for both
    save_blend.py          command-line: build + save a .blend
  references/              the user's reference images (01..09), numbered in the order sent
  renders/                 latest comparison renders vs the references
```

`blender/` is a copy of `blender_pipeline/characters3d/` at handoff time. The
canonical source is `blender_pipeline/characters3d/`; keep the two in sync
(or switch to `toon_city/blender/` as the canonical copy and say so in the
commit).
