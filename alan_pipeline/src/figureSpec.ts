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
 * Line-weight tiers, figure : structure : detail = 3 : 2 : 1, so characters
 * always dominate (docs/STYLE_BIBLE.md, section 5). Vertex dots are
 * 1.35 x the structure weight in radius.
 */
export function strokeTiers(spec: FigureSpec = BIPED) {
  const figure = strokeOf(spec);
  const structure = (figure * 2) / 3;
  return {figure, structure, detail: figure / 3, nodeRadius: structure * 1.35};
}

/** Figures are drawn at this node scale in our shots. */
export const FIGURE_SCALE = 0.8;

/**
 * Local stroke for a prop drawn at `nodeScale`, so that on screen it keeps
 * its tier ratio to a figure drawn at FIGURE_SCALE.
 */
export function propStroke(tierPx: number, nodeScale: number): number {
  return (tierPx * FIGURE_SCALE) / nodeScale;
}

/** `#rrggbb` -> `rgba(r,g,b,a)`, for soft glows that keep edges sharp. */
export function withAlpha(hex: string, alpha: number): string {
  const n = parseInt(hex.replace('#', ''), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
}

/** Total standing height in units of H (head + neck + torso + leg). */
export function heightInH(spec: FigureSpec): number {
  return 1 + spec.neck + spec.torso + spec.thigh + spec.shin;
}
