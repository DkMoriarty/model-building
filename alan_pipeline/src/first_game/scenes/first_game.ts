import {makeScene2D} from '@motion-canvas/2d';
import {all, ThreadGenerator} from '@motion-canvas/core';
import {frameAuditor} from '../../first_light/audit';
import {buildStage, Stage} from '../../first_light/stage';
import {insideAct} from '../acts/inside';
import {buildMonitor, pullIn, roomAct} from '../acts/room';
import {wakeAct} from '../acts/wake';
import {Room} from '../components/Room';
import {at, duration} from '../cues';

/**
 * FIRST GAME. Spark wants to play; there is no game, so Spark writes one.
 * Asleep at the desk, Spark falls into it and must beat every level to get
 * home: fail, fail, fail, GAME OVER, continue, win. The dream breaks, and
 * awake, Spark beats level 3 for real. Picture and sound share one
 * timeline, built from audio/first_game/story.json.
 */
export default makeScene2D(function* (view) {
  const stage = buildStage(view, 'FIRST GAME');
  // Deliberate exits from the frame, each with its reason.
  stage.spawn(
    frameAuditor(stage, duration, [
      [at('pull') + 0.7, at('inside'), 'Spark is drawn into the screen'],
      [at('seeDoor'), at('gulp') - 0.3, 'the camera looks at the door home'],
      [at('clock3'), at('lookScreen'), 'cut-in to the clock'],
      [at('hurt1') - 0.3, at('respawn1'), 'falls into the pit'],
      [at('drop2'), at('respawn2'), 'rides the platform down into the pit'],
      [at('hurt3') - 0.3, at('slumpGO'), 'falls into the pit'],
      [at('drop4'), at('boing4') + 0.2, 'drops with the platform to the spring'],
      [at('shatter'), at('wake'), 'the dream shatters'],
    ], 1.8),
  );
  yield* all(story(stage), stage.runner(duration));
});

function* story(s: Stage): ThreadGenerator {
  const room = new Room({});
  s.back.add(room);
  const m = buildMonitor(s, room);
  yield* roomAct(s, room, m);
  yield* pullIn(s, room);
  yield* insideAct(s);
  yield* wakeAct(s, room, m);
}
