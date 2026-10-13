/**
 * The physics the space_duel scene draws. Every on-screen effect is computed
 * from these formulas rather than eyeballed.
 */

/** Lorentz factor: gamma = 1 / sqrt(1 - beta^2), beta = v / c. */
export function gamma(beta: number): number {
  return 1 / Math.sqrt(1 - Math.min(0.999999, beta * beta));
}

/**
 * Relativistic Doppler factor along the line of sight. `beta` > 0 means the
 * source approaches the observer (light blueshifted, wavelength divided by D).
 */
export function dopplerFactor(beta: number): number {
  return Math.sqrt((1 + beta) / (1 - beta));
}

/** Wavelength (nm) seen by an observer the source approaches at `beta`. */
export function observedWavelength(restNm: number, beta: number): number {
  return restNm / dopplerFactor(beta);
}

/**
 * Approximate sRGB colour of monochromatic light (Bruton's piecewise fit), with
 * intensity falling to zero at the edges of human vision (380-780 nm). Light
 * outside that band is returned fully transparent: it exists, we just cannot
 * see it.
 */
export function wavelengthColor(nm: number, brightness = 1): string {
  if (!(nm >= 380 && nm <= 780)) return 'rgba(0,0,0,0)';
  let r = 0;
  let g = 0;
  let b = 0;
  if (nm >= 380 && nm < 440) {
    r = -(nm - 440) / 60;
    b = 1;
  } else if (nm < 490) {
    g = (nm - 440) / 50;
    b = 1;
  } else if (nm < 510) {
    g = 1;
    b = -(nm - 510) / 20;
  } else if (nm < 580) {
    r = (nm - 510) / 70;
    g = 1;
  } else if (nm < 645) {
    r = 1;
    g = -(nm - 645) / 65;
  } else if (nm <= 780) {
    r = 1;
  }
  let falloff = 0;
  if (nm >= 380 && nm < 420) falloff = 0.3 + (0.7 * (nm - 380)) / 40;
  else if (nm >= 420 && nm <= 700) falloff = 1;
  else if (nm > 700 && nm <= 780) falloff = 0.3 + (0.7 * (780 - nm)) / 80;
  const c = (v: number) => Math.round(255 * Math.pow(v, 0.8));
  return `rgba(${c(r)},${c(g)},${c(b)},${(falloff * brightness).toFixed(3)})`;
}

/** Quantum tunnelling probability through a barrier: T ~ exp(-2 kappa d). */
export function tunnelProbability(kappaTimesWidth: number): number {
  return Math.exp(-2 * kappaTimesWidth);
}

/** Deterministic PRNG (mulberry32) so starfields and sparks never change between renders. */
export function prng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
