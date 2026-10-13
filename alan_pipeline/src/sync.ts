import track from '../audio/master_track.markers.json';
import {createTimeline} from './timeline';

export {springContactTime} from './timeline';

export type Marker = keyof typeof track.markers;

/** Transient markers from the master audio track, in seconds. */
export const markers = track.markers;

const timeline = createTimeline<Marker>(markers, track.bpm);

/** Length of one beat in seconds. */
export const beat = timeline.beat;

/** Absolute time of an audio marker, optionally shifted by whole/partial beats. */
export const at = timeline.at;

/** Wait until the scene clock reaches an audio marker (see Timeline.syncTo). */
export const syncTo = timeline.syncTo;

/** Play reactions until a marker, then cut them off (see Timeline.playUntil). */
export const playUntil = timeline.playUntil;
