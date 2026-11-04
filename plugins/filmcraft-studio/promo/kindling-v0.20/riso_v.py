"""Corte vertical (1080x1920) del promo de kindling v0.20 en Risografía.

Misma impresión que riso.py (pasadas azul y rosa multiplicadas, registro desplazado, animación a 15 fps,
congelado = una sola tinta), con guion nuevo: gancho, terminal real en un M4 (incluye `uname` → aarch64),
Apple Silicon nativo, cuatro capacidades, HOL Guard y cierre. Los textos de cartel se ajustan al ancho.

No usa el logo de Apple: es marca registrada y Apple no permite usarlo en promoción de terceros;
el chip dibujado y "Apple Silicon" como texto descriptivo dicen lo mismo.

Uso: python3 riso_v.py <term_v.mp4> <frames_dir_tmp> <salida.mp4 sin audio> [solo_t1,t2,...]
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from timeline_v import (BEAT, CHAR_W, END, FEATS, FPS, FREEZE, H, HOL, HOOK_CMD, HOOK_TYPE, IDLE_FREEZE, ROW_H,
                        SILICON, TEXT_X, TOTAL, W, b, row_y, src_time)

PAPER = np.array([244, 239, 228], np.float32)
PINK = np.array([255, 72, 176], np.float32)
BLUE = np.array([0, 120, 191], np.float32)
HN = "/System/Library/Fonts/HelveticaNeue.ttc"
IOS_B = os.path.expanduser("~/Library/Fonts/IosevkaTermNerdFontMono-Bold.ttf")
_fonts = {}
MARGIN = 60


def font(size, path=IOS_B):
    key = (path, int(size))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(path, int(size), index=9 if path == HN else 0)
    return _fonts[key]


def black(size):
    return font(size, HN)


def fit(s, width=W - 2 * MARGIN, cap=520):
    """Tamaño de Condensed Black para que `s` ocupe `width`."""
    return min(cap, int(100 * width / black(100).getlength(s)))


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
    return math.floor(t * 15) / 15


def frozen_amt(t):
    def win(r):
        return clamp(prog(t, r[0], r[0] + 0.2)) * clamp(1 - prog(t, r[1], r[1] + 0.12))
    return max(win(FREEZE), win(IDLE_FREEZE))


def boil(t, k=0):
    if frozen_amt(t) > 0.5:
        return 0, 0
    r = np.random.default_rng(int(q(t) * 15) * 7 + k)
    return int(r.integers(-2, 3)), int(r.integers(-2, 3))


rng = np.random.default_rng(9)
PAPER_IMG = PAPER + np.repeat(np.repeat(rng.normal(0, 4, (H // 2, W // 2)).astype(np.float32), 2, 0), 2, 1)[..., None]
INK_DENSITY = np.clip(0.88 + 0.06 * np.repeat(np.repeat(rng.normal(0, 1, (H // 8, W // 8)), 8, 0), 8, 1),
                      0.75, 1.0).astype(np.float32)
GRAIN = [rng.normal(0, 5, (H // 2, W // 2)).astype(np.float32) for _ in range(4)]


def halftone(d, cx, cy, R, cell=22, x0=0, x1=W, y0=0, y1=H):
    if R < 1:
        return
    for y in range(max(0, int(cy - R)) // cell * cell, min(y1, int(cy + R)), cell):
        if y < y0:
            continue
        for x in range(max(x0, int(cx - R)) // cell * cell, min(x1, int(cx + R)), cell):
            s = max(0.0, 1 - math.hypot(x - cx, y - cy) / R) * cell * 0.5
            if s > 1:
                d.ellipse([x - s, y - s, x + s, y + s], fill=255)


def flood(d, amt, cell=30):
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
    for k in range(int(60 * p) + 1):
        a = -0.6 + 2 * math.pi * 1.08 * k / 60
        j = 1 + 0.03 * r.standard_normal()
        pts.append((cx + rx * j * math.cos(a), cy + ry * j * math.sin(a)))
    if len(pts) > 1:
        d.line(pts, fill=255, width=width, joint="curve")


def text(d, xy, s, f, anchor="ls"):
    d.text(xy, s, font=f, fill=255, anchor=anchor)


def wrap(s, f, width=W - 2 * MARGIN):
    lines, cur = [], ""
    for w_ in s.split():
        cand = (cur + " " + w_).strip()
        if f.getlength(cand) > width and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = cand
    return lines + [cur]


def para(d, xy, s, f, spacing=1.3):
    x, y = xy
    for k, ln in enumerate(wrap(s, f)):
        d.text((x, y + k * f.size * spacing), ln, font=f, fill=255, anchor="ls")


# ---------- 1. gancho ----------
STACK = [("DOCKER", "b"), ("COMPOSE", "p"), ("EN MICROVMS.", "b"), ("EN TU MAC.", "p")]


def hook(t, mb, mp):
    db, dp = ImageDraw.Draw(mb), ImageDraw.Draw(mp)
    tq = q(t)
    n = int(len(HOOK_CMD) * prog(tq, HOOK_TYPE[0], HOOK_TYPE[1]) + 0.999) if tq >= HOOK_TYPE[0] else 0
    if t < b(4):
        up = out_expo(prog(tq, b(2), b(2) + 0.3))
        f = font(lerp(58, 46, up))
        x0 = lerp((W - font(58).getlength("❯ " + HOOK_CMD)) / 2, MARGIN, up)
        y = lerp(H / 2, 1500, up)
        text(dp, (x0, y), "❯", f, "lm")
        text(db, (x0 + f.getlength("❯ "), y), HOOK_CMD[:n], f, "lm")
    if b(2) <= t < b(4):
        p = out_back(prog(tq, b(2), b(2) + 0.35))
        halftone(db, 820, 620, lerp(150, 520, clamp(p)))
        text(dp, (W / 2, 1180), "0.5s", black(lerp(620, 500, clamp(p))), "ms")
        text(db, (W - MARGIN, 150), "KINDLING v0.20", black(64), "rs")
    if t >= b(4):
        y = 520
        for k, (s, ink) in enumerate(STACK):
            size = fit(s)
            y += size * 0.78
            if tq >= b(4) + k * BEAT / 2:
                text(db if ink == "b" else dp, (MARGIN, y), s, black(size))
            y += 40
        halftone(dp if tq < b(6) else db, 900, 1650, 420, y0=1250)
        text(dp, (W - MARGIN, 150), "KINDLING v0.20", black(64), "rs")
        text(db, (MARGIN, 1760), "kling compose up -d", font(46))


# ---------- 2. terminal real ----------
term_path, tmp_dir = sys.argv[1], sys.argv[2]
os.makedirs(tmp_dir, exist_ok=True)
if not os.path.exists(os.path.join(tmp_dir, "f0001.png")):
    subprocess.run(["ffmpeg", "-v", "error", "-i", term_path, os.path.join(tmp_dir, "f%04d.png")], check=True)
TERM_FRAMES = sorted(f for f in os.listdir(tmp_dir) if f.endswith(".png"))
_tc = {}


def term_masks(st):
    i = int(clamp(int(st * 25), 0, len(TERM_FRAMES) - 1))
    if i not in _tc:
        _tc.clear()
        a = np.asarray(Image.open(os.path.join(tmp_dir, TERM_FRAMES[i])).convert("RGB"), np.float32)
        lum = np.clip((a.mean(axis=2) - 25) / 170, 0, 1)
        warm = (a[..., 0] - a[..., 2]) > 90
        _tc[i] = (Image.fromarray((np.where(warm, 0, lum) * 255).astype(np.uint8)),
                  Image.fromarray((warm * 255).astype(np.uint8)))
    return _tc[i]


TO = (40, 600)   # la ventana de 1000x1000 en el lienzo
FOCUS_Y = 760    # la fila enfocada cae aquí en pantalla; abajo queda la franja de rótulos


def ry(i):
    return TO[1] + row_y(i) + 16


def cam_key(t, cx, row, z):
    """Enfoca la fila `row` a la altura FOCUS_Y con el margen izquierdo del texto siempre visible."""
    cx = min(cx, TO[0] + TEXT_X - 34 + W / (2 * z))
    return (t, cx, ry(row) + (H / 2 - FOCUS_Y) / z, z)


CAM = [
    (b(8), 540, 1100, 1.0),
    (b(8) + 0.6, 540, 1100, 1.0),
    cam_key(b(11), 460, 4, 1.35),
    cam_key(b(13.4), 420, 8, 1.6),
    cam_key(b(14), 420, 8, 1.7),
    cam_key(b(17.4), 440, 13, 1.6),
    cam_key(b(18), 440, 13, 1.7),
    cam_key(b(21.4), 420, 15, 1.6),
    cam_key(b(22), 420, 15, 1.7),
    cam_key(b(28), 420, 15, 1.7),     # congelado: la cámara no se mueve
    cam_key(b(28) + 0.25, 360, 17, 1.95),
    (b(30), 540, 1150, 1.05),
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


def col_x(c):
    return TO[0] + TEXT_X + c * CHAR_W


CAPTIONS = [  # (desde, hasta, fila, col0, col1, texto, tinta)
    (b(14), b(17.6), 8, 14, 18, "ARRANQUE EN CALIENTE", "p"),
    (b(18), b(21.6), 13, 6, 13, "NATIVO EN APPLE SILICON", "p"),
    (FREEZE[0], FREEZE[1], 15, 16, 22, "CONGELADO · 0 RAM", "b"),
    (FREEZE[1], b(30), 17, 0, 4, "DESPIERTA SOLO", "p"),
]


def terminal(t, mb, mp):
    tq = q(t) if frozen_amt(t) < 0.5 else t
    cb, cp = Image.new("L", (W, 2200), 0), Image.new("L", (W, 2200), 0)
    tb, tp = term_masks(src_time(t))
    cb.paste(tb, TO)
    cp.paste(tp, TO)
    d = ImageDraw.Draw(cb)
    d.rectangle([TO[0] - 16, TO[1] - 16, TO[0] + 1016, TO[1] + 1016], outline=255, width=5)
    text(ImageDraw.Draw(cp), (TO[0] - 16, TO[1] - 34), "grabación real · Mac M4 · kling 0.20.1", font(30))
    cx, cy, z = cam_at(tq)
    cam = (cx, cy, z)
    box = (cx - W / z / 2, cy - H / z / 2, cx + W / z / 2, cy + H / z / 2)
    mb.paste(cb.transform((W, H), Image.EXTENT, box, Image.BILINEAR))
    mp.paste(cp.transform((W, H), Image.EXTENT, box, Image.BILINEAR))
    db, dp = ImageDraw.Draw(mb), ImageDraw.Draw(mp)
    flood(db, frozen_amt(t))
    # franja de rótulos: papel limpio abajo
    for m in (mb, mp):
        ImageDraw.Draw(m).rectangle([0, 1430, W, H], fill=0)
    for t0, t1, row, c0, c1, label, ink in CAPTIONS:
        if not (t0 <= t < t1):
            continue
        sx0, sy = to_screen(cam, col_x(c0) - 10, ry(row))
        sx1, _ = to_screen(cam, col_x(c1) + 10, ry(row))
        if ink == "p":
            wobbly_ellipse(dp, (sx0, sy - 32 * z / 1.7, sx1, sy + 32 * z / 1.7), t, int(t0), 6,
                           prog(tq, t0, t0 + 0.3))
        if tq >= t0 + 0.13:
            size = fit(label, cap=150)
            text(dp if ink == "p" else db, (MARGIN, 1640), label, black(size))
    if b(18) <= t < b(22):
        text(db, (MARGIN, 1760), "uname -m → aarch64 · sin emulación", font(40))


# ---------- 3. Apple Silicon ----------
def chip(db, dp, cx, cy, s, t):
    db.rectangle([cx - s, cy - s, cx + s, cy + s], outline=255, width=10)
    pins = 7
    for k in range(pins):
        o = -s + (k + 0.5) * 2 * s / pins
        for (x0, y0, x1, y1) in ((cx + o, cy - s - 40, cx + o, cy - s), (cx + o, cy + s, cx + o, cy + s + 40),
                                 (cx - s - 40, cy + o, cx - s, cy + o), (cx + s, cy + o, cx + s + 40, cy + o)):
            db.line([x0, y0, x1, y1], fill=255, width=12)
    halftone(dp, cx, cy, s * 0.95, cell=18, x0=int(cx - s + 14), x1=int(cx + s - 14), y0=int(cy - s + 14),
             y1=int(cy + s - 14))
    text(db, (cx, cy - 10), "APPLE", black(110), "ms")
    text(db, (cx, cy + 100), "SILICON", black(110), "ms")


def silicon(t, mb, mp):
    db, dp = ImageDraw.Draw(mb), ImageDraw.Draw(mp)
    tq = q(t)
    t0 = b(SILICON[0])
    s = out_back(prog(tq, t0, t0 + 0.35))
    chip(db, dp, W / 2, 560, 260 * clamp(s, 0.01, 1.2), t)
    text(db, (MARGIN, 1000), "NATIVO.", black(fit("NATIVO.", cap=220)))
    if tq >= b(32):
        text(dp, (MARGIN, 1250), "36 ms", black(230))
        text(db, (MARGIN + black(230).getlength("36 ms") + 30, 1250), "despertar", font(46))
    if tq >= b(33):
        text(dp, (MARGIN, 1480), "16 MiB", black(230))
        text(db, (MARGIN + black(230).getlength("16 MiB") + 30, 1480), "por copia", font(46))
    if tq >= b(34):
        para(db, (MARGIN, 1620), "kling-hv, su propio VMM sobre Hypervisor.framework. Mismo orden de "
                                 "magnitud que Linux x86 con Firecracker.", font(40))
        text(db, (MARGIN, 1860), "p50 · M4 · docs/backend-hv.md", font(28))


# ---------- 4. capacidades ----------
CARDS = [
    ("50 COPIAS", "EN 784 MiB", "Snapshots dorados: arrancas una vez y cada copia comparte la memoria.",
     "kling run -from golden", (850, 520)),
    ("1 BASE DE DATOS", "POR RAMA DE GIT", "Postgres, MySQL, Redis o SQLite desechables, copiados al instante.",
     "kling db up pg", (220, 560)),
    ("MCP", "BAJO DEMANDA", "Cualquier servidor MCP de npm o PyPI, congelado hasta que tu agente lo llama.",
     "kling mcp import", (820, 640)),
    ("10 MIN SIN USO", "SE CONGELA SOLO", "La siguiente conexión lo despierta. Mientras, 0 RAM.",
     "daemon.idle_freeze = 10m", (260, 560)),
]


def feats(t, mb, mp):
    db, dp = ImageDraw.Draw(mb), ImageDraw.Draw(mp)
    tq = q(t)
    k = min(3, int((t - b(FEATS[0])) / (3 * BEAT)))
    t0 = b(FEATS[0] + 3 * k)
    big, sub, desc, cmd, (hx, hy) = CARDS[k]
    halftone(db, hx, hy, 380 * out_back(prog(tq, t0, t0 + 0.3)))
    text(db, (MARGIN, 150), f"{k + 1}/4 · kindling v0.20", font(34))
    s = out_back(prog(tq, t0, t0 + 0.3))
    size = fit(big, cap=420)
    text(db if k == 3 else dp, (MARGIN, 980), big, black(size * lerp(1.15, 1, clamp(s))))
    if tq >= t0 + 0.13:
        text(db, (MARGIN, 1160), sub, black(fit(sub, cap=150)))
    if tq >= t0 + 0.4:
        para(db, (MARGIN, 1330), desc, font(46))
    if tq >= t0 + 0.6:
        text(dp, (MARGIN, 1720), "❯ " + cmd, font(46))
    if k == 3:
        flood(db, frozen_amt(t))


# ---------- 5. HOL Guard ----------
def shield(d, cx, cy, s, p):
    pts = [(cx - s, cy - s), (cx, cy - s * 1.25), (cx + s, cy - s), (cx + s, cy + s * 0.1),
           (cx, cy + s * 1.3), (cx - s, cy + s * 0.1), (cx - s, cy - s)]
    n = max(2, int(len(pts) * p))
    d.line(pts[:n], fill=255, width=12, joint="curve")


def hol(t, mb, mp):
    db, dp = ImageDraw.Draw(mb), ImageDraw.Draw(mp)
    tq = q(t)
    t0 = b(HOL[0])
    shield(db, W / 2, 460, 230, prog(tq, t0, t0 + 0.4))
    if tq >= t0 + 0.27:
        p = prog(tq, t0 + 0.27, t0 + 0.5)
        pts = [(W / 2 - 110, 470), (W / 2 - 25, 560), (W / 2 + 120, 360)]
        dp.line(pts[:2] if p < 0.5 else pts, fill=255, width=34, joint="curve")
    text(db, (MARGIN, 960), "AHORA EN", black(110))
    if tq >= t0 + 0.13:
        text(dp, (MARGIN, 1220), "HOL GUARD", black(fit("HOL GUARD")))
    if tq >= t0 + 0.45:
        para(db, (MARGIN, 1360), "El antivirus open source para agentes de IA revisa cada comando kling "
                                 "antes de que se ejecute.", font(46))
    if tq >= t0 + 0.7:
        text(dp, (MARGIN, 1720), "extensión command.kindling", font(40))


# ---------- 6. cierre ----------
def end(t, mb, mp):
    db, dp = ImageDraw.Draw(mb), ImageDraw.Draw(mp)
    tq = q(t)
    t0 = b(END[0])
    halftone(db, 800, 520, 480 * out_back(prog(tq, t0, t0 + 0.4)))
    s = out_back(prog(tq, t0, t0 + 0.35))
    text(dp, (MARGIN, 1000), "KINDLING", black(fit("KINDLING") * lerp(1.12, 1, clamp(s))))
    if tq >= t0 + 0.2:
        text(db, (MARGIN, 1190), "v0.20", black(190))
    if tq >= t0 + 0.45:
        para(db, (MARGIN, 1330), "microVMs que se congelan cuando nadie las usa. Linux y Apple Silicon.",
             font(44))
    if tq >= t0 + 0.65:
        text(dp, (MARGIN, 1600), "brew · kling upgrade", font(46))
        text(dp, (MARGIN, 1680), "github.com/juan52878911/kindling", font(42))
    for (x, y) in ((70, 70), (W - 70, 70), (70, H - 70), (W - 70, H - 70)):
        for d in (db, dp):
            d.ellipse([x - 18, y - 18, x + 18, y + 18], outline=255, width=3)
            d.line([x - 30, y, x + 30, y], fill=255, width=3)
            d.line([x, y - 30, x, y + 30], fill=255, width=3)


PRINTS = [b(2), FREEZE[1], b(SILICON[0]), b(HOL[0]), b(END[0])]


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
    elif t < b(SILICON[0]):
        terminal(t, mb, mp)
    elif t < b(FEATS[0]):
        silicon(t, mb, mp)
    elif t < b(HOL[0]):
        feats(t, mb, mp)
    elif t < b(END[0]):
        hol(t, mb, mp)
    else:
        end(t, mb, mp)


def frame(t):
    mb, mp = Image.new("L", (W, H), 0), Image.new("L", (W, H), 0)
    scene(t, mb, mp)
    cold = frozen_amt(t)
    bx, by = boil(t, 1)
    px, py = boil(t, 2)
    dx, dy = misregister(t)
    B_ = np.roll(np.asarray(mb, np.float32) / 255, (by, bx), axis=(0, 1)) * INK_DENSITY
    P = np.roll(np.asarray(mp, np.float32) / 255, (dy + py, dx + px), axis=(0, 1)) * INK_DENSITY
    P *= 1 - cold
    arr = PAPER_IMG * (1 - B_[..., None] * (1 - BLUE / 255) * 0.95)
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
        if i % 150 == 0:
            print(f"{i}/{n}", flush=True)
    p.stdin.close()
    p.wait()


if __name__ == "__main__":
    main()
