"""Corte vertical (1080x1920) del promo de kindling v0.20 en Gradient Map (gramática termo@1).

No es "texto con halo": es la imagen térmica de una impresión mal registrada. El gradient map
(papel → azul → naranja → rojo → granate) es una escala de TEMPERATURA y la temperatura es del lugar, no del
glifo. Cada escena coloca fuentes de calor (una forma fundida, un foco que recorre una línea, el cursor) en un
campo T(x, y), y cada letra lee T en su caja:
  lejos  tinta casi negra y nítida con un filo rojo de 2 px y uno azul de 1 px (la sangría mínima del registro)
  cerca  halo ancho y CORRIDO (−10, +8 px: una segunda pasada mal registrada), núcleo que se funde a granate
El calor cruza las letras a mitad (varía por píxel dentro del glifo) y en cada plano está caliente menos de
un tercio del texto. Lo que corre está caliente; al congelar, el frío avanza por regiones desde un punto y las
letras se enfrían hasta el filo. Guion propio en timeline_g.py: menos texto, una maqueta por idea (cifras y
formas a sangre, titular rotado, titular dentro de la forma), cortes secos en el beat y solo dos frentes firma:
la llama (ignición y entrada de HOL GUARD) y el hielo (congelados; el cierre termina congelado).

Movimientos (termo.movimientos en el DS):
  brasa              fuente fija que respira (ganancia 0,8 ± 0,08 a 0,7 Hz) bajo la palabra activa
  foco_recorre       una fuente (σ 90) recorre una línea en 1,2 s; las letras se encienden a su paso y se enfrían detrás
  contagio           el calor salta de letra en letra (60 ms por letra, subida 250 ms, cae en 0,6 s a su temperatura)
  desregistro        el halo nace corrido (−18, +12) y converge a su desplazamiento de reposo en 0,4 s (out-back)
  llamarada          pico de calor de 120 ms que cae en 0,5 s: golpes del comando y momentos firma
  frente_llama       transición firma: un frente con lenguas sube y deja la escena nueva (ignición y HOL GUARD)
  enfria_a_filo      congelar: ganancia y radio a 0 y desplazamiento a (0, 0) en 0,6 s; queda la letra nítida con filo
  hielo_que_sube     el mapa frío se extiende desde un punto (no todo el cuadro a la vez)
  despertar          al revés en 0,3 s, con una llamarada al final
  fusion             formas de contorno grueso muy desenfocadas que se suman como metabolas y son fuentes de calor

Uso: python3 gradmap_v.py <term_v.mp4> <frames_dir_tmp> <salida.mp4 sin audio> [solo_t1,t2,...]
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from timeline_g import (BEAT, CHAR_W, END, FEATS, FPS, FREEZE, H, HOL, HOOK_CMD, HOOK_TYPE, IDLE_FREEZE, SILICON,
                        TEXT_X, TOTAL, W, b, row_y, src_time)

ARIAL_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
IOS_B = os.path.expanduser("~/Library/Fonts/IosevkaTermNerdFontMono-Bold.ttf")
SX = 1.16          # ensanchado horizontal del titular (la referencia usa una grotesca extendida)
MARGIN = 60
Q = 4              # el campo de calor se calcula a 1/4 de resolución
_fonts = {}

HOT = [(0.00, (233, 228, 212)), (0.07, (214, 218, 226)), (0.20, (52, 102, 224)), (0.40, (255, 172, 64)),
       (0.58, (244, 64, 58)), (0.76, (196, 28, 62)), (1.00, (46, 18, 28))]
COLD = [(0.00, (233, 228, 212)), (0.07, (206, 224, 232)), (0.20, (120, 196, 232)), (0.40, (54, 110, 222)),
        (0.62, (34, 58, 170)), (0.80, (24, 30, 96)), (1.00, (14, 18, 44))]
FILO = 0.62        # valor del filo fino: cae en el rojo del mapa caliente
FILO_OUT = 0.16    # el filo exterior de 1 px: azul


def lut(stops):
    x = np.linspace(0, 1, 1024)
    pos = [p for p, _ in stops]
    return np.stack([np.interp(x, pos, [c[k] for _, c in stops]) for k in range(3)], 1).astype(np.float32)


LUT_HOT, LUT_COLD = lut(HOT), lut(COLD)


def font(size, path=IOS_B):
    key = (path, int(size))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(path, max(8, int(size)))
    return _fonts[key]


def black(size):
    return font(size, ARIAL_BLACK)


def fit(s, width=W - 2 * MARGIN, cap=420):
    return min(cap, int(100 * width / (black(100).getlength(s) * SX)))


def clamp(x, a=0.0, b_=1.0):
    return max(a, min(b_, x))


def prog(t, t0, t1):
    return clamp((t - t0) / (t1 - t0))


def out_expo(x):
    return 1 if x >= 1 else 1 - 2 ** (-10 * x)


def in_out_cubic(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def out_back(x, s=1.3):
    x -= 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b_, x):
    return a + (b_ - a) * x


def q(t):
    """Tiempo de animación de formas y grano: 12 fps."""
    return math.floor(t * 12) / 12


FREEZES = (FREEZE, IDLE_FREEZE)


def calor_global(t):
    """enfria_a_filo / despertar: 1 corriendo, 0 congelado (0,6 s para enfriar, 0,3 s para despertar)."""
    for f0, f1 in FREEZES:
        if f0 <= t < f1:
            return 1 - out_expo(prog(t, f0, f0 + 0.6))
        if f1 <= t < f1 + 0.3:
            return out_expo(prog(t, f1, f1 + 0.3))
    return 1.0


def frozen_amt(t):
    for f0, f1 in FREEZES:
        if f0 <= t < f1 + 0.3:
            return 1 - calor_global(t)
    return 0.0


def llamarada(t, t0, amp=0.9):
    """Pico de 120 ms que cae en 0,5 s."""
    if t < t0:
        return 0.0
    dt = t - t0
    return amp * (out_expo(dt / 0.12) if dt < 0.12 else math.exp(-(dt - 0.12) / 0.5 * 3))


# ---------- papel, polvo y grano (fijos: son la impresión) ----------
rng = np.random.default_rng(20)
lo = rng.normal(0, 1, (H // 16, W // 16)).astype(np.float32)
PAPER_TEX = 1 + 0.025 * np.asarray(Image.fromarray(lo).resize((W, H), Image.BICUBIC), np.float32)
dust = Image.new("L", (W, H), 0)
red = Image.new("L", (W, H), 0)
dd, dr = ImageDraw.Draw(dust), ImageDraw.Draw(red)
for _ in range(2600):
    x, y = rng.uniform(0, W), rng.uniform(0, H)
    s = rng.choice([0.6, 0.9, 1.3, 2.2], p=[0.5, 0.3, 0.15, 0.05])
    dd.ellipse([x - s, y - s, x + s, y + s], fill=int(rng.uniform(90, 230)))
for _ in range(26):
    x, y = rng.uniform(0, W), rng.uniform(0, H)
    for _ in range(int(rng.integers(3, 9))):
        x2, y2 = x + rng.normal(0, 7), y + rng.normal(0, 7)
        dr.line([x, y, x2, y2], fill=int(rng.uniform(120, 230)), width=int(rng.integers(1, 3)))
        x, y = x2, y2
DUST = np.asarray(dust.filter(ImageFilter.GaussianBlur(0.5)), np.float32)[..., None] / 255
RED = np.asarray(red, np.float32)[..., None] / 255
GRAIN = [rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32) for _ in range(4)]
YQ, XQ = (np.mgrid[0:H // Q, 0:W // Q].astype(np.float32) + 0.5) * Q


def up(a, mode=Image.BILINEAR):
    return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((W, H), mode), np.float32)


# ---------- el campo ----------
class Campo:
    """Fuentes de calor + capas: tinta (cuerpo, sin calor), núcleo, halo y filo por glifo, formas y glow fijo."""

    def __init__(self, t):
        self.t = t
        self.src = []                          # (cx, cy, sigma, ganancia)
        self.ink = Image.new("L", (W, H), 0)
        self.core = np.zeros((H, W), np.float32)
        self.halo = np.zeros((H, W), np.float32)
        self.edge = np.zeros((H, W), np.float32)
        self.glow = {}
        self.blob = Image.new("L", (W // 2, H // 2), 0)
        self.ember = Image.new("L", (W, H), 0)   # texto que brilla sobre el oscuro del arranque
        self.ambiente = 0.2                      # cuánto se calienta el papel alrededor de las fuentes
        self._T = None

    def fuente(self, cx, cy, sigma, gain, fija=False):
        """fija: no se enfría al congelar (el cursor del cierre) y abre un hueco en el mapa frío."""
        self.src.append((cx, cy, sigma, gain, fija))
        self._T = None

    def brasa(self, cx, cy, sigma, gain=0.8):
        self.fuente(cx, cy, sigma, gain + 0.08 * math.sin(2 * math.pi * 0.7 * self.t))

    def foco(self, x0, x1, y, t0, sigma=90, dur=1.2, gain=1.0):
        """foco_recorre: la fuente viaja de x0 a x1 y se apaga al final."""
        if t0 <= self.t < t0 + dur + 0.5:
            p = in_out_cubic(prog(self.t, t0, t0 + dur))
            fade = 1 - prog(self.t, t0 + dur, t0 + dur + 0.5)
            self.fuente(lerp(x0, x1, p), y, sigma, gain * fade)

    def T(self):
        """Campo de calor (1/4 de resolución), ya escalado por el congelado."""
        if self._T is None:
            Tq = np.zeros(XQ.shape, np.float32)
            k = calor_global(self.t)
            for cx, cy, s, g, fija in self.src:
                Tq += g * (1 if fija else k) * np.exp(-((XQ - cx) ** 2 + (YQ - cy) ** 2) / (2 * s * s))
            self._T = np.clip(Tq, 0, 1)
        return self._T

    def Tbox(self, x0, y0, w, h):
        """T muestreado en una caja de pantalla (tamaño w x h)."""
        Tq = self.T()
        xs = np.clip(((x0 + np.arange(w)) / Q).astype(int), 0, Tq.shape[1] - 1)   # vale también fuera de pantalla
        ys = np.clip(((y0 + np.arange(h)) / Q).astype(int), 0, Tq.shape[0] - 1)
        return Tq[np.ix_(ys, xs)]

    def g(self, r):
        r = int(max(6, round(r / 6) * 6))
        if r not in self.glow:
            self.glow[r] = Image.new("L", (W, H), 0)
        return self.glow[r]


def put(dst, a, x, y):
    """np.maximum de `a` en `dst` con la esquina en (x, y), recortando a pantalla."""
    x, y = int(round(x)), int(round(y))
    h, w = a.shape
    x0, y0, x1, y1 = max(0, x), max(0, y), min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    dst[y0:y1, x0:x1] = np.maximum(dst[y0:y1, x0:x1], a[y0 - y:y1 - y, x0 - x:x1 - x])


PAD = 70


def glyph_mask(ch, f, sx):
    l, t_, r, bb = f.getbbox(ch, anchor="ls")
    if r - l <= 0:
        return None, 0, 0
    im = Image.new("L", (r - l + 2 * PAD, bb - t_ + 2 * PAD), 0)
    ImageDraw.Draw(im).text((PAD - l, PAD - t_), ch, font=f, fill=255, anchor="ls")
    if sx != 1:
        im = im.resize((int(im.width * sx), im.height), Image.LANCZOS)
    return im, l * sx - PAD * sx, t_ - PAD


def htext(c, xy, s, f, anchor="ls", sx=SX, t_on=None, paso=0.06, entra=True, calor=1.0):
    """Texto térmico glifo a glifo. Cada letra lee el campo T en su caja (más el contagio de su llegada) y con
    esa temperatura decide halo (radio, ganancia, desplazamiento), núcleo (se funde a granate) y filo."""
    t = c.t
    total = f.getlength(s) * sx
    x, y = xy
    x += {"l": 0, "m": -total / 2, "r": -total}[anchor[0]]
    for k, ch in enumerate(s):
        gx = x + f.getlength(s[:k]) * sx
        if ch == " ":
            continue
        dt = None if t_on is None else t - (t_on + k * paso)
        if dt is not None and dt < 0 and entra:
            continue                                            # aún no ha llegado
        im, ox, oy = glyph_mask(ch, f, sx)
        if im is None:
            continue
        m = np.asarray(im, np.float32) / 255
        X, Y = gx + ox, y + oy
        hp = c.Tbox(X, Y, im.width, im.height) * calor
        if dt is not None and dt >= 0:                          # contagio: la llegada calienta la letra
            flare = out_expo(dt / 0.25) if dt < 0.25 else math.exp(-(dt - 0.25) / 0.6)
            hp = np.clip(hp + 0.95 * flare * calor_global(t), 0, 1)
        heat = float((hp * m).sum() / (m.sum() + 1e-6))
        # desregistro: nace corrido (−26, +18) y reposa en (−18, +12) × calor: lo caliente se corre
        rest = (-18 * heat, 12 * heat)
        if dt is not None and 0 <= dt < 0.4:
            p = out_back(dt / 0.4)
            dx, dy = lerp(-26, rest[0], p), lerp(18, rest[1], p)
        else:
            dx, dy = rest
        r = 28 * heat
        if r >= 1.5:
            hi = im.filter(ImageFilter.GaussianBlur(r))
            halo = np.asarray(hi, np.float32) / 255 * 1.3 * hp
            sx_, sy_ = int(round(dx)), int(round(dy))
            mo = np.roll(m, (-sy_, -sx_), (0, 1))                # el halo vive fuera de la letra
            put(c.halo, halo * (1 - mo), X + dx, Y + dy)
        # el mapa dentro del glifo: borde naranja/amarillo, centro rojo-granate, con grano propio
        inner = np.asarray(im.filter(ImageFilter.GaussianBlur(max(3, im.height * 0.05))), np.float32) / 255
        inner = np.clip((inner - 0.35) / 0.65, 0, 1)
        hot = 0.4 + 0.42 * inner + 0.08 * np.random.default_rng(ord(ch) + k).normal(0, 1, m.shape)
        core = m * (1 - hp) + m * hot * hp
        if heat > 0.3:
            core = np.asarray(Image.fromarray((np.clip(core, 0, 1) * 255).astype(np.uint8)).filter(
                ImageFilter.GaussianBlur(3 * (heat - 0.3) / 0.7)), np.float32) / 255
        put(c.core, np.clip(core, 0, 1), X, Y)
        e = clamp(1 - heat / 0.3)                               # frío: filo fino rojo y azul
        if e > 0:
            d2 = np.asarray(im.filter(ImageFilter.MaxFilter(5)), np.float32) / 255
            d4 = np.asarray(im.filter(ImageFilter.MaxFilter(7)), np.float32) / 255
            put(c.edge, (np.clip(d2 - m, 0, 1) * FILO + np.clip(d4 - d2, 0, 1) * FILO_OUT) * e, X, Y)
    return total


def wtext(c, xy, s, size, anchor="ls", **kw):
    return htext(c, xy, s, black(size), anchor, SX, **kw)


def text(m, xy, s, f, anchor="ls"):
    ImageDraw.Draw(m).text(xy, s, font=f, fill=255, anchor=anchor)


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


def para(m, xy, s, f, spacing=1.3):
    x, y = xy
    for k, ln in enumerate(wrap(s, f)):
        text(m, (x, y + k * f.size * spacing), ln, f)


def label(c, xy, s, size=64, pad=18):
    """Etiqueta en caja negra con el texto calado (el "+20" de la referencia)."""
    f = black(size)
    w = f.getlength(s) * SX
    x, y = xy
    box = Image.new("L", (W, H), 0)
    ImageDraw.Draw(box).rectangle([x, y, x + w + 2 * pad, y + size * 1.15 + pad], fill=255)
    im = Image.new("L", (W, H), 0)
    l, t_, r, bb = f.getbbox(s, anchor="ls")
    g = Image.new("L", (r - l + 8, bb - t_ + 8), 0)
    ImageDraw.Draw(g).text((4 - l, 4 - t_), s, font=f, fill=255, anchor="ls")
    g = g.resize((int(g.width * SX), g.height), Image.LANCZOS)
    im.paste(g, (int(x + pad), int(y + size * 0.98 + pad / 2 + t_ - 4)))
    c.ink.paste(Image.fromarray(np.clip(np.asarray(box, np.int16) - np.asarray(im, np.int16), 0, 255)
                                .astype(np.uint8)), (0, 0), box)
    return x + w + 2 * pad


def cabecera(c):
    label(c, (MARGIN, 120), "v0.20")
    text(c.ink, (MARGIN + black(64).getlength("v0.20") * SX + 70, 192), ".KLING", font(40))


# ---------- formas fundidas a sangre (media resolución); cada una es una fuente de calor ----------
# Ninguna "aparece" con pop: la forma ya está y lo que sube es su temperatura (ganancia 0 → 1 en 0,4 s).
def ganancia(t, t0, dur=0.4):
    return out_expo(prog(t, t0, t0 + dur))


def blob_line(c, pts, width, g=1.0):
    ImageDraw.Draw(c.blob).line([(x / 2, y / 2) for x, y in pts], fill=int(255 * g), width=int(width / 2),
                                joint="curve")


def blob_ring(c, cx, cy, r, width, g=1.0):
    ImageDraw.Draw(c.blob).ellipse([(cx - r) / 2, (cy - r) / 2, (cx + r) / 2, (cy + r) / 2], outline=int(255 * g),
                                   width=int(width / 2))


def blob_disc(c, cx, cy, r, g=1.0, heat=0.75):
    ImageDraw.Draw(c.blob).ellipse([(cx - r) / 2, (cy - r) / 2, (cx + r) / 2, (cy + r) / 2], fill=int(255 * g))
    if heat:
        c.brasa(cx, cy, r * 0.8, heat * g)


def blob_pill(c, x0, y0, x1, y1, width, g=1.0):
    ImageDraw.Draw(c.blob).rounded_rectangle([x0 / 2, y0 / 2, x1 / 2, y1 / 2], radius=int((y1 - y0) / 4),
                                             outline=int(255 * g), width=int(width / 2))


# ---------- 1. gancho ----------
CMD_X0 = (W - font(56).getlength("❯ " + HOOK_CMD)) / 2
CMD_END = CMD_X0 + font(56).getlength("❯ " + HOOK_CMD)
STACK = ["DOCKER", "COMPOSE", "EN MICROVMS.", "EN TU MAC."]


def a_sangre(s, width):
    """Tamaño de Arial Black ensanchada para que `s` mida `width` (más que la pantalla = recortada)."""
    return int(100 * width / (black(100).getlength(s) * SX))


def hook(t, c):
    n = int(len(HOOK_CMD) * prog(t, HOOK_TYPE[0], HOOK_TYPE[1]) + 0.999) if t >= HOOK_TYPE[0] else 0
    if t < b(2):
        # arranque en oscuro: el comando se teclea como brasa; el Enter suelta la chispa (ver ignicion)
        text(c.ember, (CMD_X0, H / 2 + 18), "❯ " + HOOK_CMD[:n] +
             ("▌" if t < HOOK_TYPE[1] and int(t * 6) % 2 else ""), font(56))
        return
    cabecera(c)
    # la brasa que dejó la chispa: un disco enorme que asoma por abajo
    blob_disc(c, W * 0.62, H + 260, 760, 1.0, 0.9)
    if t < b(4):
        text(c.ink, (MARGIN, 330), "❯ " + HOOK_CMD, font(46))
        text(c.ink, (MARGIN, 400), "demo is up in 0.5s", font(46))
        c.fuente(140, 1180, 220, llamarada(t, b(2), 1.0))           # la cifra arde por la izquierda
        wtext(c, (-40, 1250), "0.5s", a_sangre("0.5s", W * 1.18), t_on=b(2), paso=0.07)
    else:
        y = 330
        for k, s in enumerate(STACK):
            size = fit(s, cap=210)
            y += size * 0.82
            if k == 2:   # foco que recorre "EN MICROVMS." cuando la línea ya está puesta
                c.foco(MARGIN, W - MARGIN, y - size * 0.35, b(6), sigma=110)
            wtext(c, (MARGIN, y), s, size, t_on=b(4) + k * BEAT / 2, paso=0.05)
            y += 26


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
        _tc[i] = (np.where(warm, 1, lum).astype(np.float32), warm.astype(np.float32))
    return _tc[i]


TO = (40, 520)     # la ventana de 1000x1000 en un lienzo de 1080x2200
FOCUS_Y = 760


def ry(i):
    return TO[1] + row_y(i) + 16


def cam_wide(t):
    return (t, 540, ry(9) + 140, 1.0)


def cam_row(t, row, z=1.45):
    """Zoom a una fila de resultado: el margen izquierdo del texto siempre a la vista."""
    cx = TO[0] + TEXT_X - 40 + W / (2 * z)
    return (t, cx, ry(row) + (H / 2 - FOCUS_Y) / z, z)


# zoom al resultado, pausa, látigo de 0,3 s a la siguiente fila
CAM = [cam_wide(b(8)), cam_wide(b(9.6)), cam_row(b(10), 8), cam_row(b(12), 8), cam_row(b(12) + 0.3, 13),
       cam_row(b(14.6), 13), cam_row(b(15), 15), cam_row(b(19), 15), cam_row(b(19) + 0.3, 17),
       cam_row(b(21), 17), cam_wide(b(22))]
FOCUS = [(b(9.6), b(12.1), 8), (b(12.1), b(14.8), 13), (b(14.8), b(19.1), 15), (b(19.1), b(21), 17)]


def cam_at(t):
    for (t0, *a), (t1, *c_) in zip(CAM, CAM[1:]):
        if t <= t1:
            x = in_out_cubic(prog(t, t0, t1))
            return [lerp(p, q_, x) for p, q_ in zip(a, c_)]
    return CAM[-1][1:]


def to_screen(cam, x, y):
    cx, cy, z = cam
    return (x - cx) * z + W / 2, (y - cy) * z + H / 2


def col_x(col):
    return TO[0] + TEXT_X + col * CHAR_W


CAPTIONS = [  # (desde, hasta, fila, col0, col1, texto, línea)
    (b(10), b(12), 8, 14, 18, "ARRANQUE EN CALIENTE", None),
    (b(12) + 0.3, b(14.8), 13, 6, 13, "NATIVO EN APPLE SILICON", "uname -m: aarch64, sin emulación"),
    (FREEZE[0], FREEZE[1], 15, 16, 22, "CONGELADO. 0 RAM.", None),
    (FREEZE[1] + 0.3, b(22), 17, 0, 4, "DESPIERTA SOLO", None),
]


def terminal(t, c):
    c.ambiente = 0.0          # sobre la terminal la bruma taparía los caracteres
    tb, tw = term_masks(src_time(t))
    cx, cy, z = cam_at(t)
    cam = (cx, cy, z)
    canvas = np.zeros((2200, W), np.float32)
    warmc = np.zeros((2200, W), np.float32)
    canvas[TO[1]:TO[1] + tb.shape[0], TO[0]:TO[0] + tb.shape[1]] = tb
    warmc[TO[1]:TO[1] + tw.shape[0], TO[0]:TO[0] + tw.shape[1]] = tw
    # foco: con zoom, las filas que no son el resultado se quedan frías y tenues
    dim = clamp((z - 1.05) / 0.3)
    for f0, f1, row in FOCUS:
        if f0 <= t < f1 and dim > 0:
            w_ = np.full(2200, 1 - 0.9 * dim, np.float32)
            y0 = int(ry(row) - ROW_PX * 0.75)
            w_[y0:int(y0 + ROW_PX * 1.1)] = 1
            canvas *= w_[:, None]
    box = (cx - W / z / 2, cy - H / z / 2, cx + W / z / 2, cy + H / z / 2)
    term = np.asarray(Image.fromarray(canvas, "F").transform((W, H), Image.EXTENT, box, Image.BILINEAR), np.float32).copy()
    warm = np.asarray(Image.fromarray(warmc, "F").transform((W, H), Image.EXTENT, box, Image.BILINEAR), np.float32).copy()
    # látigo: desenfoque de movimiento vertical cuando la cámara corre
    _, cy0, z0 = cam_at(t - 1 / 30)
    v = abs(cy - cy0) * z
    if v > 12:
        k = min(6, int(v / 12) + 1)
        term = sum(np.roll(term, int(v * j / k), 0) for j in range(k)) / k
    sx0 = sy = sx1 = None
    for t0, t1, row, c0, c1, lab, line in CAPTIONS:
        if t0 <= t < t1:
            sx0, sy = to_screen(cam, col_x(c0) - 10, ry(row) - 14)
            sx1, _ = to_screen(cam, col_x(c1) + 10, ry(row) - 14)
            c.foco(sx0, sx1, sy, t0, sigma=70, dur=0.5)
            c.brasa((sx0 + sx1) / 2, sy, 60 + (sx1 - sx0) / 2, 0.85)
    term[1440:] = 0
    warm[1440:] = 0
    Tf = up(c.T())
    heat = np.clip(Tf + 0.5 * warm, 0, 1)
    c.core = np.maximum(c.core, term * ((1 - heat) + heat * 0.7))
    small = Image.fromarray((np.clip(term, 0, 1) * 255).astype(np.uint8)).resize((W // 2, H // 2), Image.BILINEAR)
    halo = up(np.asarray(small.filter(ImageFilter.GaussianBlur(6)), np.float32) / 255) * 1.1 * heat
    hk = float(heat.max())
    c.halo = np.maximum(c.halo, np.roll(halo, (int(10 * hk), -int(14 * hk)), (0, 1)) * (1 - np.clip(term * 3, 0, 1)))
    d2 = np.asarray(Image.fromarray((np.clip(term, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)),
                    np.float32) / 255
    c.edge = np.maximum(c.edge, np.clip(d2 - term, 0, 1) * FILO * np.clip(1 - heat / 0.3, 0, 1) * (term.max() > 0))
    text(c.ink, (MARGIN, 120), "grabación real en un Mac M4", font(30))
    for t0, t1, row, c0, c1, lab, line in CAPTIONS:
        if t0 <= t < t1:
            c.foco(MARGIN, W - MARGIN, 1610, t0 + 0.15, sigma=100, dur=0.9)
            wtext(c, (MARGIN, 1660), lab, fit(lab, cap=150), t_on=t0 + 0.1, paso=0.03)
            if line:
                text(c.ink, (MARGIN, 1790), line, font(40))


ROW_PX = 44.4


def frio_terminal():
    """Dónde nace el frío de la terminal: el "322 ms" en pantalla con la cámara quieta."""
    cam = cam_at(FREEZE[0] + 0.5)
    x, y = to_screen(cam, col_x(19), ry(15) - 14)
    return x, y


# ---------- 3. Apple Silicon ----------
def silicon(t, c):
    t0 = b(SILICON[0])
    g = ganancia(t, t0)
    # el chip enorme, recortado por arriba y a la derecha: la fuente de calor de la escena
    cx, cy, s = W - 40, 330, 470
    blob_line(c, [(cx - s, cy - s), (cx + s, cy - s), (cx + s, cy + s), (cx - s, cy + s), (cx - s, cy - s)], 70, g)
    for k in range(7):
        o = -s + (k + 0.5) * 2 * s / 7
        blob_line(c, [(cx - s - 90, cy + o), (cx - s, cy + o)], 34, g)
        blob_line(c, [(cx + o, cy + s), (cx + o, cy + s + 90)], 34, g)
    c.brasa(cx - 120, cy + 80, 360, 0.8 * g)
    wtext(c, (MARGIN, 300), "APPLE SILICON", 74, t_on=t0, paso=0.03, calor=0.5)
    c.fuente(120, 1260, 260, llamarada(t, t0 + 0.15, 1.0))
    wtext(c, (-50, 1420), "36", a_sangre("36", W * 0.98), t_on=t0 + 0.15, paso=0.08)
    wtext(c, (W - MARGIN, 1660), "ms", 230, "rs", t_on=t0 + 0.4)
    if t >= t0 + 0.7:
        text(c.ink, (MARGIN, 1800), "despertar en un M4, nativo", font(46))


# ---------- 4. capacidades: una maqueta por idea ----------
def card_copias(t, c, t0):
    """50 COPIAS: el golden se multiplica en 50 discos que se separan y se funden."""
    g = ganancia(t, t0)
    gx, gy = W * 0.7, 520
    blob_disc(c, gx, gy, 190, g, 0.85)
    p = out_expo(prog(t, t0 + 0.15, t0 + 0.9))
    r = np.random.default_rng(50)
    for k in range(50):
        a = k * 2.399963
        d = 70 + 26 * math.sqrt(k + 1) * 7
        x, y = gx + math.cos(a) * d * p, gy + math.sin(a) * d * 0.8 * p
        blob_disc(c, x + r.normal(0, 8), y + r.normal(0, 8), 38 + r.uniform(-8, 8), g * (0.35 + 0.65 * p), 0)
    c.fuente(150, 1100, 240, 0.6)
    wtext(c, (-60, 1260), "50", a_sangre("50", W * 0.92), t_on=t0, paso=0.1)
    wtext(c, (MARGIN, 1440), "COPIAS EN 784 MiB", fit("COPIAS EN 784 MiB", cap=120), t_on=t0 + 0.2, paso=0.03)


class Lienzo(Campo):
    """Campo apaisado para el titular rotado: sin fuentes, solo el contagio de su entrada."""

    def __init__(self, t, w, h):
        super().__init__(t)
        self.core = np.zeros((h, w), np.float32)
        self.halo = np.zeros((h, w), np.float32)
        self.edge = np.zeros((h, w), np.float32)

    def Tbox(self, x0, y0, w, h):
        return np.zeros((h, w), np.float32)


def card_ramas(t, c, t0):
    """1 DB POR RAMA: el grafo de git a sangre por la izquierda y el titular rotado contra el borde derecho."""
    g = ganancia(t, t0)
    p = out_expo(prog(t, t0, t0 + 0.6))
    tx = 150
    blob_line(c, [(tx, -200), (tx, H + 200)], 80, g)
    for k, (yb, x1) in enumerate(((420, 560), (860, 470), (1300, 600))):
        if p > k * 0.25:
            q_ = clamp((p - k * 0.25) / 0.5)
            blob_line(c, [(tx, yb), (tx + 120, yb - 120), (lerp(tx + 120, x1, q_), yb - 160)], 60, g)
            blob_ring(c, lerp(tx + 120, x1, q_), yb - 160, 120, 46, g)
            c.brasa(lerp(tx + 120, x1, q_), yb - 160, 130, 0.55 * g)
    lab = "1 DB POR RAMA"
    sz = int(100 * (H - 2 * MARGIN) / (black(100).getlength(lab) * SX))
    lz = Lienzo(t, H, W)
    htext(lz, (MARGIN, W - 70), lab, black(sz), t_on=t0 + 0.1, paso=0.04)
    for name in ("core", "halo", "edge"):
        setattr(c, name, np.maximum(getattr(c, name), np.rot90(getattr(lz, name), 1)))
    text(c.ink, (300, 1640), "Postgres, MySQL, Redis o SQLite", font(34))


def card_mcp(t, c, t0):
    """MCP: la píldora (el enchufe) enorme, recortada por la izquierda, con el titular dentro."""
    g = ganancia(t, t0)
    blob_pill(c, -260, 640, 940, 1200, 64, g)
    c.brasa(380, 920, 300, 0.9 * g)
    wtext(c, (70, 1030), "MCP", 330, t_on=t0 + 0.1, paso=0.08)
    wtext(c, (MARGIN, 1400), "BAJO DEMANDA", fit("BAJO DEMANDA", cap=150), t_on=t0 + 0.3, paso=0.03, calor=0.4)


CARDS = [(card_copias, "kling run -from golden", MARGIN), (card_ramas, "kling db up pg", 300),
         (card_mcp, "kling mcp import", MARGIN)]


def feats(t, c):
    k = min(2, int((t - b(FEATS[0])) / (4 * BEAT)))
    t0 = b(FEATS[0] + 4 * k)
    draw, cmd, x = CARDS[k]
    draw(t, c, t0)
    if t >= t0 + 0.45:
        c.foco(x, x + font(46).getlength("❯ " + cmd), 1705, t0 + 0.45, sigma=60, dur=0.6)
        htext(c, (x, 1760), "❯ " + cmd, font(46), sx=1)


# ---------- 5. HOL Guard ----------
def hol(t, c):
    t0 = b(HOL[0])
    g = ganancia(t, t0)
    # el escudo enorme, recortado por arriba
    s, cx, cy = 470, W / 2, 140
    blob_line(c, [(cx - s, cy - s), (cx, cy - s * 1.25), (cx + s, cy - s), (cx + s, cy + s * 0.15),
                  (cx, cy + s * 1.3), (cx - s, cy + s * 0.15), (cx - s, cy - s)], 110, g)
    c.brasa(cx, cy + 200, 300, 0.7 * g)
    if t >= t0 + 0.35:
        pc = prog(t, t0 + 0.35, t0 + 0.6)
        chk = [(cx - 130, 330), (cx - 30, 430), (cx + 150, 210)]
        ImageDraw.Draw(c.g(14)).line(chk[:2] if pc < 0.5 else chk, fill=255, width=44, joint="curve")
    wtext(c, (MARGIN, 900), "AHORA EN", 96, calor=0.3)
    wtext(c, (MARGIN, 1130), "HOL GUARD", fit("HOL GUARD"), t_on=t0 + 0.13, paso=0.05)
    # el escaneo: un foco recorre el comando real antes de dejarlo pasar
    f = font(52)
    cmd = "❯ " + HOOK_CMD
    c.foco(MARGIN, MARGIN + f.getlength(cmd), 1380, t0 + 0.6, sigma=70, dur=1.0, gain=1.1)
    htext(c, (MARGIN, 1400), cmd, f, sx=1)
    if t >= t0 + 1.7:
        text(c.ink, (MARGIN, 1500), "✓ revisado antes de ejecutarse", font(40))
    text(c.ink, (MARGIN, 1860), "extensión command.kindling", font(30))


# ---------- 6. cierre: a los 10 min sin uso se congela solo ----------
CURSOR = (MARGIN + font(56).getlength("❯ kling upgrade "), 1268)


def end(t, c):
    t0 = b(END[0])
    cabecera(c)
    blob_disc(c, W + 120, H + 160, 900, 1.0, 0.8)
    c.brasa(160, 560, 190, 0.85)       # "KIN" arde, "DLING" queda en filo
    wtext(c, (MARGIN, 640), "KINDLING", fit("KINDLING"), t_on=t0, paso=0.07)
    if t >= t0 + 0.4:
        text(c.ink, (MARGIN, 780), "microVMs que se congelan", font(52))
        text(c.ink, (MARGIN, 850), "cuando nadie las usa.", font(52))
    if t >= t0 + 0.8:
        htext(c, (MARGIN, 1290), "❯ kling upgrade", font(56), sx=1)
        # el cursor: lo único que sigue caliente cuando todo se congela
        c.fuente(CURSOR[0] + 18, CURSOR[1] - 10, 60, 1.0, fija=True)
        if int(t * 2.2) % 2 == 0:   # el cursor brilla: va en una capa con halo, no en tinta
            ImageDraw.Draw(c.g(18)).rectangle([CURSOR[0], CURSOR[1] - 50, CURSOR[0] + 30, CURSOR[1] + 6], fill=255)
        text(c.ink, (MARGIN, 1380), "github.com/juan52878911/kindling", font(36))
    if t >= IDLE_FREEZE[0] - BEAT:
        text(c.ink, (MARGIN, 960), "10 min sin uso: se congela solo.", font(40))


# ---------- composición ----------
# hielo_que_sube: de dónde nace el frío (y por dónde vuelve el calor)
def frio_desde(win):
    return frio_terminal() if win == FREEZE else (W * 0.15, 520)


def cold_map(t, holes=()):
    for win in (FREEZE, IDLE_FREEZE):
        f0, f1 = win
        if f0 <= t < f1 + 0.4:
            fx, fy = frio_desde(win)
            d = np.hypot(XQ - fx, YQ - fy)
            R_in = 2600 * out_expo(prog(t, f0, f0 + 0.7))
            m = np.clip((R_in - d) / 300, 0, 1)
            if t >= f1:
                R_out = 2600 * out_expo(prog(t, f1, f1 + 0.4))
                m = m * np.clip((d - R_out) / 300, 0, 1)
            for hx, hy, hs in holes:
                m = m * (1 - np.exp(-((XQ - hx) ** 2 + (YQ - hy) ** 2) / (2 * hs * hs)))
            return up(m)
    return None


# ---------- frentes: ignición (oscuro → escena) y llama de transición (escena → escena) ----------
DARK = np.array([11, 13, 22], np.float32)           # el extremo frío del mapa: todo apagado, 0 RAM
LAND = b(2) - 0.06                                   # la chispa toca el suelo justo antes del beat 2
IGN = (b(2), b(4) + 0.1)                             # la llama cruza la pantalla en dos beats
LLAMA = (b(HOL[0]) - 0.05, b(HOL[0]) + 0.75)         # el frente vuelve para entrar en HOL GUARD


def spark_pos(t):
    """La chispa sale del cursor con el Enter y cae al suelo con un leve vaivén."""
    p = prog(t, HOOK_TYPE[1], LAND)
    return CMD_END + 30 * math.sin(p * 9) * (1 - p), lerp(H / 2, H - 40, p ** 2.2)


def frente(t, t0, t1):
    """D a 1/4: 0 = ya quemado (escena nueva), 1 = aún sin quemar; el borde lleva lenguas."""
    yq = YQ[:, 0][:, None]
    xq = XQ[0][None, :]
    p = prog(t, t0, t1)
    yb = lerp(H + 120, -420, p ** 0.85) if t >= t0 else H + 400
    tong = (120 * np.sin(xq / 150 + t * 3.1) ** 2 + 60 * np.sin(xq / 71 - t * 5.3) ** 2
            + 18 * np.sin(xq / 29 + t * 9))
    edge = yb - tong * min(1, p * 4 + 0.2)
    return 1 - np.clip((yq - edge) / 380, 0, 1), xq, yq


def teñir_frente(col, D, fondo):
    v = (np.clip(D * 1.05, 0, 1) * 1023).astype(np.int32)
    a = np.clip(D * 5, 0, 1)[..., None]
    dk = np.clip((D - 0.86) / 0.14, 0, 1)[..., None]
    out = col * (1 - a) + LUT_HOT[v] * a
    return out * (1 - dk) + fondo * dk


def ignicion(t, col, ember):
    if t >= IGN[1] + 0.05:
        return col
    D, xq, yq = frente(t, *IGN)
    if LAND <= t < IGN[0] + 0.3:                     # brasa en el suelo donde cayó la chispa
        gx, _ = spark_pos(LAND)
        D = D - llamarada(t, LAND, 1.0) * np.exp(-((xq - gx) ** 2 + (yq - H) ** 2 * 0.5) / (2 * 140 ** 2))
    if HOOK_TYPE[1] <= t < LAND + 0.05:              # la chispa y su estela
        for k in range(14):
            sx, sy = spark_pos(max(HOOK_TYPE[1], t - k * 0.011))
            D = D - (1.0 - k * 0.065) * np.exp(-((xq - sx) ** 2 + (yq - sy) ** 2) / (2 * (14 - 0.7 * k) ** 2))
    D = up(np.clip(D, 0, 1))
    em = np.asarray(ember, np.float32) / 255
    if em.max() > 0:                                 # comando en brasa: núcleo naranja, halo rojo
        small = ember.resize((W // 2, H // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(7))
        D = np.clip(D - em * 0.55 - up(np.asarray(small, np.float32) / 255) * 0.5, 0, 1)
    return teñir_frente(col, D, DARK)


def scene(t, c):
    if t < b(8):
        hook(t, c)
    elif t < b(SILICON[0]):
        terminal(t, c)
    elif t < b(FEATS[0]):
        silicon(t, c)
    elif t < b(HOL[0]):
        feats(t, c)
    elif t < b(END[0]):
        hol(t, c)
    else:
        end(t, c)


def render(t, ts=None):
    """Compone la escena del instante `ts` (por defecto t) con el estado térmico de t."""
    ts = t if ts is None else ts
    c = Campo(ts)
    scene(ts, c)
    frio = frozen_amt(t)
    beat = (t / BEAT) % 1
    pulse = 1 + 0.1 * math.exp(-beat * 7) * (1 - frio)
    F = np.maximum(np.asarray(c.ink, np.float32) / 255, c.core)
    F = np.maximum(F, np.clip(c.halo * pulse, 0, 1))
    F = np.maximum(F, c.edge)
    for r, m in c.glow.items():
        small = m.resize((W // 2, H // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(r * lerp(1, 0.4, frio) / 2))
        F = np.maximum(F, np.maximum(np.asarray(m, np.float32) / 255, up(np.asarray(small, np.float32)) / 255 * 1.5))
    if np.asarray(c.blob).max() > 0:
        soft = np.asarray(c.blob.filter(ImageFilter.GaussianBlur(int(36 * lerp(1, 0.7, frio)))), np.float32) / 255
        F = np.maximum(F, up(np.clip(soft * 1.45 * pulse, 0, 1)))
    F = np.maximum(F, c.ambiente * up(c.T()) ** 1.4)
    gi = 0 if frio > 0.5 else int(q(t) * 12) % len(GRAIN)
    g = np.repeat(np.repeat(GRAIN[gi], 2, 0), 2, 1)
    drift = 0.03 * math.sin(t * 0.9) * (1 - frio)
    Fv = np.clip(F * (1 + drift) + g * 0.028 * (F > 0.02), 0, 1)
    idx = (Fv * 1023).astype(np.int32)
    holes = [(x, y, s * 1.6) for x, y, s, _, fija in c.src if fija]
    cm = cold_map(t, holes)
    col = LUT_HOT[idx] if cm is None else LUT_HOT[idx] * (1 - cm[..., None]) + LUT_COLD[idx] * cm[..., None]
    col = col * PAPER_TEX[..., None]
    col = col * (1 - DUST * 0.75) + (np.array([200, 40, 50], np.float32) - col) * RED * 0.8
    return col, c, g


def frame(t):
    col, c, g = render(t)
    col = ignicion(t, col, c.ember)
    if LLAMA[0] <= t < LLAMA[1]:                     # llama de transición: lo anterior arde y deja HOL GUARD
        prev, _, _ = render(t, b(HOL[0]) - 0.02)
        D, _, _ = frente(t, *LLAMA)
        col = teñir_frente(col, up(D), prev)
    col = col + g[..., None] * 5
    col *= clamp((TOTAL - t) / 0.6)
    return np.clip(col, 0, 255).astype(np.uint8)


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
