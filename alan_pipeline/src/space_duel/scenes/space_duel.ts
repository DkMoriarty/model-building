import {makeScene2D} from '@motion-canvas/2d';
import {all, ThreadGenerator} from '@motion-canvas/core';
import {ambient} from '../acts/ambient';
import {frameAuditor} from '../audit';
import {arrival} from '../acts/arrival';
import {departure} from '../acts/departure';
import {fight} from '../acts/fight';
import {duration, narration, syncTo} from '../cues';
import {buildStage, Stage} from '../stage';

/**
 * THE ENTANGLED BLADE. A ~3 minute space duel. Picture, narration, music and
 * every sound effect are locked to one timeline built from
 * audio/space_duel/story.json by tools/build_space_audio.py.
 */
export default makeScene2D(function* (view) {
  const stage = buildStage(view);
  stage.spawn(ambient(stage));
  stage.spawn(frameAuditor(stage, duration));
  yield* all(story(stage), subtitles(stage), stage.runner(duration));
});

function* story(s: Stage): ThreadGenerator {
  yield* arrival(s);
  yield* fight(s);
  yield* departure(s);
}

/** Subtitles appear exactly while each line is being spoken. */
function* subtitles(s: Stage): ThreadGenerator {
  for (const line of narration) {
    yield* syncTo(line.start);
    yield* s.subs.say(line.text, line.voice, line.end, line.start);
  }
}
