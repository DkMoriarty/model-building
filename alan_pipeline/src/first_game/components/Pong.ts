import {Circle, Gradient, Line, Node, NodeProps, Rect, Txt} from '@motion-canvas/2d';
import {createSignal, SimpleSignal, ThreadGenerator, useLogger, useTime, Vector2} from '@motion-canvas/core';
import {withAlpha} from '../../figureSpec';
import {Typography} from '../../styles';
import {physics, Rally} from '../cues';
import {roomPicture} from './Game';

/**
 * Spark's ping pong (original design), in game units: a wide 1280 x 330 court,
 * origin at the centre. The ball's path is never animated by hand: it is read
 * from the rallies tools/pong.py computed (constant speed, true reflections,
 * collisions checked per frame), so what we see is what the code would do.
 */
export const COURT = {w: 1280, h: 330};
const P = physics as unknown as {wall: number; ballR: number; paddleX: number; paddleHalfW: number; paddleHalfH: number; goalX: number; fps: number; reach: number};
export const PONG = P;

export const PONG_COLORS = {
  bg: '#07121f',
  line: '#e8e8e8',
  ball: '#ffd166',
  you: '#2ec4b6',
  cpu: '#ef476f',
};

/** Where the ball is at time t on a rally (piecewise straight lines). */
export function ballAt(r: Rally, t: number): Vector2 | null {
  const segs = r.segments;
  if (!segs.length || t < segs[0].t) return null;
  for (const s of segs) {
    if (t <= s.until + 1e-9) {
      const dt = t - s.t;
      return new Vector2(s.x + s.vx * dt, s.y + s.vy * dt);
    }
  }
  const s = segs[segs.length - 1];
  return new Vector2(s.x + s.vx * (s.until - s.t), s.y + s.vy * (s.until - s.t));
}

export class Court extends Node {
  public readonly ball: Circle;
  public readonly left: Rect;
  public readonly right: Rect;
  public readonly leftY = createSignal(0);
  public readonly rightY = createSignal(0);
  public readonly score: Txt;
  public readonly scoreL = createSignal(0);
  public readonly scoreR = createSignal(0);
  public readonly showRight = createSignal(1);
  public readonly showLeft = createSignal(1);
  public readonly showScore = createSignal(1);
  public readonly door: Node;
  /** Trail of the last few rendered frames' ball positions (shows the skip). */
  public readonly trail: Node;

  public constructor(props: NodeProps & {walls?: 'all' | 'topBottom'; door?: boolean}) {
    const {walls = 'topBottom', door = false, ...rest} = props;
    super(rest);
    const lw = 6;
    this.add(new Rect({width: COURT.w, height: COURT.h, fill: PONG_COLORS.bg}));
    this.add(new Line({points: [[0, -P.wall], [0, P.wall]], stroke: withAlpha(PONG_COLORS.line, 0.35), lineWidth: lw, lineDash: [24, 20]}));
    this.add(new Line({points: [[-640, -P.wall], [640, -P.wall]], stroke: PONG_COLORS.line, lineWidth: lw}));
    this.add(new Line({points: [[-640, P.wall], [640, P.wall]], stroke: PONG_COLORS.line, lineWidth: lw}));
    if (walls === 'all') {
      this.add(new Line({points: [[-640, -P.wall], [-640, P.wall]], stroke: PONG_COLORS.line, lineWidth: lw}));
      this.add(new Line({points: [[640, -P.wall], [640, P.wall]], stroke: PONG_COLORS.line, lineWidth: lw}));
    }
    // The exit: a door in the right wall, with Spark's room seen through it.
    this.door = new Node({x: 662, opacity: door ? 1 : 0});
    this.door.add(new Circle({size: 420, fill: new Gradient({type: 'radial', fromRadius: 0, toRadius: 210, stops: [{offset: 0, color: withAlpha('#ffd166', 0.3)}, {offset: 1, color: withAlpha('#ffd166', 0)}]})}));
    const frame = new Rect({width: 64, height: 240, radius: [32, 32, 4, 4], clip: true, fill: '#f6e7c1'});
    frame.add(roomPicture({scale: 0.2, x: 0, y: 40}));
    this.door.add(frame);
    this.door.add(new Rect({width: 64, height: 240, radius: [32, 32, 4, 4], stroke: '#ffd166', lineWidth: 6}));
    this.add(this.door);
    this.trail = new Node({});
    this.add(this.trail);
    this.left = new Rect({x: -P.paddleX, y: () => this.leftY(), width: P.paddleHalfW * 2, height: P.paddleHalfH * 2, fill: PONG_COLORS.you, opacity: () => this.showLeft()});
    this.right = new Rect({x: P.paddleX, y: () => this.rightY(), width: P.paddleHalfW * 2, height: P.paddleHalfH * 2, fill: PONG_COLORS.cpu, opacity: () => this.showRight()});
    this.ball = new Circle({size: P.ballR * 2, fill: PONG_COLORS.ball, opacity: 0});
    this.score = new Txt({y: -P.wall + 45, text: () => `${this.scoreL()}   ${this.scoreR()}`, fontFamily: Typography.mono, fontWeight: 800, fontSize: 48, fill: withAlpha(PONG_COLORS.line, 0.8), opacity: () => this.showScore()});
    this.add([this.left, this.right, this.ball, this.score]);
  }
}

/**
 * Play a rally on a court until `until`: the ball follows the computed path
 * (drawn only on whole frames, like a game), each paddle chases the ball at
 * its top speed, and every hit, miss and skip is checked against what the
 * paddles actually managed. A frame trail shows where the ball was drawn.
 */
export function* playRally(court: Court, r: Rally, until: number, speeds: {left: number; right: number}, name: string, trail = false): ThreadGenerator {
  const dt = 1 / P.fps;
  const targets = (side: number) => r.events.filter(e => e.side === side && (e.kind === 'hit' || e.kind === 'miss' || e.kind === 'tunnel'));
  const tl = targets(-1);
  const tr = targets(1);
  const checked = new Set<number>();
  const marks: Circle[] = [];
  court.ball.opacity(1);
  while (useTime() < until - 1e-6) {
    const t = useTime();
    const b = ballAt(r, t);
    if (b) court.ball.position(b);
    // Check every arrival that happened since the last frame against where the
    // paddle was on that frame, before it turns to chase the next ball.
    for (const [i, e] of r.events.entries()) {
      if (checked.has(i) || e.t > t || !(e.kind === 'hit' || e.kind === 'miss')) continue;
      checked.add(i);
      const py = e.side! < 0 ? court.leftY() : court.rightY();
      const covers = Math.abs(py - e.y!) <= P.paddleHalfH + P.ballR;
      if (e.kind === 'hit' && !covers) useLogger().warn(`${name}: paddle misses a scripted hit at ${e.t.toFixed(2)}s by ${(Math.abs(py - e.y!) - P.paddleHalfH - P.ballR).toFixed(0)}`);
      if (e.kind === 'miss' && covers) useLogger().warn(`${name}: paddle reaches a scripted miss at ${e.t.toFixed(2)}s`);
    }
    // Paddles start chasing on the serve, exactly as tools/pong.py assumes.
    const limit = P.wall - P.paddleHalfH;
    for (const [sig, list, speed] of [
      [court.leftY, tl, speeds.left],
      [court.rightY, tr, speeds.right],
    ] as [SimpleSignal<number, void>, typeof tl, number][]) {
      if (t < r.segments[0].t - 1e-6) continue;
      const next = list.find(e => e.t >= t - 1e-6);
      const goal = Math.max(-limit, Math.min(limit, next ? next.y! : sig()));
      const step = speed * dt;
      const d = goal - sig();
      sig(sig() + Math.max(-step, Math.min(step, d)));
    }
    if (trail && b) {
      const m = new Circle({position: b, size: P.ballR * 2, fill: withAlpha(PONG_COLORS.ball, 0.35)});
      court.trail.add(m);
      marks.push(m);
      if (marks.length > 5) marks.shift()!.remove();
    }
    yield;
  }
  marks.forEach(m => m.remove());
}

export {Vector2};
