"""CROSSWALK soundtrack: synthesized ambience, music and effects on the
picture's frames, then the phone-safe MP4.

    python3 blender_pipeline/characters3d/street_scene_audio.py --out renders/crosswalk

- City air: soft traffic rumble, a breeze, birds.
- A lo-fi groove (plucked chords, soft kick and brushes) while he cruises;
  it cuts dead on the skid (contrast beats volume).
- Chain whir ticking with his pedal strokes; a tyre screech on the skid;
  her small gasp; a heartbeat and a rising chime glissando for the awe,
  and a soft sparkle for each heart.
Timings mirror street_scene.py (that module needs Blender).
"""

import argparse
import os
import subprocess
import wave

import numpy as np

SR, FPS, LAST = 44100, 24, 312
DUR = LAST / FPS
N = int(DUR * SR) + SR
T_BRAKE = (151 - 1) / FPS
T_STOP = T_BRAKE + 4.2 / 7.0
V_RIDE, WHEEL_R = 4.2, 0.34
rng = np.random.default_rng(7)


def lowpass(x, fc):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X / np.sqrt(1 + (f / fc) ** 4), len(x))


def bandpass(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X / np.sqrt(1 + (f / hi) ** 4) * (1 - 1 / np.sqrt(1 + (f / lo) ** 4)), len(x))


def env(n, a=0.005, d=0.3):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / d)


def place(buf, sig, t0, g=1.0):
    i = int(t0 * SR)
    j = min(len(buf), i + len(sig))
    if i < len(buf):
        buf[i:j] += g * sig[: j - i]


def norm(x):
    return x / (np.abs(x).max() + 1e-9)


def pluck(f, dur=1.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t) + 0.15 * np.sin(6 * np.pi * f * t)) * env(n, 0.004, 0.45)


def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


def ambience():
    out = np.zeros(N)
    out += 0.1 * norm(lowpass(rng.standard_normal(N), 180))           # distant traffic rumble (kept low: phones cannot play it)
    out += 0.12 * norm(bandpass(rng.standard_normal(N), 300, 1500)) * (0.6 + 0.4 * np.sin(np.arange(N) / SR * 0.7))
    for k in range(9):                                                   # birds: quick chirps
        t0 = 0.6 + k * 1.37 + rng.uniform(0, 0.4)
        for c in range(rng.integers(2, 4)):
            n = int(0.07 * SR)
            t = np.arange(n) / SR
            f = 2600 + 900 * np.sin(np.pi * t / 0.07) + rng.uniform(-200, 200)
            place(out, np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.005, 0.03), t0 + c * 0.11, 0.18)
    return out


def groove():
    """Lo-fi: Fmaj7 - Em7 - Dm7 - Cmaj7 plucked, soft kick and brush, 84 bpm, until the skid."""
    out = np.zeros(N)
    beat = 60 / 84
    chords = [[53, 57, 60, 64], [52, 55, 59, 62], [50, 53, 57, 60], [48, 52, 55, 59]]
    t = 0.0
    bar = 0
    while t < T_BRAKE:
        for k, m in enumerate(chords[bar % 4]):
            place(out, pluck(midi(m + 12)), t + k * 0.03, 0.12)
            place(out, pluck(midi(m + 12)), t + 2 * beat + 0.15 + k * 0.03, 0.08)
        for b in range(4):
            tb = t + b * beat
            if b in (0, 2):
                n = int(0.25 * SR)
                tt = np.arange(n) / SR
                place(out, np.sin(2 * np.pi * (110 - 60 * tt) * tt) * env(n, 0.002, 0.08), tb, 0.18)
            else:
                place(out, norm(bandpass(rng.standard_normal(int(0.15 * SR)), 600, 3500)) * env(int(0.15 * SR), 0.01, 0.05), tb, 0.08)
        t += 4 * beat
        bar += 1
    cut = int(T_BRAKE * SR)
    out[cut:] = 0.0                                                      # hard cut on the skid
    return out


def effects():
    out = np.zeros(N)
    # Chain whir: a tick per chain link, rate from his speed, until he locks up.
    n = int(T_BRAKE * SR)
    t = np.arange(n) / SR
    crank_hz = V_RIDE / (2 * np.pi * WHEEL_R) / 2.6
    ticks = (np.sin(2 * np.pi * crank_hz * 46 * t) > 0.97).astype(float)
    whir = lowpass(ticks * rng.standard_normal(n), 3500)
    out[:n] += 0.08 * norm(whir)
    # Screech: tyre skid, falling pitch, noisy, then silence.
    d = T_STOP - T_BRAKE + 0.1
    n = int(d * SR)
    t = np.arange(n) / SR
    f = 1500 - 500 * t / d
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
    sk = (0.6 * tone + norm(bandpass(rng.standard_normal(n), 800, 3500))) * np.minimum(1, t / 0.02) * np.minimum(1, (d - t) / 0.08)
    place(out, lowpass(sk, 4000), T_BRAKE, 0.5)
    # Her gasp: breathy in-breath.
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    g = norm(bandpass(rng.standard_normal(n), 900, 3000)) * np.sin(np.pi * t / 0.35) ** 2
    place(out, g, T_BRAKE + 0.2, 0.3)
    # Heartbeat through the awe.
    for k in range(7):
        tb = T_STOP + 0.5 + k * 0.75
        for off, a in ((0.0, 1.0), (0.17, 0.7)):
            n = int(0.18 * SR)
            t = np.arange(n) / SR
            place(out, np.sin(2 * np.pi * (70 - 25 * t) * t) * env(n, 0.003, 0.07) + 0.4 * np.sin(2 * np.pi * 210 * t) * env(n, 0.002, 0.03), tb + off, 0.5 * a)
    # Rising chime glissando at the moment he's struck, and sparkles with the hearts.
    for k, m in enumerate([72, 76, 79, 83, 84, 88, 91]):
        place(out, pluck(midi(m), 1.6) * 0.9, T_STOP + 0.55 + k * 0.07, 0.12)
    for i in range(4):
        t0 = T_STOP + 0.8 + i * 0.6
        for k, m in enumerate((96, 100)):
            place(out, pluck(midi(m), 0.6), t0 + k * 0.05, 0.05)
    return out


def write(path, x):
    x = norm(x) * 0.89
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.stack([x, x], 1) * 32767).astype(np.int16).tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="renders/crosswalk")
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    mix = (ambience() + groove() + effects())[: int(DUR * SR)]
    mix[-int(0.5 * SR):] *= np.linspace(1, 0, int(0.5 * SR))
    wav = os.path.join(a.out, "crosswalk.wav")
    write(wav, lowpass(mix, 6000))
    print("wrote", wav)
    if a.no_video:
        return
    mp4 = os.path.join(a.out, "crosswalk.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(a.out, "frames", "f%03d.png"),
                    "-i", wav, "-vf", "scale=1280:-2,format=yuv420p", "-c:v", "libx264", "-profile:v", "main", "-crf", "18",
                    "-c:a", "aac", "-ar", "44100", "-ac", "2", "-shortest", "-movflags", "+faststart", mp4], check=True)
    print("wrote", mp4)


if __name__ == "__main__":
    main()
