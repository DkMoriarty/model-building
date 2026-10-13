import {cancel, Spring, ThreadGenerator, useLogger, useTime, waitFor} from '@motion-canvas/core';
import track from '../audio/master_track.markers.json';

export type Marker = keyof typeof track.markers;

/** Transient markers from the master audio track, in seconds. */
export const markers = track.markers;

/** Length of one beat in seconds. */
export const beat = 60 / track.bpm;

/** Absolute time of an audio marker, optionally shifted by whole/partial beats. */
export function at(marker: Marker, beats = 0): number {
  return markers[marker] + beats * beat;
}

/**
 * Wait until the scene clock reaches an audio marker. Anchoring beats to
 * absolute times (rather than chaining durations) means retiming one action
 * never shifts every hit after it off the music.
 *
 * `lead` starts the action that many seconds early, for motions whose
 * contact happens partway through (see `springContactTime`).
 */
export function* syncTo(marker: Marker, lead = 0): ThreadGenerator {
  const remaining = markers[marker] - lead - useTime();
  if (remaining > 0) {
    yield* waitFor(remaining);
  } else if (remaining < -1 / 120) {
    // The previous action overran: this beat will land off the music.
    useLogger().warn(
      `syncTo("${marker}"${lead ? `, lead ${lead.toFixed(3)}` : ''}) reached ` +
        `${(-remaining * 1000).toFixed(0)} ms late - shorten the action before it`,
    );
  }
}

/**
 * Run `tasks` (typically spring reactions) in the background and cut them off
 * when the timeline reaches `marker - lead`. Springs settle asymptotically,
 * so their tails can run far longer than they look; this keeps a reaction
 * from ever delaying the next beat. Values freeze wherever the tasks are, and
 * the next action tweens on from there.
 */
export function* playUntil(marker: Marker, lead: number, ...tasks: ThreadGenerator[]): ThreadGenerator {
  const running: ThreadGenerator[] = [];
  for (const task of tasks) {
    running.push((yield task) as ThreadGenerator);
  }
  yield* syncTo(marker, lead);
  cancel(...running);
}

/**
 * Seconds a spring takes to first reach its target. Mirrors Motion Canvas'
 * fixed 120 Hz spring integration, so starting the spring this long before a
 * marker makes the contact frame land exactly on the marker (e.g. a punch
 * connecting on the drum hit), while the overshoot still plays after it.
 */
export function springContactTime(physics: Spring, from: number, to: number): number {
  const dt = 1 / 120;
  let position = from;
  let velocity = physics.initialVelocity ?? 0;
  for (let t = dt; t < 5; t += dt) {
    const force = -physics.stiffness * (position - to) - physics.damping * velocity;
    velocity += (force / physics.mass) * dt;
    position += velocity * dt;
    if (Math.sign(position - to) !== Math.sign(from - to)) return t;
  }
  return 0;
}
