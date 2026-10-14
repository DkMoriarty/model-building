# Teardown: how a wordless film shows typed code

- **Source:** "Animation vs. Coding" (YouTube `EFmxPMdBqmU`), a third vidIQ
  pass on 2026-10-14, focused on code presentation. Technique only. Our
  code, font colours and layouts are our own.

## What it does

| aspect | observed |
| --- | --- |
| **Typing** | character by character, **8–18 chars/s** (standard about 10–14); a thick blinking underscore cursor leads each keystroke |
| **Sound** | one key click per character, strictly 1:1, with slight pitch variation |
| **Editing** | a selection or paste shows a grey highlight box for 4–8 frames, then the text changes in 1–2 frames |
| **Type** | monospace; a short active line is **8–12% of frame height**; long listings 3–5% |
| **Colour** | high-contrast text on near-black; syntax colouring separates keywords, values, function names and errors (errors on a red banner) |
| **Camera** | for short code it is close: text fills 40–50% of the frame and holds 1–2 s; then the camera pulls back so the result fills the arena |
| **Cause → effect** | the result fires **0–6 frames** after the last key (Enter); simple code and its result share **one shot** |
| **Reading time** | the code stays still for ≥ 1 s after the last character, plus about 0.3 s per extra line |
| **Rhythm** | 1–2.5 s of code, then 2–4 s of the character dealing with the result; fast edits (one character) update in a frame |

## Rules we adopt (style bible §5, "On-screen code")

- **K1 Readable:** the active line is ≥ 7% of frame height on screen
  (≥ 75 px at 1080p), in monospace; at most 3 lines in view.
- **K2 Typed, not pasted:** 12 chars/s; one key click per character; a
  blinking cursor; Enter makes a heavier key sound.
- **K3 Same shot:** the camera pushes in on the screen so the code *and* the
  game picture are both in frame; the result fires 6 frames after Enter.
- **K4 Hold:** ≥ 1.0 s on the finished code and its result before the
  camera pulls back out to the character's reaction.
- **K5 Real code:** every line is valid code that would do what we show;
  the picture obeys the numbers in it (gravity, jump speed, spring
  strength). A bug is a real bug (a missing collision, a typo).
- **K6 Edits read as edits:** fixing a typo moves the cursor to it and
  deletes one character, with a highlight flash on the changed spot.
