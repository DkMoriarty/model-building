import {makeProject} from '@motion-canvas/core';

import audio from '../audio/master_track.wav';
import openingFight from './scenes/opening_fight?scene';

export default makeProject({
  name: 'alan_pipeline',
  scenes: [openingFight],
  audio,
});
