# tools

## build_space_audio.py

Builds the soundtrack and the cue sheet for the `space_duel` project from
`audio/space_duel/story.json`:

```bash
pip install -r tools/requirements.txt
npm run audio:space          # = python tools/build_space_audio.py
```

- **Narration** is synthesized with [Piper](https://github.com/rhasspy/piper)
  and cached in `audio/space_duel/voice/` (committed). Piper is not
  bit-deterministic, so the cached clips are the source of truth: a clip is
  only re-synthesized when its text, voice or speed changes (or `--retts`).
- **Timing check:** the build measures every clip and fails if a line would
  run into the next one, listing the overrun in seconds.
- **Sound effects and music** are synthesized from code (numpy) at the event
  times in `story.json`. A sound effect can be anchored to a narration edge,
  e.g. `"at": "n14.end"`.
- **Outputs:** `audio/space_duel/master.wav` (48 kHz stereo, git-ignored,
  rebuilt by the command above) and `audio/space_duel/cues.json`
  (committed), which the scene animates to.

Voice models (`.onnx` + `.onnx.json`) go in `tools/voices/` (git-ignored).
The ones used here come from the Piper v0.0.2 release on GitHub:

```bash
mkdir -p tools/voices && cd tools/voices
curl -LO https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-en-us-ryan-high.tar.gz
curl -LO https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-en-gb-alan-low.tar.gz
tar xzf voice-en-us-ryan-high.tar.gz && tar xzf voice-en-gb-alan-low.tar.gz
```
