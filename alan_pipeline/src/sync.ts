import {ThreadGenerator, useTime, waitFor} from '@motion-canvas/core';
import track from '../audio/master_track.markers.json';

export type Marker = keyof typeof track.markers;

/** Transient markers from the master audio track, in seconds. */
export const markers = track.markers;

/**
 * Wait until the scene clock reaches an audio marker. Anchoring beats to
 * absolute times (rather than chaining durations) means retiming one action
 * never shifts every hit after it off the music.
 */
export function* syncTo(marker: Marker, lead = 0): ThreadGenerator {
  const remaining = markers[marker] - lead - useTime();
  if (remaining > 0) {
    yield* waitFor(remaining);
  }
}
