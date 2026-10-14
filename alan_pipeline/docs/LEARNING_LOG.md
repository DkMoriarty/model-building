# Learning log

Everything learned while building these films, in one place. Each entry
says where it came from and where the rule now lives. Add to it every time
a study or a mistake teaches something.

## Studies (technique only; nothing downloaded)

| date | source | what we learned | where it lives |
| --- | --- | --- | --- |
| 10-13 | "Animation vs. Geometry", passes 1 and 2 | figure construction in head units, stroke weight, 3–8 f anticipation, 2–4 f holds, line tiers 3 : 2 : 1, composition (ground at two-thirds, lead room), shot lengths | style bible §2, §3, §5 |
| 10-14 | "Animation vs. Coding", technique pass | three shake tiers, reaction freeze 6–12 f, contact squash, silence before the climax, a sound for every spawn | §3, §4, §8, §9.3 |
| 10-14 | "Animation vs. Coding", story pass | the hook = the first try refused; the child loop; cause → effect → new question; the tool turns on its maker; the bookend | §7, `references/animation_vs_coding_story.md` |
| 10-14 | Math, Physics, Animator vs. Animation, Minecraft: clarity | the want is an object in frame; gaze → reach → move; want/try/result/reaction loop; reaction holds; rule of three; same-shot causality; pay-offs | §7 C1–C10, `references/clarity_study.md` |
| 10-14 | "Animation vs. Coding", code-on-screen pass | type 10–14 chars/s with a cursor and 1:1 key clicks; the active line ≥ 8% of frame height; push in on the code, hold ≥ 1 s, pull back for the reaction; the result fires within 6 frames of Enter | §5 K1–K6, `references/code_on_screen.md` |

## Lessons from our own mistakes and feedback

| lesson | how we found it | rule now |
| --- | --- | --- |
| Narration that explains is worse than showing | user feedback on the space duel | voice only for a cold open and dialogue |
| Figures must be measured, not eyeballed | user feedback | `figureSpec.ts`, head-unit ratios |
| A film needs a small toy first, then the story | user feedback | §7 "open small" |
| Empty backgrounds feel dead; props must come and go | user feedback | §5 background-prop rules |
| **The audience must always know what the character wants** | user feedback on FIRST LIGHT ("nobody understood he invented the machine") | §7 C1–C10; every episode gets a want → try → result → reaction map |
| **Show the code itself, close up, then pull back** | user feedback on FIRST GAME | §5 K1–K6 |
| **Whatever the character does must work exactly as in the real world**, in 2D | user feedback on FIRST GAME | K5; physics constants live in `story.json` and drive both the timeline and the picture |
| A bare `yield` task is cancelled with its parent | frozen effects in the space duel | `stage.spawn` |
| Hand-rolled screen-to-world maths drifts 100+ px | the nut catch missed | `toWorldLocal` / `worldOf` |
| `rgba()` with alpha in exponent notation crashes the canvas | FIRST LIGHT render failure at 2:15 | `withAlpha` prints fixed-point |
| Sounds authored as offsets from an event are tied to it | audit false positives | `frame_audit.py` treats offset sounds as anchored |
| Medium close-ups crop at the knees by design | audit false positives | subject audit skips feet at zoom ≥ 1.8 |
| **Keep the approved half; grow the story from its last beat** | user feedback on FIRST GAME v3 ("perfect till he invents the game") | v4 keeps 0–55 s exactly as it was; the new half starts at the computer losing |
| The villain's power should come from what the hero just did | the computer learns *because* it lost | §7: cause → effect → new question |
| A rule the audience can count beats a rule they must remember | "win 3 games" | three lock lights on the door and in every round's HUD; one lights per win |
| A physics plan must check the outcome it promises | the red cars must not be able to stop | `first_game_plans.race` asserts stopping distance > room, the jump span > gap, and that no two cars overlap |
| One lane can't hold a chase where the hero brakes | a red car would have hit Spark from behind | two lanes in side view: rammers pull into the far lane, then can't stop |
| A jump that lands level needs both edges level | the kicker lifts the car 37 units | the far side of the gap is raised by the kicker's rise |
| Aimed hazards need a moving target | falling blocks at fixed spots let Spark stand still | `dodge(aim=True)`: each block aims at where Spark stands when it drops |
| **The score must be heard, end to end** | user feedback on FIRST GAME v4 ("music hasn't come") | music measured per section; no gaps between sections; `musicGain` per episode (FIRST GAME: x2.2, about +7 dB) |
| **Measure the music where people listen: phone speakers** | user still couldn't hear the music after +7 dB | the score's energy was below 300 Hz (bass, kick, low pads), which phones don't play; every FIRST GAME section now carries a melody at 500 Hz - 1 kHz, and the check measures the 300 Hz - 4 kHz band |
| **Dramatic beats need their own sound, not just music** | user feedback: anger, wins, hits, falls, relief and the cars all needed sound | angry computer = heartbeat panic bed + two-tone alarm with the music ducked under it; a laugh on every win; falling whistle + "oof" on every fall and hit; a relief sigh; engines whose pitch follows each car's real speed, tyre screech on braking, crash on every bump |
| Contrast beats volume | the alarm measured only +2 dB louder until the music was ducked | `musicDuck` in story.json drops the score under a moment that a sound must own |
