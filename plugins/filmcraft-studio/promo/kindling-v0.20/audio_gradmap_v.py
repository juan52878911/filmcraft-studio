"""Música y efectos del corte vertical en Gradient Map (gramática "termo@1", guion de timeline_g.py): UK garage
2-step a 134 BPM con pads cálidos desafinados (calima: vibrato lento), stabs de órgano y sub con portamento.
Arranca filtrado y frío; la chispa cae silbando y la ignición ruge mientras el filtro se abre. Congelar es
enfriar: el filtro cae a 180 Hz, el ritmo queda como un pulso apagado y suena una campana de cristal. Los
cambios de escena son cortes secos con un golpe; la llama vuelve al entrar en HOL GUARD y un barrido de escáner
recorre el comando. El cierre se congela y así termina.

Uso: python3 audio_gradmap_v.py <term_v.mp4> <salida.wav>
"""
import subprocess
import sys
import wave

import numpy as np

from timeline_g import (BEATS, BEAT, CMD_ROWS, END, FEATS, FREEZE, HOL, HOOK_CMD, HOOK_TYPE, IDLE_FREEZE, SILICON,
                        SRC0, TERM_SRC, TOTAL, b, out_time, row_y)

SR = 48000
N = int(TOTAL * SR)
STEP = BEAT / 4
rng = np.random.default_rng(31)
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
    """Paso bajo de un polo; `cutoff` puede ser un número o una curva por muestra."""
    a = np.exp(-2 * np.pi * np.broadcast_to(np.asarray(cutoff, float), x.shape) / SR)
    y = np.empty_like(x)
    acc = 0.0
    for k in range(len(x)):
        acc = (1 - a[k]) * x[k] + a[k] * acc
        y[k] = acc
    return y


def hp(x, cutoff):
    return x - lp(x, cutoff)


# ---------- instrumentos ----------
def kick():
    t = tt(0.35)
    return np.tanh(np.sin(2 * np.pi * np.cumsum(46 + 110 * np.exp(-t * 30)) / SR) * np.exp(-t * 8) * 2.2)


def snare():
    t = tt(0.22)
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30)
    return np.tanh(body * 0.6 + hp(rng.standard_normal(len(t)), 1800) * np.exp(-t * 22) * 0.8)


HAT = hp(rng.standard_normal(int(0.03 * SR)), 8000) * np.exp(-tt(0.03) * 140)
OPEN = hp(rng.standard_normal(int(0.16 * SR)), 7000) * np.exp(-tt(0.16) * 22)


def pad(notes, dur):
    """Sierras desafinadas con vibrato lento (la calima) y ataque suave."""
    t = tt(dur)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 0.35 * t)
    s = np.zeros(len(t))
    for m in notes:
        for det in (-0.11, 0.0, 0.13):
            ph = np.cumsum(hz(m + det) * vib) / SR
            s += 2 * (ph % 1) - 1
    s = lp(s / (3 * len(notes)), 2600)
    return s * np.minimum(1, t / 0.25) * np.clip((dur - t) / 0.4, 0, 1)


def organ(notes, dur=0.22):
    t = tt(dur)
    s = sum(np.sin(2 * np.pi * hz(m) * t) + 0.5 * np.sin(4 * np.pi * hz(m) * t) for m in notes) / len(notes)
    return s * np.exp(-t * 14) * np.minimum(1, t / 0.004)


def sub(f0, f1, dur):
    t = tt(dur)
    f = f1 + (f0 - f1) * np.exp(-t * 40)        # portamento corto desde la nota anterior
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.006) * np.clip((dur - t) / 0.04, 0, 1)


def bell(m, dur=2.4):
    """Campana de cristal (FM ligera): lo único que suena mientras está congelado."""
    t = tt(dur)
    mod = np.sin(2 * np.pi * hz(m) * 3.5 * t) * 2.2 * np.exp(-t * 3)
    return np.sin(2 * np.pi * hz(m) * t + mod) * np.exp(-t * 1.6) * np.minimum(1, t / 0.003)


# Fa menor con color garage: Fm9 · Dbmaj7 · Bbm9 · C7sus
CHORDS = [([53, 56, 60, 63, 67], 41), ([49, 53, 56, 60], 37), ([46, 49, 53, 56, 60], 34), ([48, 53, 55, 58], 36)]
KICK = (0, 10)                 # 2-step: uno y el "y" del tres
SNARE = (4, 12)
SWING = 0.22

ML, MR = np.zeros(N), np.zeros(N)
mbuf = (ML, MR)
prev = hz(CHORDS[-1][1])
for bar in range(BEATS // 4):
    t0 = bar * 4 * BEAT
    notes, root = CHORDS[bar % 4]
    add(pad(notes, 4 * BEAT + 0.3), t0, 0.5 if t0 >= b(4) else 0.35, 0, mbuf)
    for st in range(16):
        t = t0 + st * STEP + (SWING * STEP if st % 2 else 0)
        if t < b(4) or t >= IDLE_FREEZE[0]:     # en el congelado el ritmo sigue filtrado: un pulso apagado
            continue
        if st in KICK or (bar % 2 and st == 7):
            add(kick(), t, 0.85, 0, mbuf)
        if st in SNARE:
            add(snare(), t, 0.5, 0.05, mbuf)
        if st % 2 == 1:
            add(HAT, t, 0.14, 0.3, mbuf)
        if st == 14:
            add(OPEN, t, 0.1, -0.3, mbuf)
        if st in (3, 6, 11) and bar % 2 == 0 or st in (3, 9, 14) and bar % 2:
            add(organ([m + 12 for m in notes[:3]]), t, 0.22, -0.2 if st % 2 else 0.2, mbuf)
        if st in (0, 3, 10, 13):
            f = hz(root - 12 + (7 if st == 13 else 0))
            add(sub(prev, f, STEP * 2.6), t, 0.42, 0, mbuf)
            prev = f

# ---------- enfriar: el filtro cae y el reloj sigue ----------
tgrid = np.arange(N) / SR
cut = np.full(N, 16000.0)
LAND = b(2) - 0.06                         # la chispa toca el suelo (gradmap_v.py)
cut[tgrid < LAND] = 420                    # arranque en oscuro: todo filtrado, frío
rise = (tgrid >= LAND) & (tgrid < b(4))    # la llama sube y abre el filtro
cut[rise] = 420 + 15580 * ((tgrid[rise] - LAND) / (b(4) - LAND)) ** 2
for f0, f1 in (FREEZE, IDLE_FREEZE):
    down = (tgrid >= f0) & (tgrid < f1)
    cut[down] = 180 + 15820 * np.exp(-(tgrid[down] - f0) * 9)
    rise = (tgrid >= f1) & (tgrid < f1 + 0.35)
    cut[rise] = 180 + 15820 * ((tgrid[rise] - f1) / 0.35) ** 2
gain = np.ones(N)
for f0, f1 in (FREEZE, IDLE_FREEZE):
    gain[(tgrid >= f0 + 0.6) & (tgrid < f1)] = 0.35
ML = np.tanh(lp(ML, cut) * 1.2) * gain
MR = np.tanh(lp(MR, cut) * 1.2) * gain
for f0, f1 in (FREEZE, IDLE_FREEZE):
    notes, _ = CHORDS[int(f0 / (4 * BEAT)) % 4]
    for k, m in enumerate(notes[:4]):
        add(bell(m + 24, f1 - f0 + 1.0), f0 + 0.15 + k * BEAT / 2, 0.12, -0.4 + 0.27 * k, mbuf)
L += ML
R += MR


# ---------- efectos ----------
def heatwave():
    """onda: bocanada de aire caliente (ruido que se abre y se cierra) con golpe grave."""
    t = tt(0.9)
    n = rng.standard_normal(len(t))
    env = np.exp(-((t - 0.18) / 0.14) ** 2)
    air = lp(n, 300 + 5000 * env) * env * 1.6
    thump = np.sin(2 * np.pi * np.cumsum(55 + 60 * np.exp(-t * 25)) / SR) * np.exp(-t * 9)
    return np.tanh(air + thump * 0.8)


def focus():
    """calor_entra: un barrido de ruido que baja (el desenfoque que se cierra)."""
    t = tt(0.4)
    n = rng.standard_normal(len(t))
    return hp(lp(n, 9000 * np.exp(-t * 8) + 600), 300) * np.exp(-t * 6) * np.minimum(1, t / 0.01)


def click():
    t = tt(0.012)
    return (hp(rng.standard_normal(len(t)), 2500) + 0.4 * np.sin(2 * np.pi * 2100 * t)) * np.exp(-t * 500)


def frost():
    """enfria: siseo que se apaga con un cristal agudo."""
    t = tt(1.0)
    hiss = hp(rng.standard_normal(len(t)), 5000) * np.exp(-t * 4) * 0.5
    return hiss + bell(96, 1.0) * 0.4


def spark_fall():
    """La chispa cae: un silbido que baja y chisporroteo fino."""
    d = LAND - HOOK_TYPE[1]
    t = tt(d)
    f = 3200 - 2000 * (t / d) ** 2
    whistle = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.15 * np.minimum(1, t / 0.02)
    out = whistle
    for _ in range(18):
        i = rng.integers(0, len(out) - 300)
        out[i:i + 200] += hp(rng.standard_normal(200), 4000) * rng.uniform(0.1, 0.4) * np.exp(-tt(200 / SR) * 200)
    return out


def ignite(d=b(4) - LAND + 0.4):
    """Ignición: golpe grave, bocanada y el fuego que ruge mientras sube el frente."""
    t = tt(d)
    n = rng.standard_normal(len(t))
    roar = lp(n, 200 + 6000 * np.clip(t / (d - 0.4), 0, 1) ** 1.5) * np.minimum(1, t / 0.05)
    roar *= np.clip((d - t) / 0.4, 0, 1) * 0.9
    crack = np.zeros(len(t))
    for _ in range(int(d * 50)):
        i = rng.integers(0, len(t) - 400)
        crack[i:i + 300] += hp(rng.standard_normal(300), 2500) * rng.uniform(0.1, 0.6) * np.exp(-tt(300 / SR) * 120)
    out = np.tanh(roar + crack)
    hw = heatwave()
    out[: len(hw)] += hw * 0.8
    return out


add(click(), HOOK_TYPE[1] + 0.02, 0.6)                 # el Enter suelta la chispa
add(spark_fall(), HOOK_TYPE[1], 0.5)
ig = ignite()
add(ig, LAND, 0.75)
def thump():
    """Corte seco: un golpe grave corto."""
    t = tt(0.4)
    return np.tanh(np.sin(2 * np.pi * np.cumsum(50 + 90 * np.exp(-t * 30)) / SR) * np.exp(-t * 11) * 1.8)


def scanner(d=1.0):
    """El foco de HOL GUARD recorre el comando: un barrido que sube y un pitido al final."""
    t = tt(d)
    sweep = np.sin(2 * np.pi * np.cumsum(600 + 1400 * t / d) / SR) * 0.25 * np.sin(np.pi * t / d) ** 2
    out = np.concatenate([sweep, np.sin(2 * np.pi * 1760 * tt(0.18)) * np.exp(-tt(0.18) * 18) * 0.5])
    return out


for t in (b(8), b(SILICON[0]), b(FEATS[0]), b(FEATS[0] + 4), b(FEATS[0] + 8), b(END[0])):
    add(thump(), t, 0.7)                                # cortes secos en el beat
add(ignite(0.9), b(HOL[0]) - 0.05, 0.6)                 # la llama vuelve para entrar en HOL GUARD
add(scanner(), b(HOL[0]) + 0.6, 0.45)
add(heatwave(), FREEZE[1] - 0.05, 0.7)                  # despertar
for t in (b(4), b(4.5), b(5), b(5.5), b(10) + 0.1, b(12) + 0.4, FREEZE[1] + 0.4, b(SILICON[0]) + 0.15,
          b(SILICON[0]) + 0.4, b(HOL[0]) + 0.13, b(END[0])) + tuple(b(FEATS[0] + 4 * k) for k in range(3)):
    add(focus(), t, 0.35, rng.uniform(-0.3, 0.3))
for f0, _ in (FREEZE, IDLE_FREEZE):
    add(frost(), f0, 0.5)
n = len(HOOK_CMD)
for k in range(n):
    add(click(), HOOK_TYPE[0] + (HOOK_TYPE[1] - HOOK_TYPE[0]) * k / (n - 1), 0.3, rng.uniform(-0.2, 0.2))
w, h, fps = TERM_SRC
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", sys.argv[1], "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                     capture_output=True, check=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w)
for r, until in CMD_ROWS.items():
    if r == 0:
        continue                                        # el cat compose.yml no entra en este guion
    y = row_y(r)
    d = np.abs(np.diff(fr[:, y:y + 30, 80:980].astype(np.int16), axis=0)).sum(axis=(1, 2))
    for f in np.nonzero(d[:until - 1] > 500)[0]:
        if (f + 1) / fps < SRC0:
            continue
        add(click(), out_time((f + 1) / fps), 0.24, rng.uniform(-0.25, 0.25))
# cierre: una campana cálida al entrar; el resto lo pone el congelado
add(bell(CHORDS[0][0][-1] + 12, 3.0), b(END[0]) + 0.05, 0.12)

ir_t = tt(1.6)
ir = lp(rng.standard_normal(len(ir_t)) * np.exp(-ir_t * 3.2), 5000)
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
with wave.open(sys.argv[2], "wb") as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes((mix * 32767).astype("<i2").tobytes())
print("audio", round(TOTAL, 2), "s")
