import {cancel, Spring, ThreadGenerator, useLogger, useTime, waitFor} from '@motion-canvas/core';

/**
 * A named-time timeline bound to an audio track. Every action waits for an
 * absolute time from the track (a marker, an event, or a narration edge such
 * as "n14.end"), so retiming one beat never shifts the rest.
 */
export interface Timeline<Key extends string> {
  /** Absolute time of a key in seconds, optionally shifted by beats. */
  at(key: Key, beats?: number): number;
  /** Length of one beat in seconds. */
  readonly beat: number;
  /**
   * Wait until the clock reaches `key - lead`. Logs a warning if the timeline
   * is already past it, which means the action before it overran.
   */
  syncTo(key: Key | number, lead?: number): ThreadGenerator;
  /**
   * Run `tasks` in the background and cut them off at `key - lead`, so a
   * ringing spring tail can never delay the next beat.
   */
  playUntil(key: Key | number, lead: number, ...tasks: ThreadGenerator[]): ThreadGenerator;
}

export function createTimeline<Key extends string>(
  times: Record<Key, number>,
  bpm: number,
): Timeline<Key> {
  const resolve = (key: Key | number) => (typeof key === 'number' ? key : times[key]);

  function* syncTo(key: Key | number, lead = 0): ThreadGenerator {
    const target = resolve(key);
    if (target === undefined) {
      useLogger().error(`timeline: unknown key "${String(key)}"`);
      return;
    }
    const remaining = target - lead - useTime();
    if (remaining > 0) {
      yield* waitFor(remaining);
    } else if (remaining < -1 / 120) {
      useLogger().warn(
        `syncTo("${String(key)}"${lead ? `, lead ${lead.toFixed(3)}` : ''}) reached ` +
          `${(-remaining * 1000).toFixed(0)} ms late - shorten the action before it`,
      );
    }
  }

  function* playUntil(key: Key | number, lead: number, ...tasks: ThreadGenerator[]): ThreadGenerator {
    const running: ThreadGenerator[] = [];
    for (const task of tasks) {
      running.push((yield task) as ThreadGenerator);
    }
    yield* syncTo(key, lead);
    cancel(...running);
  }

  return {
    at: (key, beats = 0) => resolve(key) + beats * (60 / bpm),
    beat: 60 / bpm,
    syncTo,
    playUntil,
  };
}

/**
 * Seconds a spring takes to first reach its target. Mirrors Motion Canvas'
 * fixed 120 Hz spring integration, so starting the spring this long before a
 * beat makes the contact frame land exactly on it (a fist or blade connecting
 * on the hit), while the overshoot still plays after it.
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
