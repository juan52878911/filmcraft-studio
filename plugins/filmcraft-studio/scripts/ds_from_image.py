#!/usr/bin/env python3
"""Crea la piel de un DS a partir de un flyer: paleta por k-means + gramática de un DS base.

Uso:
    ds_from_image.py FLYER --id mi-evento [--base sbg-brutalista-s5] [--out DIR] [--k 8]
                     [--recorte auto|no|x0,y0,x1,y1] [--marca '{"hashtag":"#X", ...}'] [--nombre "…"]
    ds_from_image.py FLYER --solo-paleta          # imprime la paleta y sale

- `--recorte auto` busca la franja con color (descarta capturas de Meetup, marcos y bandas grises).
- Roles: fondo = oscuro dominante; claro = el más claro (o blanco); acento1..3 = los más saturados con
  tonos distintos (≥ 25°), por área × saturación. El color del texto sobre cada acento se elige por contraste.
- Por defecto escribe en ${CLAUDE_PLUGIN_DATA}/design-systems/<id>/ y genera los assets (ds_assets.py).
"""
import argparse
import colorsys
import copy
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from common import USER_DS, ds_dir, jload, jsave  # noqa: E402


def to_hex(c):
    return "#%02X%02X%02X" % tuple(int(round(v)) for v in c)


def lum(h):
    """Luminancia relativa WCAG."""
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def autocrop(im):
    """Franja horizontal más larga con color (≥ 3 % de píxeles saturados por fila)."""
    a = np.asarray(im.convert("HSV")).astype(np.float32) / 255
    sat = (a[..., 1] > 0.45) & (a[..., 2] > 0.35)
    rows = sat.mean(axis=1) > 0.03
    best, cur, start = (0, len(rows)), 0, 0
    best_len = 0
    gap = 0
    for i, r in enumerate(list(rows) + [False]):
        if r:
            if cur == 0:
                start = i
            cur = i - start + 1
            gap = 0
        else:
            gap += 1
            if gap > len(rows) * 0.04 or i == len(rows):
                if cur > best_len:
                    best_len, best = cur, (start, start + cur)
                cur = 0
    y0, y1 = best
    if best_len < len(rows) * 0.2:
        return im, None
    pad = int(len(rows) * 0.01)
    box = (0, max(0, y0 - pad), im.width, min(im.height, y1 + pad))
    return im.crop(box), box


def kmeans(px, k=12, it=25, seed=7):
    rng = np.random.default_rng(seed)
    c = [px[rng.integers(len(px))]]
    for _ in range(1, k):                                  # k-means++
        d = np.min(((px[:, None, :] - np.array(c)[None]) ** 2).sum(-1), axis=1)
        c.append(px[rng.choice(len(px), p=d / d.sum())])
    c = np.array(c, dtype=np.float32)
    for _ in range(it):
        lab = np.argmin(((px[:, None, :] - c[None]) ** 2).sum(-1), axis=1)
        nc = np.array([px[lab == j].mean(0) if (lab == j).any() else c[j] for j in range(k)])
        if np.allclose(nc, c, atol=0.5):
            break
        c = nc
    share = np.bincount(lab, minlength=k) / len(px)
    return c, share, lab


def vivid(px):
    """Color representativo y vivo de un grupo: mediana del 30 % de píxeles más saturados."""
    mx, mn = px.max(1), px.min(1)
    sat = (mx - mn) / np.maximum(mx, 1)
    top = px[sat >= np.quantile(sat, 0.7)]
    return np.median(top, axis=0)


def palette(path, k=12, recorte="auto"):
    im = Image.open(path).convert("RGB")
    box = None
    if recorte == "auto":
        im, box = autocrop(im)
    elif recorte not in ("no", None):
        box = tuple(int(v) for v in recorte.split(","))
        im = im.crop(box)
    im.thumbnail((240, 240))
    px = np.asarray(im).reshape(-1, 3).astype(np.float32)
    cent, share, lab = kmeans(px, k)
    cl = []
    for j, (c, s) in enumerate(zip(cent, share)):
        rgb = [float(v) / 255 for v in c]
        h, l, _ = colorsys.rgb_to_hls(*rgb)
        _, sv, v = colorsys.rgb_to_hsv(*rgb)
        cl.append({"hex": to_hex(c), "area": round(float(s), 4), "tono": round(h * 360), "luz": round(l, 3),
                   "sat": round(sv, 3), "v": round(v, 3), "vivo": to_hex(vivid(px[lab == j])) if (lab == j).any() else to_hex(c)})
    box = [int(b) for b in box] if box else None
    cl.sort(key=lambda x: -x["area"])
    return cl, box


def roles(cl):
    dark = [c for c in cl if c["luz"] < 0.22]
    fondo = max(dark, key=lambda c: c["area"]) if dark else min(cl, key=lambda c: c["luz"])
    light = [c for c in cl if c["luz"] > 0.85]
    claro = max(light, key=lambda c: c["luz"])["hex"] if light else "#FFFFFF"
    acc = sorted([c for c in cl if c["sat"] > 0.45 and c["v"] > 0.45 and 0.25 < c["luz"] < 0.88],
                 key=lambda c: -(c["area"] ** 0.5) * (c["sat"] * c["v"]) ** 2)   # área y viveza
    picked = []
    for c in acc:
        if all(min(abs(c["tono"] - p["tono"]), 360 - abs(c["tono"] - p["tono"])) >= 25 for p in picked):
            picked.append(c)
        if len(picked) == 3:
            break
    if not picked:                                         # flyer sin color: acento = claro
        picked = [{"hex": claro, "tono": 0}]
    while len(picked) < 3:                                  # completa por rotación de tono
        h, l, s = colorsys.rgb_to_hls(*[int(picked[0]["hex"][i:i + 2], 16) / 255 for i in (1, 3, 5)])
        rot = (h + (len(picked) * 0.33)) % 1
        picked.append({"hex": to_hex(np.array(colorsys.hls_to_rgb(rot, l, s)) * 255), "tono": round(rot * 360),
                       "derivado": True})
    fh = fondo["hex"]
    rej = to_hex([int(fh[i:i + 2], 16) * 0.92 + int(claro[i:i + 2], 16) * 0.08 for i in (1, 3, 5)])
    ac = [p.get("vivo", p["hex"]) for p in picked]
    pal = {"fondo": fh, "rejilla": rej, "oscuro": fh, "claro": claro, "acento1": ac[0], "acento2": ac[1], "acento3": ac[2]}
    return pal, [p for p in picked if p.get("derivado")]


def fit_text_colors(ds):
    """Sobre cada fondo de color, el texto (oscuro/claro) con más contraste. Sin fondo propio, cuenta el del lienzo."""
    pal = ds["paleta"]
    for r in ds["roles_texto"].values():
        fondos = r.get("fondo") or "fondo"
        fl = fondos if isinstance(fondos, list) else [fondos]
        best = max(("oscuro", "claro"), key=lambda t: min(contrast(pal[t], pal[f]) for f in fl))
        if r.get("color") in ("oscuro", "claro"):
            r["color"] = best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flyer")
    ap.add_argument("--id")
    ap.add_argument("--base", default="sbg-brutalista-s5")
    ap.add_argument("--out")
    ap.add_argument("--k", type=int, default=12)
    ap.add_argument("--recorte", default="auto")
    ap.add_argument("--marca", default="{}", help="JSON con campos de marca a sustituir")
    ap.add_argument("--nombre")
    ap.add_argument("--solo-paleta", action="store_true")
    a = ap.parse_args()

    cl, box = palette(a.flyer, a.k, a.recorte)
    pal, derived = roles(cl)
    if a.solo_paleta:
        print(json.dumps({"recorte": box, "clusters": cl, "paleta": pal}, ensure_ascii=False, indent=1))
        return
    if not a.id:
        sys.exit("falta --id")
    base_dir = ds_dir(a.base)
    ds = copy.deepcopy(jload(base_dir / "ds.json"))
    out = Path(a.out) if a.out else USER_DS / a.id
    (out / "assets").mkdir(parents=True, exist_ok=True)
    ds["id"] = a.id
    ds["nombre"] = a.nombre or f"{a.id} (piel derivada de {Path(a.flyer).name} sobre {ds['gramatica']})"
    ds["version"] = 1
    ds["derivado_de"] = {"base": ds.get("id_base", a.base), "flyer": str(Path(a.flyer).resolve()), "recorte": box,
                         "clusters": cl, "acentos_derivados": [d["hex"] for d in derived]}
    ds["paleta"] = pal
    ds["marca"].update(json.loads(a.marca))
    ds["match"] = {"rutas": [], "palabras": [], "flyer": "assets/flyer.jpg",
                   "paleta_ref": [pal["fondo"], pal["acento1"], pal["acento2"], pal["acento3"], pal["claro"]]}
    fit_text_colors(ds)
    im = Image.open(a.flyer).convert("RGB")
    im.thumbnail((1200, 1200))
    im.save(out / "assets/flyer.jpg", quality=90)
    jsave(out / "ds.json", ds)
    from ds_assets import make
    fondos, mattes = make(ds, out / "assets", ds["lienzo"]["ancho"], ds["lienzo"]["alto"])
    ds["fondos"], ds["mattes"] = fondos, mattes
    jsave(out / "ds.json", ds)
    for f in ("NOTAS.md",):
        if (base_dir / f).exists():
            shutil.copy(base_dir / f, out / f)
    print(json.dumps({"ds": str(out), "paleta": pal, "recorte": box,
                      "acentos_derivados": [d["hex"] for d in derived]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
