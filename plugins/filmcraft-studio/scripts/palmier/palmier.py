"""Lector de una timeline de Palmier Pro para portarla a FilmCraft (scripts convert_*.py).

Configura por entorno:
    PALMIER_PROJECT  ruta al paquete .palmier      PALMIER_TIMELINE  nombre de la timeline
    PALMIER_GRAFICA  carpeta con matte-blanco.png  (para medios generados dentro de Palmier)
Los fotogramas de Palmier van en los fps de SU timeline (FPS); en FilmCraft se convierten con fr(f, FPS).
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fclib import FC, TPS, fr as _fr, ticks  # noqa: E402,F401

P = os.environ.get("PALMIER_PROJECT", "")
TL = os.environ.get("PALMIER_TIMELINE", "")
G = os.environ.get("PALMIER_GRAFICA", "")
W, H = 1080, 1920
FPS = 60


def load():
    global W, H, FPS
    if not P or not TL:
        sys.exit("define PALMIER_PROJECT y PALMIER_TIMELINE")
    j = json.load(open(P + "/project.json"))
    tl = [t for t in j["timelines"] if t["name"] == TL][0]
    W, H, FPS = tl.get("width", W), tl.get("height", H), tl.get("fps", FPS)
    media = {e["id"]: e for e in json.load(open(P + "/media.json"))["entries"]}
    return tl, {tr["name"]: tr for tr in tl["tracks"]}, media


def fr(frame):
    """Fotograma de la timeline de Palmier -> ticks (con los fps de esa timeline)."""
    return _fr(frame, FPS)


def path_of(e):
    src = e["source"]
    if "external" in src:
        return src["external"]["absolutePath"]
    if e["name"].startswith("matte-") and G:
        return f"{G}/{e['name']}.png"
    raise KeyError(e["name"])


INTERP = {"linear": "linear", "smooth": "autoBezier", "hold": "hold"}


def kfs(clip, name):
    t = clip.get(name)
    return t["keyframes"] if t and t.get("keyframes") else None
