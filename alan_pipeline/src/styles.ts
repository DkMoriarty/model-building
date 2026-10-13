import {makeSpring} from '@motion-canvas/core';

/**
 * Global look-and-feel constants. Minimalist dark canvas with a red accent,
 * in the spirit of Alan Becker's "Animator vs. Animation" desktop fights.
 */
export const Colors = {
  background: '#0f0f12',
  surface: '#1a1a1f',
  surfaceRaised: '#24242b',
  border: '#34343d',
  ink: '#f2f2f2',
  inkMuted: '#8a8a96',
  accent: '#e63946',
  accentDark: '#9d0208',
  victim: '#4ea8de',
  impact: '#ffffff',
} as const;

export const Stroke = {
  limb: 10,
  head: 9,
  ui: 3,
} as const;

export const Typography = {
  family: 'Segoe UI, Roboto, Helvetica, Arial, sans-serif',
  mono: 'Consolas, "JetBrains Mono", monospace',
  title: 26,
  body: 30,
} as const;

/** Render target: 1080p @ 60 FPS. Mirrored in src/project.meta. */
export const Output = {
  width: 1920,
  height: 1080,
  fps: 60,
} as const;

/**
 * Project spring presets (mass, stiffness, damping). Damping ratio
 * zeta = damping / (2 * sqrt(stiffness * mass)) decides the feel:
 * ~0.6 gives one visible overshoot and a fast settle.
 */
export const Springs = {
  /** UI window arrival: one overshoot, settles in ~0.45s. */
  windowPop: makeSpring(1, 240, 18),
  /** Body knocked back by a hit: critically damped, settles in ~0.3s. */
  knockback: makeSpring(1, 300, 35),
  /** Joint reaction to an impact: snappy whip with a small rebound, ~0.3s. */
  recoil: makeSpring(1, 600, 34),
} as const;
