#!/usr/bin/env python3
"""Frame accounting audit: no frame unaccounted for.

    python tools/frame_audit.py [--video output_renders/space_duel.mp4]
                                [--story audio/space_duel/story.json]
                                [--cues audio/space_duel/cues.json]
                                [--rate 2] [--out output_renders/audit]

Checks a rendered film against the measurable rules in docs/STYLE_BIBLE.md,
section 9 ("Frame accounting"):

  Picture (sampled `--rate` times per second from the video):
    F2 space      negative space between 50% and 97% of the frame (hard)
    F1 balance    whole-frame visual-weight centroid within 0.20 of centre
    F3 margin     whole-frame weight in the 96 px border band <= 12%
                  (F1/F3 are info here: set dressing such as Earth's limb
                  may bleed off-frame. The SUBJECT versions, F1s/F3s, are
                  measured exactly from the scene graph by
                  src/space_duel/audit.ts and fail the render.)
  Timeline (from story.json + cues.json):
    T1 sync       every impact event has a sound within 1 frame, and every
                  sound has a visual event within 1 frame (no orphans)
    T2 grid       impacts land on the 8th-note grid (+-1 frame), info only
    T3 dead air   no stretch longer than 4 s with neither a beat/line/event
                  nor visible motion, unless it is a declared hold

Writes <out>/<name>_audit.md (per-second ledger + violations) and a contact
sheet of flagged frames. Exits non-zero if any picture or sync rule fails,
so it can gate a render in CI or n8n.

Requires numpy and ffmpeg (bundled with the Node deps, or on PATH).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
W, H = 480, 270  # analysis resolution (1/4 of 1080p)
SCALE = 1920 / W
MARGIN = round(96 / SCALE)  # 96 px safe margin at analysis scale
FPS = 60

RULES = {
    "F1": ("balance", "whole-frame centroid within 0.20 of centre (info)"),
    "F2": ("space", "negative space 50-97%"),
    "F3": ("margin", "whole-frame border-band weight <= 12% (info)"),
    "T1": ("sync", "every impact has a sound and every sound an event (+-1 frame)"),
    "T2": ("grid", "impacts on the 8th-note grid (+-1 frame)"),
    "T3": ("dead air", "no > 4 s stretch with no beat AND no motion"),
}

# Events that are impacts: they must be heard. Everything else is staging.
IMPACT_PREFIXES = ("clash", "f", "collapse", "disarm", "tunnel", "toss", "catch", "twirl", "flick", "glint", "measure", "spinDown", "arrive", "lock", "barrier")
# Declared holds (style bible: holds after reveals are intended).
HOLDS = {"title", "superpose", "drift", "end"}


def ffmpeg() -> str:
    local = ROOT / "node_modules/@ffmpeg-installer/linux-x64/ffmpeg"
    if local.exists():
        return str(local)
    for name in ("ffmpeg",):
        if shutil.which(name):
            return name
    sys.exit("ffmpeg not found")


def frames(video: Path, rate: float) -> np.ndarray:
    """All sampled frames as float32 luminance [n, H, W]."""
    cmd = [ffmpeg(), "-loglevel", "error", "-i", str(video), "-vf", f"fps={rate},scale={W}:{H}:flags=area", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, H, W).astype(np.float32)


def visual_weight(img: np.ndarray) -> np.ndarray:
    """Luminance above the background, with isolated stars suppressed.

    A 3x3 box average spreads a star's single bright pixel thin, while lines
    and shapes (several pixels wide at this scale) keep their weight.
    """
    bg = np.median(img)
    lum = np.clip(img - bg, 0, None)
    pad = np.pad(lum, 1, mode="edge")
    box = sum(pad[dy : dy + H, dx : dx + W] for dy in range(3) for dx in range(3)) / 9
    return np.where(box > 6, box, 0)


def measure(img: np.ndarray) -> dict:
    w = visual_weight(img)
    total = w.sum()
    if total < 1:
        return {"cx": 0.0, "cy": 0.0, "space": 1.0, "margin": 0.0, "empty": True}
    ys, xs = np.mgrid[0:H, 0:W]
    cx = float((w * xs).sum() / total / W - 0.5)
    cy = float((w * ys).sum() / total / H - 0.5)
    inner = w[MARGIN:-MARGIN, MARGIN:-MARGIN].sum()
    return {
        "cx": cx,
        "cy": cy,
        "space": float((w <= 0).mean()),
        "margin": float(1 - inner / total),
        "empty": False,
    }


def resolve(ref, events: dict, lines: dict) -> float:
    if isinstance(ref, (int, float)):
        return float(ref)
    if "." in ref:
        lid, edge = ref.split(".")
        return lines[lid][edge]
    return events[ref]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=str(ROOT / "output_renders/space_duel.mp4"))
    ap.add_argument("--story", default=str(ROOT / "audio/space_duel/story.json"))
    ap.add_argument("--cues", default=str(ROOT / "audio/space_duel/cues.json"))
    ap.add_argument("--rate", type=float, default=2.0, help="samples per second")
    ap.add_argument("--out", default=str(ROOT / "output_renders/audit"))
    args = ap.parse_args()

    video = Path(args.video)
    name = video.stem
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    story = json.loads(Path(args.story).read_text())
    cues = json.loads(Path(args.cues).read_text())
    events = {k: float(v) for k, v in cues["events"].items()}
    lines = cues["lines"]
    beat = 60 / cues["bpm"]
    frame = 1 / FPS

    # ---- picture ------------------------------------------------------------
    imgs = frames(video, args.rate)
    samples = []
    for i, img in enumerate(imgs):
        t = i / args.rate
        m = measure(img)
        m["t"] = t
        m["flags"] = []
        if not m["empty"]:
            if np.hypot(m["cx"], m["cy"]) > 0.20:
                m["flags"].append("F1")
            if not 0.50 <= m["space"] <= 0.97:
                m["flags"].append("F2")
            if m["margin"] > 0.12:
                m["flags"].append("F3")
        samples.append(m)

    # ---- timeline -------------------------------------------------------------
    sfx_times = []
    for e in story["sfx"]:
        sfx_times.append((resolve(e["at"], events, lines) + e.get("offset", 0.0), e["type"]))
    impacts = {k: v for k, v in events.items() if k.startswith(IMPACT_PREFIXES) and not k.startswith("fight")}
    sync = []
    for k, t in sorted(impacts.items(), key=lambda kv: kv[1]):
        if not any(abs(t - st) <= frame for st, _ in sfx_times):
            sync.append(f"impact `{k}` at {t:.2f}s has no sound")
    for st, typ in sfx_times:
        if not any(abs(st - t) <= frame for t in events.values()) and not any(abs(st - l[e]) <= frame for l in lines.values() for e in ("start", "end")):
            # sounds placed with an offset are still tied to an event
            sync.append(f"sound `{typ}` at {st:.2f}s has no visual event")
    grid = []
    for k, t in sorted(impacts.items(), key=lambda kv: kv[1]):
        off = (t / (beat / 2)) % 1
        if min(off, 1 - off) * (beat / 2) > frame:
            grid.append(f"`{k}` at {t:.2f}s is {min(off, 1 - off) * beat / 2 * 1000:.0f} ms off the 8th-note grid")
    marks = sorted(
        [(t, k) for k, t in events.items()]
        + [(l["start"], f"line {lid}") for lid, l in lines.items()]
        + [(st, f"sfx {typ}") for st, typ in sfx_times]
    )
    # Motion energy between consecutive samples: mean change in visual weight.
    weights = [visual_weight(img) for img in imgs]
    energy = [0.0] + [float(np.abs(b - a).mean()) for a, b in zip(weights, weights[1:])]
    dead = []
    for (t0, k0), (t1, k1) in zip(marks, marks[1:]):
        if t1 - t0 <= 4 or k0 in HOLDS:
            continue
        # The gap is dead only if the picture is also still for > 4 s of it.
        still, run_start = 0.0, None
        for i in range(int(t0 * args.rate), min(len(energy), int(t1 * args.rate))):
            if energy[i] < 0.15:
                run_start = i if run_start is None else run_start
                still = max(still, (i - run_start + 1) / args.rate)
            else:
                run_start = None
        if still > 4:
            dead.append(f"{t0:.1f}s ({k0}) -> {t1:.1f}s ({k1}): {still:.1f} s with no beat and no motion")

    # ---- report -----------------------------------------------------------------
    flagged = [m for m in samples if m["flags"]]
    counts = {r: sum(r in m["flags"] for m in samples) for r in ("F1", "F2", "F3")}
    md = [f"# Frame audit: {name}", ""]
    md.append(f"{len(samples)} frames sampled at {args.rate}/s; {len(flagged)} flagged.")
    md.append("")
    md.append("| rule | what | violations |")
    md.append("| --- | --- | --- |")
    for r in ("F1", "F2", "F3"):
        md.append(f"| {r} {RULES[r][0]} | {RULES[r][1]} | {counts[r]} frames |")
    md.append(f"| T1 sync | {RULES['T1'][1]} | {len(sync)} |")
    md.append(f"| T2 grid | {RULES['T2'][1]} | {len(grid)} (info) |")
    md.append(f"| T3 dead air | {RULES['T3'][1]} | {len(dead)} |")
    md.append("")
    for title, items in (("Sync (T1)", sync), ("Grid (T2, info)", grid), ("Dead air (T3)", dead)):
        if items:
            md.append(f"## {title}")
            md += [f"- {x}" for x in items]
            md.append("")
    md.append("## Per-second ledger")
    md.append("")
    md.append("| s | events / lines / sounds | balance (cx, cy) | space | margin | flags |")
    md.append("| --- | --- | --- | --- | --- | --- |")
    for sec in range(int(np.ceil(len(samples) / args.rate))):
        here = [m for m in samples if sec <= m["t"] < sec + 1]
        if not here:
            continue
        what = ", ".join(sorted({k for t, k in marks if sec <= t < sec + 1})) or "(continuing)"
        cx = np.mean([m["cx"] for m in here])
        cy = np.mean([m["cy"] for m in here])
        sp = np.mean([m["space"] for m in here])
        mg = max(m["margin"] for m in here)
        fl = " ".join(sorted({f for m in here for f in m["flags"]}))
        md.append(f"| {sec} | {what} | {cx:+.2f}, {cy:+.2f} | {sp:.0%} | {mg:.0%} | {fl} |")
    report = out / f"{name}_audit.md"
    report.write_text("\n".join(md) + "\n")

    # Contact sheet of up to 24 flagged frames.
    if flagged:
        sheet = out / f"{name}_flagged.png"
        picks = flagged[:: max(1, len(flagged) // 24)][:24]
        select = "+".join(f"eq(n\\,{int(round(m['t'] * args.rate))})" for m in picks)
        subprocess.run(
            [ffmpeg(), "-loglevel", "error", "-y", "-i", str(video), "-vf",
             f"fps={args.rate},select='{select}',scale=480:-1,drawtext=text='%{{pts\\:hms}}':x=6:y=6:fontcolor=white:fontsize=18,tile=6x4",
             "-frames:v", "1", str(sheet)],
            check=False,
        )

    print(f"audit: {len(samples)} frames, {len([m for m in samples if 'F2' in m['flags']])} hard-flagged; info "
          f"(F1 {counts['F1']}, F2 {counts['F2']}, F3 {counts['F3']}); "
          f"sync {len(sync)}, grid {len(grid)} (info), dead air {len(dead)}")
    print(f"report: {report.relative_to(ROOT) if report.is_relative_to(ROOT) else report}")
    hard = [m for m in samples if "F2" in m["flags"]]
    failed = bool(hard) or bool(sync) or bool(dead)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
