/**
 * Headless render worker, loaded by scripts/render.mjs in Chromium.
 *
 *   ?project=NAME&probe         -> report the project's length in frames
 *   ?project=NAME&from=A&to=B   -> render frames A..B (inclusive) as PNGs
 *
 * Frames are streamed to the Vite dev server, which writes them to
 * output_renders/<project>/<frame>.png. Frame numbers are absolute, so
 * several workers can render disjoint ranges of the same project in parallel.
 */
import {Player, Project, Renderer, RendererResult} from '@motion-canvas/core';

// Every renderable project, by name (?project=<name>).
const projects: Record<string, () => Promise<{default: Project}>> = {
  alan_pipeline: () => import('../src/project?project'),
  space_duel: () => import('../src/space_duel?project'),
  first_light: () => import('../src/first_light?project'),
  first_game: () => import('../src/first_game?project'),
};

declare global {
  interface Window {
    __render?: {done: boolean; ok: boolean; frames?: number; error?: string};
  }
}

const params = new URLSearchParams(location.search);
const project = (await projects[params.get('project') ?? 'alan_pipeline']()).default;
const settings = project.meta.getFullRenderingSettings();
const report = (value: NonNullable<Window['__render']>) => {
  window.__render = value;
};

// Surface Motion Canvas' logger in the browser console, and fail fast on
// errors (a throwing scene would otherwise leave the probe waiting forever).
project.logger.onLogged.subscribe(entry => {
  const text = `[${entry.level}] ${entry.message}${entry.stack ? '\n' + entry.stack : ''}`;
  console.log(text);
  if (entry.level === 'error') report({done: true, ok: false, error: text});
});

async function probe(): Promise<void> {
  const player = new Player(project, {
    ...project.meta.getFullPreviewSettings(),
    fps: settings.fps,
  });
  const frames = await new Promise<number>(resolve => {
    player.onRecalculated.subscribe(() => {
      const duration = player.onDurationChanged.current;
      if (duration > 0) resolve(duration);
    });
  });
  player.deactivate();
  report({done: true, ok: true, frames});
}

async function render(from: number, to: number): Promise<void> {
  const renderer = new Renderer(project);
  // The renderer converts seconds to frames with ceil(); offsetting by half a
  // frame makes that conversion land exactly on the requested frame numbers.
  const toSeconds = (frame: number) => (frame - 0.5) / settings.fps;
  const finished = new Promise<RendererResult>(resolve =>
    renderer.onFinished.subscribe(resolve),
  );
  await renderer.render({
    ...settings,
    name: project.name,
    range: [toSeconds(from), toSeconds(to)],
    exporter: {
      name: '@motion-canvas/core/image-sequence',
      options: {fileType: 'image/png', quality: 100, groupByScene: false},
    },
  });
  report({done: true, ok: (await finished) === RendererResult.Success});
}

const run = params.has('probe')
  ? probe()
  : render(Number(params.get('from')), Number(params.get('to')));

run.catch(e => report({done: true, ok: false, error: String(e?.stack ?? e)}));
