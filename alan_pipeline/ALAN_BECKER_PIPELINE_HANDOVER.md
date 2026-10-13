# System Architecture Handover: Deterministic Vector Animation Studio

## 1. Executive Summary & Mission

Initialize a local, code-driven, high-performance vector animation pipeline on a
Lenovo Legion 5 (1TB SSD, 4GB VRAM, multi-core CPU). The system bypasses
probabilistic AI video generation entirely, relying instead on Motion Canvas,
TypeScript, and mathematical motion generators to produce zero-drift,
frame-perfect, Alan Becker-style stick-figure animations and software-interface
interactions.

## 2. Technology Stack & Environment Blueprint

- **Core Animation Engine:** Motion Canvas (`@motion-canvas/core`, `@motion-canvas/2d`)
- **Language & Typing:** TypeScript (strict mode enabled)
- **Build & Render Toolchain:** Vite, headless Chromium rendering engine
- **Pipeline Orchestration:** Local Node.js execution hooks ready for integration with n8n Flow Premium
- **Hardware Utilization Target:** Local NVMe SSD for fast uncompressed frame caching; multi-threaded CPU rendering (`--concurrency=4`)

## 3. Mandatory Directory Structure

```
/alan_pipeline/
├── src/
│   ├── components/
│   │   ├── StickFigure.ts       # Hierarchical kinematic joint rig (Torso, limbs, rotation matrices)
│   │   └── UIWindow.ts          # Vector-based popups, toolbars, and dialog boxes
│   ├── scenes/
│   │   └── opening_fight.ts     # Initial test scene using generator functions (function*)
│   ├── project.ts               # Master project configuration file
│   └── styles.ts                # Global color constants (Minimalist red/dark accent theme)
├── audio/
│   └── master_track.wav         # Master audio sync file with transient markers
├── output_renders/              # High-bitrate 60FPS lossless output frames & stitched video
├── package.json
├── tsconfig.json
└── vite.config.js               # CommonJS/Vite configuration workaround for Motion Canvas
```

## 4. Engineering Rules

- **Signal-Driven Reactivity:** Avoid hardcoded linear keyframes where possible. Use Motion Canvas Signals and dynamic generator functions (`function* (view) { ... yield* ... }`) to control timing, velocity, and physics.
- **Hierarchical Kinematics:** Stick figures must be built using nested vector groups so that limbs inherit parent rotation matrices cleanly without floating coordinate drift.
- **Spring Physics Over Linear Easing:** Impacts, punches, and UI box arrivals must utilize spring-damper mathematical interpolation (`tween`, `spring`) to replicate heavy, satisfying weight dynamics.
- **Optimized Rendering Parameters:** Local build and render scripts leverage multi-threading configured for the Legion 5 hardware specs (`--concurrency=4`).

## 5. Immediate Action Items

1. **Scaffold Package Dependencies:** `package.json` includes `@motion-canvas/core`, `@motion-canvas/2d`, `@motion-canvas/ui`, and `@motion-canvas/vite-plugin`.
2. **Configure Vite & TSX:** `vite.config.js` handles Motion Canvas module resolution without CommonJS/ESM bundling errors.
3. **Build the Root Component:** `src/components/StickFigure.ts` with joint properties (head, torso, arms, legs) exposed as animatable signals.
4. **Run Validation Build:** Test compile; the local browser-preview server spins up cleanly on the local network.

## Trigger

```bash
claude -p "Read ALAN_BECKER_PIPELINE_HANDOVER.md, validate the system requirements, and initialize the Motion Canvas workspace structure on this machine."
```
