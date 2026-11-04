#!/usr/bin/env python3
"""Kit de SFX sintetizados (libres de derechos) para las gramáticas de promo por código.

Uso: promo_sfx.py GRAMATICA DIR_SALIDA
     GRAMATICA: temperatura | plano | riso

Escribe un WAV por evento (48 kHz, estéreo, pico -3 dBFS) con los mismos sintetizadores que los
promos de kindling v0.20 (promo/kindling-v0.20/audio_*.py), para que un DS de promo tenga su
`sfx.mapa` con archivos reales y FilmCraft o cualquier otro motor los pueda usar.
"""
import sys
import wave
from pathlib import Path

import numpy as np

SR = 48000
rng = np.random.default_rng(42)


def tt(dur):
    return np.arange(int(dur * SR)) / SR


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


# ---------- comunes ----------
def click():
    t = tt(0.012)
    return (hp(rng.standard_normal(len(t)), 2500) + 0.4 * np.sin(2 * np.pi * 2100 * t)) * np.exp(-t * 500)


def ping(f=1760):
    t = tt(0.9)
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t)) * np.exp(-t * 6)


def whoosh(dur=0.42):
    t = tt(dur)
    env = np.sin(np.pi * (t / dur) ** 1.6) ** 2
    return hp(lp(rng.standard_normal(len(t)), 1800), 300) * env


def impact():
    t = tt(1.2)
    boom = np.sin(2 * np.pi * np.cumsum(38 + 70 * np.exp(-t * 14)) / SR) * np.exp(-t * 3.2)
    return np.tanh((boom + hp(rng.standard_normal(len(t)), 1200) * np.exp(-t * 40) * 0.5) * 1.4)


def riser(dur=0.9):
    t = tt(dur)
    sweep = np.sin(2 * np.pi * np.cumsum(220 + 900 * (t / dur) ** 2) / SR) * 0.25
    return (hp(rng.standard_normal(len(t)), 600) * 0.35 + sweep) * (t / dur) ** 2.2


# ---------- temperatura: brasa y escarcha ----------
def ice():
    t = tt(0.9)
    s = np.zeros(len(t))
    for _ in range(70):
        i = int(rng.uniform(0, 0.8) ** 1.7 * SR)
        g = hp(rng.standard_normal(int(0.004 * SR)), 5000) * rng.uniform(0.2, 1)
        s[i:i + len(g)] += g[: len(s) - i]
    glass = sum(np.sin(2 * np.pi * f * t) for f in (2637, 3520, 4186)) * np.exp(-t * 4) * 0.08
    return s * 0.5 + glass


def tick():
    t = tt(0.02)
    return np.sin(2 * np.pi * 3000 * t) * np.exp(-t * 300)


def bell_sting():
    out = np.zeros(int(2.4 * SR))
    for k, m in enumerate([77, 80, 84, 87]):
        f = 440 * 2 ** ((m - 69) / 12)
        t = tt(2.0)
        s = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 6)
        i = int(k * 0.112 * SR)
        out[i:i + len(t)] += s * np.exp(-t * 3.2) * 0.35
    return out


# ---------- plano: lápiz y papel ----------
def pencil(dur=0.6):
    t = tt(dur)
    n = hp(lp(rng.standard_normal(len(t)), 5500), 1500)
    rough = np.abs(lp(rng.standard_normal(len(t)), 40))
    rough /= rough.max() + 1e-9
    return n * (0.4 + 0.6 * rough) * np.minimum(1, t / 0.02) * np.clip((dur - t) / 0.04, 0, 1)


def scribble(dur=0.4):
    t = tt(dur)
    return pencil(dur) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 14 * t)))


def stamp():
    t = tt(0.6)
    body = np.sin(2 * np.pi * np.cumsum(55 + 90 * np.exp(-t * 30)) / SR) * np.exp(-t * 9)
    return np.tanh((body + hp(rng.standard_normal(len(t)), 800) * np.exp(-t * 60) * 0.6) * 1.5)


def paper_slide(dur=0.4):
    t = tt(dur)
    return hp(lp(rng.standard_normal(len(t)), 3000), 400) * np.sin(np.pi * (t / dur)) ** 2


# ---------- riso: imprenta y cinta ----------
def press():
    t = tt(0.7)
    roll = lp(rng.standard_normal(len(t)), 600) * np.exp(-((t - 0.12) / 0.08) ** 2) * 2
    thunk = np.sin(2 * np.pi * np.cumsum(70 + 80 * np.exp(-t * 40)) / SR) * np.exp(-t * 12)
    sheet = hp(lp(rng.standard_normal(len(t)), 4000), 800) * np.exp(-((t - 0.35) / 0.12) ** 2) * 0.6
    return np.tanh(thunk + roll * 0.5 + sheet)


def slap():
    t = tt(0.2)
    return hp(rng.standard_normal(len(t)), 500) * np.exp(-t * 45)


def tape_stop(dur=0.7):
    """Un acorde que frena como una cinta: la velocidad cae a cero."""
    t = tt(dur)
    sp = np.clip(1 - t / (dur * 0.85), 0, 1) ** 1.5
    ph = np.cumsum(sp) / SR
    s = sum(np.sin(2 * np.pi * 440 * 2 ** ((m - 69) / 12) * ph) for m in (53, 56, 60, 63))
    return np.tanh(s * 0.5) * np.minimum(1, sp * 4)


def crackle(dur=4.0):
    out = np.zeros(int(dur * SR))
    for _ in range(int(dur * 18)):
        i = rng.integers(0, len(out) - 200)
        out[i:i + 60] += hp(rng.standard_normal(60), 3000) * rng.uniform(0.2, 1)
    return out + hp(rng.standard_normal(len(out)), 2000) * 0.015


KITS = {
    "temperatura": {"tecla": click, "barrido": whoosh, "gancho": impact, "cierre": bell_sting, "congelar": ice,
                    "despertar": ping, "riser": riser, "contador": tick, "titulo": whoosh},
    "plano": {"tecla": click, "trazo": pencil, "rayado": scribble, "sello": stamp, "barrido": paper_slide,
              "gancho": stamp, "cierre": stamp, "despertar": ping, "medida": lambda: ping(1318), "riser": riser, "titulo": paper_slide},
    "riso": {"tecla": click, "imprenta": press, "gancho": press, "cierre": press, "hoja": slap,
             "rotulador": lambda: scribble(0.3), "congelar": tape_stop, "vinilo": crackle, "riser": riser, "titulo": slap},
}


def write(path, sig):
    sig = np.asarray(sig, float)
    sig = sig / (np.abs(sig).max() + 1e-9) * 10 ** (-3 / 20)
    pcm = (np.stack([sig, sig], axis=1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in KITS:
        sys.exit(__doc__)
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in KITS[sys.argv[1]].items():
        write(out / f"{name}.wav", fn())
        print(out / f"{name}.wav")


if __name__ == "__main__":
    main()
