"""Promo de kindling v0.20 en estilo Blueprint: un plano técnico que se dibuja solo.

Kit: azul plano #0A1F3D con rejilla, trazo blanco, anotaciones cian, Helvetica Neue Condensed Black
para titulares y SF Mono para cotas. Lo congelado se raya como un corte de sección y el grano se para;
lo que corre lleva un único punto de brasa #FF5A1F (la firma que comparte con el primer video).

Uso: python3 blueprint.py <term.mp4> <frames_dir_tmp> <salida.mp4 sin audio> [solo_t1,t2,...]
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from bp_events import STAT_STARTS
from timeline import BEAT, END, FPS, FREEZE, H, IDLE_FREEZE, TOTAL, W, b, row_y, src_time

NAVY = (10, 31, 61)
WHITE = (225, 240, 255)
CYAN = (110, 200, 255)
ICE = (180, 225, 255)
HATCH = (70, 120, 175)
EMBER = (255, 90, 31)

HN = "/System/Library/Fonts/HelveticaNeue.ttc"
MONO = "/System/Library/Fonts/SFNSMono.ttf"
_fonts = {}


def font(size, path=MONO, index=0):
    key = (path, int(size), index)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(path, int(size), index=index)
    return _fonts[key]


def black(size):
    return font(size, HN, 9)  # Condensed Black


# ---------- easing ----------
def clamp(x, a=0.0, b_=1.0):
    return max(a, min(b_, x))


def prog(t, t0, t1):
    return clamp((t - t0) / (t1 - t0))


def out_expo(x):
    return 1 if x >= 1 else 1 - 2 ** (-10 * x)


def in_out_cubic(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def out_back(x, s=1.4):
    x -= 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b_, x):
    return a + (b_ - a) * x


def mix(c1, c2, x):
    return tuple(int(lerp(p, q, x)) for p, q in zip(c1, c2))


# ---------- primitivas de plano ----------
def grid_image():
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    for x in range(0, W, 40):
        d.line([x, 0, x, H], fill=(38, 76, 128) if x % 200 == 0 else (22, 50, 88))
    for y in range(0, H, 40):
        d.line([0, y, W, y], fill=(38, 76, 128) if y % 200 == 0 else (22, 50, 88))
    return im


GRID = grid_image()


def base(t):
    a = out_expo(prog(t, 0, 0.35))
    return Image.blend(Image.new("RGB", (W, H), NAVY), GRID, a) if a < 1 else GRID.copy()


def line(d, p0, p1, p, fill=WHITE, width=2):
    if p <= 0:
        return
    d.line([p0[0], p0[1], lerp(p0[0], p1[0], p), lerp(p0[1], p1[1], p)], fill=fill, width=width)


def rect(d, box, p, fill=WHITE, width=2):
    """Traza el perímetro en sentido horario desde la esquina superior izquierda."""
    x0, y0, x1, y1 = box
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    lens = [abs(x1 - x0), abs(y1 - y0)] * 2
    left = p * sum(lens)
    for (a, c), ln in zip(zip(pts, pts[1:]), lens):
        if left <= 0:
            break
        line(d, a, c, clamp(left / ln), fill, width)
        left -= ln


def typed(d, xy, s, p, f, fill, anchor="ls"):
    n = int(len(s) * clamp(p) + 0.999) if p > 0 else 0
    if n:
        d.text(xy, s[:n], font=f, fill=fill, anchor=anchor)


def hatch(im, box, p, reverse=False, color=HATCH):
    """Rayado de sección a 45°, barrido de izquierda a derecha (o retirándose)."""
    if p <= 0:
        return
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = x1 - x0, y1 - y0
    layer = Image.new("RGB", (w, h), (0, 0, 0))
    mask = Image.new("L", (w, h), 0)
    dl, dm = ImageDraw.Draw(layer), ImageDraw.Draw(mask)
    edge = p * (w + h)
    for k in range(-h, w, 22):
        on = (k + h) > edge if reverse else (k + h) < edge
        if on:
            dl.line([k, h, k + h, 0], fill=color, width=2)
            dm.line([k, h, k + h, 0], fill=255, width=2)
    im.paste(layer, (x0, y0), mask)


def dimension(d, x0, x1, y, p, label, f, fill=WHITE, bg=NAVY, label_scale=1.0):
    """Cota: la línea crece desde el centro, con remates y etiqueta en un hueco."""
    cx = (x0 + x1) / 2
    e = out_expo(p)
    a, c = lerp(cx, x0, e), lerp(cx, x1, e)
    d.line([a, y, c, y], fill=fill, width=2)
    if e > 0.95:
        for x in (x0, x1):
            d.line([x, y - 20, x, y + 20], fill=fill, width=2)
    if p > 0.3 and label:
        tw = f.getlength(label) * label_scale
        d.rectangle([cx - tw / 2 - 18, y - f.size * 0.45, cx + tw / 2 + 18, y + f.size * 0.45], fill=bg)
        d.text((cx, y), label, font=f, fill=fill, anchor="mm")


def ember_dot(d, xy, t, r=9):
    pulse = 1 + 0.35 * (0.5 + 0.5 * math.sin(t * 2 * math.pi / BEAT))
    x, y = xy
    rr = r * pulse
    d.ellipse([x - rr * 1.9, y - rr * 1.9, x + rr * 1.9, y + rr * 1.9], outline=mix(NAVY, EMBER, 0.5), width=2)
    d.ellipse([x - r, y - r, x + r, y + r], fill=EMBER)


def title_block(d, box, p, rows, t):
    x0, y0, x1, y1 = box
    rect(d, box, p, WHITE, 2)
    if p >= 1:
        hh = (y1 - y0) / len(rows)
        for k, (s, f, c) in enumerate(rows):
            if k:
                line(d, (x0, y0 + hh * k), (x1, y0 + hh * k), prog(t, 0, 1), WHITE, 1)
            d.text((x0 + 22, y0 + hh * k + hh / 2), s, font=f, fill=c, anchor="lm")


# ---------- escena 1: el plano se dibuja ----------
HOST = (120, 160, 1300, 860)
COMPOSE = (180, 280, 520, 520)
VM = (780, 280, 1240, 720)
YAML = ["services:", "  cache:", "    image: redis:7-alpine", "    ports: [\"6379\"]"]


def diagram(d, im, t, frozen_p=0.0, headline=True):
    rect(d, HOST, in_out_cubic(prog(t, 0.0, 0.9)), WHITE, 3)
    typed(d, (140, 200), "HOST · macOS · kling daemon", prog(t, 0.2, 0.7), font(30), WHITE)
    rect(d, COMPOSE, in_out_cubic(prog(t, 0.05, 0.45)), CYAN, 2)
    typed(d, (200, 320), "compose.yml", prog(t, 0.1, 0.3), font(26), CYAN)
    for k, s in enumerate(YAML):
        typed(d, (200, 370 + 34 * k), s, prog(t, 0.2 + 0.08 * k, 0.4 + 0.08 * k), font(22), WHITE)
    pa = in_out_cubic(prog(t, 0.3, 0.7))
    line(d, (520, 400), (760, 400), pa, WHITE, 2)
    if pa >= 1:
        d.polygon([(760, 400), (740, 390), (740, 410)], fill=WHITE)
    typed(d, (540, 385), "compose up -d", prog(t, 0.35, 0.7), font(22), CYAN)
    hatch(im, VM, frozen_p)
    rect(d, VM, in_out_cubic(prog(t, 0.5, 0.9)), mix(WHITE, ICE, frozen_p), 4)
    typed(d, (800, 320), "microVM · Firecracker", prog(t, 0.6, 0.9), font(26), CYAN)
    typed(d, (800, 360), "cache  redis:7-alpine", prog(t, 0.65, 0.95), font(30), WHITE)
    typed(d, (800, 690), "127.0.0.1:63224 → 6379", prog(t, b(2), b(2) + 0.3), font(26), CYAN)
    if t >= b(2):
        p = out_back(prog(t, b(2), b(2) + 0.3))
        if frozen_p > 0:
            d.rectangle([VM[0] + 40, 470, VM[2] - 40, 560], fill=NAVY)
            d.text((1010, 515), "FROZEN · 0 RAM", font=font(44), fill=ICE, anchor="mm")
        else:
            d.text((1030, 515), "RUNNING", font=font(lerp(60, 44, clamp(p))), fill=WHITE, anchor="mm")
            ember_dot(d, (900, 515), t)
        dimension(d, 520, 1240, 800, prog(t, b(2), b(2) + 0.3), "0.4 s", black(lerp(150, 96, clamp(p))))
    if headline and t >= b(4):
        for k, (s, c) in enumerate([("COMPOSE", WHITE), ("EN MICROVMS.", CYAN)]):
            p = out_expo(prog(t, b(4) + k * BEAT / 2, b(4) + k * BEAT / 2 + 0.45))
            if p > 0:
                mask = Image.new("L", (560, 110), 0)
                ImageDraw.Draw(mask).text((0, 100 + (1 - p) * 110), s, font=black(90), fill=255, anchor="ls")
                im.paste(Image.new("RGB", mask.size, c), (1340, 230 + k * 105), mask)
        typed(d, (1345, 480), "aislamiento de kernel, en tu Mac", prog(t, b(5), b(6)), font(26), CYAN)
        title_block(d, (1440, 900, 1880, 1040), in_out_cubic(prog(t, b(5), b(6))),
                    [("KINDLING v0.20", font(28), WHITE), ("PLANO 01 · compose → microVM", font(22), CYAN),
                     ("medido en un Mac M4", font(22), CYAN)], t - b(6))


def hook(t):
    im = base(t)
    diagram(ImageDraw.Draw(im), im, t)
    return im


# ---------- escena 2: detalle A, la grabación real ----------
TERM_ORIGIN = (160, 120)
term_path, tmp_dir = sys.argv[1], sys.argv[2]
os.makedirs(tmp_dir, exist_ok=True)
if not os.path.exists(os.path.join(tmp_dir, "f0001.png")):
    subprocess.run(["ffmpeg", "-v", "error", "-i", term_path, os.path.join(tmp_dir, "f%04d.png")], check=True)
TERM_FRAMES = sorted(f for f in os.listdir(tmp_dir) if f.endswith(".png"))
_tcache = {}


def term_frame(st):
    """Fotograma real recoloreado a plano: texto blanco sobre azul, el prompt sigue en brasa."""
    i = int(clamp(int(st * 25), 0, len(TERM_FRAMES) - 1))
    if i not in _tcache:
        _tcache.clear()
        a = np.asarray(Image.open(os.path.join(tmp_dir, TERM_FRAMES[i])).convert("RGB"), np.float32)
        lum = np.clip((a.mean(axis=2, keepdims=True) - 22) / 190, 0, 1)
        ember = ((a[..., 0] - a[..., 2]) > 90)[..., None]
        out = np.array(NAVY, np.float32) * (1 - lum) + np.array(WHITE, np.float32) * lum
        out = np.where(ember, np.array(EMBER, np.float32), out)
        _tcache[i] = Image.fromarray(out.astype(np.uint8))
    return _tcache[i]


CAM = [
    (b(8), 960, 570, 1.0),
    (b(8) + 0.6, 960, 570, 1.0),
    (b(11), 640, 390, 1.45),
    (b(13), 700, 590, 1.7),
    (b(14), 700, 590, 1.82),
    (b(17), 720, 690, 1.65),
    (b(20), 680, 710, 1.85),
    (b(26), 680, 710, 1.85),   # congelado: la cámara no se mueve
    (b(26) + 0.25, 620, 750, 2.2),
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


def row_pos(i, col0, col1):
    cw = 16.2
    y = TERM_ORIGIN[1] + row_y(i) + 15
    return TERM_ORIGIN[0] + 56 + col0 * cw, TERM_ORIGIN[0] + 56 + col1 * cw, y


def callout(d, cam, anchor_xy, label, color, p, num):
    """Anotación de plano: círculo numerado, línea guía y texto."""
    if p <= 0:
        return
    ax, ay = to_screen(cam, *anchor_xy)
    ex, ey = ax + 80, ay
    line(d, (ax, ay), (ex, ey), out_expo(p), color, 2)
    if p > 0.4:
        d.ellipse([ex - 22, ey - 22, ex + 22, ey + 22], outline=color, width=2)
        d.text((ex, ey + 1), str(num), font=font(26), fill=color, anchor="mm")
        typed(d, (ex + 36, ey + 2), label, prog(p, 0.4, 1), black(58), color, anchor="lm")


def terminal(t):
    canvas = GRID.copy()
    canvas.paste(term_frame(src_time(t)), TERM_ORIGIN)
    d = ImageDraw.Draw(canvas)
    ox, oy = TERM_ORIGIN
    rect(d, (ox - 2, oy - 2, ox + 1601, oy + 901), in_out_cubic(prog(t, b(8), b(8) + 0.5)), WHITE, 2)
    for (x, y) in ((ox - 2, oy - 2), (ox + 1601, oy - 2), (ox - 2, oy + 901), (ox + 1601, oy + 901)):
        d.line([x - 14, y, x + 14, y], fill=CYAN, width=2)
        d.line([x, y - 14, x, y + 14], fill=CYAN, width=2)
    d.text((ox, oy - 30), "DETALLE A · grabación real · kling 0.20.1", font=font(24), fill=CYAN, anchor="ls")
    d.text((ox + 1600, oy - 30), "escala 1:1", font=font(24), fill=CYAN, anchor="rs")

    cx, cy, z = cam_at(t)
    if b(14) <= t < b(14) + 0.2:
        z *= 1 + 0.06 * math.sin(math.pi * prog(t, b(14), b(14) + 0.2))
    cam = (cx, cy, z)
    box = (cx - W / z / 2, cy - H / z / 2, cx + W / z / 2, cy + H / z / 2)
    im = canvas.transform((W, H), Image.EXTENT, box, Image.BICUBIC)
    d = ImageDraw.Draw(im)

    # congelado: rayado de sección sobre todo el detalle
    fp = prog(t, FREEZE[0], FREEZE[0] + 0.3)
    out = prog(t, FREEZE[1], FREEZE[1] + 0.2)
    if fp > 0 and out < 1:
        x0, y0 = to_screen(cam, ox, oy)
        x1, y1 = to_screen(cam, ox + 1600, oy + 900)
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        if out > 0:
            hatch(im, (x0, y0, x1, y1), out, reverse=True, color=(40, 78, 122))
        else:
            hatch(im, (x0, y0, x1, y1), fp, color=(40, 78, 122))
        d = ImageDraw.Draw(im)

    # 1 · arranque
    if t >= b(14):
        x0, x1, y = row_pos(8, 14, 18)
        a = clamp(1 - prog(t, b(19), b(20)))
        if a > 0:
            p = out_expo(prog(t, b(14), b(14) + 0.3))
            sx0, sy = to_screen(cam, x0 - 6, y)
            sx1, _ = to_screen(cam, x1 + 6, y)
            col = mix(NAVY, WHITE, a)
            dimension(d, sx0, sx1, sy + 34 * z / 1.8, p, None, font(20), col)
            callout(d, cam, (x1 + 14, y), "ARRANQUE EN CALIENTE", mix(NAVY, CYAN, a), prog(t, b(14), b(15)), 1)
    # 2 · congelado
    if FREEZE[0] <= t < FREEZE[1] + 0.2:
        x0, x1, y = row_pos(12, 0, 22)
        a = clamp(1 - prog(t, FREEZE[1], FREEZE[1] + 0.2))
        callout(d, cam, (x1 + 10, y), "FROZEN · 0 RAM", mix(NAVY, ICE, a), prog(t, FREEZE[0], FREEZE[0] + 0.5), 2)
    # 3 · despierta
    if t >= FREEZE[1]:
        x0, x1, y = row_pos(14, 0, 4)
        a = clamp(1 - prog(t, b(27.4), b(28)))
        sx, sy = to_screen(cam, x1 + 30, y)
        if a > 0:
            ember_dot(d, (sx, sy), t, 8)
        callout(d, cam, (x1 + 50, y), "THAW · PRIMERA CONEXIÓN", mix(NAVY, CYAN, a),
                prog(t, FREEZE[1], FREEZE[1] + 0.5), 3)
    return im


# ---------- escena 3: medidas ----------
STATS = [
    ("8×", "MÁS LECTURA EN CARPETAS COMPARTIDAS", "lectura de una carpeta compartida · laboratorio, p50, n=5",
     ("antes", 21, "21 MiB/s"), ("v0.20", 167, "~167 MiB/s"), 167),
    ("9×", "MÁS RÁPIDA AL RESPONDER", "app compose de prueba en kling-hv · p50",
     ("antes", 2.24, "2.24 s"), ("v0.20", 0.25, "0.25 s"), 2.24),
    ("547×", "MENOS PAUSA CON 4 vCPU", "khv_pause p99 · Mac cargado · kling-hv sube la QoS de los vCPU",
     ("antes", 104, "104 ms"), ("v0.20", 0.19, "0.19 ms"), 104),
]


def stats(t):
    im = GRID.copy()
    d = ImageDraw.Draw(im)
    k = min(2, int((t - b(28)) / (4 * BEAT)))
    t0 = STAT_STARTS[k]
    big, head, foot, before, after, vmax = STATS[k]
    d.text((120, 90), f"PLANO 02 · MEDIDAS · {k + 1}/3", font=font(26), fill=CYAN, anchor="ls")
    d.text((1800, 90), "fuente: CHANGELOG v0.20", font=font(26), fill=CYAN, anchor="rs")
    line(d, (120, 110), (1800, 110), 1, (38, 76, 128), 2)
    p = out_expo(prog(t, t0, t0 + 0.4))
    # titular que sube desde detrás de la línea superior (máscara recortada a la franja)
    mask = Image.new("L", (1700, 300), 0)
    md = ImageDraw.Draw(mask)
    wbig = black(300).getlength(big)
    md.text((0, 280 + (1 - p) * 300), big, font=black(300), fill=255, anchor="ls")
    im.paste(Image.new("RGB", mask.size, WHITE), (120, 140), mask)
    mask = Image.new("L", (1700, 300), 0)
    ImageDraw.Draw(mask).text((wbig + 40, 270 + (1 - p) * 300), head, font=black(66), fill=255, anchor="ls")
    im.paste(Image.new("RGB", mask.size, CYAN), (120, 140), mask)
    d = ImageDraw.Draw(im)
    # barras como cotas: escala lineal real
    x0, span = 300, 1150
    for j, (name, v, lab) in enumerate((before, after)):
        y = 600 + j * 170
        pb = in_out_cubic(prog(t, t0 + 0.1 + j * 0.15, t0 + 0.7 + j * 0.15))
        d.text((x0 - 30, y), name, font=font(34), fill=CYAN if j else WHITE, anchor="rm")
        w = max(4, span * v / vmax)
        if j == 0:
            hatch(im, (x0, y - 40, x0 + w * pb, y + 40), 1)
            d = ImageDraw.Draw(im)
        rect(d, (x0, y - 40, x0 + max(1, w * pb), y + 40), 1 if pb > 0 else 0, WHITE if j == 0 else CYAN, 3)
        if pb >= 1:
            tx = x0 + w + 30
            d.text((tx, y), lab, font=black(66), fill=WHITE if j == 0 else CYAN, anchor="lm")
            if w < 20:
                d.text((tx, y + 62), "← casi no se ve a esta escala", font=font(26), fill=CYAN, anchor="lm")
    # regla
    for k2 in range(11):
        x = x0 + span * k2 / 10
        d.line([x, 880, x, 896 if k2 % 5 else 908], fill=WHITE, width=2)
    d.line([x0, 880, x0 + span, 880], fill=WHITE, width=2)
    d.text((x0, 940), foot, font=font(26), fill=mix(NAVY, CYAN, prog(t, t0 + 0.5, t0 + 1.0)), anchor="ls")
    return im


# ---------- escena 4: idle_freeze ----------
IDLE_VM = (160, 300, 760, 700)


def idle(t):
    im = GRID.copy()
    d = ImageDraw.Draw(im)
    fp = prog(t, IDLE_FREEZE[0], IDLE_FREEZE[0] + 0.3)
    hatch(im, IDLE_VM, fp)
    d = ImageDraw.Draw(im)
    rect(d, IDLE_VM, 1, mix(WHITE, ICE, fp), 4)
    d.text((190, 350), "microVM · cache", font=font(28), fill=CYAN, anchor="ls")
    if fp > 0:
        d.rectangle([220, 460, 700, 540], fill=NAVY)
        d.text((460, 500), "FROZEN · 0 RAM", font=font(42), fill=ICE, anchor="mm")
    else:
        d.text((480, 500), "sin conexiones", font=font(40), fill=WHITE, anchor="mm")
        ember_dot(d, (250, 500), t)
    # regla de 10 minutos
    x0, x1, y = 160, 1760, 860
    d.line([x0, y, x1, y], fill=WHITE, width=2)
    for k in range(11):
        x = lerp(x0, x1, k / 10)
        d.line([x, y, x, y - (24 if k % 5 == 0 else 12)], fill=WHITE, width=2)
        d.text((x, y + 40), f"{k}m", font=font(24), fill=CYAN, anchor="mm")
    m = lerp(x0, x1, in_out_cubic(prog(t, b(40), b(42))))
    d.polygon([(m, y - 30), (m - 12, y - 52), (m + 12, y - 52)], fill=ICE if fp > 0 else EMBER)
    p1 = out_expo(prog(t, b(40), b(40) + 0.4))
    d.text((880, 420), "¿NADIE LO USA?", font=black(130), fill=mix(NAVY, WHITE, p1), anchor="ls")
    p2 = out_expo(prog(t, b(42), b(42) + 0.35))
    d.text((880, 580), "SE CONGELA SOLO.", font=black(130), fill=mix(NAVY, ICE, p2), anchor="ls")
    typed(d, (884, 650), "daemon.idle_freeze = 10m · la siguiente conexión lo despierta", prog(t, b(42), b(43)),
          font(26), CYAN)
    return im


# ---------- escena 5: cajetín final ----------
def end(t):
    im = GRID.copy()
    d = ImageDraw.Draw(im)
    t0 = b(END[0])
    box = (360, 290, 1560, 790)
    p = in_out_cubic(prog(t, t0, t0 + 0.6))
    rect(d, box, p, WHITE, 3)
    if p >= 1:
        for y in (560, 680):
            line(d, (box[0], y), (box[2], y), prog(t, t0 + 0.5, t0 + 0.9), WHITE, 1)
        line(d, (1250, 560), (1250, 790), prog(t, t0 + 0.6, t0 + 1.0), WHITE, 1)
    a = out_back(prog(t, t0 + 0.1, t0 + 0.5), 1.2)
    if a > 0:
        d.text((400, 520), "KINDLING", font=black(lerp(230, 196, clamp(a))), fill=WHITE, anchor="ls")
        d.text((1520, 520), "v0.20", font=black(110), fill=CYAN, anchor="rs")
    typed(d, (400, 630), "microVMs que se congelan cuando nadie las usa", prog(t, t0 + 0.5, t0 + 1.1), font(32), WHITE)
    typed(d, (400, 750), "kling upgrade · github.com/juan52878911/kindling", prog(t, t0 + 0.8, t0 + 1.4), font(32),
          CYAN)
    if t >= t0 + 0.9:
        d.text((1405, 625), "PLANO", font=font(22), fill=CYAN, anchor="mm")
        d.text((1405, 660), "FINAL", font=font(30), fill=WHITE, anchor="mm")
        ember_dot(d, (1405, 735), t)
    return im


# ---------- composición ----------
def whip(a, b_img, x):
    off = in_out_cubic(x)
    A = np.asarray(a, np.float32)
    Bm = np.asarray(b_img, np.float32)
    shift = int(off * W)
    comp = np.empty_like(A)
    comp[:, : W - shift] = A[:, shift:]
    comp[:, W - shift:] = Bm[:, :shift]
    blur = int(80 * math.sin(math.pi * x))
    if blur > 2:
        comp = sum(np.roll(comp, int(blur * k / 6), axis=1) for k in range(6)) / 6
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


def cold(t):
    def win(r):
        return clamp(prog(t, r[0], r[0] + 0.2)) * clamp(1 - prog(t, r[1], r[1] + 0.12))
    return max(win(FREEZE), win(IDLE_FREEZE))


rng = np.random.default_rng(5)
GRAIN = [rng.normal(0, 4, (H // 2, W // 2)).astype(np.float32) for _ in range(6)]


def frame(t):
    WH = 0.22
    cuts = [c for c in (b(8), b(28), b(40), b(END[0])) if c - WH / 2 <= t < c + WH / 2]
    if cuts:
        c = cuts[0]
        arr = whip(scene(c - WH / 2 - 1e-3), scene(c + WH / 2), prog(t, c - WH / 2, c + WH / 2))
    else:
        arr = np.asarray(scene(t), np.float32)
    gi = 0 if cold(t) > 0.5 else int(t * FPS) % len(GRAIN)
    arr = arr + np.repeat(np.repeat(GRAIN[gi], 2, axis=0), 2, axis=1)[..., None]
    # regla de progreso abajo: una marca por beat
    x = int(W * t / TOTAL)
    arr[H - 4:H, :x] = CYAN
    for k in range(int(TOTAL / BEAT) + 1):
        bx = int(W * k * BEAT / TOTAL)
        arr[H - (14 if k % 4 == 0 else 8):H - 4, bx:bx + 2] = (60, 100, 150)
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
