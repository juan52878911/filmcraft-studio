#!/usr/bin/env python3
"""Fondos de tarjeta (titulo, plano, cap, cierre) con la piel de cada gramática de promo.

Uso: promo_fondos.py DS

ds_assets.py genera fondos brutalistas (rejilla y bloques de color); las gramáticas de promo necesitan
los suyos para que las tarjetas que pone FilmCraft (título, cierre) no desentonen con las escenas
renderizadas por código: brasa con grano y viñeta, plano con rejilla de dibujo, riso con papel y semitono, termo
con papel y una forma fundida teñida con el gradient map.
Sobrescribe assets/bg-*.png del DS al tamaño de su lienzo.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from common import load_ds  # noqa: E402


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def temperatura(ds, W, H, kind):
    pal = ds["paleta"]
    yy, xx = np.mgrid[0:H, 0:W]
    vig = np.clip(1 - 0.28 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) ** 1.4, 0.55, 1)[..., None]
    arr = np.array(hexrgb(pal["fondo"]), np.float32) * vig  # el grano lo pone grade.noise
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.rectangle([0, H - 6, W * (0.25 if kind == "titulo" else 1.0), H], fill=pal["acento1"])
    return im


def plano(ds, W, H, kind):
    pal = ds["paleta"]
    im = Image.new("RGB", (W, H), pal["fondo"])
    d = ImageDraw.Draw(im)
    for x in range(0, W, 40):
        d.line([x, 0, x, H], fill=pal["rejilla"] if x % 200 == 0 else "#16325A")
    for y in range(0, H, 40):
        d.line([0, y, W, y], fill=pal["rejilla"] if y % 200 == 0 else "#16325A")
    if kind in ("titulo", "cierre"):  # cajetín
        bw, bh = int(W * 0.23), int(H * 0.13)
        x0, y0 = W - bw - 40, H - bh - 40
        d.rectangle([x0, y0, x0 + bw, y0 + bh], outline=pal["claro"], width=2)
        d.line([x0, y0 + bh // 3, x0 + bw, y0 + bh // 3], fill=pal["claro"], width=1)
    return im


def riso(ds, W, H, kind):
    pal = ds["paleta"]
    paper = np.array(hexrgb(pal["fondo"]), np.float32) * np.ones((H, W, 1), np.float32)  # fibra: grade.noise
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    cx, cy, R, cell = W * 0.78, H * (0.25 if kind != "cierre" else 0.3), min(W, H) * 0.45, 22
    for y in range(0, H, cell):
        for x in range(0, W, cell):
            s = max(0.0, 1 - math.hypot(x - cx, y - cy) / R) * cell * 0.5
            if s > 1:
                d.ellipse([x - s, y - s, x + s, y + s], fill=255)
    m = np.asarray(mask, np.float32)[..., None] / 255 * 0.9
    ink = np.array(hexrgb(pal["acento2"]), np.float32)
    arr = paper * (1 - m * (1 - ink / 255))
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def termo(ds, W, H, kind):
    """Papel con una forma fundida (estrella o anillo) teñida con el mapa caliente; el grano va en grade.noise."""
    from PIL import ImageFilter
    from promo_gradmap import mapas, papel, tenir
    m = Image.new("L", (W // 2, H // 2), 0)
    d = ImageDraw.Draw(m)
    s = min(W, H) / 1080
    if kind == "plano":
        F = np.zeros((H, W), np.float32)
    else:
        cx, cy = (W * 0.74, H * 0.9) if kind != "cap" else (W * 0.9, H * 0.1)
        R = (680 if kind == "cierre" else 520) * s
        pts = [(cx / 2 + (R if k % 2 == 0 else R * 0.48) / 2 * math.cos(0.2 + math.pi * k / 5 - math.pi / 2),
                cy / 2 + (R if k % 2 == 0 else R * 0.48) / 2 * math.sin(0.2 + math.pi * k / 5 - math.pi / 2))
               for k in range(11)]
        d.line(pts, fill=255, width=int(50 * s), joint="curve")
        soft = np.asarray(m.filter(ImageFilter.GaussianBlur(36 * s)), np.float32) / 255
        F = np.asarray(Image.fromarray((np.clip(soft * 1.45, 0, 1) * 255).astype(np.uint8)).resize((W, H)),
                       np.float32) / 255
    return Image.fromarray(tenir(F, mapas(ds), papel(W, H)))


GEN = {"temperatura": temperatura, "plano": plano, "riso": riso, "termo": termo}


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    ds = load_ds(sys.argv[1])
    gen = GEN[ds["gramatica"].split("@")[0]]
    W, H = ds["lienzo"]["ancho"], ds["lienzo"]["alto"]
    for kind, path in ds["fondos"].items():
        gen(ds, W, H, kind).save(path)
        print(path)


if __name__ == "__main__":
    main()
