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
 * FIRST GAME. Spark wants to play; there is no game. Spark types hello world,
 * then invents ping pong line by line: a ball, a move, walls, a paddle, a
 * glitch, an opponent. Asleep, Spark falls into the game, wins two levels,
 * loses the third to an unbeatable paddle, and wins with the glitch. The
 * dream breaks; awake, Spark wins for real. One timeline, built from
 * audio/first_game/story.json by tools/first_game_timeline.py.
 */
export default makeScene2D(function* (view) {
  const stage = buildStage(view, 'FIRST GAME');
  stage.spawn(
    frameAuditor(stage, duration, [
      [at('pull') + 0.7, at('inside'), 'Spark is drawn into the screen'],
      [at('clock1') - 0.5, at('play2'), 'cut-in to the clock'],
      [at('clock3'), at('lookScreen'), 'cut-in to the clock'],
      [at('seeDoor'), at('l1'), 'the camera looks at the door home'],
      [at('gulp'), at('p1'), 'the camera looks at the computer paddle'],
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
  yield* pullIn(s);
  yield* insideAct(s);
  yield* wakeAct(s, room, m);
}
