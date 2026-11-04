"""Música y efectos del estilo Blueprint: electrónica ambiental a 134 BPM con pulsos de arpegio,
kick a medio tiempo y tic de reloj; lápiz cuando se dibuja, rayado al congelar y sello en los golpes.

Uso: python3 audio_blueprint.py <term.mp4> <salida.wav>
"""
import subprocess
import sys
import wave

import numpy as np

from bp_events import DRAWS, HATCHES, SLIDES, STAMPS, STAT_STARTS
from timeline import BEAT, CMD_ROWS, END, FREEZE, IDLE_FREEZE, TERM_SRC, TOTAL, b, out_time, row_y

SR = 48000
N = int(TOTAL * SR)
STEP = BEAT / 4
rng = np.random.default_rng(11)
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


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def lp(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for k in range(len(x)):
        acc = (1 - a) * x[k] + a * acc
        y[k] = acc
    return y


def hp(x, cutoff):
    return x - lp(x, cutoff)


def frozen(t):
    return FREEZE[0] <= t < FREEZE[1] or IDLE_FREEZE[0] <= t < IDLE_FREEZE[1]


# ---------- instrumentos ----------
def pluck(m, dur=0.5, bright=1.0):
    t = tt(dur)
    f = hz(m)
    s = np.sin(2 * np.pi * f * t) + 0.35 * bright * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 18)
    s += 0.15 * bright * np.sin(2 * np.pi * 3 * f * t) * np.exp(-t * 30)
    return s * np.exp(-t * 9) * np.minimum(1, t / 0.003)


def kick():
    t = tt(0.45)
    f = 42 + 70 * np.exp(-t * 22)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6)


def tick():  # tic de reloj de dibujo técnico
    t = tt(0.03)
    return (np.sin(2 * np.pi * 2600 * t) + hp(rng.standard_normal(len(t)), 4000) * 0.4) * np.exp(-t * 250)


SHAKER = hp(rng.standard_normal(int(0.06 * SR)), 6000) * np.exp(-tt(0.06) * 60)


def pad(notes, dur, glass=False):
    t = tt(dur)
    s = np.zeros(len(t))
    for m in notes:
        for det in (-0.06, 0.06):
            s += np.sin(2 * np.pi * hz(m + det) * t + rng.uniform(0, 6))
            if glass:
                s += 0.25 * np.sin(2 * np.pi * hz(m + 24 + det) * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.7 * t))
    env = np.minimum(1, t / 0.4) * np.clip((dur - t) / 0.4, 0, 1)
    return s * env / len(notes) * 0.18


def sub(freq, dur):
    t = tt(dur)
    return np.sin(2 * np.pi * freq * t) * np.minimum(1, t / 0.05) * np.clip((dur - t) / 0.1, 0, 1)


CHORDS = [([53, 56, 60, 63, 67], 29), ([49, 53, 56, 60, 63], 25), ([46, 49, 53, 56, 60], 34),
          ([51, 55, 58, 61, 65], 27)]
ARP = [0, 2, 1, 3, 4, 3, 2, 1]

kicks = []
for bar in range(12):
    t0 = bar * 4 * BEAT
    notes, root = CHORDS[bar % 4]
    cold = frozen(t0)
    add(pad(notes, 4 * BEAT + 0.4, glass=cold), t0, 1.2 if cold else 0.8)
    if not cold and t0 >= b(4) and t0 < b(END[0]):
        add(sub(hz(root + 12), 4 * BEAT), t0, 0.35)
    for st in range(16):
        t = t0 + st * STEP
        if frozen(t) or t >= b(END[0]):
            continue
        # arpegio: en la intro solo corcheas, luego semicorcheas
        if st % 2 == 0 or t >= b(4):
            m = notes[ARP[st % 8]] + 12
            add(pluck(m, 0.45, 0.6 if t < b(4) else 1.0), t, 0.16 if st % 2 else 0.22, 0.35 if st % 2 else -0.35)
        if b(4) <= t and not (b(24) <= t < b(26)):
            if st in (0, 8):
                kicks.append(t)
            if st in (4, 12):
                add(tick(), t, 0.35, 0.2)
            if st % 2 == 1:
                add(SHAKER, t + 0.012, 0.07 + 0.04 * (st % 4 == 3), -0.25)

duck = np.ones(N)
curve = 1 - 0.45 * np.exp(-tt(0.2) * 14)
for kt in kicks:
    i = int(kt * SR)
    j = min(N, i + len(curve))
    duck[i:j] = np.minimum(duck[i:j], curve[: j - i])
L *= duck
R *= duck
for kt in kicks:
    add(kick(), kt, 0.75)


# ---------- efectos ----------
def pencil(dur):
    """Grafito sobre papel: ruido de banda media con rugosidad irregular."""
    t = tt(dur)
    n = hp(lp(rng.standard_normal(len(t)), 5500), 1500)
    rough = np.abs(lp(rng.standard_normal(len(t)), 40))
    rough = rough / (rough.max() + 1e-9)
    env = np.minimum(1, t / 0.02) * np.clip((dur - t) / 0.04, 0, 1)
    return n * (0.4 + 0.6 * rough) * env


def scribble(dur):  # rayado rápido: lápiz con golpes de vaivén
    t = tt(dur)
    return pencil(dur) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 14 * t)))


def stamp():
    t = tt(0.6)
    body = np.sin(2 * np.pi * np.cumsum(55 + 90 * np.exp(-t * 30)) / SR) * np.exp(-t * 9)
    slap = hp(rng.standard_normal(len(t)), 800) * np.exp(-t * 60) * 0.6
    return np.tanh((body + slap) * 1.5)


def slide(dur=0.4):  # hoja de papel que se desliza
    t = tt(dur)
    n = hp(lp(rng.standard_normal(len(t)), 3000), 400)
    return n * np.sin(np.pi * (t / dur)) ** 2 * 0.9


def click():
    t = tt(0.012)
    return (hp(rng.standard_normal(len(t)), 2500) + 0.4 * np.sin(2 * np.pi * 2100 * t)) * np.exp(-t * 500)


def ping(f=1760):
    t = tt(0.9)
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t)) * np.exp(-t * 6) * 0.5


for t0, t1 in DRAWS:
    add(pencil(t1 - t0), t0, 0.22, rng.uniform(-0.3, 0.3))
for t0, t1 in HATCHES:
    add(scribble(t1 - t0 + 0.1), t0, 0.35)
for t in STAMPS:
    add(stamp(), t, 0.7)
for t in SLIDES:
    add(slide(), t - 0.32, 0.45)
for t in STAT_STARTS:
    add(ping(1318), t + 0.7, 0.18)

w, h, fps = TERM_SRC
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", sys.argv[1], "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                     capture_output=True, check=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w)
for r in CMD_ROWS:
    y = row_y(r)
    d = np.abs(np.diff(fr[:, y:y + 30, 80:1560].astype(np.int16), axis=0)).sum(axis=(1, 2))
    for f in np.nonzero(d > 500)[0]:
        add(click(), out_time((f + 1) / fps), 0.22, rng.uniform(-0.25, 0.25))
add(ping(), b(14), 0.3)
add(ping(2093), b(26), 0.45)
# subida antes del deshielo: el arpegio vuelve acelerando
for k in range(8):
    add(pluck(72 + k, 0.3), b(24) + k * BEAT / 4, 0.08 + 0.02 * k)

# cierre: acorde de pulsos en cascada y pad largo
for k, m in enumerate([65, 68, 72, 75, 79]):
    add(pluck(m, 1.6), b(END[0]) + k * STEP / 2, 0.3, -0.4 + 0.2 * k)
add(pad(CHORDS[0][0], TOTAL - b(END[0]), glass=True), b(END[0]), 1.0)

ir_t = tt(1.8)
ir = lp(rng.standard_normal(len(ir_t)) * np.exp(-ir_t * 3.0), 4500)
ir /= np.sqrt((ir ** 2).sum())


def conv(x):
    m = len(x) + len(ir)
    nfft = 1 << (m - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[: len(x)]


L = L + 0.25 * conv(L)
R = R + 0.25 * conv(R)
fade = np.clip((TOTAL - np.arange(N) / SR) / 0.8, 0, 1)
mix = np.stack([L * fade, R * fade], axis=1)
mix /= np.abs(mix).max() / 0.89
with wave.open(sys.argv[2], "wb") as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes((mix * 32767).astype("<i2").tobytes())
print("audio", round(TOTAL, 2), "s")
