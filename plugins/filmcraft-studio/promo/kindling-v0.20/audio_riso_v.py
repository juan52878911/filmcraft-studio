"""Música y efectos del corte vertical en Risografía (14 compases, mismo sonido que audio_riso.py): breakbeat lo-fi a 134 BPM con piano eléctrico, vinilo y
saturación de cinta. La congelación es un "tape stop" (la cinta frena) y el deshielo, la cinta que arranca;
los golpes de registro suenan a la imprenta pasando una hoja.

Uso: python3 audio_riso.py <term.mp4> <salida.wav>
"""
import subprocess
import sys
import wave

import numpy as np

from timeline_v import (BEATS, BEAT, CMD_ROWS, END, FEATS, FREEZE, HOL, HOOK_CMD, HOOK_TYPE, IDLE_FREEZE, SILICON,
                        TERM_SRC, TOTAL, b, out_time, row_y)

SR = 48000
N = int(TOTAL * SR)
STEP = BEAT / 4
rng = np.random.default_rng(21)
L = np.zeros(N)
R = np.zeros(N)


def add(sig, t, gain=1.0, pan=0.0, buf=None):
    i = int(t * SR)
    if i >= N or i + len(sig) <= 0:
        return
    j = min(N, i + len(sig))
    s = sig[: j - i] * gain
    lb, rb = buf if buf else (L, R)
    lb[i:j] += s * np.sqrt(0.5 * (1 - pan))
    rb[i:j] += s * np.sqrt(0.5 * (1 + pan))


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


# ---------- batería de break ----------
def kick():
    t = tt(0.3)
    body = np.sin(2 * np.pi * np.cumsum(50 + 110 * np.exp(-t * 35)) / SR) * np.exp(-t * 11)
    return np.tanh(body * 2.2 + rng.standard_normal(len(t)) * np.exp(-t * 300) * 0.3)


def snare(g=1.0):
    t = tt(0.25)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25)
    noise = hp(lp(rng.standard_normal(len(t)), 7000), 1200) * np.exp(-t * 16)
    return np.tanh((tone * 0.6 + noise) * 1.8) * g


HAT = hp(rng.standard_normal(int(0.04 * SR)), 7500) * np.exp(-tt(0.04) * 110)

# patrón de break (16 pasos): kick, snare, ghost
KICK = {0, 10}
KICK_B = {0, 2, 10}
SNARE = {4, 12}
GHOST = {7, 9, 15}


# ---------- piano eléctrico ----------
def epiano(m, dur):
    t = tt(dur)
    f = hz(m)
    mod = np.sin(2 * np.pi * f * 1.0 * t) * 1.6 * np.exp(-t * 5)
    s = np.sin(2 * np.pi * f * t + mod) * np.exp(-t * 1.6)
    s += 0.2 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t * 14)  # tine
    trem = 1 + 0.12 * np.sin(2 * np.pi * 4.5 * t)
    return s * trem * np.minimum(1, t / 0.004)


def sub(freq, dur):
    t = tt(dur)
    return np.sin(2 * np.pi * freq * t) * np.minimum(1, t / 0.01) * np.clip((dur - t) / 0.05, 0, 1)


CHORDS = [([53, 56, 60, 63, 67], 29), ([49, 53, 56, 60, 63], 25), ([46, 49, 53, 56, 60], 34),
          ([51, 55, 58, 61, 65], 27)]

ML, MR = np.zeros(N), np.zeros(N)  # buffer de la música (va a cinta); los efectos van aparte
mbuf = (ML, MR)
for bar in range(BEATS // 4):
    t0 = bar * 4 * BEAT
    notes, root = CHORDS[bar % 4]
    # acorde en 1 y en el "y" del 2, más un toque en el 4
    for st, g in ((0, 0.28), (6, 0.2), (13, 0.14)):
        t = t0 + st * STEP
        if t < b(END[0]):
            for k, m in enumerate(notes):
                add(epiano(m, 1.4), t + k * 0.008, g / len(notes) * 3, -0.2 + 0.1 * k, mbuf)
    if b(4) <= t0 < b(END[0]):
        for st in (0, 3, 10):
            add(sub(hz(root + 12), STEP * 2.5), t0 + st * STEP, 0.38, 0, mbuf)
    for st in range(16):
        t = t0 + st * STEP + (0.18 * STEP if st % 2 else 0)
        if t < b(4) or t >= b(END[0]):
            continue
        if st in (KICK_B if bar % 2 else KICK):
            add(kick(), t, 0.8, 0, mbuf)
        if st in SNARE:
            add(snare(), t, 0.55, 0.05, mbuf)
        if st in GHOST and rng.random() < 0.8:
            add(snare(0.25), t, 0.5, 0.1, mbuf)
        if st % 2 == 0 or rng.random() < 0.5:
            add(HAT, t, 0.12 if st % 4 == 2 else 0.06, -0.3, mbuf)


# ---------- cinta: lo-fi, frenazo y arranque ----------
def tape_speed(t):
    """Velocidad de la cinta: frena al congelar, arranca al despertar."""
    sp = np.ones_like(t)
    for f0, f1 in (FREEZE, IDLE_FREEZE):
        stop = (t >= f0) & (t < f0 + 0.6)
        sp[stop] = np.clip(1 - (t[stop] - f0) / 0.6, 0, 1) ** 1.5
        sp[(t >= f0 + 0.6) & (t < f1)] = 0
        if f1 == FREEZE[1]:
            start = (t >= f1 - 0.25) & (t < f1)
            sp[start] = ((t[start] - (f1 - 0.25)) / 0.25) ** 2
    return sp


tgrid = np.arange(N) / SR
sp = tape_speed(tgrid)
# lectura de la cinta: el tiempo de lectura avanza a la velocidad de la cinta, pero tras cada
# parada se retoma donde marca el reloj (la música sigue en su compás al volver)
read = np.cumsum(sp) / SR
for f0, f1 in (FREEZE, IDLE_FREEZE):
    i1 = int(f1 * SR)
    read[i1:] += tgrid[i1] - read[i1]
wow = 0.0018 * np.sin(2 * np.pi * 0.6 * tgrid)
read = np.clip(read + wow, 0, (N - 1) / SR)
ML = np.interp(read * SR, np.arange(N), ML) * np.minimum(1, sp * 4)
MR = np.interp(read * SR, np.arange(N), MR) * np.minimum(1, sp * 4)
# lo-fi: banda limitada, saturación suave y reducción de bits
ML = np.tanh(lp(ML, 9000) * 1.3)
MR = np.tanh(lp(MR, 9000) * 1.3)
ML = np.round(ML * 2 ** 11) / 2 ** 11
MR = np.round(MR * 2 ** 11) / 2 ** 11
# durante la congelación solo queda un pad muy filtrado (una sola "tinta")
for f0, f1 in (FREEZE, IDLE_FREEZE):
    notes, _ = CHORDS[int(f0 / (4 * BEAT)) % 4]
    t = tt(f1 - f0 + 0.3)
    pad = sum(np.sin(2 * np.pi * hz(m - 12) * t) for m in notes[:3]) / 3
    pad *= np.minimum(1, t / 0.5) * np.clip((f1 - f0 + 0.3 - t) / 0.3, 0, 1) * 0.22
    add(pad, f0 + 0.2, 1.0, 0, (ML, MR))
L += ML
R += MR


# ---------- efectos ----------
def crackle(dur):
    out = np.zeros(int(dur * SR))
    for _ in range(int(dur * 18)):
        i = rng.integers(0, len(out) - 200)
        out[i:i + 60] += hp(rng.standard_normal(60), 3000) * rng.uniform(0.2, 1)
    return out + hp(rng.standard_normal(len(out)), 2000) * 0.015


def press():
    """Pasada de imprenta: rodillo, golpe y la hoja que sale."""
    t = tt(0.7)
    roll = lp(rng.standard_normal(len(t)), 600) * np.exp(-((t - 0.12) / 0.08) ** 2) * 2
    thunk = np.sin(2 * np.pi * np.cumsum(70 + 80 * np.exp(-t * 40)) / SR) * np.exp(-t * 12) * (t > 0.0)
    sheet = hp(lp(rng.standard_normal(len(t)), 4000), 800) * np.exp(-((t - 0.35) / 0.12) ** 2) * 0.6
    return np.tanh(thunk + roll * 0.5 + sheet)


def click():
    t = tt(0.012)
    return (hp(rng.standard_normal(len(t)), 2500) + 0.4 * np.sin(2 * np.pi * 2100 * t)) * np.exp(-t * 500)


def slap():  # papel que golpea la mesa
    t = tt(0.2)
    return hp(rng.standard_normal(len(t)), 500) * np.exp(-t * 45)


def scribble(dur):
    t = tt(dur)
    n = hp(lp(rng.standard_normal(len(t)), 5000), 1200)
    return n * (0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 9 * t))) * np.clip((dur - t) / 0.05, 0, 1)


add(crackle(TOTAL), 0, 0.5)
for t in (b(2), FREEZE[1], b(SILICON[0]), b(HOL[0]), b(END[0])):
    add(press(), t - 0.05, 0.75)
for t in (b(8), b(32), b(33), b(34)) + tuple(b(FEATS[0] + 3 * k) for k in range(4)):
    add(slap(), t, 0.5)
n = len(HOOK_CMD)
for k in range(n):
    add(click(), HOOK_TYPE[0] + (HOOK_TYPE[1] - HOOK_TYPE[0]) * k / (n - 1), 0.3, rng.uniform(-0.2, 0.2))
w, h, fps = TERM_SRC
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", sys.argv[1], "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                     capture_output=True, check=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w)
for r, until in CMD_ROWS.items():  # solo mientras se teclea: hasta que llega la salida del comando
    y = row_y(r)
    d = np.abs(np.diff(fr[:, y:y + 30, 80:980].astype(np.int16), axis=0)).sum(axis=(1, 2))
    for f in np.nonzero(d[:until - 1] > 500)[0]:
        add(click(), out_time((f + 1) / fps), 0.24, rng.uniform(-0.25, 0.25))
for t in (b(14), b(18), FREEZE[1] + 0.02):  # círculos a mano en la terminal
    add(scribble(0.3), t, 0.3)
add(scribble(0.4), b(HOL[0]), 0.3)          # el escudo se dibuja
add(scribble(0.2), b(HOL[0]) + 0.27, 0.35)  # la marca de verificación
# cierre: acorde de piano largo
for k, m in enumerate(CHORDS[0][0]):
    add(epiano(m, 3.0), b(END[0]) + 0.04 * k, 0.12, -0.3 + 0.15 * k)

ir_t = tt(1.4)
ir = lp(rng.standard_normal(len(ir_t)) * np.exp(-ir_t * 3.8), 4000)
ir /= np.sqrt((ir ** 2).sum())


def conv(x):
    m = len(x) + len(ir)
    nfft = 1 << (m - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[: len(x)]


L = L + 0.15 * conv(L)
R = R + 0.15 * conv(R)
fade = np.clip((TOTAL - np.arange(N) / SR) / 0.8, 0, 1)
mix = np.stack([L * fade, R * fade], axis=1)
mix /= np.abs(mix).max() / 0.89
with wave.open(sys.argv[2], "wb") as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes((mix * 32767).astype("<i2").tobytes())
print("audio", round(TOTAL, 2), "s")
