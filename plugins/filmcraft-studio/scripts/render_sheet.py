#!/usr/bin/env python3
"""Hoja de fotogramas headless de un proyecto FilmCraft.

Uso:
    render_sheet.py PROYECTO.fcproj SALIDA.jpg 1.2 6.4 12.9 ... [--live] [--scale 0.25] [--cols 8]

--live  guarda antes el proyecto en la app abierta (canal de control 9876) para renderizar lo último.
Cada miniatura lleva su segundo arriba a la izquierda.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from fclib import CLI, FC  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("project")
ap.add_argument("out")
ap.add_argument("seconds", nargs="+", type=float)
ap.add_argument("--live", action="store_true")
ap.add_argument("--scale", type=float, default=0.25)
ap.add_argument("--cols", type=int, default=8)
a = ap.parse_args()

if a.live:
    FC().x("file.save", {})

tmp = Path(tempfile.mkdtemp(prefix="fc_sheet_"))
ims = []
for t in a.seconds:
    png = tmp / f"{t:08.2f}.png"
    r = subprocess.run([CLI, "--project", a.project, "render", "--seconds", str(t), "--scale", str(a.scale),
                        "--out", str(png), "--allow-offline"], capture_output=True, text=True)
    if not png.exists():
        print(f"fallo en {t}s: {r.stderr.strip()[-200:]}", file=sys.stderr)
        continue
    im = Image.open(png).convert("RGB")
    im.thumbnail((270, 480))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 58, 15], fill="black")
    d.text((3, 2), f"{t:.2f}", fill="yellow")
    ims.append(im)
if not ims:
    sys.exit("no se renderizó ningún fotograma")
cols = min(a.cols, len(ims))
rows = (len(ims) + cols - 1) // cols
W, H = ims[0].size
sheet = Image.new("RGB", (cols * (W + 4), rows * (H + 4)), "white")
for i, im in enumerate(ims):
    sheet.paste(im, ((i % cols) * (W + 4), (i // cols) * (H + 4)))
sheet.save(a.out, quality=85)
print(a.out, sheet.size)
