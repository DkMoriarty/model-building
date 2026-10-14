import {makeScene2D} from '@motion-canvas/2d';
import {all, ThreadGenerator} from '@motion-canvas/core';
import {frameAuditor} from '../../first_light/audit';
import {buildStage, Stage} from '../../first_light/stage';
import {homeAct} from '../acts/home';
import {raceAct} from '../acts/race';
import {buildMonitor, pullIn, roomAct} from '../acts/room';
import {roundsAct} from '../acts/rounds';
import {buildHub, worldAct} from '../acts/world';
import {Room} from '../components/Room';
import {at, duration} from '../cues';

/**
 * FIRST GAME. Spark wants to play; there is no game. Spark types hello world,
 * then invents ping pong line by line, plays it, and beats the computer. The
 * computer wakes up: it learns, gets angry, and pulls Spark into its world.
 * The Shadow sets the rules: win three games to go home. Ping pong (won with
 * the glitch), a runner, a dodge; then a race for the key. The door opens on
 * Spark's room, the sun comes up, and Spark sees himself waking up. One
 * timeline, built from audio/first_game/story.json by tools/first_game_timeline.py.
 */
export default makeScene2D(function* (view) {
  const stage = buildStage(view, 'FIRST GAME');
  stage.spawn(
    frameAuditor(stage, duration, [
      [at('pull') + 0.7, at('land'), 'Spark is drawn into the screen, and falls into the computer world'],
      [at('portal1'), at('r1') + 0.4, 'portal to round 1'],
      [at('portal2'), at('r2') + 0.4, 'portal to round 2'],
      [at('portal3'), at('r3') + 0.4, 'portal to round 3'],
      [at('keyShow'), at('point') + 0.5, 'the camera follows the door to the end of the road'],
      [at('through'), at('home'), 'through the door, home'],
    ], 1.8),
  );
  yield* all(story(stage), stage.runner(duration));
});

function* story(s: Stage): ThreadGenerator {
  const room = new Room({});
  s.back.add(room);
  const m = buildMonitor(s, room);
  yield* roomAct(s, room, m);
  yield* pullIn(s, m);
  const hub = buildHub(s);
  yield* worldAct(s, hub);
  yield* roundsAct(s, hub);
  yield* raceAct(s, hub);
  yield* homeAct(s, room, m);
}
