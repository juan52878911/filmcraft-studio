"""Render del promo de kindling v0.20 (1920x1080, 30 fps) a un pipe de ffmpeg.

Kit visual: fondo brasa #14100D, acento brasa #FF5A1F (en marcha) y escarcha #8FD3FF (congelado);
DIN Condensed para titulares y cifras, Iosevka Term para todo lo que es terminal.
La firma: "temperatura" — lo que corre es brasa, lo que se congela se vuelve escarcha y el grano se para.

Uso: python3 brasa.py <term.mp4> <frames_dir_tmp> <salida.mp4 sin audio> [solo_t1,t2,...]
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from timeline import (BEAT, END, FPS, FREEZE, H, HOOK_CMD, HOOK_TYPE, IDLE_FREEZE, TOTAL, W, b, row_y,
                      src_time)

BG = (20, 16, 13)
INK = (237, 230, 221)
DIM = (107, 94, 84)
SOFT = (156, 142, 130)
EMBER = (255, 90, 31)
FROST = (143, 211, 255)

HOME = os.path.expanduser("~/Library/Fonts/")
DIN = "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf"
MONO = HOME + "IosevkaTermNerdFontMono-Regular.ttf"
MONO_B = HOME + "IosevkaTermNerdFontMono-Bold.ttf"
_fonts = {}


def font(path, size):
    key = (path, int(size))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(path, int(size))
    return _fonts[key]


# ---------- easing ----------
def clamp(x, a=0.0, b_=1.0):
    return max(a, min(b_, x))


def prog(t, t0, t1):
    return clamp((t - t0) / (t1 - t0))


def out_expo(x):
    return 1 if x >= 1 else 1 - 2 ** (-10 * x)


def in_out_cubic(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def out_back(x, s=1.5):
    x -= 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b_, x):
    return a + (b_ - a) * x


def mix(c1, c2, x):
    return tuple(int(lerp(p, q, x)) for p, q in zip(c1, c2))


# ---------- recursos ----------
term_path, tmp_dir = sys.argv[1], sys.argv[2]
os.makedirs(tmp_dir, exist_ok=True)
if not os.path.exists(os.path.join(tmp_dir, "f0001.png")):
    subprocess.run(["ffmpeg", "-v", "error", "-i", term_path, os.path.join(tmp_dir, "f%04d.png")], check=True)
TERM_FRAMES = sorted(f for f in os.listdir(tmp_dir) if f.endswith(".png"))
_term_cache = {}


def term_frame(src_t):
    i = clamp(int(src_t * 25), 0, len(TERM_FRAMES) - 1)
    if i not in _term_cache:
        _term_cache.clear()
        _term_cache[i] = Image.open(os.path.join(tmp_dir, TERM_FRAMES[int(i)])).convert("RGB")
    return _term_cache[i]


rng = np.random.default_rng(3)
GRAIN = [rng.normal(0, 7, (H // 2, W // 2)).astype(np.float32) for _ in range(6)]
yy, xx = np.mgrid[0:H, 0:W]
VIGNETTE = (1 - 0.28 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) ** 1.4).astype(np.float32)
VIGNETTE = np.clip(VIGNETTE, 0.55, 1)[..., None]


def text(d, xy, s, f, fill, anchor="la", tracking=0):
    if not tracking:
        d.text(xy, s, font=f, fill=fill, anchor=anchor)
        return
    x, y = xy
    widths = [f.getlength(c) + tracking for c in s]
    total = sum(widths) - tracking
    if anchor[0] == "m":
        x -= total / 2
    elif anchor[0] == "r":
        x -= total
    for c, w_ in zip(s, widths):
        d.text((x, y), c, font=f, fill=fill, anchor="l" + anchor[1])
        x += w_


# ---------- escenas ----------
def hook(t):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    # 1) comando tecleado
    n = int(len(HOOK_CMD) * prog(t, HOOK_TYPE[0], HOOK_TYPE[1]) + 0.999) if t >= HOOK_TYPE[0] else 0
    up = out_expo(prog(t, b(2), b(2) + 0.35))
    size = lerp(78, 40, up)
    y = lerp(H / 2, 250, up)
    f = font(MONO, size)
    cmd = "❯ " + HOOK_CMD[:n]
    full_w = f.getlength("❯ " + HOOK_CMD)
    x0 = W / 2 - full_w / 2
    out_hl = prog(t, b(4), b(4) + 0.25)
    col = mix(INK, DIM, up)
    if out_hl < 1:
        a = 1 - out_hl
        d.text((x0, y), "❯", font=f, fill=mix(BG, EMBER, a), anchor="lm")
        d.text((x0 + f.getlength("❯ "), y), HOOK_CMD[:n], font=f, fill=mix(BG, col, a), anchor="lm")
        if t < b(2) and int(t * 4) % 2 == 0 or HOOK_TYPE[0] <= t < b(2):
            cx = x0 + f.getlength(cmd)
            d.rectangle([cx + 4, y - size * 0.5, cx + 4 + size * 0.5, y + size * 0.5], fill=EMBER)
    # 2) "0.4s" en el beat 2
    if b(2) <= t < b(4) + 0.3:
        p = prog(t, b(2), b(2) + 0.42)
        s = out_back(p, 1.2)
        size = 470 * lerp(1.35, 1.0, s)
        a = 1 - prog(t, b(4), b(4) + 0.25)
        text(d, (W / 2, H / 2 + 60), "0.4s", font(DIN, size), mix(BG, EMBER, a), anchor="mm")
        f2 = font(MONO, 34)
        d.text((W / 2, H / 2 + 330), "demo is up in 0.4s", font=f2, fill=mix(BG, DIM, a * prog(t, b(2) + 0.2, b(3))),
               anchor="mm")
    # 3) titular escalonado
    if t >= b(4):
        lines = [("DOCKER COMPOSE.", INK), ("EN MICROVMS.", INK), ("EN TU MAC.", EMBER)]
        for k, (s_, c) in enumerate(lines):
            p = out_expo(prog(t, b(4) + k * BEAT / 2, b(4) + k * BEAT / 2 + 0.5))
            if p <= 0:
                continue
            yk = 330 + k * 190 + (1 - p) * 60
            # máscara: el texto sube desde detrás de una línea
            layer = Image.new("RGB", (W, 200), BG)
            ld = ImageDraw.Draw(layer)
            text(ld, (180, 100 + (1 - p) * 120), s_, font(DIN, 210), c, anchor="lm", tracking=2)
            im.paste(layer, (0, int(yk - 100)))
        f3 = font(MONO, 30)
        p = prog(t, b(5), b(6))
        d.text((186, 160), "kindling v0.20", font=f3, fill=mix(BG, DIM, p), anchor="lm")
        d.text((W - 180, 160), "kling compose up -d", font=f3, fill=mix(BG, DIM, p), anchor="rm")
    return im


TERM_ORIGIN = (160, 90)  # la ventana de 1600x900 dentro del lienzo


def row_center(i, col0=0, col1=None):
    """Centro en el lienzo de la fila i, columnas col0..col1 (16.2 px por carácter)."""
    cw = 16.2
    y = TERM_ORIGIN[1] + row_y(i) + 15
    x0 = TERM_ORIGIN[0] + 56 + col0 * cw
    x1 = TERM_ORIGIN[0] + 56 + (col1 if col1 is not None else col0 + 10) * cw
    return x0, x1, y


# cámara: (t, cx, cy, zoom) en coordenadas del lienzo
CAM = [
    (b(8), 960, 540, 1.0),
    (b(8) + 0.6, 960, 540, 1.0),
    (b(11), 640, 360, 1.45),
    (b(13), 700, 560, 1.7),
    (b(14), 700, 560, 1.82),
    (b(17), 720, 660, 1.65),
    (b(20), 680, 680, 1.85),
    (b(26), 680, 680, 1.85),   # congelado: la cámara no se mueve
    (b(26) + 0.25, 620, 720, 2.2),
    (b(28), 900, 640, 1.2),
]


def cam_at(t):
    for (t0, *a), (t1, *c) in zip(CAM, CAM[1:]):
        if t <= t1:
            x = in_out_cubic(prog(t, t0, t1))
            return [lerp(p, q, x) for p, q in zip(a, c)]
    return CAM[-1][1:]


def to_screen(cam, x, y):
    cx, cy, z = cam
    return (x - cx) * z + W / 2, (y - cy) * z + H / 2


def terminal(t):
    st = src_time(t)
    canvas = Image.new("RGB", (W, H), BG)
    tf = term_frame(st)
    canvas.paste(tf, TERM_ORIGIN)
    d = ImageDraw.Draw(canvas)
    ox, oy = TERM_ORIGIN
    d.rectangle([ox - 1, oy - 1, ox + 1600, oy + 900], outline=(58, 42, 32), width=2)
    d.text((ox, oy - 36), "~/demo   kling 0.20.1   grabación real", font=font(MONO, 24), fill=DIM, anchor="lm")
    cx, cy, z = cam_at(t)
    if b(14) <= t < b(14) + 0.2:  # golpe de zoom en el beat del "0.4s"
        z *= 1 + 0.06 * math.sin(math.pi * prog(t, b(14), b(14) + 0.2))
    cam = (cx, cy, z)
    cw, ch = W / z, H / z
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    im = canvas.transform((W, H), Image.EXTENT, box, Image.BICUBIC)
    d = ImageDraw.Draw(im)

    # resaltado "0.4s"
    if t >= b(14):
        x0, x1, y = row_center(8, 14, 18)
        a = clamp(1 - prog(t, b(19), b(20)))
        if a > 0:
            p = out_expo(prog(t, b(14), b(14) + 0.3))
            sx0, sy = to_screen(cam, x0 - 6, y)
            sx1, _ = to_screen(cam, x1 + 6, y)
            hh = 22 * cam[2]
            d.rectangle([sx0, sy - hh, sx0 + (sx1 - sx0) * p, sy + hh], outline=mix(BG, EMBER, a), width=4)
            text(d, (sx1 + 30, sy - 4), "ARRANQUE EN CALIENTE", font(DIN, 62), mix(BG, EMBER, a * p), anchor="lm",
                 tracking=2)
    # congelado
    if FREEZE[0] <= t < FREEZE[1] + 0.3:
        x0, x1, y = row_center(12, 0, 22)
        a = clamp(prog(t, FREEZE[0], FREEZE[0] + 0.25)) * clamp(1 - prog(t, FREEZE[1], FREEZE[1] + 0.3))
        sx1, sy = to_screen(cam, x1 + 10, y)
        text(d, (sx1 + 30, sy - 4), "CONGELADO · 0 RAM", font(DIN, 62), mix(BG, FROST, a), anchor="lm", tracking=2)
    # PONG: despierta
    if t >= FREEZE[1]:
        x0, x1, y = row_center(14, 0, 4)
        p = out_expo(prog(t, FREEZE[1], FREEZE[1] + 0.35))
        a = clamp(1 - prog(t, b(27.4), b(28)))
        sx1, sy = to_screen(cam, x1 + 10, y)
        text(d, (sx1 + 34, sy - 4), "SE DESPIERTA CON LA PRIMERA CONEXIÓN", font(DIN, 58), mix(BG, EMBER, p * a),
             anchor="lm", tracking=2)
    return im


STATS_DATA = [
    ("~4×", None, "CARPETAS COMPARTIDAS EN VIVO, MÁS RÁPIDAS EN MAC",
     "lectura en el laboratorio: 21 → ~167 MiB/s (p50, n=5)"),
    ("0.25 s", "2.24 s", "LA APP COMPOSE DE PRUEBA RESPONDE",
     "kling-hv, p50 · un servicio que aún no escucha recibe reset al momento"),
    ("0.19 ms", "104 ms", "PAUSA p99 CON 4 vCPU EN UN MAC CARGADO",
     "kling-hv sube la QoS de los vCPU y re-empuja a los rezagados"),
]


def stats(t):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    k = min(2, int((t - b(28)) / (4 * BEAT)))
    t0 = b(28 + 4 * k)
    big, old, label, foot = STATS_DATA[k]
    p = out_expo(prog(t, t0, t0 + 0.45))
    dy = (1 - p) * 140
    # contador: los dígitos ruedan hasta su valor
    roll = prog(t, t0, t0 + 0.4)
    shown = big
    if roll < 1:
        chars = list(big)
        for i, c in enumerate(chars):
            if c.isdigit() and roll < 0.3 + 0.7 * i / len(chars):
                chars[i] = str(int(t * 40 + i * 3) % 10)
        shown = "".join(chars)
    text(d, (180, 620 + dy), shown, font(DIN, 400), EMBER, anchor="ls", tracking=4)
    if old:
        fo = font(DIN, 110)
        a = prog(t, t0 + 0.15, t0 + 0.5)
        text(d, (190, 260 + dy), "ANTES " + old, fo, mix(BG, DIM, a), anchor="ls", tracking=2)
        wline = fo.getlength("ANTES " + old) + 2 * 6
        s = prog(t, t0 + 0.45, t0 + 0.75)
        d.line([190, 228 + dy, 190 + wline * s, 228 + dy], fill=EMBER, width=6)
    pl = prog(t, t0 + 0.25, t0 + 0.7)
    text(d, (186, 750 + (1 - pl) * 40), label, font(DIN, 84), mix(BG, INK, pl), anchor="ls", tracking=2)
    d.text((190, 830), foot, font=font(MONO, 30), fill=mix(BG, SOFT, prog(t, t0 + 0.5, t0 + 1.0)), anchor="ls")
    d.text((186, 120), f"kindling v0.20 · {k + 1}/3", font=font(MONO, 28), fill=DIM, anchor="lm")
    d.text((W - 180, 120), "medido · CHANGELOG", font=font(MONO, 28), fill=DIM, anchor="rm")
    return im


def idle(t):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    p1 = out_expo(prog(t, b(40), b(40) + 0.4))
    text(d, (180, 420 + (1 - p1) * 60), "¿NADIE LO USA EN 10 MIN?", font(DIN, 150), mix(BG, INK, p1), anchor="ls",
         tracking=2)
    p2 = out_expo(prog(t, b(42), b(42) + 0.35))
    if p2 > 0:
        text(d, (180, 660 + (1 - p2) * 60), "SE CONGELA SOLO.", font(DIN, 210), mix(BG, FROST, p2), anchor="ls",
             tracking=2)
        d.text((186, 760), "daemon.idle_freeze = 10m  ·  la siguiente conexión lo despierta",
               font=font(MONO, 32), fill=mix(BG, SOFT, p2), anchor="ls")
    return im


def end(t):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    t0 = b(END[0])
    p = out_back(prog(t, t0, t0 + 0.5), 1.1)
    text(d, (W / 2, 520), "KINDLING", font(DIN, lerp(330, 300, p)), mix(BG, INK, clamp(p)), anchor="ms", tracking=10)
    pv = out_expo(prog(t, t0 + STEP_T * 2, t0 + STEP_T * 2 + 0.4))
    text(d, (W / 2, 640), "v0.20", font(DIN, 120), mix(BG, EMBER, pv), anchor="ms", tracking=6)
    wl = 520 * out_expo(prog(t, t0 + 0.1, t0 + 0.8))
    d.line([W / 2 - wl, 690, W / 2 + wl, 690], fill=EMBER, width=3)
    pc = prog(t, t0 + 0.6, t0 + 1.1)
    d.text((W / 2, 770), "microVMs que se congelan cuando nadie las usa", font=font(MONO, 34),
           fill=mix(BG, INK, pc), anchor="ms")
    d.text((W / 2, 840), "kling upgrade  ·  github.com/juan52878911/kindling", font=font(MONO_B, 34),
           fill=mix(BG, EMBER, pc), anchor="ms")
    return im


STEP_T = BEAT / 4


def whip(a, b_img, x):
    """Barrido horizontal con desenfoque de movimiento entre dos fotogramas."""
    off = in_out_cubic(x)
    A = np.asarray(a, np.float32)
    Bm = np.asarray(b_img, np.float32)
    shift = int(off * W)
    comp = np.empty_like(A)
    comp[:, : W - shift] = A[:, shift:]
    comp[:, W - shift:] = Bm[:, : shift]
    blur = int(80 * math.sin(math.pi * x))
    if blur > 2:
        acc = np.zeros_like(comp)
        taps = 6
        for k in range(taps):
            acc += np.roll(comp, int(blur * k / taps), axis=1)
        comp = acc / taps
    return comp


def scene(t):
    if t < b(8):
        return hook(t)
    if t < b(28):
        return terminal(t)
    if t < b(40):
        return stats(t)
    if t < b(END[0]):
        return idle(t)
    return end(t)


def temperature(t):
    """0 = brasa, 1 = escarcha."""
    def win(r):
        return clamp(prog(t, r[0], r[0] + 0.2)) * clamp(1 - prog(t, r[1], r[1] + 0.12))
    return max(win(FREEZE), win(IDLE_FREEZE))


def frame(t):
    WH = 0.22  # duración del barrido
    if any(c - WH / 2 <= t < c + WH / 2 for c in (b(8), b(28))):
        c = b(8) if t < b(20) else b(28)
        x = prog(t, c - WH / 2, c + WH / 2)
        arr = whip(scene(c - WH / 2 - 1e-3), scene(c + WH / 2), x)
    else:
        arr = np.asarray(scene(t), np.float32)

    cold = temperature(t)
    if cold > 0:  # escarcha: desatura hacia azul hielo
        lum = arr.mean(axis=2, keepdims=True)
        ice = lum * np.array([0.62, 0.86, 1.08], np.float32) + np.array([4, 10, 22], np.float32)
        arr = arr * (1 - 0.85 * cold) + ice * 0.85 * cold
    # grano: se mueve mientras algo corre, se queda quieto en la congelación
    gi = 0 if cold > 0.5 else int(t * FPS) % len(GRAIN)
    g = np.repeat(np.repeat(GRAIN[gi], 2, axis=0), 2, axis=1)[..., None]
    arr = arr * VIGNETTE + g
    # barra de temperatura (progreso) abajo
    x = int(W * t / TOTAL)
    col = np.array(mix(EMBER, FROST, cold), np.float32)
    arr[H - 6:H, :x] = col
    # fundido final
    fade = clamp((TOTAL - t) / 0.6)
    arr *= fade
    return np.clip(arr, 0, 255).astype(np.uint8)


def main():
    out = sys.argv[3]
    only = [float(x) for x in sys.argv[4].split(",")] if len(sys.argv) > 4 else None
    if only:
        for t in only:
            Image.fromarray(frame(t)).save(f"{out}_{t:05.2f}.png")
        return
    n = int(TOTAL * FPS)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                          "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(frame(i / FPS).tobytes())
        if i % 60 == 0:
            print(f"{i}/{n}", flush=True)
    p.stdin.close()
    p.wait()


if __name__ == "__main__":
    main()
