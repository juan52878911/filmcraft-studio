#!/usr/bin/env python3
"""Pasada de gradient map (gramática termo@1) sobre cualquier imagen o video: la versión "efecto" del estilo.

Uso: promo_gradmap.py DS ENTRADA SALIDA [--invertir] [--niveles 0.1,0.85] [--halo R] [--frio 3.1-5.8,...]
                       [--fuente x,y,sigma,ganancia ...] [--sin-grano]

Usa --fuente: el calor es del lugar, no de la letra (ver termo.filosofia en el DS). Sin fuentes, el halo va
en todo por igual, que es justo lo que el estilo evita; sirve solo para pruebas.

FilmCraft no tiene un gradient map de varios tonos (Tint solo mapea a dos colores), así que el look se aplica
por código, igual que liquid glass: exporta de FilmCraft (o toma un clip), pásalo por aquí y vuelve a
importarlo, o úsalo de fuente en plan.json. Cada píxel se convierte en una intensidad (luminancia; con
--invertir, lo oscuro es lo caliente, para material sobre fondo claro), se estira entre --niveles (lo
que queda por debajo del primero es papel limpio), se suma un halo (la misma imagen
desenfocada, radio R) y se tiñe con `promo.mapas.caliente` del DS; dentro de los tramos --frio usa
`promo.mapas.frio`. Encima van el polvo, las salpicaduras y el grano dentro del degradado de la piel.

Las funciones `lut`, `tenir` y `papel` las usan también promo_fondos.py y los renders de escena.
"""
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
from common import load_ds  # noqa: E402


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def lut(stops, n=1024):
    """[[pos, "#rrggbb"], ...] -> tabla n x 3."""
    x = np.linspace(0, 1, n)
    pos = [p for p, _ in stops]
    cols = [hexrgb(c) for _, c in stops]
    return np.stack([np.interp(x, pos, [c[k] for c in cols]) for k in range(3)], 1).astype(np.float32)


def papel(W, H, seed=20):
    """Textura de papel, polvo y salpicaduras rojas (fijos: son la impresión)."""
    rng = np.random.default_rng(seed)
    lo = rng.normal(0, 1, (max(2, H // 16), max(2, W // 16))).astype(np.float32)
    tex = 1 + 0.025 * np.asarray(Image.fromarray(lo).resize((W, H), Image.BICUBIC), np.float32)
    dust, red = Image.new("L", (W, H), 0), Image.new("L", (W, H), 0)
    dd, dr = ImageDraw.Draw(dust), ImageDraw.Draw(red)
    k = W * H / (1080 * 1920)
    for _ in range(int(2600 * k)):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        s = rng.choice([0.6, 0.9, 1.3, 2.2], p=[0.5, 0.3, 0.15, 0.05])
        dd.ellipse([x - s, y - s, x + s, y + s], fill=int(rng.uniform(90, 230)))
    for _ in range(int(26 * k) + 1):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        for _ in range(int(rng.integers(3, 9))):
            x2, y2 = x + rng.normal(0, 7), y + rng.normal(0, 7)
            dr.line([x, y, x2, y2], fill=int(rng.uniform(120, 230)), width=int(rng.integers(1, 3)))
            x, y = x2, y2
    return (tex, np.asarray(dust.filter(ImageFilter.GaussianBlur(0.5)), np.float32)[..., None] / 255,
            np.asarray(red, np.float32)[..., None] / 255)


def tenir(F, mapa, piel, grano=None, frio=0.0, salpicadura="#C82832"):
    """Campo F (H x W, 0..1) -> RGB uint8 con el mapa caliente/frío, grano dentro del degradado y polvo."""
    tex, dust, red = piel
    if grano is not None:
        F = np.clip(F + grano * 0.028 * (F > 0.02), 0, 1)
    idx = (np.clip(F, 0, 1) * 1023).astype(np.int32)
    col = mapa["caliente"][idx] * (1 - frio) + mapa["frio"][idx] * frio
    col = col * tex[..., None]
    col = col * (1 - dust * 0.75) + (np.array(hexrgb(salpicadura), np.float32) - col) * red * 0.8
    if grano is not None:
        col = col + grano[..., None] * 5
    return np.clip(col, 0, 255).astype(np.uint8)


def mapas(ds):
    m = ds["promo"]["mapas"]
    return {"caliente": lut(m["caliente"]), "frio": lut(m["frio"])}


def calor(W, H, fuentes):
    """Campo de calor T: suma de gaussianas [(x, y, sigma, ganancia)] en píxeles; sin fuentes, calor 1 en todo."""
    if not fuentes:
        return None
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    T = sum(g * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * s * s)) for x, y, s, g in fuentes)
    return np.clip(T, 0, 1)


def campo(rgb, invertir, halo, niveles=(0.1, 0.85), T=None):
    """Intensidad + halo. Con T (calor localizado, la regla de termo@1): el halo solo nace donde hay calor y va
    corrido (−10, +8) × calor, el núcleo caliente se funde a granate y lo frío se queda nítido con filo rojo."""
    a = np.asarray(rgb, np.float32)
    lum = (a[..., 0] * 0.3 + a[..., 1] * 0.59 + a[..., 2] * 0.11) / 255
    F = 1 - lum if invertir else lum
    F = np.clip((F - niveles[0]) / (niveles[1] - niveles[0]), 0, 1)
    if halo > 0:
        H, W = F.shape
        small = Image.fromarray((F * 255).astype(np.uint8)).resize((W // 2, H // 2), Image.BILINEAR)
        blur = np.asarray(small.filter(ImageFilter.GaussianBlur(halo / 2)).resize((W, H), Image.BILINEAR),
                          np.float32) / 255
        if T is None:
            F = np.maximum(F, blur * 1.55)
        else:
            k = float(T.max())
            blur = np.roll(blur, (int(8 * k), -int(10 * k)), (0, 1))
            core = F * (1 - 0.22 * T)
            mask = Image.fromarray((F * 255).astype(np.uint8))
            filo = np.clip(np.asarray(mask.filter(ImageFilter.MaxFilter(5)), np.float32) / 255 - F, 0, 1)
            F = np.maximum(np.maximum(core, blur * 1.3 * T), filo * 0.62 * np.clip(1 - T / 0.3, 0, 1))
    return np.clip(F, 0, 1)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout.strip().split(",")
    num, den = out[2].split("/")
    return int(out[0]), int(out[1]), float(num) / float(den)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ds")
    ap.add_argument("entrada")
    ap.add_argument("salida")
    ap.add_argument("--invertir", action="store_true", help="lo oscuro es lo caliente (material sobre fondo claro)")
    ap.add_argument("--niveles", default="0.1,0.85", help="punto negro y blanco de la intensidad (0..1)")
    ap.add_argument("--halo", type=float, default=16)
    ap.add_argument("--frio", default="", help="tramos fríos en segundos: 3.1-5.8,12-14")
    ap.add_argument("--sin-grano", action="store_true")
    ap.add_argument("--fuente", action="append", default=[],
                    help="fuente de calor x,y,sigma,ganancia en px (repetible); sin fuentes el halo va en todo")
    a = ap.parse_args()
    ds = load_ds(a.ds)
    mp = mapas(ds)
    fuentes = [tuple(float(v) for v in f.split(",")) for f in a.fuente]
    niv = tuple(float(x) for x in a.niveles.split(","))
    tramos = [tuple(float(x) for x in r.split("-")) for r in a.frio.split(",") if r]

    if a.entrada.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        im = Image.open(a.entrada).convert("RGB")
        piel = papel(im.width, im.height)
        g = None if a.sin_grano else np.random.default_rng(1).normal(0, 1, (im.height, im.width)).astype(np.float32)
        T = calor(im.width, im.height, fuentes)
        Image.fromarray(tenir(campo(im, a.invertir, a.halo, niv, T), mp, piel, g)).save(a.salida)
        print(a.salida)
        return

    W, H, fps = probe(a.entrada)
    piel = papel(W, H)
    T = calor(W, H, fuentes)
    rng = np.random.default_rng(2)
    granos = [rng.normal(0, 1, (H, W)).astype(np.float32) for _ in range(4)]
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", a.entrada, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-i", a.entrada, "-map", "0:v", "-map", "1:a?",
                            "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "copy", a.salida],
                           stdin=subprocess.PIPE)
    i = 0
    while True:
        buf = dec.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        t = i / fps
        frio = 1.0 if any(t0 <= t < t1 for t0, t1 in tramos) else 0.0
        g = None if a.sin_grano else granos[0 if frio else int(t * 12) % 4]   # grano a 12 fps; quieto en frío
        rgb = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        enc.stdin.write(tenir(campo(rgb, a.invertir, a.halo, niv, T), mp, piel, g, frio).tobytes())
        i += 1
    enc.stdin.close()
    enc.wait()
    print(a.salida, i, "fotogramas")


if __name__ == "__main__":
    main()
