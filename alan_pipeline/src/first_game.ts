import {makeProject} from '@motion-canvas/core';

import audio from '../audio/first_game/master.wav';
import firstGame from './first_game/scenes/first_game?scene';

export default makeProject({
  name: 'first_game',
  scenes: [firstGame],
  audio,
});
