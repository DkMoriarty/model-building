import {Circle, Line, Node, Rect, Txt} from '@motion-canvas/2d';
import {
  all,
  createSignal,
  easeInCubic,
  easeInOutCubic,
  easeInOutSine,
  easeOutCubic,
  linear,
  ThreadGenerator,
  useLogger,
  useTime,
  Vector2,
  waitFor,
} from '@motion-canvas/core';
import {JOINTS, Pose, StickFigure} from '../../components/StickFigure';
import {Colors, Typography} from '../../styles';
import {Blade} from '../components/Blade';
import {exhaust, sparks} from '../components/Effects';
import {ALIEN_BLADE, ALIEN_COLOR, Fighter, KEEPER_BLADE} from '../components/Fighters';
import {at, Cue, syncTo} from '../cues';
import {tunnelProbability} from '../physics';
import {bindToCentreOfMass, bladeContact, everyFrame, inertia, separationOf, Stage, toWorldLocal} from '../stage';

const GUARD: Pose = {
  torso: 10,
  head: 0,
  rightShoulder: -60,
  rightElbow: -40,
  leftShoulder: -40,
  leftElbow: -70,
  leftHip: -30,
  leftKnee: 40,
  rightHip: 15,
  rightKnee: 30,
};

type Style = 'high' | 'mid' | 'low';
/** Wind-up and contact poses (authored facing +x; the alien is mirrored). */
const STYLES: Record<Style, {windup: Pose; strike: Pose; grip: number}> = {
  high: {
    windup: {rightShoulder: 150, rightElbow: -50, torso: -12, leftShoulder: -60},
    strike: {rightShoulder: 235, rightElbow: -15, torso: 14, leftShoulder: 20},
    grip: -60,
  },
  mid: {
    windup: {rightShoulder: -10, rightElbow: -120, torso: -6, leftShoulder: -70},
    strike: {rightShoulder: -88, rightElbow: -5, torso: 16, leftShoulder: 30},
    grip: -75,
  },
  low: {
    windup: {rightShoulder: 45, rightElbow: -40, torso: -4, leftShoulder: -50},
    strike: {rightShoulder: -45, rightElbow: -15, torso: 20, leftShoulder: 25},
    grip: -100,
  },
};

const CONTACT_TOLERANCE = 14;

/** Distance from point p to segment ab. */
function segmentPointDistance(a: Vector2, b: Vector2, p: Vector2): number {
  const ab = b.sub(a);
  const t = Math.max(0, Math.min(1, p.sub(a).dot(ab) / Math.max(1e-6, ab.squaredMagnitude)));
  return p.sub(a.add(ab.scale(t))).magnitude;
}

/** The figure's current joint angles as a Pose. */
function currentPose(f: Fighter): Pose {
  return Object.fromEntries(JOINTS.map(j => [j, f.body.joints[j]()])) as Pose;
}

/** Snapshot every joint + grip so poses can be tried and restored in one frame. */
function snapshot(f: Fighter): () => void {
  const joints = JOINTS.map(j => [j, f.body.joints[j]()] as const);
  const grip = f.blade.rotation();
  return () => {
    for (const [j, v] of joints) f.body.joints[j](v);
    f.blade.rotation(grip);
  };
}

/**
 * Separation (x, along the line between them) at which the two blades just
 * cross when both fighters are in the given poses. Tried in place and
 * restored within the same frame, so nothing is ever drawn in the trial pose.
 * Picks the widest separation that still makes contact: blades meet near
 * their tips, the way real fencers engage.
 */
function solveContactSep(
  s: Stage,
  keeperPose: Pose,
  alienPose: Pose,
  keeperGrip: number,
  alienGrip: number,
  sepY: number,
  bladeOverride?: (b: Blade) => void,
  gap: () => number = () => bladeContact(s.keeper.blade, s.alien.blade).distance,
  quiet = false,
): number {
  const restoreK = snapshot(s.keeper);
  const restoreA = snapshot(s.alien);
  const sep0 = s.sep();
  s.keeper.body.setPose(keeperPose);
  s.alien.body.setPose(alienPose);
  s.keeper.blade.rotation(keeperGrip);
  s.alien.blade.rotation(alienGrip);
  bladeOverride?.(s.alien.blade);
  let best = NaN;
  let closest = {x: 420, gap: Infinity};
  for (let x = 760; x >= 120; x -= 3) {
    s.sep(new Vector2(x, sepY));
    const g = gap();
    if (g < closest.gap) closest = {x, gap: g};
    if (g < 6) {
      best = x;
      break;
    }
  }
  if (Number.isNaN(best) && !quiet) {
    // No separation makes contact with these poses: use the nearest miss and say so.
    useLogger().warn(`contact solver: poses never touch (closest ${closest.gap.toFixed(0)} px at sep ${closest.x})`);
    best = closest.x;
  }
  s.sep(sep0);
  restoreK();
  restoreA();
  return best;
}

function* checkContact(s: Stage, id: string, a: Blade = s.keeper.blade, b: Blade = s.alien.blade): Generator<never, Vector2> {
  const contact = bladeContact(a, b);
  if (contact.distance > CONTACT_TOLERANCE) {
    useLogger().warn(`contact "${id}": blades miss by ${contact.distance.toFixed(0)} px`);
  }
  return contact.point;
}

/** Impact shake: 4 single-frame jolts of ~8 px, then rest (style bible, section 4). */
function* shake(s: Stage, strength = 1): ThreadGenerator {
  const f = 1 / 60;
  for (const [dx, dy] of [
    [8, -4],
    [-6, 3],
    [4, -2],
    [-2, 1],
  ]) {
    s.shake(new Vector2(dx * strength, dy * strength));
    yield* waitFor(f);
  }
  s.shake(Vector2.zero);
}

/** 2-frame white-out, reserved for the biggest hits. */
function* whiteout(s: Stage, strength = 0.8): ThreadGenerator {
  s.whiteout.opacity(strength);
  yield* waitFor(1 / 60);
  s.whiteout.opacity(strength * 0.4);
  yield* waitFor(1 / 60);
  s.whiteout.opacity(0);
}

/**
 * Smear trails: an arc traced through the blade tip's last 5 positions, like
 * a hand-drawn swipe line. Brightness scales with tip speed, so slow moves
 * leave nothing (style bible, section 3).
 */
function* smearTrails(s: Stage, until: number): ThreadGenerator {
  const toLocal = (p: Vector2) => toWorldLocal(s, p);
  const trails = [
    {blade: s.keeper.blade, color: KEEPER_BLADE},
    {blade: s.alien.blade, color: ALIEN_BLADE},
  ].map(({blade, color}) => {
    const arc = new Line({points: [], stroke: color, lineWidth: 5, lineCap: 'round', lineJoin: 'round', opacity: 0});
    s.world.add(arc);
    arc.moveBelow(s.alien.body);
    return {blade, arc, history: [] as Vector2[]};
  });
  yield* everyFrame(until, () => {
    for (const t of trails) {
      t.history.push(toLocal(t.blade.tip()));
      if (t.history.length > 5) t.history.shift();
      if (t.history.length < 2) continue;
      const speed = t.history[t.history.length - 1].sub(t.history[0]).magnitude / (t.history.length - 1);
      t.arc.opacity(Math.max(0, Math.min(0.55, (speed - 12) / 80)));
      t.arc.points([...t.history]);
    }
  });
  for (const t of trails) t.arc.remove();
}

/** A thruster burn: exhaust from the pack while the separation eases to its target. */
function* burn(s: Stage, target: Vector2, duration: number): ThreadGenerator {
  const closing = target.x < s.sep().x;
  // Exhaust puffs outlive the burn; run them in the background so they never delay a beat.
  s.spawn(exhaust(s.fx, () => s.keeper.body.bones.torso.absolutePosition(), new Vector2(closing ? -1 : 1, 0), duration * 0.7));
  s.spawn(exhaust(s.fx, () => s.alien.body.absolutePosition(), new Vector2(closing ? 1 : -1, 0), duration * 0.7));
  yield* s.sep(target, duration, easeInOutSine);
}

interface ExchangeOptions {
  keeper?: Style;
  alien?: Style;
  sepY?: number;
  /** Extra separation gained in the recoil coast (px). */
  recoil?: number;
  sparkScale?: number;
  shakeStrength?: number;
  /** Contact measures the traveller's blade: its superposition collapses. */
  collapse?: boolean;
}

/**
 * One exchange that connects exactly on cue `id`: thrusters close to the
 * solved contact distance, both fighters wind up and swing, the blades meet
 * on the frame, and the impulse sends them apart (linear coast: no forces
 * act between pushes, so velocity is constant).
 */
function* exchange(s: Stage, id: Cue, o: ExchangeOptions = {}): ThreadGenerator {
  const T = at(id);
  const k = STYLES[o.keeper ?? 'mid'];
  const a = STYLES[o.alien ?? o.keeper ?? 'mid'];
  const sepY = o.sepY ?? 0;
  const sepX = solveContactSep(s, {...GUARD, ...k.strike}, {...GUARD, ...a.strike}, k.grip, a.grip, sepY);
  const approach = Math.max(0.3, T - useTime() - 0.05);

  yield* all(
    burn(s, new Vector2(sepX, sepY), approach),
    swing(s.keeper, k, T),
    swing(s.alien, a, T),
  );
  const point = yield* checkContact(s, id);
  if (o.collapse) {
    // Measurement is instantaneous: every branch but one vanishes this frame.
    s.alien.blade.spread(0);
    const ring = new Circle({size: 40, stroke: ALIEN_BLADE, lineWidth: 4});
    s.fx.add(ring);
    ring.absolutePosition(point);
    s.spawn(all(ring.size(260, 0.5, easeOutCubic), ring.opacity(0, 0.5)));
  }
  const recoil = o.recoil ?? 160;
  if ((o.sparkScale ?? 1) >= 1.3) s.spawn(whiteout(s));
  // Contact hold: both freeze on the hit for 3 frames before the recoil reads.
  s.spawn(sparks(s.fx, point, '#ffd27a', o.sparkScale ?? 1));
  s.spawn(shake(s, o.shakeStrength ?? 1));
  yield* waitFor(3 / 60);
  s.spawn(all(
    s.sep(s.sep().add([recoil, 0]), 0.6, linear),
    s.keeper.body.pose(GUARD, 0.45, easeOutCubic),
    s.alien.body.pose(GUARD, 0.45, easeOutCubic),
  ));
  yield* waitFor(0.6);
}

/** Wind up, then swing so the strike pose is reached exactly at `T`. */
function* swing(f: Fighter, style: {windup: Pose; strike: Pose; grip: number}, T: number, windup = 0.3, strike = 0.18): ThreadGenerator {
  yield* syncTo(T, windup + strike + 0.05);
  yield* all(f.body.pose(style.windup, windup, easeOutCubic), f.blade.rotation(style.grip, windup));
  yield* syncTo(T, strike);
  yield* f.body.pose(style.strike, strike, easeInCubic);
}

export function* fight(s: Stage): ThreadGenerator {
  yield* syncTo('fight');
  // Centre-of-mass frame. Momentum is conserved, so this point never moves.
  const kp = s.keeper.body.position();
  const ap = s.alien.body.position();
  s.com(kp.scale(1 / 2.5).add(ap.scale(1.5 / 2.5)));
  s.sep(ap.sub(kp));
  bindToCentreOfMass(s);
  s.spawn(smearTrails(s, at('disarm')));
  // Frame the centre of mass at the live zoom, so it stays centred mid-zoom.
  s.world.position(() => s.com().scale(-s.world.scale().x).add(s.shake()));
  yield* all(
    s.world.scale(1.2, 1.5, easeInOutCubic),
    s.label.show('frame: centre of mass', 'no outside force acts, so this point never moves'),
  );

  // --- Momentum ----------------------------------------------------------
  yield* exchange(s, 'clash1', {keeper: 'high'});
  yield* exchange(s, 'clash2', {keeper: 'low', sepY: 20});
  yield* exchange(s, 'clash3', {keeper: 'mid', recoil: 260, sparkScale: 1.3, shakeStrength: 1.4});
  s.spawn(momentumArrows(s));
  yield* syncTo('lblMomentum');
  yield* s.label.show('m₁Δv₁ = −m₂Δv₂', 'equal and opposite: the lighter keeper flies 1.5× faster');
  yield* exchange(s, 'clash4', {keeper: 'high', sepY: -20});
  yield* exchange(s, 'clash5', {keeper: 'low'});

  // --- Angular momentum ---------------------------------------------------
  yield* exchange(s, 'clash6', {keeper: 'high', recoil: 220, sparkScale: 1.3, shakeStrength: 1.3});
  yield* spin(s);
  yield* exchange(s, 'clash7', {keeper: 'mid', recoil: 200, sparkScale: 1.2});

  // --- Superposition and measurement -------------------------------------
  yield* superposition(s);

  // --- Tunnelling ----------------------------------------------------------
  yield* tunnelling(s);

  // --- Flurry --------------------------------------------------------------
  const flurry: [Cue, Style, Style][] = [
    ['f1', 'high', 'high'],
    ['f2', 'low', 'low'],
    ['f3', 'mid', 'mid'],
    ['f4', 'high', 'high'],
    ['f5', 'low', 'low'],
    ['f6', 'mid', 'mid'],
    ['f7', 'high', 'high'],
    ['f8', 'low', 'low'],
    ['f9', 'mid', 'mid'],
    ['f10', 'high', 'high'],
    ['f11', 'low', 'low'],
    ['f12', 'mid', 'mid'],
  ];
  s.world.position(() => s.com().scale(-s.world.scale().x).add(s.shake()));
  s.spawn(s.world.scale(1.35, 0.8, easeInOutCubic));
  for (const [id, ks, as] of flurry) {
    yield* quickStrike(s, id, ks, as);
  }

  // --- Entanglement finale -------------------------------------------------
  yield* finale(s);
}

/** Flurry strike: no approach burn, just a small re-spacing and a fast swing. */
function* quickStrike(s: Stage, id: Cue, ks: Style, as: Style): ThreadGenerator {
  const T = at(id);
  const k = STYLES[ks];
  const a = STYLES[as];
  const sepX = solveContactSep(s, {...GUARD, ...k.strike}, {...GUARD, ...a.strike}, k.grip, a.grip, 0);
  const lead = Math.min(0.38, T - useTime() - 0.02);
  yield* all(
    s.sep(new Vector2(sepX, 0), Math.max(0.1, lead - 0.05), easeInOutSine),
    swing(s.keeper, k, T, lead * 0.55, lead * 0.4),
    swing(s.alien, a, T, lead * 0.55, lead * 0.4),
  );
  const point = yield* checkContact(s, id);
  s.spawn(sparks(s.fx, point, '#ffd27a', 0.8));
  s.spawn(shake(s, 0.6));
  yield* waitFor(2 / 60);
  s.spawn(s.sep(s.sep().add([40, 0]), 0.12, linear));
}

function* momentumArrows(s: Stage): ThreadGenerator {
  const arrow = (fig: StickFigure, dir: number, color: string) => {
    const group = new Node({opacity: 0});
    s.fx.add(group);
    group.position(() => fig.position().add([0, -170]));
    group.add([
      new Line({
        points: [
          [0, 0],
          [dir * 150, 0],
        ],
        stroke: color,
        lineWidth: 6,
        endArrow: true,
        arrowSize: 16,
      }),
      new Txt({x: dir * 75, y: -28, text: 'p', fill: color, fontFamily: Typography.mono, fontSize: 30, fontStyle: 'italic'}),
    ]);
    return group;
  };
  const a1 = arrow(s.keeper.body, -1, Colors.accent);
  const a2 = arrow(s.alien.body, 1, ALIEN_COLOR);
  yield* all(a1.opacity(1, 0.3), a2.opacity(1, 0.3));
  yield* syncTo('momentumEnd');
  yield* all(a1.opacity(0, 0.4), a2.opacity(0, 0.4));
  a1.remove();
  a2.remove();
}

/**
 * The off-centre hit at clash6 leaves the keeper spinning with angular
 * momentum L. Each frame: omega = L / I(pose), so tucking (smaller I) spins
 * faster with no torque at all. Thrusters then stop the spin upright.
 */
function* spin(s: Stage): ThreadGenerator {
  const body = s.keeper.body;
  const startOmega = 140; // deg/s just after the hit
  const L = startOmega * inertia(body, s.keeper.blade);
  const readout = new Txt({
    fill: '#ffd166',
    fontFamily: Typography.mono,
    fontSize: 26,
    opacity: 0,
    text: '',
  });
  s.fx.add(readout);
  readout.position(() => body.position().add([0, 190]));
  s.spawn(everyFrame(at('untuck', 0.5), dt => {
    const I = inertia(body, s.keeper.blade);
    const omega = L / I;
    body.rotation(body.rotation() + omega * dt);
    readout.text(`ω = ${omega.toFixed(0)}°/s   I = ${(I / 1000).toFixed(0)}k`);
  }));
  yield* syncTo('lblSpin');
  yield* all(
    s.label.show('L = I ω = constant', 'pull mass inward, I falls, ω rises'),
    readout.opacity(1, 0.3),
  );
  yield* syncTo('tuck');
  yield* body.pose(
    {torso: 30, head: 20, leftHip: -120, leftKnee: 140, rightHip: -110, rightKnee: 135, leftShoulder: -40, leftElbow: -120, rightShoulder: -20, rightElbow: -130},
    0.6,
    easeInOutCubic,
  );
  yield* syncTo('untuck');
  yield* body.pose(GUARD, 0.5, easeInOutCubic);
  // Counter-thrust: stop at the nearest upright orientation.
  yield* syncTo('untuck', -0.5);
  const upright = Math.round(body.rotation() / 360 + 0.5) * 360;
  s.spawn(exhaust(s.fx, () => body.bones.chest.absolutePosition(), new Vector2(0, -1), 0.6));
  yield* all(body.rotation(upright, 0.75, easeOutCubic), readout.opacity(0, 0.4));
  body.rotation(0);
  readout.remove();
}

/** The alien's blade spreads into a cloud of possible angles until touched. */
function* superposition(s: Stage): ThreadGenerator {
  const blade = s.alien.blade;
  yield* syncTo('superpose');
  yield* blade.spread(11, 2.0, easeInOutSine);
  yield* syncTo('lblSuper');
  yield* s.label.show('Δx · Δp ≥ ħ / 2', 'a superposition: every angle at once, weighted by |ψ|²');

  // The keeper parries a ghost (branch +2): nothing there to hit.
  const T = at('ghostMiss');
  const k = STYLES.high;
  const ghostRot = (b: Blade) => b.rotation(b.rotation() + 2 * b.spread());
  const sepX = solveContactSep(s, {...GUARD, ...k.strike}, GUARD, k.grip, STYLES.mid.grip, 0, ghostRot);
  yield* all(burn(s, new Vector2(sepX, 0), Math.max(0.3, T - useTime() - 0.05)), swing(s.keeper, k, T));
  const ghost = new Txt({
    text: 'only a possibility',
    fill: ALIEN_BLADE,
    fontFamily: Typography.mono,
    fontSize: 24,
    opacity: 0,
  });
  s.fx.add(ghost);
  ghost.absolutePosition(s.keeper.blade.tip().add([0, -50]));
  s.spawn(all(ghost.opacity(1, 0.2).wait(1.2).to(0, 0.4), s.keeper.body.pose(GUARD, 0.5)));

  // The real clash measures it: every branch but one vanishes.
  yield* exchange(s, 'collapse1', {keeper: 'mid', alien: 'mid', recoil: 200, sparkScale: 1.4, collapse: true});
  yield* s.label.show('measurement → one outcome', 'contact forces the blade into a single place');
  ghost.remove();
}

function* tunnelling(s: Stage): ThreadGenerator {
  yield* syncTo('barrier');
  const keeper = s.keeper.body;
  const barrier = new Rect({
    width: 18,
    height: 0,
    radius: 9,
    fill: 'rgba(120,200,255,0.25)',
    stroke: '#78c8ff',
    lineWidth: 3,
    shadowColor: '#78c8ff',
    shadowBlur: 24,
  });
  s.fx.add(barrier);
  barrier.position(() => keeper.position().add([175, -60]));
  yield* all(
    barrier.height(440, 0.6, easeOutCubic),
    keeper.pose({leftShoulder: -95, leftElbow: 0, rightShoulder: 30, rightElbow: -60}, 0.5),
  );

  // The alien thrusts; its blade's wave packet runs into the barrier.
  const T = tunnelProbability(1.6);
  const centre = createSignal(Vector2.zero);
  const amp = createSignal(0);
  const packet = (c: () => Vector2, a: () => number, color: string) =>
    new Line({
      points: () => {
        const pts: [number, number][] = [];
        for (let x = -170; x <= 170; x += 5) {
          const env = Math.exp(-((x / 60) ** 2));
          pts.push([x, -a() * 70 * env * Math.sin(0.11 * (x + c().x))]);
        }
        return pts;
      },
      position: c,
      stroke: color,
      lineWidth: 4,
      opacity: () => Math.min(1, a() * 6),
      shadowColor: color,
      shadowBlur: 12,
    });
  const incoming = packet(centre, amp, ALIEN_BLADE);
  s.fx.add(incoming);
  yield* syncTo('barrier', -2.0);
  yield* s.alien.body.pose({...GUARD, ...STYLES.mid.strike}, 0.3, easeInCubic);
  centre(toWorldLocal(s, s.alien.blade.tip()));
  const wall = () => barrier.position().add([30, 0]);
  yield* all(amp(1, 0.3), centre(wall(), at('barrier', 8) - useTime(), linear));

  // At the wall: most reflects, a sliver tunnels through. T = e^(-2κd).
  const reflected = createSignal(wall());
  const reflectedAmp = createSignal(Math.sqrt(1 - T));
  const through = createSignal(wall().add([-60, 0]));
  const throughAmp = createSignal(Math.sqrt(T) * 1.8);
  incoming.remove();
  const r = packet(reflected, reflectedAmp, ALIEN_BLADE);
  const t = packet(through, throughAmp, '#ffffff');
  s.fx.add([r, t]);
  const chest = () => keeper.position().add([0, -80]);
  s.spawn(all(reflected(reflected().add([520, 0]), 2.5, linear), reflectedAmp(0, 2.5)));
  s.spawn(s.label.show(`T ≈ e^(−2κd) ≈ ${(T * 100).toFixed(0)}%`, 'a wave leaks through a wall it cannot classically cross'));
  yield* through(chest(), at('tunnel') - useTime(), linear);

  // It arrives: the keeper is clipped and sent tumbling.
  const hit = keeper.bones.chest.absolutePosition();
  s.spawn(all(
    sparks(s.fx, hit, KEEPER_BLADE, 1.2),
    shake(s, 1.5),
    throughAmp(0, 0.2),
    keeper.rotation(-55, 0.5, easeOutCubic),
    s.sep(s.sep().add([-150, -40]), 1.2, linear),
    keeper.pose({torso: -30, head: -30, leftShoulder: 60, rightShoulder: 80}, 0.3),
  ));

  yield* syncTo('recover');
  s.spawn(exhaust(s.fx, () => keeper.bones.chest.absolutePosition(), new Vector2(0, 1), 1.0));
  yield* all(barrier.opacity(0, 0.5), keeper.rotation(0, 1.0, easeInOutCubic), keeper.pose(GUARD, 0.9), s.label.hide());
  barrier.remove();
  r.remove();
  t.remove();
}

function* finale(s: Stage): ThreadGenerator {
  const {keeper, alien} = s;
  // Blades lock. The traveller's blade blurs back into superposition.
  yield* syncTo('lock', 0.4);
  const k = STYLES.mid;
  const sepX = solveContactSep(s, {...GUARD, ...k.strike}, {...GUARD, ...k.strike}, k.grip, k.grip, 0);
  yield* all(
    s.sep(new Vector2(sepX, 0), 0.38, easeInOutSine),
    keeper.body.pose({...GUARD, ...k.strike}, 0.38, easeInCubic),
    alien.body.pose({...GUARD, ...k.strike}, 0.38, easeInCubic),
    keeper.blade.rotation(k.grip, 0.38),
    alien.blade.rotation(k.grip, 0.38),
  );
  yield* checkContact(s, 'lock');
  s.spawn(all(alien.blade.spread(7, 2.5, easeInOutSine), s.world.scale(1.5, 4, easeInOutSine)));
  s.spawn(s.label.hide());
  // Grinding: the locked blades shed sparks while they push.
  s.spawn((function* () {
    while (useTime() < at('spinDown') - 0.3) {
      yield* sparks(s.fx, bladeContact(keeper.blade, alien.blade).point, '#ffd27a', 0.45);
    }
  })());

  // The keeper measures his own blade: spin up.
  yield* syncTo('measure');
  const ring = new Circle({size: 60, stroke: KEEPER_BLADE, lineWidth: 4});
  keeper.blade.add(ring);
  keeper.blade.spin(1);
  keeper.blade.showSpin(1);
  s.spawn(all(ring.size(220, 0.6, easeOutCubic), ring.opacity(0, 0.6)));
  yield* s.label.show('measure A → ↑', 'the keeper reads his own blade');

  // Across the gap, with nothing crossing it, the other blade is down.
  yield* syncTo('singlet', -1.5);
  yield* s.label.show('singlet: A ↑  ⇒  B ↓', 'perfectly anti-correlated, always');
  yield* syncTo('spinDown');
  alien.blade.spin(-1);
  alien.blade.showSpin(1);
  alien.blade.spread(0);
  const ring2 = new Circle({size: 60, stroke: ALIEN_BLADE, lineWidth: 4});
  alien.blade.add(ring2);
  s.spawn(all(
    ring2.size(220, 0.6, easeOutCubic),
    ring2.opacity(0, 0.6),
    // Spin down is the branch angled away: the guard opens.
    alien.blade.rotation(alien.blade.rotation() + 80, 0.25, easeOutCubic),
    // Arm stays forward, blade tipped back over the shoulder: the line is open.
    alien.body.pose({rightShoulder: -150, rightElbow: -20, torso: -10}, 0.4, easeOutCubic),
    s.world.scale(1.25, 1.5, easeInOutCubic),
  ));

  // The disarm: a rising cut through the traveller's grip.
  // Aim at the hilt: the keeper's blade must pass through the traveller's grip.
  // Search the arm angle as well as the separation for a cut that connects.
  const hiltGap = () => segmentPointDistance(keeper.blade.absolutePosition(), keeper.blade.tip(), alien.blade.absolutePosition());
  yield* syncTo('disarm', 1.4);
  const alienPose = currentPose(alien);
  const alienGrip = alien.blade.rotation();
  let disarmPose: Pose = {...GUARD, rightShoulder: -140, rightElbow: -10, torso: 20};
  let disarmSep = NaN;
  for (let shoulder = -60; shoulder >= -200 && Number.isNaN(disarmSep); shoulder -= 10) {
    const pose: Pose = {...GUARD, rightShoulder: shoulder, rightElbow: -10, torso: 20};
    const sep = solveContactSep(s, pose, alienPose, -25, alienGrip, 0, undefined, hiltGap, true);
    if (!Number.isNaN(sep)) {
      disarmPose = pose;
      disarmSep = sep;
    }
  }
  if (Number.isNaN(disarmSep)) {
    useLogger().warn('disarm: no arm angle reaches the hilt');
    disarmSep = 300;
  }
  yield* s.sep(new Vector2(disarmSep, 0), 0.8, easeInOutSine);
  yield* syncTo('disarm', 0.5);
  yield* all(keeper.body.pose({...GUARD, ...STYLES.low.windup}, 0.3, easeOutCubic), keeper.blade.rotation(-25, 0.3));
  yield* syncTo('disarm', 0.15);
  yield* keeper.body.pose(disarmPose, 0.15, easeInCubic);
  const contact = {point: alien.blade.absolutePosition()};
  const miss = hiltGap();
  if (miss > CONTACT_TOLERANCE) useLogger().warn(`contact "disarm": blade misses the hilt by ${miss.toFixed(0)} px`);

  // The blade leaves the traveller's hand and keeps the momentum it was given:
  // straight line, constant spin, forever.
  const free = alien.blade;
  free.reparent(s.fx);
  const v = new Vector2(260, -120);
  const omega = 220;
  const life = 40;
  s.spawn(whiteout(s, 0.9));
  s.spawn(all(
    sparks(s.fx, contact.point, '#ffffff', 1.8),
    shake(s, 2),
    free.position(free.position().add(v.scale(life)), life, linear),
    free.rotation(free.rotation() + omega * life, life, linear),
    s.sep(s.sep().add([180, 0]), 1.5, linear),
    alien.body.pose({torso: -25, head: -20, rightShoulder: 120, rightElbow: -60, leftShoulder: 100}, 0.4, easeOutCubic),
  ));
  s.freeBlade = free;

  yield* syncTo('lblSignal');
  yield* s.label.show('no-signalling theorem', 'entanglement shares correlations, never messages');
  yield* all(
    keeper.body.pose({...GUARD, rightShoulder: -20, rightElbow: -30, torso: 0}, 1.5),
    alien.body.pose({torso: 35, head: 25, rightShoulder: 10, rightElbow: -20, leftShoulder: 10, leftElbow: -20, leftHip: -5, leftKnee: 10, rightHip: 5, rightKnee: 10}, 2),
  );
  yield* syncTo('lblSignalEnd');
  yield* s.label.hide();
}
