#!/usr/bin/env python3
"""Catálogo de design systems y ciclo crear → ver → modificar → aprobar.

    ds_studio.py catalogo [--hoja catalogo.png]          # DS aprobados (+ precargados) con miniatura
    ds_studio.py crear --id X [--spec spec.json|'{…}'] [--flyer F] [--base sbg-brutalista-s5] [--frame foto.jpg]
    ds_studio.py modificar X --spec '{…}' [--frame foto.jpg]
    ds_studio.py aprobar X                                # borrador -> catálogo
    ds_studio.py borradores

Los borradores viven en <datos>/borradores/<id>/ y no salen en el catálogo hasta aprobarlos; al aprobar
pasan a <datos>/design-systems/<id>/. <datos> = $CLAUDE_PLUGIN_DATA o ~/.cache/filmcraft-studio; el
catálogo puede ir a otra carpeta con $FILMCRAFT_DS_CATALOGO.

`spec` traduce una descripción en lenguaje natural (la escribe el modelo):
{
 "nombre": "…", "descripcion": "una línea",
 "paleta": {"fondo": "#…", "claro": "#…", "acento1": "#…", "acento2": "#…", "acento3": "#…"},
 "fuentes": {"titular": {"familia": "Futura", "estilo": "Bold"}, "ui": {…}},
 "escala_texto": 1.0,                     # multiplica todos los tamaños
 "animacion": "suave|normal|energica",    # popIn, aparición por palabras y transiciones preferidas
 "marca": {"barra": "…", "hashtag": "…", "titulo": "L1\\nL2", "cta": "…", …},
 "roles_texto": {"subtitulo": {"tam": 70}}, "musica": {…}, "grade": {…}   # cualquier otra clave se fusiona
}
"""
import argparse
import copy
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from common import DRAFT_DS, ROOT, USER_DS, ds_dir, jload, jsave, list_ds, load_ds, pil_font  # noqa: E402

DRAFTS = DRAFT_DS
TONOS = {
    "suave": {"popIn": {"escala": [[0, 85], [10, 102], [18, 100]], "opacidad": [[0, 0], [10, 100]]},
              "wordReveal": {"paso_f": 14, "fade_f": 12, "dy": 18},
              "preferencia": ["barrido_camara", "matte", "flash", "corte"]},
    "normal": {"popIn": {"escala": [[0, 70], [9, 105], [15, 100]], "opacidad": [[0, 0], [7, 100]]},
               "wordReveal": {"paso_f": 11, "fade_f": 9, "dy": 26},
               "preferencia": ["barrido_camara", "flash", "matte", "glitch", "corte"]},
    "energica": {"popIn": {"escala": [[0, 60], [8, 108], [14, 100]], "opacidad": [[0, 0], [6, 100]]},
                 "wordReveal": {"paso_f": 10, "fade_f": 8, "dy": 30},
                 "preferencia": ["barrido_camara", "flash", "matte", "glitch", "corte"]},
}


def merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            merge(a[k], v)
        else:
            a[k] = v
    return a


def apply_spec(ds, spec):
    spec = copy.deepcopy(spec)
    esc = spec.pop("escala_texto", None)
    tono = spec.pop("animacion", None)
    if esc and esc != 1:
        for r in ds["roles_texto"].values():
            r["tam"] = round(r["tam"] * esc, 1)
    if tono:
        t = TONOS[tono.replace("é", "e")]
        ds["animaciones"]["popIn"] = t["popIn"]
        ds["animaciones"]["wordReveal"] = t["wordReveal"]
        ds["transiciones"]["preferencia"] = [p for p in t["preferencia"] if p in ds["transiciones"]]
        ds["ritmo"]["energia"] = {"suave": "baja", "normal": "media", "energica": "alta"}[tono.replace("é", "e")]
    pal = spec.get("paleta", {})
    if "fondo" in pal:
        pal.setdefault("oscuro", pal["fondo"])
        if "rejilla" not in pal:
            f, c = pal["fondo"], pal.get("claro", ds["paleta"]["claro"])
            pal["rejilla"] = "#%02X%02X%02X" % tuple(round(int(f[i:i + 2], 16) * 0.92 + int(c[i:i + 2], 16) * 0.08) for i in (1, 3, 5))
    for k, f in spec.get("fuentes", {}).items():           # fuente nueva: el archivo de la vieja ya no vale
        if "familia" in f and "archivo" not in f and k in ds["fuentes"]:
            ds["fuentes"][k].pop("archivo", None)
    merge(ds, spec)
    for k, f in ds["fuentes"].items():                     # una fuente cambiada pierde el archivo viejo
        if f.get("archivo") and Path(f["archivo"]).expanduser().exists():
            continue
        f.pop("archivo", None)
    from ds_from_image import fit_text_colors
    fit_text_colors(ds)
    ds["match"]["paleta_ref"] = [ds["paleta"][k] for k in ("fondo", "acento1", "acento2", "acento3", "claro")]
    return ds


def regen(d, frame=None):
    from ds_assets import make
    ds = jload(d / "ds.json")
    ds["fondos"], ds["mattes"] = make(ds, d / "assets", ds["lienzo"]["ancho"], ds["lienzo"]["alto"])
    jsave(d / "ds.json", ds)
    v = subprocess.run([sys.executable, str(Path(__file__).parent / "ds_validate.py"), str(d), "--json"], capture_output=True, text=True)
    cmd = [sys.executable, str(Path(__file__).parent / "ds_preview.py"), str(d), "--fc", "--out", str(d / "preview.png")]
    if frame:
        cmd += ["--frame", frame]
    subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(v.stdout or "{}"), d / "preview.png"


def load_spec(s):
    if not s:
        return {}
    if s.lstrip().startswith("{"):
        return json.loads(s)
    return jload(Path(s))


def thumb(d):
    """Miniatura 9:16 (maqueta de título PIL) para el catálogo."""
    t = d / "thumb.png"
    if t.exists() and t.stat().st_mtime >= (d / "ds.json").stat().st_mtime:
        return t
    from ds_preview import mock_content, mock_title
    ds = load_ds(d)
    a, b = mock_title(ds).resize((270, 480)), mock_content(ds, None).resize((270, 480))
    im = Image.new("RGB", (548, 480), "white")
    im.paste(a, (0, 0))
    im.paste(b, (278, 0))
    im.save(t)
    return t


def catalogo(hoja=None):
    out = []
    for d in list_ds():
        if DRAFTS in d.parents:
            continue
        ds = jload(d / "ds.json")
        out.append({"id": ds["id"], "nombre": ds.get("nombre", ds["id"]), "descripcion": ds.get("descripcion", "")[:160],
                    "gramatica": ds.get("gramatica"), "precargado": ROOT in d.parents, "dir": str(d),
                    "miniatura": str(thumb(d)), "preview": str(d / "preview.png") if (d / "preview.png").exists() else None})
    if hoja and out:
        W = 548
        f = pil_font({"familia": "Menlo", "estilo": "Bold"}, 20)
        fs = pil_font({"familia": "Menlo"}, 15)
        im = Image.new("RGB", (len(out) * (W + 24) + 24, 600), "white")
        d = ImageDraw.Draw(im)
        for i, c in enumerate(out):
            x = 24 + i * (W + 24)
            d.text((x, 14), f"{i + 1}. {c['id']}", font=f, fill="#000000")
            d.text((x, 42), c["nombre"][:58], font=fs, fill="#444444")
            im.paste(Image.open(c["miniatura"]).convert("RGB"), (x, 80))
        Path(hoja).parent.mkdir(parents=True, exist_ok=True)
        im.save(hoja)
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("catalogo")
    c.add_argument("--hoja")
    c = sub.add_parser("crear")
    c.add_argument("--id", required=True)
    c.add_argument("--spec")
    c.add_argument("--flyer")
    c.add_argument("--base", default="sbg-brutalista-s5")
    c.add_argument("--frame")
    c = sub.add_parser("modificar")
    c.add_argument("id")
    c.add_argument("--spec", required=True)
    c.add_argument("--frame")
    c = sub.add_parser("aprobar")
    c.add_argument("id")
    sub.add_parser("borradores")
    a = ap.parse_args()

    if a.cmd == "catalogo":
        print(json.dumps(catalogo(a.hoja), ensure_ascii=False, indent=1))
    elif a.cmd == "borradores":
        print(json.dumps([p.name for p in sorted(DRAFTS.glob("*")) if (p / "ds.json").exists()], ensure_ascii=False))
    elif a.cmd == "crear":
        d = DRAFTS / a.id
        if d.exists():
            shutil.rmtree(d)
        spec = load_spec(a.spec)
        if a.flyer:
            subprocess.run([sys.executable, str(Path(__file__).parent / "ds_from_image.py"), a.flyer, "--id", a.id,
                            "--base", a.base, "--out", str(d)], check=True, capture_output=True)
        else:
            src = ds_dir(a.base)
            d.mkdir(parents=True)
            ds = jload(src / "ds.json")
            (d / "assets").mkdir()                            # fondos y mattes se regeneran con la paleta nueva
            ds["id"] = a.id
            ds["derivado_de"] = {"base": ds.get("id"), "descripcion": True}
            jsave(d / "ds.json", ds)
        ds = jload(d / "ds.json")
        ds["id"] = a.id
        ds["match"] = {"rutas": [], "palabras": [], "flyer": ds.get("match", {}).get("flyer") if a.flyer else None, "paleta_ref": []}
        ds = apply_spec(ds, spec)
        ds["estado"] = {"borrador": True, "creado": str(date.today()), "iteracion": 1, "spec": spec}
        jsave(d / "ds.json", ds)
        val, prev = regen(d, a.frame)
        print(json.dumps({"borrador": str(d), "preview": str(prev), "validacion": val, "paleta": ds["paleta"]}, ensure_ascii=False, indent=1))
    elif a.cmd == "modificar":
        d = DRAFTS / a.id
        if not d.exists():                                    # modificar uno aprobado = nuevo borrador
            src = ds_dir(a.id)
            shutil.copytree(src, d)
        ds = jload(d / "ds.json")
        spec = load_spec(a.spec)
        ds = apply_spec(ds, spec)
        st = ds.setdefault("estado", {"borrador": True})
        st["iteracion"] = st.get("iteracion", 1) + 1
        st.setdefault("cambios", []).append(spec)
        jsave(d / "ds.json", ds)
        val, prev = regen(d, a.frame)
        print(json.dumps({"borrador": str(d), "preview": str(prev), "validacion": val, "iteracion": st["iteracion"]}, ensure_ascii=False, indent=1))
    elif a.cmd == "aprobar":
        d = DRAFTS / a.id
        if not d.exists():
            sys.exit(f"no hay borrador '{a.id}'")
        val = subprocess.run([sys.executable, str(Path(__file__).parent / "ds_validate.py"), str(d)], capture_output=True, text=True)
        if val.returncode:
            sys.exit("no se puede aprobar, la validación falla:\n" + val.stdout)
        ds = jload(d / "ds.json")
        ds["estado"] = {"borrador": False, "aprobado": str(date.today()), "iteraciones": ds.get("estado", {}).get("iteracion", 1)}
        jsave(d / "ds.json", ds)
        dest = USER_DS / a.id
        if dest.exists():
            shutil.move(str(dest), str(USER_DS / f"{a.id}.anterior-{date.today()}"))
        USER_DS.mkdir(parents=True, exist_ok=True)
        shutil.move(str(d), str(dest))
        thumb(dest)
        print(json.dumps({"aprobado": a.id, "catalogo": str(dest)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
