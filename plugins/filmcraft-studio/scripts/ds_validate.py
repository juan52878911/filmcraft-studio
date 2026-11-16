#!/usr/bin/env python3
"""Valida un design system de video. Sale con código 1 si hay errores.

Uso: ds_validate.py DS [--json] [--estricto]
     ds_validate.py --todos [--json] [--estricto]       # todos los DS del catálogo (precargados y del usuario)

Comprueba:
- forma: contra schemas/ds.schema.json si `jsonschema` está instalado; además (siempre) las claves
  obligatorias, también las anidadas que los scripts leen sin .get (continuidad.entrada,
  musica.bajo_voz_db, animaciones.wordReveal, roles marca/subtitulo con pos…);
- colores hex y referencias de color de los roles; contraste del texto sobre su fondo (≥ 4,5:1 en texto
  pequeño, ≥ 3:1 en titulares ≥ 60 px);
- fuentes instaladas (aviso si el archivo vive en ~/, porque en otra máquina no estará);
- assets (fondos, mattes, SFX) existentes y fondos/mattes al tamaño del lienzo (aviso si miden como una
  de lienzo.variantes; error si no casan con nada);
- pistas de los roles declaradas; SFX de roles y transiciones presentes en sfx.mapa; animaciones de los
  roles definidas en `animaciones`; transiciones de `preferencia` definidas.
--estricto trata los avisos como errores.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT, font_file, list_ds, load_ds  # noqa: E402
from ds_from_image import contrast  # noqa: E402

SCHEMA = ROOT / "schemas" / "ds.schema.json"
REQ = ["id", "gramatica", "lienzo", "paleta", "fuentes", "marca", "pistas", "roles_texto", "animaciones",
       "continuidad", "transiciones", "fondos", "mattes", "sfx", "musica", "grade", "audio", "estructura"]
# claves anidadas que plan_compile/apply_plan/fcstyle/brief_infer indexan sin .get
REQ_ANIDADAS = ["continuidad.entrada", "continuidad.zoom_crash", "fondos.titulo", "fondos.plano", "fondos.cap",
                "fondos.cierre", "mattes.blanco", "marca.barra", "marca.titulo", "marca.cta", "estructura.duracion_s",
                "musica.bajo_voz_db", "musica.sin_voz_db", "animaciones.base_fps", "animaciones.popIn",
                "animaciones.wordReveal", "animaciones.eco", "transiciones.preferencia", "transiciones.corte",
                "audio.lufs", "audio.pico_dbtp", "pistas.video", "pistas.audio", "sfx.mapa",
                "lienzo.ancho", "lienzo.alto", "lienzo.fps",
                # fcstyle.title (titulo y cierre) e fcstyle.eco / plan_compile los leen a pelo
                "roles_texto.titulo.x", "roles_texto.titulo.y", "roles_texto.titulo.color",
                "roles_texto.cierre.x", "roles_texto.cierre.y", "roles_texto.cierre.color", "roles_texto.eco.colores"]
# pistas por nombre que apply_plan usa siempre (las de los roles y pistas.sfx se comprueban aparte)
PISTAS_VIDEO = ["Fondo", "Main", "Mattes"]
PISTAS_AUDIO = ["Dialogue", "Music"]
PAL = ["fondo", "oscuro", "claro", "acento1"]
ANIMS = {"popIn", "wordReveal", "eco", "calorEntra", "ninguna"}
ROLES_MIN = ["marca", "subtitulo", "etiqueta", "eco", "pill", "tag", "titulo", "cierre", "meta", "pie"]  # tarjeta y cierre
ROLES_CON_POS = ["marca", "subtitulo"]                     # apply_plan los coloca con pos fija
HEX = re.compile(r"#[0-9A-Fa-f]{6}")


def _get(d, ruta):
    for k in ruta.split("."):
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def schema_errors(raw):
    """Errores contra ds.schema.json; None si jsonschema no está instalado."""
    try:
        import jsonschema
    except ImportError:
        return None
    v = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text()))
    out = []
    for e in sorted(v.iter_errors(raw), key=lambda e: [str(p) for p in e.absolute_path]):
        ruta = ".".join(str(p) for p in e.absolute_path) or "(raíz)"
        out.append(f"esquema: {ruta}: {e.message[:200]}")
    return out


def own_shape_errors(raw):
    err = [f"falta '{k}'" for k in REQ if k not in raw]
    if err:
        return err
    err += [f"falta '{k}'" for k in REQ_ANIDADAS if _get(raw, k) is None]
    if not isinstance(raw.get("roles_texto"), dict):
        return err + ["roles_texto no es un objeto"]
    for name, r in raw["roles_texto"].items():
        if not isinstance(r, dict):
            err.append(f"rol {name}: no es un objeto")
            continue
        if not isinstance(r.get("tam"), (int, float)) or r.get("tam", 0) <= 0:
            err.append(f"rol {name}: 'tam' tiene que ser un número > 0")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", str(raw.get("id", ""))):
        err.append(f"id no válido: {raw.get('id')!r} (slug [a-z0-9-])")
    eco = _get(raw, "roles_texto.eco.colores")
    if eco is not None and (not isinstance(eco, list) or not eco or
                            not all(isinstance(p, (list, tuple)) and len(p) == 2 for p in eco)):
        err.append("rol eco: 'colores' tiene que ser una lista no vacía de pares [texto, fondo]")
    for rol in ("titulo", "cierre"):
        for k in ("x", "y"):
            v = _get(raw, f"roles_texto.{rol}.{k}")
            if v is not None and not (isinstance(v, (int, float)) and 0 <= v <= 1):
                err.append(f"rol {rol}: '{k}' tiene que ser un número entre 0 y 1 (fracción del lienzo)")
    ev = _get(raw, "zonas.evitar_y")
    if ev is not None and not (isinstance(ev, list) and all(
            isinstance(z, (list, tuple)) and len(z) == 2 and all(isinstance(x, (int, float)) for x in z) for z in ev)):
        err.append("zonas.evitar_y tiene que ser una lista de pares [y0, y1] (plan_compile los desempaqueta)")
    if "promo" in raw and not isinstance(_get(raw, "promo.bpm"), (int, float)):
        err.append("promo sin 'bpm' numérico (promo_preview.py lo lee)")
    return err


def variantes(lz):
    """{(ancho, alto): nombre} de lienzo.variantes."""
    return {(v.get("ancho"), v.get("alto")): n for n, v in (lz.get("variantes") or {}).items() if isinstance(v, dict)}


def validate(ds, raw=None):
    """ds: load_ds() (rutas resueltas). raw: el ds.json tal cual (para el esquema); si falta, se usa ds."""
    if raw is None:
        raw = {k: v for k, v in ds.items() if k != "_dir"}
        raw["sfx"] = {k: v for k, v in raw.get("sfx", {}).items() if k != "_mapa_abs"}
    err, warn = [], []
    sch = schema_errors(raw)
    err += sch or []
    err += own_shape_errors(raw)
    if any(e.startswith("falta '") and "." not in e for e in err):
        return _dedup(err), _dedup(warn)
    pal = ds["paleta"]
    for k in PAL:
        if k not in pal:
            err.append(f"paleta sin '{k}'")
    for k, v in pal.items():
        if not isinstance(v, str) or not HEX.fullmatch(v):
            err.append(f"color no hex: {k}={v}")
    for k in ("rejilla", "acento2", "acento3"):
        if k not in pal:
            warn.append(f"paleta sin '{k}' (ds_preview y ds_assets usan el acento1 o una mezcla)")

    def ok_ref(x):
        return x is None or (isinstance(x, str) and (HEX.fullmatch(x) or x in pal))

    def hexc(x, defecto):
        """Hex del color o None si no se puede medir (un color de paleta no hex ya es error aparte)."""
        v = pal.get(defecto) if x is None else (x if x.startswith("#") else pal.get(x))
        return v if isinstance(v, str) and HEX.fullmatch(v) else None
    vt = set(ds["pistas"].get("video", []))
    at = set(ds["pistas"].get("audio", []))
    mapa = ds["sfx"].get("mapa", {})
    for t in PISTAS_VIDEO:
        if t not in vt:
            err.append(f"pistas.video sin '{t}' (apply_plan coloca ahí fondo, planos o mattes)")
    for t in PISTAS_AUDIO + list(ds["pistas"].get("sfx", ["SFX"])):
        if t not in at:
            err.append(f"pistas.audio sin '{t}' (apply_plan coloca ahí diálogo, música o SFX)")
    if "Producto" not in vt:
        warn.append("pistas.video sin 'Producto': las capas de producto del plan no tendrán dónde ir")
    for r in ROLES_MIN:
        if r not in ds["roles_texto"]:
            err.append(f"falta el rol de texto '{r}'")
    for r in ROLES_CON_POS:
        if r in ds["roles_texto"] and not ds["roles_texto"][r].get("pos"):
            err.append(f"rol {r}: falta 'pos' (apply_plan lo coloca con posición fija)")
    for name, r in ds["roles_texto"].items():
        if not isinstance(r, dict):
            continue
        if r.get("fuente") not in ds["fuentes"]:
            err.append(f"rol {name}: fuente '{r.get('fuente')}' no declarada")
        for t in (r.get("pistas") or [r.get("pista")]):
            if t not in vt:
                err.append(f"rol {name}: pista '{t}' no está en pistas.video")
        an = r.get("anim", "ninguna")
        if an not in ANIMS:
            err.append(f"rol {name}: animación '{an}' desconocida")
        elif an != "ninguna" and an not in ds["animaciones"]:
            err.append(f"rol {name}: animación '{an}' sin definir en 'animaciones'")
        if r.get("sfx") and r["sfx"] not in mapa:
            err.append(f"rol {name}: sfx '{r['sfx']}' no está en sfx.mapa")
        pares = r.get("colores") or [[r.get("color", "claro"), f] for f in
                                     (r["fondo"] if isinstance(r.get("fondo"), list) else [r.get("fondo")])]
        for par in pares:
            tc, bc = (list(par) + [None, None])[:2]
            if not ok_ref(tc) or not ok_ref(bc):
                err.append(f"rol {name}: color '{tc}'/'{bc}' no está en la paleta")
                continue
            txc, bgc = hexc(tc, "claro"), hexc(bc, "fondo")
            if not txc or not bgc:
                continue
            c = contrast(txc, bgc)
            minimo = 3.0 if r.get("tam", 0) >= 60 else 4.5
            if c < minimo:
                (err if c < 2.5 else warn).append(f"rol {name}: contraste {c:.1f}:1 de {tc} sobre {bc or 'fondo'} (mínimo {minimo})")
    for k, f in ds["fuentes"].items():
        ff = font_file(f)
        if not ff or not Path(ff).exists():
            err.append(f"fuente '{k}' ({f.get('familia')} {f.get('estilo', '')}) no está instalada")
        elif str(ff).startswith(str(Path.home())):
            warn.append(f"fuente '{k}' en {str(ff).replace(str(Path.home()), '~')}: en otra máquina puede no estar")
    lz = ds["lienzo"]
    lienzo, vars_ = (lz.get("ancho"), lz.get("alto")), variantes(lz)
    for grp in ("fondos", "mattes"):
        for k, p in ds[grp].items():
            if not Path(p).exists():
                err.append(f"{grp}.{k}: no existe {p}")
                continue
            try:
                from PIL import Image
                with Image.open(p) as im:
                    tam = im.size
            except Exception as ex:  # noqa: BLE001
                err.append(f"{grp}.{k}: no se puede abrir ({ex})")
                continue
            if tam != lienzo and tam in vars_:
                warn.append(f"{grp}.{k}: mide {tam[0]}x{tam[1]} (variante '{vars_[tam]}'), no como el lienzo "
                            f"{lienzo[0]}x{lienzo[1]}")
            elif tam != lienzo:
                err.append(f"{grp}.{k}: mide {tam[0]}x{tam[1]} y el lienzo es {lz.get('ancho')}x{lz.get('alto')} "
                           "(regenera con promo_fondos.py o ds_assets.py)")
    for k, p in ds["sfx"].get("_mapa_abs", {}).items():
        if not Path(p).exists():            # apply_plan muere en file.import con él
            err.append(f"sfx.{k}: no existe {p}")
    # mattes que las transiciones van a pedir (plan_compile pone esos nombres; apply_plan indexa ds["mattes"])
    tr_ = ds["transiciones"]
    usadas = set(tr_.get("preferencia", [])) | {k for k in tr_ if k != "preferencia"}
    pide = {}
    if "matte" in usadas:
        pide["matte"] = (tr_.get("matte") or {}).get("mattes") or ["acento1"]
    for t in ("flash", "glitch"):
        if t in usadas:
            pide[t] = [(tr_.get(t) or {}).get("matte", "blanco")]
    for t, ms in pide.items():
        for m_ in ms:
            if m_ not in ds["mattes"]:
                err.append(f"transición {t}: el matte '{m_}' no está en mattes")
    for t, cfg in ds["transiciones"].items():
        if isinstance(cfg, dict) and cfg.get("sfx") and cfg["sfx"] not in mapa:
            err.append(f"transición {t}: sfx '{cfg['sfx']}' no está en sfx.mapa")
    for t in ds["transiciones"].get("preferencia", []):
        if t not in ds["transiciones"]:
            err.append(f"transición '{t}' en preferencia pero sin definir")
    if not (lz.get("ancho") and lz.get("alto") and lz.get("fps")):
        err.append("lienzo necesita ancho, alto y fps")
    return _dedup(err), _dedup(warn)


def _dedup(xs):
    seen, out = set(), []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def check(ref, estricto=False):
    try:
        ds = load_ds(ref)
        raw = json.loads((Path(ds["_dir"]) / "ds.json").read_text())
    except FileNotFoundError as ex:
        return {"ds": str(ref), "dir": None, "ok": False, "errores": [str(ex)], "avisos": [], "esquema": None}
    except (ValueError, TypeError, AttributeError, KeyError) as ex:     # ds.json roto o con tipos que load_ds no espera
        return {"ds": str(ref), "dir": None, "ok": False, "errores": [f"ds.json no se puede cargar: {type(ex).__name__}: {ex}"],
                "avisos": [], "esquema": None}
    try:
        err, warn = validate(ds, raw)
    except (ValueError, TypeError, AttributeError, KeyError, IndexError) as ex:
        # una forma que las comprobaciones de arriba no previeron: error claro, nunca traza
        err, warn = [f"el DS tiene una forma que el validador no esperaba: {type(ex).__name__}: {ex}"], []
    if estricto:
        err, warn = err + [f"(estricto) {w}" for w in warn], []
    return {"ds": ds.get("id"), "dir": ds["_dir"], "ok": not err, "errores": err, "avisos": warn,
            "esquema": "jsonschema" if schema_errors({}) is not None else "comprobaciones propias"}


def main():
    ap = argparse.ArgumentParser(description="Valida design systems de video.")
    ap.add_argument("ds", nargs="?")
    ap.add_argument("--todos", action="store_true", help="valida todo el catálogo")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--estricto", action="store_true", help="los avisos cuentan como errores")
    a = ap.parse_args()
    if not a.ds and not a.todos:
        ap.error("indica un DS o --todos")
    res = [check(d, a.estricto) for d in list_ds()] if a.todos else [check(a.ds, a.estricto)]
    if a.json:
        print(json.dumps(res if a.todos else res[0], ensure_ascii=False, indent=1))
    else:
        for r in res:
            print(f"DS {r['ds']}: {'OK' if r['ok'] else 'CON ERRORES'}")
            for e in r["errores"]:
                print("  ✗", e)
            for w in r["avisos"]:
                print("  !", w)
    sys.exit(0 if all(r["ok"] for r in res) else 1)


if __name__ == "__main__":
    main()
