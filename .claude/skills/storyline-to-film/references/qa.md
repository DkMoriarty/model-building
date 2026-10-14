# Verification and delivery

A film is done only when all of these pass. Report failures honestly; never
ship around them.

## Gates

| gate | how | pass |
| --- | --- | --- |
| types | `npm run typecheck` | no errors |
| timeline | `python tools/<ep>_timeline.py` | runs; every planner assert holds; unique cue names |
| stills | `node scripts/render.mjs --project=<ep> --at=...` (one or more per beat) | read every still: subject clear, goal object in frame, text readable, nothing overlapping (labels vs scores, HUD vs eye) |
| probe | printed by every render | no `late`, no `paddle misses`, no F3s flags |
| full render | `npm run render:<x>` (`--strict`) | completes; 0 warnings |
| frame audit | `python tools/frame_audit.py --episode <ep>` | 0 hard flags, sync 0, dead air 0 |
| sound | band-limited measurements (audio.md) | score audible on a phone, drama stands out, nothing shrill |
| delivery | `ffprobe` the MP4 | H.264 Main yuv420p + AAC-LC 44.1 kHz stereo, faststart, audio non-silent |

Typical fixes:
- `late` beat: shorten the action before it (pose times, camera moves), or lower the lead.
- F3s framing: smaller pose, move the camera, or declare a deliberate exit with a reason.
- F2 negative space: declare transitions (portals, fades) in `audit.declared`; shrink oversized panels.
- T1 sync: add a sound to every impact cue (drops, line runs).
- Picture frozen while time runs: a spawned tween still owns the signal (see pipeline.md).

## Delivery

```
ffmpeg -i output_renders/<ep>.mp4 -vf scale=1280:-2,format=yuv420p -c:v libx264 \
  -profile:v main -crf 26 -preset veryfast -c:a aac -ar 44100 -ac 2 -b:a 192k \
  -movflags +faststart <scratchpad>/<EP>.mp4
```

Send with SendUserFile, `display: attach`. Tell the user to download it and
play it in the phone's own player; the in-app preview can be silent. If they
report no sound, send the soundtrack alone as an MP3 to tell player problems
from file problems.

Then: commit (timeline, plans, story.json, cues.json, src, docs) and push;
never commit renders or master.wav. Add lessons to `docs/LEARNING_LOG.md`.
