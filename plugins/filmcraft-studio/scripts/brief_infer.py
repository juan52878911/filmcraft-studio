#!/usr/bin/env python3
"""Brief de intenciones inferido del material, con origen y confianza por campo, y elección del DS.

Uso:
    brief_infer.py --analisis WORK/analisis --out WORK/brief.json [--dado '{"duracion_s": 55, "ds": "x"}']
    brief_infer.py --out WORK/brief.json --dado '{…respuestas de la biblia…}' [--flyer F]   # sin material de cámara
    brief_infer.py --solo-ds [--flyer F] [--ruta RUTA] [--para camara|promo]   # ranking de DS por rutas y color del flyer

Cada campo: {"valor", "origen": "dado|inferido|defecto", "confianza": 0-1, "por": "…"}.
En asistido se pregunta lo que tenga confianza < 0,6; en headless se usa y queda marcado en el informe.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import cine, jload, jsave, list_ds, load_ds, norm, sin_tildes  # noqa: E402,F401

PREMIO = re.compile(r"^(gan[óoa]\w*|premio\w*|regal\w*|figurit\w*|sorteo\w*|ganador\w*)$", re.I)
NUM = re.compile(r"^\d+([.,]\d+)?$")
UNIDAD = re.compile(r"^(dólares|dolares|usd|créditos|creditos|por|%|mil|millones)[,.]?$", re.I)


def es_promo(ds):
    """DS de promo de código (renderizado por código, sin cámara): los que traen bloque `promo`."""
    return bool(ds.get("promo"))


def match_ds(flyer=None, ruta="", para="todos"):
    """[(score, id, detalle)] ordenado, de `cine elegir-ds` (motor Rust): media de las señales disponibles
    (rutas por palabras enteras de los nombres de carpeta del material y parecido ΔE en OKLab de la paleta
    del flyer con `match.paleta_ref`); con las dos, 50 % cada una.

    `ruta`: una ruta o lista de rutas (las del material). `para`: "camara" deja fuera los DS de promo,
    "promo" solo los de promo, "todos" no filtra."""
    rutas = [str(ruta)] if isinstance(ruta, (str, Path)) else [str(r) for r in ruta]
    args = ["elegir-ds", "--json", "--para", para, "--rutas-json", json.dumps([r for r in rutas if r.strip()])]
    if flyer and Path(flyer).exists():
        args += ["--flyer", str(flyer)]
    return [(r["score"], r["id"], {"ruta": r["ruta"], "color": r["color"]}) for r in cine(*args)]


def dicho(entrada, ws, i):
    """La entrada del vocabulario tal como la dijo el ponente: «Amazon SageMaker» si dijo las dos palabras,
    «SageMaker» si solo dijo esa (un rótulo «SAGEMAKER» debe poder cubrir el obligatorio)."""
    pal = entrada.split()
    pre = pal[:-1]
    antes = [norm(w["w"]) for w in ws[max(0, i - len(pre)):i]]
    if pre and antes == [norm(x) for x in pre]:
        return entrada
    return ws[i]["w"].strip(",.;:?!¿¡\"'«»") or pal[-1]


def candidates(analisis, ds):
    """Obligatorios candidatos: cifras con unidad, servicios del vocabulario, premios y nombres propios."""
    mat = jload(Path(analisis) / "material.json")
    vocab = [v.strip() for v in ds.get("vocabulario", "").split(",") if v.strip()]
    vkeys = {norm(v.split()[-1]): v for v in vocab}
    found = {}
    for v in mat["videos"]:
        pj = Path(analisis) / (v.get("palabras_json") or "")
        if not v.get("palabras_json") or not pj.exists():
            continue
        ws = jload(pj)
        for i, w in enumerate(ws):
            t = w["w"]
            n = norm(t)
            nxt = ws[i + 1]["w"] if i + 1 < len(ws) else ""
            item = None
            if NUM.match(n) and UNIDAD.match(nxt):
                item = (f"{n} {norm(nxt)}", "cifra")
            elif n in vkeys and len(n) > 3:
                item = (dicho(vkeys[n], ws, i), "servicio", vkeys[n])
            elif PREMIO.match(n):
                item = ("momento de premio", "humano")
            elif t[:1].isupper() and i > 0 and not re.search(r"[.?!]$", ws[i - 1]["w"]) and len(n) > 3 \
                    and n not in {"amazon", "aws", "github"} and n not in vkeys:
                item = (t.strip(",.?!¿¡"), "nombre")
            if item:
                k = (item[2] if len(item) > 2 else item[0]).lower()     # un servicio cuenta una vez, se diga como se diga
                if k not in found:
                    found[k] = {"texto": item[0], "tipo": item[1], "src": v["stem"], "t": w["s"], "veces": 0}
                elif len(item[0]) < len(found[k]["texto"]):
                    found[k]["texto"] = item[0]                          # la forma más corta dicha: la cubre cualquier rótulo
                found[k]["veces"] += 1
    order = {"cifra": 0, "servicio": 1, "humano": 2, "nombre": 3}
    c = sorted(found.values(), key=lambda x: (order[x["tipo"]], -x["veces"]))
    return [x for x in c if x["tipo"] != "nombre" or x["veces"] >= 2][:12]     # un nombre suelto no basta


def field(v, origen, conf, por=""):
    return {"valor": v, "origen": origen, "confianza": conf, "por": por}


def infer(mat, dado, analisis=None, flyer=None):
    """Brief a partir del material (mat = material.json; {"videos": []} si no hay material de cámara) y de lo
    dado. Sin material, lo que dependería de él (tono, obligatorios, idioma) va con confianza baja."""
    hay_material = bool(mat.get("videos"))
    rutas = [v["path"] for v in mat.get("videos", [])]
    flyer = dado.get("flyer") or flyer or mat.get("flyer")
    if "ds" in dado:
        dsf = field(dado["ds"], "dado", 1.0)
    else:
        # con material de cámara, los DS de promo (renderizados por código) no compiten salvo que se pidan
        para = dado.get("para") or ("camara" if hay_material else "todos")
        rk = match_ds(flyer, rutas, para)
        nota = ""
        if not rk and para != "todos":
            rk, nota = match_ds(flyer, rutas), f" (ningún DS para {para}: elegido entre todos)"
        if not rk:
            sys.exit("no hay ningún design system en el catálogo: crea uno con ds_studio.py crear o pásalo en --dado")
        best = rk[0]
        conf = round(min(0.95, best[0] + 0.1), 2) if not nota else min(0.3, round(best[0] + 0.1, 2))
        dsf = field(best[1], "inferido", conf,
                    f"rutas={best[2]['ruta']}, color del flyer={best[2]['color']}; alternativas: "
                    + ", ".join(f"{i} ({s})" for s, i, _ in rk[1:3]) + nota)
    ds = load_ds(dsf["valor"])
    lz = ds["lienzo"]
    asp = "9:16" if lz["alto"] > lz["ancho"] else ("1:1" if lz["alto"] == lz["ancho"] else "16:9")
    dmin, dmax = ds.get("estructura", {}).get("duracion_s", [30, 60])
    en = [v["energia_media_db"] for v in mat.get("videos", []) if v.get("energia_media_db") is not None]
    em = sum(en) / len(en) if en else None
    ritmo = ds.get("ritmo", {}).get("energia")
    tono = "enérgico y directo" if (ritmo == "alta" or (em is not None and em > -22)) else "cálido y pausado"
    if em is not None:
        tonof = field(tono, "inferido", 0.6, f"energía media {em:.1f} dBFS, ritmo del DS {ritmo}")
    else:
        tonof = field(tono, "inferido", 0.4, f"sin material: solo el ritmo del DS ({ritmo})")
    cands = candidates(analisis, ds) if (analisis and hay_material) else []
    habla = sum(len(v.get("frases", [])) for v in mat.get("videos", []))
    marca = ds.get("marca", {})
    if hay_material:
        oblf = field([c["texto"] for c in cands if c["tipo"] in ("cifra", "servicio", "humano")][:8], "inferido", 0.5,
                     "cifras con unidad, servicios del vocabulario y premios en la transcripción")
    else:
        oblf = field([], "defecto", 0.3, "sin material de cámara: no hay transcripción de la que sacarlos")
    lang = mat.get("lang")
    idif = (field(lang, "inferido", 0.9, f"idioma pedido al analizar ({habla} frases)") if lang and hay_material
            else field(lang or "es", "defecto", 0.4, "no consta en el análisis" if hay_material else "sin material"))
    b = {
        "objetivo": field(marca.get("objetivo") or "contar lo mejor del material y llevar al público a la llamada a la acción",
                          "defecto", 0.4),
        "publico": field(marca.get("publico") or "el público habitual de la marca del DS", "defecto", 0.4),
        "plataforma": field({"9:16": "Instagram Reels / TikTok / Shorts", "1:1": "feed cuadrado", "16:9": "YouTube"}[asp],
                            "inferido", 0.8, f"aspecto {asp} del DS"),
        "duracion_s": field(round((dmin + dmax) / 2), "defecto", 0.5, f"rango del DS {dmin}–{dmax} s"),
        "tono": tonof,
        "obligatorios": oblf,
        "candidatos": cands,
        "evitar": field(["tapar caras o personas con pop-ups", "cortar dentro de una palabra",
                         "tramos sin voz clara"], "defecto", 0.7, "reglas duras de editor-filmcraft"),
        "cta": field(marca.get("cta"), "inferido", 0.7, "marca del DS"),
        "ds": dsf,
        "idioma": idif,
    }
    for k, v in dado.items():
        if k not in ("ds", "flyer", "para"):            # lo dado manda; campos extra de la biblia se conservan
            b[k] = field(v, "dado", 1.0)
    return b


def main():
    ap = argparse.ArgumentParser(description="Brief de intenciones con origen y confianza por campo.")
    ap.add_argument("--analisis", help="carpeta del análisis; sin ella (video sin material de cámara) se infiere "
                                       "solo de --dado y --flyer, con confianza baja en lo que dependa del material")
    ap.add_argument("--out")
    ap.add_argument("--dado", default="{}", help="JSON con los campos ya decididos (p. ej. respuestas de la biblia)")
    ap.add_argument("--solo-ds", action="store_true")
    ap.add_argument("--flyer")
    ap.add_argument("--ruta", default="", help="carpeta o fichero del material (se casa por nombres de carpeta)")
    ap.add_argument("--para", choices=["todos", "camara", "promo"], default="todos",
                    help="con --solo-ds: camara deja fuera los DS de promo; promo, solo esos")
    a = ap.parse_args()
    if a.solo_ds:                       # atajo antiguo: es `bin/cine elegir-ds`
        r = cine("elegir-ds", "--para", a.para, *(["--ruta", a.ruta] if a.ruta else []),
                 *(["--flyer", a.flyer] if a.flyer else []), json_out=False)
        print(r.stdout, end="")
        return
    if not a.out:
        ap.error("falta --out (o usa --solo-ds)")
    try:
        dado = json.loads(a.dado)
    except json.JSONDecodeError as ex:
        ap.error(f"--dado no es JSON válido: {ex}")
    if not isinstance(dado, dict):
        ap.error("--dado debe ser un objeto JSON")
    if a.analisis:
        mf = Path(a.analisis) / "material.json"
        if not mf.exists():
            ap.error(f"no existe {mf}: corre antes analyze_media.py o quita --analisis")
        mat = jload(mf)
    else:
        mat = {"videos": []}
    b = infer(mat, dado, a.analisis, a.flyer)
    jsave(a.out, b)
    low = [k for k, v in b.items() if isinstance(v, dict) and v.get("confianza", 1) < 0.6]
    print(json.dumps({"brief": a.out, "ds": b["ds"]["valor"], "baja_confianza": low,
                      "obligatorios": b["obligatorios"]["valor"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
