"""Música (UK garage 2-step a 134 BPM, Fa menor) y efectos de sonido, sintetizados con numpy.

Uso: python3 audio_brasa.py <term.mp4> <salida.wav>
"""
import subprocess
import sys
import wave

import numpy as np

from timeline import (BEAT, CMD_ROWS, END, FREEZE, HOOK_CMD, HOOK_TYPE, IDLE_FREEZE, TERM_SRC,
                      TOTAL, b, out_time, row_y)

SR = 48000
N = int(TOTAL * SR)
STEP = BEAT / 4
rng = np.random.default_rng(7)

L = np.zeros(N)
R = np.zeros(N)


def add(sig, t, gain=1.0, pan=0.0):
    i = int(t * SR)
    if i >= N or i + len(sig) <= 0:
        return
    j = min(N, i + len(sig))
    s = sig[: j - i] * gain
    L[i:j] += s * np.sqrt(0.5 * (1 - pan))
    R[i:j] += s * np.sqrt(0.5 * (1 + pan))


def tt(dur):
    return np.arange(int(dur * SR)) / SR


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def onepole_lp(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for k in range(len(x)):  # señales cortas: aceptable
        acc = (1 - a) * x[k] + a * acc
        y[k] = acc
    return y


def hp(x, cutoff):
    return x - onepole_lp(x, cutoff)


# ---------- instrumentos ----------
def kick():
    t = tt(0.38)
    f = 45 + 95 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 7.5)
    click = rng.standard_normal(len(t)) * np.exp(-t * 400) * 0.25
    return np.tanh((body + click) * 1.6)


def clap():
    t = tt(0.22)
    n = hp(rng.standard_normal(len(t)), 900)
    env = np.zeros(len(t))
    for d in (0.0, 0.011, 0.022):
        env += np.where(t >= d, np.exp(-(t - d) * 60), 0)
    env += np.exp(-t * 18) * 0.35
    return n * env * 0.5


HAT = hp(rng.standard_normal(int(0.05 * SR)), 7000) * np.exp(-tt(0.05) * 90)
OHAT = hp(rng.standard_normal(int(0.22 * SR)), 6500) * np.exp(-tt(0.22) * 14)


def additive(freq, dur, harmonics, decay, bright=1.0):
    t = tt(dur)
    s = np.zeros(len(t))
    for h in range(1, harmonics + 1):
        if freq * h > 16000:
            break
        s += np.sin(2 * np.pi * freq * h * t) / h * np.exp(-t * decay * (1 + (h - 1) * 0.35 / bright))
    return s


def stab(notes, bright=1.0):
    dur = 0.32
    s = np.zeros(int(dur * SR))
    for m in notes:
        for det in (-0.08, 0.08):  # dos sierras ligeramente desafinadas
            s += additive(hz(m + det), dur, 18, 9, bright)
    return s / len(notes) * 0.5


def pad(notes, dur, harmonics=4):
    t = tt(dur)
    s = np.zeros(len(t))
    for m in notes:
        for det in (-0.05, 0.05):
            for h in range(1, harmonics + 1):
                s += np.sin(2 * np.pi * hz(m + det) * h * t + rng.uniform(0, 6)) / (h * h)
    att = np.minimum(1, t / 0.25)
    rel = np.minimum(1, (dur - t) / 0.3)
    return s * att * np.clip(rel, 0, 1) / len(notes) * 0.25


def sub(freq, dur):
    t = tt(dur)
    env = np.minimum(1, t / 0.01) * np.clip((dur - t) / 0.03, 0, 1)
    return np.sin(2 * np.pi * freq * t) * env


def bell(m, dur=1.2):
    t = tt(dur)
    f = hz(m)
    s = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 6)
    s += 0.25 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 12)
    return s * np.exp(-t * 3.2) * 0.35


# Fm9 · Dbmaj9 · Bbm9 · Eb(sus)  — un acorde por compás
CHORDS = [
    ([53, 56, 60, 63, 67], 29),  # Fm9, raíz F1
    ([49, 53, 56, 60, 63], 25),  # Dbmaj9, Db1
    ([46, 49, 53, 56, 60], 34),  # Bbm9, Bb1
    ([51, 55, 58, 61, 65], 27),  # Eb7, Eb1
]


def in_range(t, rng_):
    return rng_[0] <= t < rng_[1]


def frozen(t):
    return in_range(t, FREEZE) or in_range(t, IDLE_FREEZE)


def drums_on(t):
    return b(4) <= t < b(END[0]) and not frozen(t) and not in_range(t, (b(24), b(26)))


# ---------- secuencia ----------
K = kick()
CL = clap()
kick_times = []
for bar in range(12):
    t0 = bar * 4 * BEAT
    notes, root = CHORDS[bar % 4]
    # pad continuo (frío: menos armónicos durante la congelación)
    cold = frozen(t0)
    add(pad(notes, 4 * BEAT + 0.3, 2 if cold else 4), t0, 0.9 if cold else 0.7)
    kicks = [0, 10] if bar % 2 == 0 else [0, 7, 10]
    for st in range(16):
        t = t0 + st * STEP + (0.22 * STEP if st % 2 else 0)  # swing en semicorcheas impares
        if drums_on(t):
            if st in kicks:
                kick_times.append(t)
            if st in (4, 12):
                add(CL, t, 0.55, 0.05)
            if st % 4 == 2:
                add(HAT, t, 0.22, -0.3)
            elif st % 2 == 1 and rng.random() < 0.6:
                add(HAT, t, 0.08, 0.3)
            if st == 14 and bar % 2:
                add(OHAT, t, 0.12, 0.2)
        if st in (3, 6, 11, 14) and not frozen(t) and t < b(END[0]):
            bright = 0.35 if t < b(4) else 1.0  # intro "filtrada"
            add(stab(notes, bright), t, 0.32, -0.15 if st % 2 else 0.15)
        if st in (0, 3, 8, 11) and drums_on(t):
            add(sub(hz(root + 12), STEP * 2.6), t, 0.42)

# sidechain: el kick empuja todo lo demás
duck = np.ones(N)
dt = tt(0.18)
curve = 1 - 0.55 * np.exp(-dt * 18)
for kt in kick_times:
    i = int(kt * SR)
    j = min(N, i + len(curve))
    duck[i:j] = np.minimum(duck[i:j], curve[: j - i])
L *= duck
R *= duck
for kt in kick_times:  # el kick entra después del duck para no apretarse a sí mismo
    add(K, kt, 0.9)

# ---------- efectos ----------
def click():
    t = tt(0.012)
    n = hp(rng.standard_normal(len(t)), 2500) * np.exp(-t * 500)
    tone = np.sin(2 * np.pi * rng.uniform(1800, 2400) * t) * np.exp(-t * 700) * 0.4
    return n + tone


def whoosh(dur=0.42):
    t = tt(dur)
    n = rng.standard_normal(len(t))
    env = np.sin(np.pi * (t / dur) ** 1.6) ** 2
    lo = onepole_lp(n, 1800)
    return hp(lo, 300) * env * 1.4


def impact():
    t = tt(1.2)
    f = 38 + 70 * np.exp(-t * 14)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.2)
    crack = hp(rng.standard_normal(len(t)), 1200) * np.exp(-t * 40) * 0.5
    return np.tanh((boom + crack) * 1.4)


def ice():
    t = tt(0.9)
    s = np.zeros(len(t))
    for _ in range(70):
        c = rng.uniform(0, 0.8) ** 1.7
        i = int(c * SR)
        g = hp(rng.standard_normal(int(0.004 * SR)), 5000) * rng.uniform(0.2, 1)
        s[i:i + len(g)] += g[: len(s) - i]
    glass = sum(np.sin(2 * np.pi * f * t) for f in (2637, 3520, 4186)) * np.exp(-t * 4) * 0.08
    return s * 0.5 + glass


def riser(dur):
    t = tt(dur)
    n = hp(rng.standard_normal(len(t)), 600)
    sweep = np.sin(2 * np.pi * np.cumsum(220 + 900 * (t / dur) ** 2) / SR) * 0.25
    return (n * 0.35 + sweep) * (t / dur) ** 2.2


def ping():
    t = tt(0.9)
    return (np.sin(2 * np.pi * 1760 * t) + 0.3 * np.sin(2 * np.pi * 3520 * t)) * np.exp(-t * 7) * 0.5


def tick():
    t = tt(0.02)
    return np.sin(2 * np.pi * 3000 * t) * np.exp(-t * 300)


# clics del gancho
n = len(HOOK_CMD)
for k in range(n):
    add(click(), HOOK_TYPE[0] + (HOOK_TYPE[1] - HOOK_TYPE[0]) * k / (n - 1), 0.32, rng.uniform(-0.2, 0.2))
add(click(), HOOK_TYPE[1] + 0.07, 0.45)  # enter

# clics de la grabación real: un clic por cada fotograma en que cambia una fila de comando
w, h, fps = TERM_SRC
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", sys.argv[1], "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                     capture_output=True, check=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w)
for r in CMD_ROWS:
    y = row_y(r)
    d = np.abs(np.diff(fr[:, y:y + 30, 80:1560].astype(np.int16), axis=0)).sum(axis=(1, 2))
    for f in np.nonzero(d > 500)[0]:
        add(click(), out_time((f + 1) / fps), 0.26, rng.uniform(-0.25, 0.25))

for t in (b(8), b(28), b(40)):
    add(whoosh(), t - 0.38, 0.5)
for t in (b(2), b(26), b(END[0])):
    add(impact(), t, 0.75)
add(ice(), FREEZE[0], 0.8)
add(ice(), IDLE_FREEZE[0], 0.7)
add(riser(2 * BEAT), b(24), 0.55)
add(ping(), b(26), 0.5)
add(ping(), b(14), 0.28)  # "0.4s" en la terminal
for s0 in (28, 32, 36):  # contadores de cifras
    for k in range(8):
        add(tick(), b(s0) + 0.05 + k * 0.045, 0.12)

# sting: arpegio de campana Fa-Lab-Do-Mib + pad final
for k, m in enumerate([77, 80, 84, 87]):
    add(bell(m, 2.0), b(END[0]) + k * STEP, 0.55, -0.3 + 0.2 * k)
add(pad(CHORDS[0][0], TOTAL - b(END[0]), 3), b(END[0]), 0.9)

# ---------- reverb (IR de ruido decayente) y salida ----------
ir_t = tt(1.6)
ir = rng.standard_normal(len(ir_t)) * np.exp(-ir_t * 3.4)
ir = onepole_lp(ir, 5000)
ir /= np.sqrt((ir ** 2).sum())


def conv(x):
    m = len(x) + len(ir)
    nfft = 1 << (m - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[: len(x)]


L = L + 0.18 * conv(L)
R = R + 0.18 * conv(R)
fade = np.clip((TOTAL - np.arange(N) / SR) / 0.8, 0, 1)
mix = np.stack([L * fade, R * fade], axis=1)
mix /= np.abs(mix).max() / 0.89
pcm = (mix * 32767).astype("<i2")
with wave.open(sys.argv[2], "wb") as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes(pcm.tobytes())
print("audio", round(TOTAL, 2), "s")
