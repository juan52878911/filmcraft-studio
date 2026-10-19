#!/usr/bin/env python3
"""Vista previa de un design system de video.

Uso: ds_preview.py DS [--out preview.png] [--frame FOTO_O_FOTOGRAMA.jpg] [--fc]

- Lámina PIL (rápida): paleta con roles y contrastes, cuatro maquetas 9:16 (título, contenido con
  marca + etiqueta + subtítulo, eco, cierre) dibujadas con las fuentes y tamaños del DS, y el flyer.
- --fc además monta la tarjeta de título y un plano de contenido en un proyecto FilmCraft temporal
  (headless) y los renderiza: prueba que FilmCraft tiene las fuentes y que los roles se ven igual.
"""
import argparse
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).parent))
from common import color, load_ds, pil_font  # noqa: E402
from ds_from_image import contrast  # noqa: E402
from fcstyle import Styler  # noqa: E402

W, H = 1080, 1920


def block(d, ds, role, text, cx, cy, fill_override=None, align=None, scale=1.0):
    r = ds["roles_texto"][role]
    f = pil_font(ds["fuentes"][r["fuente"]], r["tam"] * scale)
    lines = text.split("\n")
    bbs = [d.textbbox((0, 0), ln, font=f) for ln in lines]
    lh = max(b[3] - b[1] for b in bbs) * 1.18
    tw = max(b[2] - b[0] for b in bbs)
    th = lh * len(lines)
    al = align or r.get("align", "Center")
    x0 = cx - tw / 2 if al == "Center" else (cx - tw if al == "Right" else cx)
    y0 = cy - th / 2
    fondo = fill_override[1] if fill_override else r.get("fondo")
    if isinstance(fondo, list):
        fondo = fondo[0]
    tc = color(ds, fill_override[0] if fill_override else r.get("color", "claro"))
    if fondo:
        m = r.get("margen", 40) * scale * 0.6
        d.rectangle([x0 - m, y0 - m * 0.5, x0 + tw + m, y0 + th + m * 0.5], fill=color(ds, fondo))
    for i, ln in enumerate(lines):
        b = bbs[i]
        lx = x0 if al == "Left" else (x0 + (tw - (b[2] - b[0])) / 2 if al == "Center" else x0 + tw - (b[2] - b[0]))
        d.text((lx - b[0], y0 + i * lh - b[1] + (lh - (b[3] - b[1])) / 2), ln, font=f, fill=tc)


def bg(ds, key):
    p = ds["fondos"].get(key)
    return Image.open(p).convert("RGB").resize((W, H)) if p and Path(p).exists() else Image.new("RGB", (W, H), ds["paleta"]["fondo"])


def mock_title(ds):
    im = bg(ds, "titulo")
    d = ImageDraw.Draw(im)
    m = ds["marca"]
    block(d, ds, "tag", m.get("hashtag", "#Evento"), W * 0.29, H * 0.16)
    r = ds["roles_texto"]["titulo"]
    t = m.get("titulo", "TÍTULO DEL EVENTO")
    lines = t.split("\n") if "\n" in t else Styler.wrap(None, t, r.get("max_chars", 12))
    tam = r["tam"]
    f = pil_font(ds["fuentes"][r["fuente"]], tam)
    widest = max(f.getlength(ln) for ln in lines)
    if widest > W * (1 - 2 * r["x"]):                      # igual que Styler.title: encaja en el ancho
        tam = tam * W * (1 - 2 * r["x"]) / widest
        f = pil_font(ds["fuentes"][r["fuente"]], tam)
    y = H * r["y"]
    for ln in lines:
        d.text((W * r["x"], y), ln, font=f, fill=color(ds, r["color"]))
        y += tam * r.get("interlinea", 1.25)
    block(d, ds, "pill", m.get("titulo_pill", "PILL"), W * 0.5, H * 0.72)
    return im


def mock_content(ds, frame):
    if frame and Path(frame).exists():
        im = ImageOps.fit(Image.open(frame).convert("RGB"), (W, H))
    else:
        im = bg(ds, "plano")
    d = ImageDraw.Draw(im)
    block(d, ds, "marca", ds["marca"].get("barra", "MARCA"), W * 0.5, H * 0.06)
    block(d, ds, "etiqueta", "ETIQUETA", W * 0.5, H * 0.24)
    block(d, ds, "escalon", "ESCALÓN", W * 0.36, H * 0.36, fill_override=("oscuro", "acento2"))
    block(d, ds, "subtitulo", "Subtítulo de 20 c", W * 0.5, H * 0.78)
    return im


def mock_eco(ds):
    im = bg(ds, "plano")
    d = ImageDraw.Draw(im)
    r = ds["roles_texto"]["eco"]
    for i, (tc, fc) in enumerate(r["colores"]):
        block(d, ds, "eco", "100 USD", W * 0.5, H * (0.22 + i * r.get("paso_y", 0.125)), fill_override=(tc, fc))
    block(d, ds, "subtitulo", "nos dan 100 dólares.", W * 0.5, H * 0.78)
    return im


def mock_outro(ds):
    im = bg(ds, "cierre")
    d = ImageDraw.Draw(im)
    m = ds["marca"]
    r = ds["roles_texto"]["cierre"]
    f = pil_font(ds["fuentes"][r["fuente"]], r["tam"])
    y = H * r["y"]
    for w in m.get("cierre_palabras", ["CIERRE"]):
        d.text((W * r["x"], y), w, font=f, fill=color(ds, r["color"]))
        y += r["tam"] * r.get("interlinea", 1.25)
    block(d, ds, "meta", m.get("cierre_linea", ""), W * 0.5, H * 0.62)
    block(d, ds, "pill", m.get("cta", "SÍGUENOS"), W * 0.5, H * 0.69)
    block(d, ds, "pie", m.get("cierre_pie", ""), W * 0.5, H * 0.031)
    return im


def swatches(ds, w):
    pal = ds["paleta"]
    im = Image.new("RGB", (w, 300), "#FFFFFF")
    d = ImageDraw.Draw(im)
    f = pil_font({"familia": "Menlo", "estilo": "Bold"}, 22)
    keys = ["fondo", "rejilla", "claro", "acento1", "acento2", "acento3"]
    sw = w // len(keys)
    for i, k in enumerate(keys):
        h = pal[k]
        d.rectangle([i * sw + 8, 10, (i + 1) * sw - 8, 190], fill=h, outline="#000000")
        d.text((i * sw + 12, 198), f"{k}\n{h}", font=f, fill="#000000")
        if k.startswith("acento"):
            c_o, c_c = contrast(pal["oscuro"], h), contrast(pal["claro"], h)
            d.text((i * sw + 12, 252), f"osc {c_o:.1f} · cla {c_c:.1f}", font=pil_font({"familia": "Menlo"}, 18), fill="#333333")
    return im


def fc_frames(ds, tmp):
    """Monta la tarjeta de título y un plano de contenido en FilmCraft (headless) y los renderiza."""
    import subprocess
    from fcengine import Engine
    from fclib import CLI
    e = Engine.headless()
    lz = ds["lienzo"]
    e.new_project("ds-preview", lz["ancho"], lz["alto"], lz["fps"], ds["pistas"]["video"], ds["pistas"]["audio"])
    st = Styler(e, ds)
    e.place(ds["fondos"]["titulo"], "Main", 0, 2, audio=False)
    st.title(ds["marca"].get("titulo", "TÍTULO"), 0, 2, role="titulo")
    st.text("tag", ds["marca"].get("hashtag", "#Evento"), 0, 2, (0.29, 0.16))
    st.text("pill", ds["marca"].get("titulo_pill", "PILL"), 0, 2, (0.5, 0.72))
    e.place(ds["fondos"]["plano"], "Main", 2, 2, audio=False)
    st.text("marca", ds["marca"].get("barra", "MARCA"), 2, 2, (0.5, 0.06))
    st.text("etiqueta", "ETIQUETA", 2, 2, (0.5, 0.24))
    st.text("subtitulo", "Subtítulo de 20 c", 2, 2, (0.5, 0.78))
    proj = Path(tmp) / "ds-preview.fcproj"
    e.save_as(proj)
    e.close()
    outs = []
    for t in (1.5, 3.5):
        png = Path(tmp) / f"fc_{t}.png"
        subprocess.run([CLI, "--project", str(proj), "render", "--seconds", str(t), "--scale", "0.5", "--out", str(png),
                        "--allow-offline"], capture_output=True)
        if png.exists():
            outs.append(Image.open(png).convert("RGB").resize((W, H)))
    return outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ds")
    ap.add_argument("--out")
    ap.add_argument("--frame")
    ap.add_argument("--fc", action="store_true")
    a = ap.parse_args()
    ds = load_ds(a.ds)
    out = Path(a.out) if a.out else Path(ds["_dir"]) / "preview.png"
    mocks = [mock_title(ds), mock_content(ds, a.frame), mock_eco(ds), mock_outro(ds)]
    labels = ["PIL · título", "PIL · contenido", "PIL · eco", "PIL · cierre"]
    if a.fc:
        with tempfile.TemporaryDirectory(prefix="fcs_prev_") as tmp:
            fcs = fc_frames(ds, tmp)
        mocks += fcs
        labels += ["FilmCraft · título", "FilmCraft · contenido"][:len(fcs)]
    tw, th = 360, 640
    flyer = ds.get("match", {}).get("flyer")
    fl = Image.open(flyer).convert("RGB") if flyer and Path(flyer).exists() else None
    if fl:
        fl.thumbnail((tw * 1.3, th))
    cols = len(mocks) + (1 if fl else 0)
    Wb = cols * (tw + 20) + 40
    board = Image.new("RGB", (int(Wb + (fl.width - tw if fl else 0)), th + 470), "#FFFFFF")
    d = ImageDraw.Draw(board)
    d.text((24, 16), f"{ds['nombre']}  ·  {ds['id']}  ·  {ds['gramatica']}", font=pil_font({"familia": "Menlo", "estilo": "Bold"}, 28), fill="#000000")
    x = 24
    lf = pil_font({"familia": "Menlo"}, 18)
    for im, lb in zip(mocks, labels):
        board.paste(im.resize((tw, th)), (x, 70))
        d.text((x, 70 + th + 6), lb, font=lf, fill="#333333")
        x += tw + 20
    if fl:
        board.paste(fl, (x, 70))
        d.text((x, 70 + fl.height + 6), "flyer de referencia", font=lf, fill="#333333")
    board.paste(swatches(ds, board.width - 48), (24, 70 + th + 40))
    out.parent.mkdir(parents=True, exist_ok=True)
    board.save(out)
    print(out)


if __name__ == "__main__":
    main()
