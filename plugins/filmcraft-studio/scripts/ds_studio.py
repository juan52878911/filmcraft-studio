#!/usr/bin/env python3
"""Catálogo de design systems y ciclo crear → ver → modificar → aprobar.

    ds_studio.py catalogo [--hoja catalogo.png]          # DS aprobados (+ precargados) con miniatura
    ds_studio.py crear --id X [--spec spec.json|'{…}'] [--flyer F] [--base sbg-brutalista-s5] [--frame foto.jpg]
    ds_studio.py modificar X --spec '{…}' [--frame foto.jpg]
    ds_studio.py aprobar X                                # borrador -> catálogo
    ds_studio.py borradores
    ds_studio.py ver X                                    # dónde está, estado, iteración, paleta y vista previa
    ds_studio.py descartar X                              # borrador -> papelera (<datos>/papelera/), nunca rm

Los ids son slugs [a-z0-9-] (sin «..» ni «/»); se comprueban en todos los subcomandos.
Con un DS de promo (clave `promo`), crear/modificar regeneran los fondos con promo_fondos.py (la piel de su
gramática), no con la rejilla brutalista de ds_assets.py.

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
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from common import DATA, DRAFT_DS, ROOT, USER_DS, ds_dir, jload, jsave, list_ds, load_ds, pil_font  # noqa: E402

DRAFTS = DRAFT_DS
THUMBS = DATA / "thumbs"          # miniaturas de los DS precargados: la carpeta del plugin puede ser de solo lectura
PAPELERA = DATA / "papelera"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def check_id(ds_id):
    """Slug [a-z0-9-]: un id con «..» o «/» sacaría las rutas de borradores y catálogo (y rmtree borraría fuera)."""
    if not isinstance(ds_id, str) or not ID_RE.fullmatch(ds_id) or ".." in ds_id:
        raise SystemExit(f"id de DS no válido: {ds_id!r} (solo minúsculas, cifras y guiones; p. ej. mi-marca-2)")
    return ds_id


def dentro(p, base):
    """p está dentro de base (rutas resueltas)."""
    p, base = Path(p).resolve(), Path(base).resolve()
    return p == base or base in p.parents
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
        if tono.replace("é", "e") not in TONOS:
            raise SystemExit(f"animacion '{tono}' desconocida; usa: {', '.join(TONOS)}")
        t = TONOS[tono.replace("é", "e")]
        ds["animaciones"]["popIn"] = t["popIn"]
        ds["animaciones"]["wordReveal"] = t["wordReveal"]
        ds["transiciones"]["preferencia"] = [p for p in t["preferencia"] if p in ds["transiciones"]]
        ds.setdefault("ritmo", {})["energia"] = {"suave": "baja", "normal": "media", "energica": "alta"}[tono.replace("é", "e")]
    pal = spec.get("paleta", {})
    from ds_from_image import contrast                     # claro = el luminoso; oscuro = cajas/tinta (esquema.md)
    if "claro" in pal and "oscuro" not in pal and "fondo" in pal \
            and contrast(pal["claro"], "#000000") < contrast(pal["fondo"], "#000000") and \
            contrast(pal["fondo"], "#000000") > 10:              # tema claro con «claro» = color del texto
        print(f"aviso: 'claro' ({pal['claro']}) es la tinta de un tema claro: pasa a 'oscuro' y 'claro' = fondo",
              file=sys.stderr)
        pal["oscuro"], pal["claro"] = pal["claro"], pal["fondo"]
    if "claro" in pal or "oscuro" in pal:
        c, o = pal.get("claro", ds["paleta"]["claro"]), pal.get("oscuro", ds["paleta"]["oscuro"])
        if contrast(c, "#000000") < contrast(o, "#000000"):
            pal["claro"], pal["oscuro"] = o, c
            print(f"aviso: 'claro' ({c}) era más oscuro que 'oscuro' ({o}); los intercambio", file=sys.stderr)
    if "fondo" in pal:
        f = pal["fondo"]
        claro_fondo = sum(int(f[i:i + 2], 16) for i in (1, 3, 5)) / 765 > 0.5
        pal.setdefault("oscuro", "#1A1A1F" if claro_fondo else f)   # con fondo claro, "oscuro" tiene que ser oscuro de verdad
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
    """Regenera fondos/mattes, valida y rehace la vista previa. Devuelve (validacion, preview|None, error|None).

    Nunca devuelve un preview.png viejo: se borra antes y, si la vista previa falla, preview es None.
    """
    here = Path(__file__).parent
    ds = jload(d / "ds.json")
    if "promo" in ds:                                       # DS de promo: la piel de su gramática, no la rejilla
        r = subprocess.run([sys.executable, str(here / "promo_fondos.py"), str(d)], capture_output=True, text=True)
        if r.returncode:
            raise SystemExit("promo_fondos.py falló:\n" + (r.stderr or r.stdout)[-600:])
    else:
        from ds_assets import make
        ds["fondos"], ds["mattes"] = make(ds, d / "assets", ds["lienzo"]["ancho"], ds["lienzo"]["alto"])
        jsave(d / "ds.json", ds)
    v = subprocess.run([sys.executable, str(here / "ds_validate.py"), str(d), "--json"], capture_output=True, text=True)
    try:
        val = json.loads(v.stdout)
    except json.JSONDecodeError:
        val = {"ok": False, "errores": [f"ds_validate.py no terminó: {(v.stderr or v.stdout)[-400:]}"], "avisos": []}
    prev = d / "preview.png"
    prev.unlink(missing_ok=True)
    (d / "thumb.png").unlink(missing_ok=True)
    cmd = [sys.executable, str(here / "ds_preview.py"), str(d), "--fc", "--out", str(prev)]
    if frame:
        cmd += ["--frame", frame]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not prev.exists():
        return val, None, (r.stderr or r.stdout or "sin salida")[-600:]
    st = ds.get("estado", {})
    n = st.get("iteracion")
    if n:                                                   # copia numerada para comparar iteraciones
        shutil.copy2(prev, d / f"preview-{n}.png")
    return val, prev, None


HEX = re.compile(r"#[0-9A-Fa-f]{6}")


def load_spec(s):
    """spec como JSON en línea o ruta a un .json; un spec roto sale con mensaje, no con traza."""
    if not s:
        return {}
    try:
        spec = json.loads(s) if s.lstrip().startswith("{") else jload(Path(s))
    except json.JSONDecodeError as ex:
        raise SystemExit(f"--spec no es JSON válido: {ex}") from None
    except OSError as ex:
        raise SystemExit(f"--spec: no puedo leer {s}: {ex.strerror or ex}") from None
    if not isinstance(spec, dict):
        raise SystemExit("--spec tiene que ser un objeto JSON {…}")
    check_spec(spec)
    return spec


def check_spec(spec):
    """Lo que apply_spec rechazaría a mitad (o con traza), comprobado ANTES de crear nada en disco."""
    tono = spec.get("animacion")
    if tono is not None and str(tono).replace("é", "e") not in TONOS:
        raise SystemExit(f"animacion '{tono}' desconocida; usa: {', '.join(TONOS)}")
    pal = spec.get("paleta", {})
    if not isinstance(pal, dict):
        raise SystemExit("spec.paleta tiene que ser un objeto {\"fondo\": \"#RRGGBB\", …}")
    malos = [f"{k}={v!r}" for k, v in pal.items() if not (isinstance(v, str) and HEX.fullmatch(v))]
    if malos:
        raise SystemExit(f"spec.paleta: colores no hex ({', '.join(malos)}); usa #RRGGBB")
    esc = spec.get("escala_texto")
    if esc is not None and not (isinstance(esc, (int, float)) and esc > 0):
        raise SystemExit(f"escala_texto tiene que ser un número > 0 (recibido {esc!r})")


def thumb(d):
    """Miniatura (maqueta de título y contenido PIL) para el catálogo.

    Usa thumb.png del DS si existe. Para un DS precargado (dentro del plugin) no escribe en el plugin: la
    genera en <datos>/thumbs/<id>.png. Un DS de promo con thumb.png la conserva (sale de un render real).
    """
    t = d / "thumb.png"
    precargado = dentro(d, ROOT)
    if t.exists() and (precargado or "promo" in jload(d / "ds.json")
                       or t.stat().st_mtime >= (d / "ds.json").stat().st_mtime):
        return t
    if precargado:
        t = THUMBS / f"{d.name}.png"
        if t.exists() and t.stat().st_mtime >= (d / "ds.json").stat().st_mtime:
            return t
    from ds_preview import mock_content, mock_title
    ds = load_ds(d)
    a, b = mock_title(ds), mock_content(ds, None)
    a.thumbnail((270, 480))
    b.thumbnail((270, 480))
    im = Image.new("RGB", (548, 480), "white")
    im.paste(a, (0, 0))
    im.paste(b, (278, 0))
    t.parent.mkdir(parents=True, exist_ok=True)
    im.save(t)
    return t


def catalogo(hoja=None):
    out = []
    for d in list_ds():
        if DRAFTS in d.parents:
            continue
        ds = jload(d / "ds.json")
        try:
            mini, err = str(thumb(d)), None
        except Exception as ex:  # noqa: BLE001 - un DS roto no tumba el catálogo entero
            mini, err = None, f"{type(ex).__name__}: {ex}"[:300]
            print(f"aviso: sin miniatura para {d.name}: {err}", file=sys.stderr)
        c = {"id": ds.get("id", d.name), "nombre": ds.get("nombre", ds.get("id", d.name)),
             "descripcion": ds.get("descripcion", "")[:160], "gramatica": ds.get("gramatica"),
             "precargado": dentro(d, ROOT), "dir": str(d), "miniatura": mini,
             "preview": str(d / "preview.png") if (d / "preview.png").exists() else None}
        if err:
            c["error_miniatura"] = err
        out.append(c)
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
            if c["miniatura"]:
                mi = Image.open(c["miniatura"]).convert("RGB")
                mi.thumbnail((W, 480))
                im.paste(mi, (x, 80))
            else:
                d.rectangle([x, 80, x + W, 560], outline="#CC0000", width=3)
                d.text((x + 12, 300), "sin miniatura", font=fs, fill="#CC0000")
        Path(hoja).parent.mkdir(parents=True, exist_ok=True)
        im.save(hoja)
    return out


def a_papelera(d):
    """Mueve una carpeta a <datos>/papelera/<nombre>-<fecha-hora> (recuperable; nunca rm)."""
    PAPELERA.mkdir(parents=True, exist_ok=True)
    dest = PAPELERA / f"{d.name}-{datetime.now():%Y%m%d-%H%M%S-%f}"
    shutil.move(str(d), str(dest))
    return dest


def ver(ds_id):
    d = DRAFTS / ds_id if (DRAFTS / ds_id / "ds.json").exists() else ds_dir(ds_id)
    ds = jload(d / "ds.json")
    donde = "borrador" if dentro(d, DRAFTS) else ("precargado" if dentro(d, ROOT) else "catalogo")
    previews = sorted(str(p) for p in d.glob("preview*.png"))
    previews += sorted(str(p) for p in (DATA / "previews" / d.name).glob("preview*.png"))   # ds_preview.py sin --out
    return {"id": ds.get("id"), "nombre": ds.get("nombre"), "donde": donde, "dir": str(d),
            "gramatica": ds.get("gramatica"), "lienzo": ds.get("lienzo"), "promo": "promo" in ds,
            "estado": ds.get("estado"), "derivado_de": ds.get("derivado_de"), "paleta": ds.get("paleta"),
            "previews": previews}


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
    c.add_argument("--forzar", action="store_true", help="rehace el borrador si ya existe (el viejo va a la papelera)")
    c = sub.add_parser("modificar")
    c.add_argument("id")
    c.add_argument("--spec", required=True)
    c.add_argument("--frame")
    c = sub.add_parser("aprobar")
    c.add_argument("id")
    sub.add_parser("borradores")
    c = sub.add_parser("ver")
    c.add_argument("id")
    c = sub.add_parser("descartar")
    c.add_argument("id")
    a = ap.parse_args()
    for k in ("id", "base"):
        if getattr(a, k, None) is not None and not (k == "base" and Path(a.base).expanduser().is_dir()):
            check_id(getattr(a, k))

    if a.cmd == "catalogo":
        print(json.dumps(catalogo(a.hoja), ensure_ascii=False, indent=1))
    elif a.cmd == "borradores":
        print(json.dumps([p.name for p in sorted(DRAFTS.glob("*")) if (p / "ds.json").exists()], ensure_ascii=False))
    elif a.cmd == "ver":
        print(json.dumps(ver(a.id), ensure_ascii=False, indent=1))
    elif a.cmd == "descartar":
        d = DRAFTS / a.id
        if not d.exists() or not dentro(d, DRAFTS) or d.resolve() == DRAFTS.resolve():
            sys.exit(f"no hay borrador '{a.id}' (solo se descartan borradores; un DS aprobado no se toca)")
        print(json.dumps({"descartado": a.id, "papelera": str(a_papelera(d))}, ensure_ascii=False))
    elif a.cmd == "crear":
        d = DRAFTS / a.id
        if not dentro(d, DRAFTS) or d.resolve() == DRAFTS.resolve():
            sys.exit(f"id fuera de borradores: {a.id}")
        if d.exists() and not a.forzar:
            sys.exit(f"ya hay un borrador '{a.id}': modifícalo, descártalo o usa --forzar")
        spec = load_spec(a.spec)                              # antes de tocar el disco: un spec malo no deja nada
        if a.flyer and not Path(a.flyer).is_file():
            sys.exit(f"--flyer: no existe {a.flyer}")
        if d.exists():
            a_papelera(d)
        try:
            res = crear(a, d, spec)
        except BaseException:
            # nada de borradores a medias: el reintento daría «ya hay un borrador»
            if d.exists() and dentro(d, DRAFTS) and d.resolve() != DRAFTS.resolve():
                shutil.rmtree(d, ignore_errors=True)
            raise
        print(json.dumps(res, ensure_ascii=False, indent=1))
    elif a.cmd == "modificar":
        d = DRAFTS / a.id
        nuevo = not d.exists()
        if nuevo:                                             # modificar uno aprobado = nuevo borrador
            src = ds_dir(a.id)
            spec = load_spec(a.spec)
            shutil.copytree(src, d, ignore=shutil.ignore_patterns("preview*.png", "thumb.png"))
        else:
            spec = load_spec(a.spec)
        try:
            ds = jload(d / "ds.json")
            ds = apply_spec(ds, spec)
            st = ds.setdefault("estado", {})
            st["borrador"] = True                             # copia de un aprobado: vuelve a ser borrador
            st.pop("aprobado", None)
            st["iteracion"] = st.pop("iteraciones", None) or st.get("iteracion", 1)
            st["iteracion"] += 1
            st.setdefault("cambios", []).append(spec)
            jsave(d / "ds.json", ds)
        except BaseException:
            if nuevo:
                shutil.rmtree(d, ignore_errors=True)
            raise
        val, prev, perr = regen(d, a.frame)
        res = {"borrador": str(d), "preview": str(prev) if prev else None, "validacion": val, "iteracion": st["iteracion"]}
        if perr:
            res["error_preview"] = perr
        print(json.dumps(res, ensure_ascii=False, indent=1))
    elif a.cmd == "aprobar":
        d = DRAFTS / a.id
        if not d.exists():
            sys.exit(f"no hay borrador '{a.id}'")
        val = subprocess.run([sys.executable, str(Path(__file__).parent / "ds_validate.py"), str(d)], capture_output=True, text=True)
        if val.returncode:
            motivo = "\n".join(x for x in (val.stdout.strip(), val.stderr.strip()[-800:]) if x) or f"código {val.returncode}, sin salida"
            sys.exit("no se puede aprobar, la validación falla:\n" + motivo)
        ds = jload(d / "ds.json")
        ds["estado"] = {"borrador": False, "aprobado": str(date.today()), "iteraciones": ds.get("estado", {}).get("iteracion", 1)}
        jsave(d / "ds.json", ds)
        dest = USER_DS / a.id
        if dest.exists():
            shutil.move(str(dest), str(USER_DS / f"{a.id}.anterior-{datetime.now():%Y-%m-%d-%H%M%S}"))
        USER_DS.mkdir(parents=True, exist_ok=True)
        shutil.move(str(d), str(dest))
        try:
            thumb(dest)
        except Exception as ex:  # noqa: BLE001
            print(f"aviso: sin miniatura ({ex})", file=sys.stderr)
        print(json.dumps({"aprobado": a.id, "catalogo": str(dest)}, ensure_ascii=False))


def crear(a, d, spec):
    """Crea el borrador d (que no existe) desde el flyer o el DS base y devuelve el resumen."""
    if a.flyer:
        r = subprocess.run([sys.executable, str(Path(__file__).parent / "ds_from_image.py"), a.flyer, "--id", a.id,
                            "--base", a.base, "--out", str(d)], capture_output=True, text=True)
        if r.returncode:
            msg = (r.stderr or r.stdout or "sin salida").strip()
            if "Traceback" in msg:                        # de una traza del hijo basta la última línea: el motivo
                msg = msg.splitlines()[-1]
            raise SystemExit(f"ds_from_image.py no pudo sacar el DS de {a.flyer} (código {r.returncode}): {msg[-600:]}")
    else:
        src = ds_dir(a.base)
        d.mkdir(parents=True)
        ds = jload(src / "ds.json")
        (d / "assets").mkdir()                            # fondos y mattes se regeneran con la paleta nueva
        if (src / "assets" / "sfx").is_dir():             # los SFX no dependen de la paleta: se heredan del base
            shutil.copytree(src / "assets" / "sfx", d / "assets" / "sfx")
        ds["derivado_de"] = {"base": ds.get("id", a.base), "descripcion": True}   # antes de cambiar el id
        ds["id"] = a.id
        jsave(d / "ds.json", ds)
    ds = jload(d / "ds.json")
    ds["id"] = a.id
    ds["match"] = {"rutas": [], "palabras": [], "flyer": ds.get("match", {}).get("flyer") if a.flyer else None, "paleta_ref": []}
    ds = apply_spec(ds, spec)
    ds["estado"] = {"borrador": True, "creado": str(date.today()), "iteracion": 1, "spec": spec}
    jsave(d / "ds.json", ds)
    val, prev, perr = regen(d, a.frame)
    res = {"borrador": str(d), "preview": str(prev) if prev else None, "validacion": val, "paleta": ds["paleta"]}
    if perr:
        res["error_preview"] = perr
    return res


if __name__ == "__main__":
    main()
