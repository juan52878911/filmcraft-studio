#!/usr/bin/env python3
"""Vista previa de un DS de promo a partir de un render real: cabecera, fotogramas y paleta.

Uso: promo_preview.py DS VIDEO [--tiempos 0.5,3,...] [--cols N] [--out preview.png] [--thumb thumb.png]

Sin --tiempos toma 8 fotogramas repartidos. Escribe preview.png (y thumb.png) en la carpeta del DS si
no se indica otra ruta. A diferencia de ds_preview.py (maquetas PIL + FilmCraft), aquí manda el render.
"""
import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from common import font_file, load_ds  # noqa: E402
from ds_from_image import contrast  # noqa: E402


def grab(video, t, width):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", video, "-frames:v", "1", "-vf",
                          f"scale={width}:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                         capture_output=True, check=True).stdout
    from io import BytesIO
    return Image.open(BytesIO(raw)).convert("RGB")


def duration(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ds")
    ap.add_argument("video")
    ap.add_argument("--tiempos")
    ap.add_argument("--cols", type=int)
    ap.add_argument("--out")
    ap.add_argument("--thumb")
    a = ap.parse_args()
    ds = load_ds(a.ds)
    pal = ds["paleta"]
    dur = duration(a.video)
    ts = [float(x) for x in a.tiempos.split(",")] if a.tiempos else [dur * (k + 0.5) / 8 for k in range(8)]
    vertical = ds["lienzo"]["alto"] > ds["lienzo"]["ancho"]
    cols = a.cols or (len(ts) if vertical else 4)
    W = 2400
    gap = 16
    cw = (W - gap * (cols + 1)) // cols
    frames = [grab(a.video, t, cw) for t in ts]
    ch = frames[0].height
    rows = -(-len(frames) // cols)
    head, foot = 190, 200
    H = head + rows * (ch + gap) + gap + foot
    bg, ink = pal["fondo"], pal["claro"] if contrast(pal["claro"], pal["fondo"]) > 4 else pal["oscuro"]
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    tit = ImageFont.truetype(font_file(ds["fuentes"]["titular"]), 84,
                             index=9 if ds["fuentes"]["titular"]["archivo"].endswith("HelveticaNeue.ttc") else 0)
    meta = ImageFont.truetype(font_file(ds["fuentes"]["meta"]), 30)
    small = ImageFont.truetype(font_file(ds["fuentes"]["meta"]), 24)
    d.text((gap * 2, 110), ds["nombre"].upper(), font=tit, fill=pal["acento1"], anchor="ls")
    d.text((gap * 2, 160), f"{ds['id']} · {ds['gramatica']} · {ds['lienzo']['ancho']}x{ds['lienzo']['alto']} · "
                           f"{ds['promo']['bpm']} BPM · render real", font=meta, fill=ink, anchor="ls")
    for k, fr in enumerate(frames):
        x = gap + (k % cols) * (cw + gap)
        y = head + (k // cols) * (ch + gap)
        im.paste(fr, (x, y))
        d.text((x + 10, y + ch - 12), f"{ts[k]:.1f}s", font=meta, fill="#000000", anchor="ls")
        d.text((x + 8, y + ch - 14), f"{ts[k]:.1f}s", font=meta, fill="#FFFFFF", anchor="ls")
    y0 = H - foot + 30
    sw = (W - gap * 2) // len(pal)
    for k, (name, hexc) in enumerate(pal.items()):
        x = gap + k * sw
        d.rectangle([x, y0, x + sw - 12, y0 + 80], fill=hexc, outline=ink, width=2)
        d.text((x, y0 + 112), name, font=meta, fill=ink, anchor="ls")
        d.text((x, y0 + 146), f"{hexc} · {contrast(hexc, pal['fondo']):.1f}:1", font=small, fill=ink, anchor="ls")
    d_ = Path(ds["_dir"])
    out = Path(a.out) if a.out else d_ / "preview.png"
    im.save(out)
    thumb = Path(a.thumb) if a.thumb else d_ / "thumb.png"
    fr = frames[min(1, len(frames) - 1)].copy()
    fr.thumbnail((480, 480))
    fr.save(thumb)
    print(out, thumb)


if __name__ == "__main__":
    main()
