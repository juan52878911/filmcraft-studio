#!/usr/bin/env python3
"""Kit de SFX sintetizados (libres de derechos) para las gramáticas de promo por código.

Uso: promo_sfx.py GRAMATICA DIR_SALIDA [--solo evento,evento]
     GRAMATICA: temperatura | plano | riso | termo | tres-fases (= kit riso)

--solo escribe solo esos eventos (para completar un kit sin tocar los WAV que ya existen).

Escribe un WAV por evento (48 kHz, estéreo, pico -3 dBFS) con los sintetizadores con que se hicieron
los primeros promos de cada gramática, para que un DS de promo tenga su `sfx.mapa` con archivos reales
y FilmCraft o cualquier otro motor los pueda usar.
"""
import argparse
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


# ---------- termo: gradient map / cámara térmica ----------
def heatwave():
    """onda: bocanada de aire caliente (ruido que se abre y se cierra) con golpe grave."""
    t = tt(0.9)
    env = np.exp(-((t - 0.18) / 0.14) ** 2)
    air = np.zeros(len(t))
    n = rng.standard_normal(len(t))
    for k in range(0, len(t), 480):  # filtro que sigue a la envolvente, por bloques de 10 ms
        a = np.exp(-2 * np.pi * (300 + 5000 * env[k]) / SR)
        acc = air[k - 1] if k else 0.0
        for j in range(k, min(len(t), k + 480)):
            acc = (1 - a) * n[j] + a * acc
            air[j] = acc
    thump = np.sin(2 * np.pi * np.cumsum(55 + 60 * np.exp(-t * 25)) / SR) * np.exp(-t * 9)
    return np.tanh(air * env * 1.6 + thump * 0.8)


def focus():
    """calor_entra: ruido que baja de brillo, el desenfoque que se cierra."""
    t = tt(0.4)
    n = hp(rng.standard_normal(len(t)), 300)
    out = np.zeros(len(t))
    acc = 0.0
    for j in range(len(t)):
        a = np.exp(-2 * np.pi * (9000 * np.exp(-t[j] * 8) + 600) / SR)
        acc = (1 - a) * n[j] + a * acc
        out[j] = acc
    return out * np.exp(-t * 6) * np.minimum(1, t / 0.01)


def glass_bell(f=2093.0, dur=2.0):
    t = tt(dur)
    mod = np.sin(2 * np.pi * f * 3.5 * t) * 2.2 * np.exp(-t * 3)
    return np.sin(2 * np.pi * f * t + mod) * np.exp(-t * 1.6) * np.minimum(1, t / 0.003)


def frost():
    """enfria: siseo que se apaga y un cristal agudo."""
    t = tt(1.0)
    return hp(rng.standard_normal(len(t)), 5000) * np.exp(-t * 4) * 0.5 + glass_bell(4186, 1.0) * 0.4


def spark_fall(d=0.42):
    """chispa: silbido que baja con chisporroteo fino."""
    t = tt(d)
    out = np.sin(2 * np.pi * np.cumsum(3200 - 2000 * (t / d) ** 2) / SR) * 0.15 * np.minimum(1, t / 0.02)
    for _ in range(18):
        i = rng.integers(0, len(out) - 300)
        out[i:i + 200] += hp(rng.standard_normal(200), 4000) * rng.uniform(0.1, 0.4) * np.exp(-tt(200 / SR) * 200)
    return out


def ignition(d=1.4):
    """ignicion: golpe grave, el fuego que ruge mientras sube el frente y chasquidos."""
    t = tt(d)
    n = rng.standard_normal(len(t))
    roar = np.zeros(len(t))
    acc = 0.0
    for j in range(len(t)):
        a = np.exp(-2 * np.pi * (200 + 6000 * min(1, t[j] / (d - 0.4)) ** 1.5) / SR)
        acc = (1 - a) * n[j] + a * acc
        roar[j] = acc
    roar *= np.minimum(1, t / 0.05) * np.clip((d - t) / 0.4, 0, 1) * 0.9
    for _ in range(int(d * 50)):
        i = rng.integers(0, len(t) - 400)
        roar[i:i + 300] += hp(rng.standard_normal(300), 2500) * rng.uniform(0.1, 0.6) * np.exp(-tt(300 / SR) * 120)
    out = np.tanh(roar)
    hw = heatwave()
    out[: len(hw)] += hw * 0.8
    return out


def thump():
    """golpe: corte seco en el beat."""
    t = tt(0.4)
    return np.tanh(np.sin(2 * np.pi * np.cumsum(50 + 90 * np.exp(-t * 30)) / SR) * np.exp(-t * 11) * 1.8)


def scanner(d=1.0):
    """escaner: un foco recorre el comando (barrido que sube y pitido)."""
    t = tt(d)
    sweep = np.sin(2 * np.pi * np.cumsum(600 + 1400 * t / d) / SR) * 0.25 * np.sin(np.pi * t / d) ** 2
    return np.concatenate([sweep, np.sin(2 * np.pi * 1760 * tt(0.18)) * np.exp(-tt(0.18) * 18) * 0.5])


def warm_chord():
    """cierre: acorde cálido de sierras desafinadas (Fm9) con campana."""
    t = tt(2.6)
    s = np.zeros(len(t))
    for m in (53, 56, 60, 63, 67):
        for det in (-0.11, 0.0, 0.13):
            ph = np.cumsum(np.full(len(t), 440 * 2 ** ((m + det - 69) / 12))) / SR
            s += 2 * (ph % 1) - 1
    s = lp(s / 15, 2600) * np.minimum(1, t / 0.05) * np.clip((2.6 - t) / 0.8, 0, 1)
    return s + glass_bell(1568, 2.6) * 0.15


KITS = {
    "temperatura": {"tecla": click, "barrido": whoosh, "gancho": impact, "cierre": bell_sting, "congelar": ice,
                    "despertar": ping, "riser": riser, "contador": tick, "titulo": whoosh},
    "plano": {"tecla": click, "trazo": pencil, "rayado": scribble, "sello": stamp, "barrido": paper_slide,
              "gancho": stamp, "cierre": stamp, "despertar": ping, "medida": lambda: ping(1318), "riser": riser, "titulo": paper_slide,
              "contador": tick},
    "riso": {"tecla": click, "imprenta": press, "gancho": press, "cierre": press, "hoja": slap,
             "rotulador": lambda: scribble(0.3), "congelar": tape_stop, "vinilo": crackle, "riser": riser, "titulo": slap,
             "despertar": ping, "contador": tick},
    "termo": {"tecla": click, "onda": heatwave, "gancho": heatwave, "enfoque": focus, "titulo": focus,
              "congelar": frost, "despertar": heatwave, "cierre": warm_chord, "contador": tick, "riser": riser,
              "chispa": spark_fall, "ignicion": ignition, "golpe": thump, "escaner": scanner},
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


KITS["tres-fases"] = KITS["riso"]   # vidrio → termo → riso: entrega en riso


def main():
    ap = argparse.ArgumentParser(description="Kit de SFX sintetizados de una gramática de promo.")
    ap.add_argument("gramatica")
    ap.add_argument("salida")
    ap.add_argument("--solo", default="", help="eventos separados por comas")
    a = ap.parse_args()
    g = a.gramatica.split("@")[0]
    if g not in KITS:
        sys.exit(f"gramática '{g}' sin kit de SFX; conocidas: {', '.join(sorted(KITS))}")
    solo = [x for x in a.solo.split(",") if x]
    falta = [x for x in solo if x not in KITS[g]]
    if falta:
        sys.exit(f"el kit {g} no tiene {', '.join(falta)}; tiene: {', '.join(KITS[g])}")
    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in KITS[g].items():
        if solo and name not in solo:
            continue
        write(out / f"{name}.wav", fn())
        print(out / f"{name}.wav")


if __name__ == "__main__":
    main()
