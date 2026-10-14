# Spark Studio

A code-driven 2D stick-figure animation studio (Motion Canvas). Give it a
storyline; it produces a finished film: real physics, typed code on screen,
a synchronized score and sound design, and every frame checked.

- [`alan_pipeline/`](./alan_pipeline): the studio (episodes, tools, docs).
- [`.claude/skills/storyline-to-film/`](./.claude/skills/storyline-to-film): the full production method, as a Claude Code skill.

Episodes: **FIRST GAME** (`render:game`), **FIRST LIGHT** (`render:light`),
**The Entangled Blade** (`render:space`).

## Run it on your machine

1. Install Git, then clone (sign in with the GitHub account that owns the repo):
   ```
   git clone https://github.com/DkMoriarty/spark-studio.git
   cd spark-studio
   ```
2. One-command setup (installs missing tools, packages, soundtracks, and checks the machine):
   - Windows: `powershell -ExecutionPolicy Bypass -File setup.ps1`
   - macOS / Linux: `bash setup.sh`
3. Use it:
   ```
   cd alan_pipeline
   npm start                  # live editor at http://localhost:9000
   npm run render:game        # full render -> output_renders/first_game.mp4
   node scripts/render.mjs --project=first_game --at=60,120   # quick stills
   python tools/frame_audit.py --episode first_game           # frame audit
   ```

## Make a new film with Claude

From any Claude account connected to this GitHub account (claude.ai/code,
the desktop app, or Claude Code in a terminal opened in this folder): open a
session on this repository and send a storyline. The `storyline-to-film`
skill loads automatically and runs the whole method: story refinement,
physics, timeline, animation, sound, verification and delivery.

Locally with Claude Code: `cd spark-studio && claude`, then send the storyline.
