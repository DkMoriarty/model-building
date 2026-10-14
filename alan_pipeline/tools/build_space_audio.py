#!/usr/bin/env python3
"""Build the soundtrack and cue sheet for an episode (default: space_duel).

    python tools/build_space_audio.py [--episode NAME] [--voices DIR] [--piper PATH] [--retts]

Reads   audio/<episode>/story.json    (narration, events, sfx, music sections,
                                       optional designed silences)
Writes  audio/<episode>/voice/*.wav   (TTS clips, cached: Piper is not
                                       bit-deterministic, so the clips are the
                                       committed source of truth)
        audio/<episode>/cues.json     (resolved times the scene animates to)
        audio/<episode>/master.wav    (48 kHz stereo mix)

Picture and sound share one timeline. Every narration line's real start and
end, every fight event and every sound effect comes from the same story file,
so a hit can never land off its sound. Event times may reference narration
lines ("n14.end"), so a visual beat can land exactly as a sentence finishes.
The build fails if a line overruns the next one.

Requires numpy. Piper (pip install piper-tts) plus voice models are only needed
when a line's text, voice or speed changes (or with --retts).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "audio" / "space_duel"  # set from --episode in main()
SR = 48000
VOICE_SR = 24000
RNG = np.random.default_rng(20261013)


# --------------------------------------------------------------------------- io


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64)
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data / 32768.0, sr


def write_wav(path: Path, stereo: np.ndarray, sr: int = SR) -> None:
    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(stereo.shape[1] if stereo.ndim == 2 else 1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def resample(x: np.ndarray, sr_from: float, sr_to: float) -> np.ndarray:
    n = int(round(len(x) * sr_to / sr_from))
    return np.interp(np.arange(n) * sr_from / sr_to, np.arange(len(x)), x)


# ------------------------------------------------------------------------- dsp


def spectral_filter(x: np.ndarray, low: float = 0.0, high: float = SR / 2) -> np.ndarray:
    """Zero-phase band-pass with smooth (raised-cosine, half-octave) edges."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    gain = np.ones_like(f)
    if low > 0:
        lo = np.clip(np.log2(np.maximum(f, 1e-3) / low) / 0.5 + 1, 0, 1)
        gain *= 0.5 - 0.5 * np.cos(np.pi * lo)
    if high < SR / 2:
        hi = np.clip(np.log2(high / np.maximum(f, 1e-3)) / 0.5 + 1, 0, 1)
        gain *= 0.5 - 0.5 * np.cos(np.pi * hi)
    return np.fft.irfft(spec * gain, n=len(x))


def env_adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    t = np.arange(n) / SR
    total = n / SR
    e = np.where(t < a, t / max(a, 1e-6), 1.0)
    e = np.where((t >= a) & (t < a + d), 1 - (1 - s) * (t - a) / max(d, 1e-6), e)
    e = np.where(t >= a + d, s, e)
    rel = np.clip((total - t) / max(r, 1e-6), 0, 1)
    return e * rel


def smooth(x: np.ndarray, seconds: float) -> np.ndarray:
    k = max(1, int(seconds * SR))
    c = np.cumsum(np.insert(np.abs(x), 0, 0))
    out = (c[k:] - c[:-k]) / k
    return np.concatenate([out, np.full(k - 1, out[-1])])


def midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def saw(freq: float, n: int, harmonics: int = 8, detune: float = 0.0) -> np.ndarray:
    t = np.arange(n) / SR
    out = np.zeros(n)
    f = freq * (1 + detune)
    for k in range(1, harmonics + 1):
        if f * k > SR / 2.2:
            break
        out += np.sin(2 * np.pi * f * k * t + k) / k
    return out


def add(buf: np.ndarray, at: float, sig: np.ndarray, gain: float = 1.0) -> None:
    i = int(round(at * SR))
    if i >= len(buf) or i + len(sig) <= 0:
        return
    j0 = max(0, -i)
    j1 = min(len(sig), len(buf) - i)
    buf[i + j0 : i + j1] += sig[j0:j1] * gain


# ------------------------------------------------------------------------- sfx


def sfx_clash(length: float = 1.6) -> np.ndarray:
    """Struck metal: inharmonic bar modes (1, 2.76, 5.40, 8.93) + a bright tick."""
    n = int(length * SR)
    t = np.arange(n) / SR
    base = 420 * (1 + RNG.uniform(-0.06, 0.06))
    out = np.zeros(n)
    for ratio, amp, decay in [(1, 1.0, 3.5), (2.76, 0.7, 5), (5.40, 0.45, 8), (8.93, 0.3, 12), (13.3, 0.18, 18)]:
        out += amp * np.sin(2 * np.pi * base * ratio * t + RNG.uniform(0, 6)) * np.exp(-decay * t)
    tick = spectral_filter(RNG.normal(0, 1, n), 2500) * np.exp(-t * 90) * 0.9
    thump = np.sin(2 * np.pi * (70 + 90 * np.exp(-t * 25)) * t) * np.exp(-t * 10) * 0.9
    return (out * 0.35 + tick + thump) * 0.8


def sfx_tink(length: float = 0.7) -> np.ndarray:
    """A small metal part tapped: a short, bright bar ring."""
    n = int(length * SR)
    t = np.arange(n) / SR
    base = 1850 * (1 + RNG.uniform(-0.03, 0.03))
    out = sum(a * np.sin(2 * np.pi * base * r * t) * np.exp(-d * t) for r, a, d in [(1, 1, 9), (2.76, 0.5, 14), (5.4, 0.25, 22)])
    return out * 0.22


def sfx_whoosh(length: float = 0.9) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n) / SR
    noise = RNG.normal(0, 1, n)
    swept = spectral_filter(noise, 300, 3500)
    e = np.sin(np.pi * np.clip(t / length, 0, 1)) ** 2
    return swept * e * 0.35


def sfx_thrust(length: float) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n) / SR
    rumble = spectral_filter(RNG.normal(0, 1, n), 40, 400)
    hiss = spectral_filter(RNG.normal(0, 1, n), 2000, 7000) * 0.25
    flutter = 1 + 0.3 * np.sin(2 * np.pi * 23 * t)
    return (rumble + hiss) * flutter * env_adsr(n, 0.08, 0.2, 0.8, 0.35) * 0.45


def sfx_boom(length: float = 3.0) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * (38 + 60 * np.exp(-t * 6)) * t) * np.exp(-t * 1.6)
    body = spectral_filter(RNG.normal(0, 1, n), 30, 900) * np.exp(-t * 3) * 0.6
    return (sub + body) * 0.8


def sfx_riser(length: float) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n) / SR
    f = 120 * 2 ** (3 * t / length)
    phase = 2 * np.pi * np.cumsum(f) / SR
    tone = np.sin(phase) + 0.5 * np.sin(2 * phase + 0.3)
    air = spectral_filter(RNG.normal(0, 1, n), 1500, 9000) * 0.4
    return (tone * 0.4 + air) * (t / length) ** 2 * 0.5


def sfx_hum(length: float) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n) / SR
    f = 110 * (1 + 0.004 * np.sin(2 * np.pi * 5 * t))
    phase = 2 * np.pi * np.cumsum(f) / SR
    tone = sum(np.sin(k * phase) / k for k in (1, 2, 3, 5))
    return tone * env_adsr(n, 0.3, 0.4, 0.6, 0.5) * 0.35


def sfx_spin(length: float) -> np.ndarray:
    """Air-less spin: a rising tremolo whose rate tracks the angular speed."""
    n = int(length * SR)
    t = np.arange(n) / SR
    rate = 3 + 9 * np.clip(t / (length * 0.5), 0, 1)
    trem = 0.5 + 0.5 * np.sin(2 * np.pi * np.cumsum(rate) / SR)
    tone = spectral_filter(RNG.normal(0, 1, n), 200, 1200)
    return tone * trem * env_adsr(n, 0.4, 0.5, 0.8, 0.8) * 0.4


def sfx_shimmer(length: float) -> np.ndarray:
    """Superposition: many detuned partials beating against each other."""
    n = int(length * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k in range(9):
        f = midi(76 + [0, 3, 7, 10, 12, 15, 19, 22, 24][k]) * (1 + RNG.uniform(-0.004, 0.004))
        out += np.sin(2 * np.pi * f * t + RNG.uniform(0, 6)) * (0.5 + 0.5 * np.sin(2 * np.pi * RNG.uniform(0.2, 0.9) * t))
    return out / 9 * env_adsr(n, 1.2, 0.5, 0.8, 1.5) * 0.5


def sfx_collapse(length: float = 1.4) -> np.ndarray:
    """Measurement: shimmer sucked into a single pure tone, then a click."""
    n = int(length * SR)
    t = np.arange(n) / SR
    pre = int(0.35 * SR)
    swell = np.zeros(n)
    tp = t[:pre]
    swell[:pre] = spectral_filter(RNG.normal(0, 1, pre), 2000, 9000) * (tp / 0.35) ** 3 * 0.6
    tone = np.zeros(n)
    tone[pre:] = np.sin(2 * np.pi * midi(88) * (t[pre:] - t[pre])) * np.exp(-(t[pre:] - t[pre]) * 3)
    click = np.zeros(n)
    click[pre : pre + 200] = np.hanning(200)
    return (swell + tone * 0.5 + click) * 0.7


def sfx_barrier(length: float) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n) / SR
    tone = sum(np.sin(2 * np.pi * midi(n_) * t) for n_ in (57, 64, 69))
    pulse = 0.7 + 0.3 * np.sin(2 * np.pi * 2 * t)
    return tone / 3 * pulse * env_adsr(n, 0.25, 0.3, 0.7, 0.6) * 0.3


def sfx_tunnel(length: float = 1.4) -> np.ndarray:
    """Tunnelling: a descending glide that thins out (exponential decay)."""
    n = int(length * SR)
    t = np.arange(n) / SR
    f = 1600 * 2 ** (-3 * t / length)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return tone * np.exp(-t * 2.2) * 0.45 + sfx_clash(length)[:n] * 0.35


def sfx_grind(length: float) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n) / SR
    noise = spectral_filter(RNG.normal(0, 1, n), 600, 4000)
    am = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 31 * t))
    return noise * am * env_adsr(n, 0.1, 0.3, 0.7, 0.6) * 0.35


def sfx_measure(length: float = 1.2) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n) / SR
    up = np.sin(2 * np.pi * np.cumsum(midi(81) * 2 ** (t / length)) / SR)
    return up * np.exp(-t * 2.5) * 0.4


def sfx_zap(length: float = 0.7) -> np.ndarray:
    """Electric shock: crackling broadband bursts over a 120 Hz buzz."""
    n = int(length * SR)
    t = np.arange(n) / SR
    crackle = spectral_filter(RNG.normal(0, 1, n), 1500, 12000)
    gate = (RNG.uniform(0, 1, n // 240 + 1) > 0.45).repeat(240)[:n]
    buzz = np.sign(np.sin(2 * np.pi * 120 * t)) * 0.4
    return (crackle * gate + buzz) * np.exp(-t * 4) * 0.55


def sfx_click(length: float = 0.12) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n) / SR
    return (spectral_filter(RNG.normal(0, 1, n), 1200, 9000) * np.exp(-t * 160) + np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 90) * 0.3) * 0.6


def sfx_tick(length: float = 0.1) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * 3200 * t) * np.exp(-t * 120) * 0.35


def sfx_thud(length: float = 0.5) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * (60 + 80 * np.exp(-t * 30)) * t) * np.exp(-t * 14)
    slap = spectral_filter(RNG.normal(0, 1, n), 200, 2500) * np.exp(-t * 60) * 0.5
    return (body + slap) * 0.7


def sfx_blip(length: float = 0.5) -> np.ndarray:
    """A bulb coming on: a soft rising glass tone."""
    n = int(length * SR)
    t = np.arange(n) / SR
    f = midi(84) * (1 + 0.05 * (1 - np.exp(-t * 30)))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6) * 0.3


def sfx_bzz(length: float = 1.0) -> np.ndarray:
    """Current pressing against an open gap: a thin, uneasy 60 Hz fizz."""
    n = int(length * SR)
    t = np.arange(n) / SR
    tone = spectral_filter(np.sign(np.sin(2 * np.pi * 60 * t)), 300, 3000)
    return tone * env_adsr(n, 0.05, 0.2, 0.6, 0.3) * 0.25


def sfx_buzzer(length: float = 6.0) -> np.ndarray:
    """The self-blinking relay: clicks that speed up from 8th notes to a rattle."""
    n = int(length * SR)
    out = np.zeros(n)
    t = 0.0
    period = 0.3
    while t < length - 0.05:
        add(out, t, sfx_click() * 0.7)
        t += period
        period = max(0.06, period * 0.93)
    return out


def sfx_sizzle(length: float = 3.0) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n) / SR
    noise = spectral_filter(RNG.normal(0, 1, n), 3000, 12000)
    return noise * (t / length) ** 2 * 0.35


def sfx_pop(length: float = 0.6) -> np.ndarray:
    """A bulb bursting: a sharp pop and a little air."""
    n = int(length * SR)
    t = np.arange(n) / SR
    pop = spectral_filter(RNG.normal(0, 1, n), 400, 8000) * np.exp(-t * 45)
    low = np.sin(2 * np.pi * (90 + 200 * np.exp(-t * 40)) * t) * np.exp(-t * 20) * 0.6
    return (pop + low) * 0.8


def sfx_glass(length: float = 1.6) -> np.ndarray:
    """Shards landing: a scatter of tiny bright rings."""
    n = int(length * SR)
    out = np.zeros(n)
    for _ in range(14):
        at = RNG.uniform(0, length * 0.7)
        k = int(0.25 * SR)
        tt = np.arange(k) / SR
        f = RNG.uniform(3000, 6500)
        add(out, at, np.sin(2 * np.pi * f * tt) * np.exp(-tt * 30) * RNG.uniform(0.1, 0.3))
    return out


def sfx_ripple(length: float = 0.6) -> np.ndarray:
    """Several parts appearing in a quick run: rising ticks."""
    n = int(length * SR)
    out = np.zeros(n)
    for i in range(6):
        k = int(0.12 * SR)
        tt = np.arange(k) / SR
        add(out, i * 0.06, np.sin(2 * np.pi * midi(79 + i * 2) * tt) * np.exp(-tt * 50) * 0.25)
    return out


def sfx_pour(length: float = 1.6) -> np.ndarray:
    """Beads streaming down the wires: soft granular patter."""
    n = int(length * SR)
    t = np.arange(n) / SR
    grains = spectral_filter(RNG.normal(0, 1, n), 2500, 8000) * (RNG.uniform(0, 1, n) > 0.985)
    return spectral_filter(grains, 2000, 9000) * env_adsr(n, 0.1, 0.3, 0.8, 0.4) * 1.5


def sfx_buzz(length: float = 0.55) -> np.ndarray:
    """Wrong answer: a flat square-wave buzz."""
    n = int(length * SR)
    t = np.arange(n) / SR
    tone = np.sign(np.sin(2 * np.pi * 98 * t)) + 0.5 * np.sign(np.sin(2 * np.pi * 104 * t))
    return spectral_filter(tone, 80, 4000) * env_adsr(n, 0.01, 0.1, 0.8, 0.08) * 0.22


def sfx_ding(length: float = 1.2) -> np.ndarray:
    """Right answer: a bright bell (two partials, slow decay)."""
    n = int(length * SR)
    t = np.arange(n) / SR
    f = midi(88)
    return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2.4 * t) * np.exp(-t * 4)) * np.exp(-t * 3) * 0.3


def sfx_ratchet(length: float = 0.25) -> np.ndarray:
    n = int(length * SR)
    out = np.zeros(n)
    for i in range(4):
        add(out, i * 0.05, sfx_tick() * (1 - i * 0.15))
    return out


def sfx_violet(length: float = 2.5) -> np.ndarray:
    """The Mind's colour: a detuned bell chord with a slow beating shimmer."""
    n = int(length * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k, note in enumerate((76, 80, 83, 87)):
        f = midi(note) * (1 + 0.003 * (k - 1.5))
        out += np.sin(2 * np.pi * f * t) * np.exp(-t * (1.2 + k * 0.3))
    return out / 4 * (0.8 + 0.2 * np.sin(2 * np.pi * 3 * t)) * 0.5


def sfx_copy(length: float = 0.7) -> np.ndarray:
    """A board copying itself: a whoosh that lands on a pop."""
    w = sfx_whoosh(0.45) * 0.8
    out = np.zeros(int(length * SR))
    add(out, 0.0, w)
    add(out, 0.4, sfx_pop(0.3) * 0.5)
    return out


def square(freq: float, n: int, duty: float = 0.5) -> np.ndarray:
    t = np.arange(n) / SR
    return np.where((t * freq) % 1 < duty, 1.0, -1.0)


def sweep(f0: float, f1: float, length: float, duty: float = 0.5) -> np.ndarray:
    """An 8-bit pitch sweep (square wave), exponential in frequency."""
    n = int(length * SR)
    t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / length)
    phase = np.cumsum(f) / SR
    return np.where(phase % 1 < duty, 1.0, -1.0)


def sfx_key(length: float = 0.06) -> np.ndarray:
    """A keyboard key: a short plastic tick with a little body."""
    n = int(length * SR)
    t = np.arange(n) / SR
    f = RNG.uniform(1800, 2600)
    return (spectral_filter(RNG.normal(0, 1, n), 1500, 7000) * np.exp(-t * 220) + np.sin(2 * np.pi * f * t) * np.exp(-t * 160) * 0.3) * 0.35


def sfx_enter(length: float = 0.12) -> np.ndarray:
    """The Enter key: a longer, lower, heavier click."""
    n = int(length * SR)
    t = np.arange(n) / SR
    return (spectral_filter(RNG.normal(0, 1, n), 600, 5000) * np.exp(-t * 120) + np.sin(2 * np.pi * 900 * t) * np.exp(-t * 90) * 0.4) * 0.5


def sfx_pong(length: float = 0.09) -> np.ndarray:
    """Ball on paddle: a short square blip."""
    n = int(length * SR)
    return square(523.25, n, 0.5) * env_adsr(n, 0.002, 0.02, 0.8, 0.03) * 0.13


def sfx_wallbeep(length: float = 0.07) -> np.ndarray:
    """Ball on wall: the same blip an octave lower."""
    n = int(length * SR)
    return square(261.6, n, 0.5) * env_adsr(n, 0.002, 0.02, 0.8, 0.03) * 0.11


def sfx_score(length: float = 0.5) -> np.ndarray:
    n = int(length * SR)
    return sweep(500, 160, length, 0.5) * env_adsr(n, 0.005, 0.1, 0.7, 0.1) * 0.12


def sfx_glitch(length: float = 0.45) -> np.ndarray:
    """The ball skipping through a paddle: a stuttering, bit-crushed zip."""
    n = int(length * SR)
    t = np.arange(n) / SR
    tone = sweep(1400, 2800, length, 0.5)
    gate = (np.floor(t * 40) % 2).astype(float)
    crush = np.round(spectral_filter(RNG.normal(0, 1, n), 2000, 9000) * 4) / 4
    return (tone * gate * 0.1 + crush * 0.08) * env_adsr(n, 0.005, 0.1, 0.8, 0.1)


def sfx_beep(length: float = 0.18) -> np.ndarray:
    n = int(length * SR)
    return square(880, n, 0.25) * env_adsr(n, 0.005, 0.05, 0.7, 0.04) * 0.12


def sfx_jump8(length: float = 0.22) -> np.ndarray:
    n = int(length * SR)
    return sweep(300, 900, length, 0.5) * env_adsr(n, 0.005, 0.05, 0.6, 0.08) * 0.13


def sfx_fall8(length: float = 0.6) -> np.ndarray:
    n = int(length * SR)
    return sweep(800, 120, length, 0.5) * env_adsr(n, 0.005, 0.1, 0.7, 0.15) * 0.12


def sfx_boing(length: float = 0.7) -> np.ndarray:
    """A spring: a wobbling pitch that rises and rings out."""
    n = int(length * SR)
    t = np.arange(n) / SR
    f = 220 * (1 + 1.5 * (1 - np.exp(-t * 8))) * (1 + 0.15 * np.sin(2 * np.pi * 18 * t) * np.exp(-t * 4))
    phase = np.cumsum(f) / SR
    return np.where(phase % 1 < 0.5, 1.0, -1.0) * np.exp(-t * 3) * 0.14


def sfx_hurt(length: float = 0.45) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n) / SR
    tri = sweep(600, 90, length, 0.5) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 30 * t)))
    return tri * env_adsr(n, 0.005, 0.1, 0.8, 0.1) * 0.14


def notes(seq: list[tuple[int, float]], duty: float = 0.5, gain: float = 0.12) -> np.ndarray:
    total = sum(d for _, d in seq)
    out = np.zeros(int(total * SR) + 1)
    at = 0.0
    for m, d in seq:
        n = int(d * SR)
        if m > 0:
            add(out, at, square(midi(m), n, duty) * env_adsr(n, 0.005, 0.04, 0.7, min(0.05, d / 3)) * gain)
        at += d
    return out


def sfx_fanfare(length: float = 1.3) -> np.ndarray:
    """Level clear: a rising major arpeggio that lands on a held chord tone."""
    return notes([(72, 0.1), (76, 0.1), (79, 0.1), (84, 0.25), (79, 0.1), (84, 0.6)], 0.5, 0.12)


def sfx_gameover(length: float = 1.6) -> np.ndarray:
    return notes([(67, 0.25), (66, 0.25), (65, 0.25), (64, 0.8)], 0.5, 0.11)


def sfx_oneup(length: float = 0.6) -> np.ndarray:
    return notes([(76, 0.08), (79, 0.08), (88, 0.08), (84, 0.08), (86, 0.08), (91, 0.2)], 0.25, 0.1)


def sfx_roll(length: float = 3.0) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n) / SR
    rum = spectral_filter(RNG.normal(0, 1, n), 60, 500) * (0.7 + 0.3 * np.sin(2 * np.pi * 7 * t))
    return rum * env_adsr(n, 0.2, 0.2, 0.8, 0.4) * 0.3


def sfx_rattle(length: float = 0.6) -> np.ndarray:
    out = np.zeros(int(length * SR))
    for i in range(8):
        add(out, i * 0.07, sfx_tick() * 0.8)
    return out


def sfx_crack(length: float = 0.5) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n) / SR
    snap = spectral_filter(RNG.normal(0, 1, n), 2500, 12000) * np.exp(-t * 40)
    return snap * 0.6


def sfx_shatter(length: float = 2.0) -> np.ndarray:
    return sfx_glass(length) * 2.5


SFX = {
    "clash": lambda e: sfx_clash(),
    "whoosh": lambda e: sfx_whoosh(),
    "tink": lambda e: sfx_tink(),
    "thrust": lambda e: sfx_thrust(e.get("length", 2.0)),
    "boom": lambda e: sfx_boom(),
    "riser": lambda e: sfx_riser(e.get("length", 3.0)),
    "hum": lambda e: sfx_hum(e.get("length", 1.5)),
    "spin": lambda e: sfx_spin(e.get("length", 4.0)),
    "shimmer": lambda e: sfx_shimmer(e.get("length", 8.0)),
    "collapse": lambda e: sfx_collapse(),
    "barrier": lambda e: sfx_barrier(e.get("length", 6.0)),
    "tunnel": lambda e: sfx_tunnel(),
    "grind": lambda e: sfx_grind(e.get("length", 3.0)),
    "measure": lambda e: sfx_measure(),
    "zap": lambda e: sfx_zap(),
    "click": lambda e: sfx_click(),
    "tick": lambda e: sfx_tick(),
    "thud": lambda e: sfx_thud(),
    "blip": lambda e: sfx_blip(),
    "bzz": lambda e: sfx_bzz(e.get("length", 1.0)),
    "buzzer": lambda e: sfx_buzzer(e.get("length", 6.0)),
    "sizzle": lambda e: sfx_sizzle(e.get("length", 3.0)),
    "pop": lambda e: sfx_pop(),
    "glass": lambda e: sfx_glass(),
    "ripple": lambda e: sfx_ripple(),
    "pour": lambda e: sfx_pour(e.get("length", 1.6)),
    "buzz": lambda e: sfx_buzz(),
    "ding": lambda e: sfx_ding(),
    "ratchet": lambda e: sfx_ratchet(),
    "violet": lambda e: sfx_violet(),
    "copy": lambda e: sfx_copy(),
    "key": lambda e: sfx_key(),
    "enter": lambda e: sfx_enter(),
    "pong": lambda e: sfx_pong(),
    "wallbeep": lambda e: sfx_wallbeep(),
    "score": lambda e: sfx_score(),
    "glitch": lambda e: sfx_glitch(),
    "beep": lambda e: sfx_beep(),
    "jump8": lambda e: sfx_jump8(),
    "fall8": lambda e: sfx_fall8(),
    "boing": lambda e: sfx_boing(),
    "hurt": lambda e: sfx_hurt(),
    "fanfare": lambda e: sfx_fanfare(),
    "gameover": lambda e: sfx_gameover(),
    "oneup": lambda e: sfx_oneup(),
    "roll": lambda e: sfx_roll(e.get("length", 3.0)),
    "rattle": lambda e: sfx_rattle(),
    "crack": lambda e: sfx_crack(),
    "shatter": lambda e: sfx_shatter(),
}


# ----------------------------------------------------------------------- music

# A minor. Each section: chord roots per 2-second bar and which layers play.
PROGRESSIONS = {
    "void": [[45, 52, 57, 60]],
    "approach": [[45, 52, 57, 60], [41, 48, 57, 60], [43, 50, 55, 59], [40, 47, 55, 59]],
    "standoff": [[38, 50, 53, 57], [45, 52, 57, 60], [38, 50, 53, 57], [40, 52, 56, 59]],
    "fight": [[45, 52, 57, 60], [41, 53, 57, 60], [36, 52, 55, 60], [43, 50, 55, 59]],
    "climax": [[45, 52, 57, 60], [41, 53, 57, 60], [36, 52, 55, 60], [40, 52, 56, 59]],
    "hush": [[45, 57, 64, 72]],
    "resolve": [[41, 53, 57, 60], [36, 52, 55, 60], [43, 55, 59, 62], [45, 57, 61, 64]],
    # first_light: C major for play, drifting to A minor as the Mind wakes.
    "tinker": [[48, 55, 60, 64], [41, 57, 60, 65], [43, 55, 59, 62], [48, 55, 60, 64]],
    "tinker2": [[48, 55, 60, 64], [45, 57, 60, 64], [41, 57, 60, 65], [43, 55, 59, 62]],
    "build": [[41, 57, 60, 65], [43, 55, 59, 62], [48, 55, 60, 64], [45, 57, 60, 64]],
    "learn": [[48, 55, 60, 64], [43, 55, 59, 62], [45, 57, 60, 64], [41, 57, 60, 65]],
    "wonder": [[45, 57, 60, 64], [41, 57, 60, 65], [48, 55, 60, 64], [44, 56, 59, 64]],
    "grow": [[45, 52, 57, 60], [44, 52, 56, 59], [41, 53, 57, 60], [40, 52, 56, 59]],
    # first_game: a quiet night, a busy keyboard, then a chiptune world.
    "night": [[45, 57, 60, 64], [41, 57, 60, 65]],
    "code": [[48, 55, 60, 64], [45, 57, 60, 64], [41, 57, 60, 65], [43, 55, 59, 62]],
    "chip": [[48, 60, 64, 67], [41, 60, 65, 69], [43, 59, 62, 67], [48, 60, 64, 67]],
    "chipTense": [[45, 57, 60, 64], [41, 57, 60, 65], [44, 56, 59, 64], [45, 57, 60, 64]],
    "chipFinal": [[48, 60, 64, 67], [43, 59, 62, 67], [45, 57, 60, 64], [41, 60, 65, 69]],
    "morning": [[48, 55, 60, 64], [41, 57, 60, 65], [43, 55, 59, 62], [48, 55, 60, 64]],
}
LAYERS = {
    "void": {"pad": 0.55, "air": 0.25},
    "approach": {"pad": 0.6, "arp": 0.22, "pulse": 0.25},
    "standoff": {"pad": 0.6, "pulse": 0.3, "arp": 0.15},
    "fight": {"pad": 0.45, "bass": 0.5, "kick": 0.55, "snare": 0.3, "hat": 0.12, "arp": 0.2},
    "climax": {"pad": 0.55, "bass": 0.6, "kick": 0.7, "snare": 0.4, "hat": 0.18, "arp": 0.3},
    "hush": {"pad": 0.45, "air": 0.35},
    "resolve": {"pad": 0.6, "arp": 0.12},
    "tinker": {"pad": 0.35, "pulse": 0.3, "arp": 0.3, "hat": 0.08},
    "tinker2": {"pad": 0.35, "pulse": 0.3, "arp": 0.3, "bass": 0.3, "hat": 0.12, "kick": 0.3},
    "build": {"pad": 0.45, "arp": 0.35, "pulse": 0.3, "hat": 0.1},
    "learn": {"pad": 0.35, "bass": 0.3, "kick": 0.35, "hat": 0.12, "arp": 0.25},
    "wonder": {"pad": 0.6, "arp": 0.3, "air": 0.2},
    "grow": {"pad": 0.55, "bass": 0.55, "kick": 0.6, "snare": 0.3, "hat": 0.15, "arp": 0.3},
    "night": {"pad": 0.4, "air": 0.2},
    "code": {"pad": 0.3, "pulse": 0.25, "arp": 0.25, "hat": 0.08},
    "chip": {"sqlead": 0.5, "sqbass": 0.5, "kick": 0.3, "hat": 0.1},
    "chipTense": {"sqlead": 0.4, "sqbass": 0.55, "kick": 0.45, "snare": 0.25, "hat": 0.14},
    "chipFinal": {"sqlead": 0.6, "sqbass": 0.6, "kick": 0.55, "snare": 0.35, "hat": 0.16},
    "morning": {"pad": 0.45, "arp": 0.3, "pulse": 0.2},
}


def build_music(story: dict, n: int) -> np.ndarray:
    bpm = story["bpm"]
    beat = 60 / bpm
    bar = beat * 4
    left = np.zeros(n)
    right = np.zeros(n)
    for sec in story["music"]:
        name, t0, t1 = sec["section"], sec["from"], sec["to"]
        prog = PROGRESSIONS[name]
        layers = LAYERS[name]
        bars = int(math.ceil((t1 - t0) / bar))
        for b in range(bars):
            bt = t0 + b * bar
            chord = prog[b % len(prog)]
            dur = min(bar, t1 - bt)
            if dur <= 0.05:
                continue
            m = int((dur + 0.6) * SR)
            if "pad" in layers:
                for note in chord:
                    for side, det in ((left, -0.003), (right, 0.003)):
                        tone = saw(midi(note), m, 6, det)
                        add(side, bt, tone * env_adsr(m, 0.5, 0.3, 0.9, 0.6), layers["pad"] * 0.06)
            if "air" in layers:
                hiss = spectral_filter(RNG.normal(0, 1, m), 3000, 10000)
                add(left, bt, hiss * env_adsr(m, 0.8, 0.2, 1, 0.8), layers["air"] * 0.05)
                add(right, bt, np.roll(hiss, 997) * env_adsr(m, 0.8, 0.2, 1, 0.8), layers["air"] * 0.05)
            steps = int(round(dur / (beat / 2)))
            for s in range(steps):
                st = bt + s * beat / 2
                on_beat = s % 2 == 0
                if "bass" in layers:
                    k = int(0.4 * SR)
                    f = midi(chord[0] - 12 if chord[0] > 40 else chord[0])
                    tt = np.arange(k) / SR
                    tone = (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt * 6)
                    add(left, st, tone, layers["bass"] * 0.35)
                    add(right, st, tone, layers["bass"] * 0.35)
                if "pulse" in layers and on_beat:
                    k = int(0.6 * SR)
                    tt = np.arange(k) / SR
                    tone = np.sin(2 * np.pi * midi(chord[0]) * tt) * np.exp(-tt * 5)
                    add(left, st, tone, layers["pulse"] * 0.3)
                    add(right, st, tone, layers["pulse"] * 0.3)
                if "kick" in layers and on_beat:
                    k = int(0.35 * SR)
                    tt = np.arange(k) / SR
                    tone = np.sin(2 * np.pi * (45 + 110 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 9)
                    add(left, st, tone, layers["kick"] * 0.6)
                    add(right, st, tone, layers["kick"] * 0.6)
                if "snare" in layers and s % 4 == 2:
                    k = int(0.25 * SR)
                    tt = np.arange(k) / SR
                    noise = spectral_filter(RNG.normal(0, 1, k), 900, 6000) * np.exp(-tt * 18)
                    add(left, st, noise, layers["snare"] * 0.45)
                    add(right, st, noise, layers["snare"] * 0.45)
                if "hat" in layers:
                    k = int(0.06 * SR)
                    tt = np.arange(k) / SR
                    noise = spectral_filter(RNG.normal(0, 1, k), 7000) * np.exp(-tt * 70)
                    add(left if s % 2 else right, st, noise, layers["hat"] * 0.5)
                if "sqlead" in layers:
                    k = int(beat / 2 * SR)
                    note = chord[[1, 2, 3, 2, 3, 2, 1, 3][s % 8]] + 12
                    tone = square(midi(note), k, 0.25) * env_adsr(k, 0.003, 0.05, 0.6, 0.03)
                    add(left, st, tone, layers["sqlead"] * 0.05)
                    add(right, st, tone, layers["sqlead"] * 0.05)
                if "sqbass" in layers:
                    k = int(beat / 2 * SR * 0.9)
                    f = midi(chord[0] - (12 if chord[0] > 40 else 0) + (12 if s % 2 else 0))
                    tone = square(f, k, 0.5) * env_adsr(k, 0.003, 0.05, 0.7, 0.03)
                    add(left, st, tone, layers["sqbass"] * 0.06)
                    add(right, st, tone, layers["sqbass"] * 0.06)
                if "arp" in layers:
                    k = int(0.5 * SR)
                    tt = np.arange(k) / SR
                    note = chord[[1, 2, 3, 2][s % 4]] + 12
                    tone = np.sin(2 * np.pi * midi(note) * tt) * np.exp(-tt * 7)
                    add(left if s % 2 else right, st, tone, layers["arp"] * 0.25)
    # Gentle fades at section boundaries come from the per-bar envelopes; add
    # a global fade-in and fade-out.
    fade = np.ones(n)
    fi, fo = int(2 * SR), int(4 * SR)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[-fo:] = np.linspace(1, 0, fo)
    return np.stack([left * fade, right * fade], axis=1)


# ----------------------------------------------------------------------- voice


def tts(line: dict, voice: dict, args: argparse.Namespace) -> np.ndarray:
    """Return the processed clip for a line, synthesizing only when needed."""
    out_dir = DIR / "voice"
    out_dir.mkdir(exist_ok=True)
    key = hashlib.sha1(json.dumps([line["text"], voice], sort_keys=True).encode()).hexdigest()[:12]
    path = out_dir / f"{line['id']}.wav"
    stamp = out_dir / f"{line['id']}.key"
    if args.retts or not path.exists() or not stamp.exists() or stamp.read_text().strip() != key:
        model = Path(args.voices) / f"{voice['model']}.onnx"
        if not model.exists():
            sys.exit(f"voice model missing: {model} (needed to synthesize '{line['id']}')")
        raw = out_dir / f"{line['id']}.raw.wav"
        subprocess.run(
            [args.piper, "-m", str(model), "-f", str(raw), "--length-scale", str(voice.get("lengthScale", 1.0))],
            input=line["text"].encode(),
            check=True,
            capture_output=True,
        )
        x, sr = read_wav(raw)
        raw.unlink()
        x = resample(x, sr, SR)
        if voice.get("alien"):
            x = alienize(x)
        x = trim(x)
        x = x / (np.max(np.abs(x)) + 1e-9) * 0.9
        # Speech needs no more than 24 kHz; halves what the repo stores.
        write_wav(path, resample(x, SR, VOICE_SR)[:, None], VOICE_SR)
        stamp.write_text(key)
    x, sr = read_wav(path)
    return resample(x, sr, SR)


def alienize(x: np.ndarray) -> np.ndarray:
    """Lower and stretch the voice, add a sub ring-mod and a short flange."""
    y = resample(x, SR, SR / 0.84)  # play 16% slower: lower pitch, longer
    t = np.arange(len(y)) / SR
    ring = y * (0.75 + 0.25 * np.sin(2 * np.pi * 38 * t))
    d = int(0.011 * SR)
    flange = ring + 0.45 * np.concatenate([np.zeros(d), ring[:-d]])
    return spectral_filter(flange, 90, 6000)


def trim(x: np.ndarray, threshold: float = 0.01) -> np.ndarray:
    loud = np.where(np.abs(x) > threshold * np.max(np.abs(x)))[0]
    if len(loud) == 0:
        return x
    a = max(0, loud[0] - int(0.02 * SR))
    b = min(len(x), loud[-1] + int(0.08 * SR))
    return x[a:b]


# ------------------------------------------------------------------------ main


def resolve(ref: str | float, events: dict, lines: dict) -> float:
    if isinstance(ref, (int, float)):
        return float(ref)
    if "." in ref:
        lid, edge = ref.split(".")
        return lines[lid][edge]
    return events[ref]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", default="space_duel", help="folder under audio/")
    ap.add_argument("--voices", default=str(ROOT / "tools" / "voices"))
    ap.add_argument("--piper", default="piper")
    ap.add_argument("--retts", action="store_true", help="re-synthesize every line")
    args = ap.parse_args()
    global DIR
    DIR = ROOT / "audio" / args.episode

    story = json.loads((DIR / "story.json").read_text())
    n = int(story["duration"] * SR)

    # 1. Narration: synthesize/measure, then check nothing overlaps.
    voice_bus = np.zeros(n)
    lines: dict[str, dict] = {}
    ordered = sorted(story["lines"], key=lambda l: l["at"])
    problems = []
    for i, line in enumerate(ordered):
        clip = tts(line, story["voices"][line["voice"]], args)
        start = line["at"]
        end = start + len(clip) / SR
        lines[line["id"]] = {
            "start": round(start, 4),
            "end": round(end, 4),
            "voice": line["voice"],
            "text": line["text"],
        }
        nxt = ordered[i + 1]["at"] if i + 1 < len(ordered) else story["duration"]
        if end > nxt - 0.25:
            problems.append(f"  {line['id']} ends at {end:.2f}s, next line starts at {nxt:.2f}s ({end - nxt + 0.25:+.2f}s)")
        add(voice_bus, start, clip, 0.95)
    if problems:
        sys.exit("narration overruns its slot:\n" + "\n".join(problems))

    events = {k: float(v) for k, v in story["events"].items()}

    # 2. Sound effects.
    sfx_l = np.zeros(n)
    sfx_r = np.zeros(n)
    for e in story["sfx"]:
        at = resolve(e["at"], events, lines) + e.get("offset", 0.0)
        sig = SFX[e["type"]](e)
        pan = e.get("pan", 0.0)
        add(sfx_l, at, sig, e.get("gain", 1.0) * (1 - pan) * 0.7)
        add(sfx_r, at, sig, e.get("gain", 1.0) * (1 + pan) * 0.7)

    # 3. Music, ducked under the voice.
    music = build_music(story, n)
    env = smooth(voice_bus, 0.25)
    duck = 1 - 0.6 * np.clip(env / 0.04, 0, 1)
    music *= duck[:, None]

    mix = music * 0.9 + np.stack([sfx_l, sfx_r], axis=1) * 0.8 + voice_bus[:, None]

    # 4. Designed silences (style bible S6): duck everything by 24 dB, with
    # 40 ms fades, so the hit after them lands at full scale.
    if story.get("silences"):
        gain = np.ones(n)
        fade = int(0.04 * SR)
        for sil in story["silences"]:
            a, b = int(resolve(sil["from"], events, lines) * SR), int(resolve(sil["to"], events, lines) * SR)
            g = np.full(b - a, 10 ** (-24 / 20))
            g[:fade] = np.linspace(1, g[fade], fade)
            gain[a:b] = np.minimum(gain[a:b], g)
        mix *= gain[:, None]
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)  # soft limiter
    mix *= 0.89 / np.max(np.abs(mix))  # peak at -1 dBFS
    write_wav(DIR / "master.wav", mix)

    cues = {
        "bpm": story["bpm"],
        "duration": story["duration"],
        "lines": lines,
        "events": events,
    }
    # Episode data the scene needs verbatim (the code typed on screen, physics).
    for key in ("code", "physics", "rallies"):
        if key in story:
            cues[key] = story[key]
    (DIR / "cues.json").write_text(json.dumps(cues, indent=2) + "\n")
    print(f"wrote master.wav ({story['duration']}s) and cues.json ({len(lines)} lines, {len(events)} events)")
    for lid, l in lines.items():
        print(f"  {lid:4} {l['start']:7.2f} -> {l['end']:7.2f}  ({l['end'] - l['start']:.2f}s)")


if __name__ == "__main__":
    main()
