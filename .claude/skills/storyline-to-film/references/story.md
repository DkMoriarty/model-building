# Refining a storyline

The user writes fast, loose storylines ("then he wanders, a shadow appears,
win or die, three games, a car race, he wakes up"). Your job is to make every
beat unmistakable on screen, without words, while keeping their story.

## Step by step

1. **List the user's beats verbatim, numbered.** Every one must appear in the
   film, in that order. Approved parts of an earlier version stay untouched.
2. **Name the want in each beat as an object in frame (C1).** "He wants to go
   home" becomes "a door with his room inside it, locked by three lights".
   "Win three games" becomes three lock lights, one lit per win, shown in the
   HUD of every round.
3. **Write each beat as want / try / result / reaction (C3).** Every result
   gets a reaction hold (C4): 12-24 f, 1-2 s at turning points.
4. **Cause -> effect -> new question.** The villain's power comes from what
   the hero just did (the computer learns *because* it lost). Each beat's
   result is the next beat's problem.
5. **Set-ups and pay-offs (C9).** Plant every solution before it is used
   (C8): the speed-3000 glitch is typed in act 1 and wins round 1; the door
   with the room in it appears early and opens at the end; the clock and the
   window at night pay off as sunrise. Write them in a table.
6. **Escalate.** Rounds get harder and change genre ("multiverse": a new
   colour universe per round). Rule of three where attempts matter (C5).
7. **Make it physical.** Abstract ideas become things a child already knows:
   a falling block, a car that can't stop, a ball that skips a paddle.
8. **The bookend.** The last image answers the first want (the game he wanted
   to play; waking at his desk at sunrise).
9. **Clarity pass.** Read each beat as a viewer seeing it once with no sound:
   is the goal in frame? Is the cause in the same shot as the effect (C6)?
   One action at a time (C7)? If something confusing starts, pull back (C10).
10. **Write it down** in `docs/episodes/<episode>.md`: a beat table
    (# / beat / want and goal object / what we see / reaction), the set-up and
    pay-off list, and any deviations from the user's text with the reason.

## On-screen text and code

- Text only where a game or computer would show it (HUD labels, a typed
  threat, code). Typed at 12 chars/s with a tick per character.
- Code is real and minimal, one line at a time, readable (K1: the active line
  at least 7% of frame height), zoomed in, then pull back for the reaction (K3, K4).
- A villain who "speaks" types in red terminal text, short lines, one at a time.

## Pacing

- 3:00 is a good length. Saw tooth: after every peak, a 2-5 s breather with a
  small human moment, then a higher peak.
- Silence (a duck of everything) for 0.3-0.6 s right before a big reveal or crash.
