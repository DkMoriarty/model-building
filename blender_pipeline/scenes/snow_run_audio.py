"""SNOW RUN soundtrack: an original swing-jazz loop plus sound effects on the
picture's frames, then the phone-safe MP4.

    python3 blender_pipeline/scenes/snow_run_audio.py --out renders/snow_run

Music (all synthesized, nothing sampled): 132 bpm swing in F, a ii-V-I-VI
loop (Gm7 C7 Fmaj7 D7): walking bass, ride cymbal with brushes, soft
electric-piano comping and a short vibraphone motif. Effects follow the
shots in snow_run.py: snow swish while carving (louder with speed), a puff
on takeoff, a thump and crunch on the landing, a metal scrape on the rail,
wind in the air. Highs are kept soft (low-passed), the melody sits in the
phone band (500 Hz - 1 kHz).
"""

import argparse
import os
import subprocess
import wave

import numpy as np

SR = 44100
FPS = 24
FRAMES = 336
# Shot timing, mirrored from snow_run.SHOTS (that module needs Blender).
SHOTS = [("LEDGE", 1, 48), ("CARVE", 49, 132), ("RAIL", 133, 204), ("SUNSET", 205, 264), ("LAND", 265, 336)]
DUR = FRAMES / FPS
N = int(DUR * SR) + SR // 2
rng = np.random.default_rng(1729)


def t_of(frame):
    return (frame - 1) / FPS


def lowpass(x, cutoff):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / np.sqrt(1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x))


def bandpass(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / np.sqrt(1 + (f / hi) ** 4) * (1 - 1 / np.sqrt(1 + (f / lo) ** 4))
    return np.fft.irfft(X, len(x))


def place(buf, sig, t0, gain=1.0):
    i = int(t0 * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += gain * sig[: j - i]


def env(n, a=0.005, d=0.3):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / d)


def tone(freq, dur, harm=(1.0,), a=0.005, d=0.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = sum(h * np.sin(2 * np.pi * freq * (k + 1) * t) for k, h in enumerate(harm))
    return s * env(n, a, d)


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# ---------------------------------------------------------------------------
# Music
# ---------------------------------------------------------------------------

BPM = 132
BEAT = 60 / BPM
SWING = 0.62          # long-short eighths
CHORDS = [  # (bass walk for 4 beats, piano voicing)
    ([43, 46, 50, 49], [58, 62, 65, 69]),   # Gm7  (G Bb D Db->)
    ([48, 52, 55, 54], [58, 62, 64, 67]),   # C7   (C E G F#->)
    ([41, 45, 48, 50], [57, 60, 64, 67]),   # Fmaj7
    ([50, 54, 45, 44], [57, 60, 62, 66]),   # D7   (D F# A Ab->)
]


def music():
    out = np.zeros(N)
    bars = int(DUR / (4 * BEAT)) + 2
    for b in range(bars):
        bass, voicing = CHORDS[b % 4]
        t_bar = b * 4 * BEAT
        for k, m in enumerate(bass):  # walking bass: plucked, warm
            # strong upper harmonics so the walk is heard on phone speakers
            place(out, tone(midi(m), BEAT * 1.1, (0.6, 0.8, 0.55, 0.3), a=0.008, d=0.35), t_bar + k * BEAT, 0.16)
        for beat in range(4):         # ride: ding (beat) ding-da (swung)
            t = t_bar + beat * BEAT
            place(out, ride(), t, 0.16)
            if beat in (1, 3):
                place(out, ride(), t + SWING * BEAT, 0.1)
                place(out, brush(), t, 0.22)
        for beat, frac in ((1, SWING), (3, 0.0)):  # piano comping: and-of-2, beat 4
            for m in voicing:
                place(out, tone(midi(m), BEAT * 0.9, (1.0, 0.3, 0.08), a=0.01, d=0.45), t_bar + (beat + frac) * BEAT, 0.11)
    # Vibraphone motif in the phone band, every other bar.
    motif = [(0, 72), (0.75, 74), (1.5, 77), (2.0, 76), (2.75, 72)]
    for b in range(0, bars, 2):
        for off, m in motif:
            place(out, vibe(midi(m)), b * 4 * BEAT + off * BEAT, 0.24)
    return lowpass(out, 5000)


def ride():
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    partials = sum(np.sin(2 * np.pi * f * t + p) for f, p in ((3150, 0.2), (4370, 1.1), (5230, 2.3), (6620, 0.7)))
    noise = bandpass(rng.standard_normal(n), 3000, 7000)
    return (0.5 * partials / 4 + 0.5 * noise / (np.abs(noise).max() + 1e-9)) * env(n, 0.002, 0.22)


def brush():
    n = int(0.25 * SR)
    noise = bandpass(rng.standard_normal(n), 400, 3000)
    return noise / (np.abs(noise).max() + 1e-9) * env(n, 0.02, 0.08)


def vibe(f):
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    trem = 1 + 0.25 * np.sin(2 * np.pi * 5.5 * t)
    return (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t / 0.05)) * env(n, 0.003, 0.7) * trem


# ---------------------------------------------------------------------------
# Effects
# ---------------------------------------------------------------------------

def noise_seg(dur, lo, hi):
    n = int(dur * SR)
    x = bandpass(rng.standard_normal(n), lo, hi)
    return x / (np.abs(x).max() + 1e-9)


def effects():
    out = np.zeros(N)
    # Snow carve: continuous swish while on snow, swelling with each carve.
    for name, a, b in SHOTS:
        if name in ("CARVE", "LAND"):
            start = t_of(a) + (0.55 if name == "LAND" else 0.0)
            dur = t_of(b + 1) - start
            n = int(dur * SR)
            t = np.arange(n) / SR
            sw = noise_seg(dur, 500, 3500) * (0.55 + 0.45 * np.abs(np.sin(t * 3.2))) * np.minimum(1, t / 0.08)
            fade = np.minimum(1, (dur - t) / 0.05)
            place(out, sw * fade, start, 0.22)
    # Takeoff puff (shot 1) and the landing thump + crunch (shot 5).
    place(out, noise_seg(0.35, 300, 2500) * env(int(0.35 * SR), 0.005, 0.1), t_of(1), 0.35)
    land = t_of(265) + 0.55
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    thump = (np.sin(2 * np.pi * (90 - 40 * t) * t) + 0.6 * np.sin(2 * np.pi * (260 - 80 * t) * t)) * env(n, 0.002, 0.12)
    place(out, thump, land, 0.45)
    place(out, noise_seg(0.4, 400, 3000) * env(int(0.4 * SR), 0.003, 0.12), land, 0.4)
    # Rail: a clack on contact, then a grainy metal scrape for the slide.
    a, b = 133, 204
    place(out, noise_seg(0.08, 800, 4000) * env(int(0.08 * SR), 0.001, 0.02), t_of(a), 0.45)
    dur = t_of(b + 1) - t_of(a)
    n = int(dur * SR)
    t = np.arange(n) / SR
    scrape = noise_seg(dur, 1200, 4500) * (0.6 + 0.4 * np.sin(2 * np.pi * 13 / 2 * t) ** 2)
    scrape *= np.minimum(1, t / 0.03) * np.minimum(1, (dur - t) / 0.05)
    place(out, scrape, t_of(a), 0.2)
    # Wind in the air: low and soft (shots 1 and 4).
    for name, a, b in SHOTS:
        if name in ("LEDGE", "SUNSET"):
            dur = t_of(b + 1) - t_of(a)
            n = int(dur * SR)
            t = np.arange(n) / SR
            w = noise_seg(dur, 150, 900) * np.sin(np.pi * t / dur) ** 0.5
            place(out, w, t_of(a), 0.18)
    return lowpass(out, 6000)


def write_wav(path, x):
    x = x / (np.abs(x).max() + 1e-9) * 0.89
    st = np.stack([x, x], axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="renders/snow_run")
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    mix = 0.7 * music() + effects()
    mix = mix[: int(DUR * SR)]
    fade = np.ones(len(mix))
    fade[-int(0.6 * SR):] = np.linspace(1, 0, int(0.6 * SR))
    wav = os.path.join(a.out, "snow_run.wav")
    write_wav(wav, mix * fade)
    print("wrote", wav)
    if a.no_video:
        return
    mp4 = os.path.join(a.out, "snow_run.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i",
                    os.path.join(a.out, "frames", "f%03d.png"), "-i", wav, "-vf", "scale=1280:-2,format=yuv420p",
                    "-c:v", "libx264", "-profile:v", "main", "-crf", "18", "-c:a", "aac", "-ar", "44100", "-ac", "2",
                    "-shortest", "-movflags", "+faststart", mp4], check=True)
    print("wrote", mp4)


if __name__ == "__main__":
    main()
