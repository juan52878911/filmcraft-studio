#!/usr/bin/env python3
"""Brief de intenciones inferido del material, con origen y confianza por campo, y elección del DS.

Uso:
    brief_infer.py --analisis WORK/analisis --out WORK/brief.json [--dado '{"duracion_s": 55, "ds": "x"}']
    brief_infer.py --solo-ds [--flyer F] [--ruta RUTA]       # ranking de DS por rutas y color del flyer

Cada campo: {"valor", "origen": "dado|inferido|defecto", "confianza": 0-1, "por": "…"}.
En asistido se pregunta lo que tenga confianza < 0,6; en headless se usa y queda marcado en el informe.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import jload, jsave, list_ds, load_ds  # noqa: E402

PREMIO = re.compile(r"^(gan[óoa]\w*|premio\w*|regal\w*|figurit\w*|sorteo\w*|ganador\w*)$", re.I)
NUM = re.compile(r"^\d+([.,]\d+)?$")
UNIDAD = re.compile(r"^(dólares|dolares|usd|créditos|creditos|por|%|mil|millones)[,.]?$", re.I)


def norm(w):
    return re.sub(r"[^\wáéíóúñü]", "", w.lower())


def hexd(a, b):
    return sum((int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) ** 2 for i in (1, 3, 5)) ** 0.5 / 441.7


def match_ds(flyer=None, ruta=""):
    """[(score, id, detalle)] ordenado: 50 % rutas/palabras, 50 % parecido de paleta con el flyer."""
    pal = None
    if flyer and Path(flyer).exists():
        from ds_from_image import palette, roles
        cl, _ = palette(flyer)
        p, _ = roles(cl)
        pal = [p["fondo"], p["acento1"], p["acento2"], p["acento3"], p["claro"]]
    out = []
    for d in list_ds():
        ds = load_ds(d)
        m = ds.get("match", {})
        r = 1.0 if any(x.lower() in ruta.lower() for x in m.get("rutas", []) if x) else 0.0
        c = None
        if pal and m.get("paleta_ref"):
            ref = m["paleta_ref"]
            c = 1 - sum(min(hexd(a, b) for b in ref) for a in pal) / len(pal)
        score = 0.5 * r + 0.5 * (c if c is not None else 0)
        out.append((round(score, 3), ds["id"], {"ruta": r, "color": round(c, 3) if c is not None else None}))
    return sorted(out, reverse=True)


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
                item = (vkeys[n], "servicio")
            elif PREMIO.match(n):
                item = ("momento de premio", "humano")
            elif t[:1].isupper() and i > 0 and not re.search(r"[.?!]$", ws[i - 1]["w"]) and len(n) > 3 \
                    and n not in {"amazon", "aws", "github"} and n not in vkeys:
                item = (t.strip(",.?!¿¡"), "nombre")
            if item:
                k = item[0].lower()
                if k not in found:
                    found[k] = {"texto": item[0], "tipo": item[1], "src": v["stem"], "t": w["s"], "veces": 0}
                found[k]["veces"] += 1
    order = {"cifra": 0, "servicio": 1, "humano": 2, "nombre": 3}
    c = sorted(found.values(), key=lambda x: (order[x["tipo"]], -x["veces"]))
    return [x for x in c if x["tipo"] != "nombre" or x["veces"] >= 1][:12]


def field(v, origen, conf, por=""):
    return {"valor": v, "origen": origen, "confianza": conf, "por": por}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--analisis")
    ap.add_argument("--out")
    ap.add_argument("--dado", default="{}")
    ap.add_argument("--solo-ds", action="store_true")
    ap.add_argument("--flyer")
    ap.add_argument("--ruta", default="")
    a = ap.parse_args()
    if a.solo_ds:
        for s, i, det in match_ds(a.flyer, a.ruta):
            print(f"{s:5.2f}  {i:28} ruta={det['ruta']} color={det['color']}")
        return
    mat = jload(Path(a.analisis) / "material.json")
    dado = json.loads(a.dado)
    ruta = " ".join(v["path"] for v in mat["videos"])
    flyer = dado.get("flyer") or mat.get("flyer")
    if "ds" in dado:
        dsf = field(dado["ds"], "dado", 1.0)
    else:
        rk = match_ds(flyer, ruta)
        best = rk[0]
        dsf = field(best[1], "inferido", round(min(0.95, best[0] + 0.1), 2),
                    f"rutas={best[2]['ruta']}, color del flyer={best[2]['color']}; alternativas: "
                    + ", ".join(f"{i} ({s})" for s, i, _ in rk[1:3]))
    ds = load_ds(dsf["valor"])
    lz = ds["lienzo"]
    asp = "9:16" if lz["alto"] > lz["ancho"] else ("1:1" if lz["alto"] == lz["ancho"] else "16:9")
    dmin, dmax = ds["estructura"]["duracion_s"]
    en = [v["energia_media_db"] for v in mat["videos"] if v.get("energia_media_db") is not None]
    em = sum(en) / len(en) if en else -30
    tono = "enérgico y directo" if (ds.get("ritmo", {}).get("energia") == "alta" or em > -22) else "cálido y pausado"
    cands = candidates(a.analisis, ds)
    habla = sum(len(v["frases"]) for v in mat["videos"])
    b = {
        "objetivo": field("reel de evento: contar lo mejor de la sesión y atraer a la próxima", "defecto", 0.4),
        "publico": field("estudiantes universitarios interesados en la nube y en AWS", "defecto", 0.4),
        "plataforma": field({"9:16": "Instagram Reels / TikTok / Shorts", "1:1": "feed cuadrado", "16:9": "YouTube"}[asp],
                            "inferido", 0.8, f"aspecto {asp} del DS"),
        "duracion_s": field(round((dmin + dmax) / 2), "defecto", 0.5, f"rango del DS {dmin}–{dmax} s"),
        "tono": field(tono, "inferido", 0.6, f"energía media {em:.1f} dBFS, ritmo del DS {ds.get('ritmo', {}).get('energia')}"),
        "obligatorios": field([c["texto"] for c in cands if c["tipo"] in ("cifra", "servicio", "humano")][:8], "inferido", 0.5,
                              "cifras con unidad, servicios del vocabulario y premios en la transcripción"),
        "candidatos": cands,
        "evitar": field(["tapar caras o personas con pop-ups", "cortar dentro de una palabra",
                         "tramos sin voz clara"], "defecto", 0.7, "reglas duras de editor-filmcraft"),
        "cta": field(ds["marca"].get("cta"), "inferido", 0.7, "marca del DS"),
        "ds": dsf,
        "idioma": field("es", "inferido", 0.9, f"whisper, {habla} frases"),
    }
    for k, v in dado.items():
        if k in b and k != "ds":
            b[k] = field(v, "dado", 1.0)
    jsave(a.out, b)
    low = [k for k, v in b.items() if isinstance(v, dict) and v.get("confianza", 1) < 0.6]
    print(json.dumps({"brief": a.out, "ds": dsf["valor"], "baja_confianza": low,
                      "obligatorios": b["obligatorios"]["valor"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
