#!/usr/bin/env python3
"""Valida un design system de video. Sale con código 1 si hay errores.

Uso: ds_validate.py DS [--json]

Comprueba: campos obligatorios, colores hex, referencias de color de los roles, fuentes instaladas,
assets (fondos, mattes, SFX) existentes, pistas de los roles declaradas, contraste del texto sobre su
fondo (≥ 4,5:1 en texto pequeño, ≥ 3:1 en titulares ≥ 60 px) y animaciones conocidas.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import font_file, load_ds  # noqa: E402
from ds_from_image import contrast  # noqa: E402

REQ = ["id", "gramatica", "lienzo", "paleta", "fuentes", "marca", "pistas", "roles_texto", "animaciones",
       "transiciones", "fondos", "mattes", "sfx", "musica", "grade", "audio", "estructura"]
PAL = ["fondo", "oscuro", "claro", "acento1"]
ANIMS = {"popIn", "wordReveal", "eco", "ninguna"}
ROLES_MIN = ["marca", "subtitulo", "etiqueta", "eco", "pill", "titulo", "cierre"]


def validate(ds):
    err, warn = [], []
    for k in REQ:
        if k not in ds:
            err.append(f"falta '{k}'")
    if err:
        return err, warn
    for k in PAL:
        if k not in ds["paleta"]:
            err.append(f"paleta sin '{k}'")
    for k, v in ds["paleta"].items():
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
            err.append(f"color no hex: {k}={v}")
    pal = ds["paleta"]

    def ok_ref(x):
        return x is None or (isinstance(x, str) and (x.startswith("#") or x in pal))
    vt = set(ds["pistas"]["video"])
    for r in ROLES_MIN:
        if r not in ds["roles_texto"]:
            err.append(f"falta el rol de texto '{r}'")
    for name, r in ds["roles_texto"].items():
        if r.get("fuente") not in ds["fuentes"]:
            err.append(f"rol {name}: fuente '{r.get('fuente')}' no declarada")
        for t in (r.get("pistas") or [r.get("pista")]):
            if t not in vt:
                err.append(f"rol {name}: pista '{t}' no está en pistas.video")
        if r.get("anim", "ninguna") not in ANIMS:
            err.append(f"rol {name}: animación '{r.get('anim')}' desconocida")
        pares = r.get("colores") or [[r.get("color", "claro"), f] for f in
                                     (r["fondo"] if isinstance(r.get("fondo"), list) else [r.get("fondo")])]
        for tc, bc in pares:
            if not ok_ref(tc) or not ok_ref(bc):
                err.append(f"rol {name}: color '{tc}'/'{bc}' no está en la paleta")
                continue
            bgc = (bc if bc and bc.startswith("#") else pal.get(bc)) if bc else pal["fondo"]
            txc = tc if tc.startswith("#") else pal[tc]
            c = contrast(txc, bgc)
            minimo = 3.0 if r.get("tam", 0) >= 60 else 4.5
            if c < minimo:
                (err if c < 2.5 else warn).append(f"rol {name}: contraste {c:.1f}:1 de {tc} sobre {bc or 'fondo'} (mínimo {minimo})")
    for k, f in ds["fuentes"].items():
        ff = font_file(f)
        if not ff or not Path(ff).exists():
            err.append(f"fuente '{k}' ({f['familia']} {f.get('estilo', '')}) no está instalada")
    for grp in ("fondos", "mattes"):
        for k, p in ds[grp].items():
            if not Path(p).exists():
                err.append(f"{grp}.{k}: no existe {p}")
    for k, p in ds["sfx"].get("_mapa_abs", {}).items():
        if not Path(p).exists():
            warn.append(f"sfx.{k}: no existe {p}")
    for k in ("blanco",):
        if k not in ds["mattes"]:
            err.append(f"mattes sin '{k}'")
    for t in ds["transiciones"].get("preferencia", []):
        if t not in ds["transiciones"]:
            err.append(f"transición '{t}' en preferencia pero sin definir")
    lz = ds["lienzo"]
    if not (lz.get("ancho") and lz.get("alto") and lz.get("fps")):
        err.append("lienzo necesita ancho, alto y fps")
    return err, warn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ds")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    ds = load_ds(a.ds)
    err, warn = validate(ds)
    if a.json:
        print(json.dumps({"ds": ds["id"], "ok": not err, "errores": err, "avisos": warn}, ensure_ascii=False, indent=1))
    else:
        print(f"DS {ds['id']}: {'OK' if not err else 'CON ERRORES'}")
        for e in err:
            print("  ✗", e)
        for w in warn:
            print("  !", w)
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
