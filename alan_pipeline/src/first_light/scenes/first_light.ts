import {makeScene2D} from '@motion-canvas/2d';
import {all, createSignal, easeOutBack, ThreadGenerator, Vector2} from '@motion-canvas/core';
import {dark, TIP} from '../acts/dark';
import {Lamp, sandbox} from '../acts/sandbox';
import {logic} from '../acts/logic';
import {boardAct, Lab} from '../acts/board';
import {mind} from '../acts/mind';
import {Bulb, Wire} from '../components/Circuit';
import {duration} from '../cues';
import {frameAuditor} from '../audit';
import {buildStage, Stage} from '../stage';

/**
 * FIRST LIGHT. Spark wants light, learns electricity by being zapped, wires
 * switches into logic and logic into a lamp that learns, and by accident
 * gives it a mind. Picture and sound share one timeline, built from
 * audio/first_light/story.json.
 */
export default makeScene2D(function* (view) {
  const stage = buildStage(view);
  stage.spawn(frameAuditor(stage, duration));
  yield* all(story(stage), stage.runner(duration));
});

function* story(s: Stage): ThreadGenerator {
  const bulb = new Bulb({});
  s.props.add(bulb);
  // The cable is two leads side by side; they splay apart at the end later.
  const lift = createSignal(-900);
  const spread = createSignal(0);
  const aEnd = Vector2.createSignal(() => TIP.add([0, lift()]));
  const bEnd = Vector2.createSignal(() => TIP.add([8 + 46 * spread(), lift() - 10 * spread()]));
  const top = (dx: number) => new Vector2(TIP.x + dx, -1200 + lift());
  const leadB = s.wire(new Wire({points: () => [top(8), new Vector2(TIP.x + 8, TIP.y - 70 + lift()), bEnd()], time: () => s.time()}));
  leadB.beads(0);
  const leadA = s.wire(new Wire({points: () => [top(0), aEnd()], time: () => s.time()}));
  s.props.add([leadB, leadA]);
  const drop = (v: number, d: number) => lift(v, d, easeOutBack);
  const lamp: Partial<Lamp> = {bulb, leadA, leadB};
  yield* dark(s, bulb, leadA, drop);
  yield* sandbox(s, bulb, leadA, leadB, aEnd, bEnd, (v, d) => spread(v, d, easeOutBack), lamp);
  // Cut: the sandbox set-up is gone; Spark has moved the loop onto the wall.
  yield* logic(s, () => s.props.removeChildren());
  const lab: Partial<Lab> = {};
  yield* boardAct(s, lab);
  yield* mind(s, lab as Lab);
}
