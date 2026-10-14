import {Node, Rect, Txt} from '@motion-canvas/2d';
import {all, easeInCubic, easeInOutCubic, easeInOutSine, easeOutBack, easeOutCubic, ThreadGenerator, useTime, Vector2, waitFor} from '@motion-canvas/core';
import {Pose} from '../../components/StickFigure';
import {withAlpha} from '../../figureSpec';
import {STAND} from '../../first_light/acts/dark';
import {standHeight} from '../../first_light/acts/sandbox';
import {reach, Stage} from '../../first_light/stage';
import {at, G, racePlan, shadow, syncTo} from '../cues';
import {Typography} from '../../styles';
import {BitBlock, buildCity, HomeDoor, rand, Shadow, WORLD} from '../components/World';

/** The hub of the computer world. The race road starts here and runs to +x. */
export const HUB = new Vector2(10000, 0);
/** Where Spark's car starts (its centre), and the race's road positions are measured from. */
export const ROAD_X0 = HUB.x - 100;
const LAND_X = HUB.x - 560;
const PEDESTAL_X = HUB.x - 270;
export const SPARK_HUB_X = HUB.x - 340;
export const SHADOW_X = HUB.x + 150;
export const DOOR_X = HUB.x + 520;
/** The far side of the broken bridge sits higher by the kicker's rise, so the jump lands level. */
export const KICK_LEN = 80;
export const KICK_RISE = KICK_LEN * Math.tan((racePlan.numbers.rampAngle * Math.PI) / 180);

export interface Hub {
  city: Node;
  shadow: Shadow;
  door: HomeDoor;
  ripple: BitBlock[];
  pedestal: BitBlock[];
  say: (text: string | null) => void;
  type: (cue: string, text: string) => ThreadGenerator;
}

/** Big red terminal text: the Shadow speaks only in typed lines (CPS 12, one tick per character). */
function shadowSpeech(s: Stage): {node: Node; say: (text: string | null) => void; type: (cue: string, text: string) => ThreadGenerator} {
  const node = new Node({y: -390, opacity: 0});
  const panel = new Rect({width: 1300, height: 110, radius: 10, fill: withAlpha('#0b0204', 0.85), stroke: WORLD.red, lineWidth: 3});
  const txt = new Txt({text: '', fontFamily: Typography.mono, fontWeight: 800, fontSize: 56, letterSpacing: 4, fill: WORLD.eye, shadowColor: WORLD.eye, shadowBlur: 12});
  node.add([panel, txt]);
  s.view.add(node);
  s.hud.moveToTop();
  return {
    node,
    say: text => {
      txt.text(text ?? '');
      node.opacity(text ? 1 : 0);
    },
    *type(cue, text) {
      node.opacity(1);
      const t0 = at(cue as never);
      while (useTime() < t0 + text.length / 12 - 1e-6) {
        const n = Math.min(text.length, Math.floor((useTime() - t0) * 12 + 1e-6) + 1);
        txt.text(text.slice(0, n) + (n < text.length ? '_' : ''));
        yield;
      }
      txt.text(text);
    },
  };
}

/** The computer world's set: the city, the flip row, the pedestal, the Shadow, the door, the speech panel. */
export function buildHub(s: Stage): Hub {
  const raised: [number, number, number][] = [[ROAD_X0 + racePlan.numbers.lip + racePlan.numbers.gap - 1, ROAD_X0 + racePlan.numbers.xDoor + 3000, KICK_RISE]];
  const gap: [number, number] = [ROAD_X0 + racePlan.numbers.lip, ROAD_X0 + racePlan.numbers.lip + racePlan.numbers.gap];
  const city = buildCity(s.back, () => s.time(), HUB.x - 2200, ROAD_X0 + racePlan.numbers.xDoor + 2400, [gap], raised);
  // The flip-ripple row: blocks set into the floor's facade.
  const ripple: BitBlock[] = [];
  for (let x = HUB.x - 1300; x <= HUB.x + 1100; x += 44) {
    const b = new BitBlock({size: 40, bit: rand() < 0.5 ? 0 : 1, x, y: 324});
    city.add(b);
    ripple.push(b);
  }
  const pedestal = [275, 225, 175].map((y, i) => new BitBlock({size: 50, bit: i === 2 ? 0 : 1, x: PEDESTAL_X, y}));
  pedestal.forEach(b => city.add(b));
  const shadowFig = new Shadow({x: SHADOW_X, y: 300});
  shadowFig.rise(0);
  shadowFig.open(0);
  s.props.add(shadowFig);
  const door = new HomeDoor({x: DOOR_X, y: 300, scale: 0});
  s.props.add(door);
  const speech = shadowSpeech(s);

  return {city, shadow: shadowFig, door, ripple, pedestal, say: speech.say, type: speech.type};
}

/**
 * 64 - 92 s. Spark falls into the computer world: a city of binary blocks.
 * He gets up, looks around, walks, and touches a block: it flips 0 -> 1 and
 * the flip runs along the floor. Then a glitch, and the Shadow rises: it
 * types its rules in red, and a door with Spark's room in it appears, locked
 * by three lights. Spark sets his feet.
 */
export function* worldAct(s: Stage, hub: Hub): ThreadGenerator {
  const spark = s.spark.body;
  const {city, shadow: shadowFig, door, ripple, pedestal} = hub;
  const speech = {say: hub.say, type: hub.type};
  // ---- Spark arrives: a free fall from above the frame onto the floor.
  spark.remove();
  s.cast.add(spark);
  spark.scale([0.8, 0.8]);
  spark.rotation(0);
  spark.opacity(1);
  spark.face(1);
  s.room(0.35);
  s.lightColor(WORLD.bit);
  s.lightAt(HUB.add([-300, 0]));
  s.cam(new Vector2(LAND_X + 100, 90));
  s.zoom(1.35);
  const standY = standHeight(s, spark);
  const startY = -520;
  const tFall = Math.sqrt((2 * (standY - startY)) / G);
  const t0 = at('land') - tFall;
  spark.setPose({...STAND, leftShoulder: -160, rightShoulder: -150, leftElbow: -20, rightElbow: -30, leftHip: -20, leftKnee: 30, rightHip: 10, rightKnee: 20});
  spark.position(new Vector2(LAND_X, startY));
  while (useTime() < t0 - 0.3) yield;
  s.spawn(s.whiteout.opacity(0, 0.3, easeOutCubic));
  while (useTime() < at('land') - 1e-6) {
    const u = Math.max(0, useTime() - t0);
    spark.y(startY + 0.5 * G * u * u);
    yield;
  }
  spark.y(standY);
  // Landing: knees take the impact (3 frames down, then up slowly).
  const CROUCH: Pose = {...STAND, torso: 24, head: -10, leftHip: -60, leftKnee: 100, rightHip: -40, rightKnee: 90, leftShoulder: 30, rightShoulder: 20};
  s.spawn(shake(s, 7, 6));
  s.spawn(rippleFrom(s, ripple, LAND_X, 0.5, false));
  yield* all(spark.pose(CROUCH, 3 / 60), spark.y(standY + 40, 3 / 60));
  yield* waitFor(0.3);
  yield* all(spark.pose(STAND, 0.5, easeInOutSine), spark.y(standY, 0.5, easeInOutSine));

  // ---- Where am I? Look left, look right, look up; the camera opens on the city.
  yield* syncTo('look', 0);
  s.spawn(all(s.cam(new Vector2(HUB.x - 300, 40), 2.4, easeInOutSine), s.zoom(1.0, 2.4, easeInOutSine)));
  yield* spark.face(-1, 0.2);
  yield* spark.joints.head(-14, 0.4, easeInOutSine);
  yield* waitFor(0.3);
  yield* spark.face(1, 0.2);
  yield* spark.pose({head: -26, torso: -6}, 0.4, easeInOutSine);

  // ---- Walk to the glowing block on its pedestal, and touch it.
  yield* syncTo('walk', 0);
  yield* spark.walkTo(SPARK_HUB_X, {steps: 4, arriveAt: at('touch') - 0.5});
  yield* syncTo('touch', 0.3);
  const touchAt = new Vector2(PEDESTAL_X - 25, 175);
  yield* spark.pose(reach(s, spark, 'rightArm', touchAt, {...STAND, head: 4, torso: 6}), 0.3, easeOutCubic);
  pedestal[2].bit(1);
  pedestal[2].glow(1);
  s.spawn(pedestal[2].glow(0.3, 0.8));
  s.spawn(rippleFrom(s, ripple, PEDESTAL_X, 1, true));
  yield* spark.pose({...STAND, torso: -6, head: -12, rightShoulder: -30, rightElbow: -40}, 0.25, easeOutCubic);

  // ---- Wonder: the flip runs away along the floor. Spark steps back and watches it go.
  yield* syncTo('wonder', 0);
  yield* spark.walkTo(SPARK_HUB_X - 40, {mode: 'backward', steps: 1, duration: 0.4});
  yield* spark.pose({...STAND, head: -20, torso: -8, leftShoulder: -40, leftElbow: -100}, 0.5, easeInOutSine);
  yield* spark.joints.head(-34, 0.8, easeInOutSine);

  // ---- The glitch: everything turns red. The Shadow rises out of the floor.
  yield* syncTo('glitch', 0);
  s.spawn(shake(s, 10, 10));
  for (const b of [...ripple, ...pedestal]) b.color(WORLD.red);
  s.lightColor(WORLD.red);
  s.spawn(flicker(city));
  yield* spark.pose({...STAND, torso: -14, head: -20, leftShoulder: -60, leftElbow: -110, rightShoulder: -50, rightElbow: -120, leftHip: 16, rightHip: -14}, 0.1, easeOutBack);
  yield* syncTo('rise', 0);
  s.spawn(all(s.cam(new Vector2(HUB.x - 90, -20), 1.4, easeInOutCubic), s.zoom(0.95, 1.4, easeInOutCubic)));
  yield* shadowFig.rise(1, 1.3, easeOutCubic);
  // One red eye opens and finds Spark.
  yield* syncTo('eye', 0);
  yield* shadowFig.open(1, 0.25, easeOutBack);
  yield* shadowFig.look(-1, 0.3, easeInOutCubic);

  // ---- The rules, typed in red.
  const lines = shadow;
  yield* syncTo('say1', 0);
  s.spawn(shadowFig.armL(70, 0.4, easeOutCubic));
  yield* speech.type('say1', lines[0]);
  yield* syncTo('say2', 0);
  s.spawn(all(shadowFig.armL(30, 0.4), shadowFig.armR(-30, 0.4)));
  yield* speech.type('say2', lines[1]);
  yield* syncTo('say3', 0);
  s.spawn(speech.type('say3', lines[2]));
  // The door home appears (the Shadow points at it), locked by three lights.
  yield* syncTo('door0', 0.3);
  yield* shadowFig.armR(-80, 0.3, easeOutCubic);
  s.spawn(door.scale(1, 0.4, easeOutBack));
  yield* spark.pose({...STAND, head: -16, torso: -2}, 0.3, easeInOutSine);
  yield* syncTo('say4', 0);
  s.spawn(all(shadowFig.armR(-12, 0.4), shadowFig.armL(60, 0.4)));
  s.spawn(speech.type('say4', lines[3]));
  // LOSE - YOU ARE DELETED. Spark steps back.
  yield* syncTo('stepBack', 0);
  yield* spark.walkTo(SPARK_HUB_X - 120, {mode: 'backward', steps: 2, duration: 0.6});
  yield* spark.pose({...STAND, torso: -10, head: -6, leftShoulder: -40, leftElbow: -110, rightShoulder: -30, rightElbow: -120}, 0.2, easeOutCubic);
  // Then sets his feet: fists up, a nod. Game on.
  yield* syncTo('setFeet', 0);
  speech.say(null);
  const GUARD: Pose = {...STAND, torso: 8, head: -4, leftHip: 18, leftKnee: 16, rightHip: -22, rightKnee: 20, leftShoulder: -70, leftElbow: -120, rightShoulder: -60, rightElbow: -130};
  yield* spark.pose(GUARD, 0.25, easeOutBack);
  yield* spark.joints.head(10, 0.15).to(-4, 0.2);
}

/** A flip wave from x along the facade row, at 600 units/s. */
function* rippleFrom(s: Stage, row: BitBlock[], x: number, strength: number, flip: boolean): ThreadGenerator {
  const t0 = useTime();
  const pending = new Set(row);
  while (pending.size) {
    const d = (useTime() - t0) * 600;
    for (const b of [...pending]) {
      if (Math.abs(b.x() - x) <= d) {
        pending.delete(b);
        if (flip) b.bit(1 - b.bit());
        b.glow(strength);
        s.spawn(b.glow(0, 0.6, easeInCubic));
      }
    }
    if (d > 2600) break;
    yield;
  }
}

function* flicker(n: Node): ThreadGenerator {
  for (const o of [0.4, 1, 0.6, 1]) {
    n.opacity(o);
    yield* waitFor(2 / 60);
  }
}

export function* shake(s: Stage, px: number, frames: number): ThreadGenerator {
  for (let i = 0; i < frames; i++) {
    const a = i * 2.4;
    s.shake(new Vector2(Math.cos(a), Math.sin(a)).scale(px * (1 - i / frames)));
    yield;
  }
  s.shake(Vector2.zero);
}

export {easeInOutCubic};
