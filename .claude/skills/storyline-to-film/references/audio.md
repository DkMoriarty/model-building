# Sound design

Everything is synthesized in `tools/build_space_audio.py` (numpy only; no
scipy, no samples). Sounds are placed in the timeline at the same cue as the
picture: `sfx(kind, cue, offset=..., gain=..., length=..., seed=...)`.

## Score

- **Continuous:** music sections cover the whole film with no gaps
  (`story["music"]`). Pick sections by mood: night, code, standoff (tension),
  hush, grow, chip / chipTense / chipFinal (games, chases), wonder (reveals),
  resolve, morning.
- **Audible on a phone:** phone speakers play nothing below ~300 Hz. Every
  section carries a melody (`story["melody"][section] = {wave, gain, low}`)
  in 330-780 Hz. Measure the mix in the 300 Hz-4 kHz band.
- **Comfortable:** no shrill tones. Use `bell` (soft harmonics) and `soft`
  (rounded chiptune: odd harmonics 1-7 only), never raw square leads;
  `musicLowpass: 4000`. Energy above 4 kHz in the music below 1%.
- **Level:** `musicGain` (FIRST GAME 2.2). Duck the score under a moment a
  sound must own: `musicDuck: [[from, to, dB]]` (-5 before, -12 during an alarm).
- Designed silences (`silences`) right before big hits and reveals.

## Effects palette (what each story moment gets)

| moment | sound |
| --- | --- |
| typing | `tick` per character at 12 cps; `enter`; `blip` when a line runs |
| ball / game hits | `pong`, `wallbeep`, `score` |
| danger / villain wakes | `panic` bed (racing heartbeat + trembling string) and `alarm` (two-tone, 720/960 Hz), music ducked |
| reveal / appear | `riser` into it, `violet` shimmer, `pop`, `glitch` |
| fall | `whistle` (falling slide, length = the real fall time) then `thud` + `oof` |
| hit / bump / stumble | `oof` + `thud`; vehicles: `crash` |
| win | `fanfare` + `laugh` (natural voice, a different `seed` each time) |
| jump / land (games) | `jump8`, `thud` |
| braking | `screech` for the real stopping time |
| relief / home | `sigh` on the breath out |
| doors, keys | `click`, `ding`, `oneup` |

## Voices without words

Human reactions (laugh, oof, sigh) come from a glottal source (Rosenberg
pulses with jitter 2% and shimmer 10%, breath noise) through vocal-tract
resonances (`formant_shape`, vowel /a/: 800, 1250, 2600, 3500 Hz) plus a small
`room`. Uneven syllable timing, falling pitch, an in-breath after a laugh.
Never stack pure sines for a voice: it sounds robotic.

## Engines and machines follow their physics

`story["engines"]`: per car, the speed sampled every 0.02 s from the plan
(`phase_state`), distance to the camera car, gain, pitch. The engine note
rises through gears with speed, gets louder with throttle and closeness, and
pans with position.

## Checks

- `frame_audit.py`: T1 sync 0 (every impact has a sound, every sound an event).
- Measure each key moment in the 300 Hz-4 kHz band: the score at about
  -19 to -21 dB, drama moments clearly above their surroundings.
- Audio-only change: rebuild master.wav and remux it onto the video
  (`ffmpeg -i video -i master.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k`).
