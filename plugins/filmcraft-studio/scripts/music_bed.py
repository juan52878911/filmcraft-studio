"""Base musical sintetizada (promo-tech, La menor, 112 bpm) a la duración pedida.

Uso: music_bed.py SALIDA.wav DURACION_S [--bpm 112]
Adaptado de sonidos/_scripts/synth_bed.py: BARS sale de la duración (+1 compás de cola) y el WAV se recorta.
"""
import math
import numpy as np, wave, sys

SR = 44100
BPM = float(sys.argv[sys.argv.index('--bpm') + 1]) if '--bpm' in sys.argv else 112
BEAT = 60 / BPM
BAR = BEAT * 4
BARS = max(4, math.ceil(float(sys.argv[2]) / (60 / BPM * 4)) + 1)
TOTAL = BAR * BARS
N = int(TOTAL * SR)
t_all = np.arange(N) / SR
rng = np.random.default_rng(7)

def midi(n): return 440 * 2 ** ((n - 69) / 12)

# A minor: Am F C G  (roots 57,53,48,55 -> midi)
CHORDS = [
    (57, [57, 60, 64]),   # Am
    (53, [53, 57, 60]),   # F
    (48, [48, 52, 55]),   # C
    (55, [55, 59, 62]),   # G
]

mix = np.zeros(N)

def add(buf, start, sig):
    i = int(start * SR)
    j = min(i + len(sig), N)
    if i >= N: return
    buf[i:j] += sig[: j - i]

def env(n, a, d, s=0.0, r=0.0, hold=0.0):
    a_n, d_n, h_n, r_n = int(a*SR), int(d*SR), int(hold*SR), int(r*SR)
    e = np.zeros(n)
    idx = 0
    seg = np.linspace(0, 1, max(a_n,1)); e[idx:idx+len(seg)] = seg[:n-idx]; idx += a_n
    seg = np.linspace(1, s, max(d_n,1)); e[idx:idx+len(seg)] = seg[:max(n-idx,0)]; idx += d_n
    e[idx:idx+h_n] = s; idx += h_n
    seg = np.linspace(s, 0, max(r_n,1)); e[idx:idx+len(seg)] = seg[:max(n-idx,0)]
    return e[:n]

def onepole_lp(x, cutoff):
    # vectorised approximation: FFT-based lowpass
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1/SR)
    H = 1 / np.sqrt(1 + (f / cutoff) ** 4)
    return np.fft.irfft(X * H, n=len(x))

def onepole_hp(x, cutoff):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1/SR)
    H = (f / cutoff) ** 2 / np.sqrt(1 + (f / cutoff) ** 4)
    return np.fft.irfft(X * H, n=len(x))

# ---------- drums ----------
kick_len = int(0.35 * SR); tk = np.arange(kick_len) / SR
kick = np.sin(2*np.pi*(45*tk + (150-45)*0.04*(1-np.exp(-tk/0.04)))) * np.exp(-tk*9)
kick += 0.4*np.sin(2*np.pi*55*tk)*np.exp(-tk*14)
kick *= 0.9

hat_len = int(0.06*SR); th = np.arange(hat_len)/SR
hat = onepole_hp(rng.standard_normal(hat_len), 7000) * np.exp(-th*70) * 0.25
hat_open = onepole_hp(rng.standard_normal(int(0.18*SR)), 6000) * np.exp(-np.arange(int(0.18*SR))/SR*18) * 0.18

clap_len = int(0.2*SR); tc = np.arange(clap_len)/SR
clap = onepole_lp(onepole_hp(rng.standard_normal(clap_len), 1200), 6000) * np.exp(-tc*25) * 0.5
clap[int(0.012*SR):] += (onepole_hp(rng.standard_normal(clap_len-int(0.012*SR)), 1500) * np.exp(-tc[:clap_len-int(0.012*SR)]*25) * 0.3)

drums = np.zeros(N)
kick_track = np.zeros(N)
for bar in range(BARS):
    intro = bar < 4
    outro = bar >= BARS - 1
    for beat in range(4):
        tb = bar*BAR + beat*BEAT
        if not intro and not outro:
            add(drums, tb, kick); add(kick_track, tb, np.ones(int(0.12*SR)))
        if not intro and beat in (1, 3) and not outro:
            add(drums, tb, clap)
        # hats on 8ths from bar 2
        if bar >= 2 and not outro:
            add(drums, tb, hat*0.8)
            add(drums, tb + BEAT/2, hat_open if beat == 3 else hat)
        # 16th shuffle hats in full section
        if bar >= 12 and not outro:
            add(drums, tb + BEAT/4, hat*0.35); add(drums, tb + 3*BEAT/4, hat*0.35)

# ---------- bass ----------
bass = np.zeros(N)
def saw(freq, n):
    tt = np.arange(n)/SR
    s = np.zeros(n)
    for k in range(1, 12):
        s += np.sin(2*np.pi*freq*k*tt)/k
    return s
for bar in range(BARS):
    if bar < 4 or bar >= BARS-1: continue
    root, _ = CHORDS[bar % 4]
    f = midi(root - 12)
    pattern = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5] if bar >= 8 else [0, 1, 2, 3]
    for i, p in enumerate(pattern):
        n = int(BEAT*0.5*SR)
        note = saw(f * (2 if (bar >= 8 and i % 4 == 3) else 1), n)
        note += 0.6*np.sin(2*np.pi*f*np.arange(n)/SR)
        note *= env(n, 0.004, 0.22, 0.0)
        add(bass, bar*BAR + p*BEAT, note*0.55)
bass = onepole_lp(bass, 900)

# ---------- arp ----------
arp = np.zeros(N)
for bar in range(BARS):
    if bar < 2 or bar >= BARS-1: continue
    _, tones = CHORDS[bar % 4]
    seq = [tones[0]+12, tones[1]+12, tones[2]+12, tones[0]+24, tones[2]+12, tones[1]+12, tones[0]+12, tones[2]+24]
    step = BEAT/4
    for i in range(16):
        n = int(step*1.2*SR)
        f = midi(seq[i % len(seq)])
        tt = np.arange(n)/SR
        note = (np.sign(np.sin(2*np.pi*f*tt))*0.5 + np.sin(2*np.pi*f*tt)*0.5) * env(n, 0.002, 0.16, 0.0)
        vel = 0.9 if i % 4 == 0 else 0.6
        add(arp, bar*BAR + i*step, note*0.22*vel)
arp = onepole_lp(arp, 4500)

# ---------- pad ----------
pad = np.zeros(N)
for bar in range(BARS):
    _, tones = CHORDS[bar % 4]
    n = int(BAR*1.05*SR); tt = np.arange(n)/SR
    chord = np.zeros(n)
    for m in tones:
        f = midi(m)
        for det in (-0.4, 0.0, 0.4):
            chord += saw(f * 2 ** (det/1200), n)
    chord /= 9
    chord *= env(n, 0.6, 0.3, 0.8, 0.5, hold=BAR-1.4)
    add(pad, bar*BAR, chord*0.16)
pad = onepole_lp(pad, 1800)

# ---------- riser / FX ----------
fx = np.zeros(N)
for bar in (3, 11):
    n = int(BAR*SR); tt = np.arange(n)/SR
    noise = onepole_hp(rng.standard_normal(n), 800) * (tt/BAR)**2 * 0.12
    add(fx, bar*BAR, noise)

# ---------- sidechain ----------
duck = np.ones(N)
k = int(0.25*SR)
decay = np.linspace(0.35, 1.0, k)
idx = np.flatnonzero(np.diff(np.concatenate([[0], kick_track])) > 0)
for i in idx:
    duck[i:i+k] = np.minimum(duck[i:i+k], decay[:min(k, N-i)])

mix = drums + (bass + arp + pad) * duck + fx
# master fades
fade_out = int(2.5*SR); mix[-fade_out:] *= np.linspace(1, 0, fade_out)
fade_in = int(0.3*SR); mix[:fade_in] *= np.linspace(0, 1, fade_in)
mix = mix / np.max(np.abs(mix)) * 0.9
out = (mix * 32767).astype(np.int16)
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())
print("wrote", sys.argv[1], round(TOTAL, 2), "s")
