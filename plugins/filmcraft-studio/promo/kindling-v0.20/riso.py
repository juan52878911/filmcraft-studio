"""Promo de kindling v0.20 en estilo Risografía: dos tintas (rosa flúor y azul) sobre papel.

Cada fotograma se compone como dos pasadas de impresión que se multiplican: la azul y la rosa, con el
registro desplazado. La animación va "a dos" (15 fps) y las formas tiemblan un poco, como stop-motion.
La firma: congelado = una sola tinta. La pasada rosa se detiene, entra un semitono azul, el temblor y el
grano se paran; al despertar, la rosa vuelve con un golpe de registro.

Uso: python3 riso.py <term.mp4> <frames_dir_tmp> <salida.mp4 sin audio> [solo_t1,t2,...]
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from timeline import BEAT, END, FPS, FREEZE, H, HOOK_CMD, HOOK_TYPE, IDLE_FREEZE, TOTAL, W, b, row_y, src_time

PAPER = np.array([244, 239, 228], np.float32)
PINK = np.array([255, 72, 176], np.float32)
BLUE = np.array([0, 120, 191], np.float32)
HN = "/System/Library/Fonts/HelveticaNeue.ttc"
IOS = os.path.expanduser("~/Library/Fonts/IosevkaTermNerdFontMono-Regular.ttf")
IOS_B = os.path.expanduser("~/Library/Fonts/IosevkaTermNerdFontMono-Bold.ttf")
_fonts = {}


def font(size, path=IOS):
    key = (path, int(size))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(path, int(size), index=9 if path == HN else 0)
    return _fonts[key]


def black(size):
    return font(size, HN)


def clamp(x, a=0.0, b_=1.0):
    return max(a, min(b_, x))


def prog(t, t0, t1):
    return clamp((t - t0) / (t1 - t0))


def out_expo(x):
    return 1 if x >= 1 else 1 - 2 ** (-10 * x)


def in_out_cubic(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def out_back(x, s=1.6):
    x -= 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b_, x):
    return a + (b_ - a) * x


def q(t):
    """Tiempo cuantizado a 15 fps: animación a dos."""
    return math.floor(t * 15) / 15


def frozen_amt(t):
    def win(r):
        return clamp(prog(t, r[0], r[0] + 0.2)) * clamp(1 - prog(t, r[1], r[1] + 0.12))
    return max(win(FREEZE), win(IDLE_FREEZE))


def boil(t, k=0):
    """Desplazamiento de temblor por pasada; quieto mientras está congelado."""
    if frozen_amt(t) > 0.5:
        return 0, 0
    r = np.random.default_rng(int(q(t) * 15) * 7 + k)
    return int(r.integers(-2, 3)), int(r.integers(-2, 3))


# ---------- texturas fijas ----------
rng = np.random.default_rng(9)
paper_noise = rng.normal(0, 4, (H // 2, W // 2)).astype(np.float32)
fiber = np.repeat(np.repeat(paper_noise, 2, 0), 2, 1)[..., None]
PAPER_IMG = PAPER + fiber
ink_noise = rng.normal(0, 1, (H // 8, W // 8)).astype(np.float32)
INK_DENSITY = np.clip(0.88 + 0.06 * np.repeat(np.repeat(ink_noise, 8, 0), 8, 1), 0.75, 1.0)
GRAIN = [rng.normal(0, 5, (H // 2, W // 2)).astype(np.float32) for _ in range(4)]


def halftone(d, cx, cy, R, cell=22, x0=0, x1=W, y0=0, y1=H, scale=1.0):
    """Mancha de semitono radial."""
    if R < 1:
        return
    for y in range(y0 - y0 % cell, y1, cell):
        for x in range(x0 - x0 % cell, x1, cell):
            s = max(0.0, 1 - math.hypot(x - cx, y - cy) / R) * cell * 0.5 * scale
            if s > 1:
                d.ellipse([x - s, y - s, x + s, y + s], fill=255)


def flood(d, amt, cell=30):
    """Semitono parejo sobre toda la página: la congelación."""
    s = cell * 0.5 * 0.3 * amt
    if s < 1:
        return
    for y in range(cell // 2, H, cell):
        for x in range(cell // 2 + (cell // 2 if (y // cell) % 2 else 0), W, cell):
            d.ellipse([x - s, y - s, x + s, y + s], fill=255)


def wobbly_ellipse(d, box, t, seed, width=6, p=1.0):
    x0, y0, x1, y1 = box
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    r = np.random.default_rng(seed + int(q(t) * 15) * (frozen_amt(t) < 0.5))
    pts = []
    n = 60
    for k in range(int(n * p) + 1):
        a = -0.6 + 2 * math.pi * 1.08 * k / n
        j = 1 + 0.03 * r.standard_normal()
        pts.append((cx + rx * j * math.cos(a), cy + ry * j * math.sin(a)))
    if len(pts) > 1:
        d.line(pts, fill=255, width=width, joint="curve")


def text(d, xy, s, f, anchor="ls", fill=255):
    d.text(xy, s, font=f, fill=fill, anchor=anchor)


# ---------- escena 1 ----------
def hook(t, mb, mp):
    db, dp = ImageDraw.Draw(mb), ImageDraw.Draw(mp)
    tq = q(t)
    n = int(len(HOOK_CMD) * prog(tq, HOOK_TYPE[0], HOOK_TYPE[1]) + 0.999) if tq >= HOOK_TYPE[0] else 0
    if t < b(4):
        up = out_expo(prog(tq, b(2), b(2) + 0.3))
        f = font(lerp(84, 54, up), IOS_B)
        y = lerp(H / 2, 960, up)
        x0 = W / 2 - f.getlength("❯ " + HOOK_CMD) / 2 if up < 0.5 else 130
        x0 = lerp(W / 2 - font(84, IOS_B).getlength("❯ " + HOOK_CMD) / 2, 130, up)
        text(dp, (x0, y), "❯", f, "lm")
        text(db, (x0 + f.getlength("❯ "), y), HOOK_CMD[:n], f, "lm")
    if b(2) <= t < b(4):
        p = out_back(prog(tq, b(2), b(2) + 0.35))
        halftone(db, 1380, 500, lerp(200, 560, clamp(p)), x0=840)
        text(dp, (120, 840), "0.4s", black(lerp(700, 520, clamp(p))))
        text(db, (1820, 140), "KINDLING v0.20", black(60), "rs")
    if t >= b(4):
        lines = [("DOCKER COMPOSE", db), ("EN MICROVMS.", dp), ("EN TU MAC.", db)]
        for k, (s, d) in enumerate(lines):
            if tq >= b(4) + k * BEAT / 2:
                text(d, (120, 330 + k * 230), s, black(212))
        halftone(dp if tq < b(6) else db, 1500, 820, 420, x0=1000, y0=420)
        text(dp, (1820, 140), "KINDLING v0.20", black(60), "rs")
        text(db, (130, 990), "kling compose up -d", font(52, IOS_B))


# ---------- escena 2: la grabación impresa ----------
term_path, tmp_dir = sys.argv[1], sys.argv[2]
os.makedirs(tmp_dir, exist_ok=True)
if not os.path.exists(os.path.join(tmp_dir, "f0001.png")):
    subprocess.run(["ffmpeg", "-v", "error", "-i", term_path, os.path.join(tmp_dir, "f%04d.png")], check=True)
TERM_FRAMES = sorted(f for f in os.listdir(tmp_dir) if f.endswith(".png"))
_tc = {}


def term_masks(st):
    """Fotograma real separado en dos tintas: texto → azul, prompt naranja → rosa."""
    i = int(clamp(int(st * 25), 0, len(TERM_FRAMES) - 1))
    if i not in _tc:
        _tc.clear()
        a = np.asarray(Image.open(os.path.join(tmp_dir, TERM_FRAMES[i])).convert("RGB"), np.float32)
        lum = np.clip((a.mean(axis=2) - 25) / 170, 0, 1)
        warm = (a[..., 0] - a[..., 2]) > 90
        blue = np.where(warm, 0, lum)
        pink = np.where(warm, 1.0, 0)
        _tc[i] = (Image.fromarray((blue * 255).astype(np.uint8)), Image.fromarray((pink * 255).astype(np.uint8)))
    return _tc[i]


TERM_ORIGIN = (160, 90)
CAM = [
    (b(8), 960, 540, 1.0),
    (b(8) + 0.6, 960, 540, 1.0),
    (b(11), 640, 360, 1.45),
    (b(13), 700, 560, 1.7),
    (b(14), 700, 560, 1.82),
    (b(17), 720, 660, 1.65),
    (b(20), 680, 680, 1.85),
    (b(26), 680, 680, 1.85),
    (b(26) + 0.25, 620, 720, 2.2),
    (b(28), 900, 640, 1.2),
]


def cam_at(t):
    for (t0, *a), (t1, *c) in zip(CAM, CAM[1:]):
        if t <= t1:
            x = in_out_cubic(prog(t, t0, t1))
            return [lerp(p, q_, x) for p, q_ in zip(a, c)]
    return CAM[-1][1:]


def to_screen(cam, x, y):
    cx, cy, z = cam
    return (x - cx) * z + W / 2, (y - cy) * z + H / 2


def row_pos(i, c0, c1):
    y = TERM_ORIGIN[1] + row_y(i) + 15
    return TERM_ORIGIN[0] + 56 + c0 * 16.2, TERM_ORIGIN[0] + 56 + c1 * 16.2, y


def terminal(t, mb, mp):
    tq = q(t) if frozen_amt(t) < 0.5 else t
    st = src_time(t)
    cb, cp = Image.new("L", (W, H), 0), Image.new("L", (W, H), 0)
    tb, tp = term_masks(st)
    cb.paste(tb, TERM_ORIGIN)
    cp.paste(tp, TERM_ORIGIN)
    d = ImageDraw.Draw(cb)
    ox, oy = TERM_ORIGIN
    d.rectangle([ox - 30, oy - 30, ox + 1630, oy + 930], outline=255, width=5)
    text(ImageDraw.Draw(cp), (ox - 30, oy - 48), "grabación real · kling 0.20.1", font(30, IOS_B))
    cx, cy, z = cam_at(tq)
    if b(14) <= t < b(14) + 0.2:
        z *= 1.06
    cam = (cx, cy, z)
    box = (cx - W / z / 2, cy - H / z / 2, cx + W / z / 2, cy + H / z / 2)
    mb.paste(cb.transform((W, H), Image.EXTENT, box, Image.BILINEAR))
    mp.paste(cp.transform((W, H), Image.EXTENT, box, Image.BILINEAR))
    db, dp = ImageDraw.Draw(mb), ImageDraw.Draw(mp)

    flood(db, frozen_amt(t))
    if b(14) <= t < b(20):
        x0, x1, y = row_pos(8, 14, 18)
        sx0, sy = to_screen(cam, x0 - 14, y)
        sx1, _ = to_screen(cam, x1 + 14, y)
        wobbly_ellipse(dp, (sx0, sy - 34, sx1, sy + 34), t, 3, 6, prog(tq, b(14), b(14) + 0.3))
        if tq >= b(14) + 0.2:
            text(dp, (sx1 + 40, sy), "ARRANQUE EN CALIENTE", black(70), "lm")
    if FREEZE[0] <= t < FREEZE[1]:
        x0, x1, y = row_pos(12, 0, 22)
        sx1, sy = to_screen(cam, x1 + 10, y)
        if t >= FREEZE[0] + 0.15:
            text(db, (sx1 + 34, sy), "CONGELADO · 0 RAM", black(70), "lm")
    if t >= FREEZE[1]:
        x0, x1, y = row_pos(14, 0, 4)
        sx0, sy = to_screen(cam, x0 - 14, y)
        sx1, _ = to_screen(cam, x1 + 14, y)
        wobbly_ellipse(dp, (sx0, sy - 36, sx1, sy + 36), t, 5, 6, prog(tq, FREEZE[1], FREEZE[1] + 0.25))
        if tq >= FREEZE[1] + 0.15:
            text(dp, (sx1 + 40, sy), "DESPIERTA CON LA PRIMERA CONEXIÓN", black(62), "lm")


# ---------- escena 3: cifras ----------
STATS = [("8×", None, "MÁS LECTURA EN CARPETAS COMPARTIDAS", "21 → ~167 MiB/s · laboratorio, p50, n=5"),
         ("0.25 s", "2.24 s", "RESPONDE LA APP COMPOSE DE PRUEBA", "kling-hv, p50"),
         ("0.19 ms", "104 ms", "PAUSA p99 CON 4 vCPU", "Mac cargado · kling-hv sube la QoS de los vCPU")]
BLOBS = [(1500, 380, 480), (1560, 330, 420), (1660, 860, 340)]


def stats(t, mb, mp):
    db, dp = ImageDraw.Draw(mb), ImageDraw.Draw(mp)
    tq = q(t)
    k = min(2, int((t - b(28)) / (4 * BEAT)))
    t0 = b(28 + 4 * k)
    big, old, head, foot = STATS[k]
    cx, cy, R = BLOBS[k]
    halftone(db, cx, cy, R * out_back(prog(tq, t0, t0 + 0.3)), x0=1150)
    s = out_back(prog(tq, t0, t0 + 0.3))
    text(dp, (120, 640), big, black(lerp(560, 420, clamp(s))))
    if old and tq >= t0 + 0.13:
        f = black(120)
        text(db, (130, 230), "ANTES " + old, f)
        w = f.getlength("ANTES " + old)
        p = prog(tq, t0 + 0.27, t0 + 0.6)
        r = np.random.default_rng(k)
        pts = [(130 + w * p * j / 12, 190 + 8 * r.standard_normal()) for j in range(13)]
        dp.line(pts, fill=255, width=12, joint="curve")
    if tq >= t0 + 0.27:
        text(db, (126, 770), head, black(92))
    if tq >= t0 + 0.4:
        text(db, (130, 860), foot, font(38, IOS_B))
    text(dp, (1820, 1010), f"{k + 1}/3 · CHANGELOG v0.20", font(30, IOS_B), "rs")


# ---------- escena 4 y 5 ----------
def idle(t, mb, mp):
    db, dp = ImageDraw.Draw(mb), ImageDraw.Draw(mp)
    tq = q(t)
    text(db, (120, 420), "¿NADIE LO USA", black(220))
    text(db, (120, 640), "EN 10 MIN?", black(220))
    if t < IDLE_FREEZE[0]:
        n = int(10 * prog(tq, b(40), b(42)))
        text(dp, (1820, 640), f"{n} MIN", black(220), "rs")
    else:
        flood(db, frozen_amt(t))
        text(db, (120, 900), "SE CONGELA SOLO.", black(230))
        text(db, (130, 1000), "daemon.idle_freeze = 10m", font(38, IOS_B))


def end(t, mb, mp):
    db, dp = ImageDraw.Draw(mb), ImageDraw.Draw(mp)
    tq = q(t)
    t0 = b(END[0])
    halftone(db, 1500, 300, 520 * out_back(prog(tq, t0, t0 + 0.4)), x0=900, y0=0, y1=800)
    s = out_back(prog(tq, t0, t0 + 0.35))
    text(dp, (110, 600), "KINDLING", black(lerp(460, 380, clamp(s))))
    if tq >= t0 + 0.2:
        text(db, (120, 760), "v0.20", black(160))
    if tq >= t0 + 0.45:
        text(db, (130, 870), "microVMs que se congelan cuando nadie las usa", font(44, IOS_B))
    if tq >= t0 + 0.65:
        text(dp, (130, 950), "kling upgrade · github.com/juan52878911/kindling", font(44, IOS_B))
    for (x, y) in ((70, 70), (W - 70, 70), (70, H - 70), (W - 70, H - 70)):  # marcas de registro
        for d in (db, dp):
            d.ellipse([x - 18, y - 18, x + 18, y + 18], outline=255, width=3)
            d.line([x - 30, y, x + 30, y], fill=255, width=3)
            d.line([x, y - 30, x, y + 30], fill=255, width=3)


# ---------- impresión ----------
PRINTS = [b(2), FREEZE[1], b(END[0])]  # golpes de registro


def misregister(t):
    dx, dy = 7, -4
    for p in PRINTS:
        if p <= t < p + 0.4:
            k = 1 - out_expo(prog(t, p, p + 0.4))
            dx, dy = dx + 34 * k, dy - 20 * k
    return int(dx), int(dy)


def scene(t, mb, mp):
    if t < b(8):
        hook(t, mb, mp)
    elif t < b(28):
        terminal(t, mb, mp)
    elif t < b(40):
        stats(t, mb, mp)
    elif t < b(END[0]):
        idle(t, mb, mp)
    else:
        end(t, mb, mp)


def frame(t):
    mb, mp = Image.new("L", (W, H), 0), Image.new("L", (W, H), 0)
    scene(t, mb, mp)
    cold = frozen_amt(t)
    bx, by = boil(t, 1)
    px, py = boil(t, 2)
    dx, dy = misregister(t)
    B = np.roll(np.asarray(mb, np.float32) / 255, (by, bx), axis=(0, 1)) * INK_DENSITY
    P = np.roll(np.asarray(mp, np.float32) / 255, (dy + py, dx + px), axis=(0, 1)) * INK_DENSITY
    P *= 1 - cold  # congelado: la pasada rosa no imprime
    arr = PAPER_IMG * (1 - B[..., None] * (1 - BLUE / 255) * 0.95)
    arr = arr * (1 - P[..., None] * (1 - PINK / 255) * 0.95)
    gi = 0 if cold > 0.5 else int(q(t) * 15) % len(GRAIN)
    arr = arr + np.repeat(np.repeat(GRAIN[gi], 2, 0), 2, 1)[..., None]
    arr *= clamp((TOTAL - t) / 0.6)
    return np.clip(arr, 0, 255).astype(np.uint8)


def main():
    out = sys.argv[3]
    if len(sys.argv) > 4:
        for t in (float(x) for x in sys.argv[4].split(",")):
            Image.fromarray(frame(t)).save(f"{out}_{t:05.2f}.png")
        return
    n = int(TOTAL * FPS)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                          "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(frame(i / FPS).tobytes())
        if i % 120 == 0:
            print(f"{i}/{n}", flush=True)
    p.stdin.close()
    p.wait()


if __name__ == "__main__":
    main()
