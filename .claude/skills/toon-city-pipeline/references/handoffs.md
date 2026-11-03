# Hand-off templates

All files live under `alan_pipeline/docs/production/<ep>/`.

## Shot id
`<ep-abbrev>_sq<NN>_sh<NNN>`. Example: `fg_sq03_sh021`. Number shots in steps of 10
(010, 020…) so inserts fit in without renumbering.

## board.md (owned by production-coordinator)
```markdown
# <Episode> production board
Timeline locked at: <commit> · Audio built: <date>

| shot | cues (start → end) | field | owner | status | last note |
|---|---|---|---|---|---|
| fg_sq01_sh010 | cold_open → spark_sees_door | wide | key-animator | wip | — |
```
Statuses: `waiting → wip → review → notes → approved → final`.
Approved and final shots are frozen.

## shots.md (owned by story-animatic-lead, marks added by layout-artist)
```markdown
| shot | cues | field | camera move | characters (marks, facing) | props | action (one line) | want → result → reaction |
|---|---|---|---|---|---|---|---|
| fg_sq01_sh010 | cold_open → spark_sees_door | wide → medium | push in 1.0→1.4 | Spark x −230 → 40, faces +x | door, key | Spark walks to the door, tries it: locked | open door → locked → slump |
```

## Work order (coordinator → department agent)
```
Episode: <ep>        Shots: <ids>
Read first: .claude/agents/<agent>.md, alan_pipeline/CLAUDE.md, <specific files>
Inputs (locked): <files + commit>
Produce: <files>
Gate: <exact command(s)> must show <expected result>
Do not touch: <approved shots / files>
Return: what changed (files), gate output, open questions
```

## notes.md (owned by qc-reviewer)
```markdown
## Pass <n> · <date> · scope: <shots>
typecheck: ok · probe: 0 late / 0 miss · audit: 0 hard, sync 0, dead air 0

| # | shot | at / cue | note | rule | severity | owner |
|---|---|---|---|---|---|---|
| 1 | fg_sq03_sh021 | 41.2 s spark_reaches_key | hand stops ~10 px short of key | rig: checkReach | hard | character-rigger |

Verdict: RETAKE: character-rigger → key-animator   (or APPROVED)
```
