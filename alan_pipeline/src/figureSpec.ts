import type {Proportions} from './components/StickFigure';

/**
 * Measured figure system. Every length is a multiple of H, the head's outer
 * diameter, so figures are built from ratios, never from loose pixel numbers.
 * The ratios come from docs/STYLE_BIBLE.md (section 2); change them there
 * first, then here.
 *
 * Our characters are original designs. This file encodes construction
 * technique (proportion, stroke weight), not anyone else's character.
 */
export interface FigureSpec {
  /** Head outer diameter in px at scale 1. */
  H: number;
  /** Ratios to H. */
  neck: number;
  torso: number;
  upperArm: number;
  forearm: number;
  thigh: number;
  shin: number;
  /** Limb + head-ring stroke weight as a fraction of H. */
  stroke: number;
}

/** Base biped: 4.85 H tall, segments within the measured 1.0-1.2 H band. */
export const BIPED: FigureSpec = {
  H: 56,
  neck: 0.12,
  torso: 1.4,
  upperArm: 1.05,
  forearm: 1.05,
  thigh: 1.15,
  shin: 1.15,
  stroke: 0.14,
};

/**
 * Taller, longer-limbed variant for non-human characters: same H and stroke,
 * every proportion still a measured ratio (5.5 H tall).
 */
export const LONG_BIPED: FigureSpec = {
  ...BIPED,
  neck: 0.35,
  torso: 1.65,
  upperArm: 1.2,
  forearm: 1.2,
  thigh: 1.25,
  shin: 1.4,
};

/** Pixel proportions for StickFigure from a spec. */
export function proportionsOf(spec: FigureSpec): Proportions {
  return {
    headRadius: spec.H / 2,
    neck: spec.neck * spec.H,
    torso: spec.torso * spec.H,
    upperArm: spec.upperArm * spec.H,
    forearm: spec.forearm * spec.H,
    thigh: spec.thigh * spec.H,
    shin: spec.shin * spec.H,
  };
}

/** Stroke weight in px for figures built from `spec`. */
export function strokeOf(spec: FigureSpec): number {
  return spec.stroke * spec.H;
}

/**
 * Environment line weight: 50-65% of the figure stroke, so characters always
 * dominate the frame (style bible, rule "hierarchy").
 */
export function environmentStroke(spec: FigureSpec = BIPED): number {
  return strokeOf(spec) * 0.55;
}

/** Total standing height in units of H (head + neck + torso + leg). */
export function heightInH(spec: FigureSpec): number {
  return 1 + spec.neck + spec.torso + spec.thigh + spec.shin;
}
