import {Node, NodeProps, Rect, Txt} from '@motion-canvas/2d';
import {createSignal, SimpleSignal, ThreadGenerator, useTime} from '@motion-canvas/core';
import {Typography} from '../../styles';

/**
 * The code editor on Spark's monitor (style bible K1-K6). Monospace, one
 * glyph per character so typing reveals exactly one character per key
 * click, a blinking cursor, our own syntax colours, at most three lines.
 */
export const FONT = 16;
export const CHAR_W = FONT * 0.6;
export const LINE_H = 22;
const COLORS = {
  number: '#ffd166',
  fn: '#06d6a0',
  prop: '#8ecae6',
  punct: '#8d99ae',
  text: '#e8e8e8',
};

/** Colour each character by a tiny tokenizer: numbers, calls, properties, punctuation. */
function colours(line: string): string[] {
  const out: string[] = new Array(line.length).fill(COLORS.text);
  const re = /(-?\d+)|([A-Za-z_]\w*)(?=\()|\.([A-Za-z_]\w*)|([(){}.,:=+<>])/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(line))) {
    const start = m.index;
    if (m[1]) for (let i = 0; i < m[1].length; i++) out[start + i] = COLORS.number;
    else if (m[2]) for (let i = 0; i < m[2].length; i++) out[start + i] = COLORS.fn;
    else if (m[3]) {
      out[start] = COLORS.punct;
      for (let i = 0; i < m[3].length; i++) out[start + 1 + i] = COLORS.prop;
    } else if (m[4]) out[start] = COLORS.punct;
  }
  return out;
}

export class CodeView extends Node {
  private readonly lines: {node: Node; text: string; shown: SimpleSignal<number, void>}[] = [];
  private readonly cursor: Rect;
  private readonly body: Node;
  public readonly typing = createSignal(false);

  public constructor(props: NodeProps & {width: number; height: number; time: () => number}) {
    const {width, height, time, ...rest} = props;
    super(rest);
    this.add(new Rect({width, height, fill: '#0b0f18'}));
    this.body = new Node({x: -width / 2 + 12, y: -height / 2 + 18});
    this.add(this.body);
    this.cursor = new Rect({width: CHAR_W, height: 3, offset: [-1, 0], fill: '#ffffff'});
    this.body.add(this.cursor);
    // Blink on the scene clock (useTime is only valid inside a thread, not while drawing).
    this.cursor.opacity(() => (this.typing() || Math.floor(time() * 2.5) % 2 === 0 ? 1 : 0));
  }

  /** Start a new line; returns it so it can be typed into. */
  public newLine(text: string): number {
    if (this.lines.length >= 3) {
      // Scroll: the oldest line leaves, the rest move up a row.
      const old = this.lines.shift()!;
      old.node.remove();
      this.lines.forEach((l, i) => l.node.y(i * LINE_H));
    }
    const shown = createSignal(0);
    const node = new Node({y: this.lines.length * LINE_H});
    const cols = colours(text);
    [...text].forEach((ch, i) => {
      if (ch === ' ') return;
      node.add(new Txt({x: i * CHAR_W, text: ch, fontFamily: Typography.mono, fontSize: FONT, fontWeight: 600, fill: cols[i], offset: [-1, 0], opacity: () => (shown() > i ? 1 : 0)}));
    });
    this.body.add(node);
    this.lines.push({node, text, shown});
    this.placeCursor();
    return this.lines.length - 1;
  }

  private placeCursor(): void {
    const l = this.lines[this.lines.length - 1];
    this.cursor.position(() => [l.shown() * CHAR_W, l.node.y() + FONT * 0.55]);
  }

  /** Reveal characters of the last line, one per key, at absolute times start + i / cps. */
  public *type(start: number, cps: number): ThreadGenerator {
    const l = this.lines[this.lines.length - 1];
    this.typing(true);
    for (let i = 1; i <= l.text.length; i++) {
      while (useTime() < start + i / cps - 1e-6) yield;
      l.shown(i);
    }
    this.typing(false);
  }

  /** Enter: the cursor drops to the start of a fresh row. */
  public enter(): void {
    const row = this.lines.length;
    this.cursor.position([0, Math.min(row, 2) * LINE_H + FONT * 0.55 + (row >= 3 ? LINE_H : 0)]);
  }

  /**
   * Edit in place (K6): flash the character at `index` on line `line`, then
   * delete it, shifting the rest of the line left.
   */
  public *deleteAt(line: number, index: number, flash: number): ThreadGenerator {
    const l = this.lines[line];
    this.cursor.position([(index + 1) * CHAR_W, l.node.y() + FONT * 0.55]);
    const hi = new Rect({x: index * CHAR_W, y: 0, width: CHAR_W, height: LINE_H - 2, offset: [-1, 0], fill: 'rgba(239,71,111,0.55)'});
    l.node.add(hi);
    hi.moveToBottom();
    const t0 = useTime();
    while (useTime() < t0 + flash) yield;
    const text = l.text.slice(0, index) + l.text.slice(index + 1);
    const y = l.node.y();
    l.node.remove();
    const shown = createSignal(text.length);
    const node = new Node({y});
    const cols = colours(text);
    [...text].forEach((ch, i) => {
      if (ch === ' ') return;
      node.add(new Txt({x: i * CHAR_W, text: ch, fontFamily: Typography.mono, fontSize: FONT, fontWeight: 600, fill: cols[i], offset: [-1, 0]}));
    });
    this.body.add(node);
    this.lines[line] = {node, text, shown};
    this.cursor.position([text.length * CHAR_W, y + FONT * 0.55]);
  }

  public lineCount(): number {
    return this.lines.length;
  }
}
