import {makeProject} from '@motion-canvas/core';

import audio from '../audio/first_light/master.wav';
import firstLight from './first_light/scenes/first_light?scene';

export default makeProject({
  name: 'first_light',
  scenes: [firstLight],
  audio,
});
