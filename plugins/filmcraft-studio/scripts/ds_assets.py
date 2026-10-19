#!/usr/bin/env python3
"""Genera los fondos y mattes de un DS a partir de su paleta (generaliza gen_bgs.py del Reto).

Uso: ds_assets.py DS_ID_O_DIR [--solo-faltantes]

Escribe en <ds>/assets/: bg-title, bg-plain, bg-cap, bg-outro (rejilla de celdas de 40 px con píxeles
de color en las esquinas), matte-blanco y un matte sólido por acento. Actualiza `fondos` y `mattes` del ds.json.
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from common import ds_dir, jload, jsave  # noqa: E402

C = 40   # celda de la rejilla en px (a 1080 de ancho)

# (x, y, w, h, color) en celdas sobre 27x48; colores por rol: a1, a2, a3
LAYOUTS = {
    "bg-title": [(0, 0, 3, 2, "a3"), (21, 3, 6, 3, "a1"), (24, 6, 3, 3, "a1"), (19, 4, 2, 2, "a2"), (22, 9, 2, 2, "a2"),
                 (0, 38, 5, 2, "a1"), (0, 40, 2, 2, "a2"), (1, 42, 1, 1, "a3"), (0, 46, 27, 2, "a2"), (23, 42, 4, 4, "a3"),
                 (25, 40, 2, 2, "a1")],
    "bg-plain": [],
    "bg-cap": [(0, 20, 27, 9, "a1"), (22, 18, 2, 2, "a2"), (0, 29, 3, 1, "a3")],
    "bg-outro": [(0, 0, 27, 3, "a2"), (24, 3, 3, 2, "a2"), (0, 40, 27, 2, "a1"), (0, 42, 2, 6, "a1"), (25, 36, 2, 2, "a3"),
                 (3, 44, 1, 1, "a3")],
}
NAMES = {"bg-title": "titulo", "bg-plain": "plano", "bg-cap": "cap", "bg-outro": "cierre"}


def mix(h1, h2, t):
    a = [int(h1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(h2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def make(ds, out, W, H, only_missing=False):
    pal = ds["paleta"]
    bg = pal["fondo"]
    grid = pal.get("rejilla") or mix(bg, pal.get("claro", "#FFFFFF"), 0.08)
    roles = {"a1": pal["acento1"], "a2": pal.get("acento2", pal["acento1"]), "a3": pal.get("acento3", pal["acento1"])}
    sx, sy = W / 1080, H / 1920
    out.mkdir(parents=True, exist_ok=True)
    fondos, mattes = {}, {}
    for name, cells in LAYOUTS.items():
        f = out / f"{name}.png"
        fondos[NAMES[name]] = f"assets/{f.name}"
        if only_missing and f.exists():
            continue
        im = Image.new("RGB", (W, H), bg)
        d = ImageDraw.Draw(im)
        for x in range(0, W, round(C * sx)):
            d.line([(x, 0), (x, H)], grid, 2)
        for y in range(0, H, round(C * sy)):
            d.line([(0, y), (W, y)], grid, 2)
        for x, y, w, h, c in cells:
            d.rectangle([x * C * sx, y * C * sy, (x + w) * C * sx - 1, (y + h) * C * sy - 1], fill=roles[c])
        im.save(f)
    for key, col in (("blanco", "#FFFFFF"), ("acento1", roles["a1"]), ("acento2", roles["a2"]), ("acento3", roles["a3"])):
        f = out / f"matte-{key}.png"
        mattes[key] = f"assets/{f.name}"
        if not (only_missing and f.exists()):
            Image.new("RGB", (W, H), col).save(f)
    return fondos, mattes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ds")
    ap.add_argument("--solo-faltantes", action="store_true")
    a = ap.parse_args()
    d = ds_dir(a.ds)
    ds = jload(d / "ds.json")
    W, H = ds["lienzo"]["ancho"], ds["lienzo"]["alto"]
    fondos, mattes = make(ds, d / "assets", W, H, a.solo_faltantes)
    ds["fondos"], ds["mattes"] = fondos, mattes
    jsave(d / "ds.json", ds)
    print(json.dumps({"fondos": fondos, "mattes": mattes}, ensure_ascii=False))


if __name__ == "__main__":
    main()
