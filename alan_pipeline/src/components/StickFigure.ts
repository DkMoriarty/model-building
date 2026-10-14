import {Circle, Line, Node, NodeProps} from '@motion-canvas/2d';
import {
  all,
  createSignal,
  easeInOutCubic,
  easeInOutSine,
  linear,
  SimpleSignal,
  spring,
  Spring,
  ThreadGenerator,
  TimingFunction,
  useTime,
} from '@motion-canvas/core';
import {BIPED, proportionsOf, strokeOf} from '../figureSpec';
import {Colors} from '../styles';

/**
 * Every rotatable joint on the rig. Angles are in degrees and are LOCAL to the
 * parent bone: 0 means "hanging straight down" for limbs and "straight up" for
 * the torso/head. Positive values rotate clockwise (canvas convention).
 *
 * The rig is authored FACING RIGHT (+x). In that frame the sign convention is:
 *   hip / shoulder   negative = swing forward, positive = swing back
 *   knee             positive = flex (shin folds back, as a real knee does)
 *   elbow            negative = flex (forearm folds forward)
 *   torso            positive = lean forward, negative = lean back
 * A figure facing left is the same rig with `scale.x < 0`, so every pose and
 * gait reads correctly in both directions without mirrored angle tables.
 */
export const JOINTS = [
  'torso',
  'head',
  'leftShoulder',
  'leftElbow',
  'rightShoulder',
  'rightElbow',
  'leftHip',
  'leftKnee',
  'rightHip',
  'rightKnee',
] as const;

export type Joint = (typeof JOINTS)[number];
export type Pose = Partial<Record<Joint, number>>;

export interface Proportions {
  headRadius: number;
  neck: number;
  torso: number;
  upperArm: number;
  forearm: number;
  thigh: number;
  shin: number;
}

export interface StickFigureProps extends NodeProps {
  color?: string;
  lineWidth?: number;
  proportions?: Partial<Proportions>;
  pose?: Pose;
}

/** Measured default: the BIPED spec (docs/STYLE_BIBLE.md, section 2). */
const DEFAULT_PROPORTIONS: Proportions = proportionsOf(BIPED);

/** Relaxed standing pose. */
export const IDLE: Pose = {
  torso: 0,
  head: 0,
  leftShoulder: 14,
  leftElbow: -10,
  rightShoulder: -14,
  rightElbow: -14,
  leftHip: 8,
  leftKnee: 3,
  rightHip: -8,
  rightKnee: 3,
};

/** +1 = facing right (+x), -1 = facing left. */
export type Facing = 1 | -1;

/**
 * How `walkTo` relates the direction of travel to the way the figure faces.
 * - `auto`: turn to face the destination, then walk forward (default).
 * - `forward`: walk forward; turns first if the target is behind.
 * - `backward`: keep facing the same way and back-pedal.
 */
export type WalkMode = 'auto' | 'forward' | 'backward';

export interface WalkOptions {
  mode?: WalkMode;
  /** Number of footfalls. Defaults to `distance / stride`, rounded. */
  steps?: number;
  /** Target step length in px when `steps` is not given. Default 90. */
  stride?: number;
  /** Absolute scene time (s) at which the final foot lands, e.g. an audio marker. */
  arriveAt?: number;
  /** Walk duration (s) when `arriveAt` is not given. Default 0.25 s per step. */
  duration?: number;
  /**
   * Ease back into IDLE after the last footfall (default true). Pass false to
   * flow straight into the next action from the planted end-of-walk stance.
   */
  settle?: boolean;
}

/** Peak knee flex of the swinging leg, degrees. */
const SWING_KNEE = 48;
const frac = (v: number) => v - Math.floor(v);
const deg = (rad: number) => (rad * 180) / Math.PI;

/**
 * Hierarchical kinematic stick-figure rig.
 *
 * The node's own position is the pelvis. Bones are nested `Node`s, so every
 * child inherits its parent's full transform matrix (hip -> knee -> foot,
 * torso -> shoulder -> elbow -> fist). Nothing stores absolute coordinates, so
 * there is no floating-point drift between frames: a pose is just ten angles.
 *
 * Each joint is a Motion Canvas signal and can be tweened directly:
 *
 *   yield* fig.joints.rightShoulder(-95, 0.2);
 *   yield* fig.pose({rightShoulder: -95, rightElbow: 0}, 0.2);
 *   yield* fig.springPose(StrikeSpring, {rightShoulder: -95});
 */
export class StickFigure extends Node {
  public readonly joints: Record<Joint, SimpleSignal<number, this>>;
  public readonly color: SimpleSignal<string, this>;
  public readonly proportions: Proportions;

  /** Bone nodes, exposed for attaching props (weapons, effects) to a limb. */
  public readonly bones: {
    torso: Node;
    chest: Node;
    head: Circle;
    leftFist: Node;
    rightFist: Node;
    leftFoot: Node;
    rightFoot: Node;
  };

  public constructor({
    color = Colors.ink,
    lineWidth = strokeOf(BIPED),
    proportions,
    pose,
    ...props
  }: StickFigureProps = {}) {
    super(props);
    const p = {...DEFAULT_PROPORTIONS, ...proportions};
    this.proportions = p;
    this.color = createSignal(color) as SimpleSignal<string, this>;

    const initial = {...IDLE, ...pose};
    this.joints = Object.fromEntries(
      JOINTS.map(joint => [joint, createSignal(initial[joint] ?? 0)]),
    ) as unknown as Record<Joint, SimpleSignal<number, this>>;

    const stroke = () => this.color();
    const bone = (length: number) =>
      new Line({
        points: [
          [0, 0],
          [0, length],
        ],
        stroke,
        lineWidth,
        lineCap: 'round',
      });

    /** Two-segment limb: root joint -> mid joint -> end effector. */
    const limb = (
      rootJoint: Joint,
      midJoint: Joint,
      upper: number,
      lower: number,
    ): {root: Node; end: Node} => {
      const end = new Node({y: lower});
      const mid = new Node({
        y: upper,
        rotation: () => this.joints[midJoint](),
        children: [bone(lower), end],
      });
      const root = new Node({
        rotation: () => this.joints[rootJoint](),
        children: [bone(upper), mid],
      });
      return {root, end};
    };

    const leftArm = limb('leftShoulder', 'leftElbow', p.upperArm, p.forearm);
    const rightArm = limb('rightShoulder', 'rightElbow', p.upperArm, p.forearm);
    const leftLeg = limb('leftHip', 'leftKnee', p.thigh, p.shin);
    const rightLeg = limb('rightHip', 'rightKnee', p.thigh, p.shin);

    // Open ring head, same weight as the limbs: reads at any zoom.
    // The ring's OUTER diameter is H, so the path sits half a stroke inside.
    const head = new Circle({
      y: -(p.neck + p.headRadius),
      size: p.headRadius * 2 - lineWidth,
      stroke,
      lineWidth,
    });

    const chest = new Node({
      y: -p.torso,
      children: [
        leftArm.root,
        rightArm.root,
        new Node({
          rotation: () => this.joints.head(),
          children: [
            new Line({
              points: [
                [0, 0],
                [0, -p.neck],
              ],
              stroke,
              lineWidth,
              lineCap: 'round',
            }),
            head,
          ],
        }),
      ],
    });

    const torso = new Node({
      rotation: () => this.joints.torso(),
      children: [
        new Line({
          points: [
            [0, 0],
            [0, -p.torso],
          ],
          stroke,
          lineWidth,
          lineCap: 'round',
        }),
        chest,
      ],
    });

    // Legs first so the torso/arms draw on top of them.
    this.add([leftLeg.root, rightLeg.root, torso]);

    this.bones = {
      torso,
      chest,
      head,
      leftFist: leftArm.end,
      rightFist: rightArm.end,
      leftFoot: leftLeg.end,
      rightFoot: rightLeg.end,
    };
  }

  /** Distance from pelvis to the soles in the IDLE pose (for ground placement). */
  public get legLength(): number {
    return this.proportions.thigh + this.proportions.shin;
  }

  /** Snap to a pose instantly. */
  public setPose(pose: Pose): void {
    for (const joint of Object.keys(pose) as Joint[]) {
      this.joints[joint](pose[joint]!);
    }
  }

  /** Tween any subset of joints in parallel. */
  public *pose(
    pose: Pose,
    duration: number,
    timing: TimingFunction = easeInOutCubic,
  ): ThreadGenerator {
    yield* all(
      ...(Object.keys(pose) as Joint[]).map(joint =>
        this.joints[joint](pose[joint]!, duration, timing),
      ),
    );
  }

  /**
   * Drive joints with a spring-damper simulation instead of an easing curve.
   * Overshoot and settle come from the physics, which is what sells weight on
   * punches and recoils.
   */
  public *springPose(
    physics: Spring,
    pose: Pose,
    settleDegrees = 0.5,
  ): ThreadGenerator {
    yield* all(
      ...(Object.keys(pose) as Joint[]).map(joint => {
        const signal = this.joints[joint];
        return spring(physics, signal(), pose[joint]!, settleDegrees, value =>
          signal(value),
        );
      }),
    );
  }

  /** Which way the figure currently faces, from the sign of `scale.x`. */
  public get facing(): Facing {
    return this.scale.x() < 0 ? -1 : 1;
  }

  /** Turn to face `direction` with a quick squash-through-zero flip. */
  public *face(direction: Facing, duration = 0.1): ThreadGenerator {
    if (this.facing === direction) return;
    yield* this.scale.x(direction * Math.abs(this.scale.x()), duration, easeInOutSine);
  }

  /**
   * Walk to `x` with a zero-slip procedural gait.
   *
   * Every joint is DERIVED from how far the pelvis has travelled, rather than
   * tweened on its own clock. The planted foot moves backwards relative to
   * the pelvis by exactly the distance the pelvis moves forward, so it stays
   * glued to the ground. Footfalls land at equal time intervals between now
   * and `arriveAt`, so with an audio marker as `arriveAt` the steps fall on
   * that beat grid and the last foot lands on the marker.
   *
   *   yield* fig.walkTo(400, {steps: 6, arriveAt: markers.windup});
   *   yield* fig.walkTo(-200, {mode: 'backward', steps: 2, duration: 0.4});
   */
  public *walkTo(x: number, options: WalkOptions = {}): ThreadGenerator {
    const startX = this.x();
    const distance = x - startX;
    if (Math.abs(distance) < 1) return;

    const mode = options.mode ?? 'auto';
    const travel: Facing = distance > 0 ? 1 : -1;
    if (mode !== 'backward') yield* this.face(travel);
    // +1 when travelling the way the figure faces, -1 when back-pedalling.
    const local = travel * this.facing;

    const steps =
      options.steps ?? Math.max(1, Math.round(Math.abs(distance) / (options.stride ?? 90)));
    // Exact step length, so the walk ends precisely on a footfall.
    const step = Math.abs(distance) / steps;
    const duration =
      options.arriveAt !== undefined
        ? Math.max(1 / 60, options.arriveAt - useTime())
        : (options.duration ?? steps * 0.25);

    const leg = this.legLength;
    const baseY = this.y();
    const lean = local > 0 ? 5 : -4;

    // Steps travelled so far, signed: forward walking counts up, back-pedalling
    // counts down, which runs the same cycle in reverse.
    const progress = () => (local * Math.abs(this.x() - startX)) / step;

    /** Hip angle (deg) that puts the foot `footX` px ahead of the pelvis. */
    const hipFor = (footX: number) => deg(Math.asin(Math.max(-1, Math.min(1, -footX / leg))));

    /**
     * One leg over a two-step cycle. t in [0, 0.5): stance, the foot is planted
     * and slides from +step/2 to -step/2 relative to the pelvis (leg straight).
     * t in [0.5, 1): swing, the foot travels back to the front with the knee
     * flexed so it clears the ground.
     */
    const legAt = (t: number) => {
      if (t < 0.5) {
        const u = t / 0.5;
        return {hip: hipFor(step / 2 - step * u), knee: 0, stance: true};
      }
      const u = (t - 0.5) / 0.5;
      return {
        hip: hipFor(-step / 2 + step * easeInOutSine(u)),
        knee: SWING_KNEE * Math.sin(Math.PI * u),
        stance: false,
      };
    };
    const left = () => legAt(frac(progress() / 2));
    const right = () => legAt(frac(progress() / 2 + 0.5));

    this.joints.leftHip(() => left().hip);
    this.joints.leftKnee(() => left().knee);
    this.joints.rightHip(() => right().hip);
    this.joints.rightKnee(() => right().knee);
    // Arms counter-swing against the leg on the same side.
    this.joints.leftShoulder(() => -0.9 * left().hip);
    this.joints.rightShoulder(() => -0.9 * right().hip);
    this.joints.leftElbow(() => -14 + 0.4 * Math.min(0, this.joints.leftShoulder()));
    this.joints.rightElbow(() => -14 + 0.4 * Math.min(0, this.joints.rightShoulder()));
    this.joints.torso(lean);
    // Pelvis rides on the straight stance leg: lowest at contact, highest mid-stance.
    this.y(() => {
      const planted = left().stance ? left() : right();
      return baseY + leg * (1 - Math.cos((planted.hip * Math.PI) / 180));
    });

    yield* this.x(x, duration, linear);

    // Freeze the derived values, then (optionally) settle into the idle stance.
    for (const joint of JOINTS) this.joints[joint](this.joints[joint]());
    this.y(this.y());
    if (options.settle ?? true) {
      yield* all(this.pose(IDLE, 0.18), this.y(baseY, 0.18));
    }
  }
}
