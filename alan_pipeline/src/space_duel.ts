import {makeProject} from '@motion-canvas/core';

import audio from '../audio/space_duel/master.wav';
import spaceDuel from './space_duel/scenes/space_duel?scene';

export default makeProject({
  name: 'space_duel',
  scenes: [spaceDuel],
  audio,
});
