#!/usr/bin/env python3
"""Verificación headless de un montaje: hojas, textos frente a caras, keyframes, cortes en palabra y audio.

Uso:
    verify.py PROYECTO.fcproj --compiled WORK/compiled.json --analisis WORK/analisis --out WORK/verificacion
              [--ref REFERENCIA.fcproj] [--segundos 1.2 6.4 …]

No escribe el proyecto: renderiza desde él y, para las hojas sin textos, desde una COPIA temporal con
las pistas de texto desactivadas. Con --ref compara con otro montaje en los mismos segundos (hojas,
curva de loudness por segundo, número de cortes y obligatorios). Resultado: OUT/verificacion.json.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from common import detect, jload, jsave  # noqa: E402
from fclib import CLI, TPS  # noqa: E402

TEXT_TRACKS = ["Brand", "Captions", "Labels", "Pills", "Tags", "Eco", "Mattes", "Producto", "Tarjeta"]


def seq_of(fcproj):
    j = jload(fcproj)
    items = j["project"]["items"]
    seq = [v for v in items.values() if "Sequence" in v.get("kind", {})]
    seq = seq[0]["kind"]["Sequence"]
    paths = {}
    for k, v in items.items():
        m = v.get("kind", {}).get("Media", {}).get("media", {})
        if (m.get("File") or {}).get("path"):
            paths[int(k)] = m["File"]["path"]
    return seq, paths, items


def clips(track):
    return track.get("clips") or track.get("items") or []


def render(project, secs, outdir, scale=0.25):
    outdir.mkdir(parents=True, exist_ok=True)
    res = {}
    for t in secs:
        png = outdir / f"{t:08.3f}.png"
        if not png.exists():
            subprocess.run([CLI, "--project", str(project), "render", "--seconds", f"{t:.3f}", "--scale", str(scale),
                            "--out", str(png), "--allow-offline"], capture_output=True)
        if png.exists():
            res[t] = png
    return res


def sheet(frames, out, labels=None, cols=8, boxes=None):
    ims = []
    for t, p in frames:
        im = Image.open(p).convert("RGB")
        im.thumbnail((270, 480))
        d = ImageDraw.Draw(im)
        for b, col in (boxes or {}).get(t, []):
            W, H = im.size
            d.rectangle([b[0] * W, b[1] * H, b[2] * W, b[3] * H], outline=col, width=2)
        d.rectangle([0, 0, 92, 15], fill="black")
        d.text((3, 2), (labels or {}).get(t, f"{t:.2f}"), fill="yellow")
        ims.append(im)
    if not ims:
        return None
    cols = min(cols, len(ims))
    rows = (len(ims) + cols - 1) // cols
    W, H = ims[0].size
    s = Image.new("RGB", (cols * (W + 4), rows * (H + 4)), "white")
    for i, im in enumerate(ims):
        s.paste(im.resize((W, H)), ((i % cols) * (W + 4), (i // cols) * (H + 4)))
    out.parent.mkdir(parents=True, exist_ok=True)
    s.save(out, quality=85)
    return str(out)


def loudness(project, out_wav):
    r = subprocess.run([CLI, "--project", str(project), "export", str(out_wav), "--allow-offline"], capture_output=True, text=True)
    if not Path(out_wav).exists():
        return {"error": r.stderr[-300:]}
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(out_wav), "-af", "ebur128=peak=true:metadata=1,"
                        "ametadata=print:key=lavfi.r128.S:file=-", "-f", "null", "-"], capture_output=True, text=True)
    txt = r.stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", txt)
    LRA = re.findall(r"LRA:\s+(-?[\d.]+) LU", txt)
    peaks = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", txt)
    curve, last = [], -1
    for m in re.finditer(r"pts_time:([\d.]+)\s*\nlavfi\.r128\.S=(-?[\d.inf]+)", r.stdout):
        t, v = float(m.group(1)), m.group(2)
        if int(t) > last:
            last = int(t)
            curve.append(round(float(v), 1) if "inf" not in v else -70.0)
    return {"lufs": float(I[-1]) if I else None, "lra": float(LRA[-1]) if LRA else None,
            "pico_dbtp": float(peaks[-1]) if peaks else None, "curva_s": curve, "wav": str(out_wav)}


def overlap(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    ab = (b[2] - b[0]) * (b[3] - b[1])
    return inter / ab if ab else 0


def kf_check(seq):
    """Todos los keyframes deben caer dentro del rango de media del clip (base source_in + desfase × speed)."""
    bad, total = [], 0
    for kind in ("video_tracks", "audio_tracks"):
        for tr in seq[kind]:
            for c in clips(tr):
                lo = c.get("source_in", 0)
                hi = lo + c["duration"] * c.get("speed", 1)
                for e in c.get("effects", []):
                    for p, v in e.get("params", {}).items():
                        for k in v.get("keyframes", []) or []:
                            total += 1
                            if not (lo - TPS * 0.05 <= k["time"] <= hi + TPS * 0.05):
                                bad.append({"clip": c["id"], "pista": tr.get("name"), "efecto": e["effect"], "param": p,
                                            "t_media": round(k["time"] / TPS, 3), "rango": [round(lo / TPS, 3), round(hi / TPS, 3)]})
    return {"keyframes": total, "fuera_de_rango": bad[:20], "n_fuera": len(bad)}


def cut_check(seq, paths, analisis):
    """Bordes de los clips de diálogo frente a las palabras de la transcripción."""
    out, n = [], 0
    for tr in seq["audio_tracks"]:
        if tr.get("name") != "Dialogue":
            continue
        for c in clips(tr):
            p = paths.get(c["item"])
            if not p:
                continue
            pj = Path(analisis) / f"{Path(p).stem}.palabras.json"
            if not pj.exists():
                continue
            ws = jload(pj)
            a = c["source_in"] / TPS
            b = a + c["duration"] / TPS * c.get("speed", 1)
            for edge, t in (("entrada", a), ("salida", b)):
                n += 1
                for w in ws:
                    if w["s"] + 0.02 < t < w["e"] - 0.02:
                        out.append({"clip": c["id"], "borde": edge, "t_fuente": round(t, 3), "palabra": w["w"],
                                    "seq_s": round(c["start"] / TPS + (0 if edge == "entrada" else c["duration"] / TPS), 2)})
    return {"bordes": n, "dentro_de_palabra": out}


def main_cuts(seq):
    for tr in seq["video_tracks"]:
        if tr.get("name") == "Main":
            cs = sorted(clips(tr), key=lambda c: c["start"])
            return [round(c["start"] / TPS, 3) for c in cs[1:]], len(cs)
    return [], 0


def texts_of(seq):
    out = []
    for tr in seq["video_tracks"]:
        for c in clips(tr):
            for e in c.get("effects", []):
                if e["effect"] == "graphic_text":
                    out.append(e["params"]["text"]["value"].get("Text", ""))
    return out


def no_text_copy(project, tmp):
    cp = Path(tmp) / "sin_textos.fcproj"
    seq, _, _ = seq_of(project)
    names = [t.get("name") for t in seq["video_tracks"]]
    lines = [json.dumps({"id": "timeline.setTrack", "params": {"track": f"V{i + 1}", "enabled": False}})
             for i, n in enumerate(names) if n in TEXT_TRACKS]
    js = Path(tmp) / "off.jsonl"
    js.write_text("\n".join(lines) + "\n")
    subprocess.run([CLI, "--project", str(project), "--save-as", str(cp), "run", str(js)], capture_output=True)
    return cp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--compiled", required=True)
    ap.add_argument("--analisis", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ref")
    ap.add_argument("--segundos", nargs="*", type=float)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    comp = jload(a.compiled)
    estado = jload(Path(a.compiled).parent / "estado.json")
    seq, paths, _ = seq_of(a.project)
    res = {"proyecto": a.project}
    dur = max((c["start"] + c["duration"]) / TPS for tr in seq["video_tracks"] for c in clips(tr))
    res["duracion_s"] = round(dur, 2)
    cuts, nmain = main_cuts(seq)
    res["cortes"] = len(cuts)
    res["planos"] = nmain

    # hojas: cortes (antes/después) y transiciones
    tc = sorted({round(max(0, t - 0.25), 3) for t in cuts} | {round(t + 0.25, 3) for t in cuts if t + 0.25 < dur})
    tmpd = Path(tempfile.mkdtemp(prefix="fcs_ver_"))
    fr = render(a.project, tc, tmpd / "cortes")
    res["hoja_cortes"] = sheet(sorted(fr.items()), out / "hoja_cortes.jpg", cols=10)

    # pop-ups: con textos y sin textos + caras
    pops = [(k, v) for k, v in estado.get("textos", {}).items() if v.get("rol") in
            ("etiqueta", "concepto", "escalon", "eco", "nombre", "tag", "pill")]
    mids = {}
    for k, v in pops:
        mids.setdefault(round(v["start"] + min(v["dur"], 3) / 2, 3), []).append((k, v))
    tm = sorted(mids)
    fr_t = render(a.project, tm, tmpd / "pop")
    cp = no_text_copy(a.project, tmpd)
    fr_n = render(cp, tm, tmpd / "pop_sin")
    det = detect(list(fr_n.values())) if fr_n else {}
    choques, boxes = [], {}
    for t in tm:
        d = det.get(str(Path(fr_n[t]).resolve()), {}) if t in fr_n else {}
        faces = [[x, y, x + w, y + h] for x, y, w, h in d.get("faces", [])]
        people = [[x, y, x + w, y + h] for x, y, w, h in d.get("people", [])]
        for k, v in mids[t]:
            b = v["box"]
            fo = max([overlap(b, f) for f in faces] or [0])
            po = max([overlap(b, p) for p in people] or [0])
            boxes.setdefault(t, []).append((b, "red" if fo > 0.05 else ("orange" if po > 0.25 else "lime")))
            if fo > 0.05 or po > 0.25:
                choques.append({"texto": v["texto"], "t": t, "cara": round(fo, 2), "persona": round(po, 2)})
    res["hoja_popups"] = sheet(sorted(fr_t.items()), out / "hoja_popups.jpg")
    res["hoja_popups_sin_textos"] = sheet(sorted(fr_n.items()), out / "hoja_popups_sin_textos.jpg", boxes=boxes)
    res["textos_vs_caras"] = {"popups": len(pops), "momentos": len(tm), "choques": choques}

    res["keyframes"] = kf_check(seq)
    res["cortes_en_palabra"] = cut_check(seq, paths, a.analisis)
    res["audio"] = loudness(a.project, out / "mezcla.wav")
    res["cobertura"] = comp.get("cobertura", {})

    if a.ref:
        rseq, rpaths, _ = seq_of(a.ref)
        rcuts, rn = main_cuts(rseq)
        rdur = max((c["start"] + c["duration"]) / TPS for tr in rseq["video_tracks"] for c in clips(tr))
        secs = a.segundos or [round(x, 2) for x in [1.5, 4.5, 7.5, 11.0, 13.8, 16.0, 19.5, 24.0, 27.0, 30.0, 34.0,
                                                    36.5, 40.0, 44.0, 49.0, 52.5, 55.0] if x < max(dur, rdur)]
        fa = render(a.project, [s for s in secs if s < dur], tmpd / "cmp_a")
        fb = render(a.ref, [s for s in secs if s < rdur], tmpd / "cmp_b")
        pares = []
        for s in secs:
            if s in fb:
                pares.append((s - 0.0001, fb[s]))
            if s in fa:
                pares.append((s, fa[s]))
        labels = {t: (f"REF {t + 0.0001:.1f}" if abs(t - round(t, 2)) > 1e-6 else f"AUTO {t:.1f}") for t, _ in pares}
        res["hoja_comparacion"] = sheet(pares, out / "hoja_comparacion.jpg", labels=labels, cols=8)
        ra = loudness(a.ref, out / "mezcla_ref.wav")
        rtexts = " ".join(texts_of(rseq)).lower()
        obl = list(res["cobertura"].keys())
        res["referencia"] = {"proyecto": a.ref, "duracion_s": round(rdur, 2), "cortes": len(rcuts), "planos": rn,
                             "audio": ra, "obligatorios": {o: (max(o.lower().split(), key=len) in rtexts) for o in obl}}
        res["hoja_curvas"] = curves(res["audio"].get("curva_s", []), ra.get("curva_s", []), out / "curvas_lufs.png")
    jsave(out / "verificacion.json", res)
    a_ = res["audio"]
    print(json.dumps({"duracion_s": res["duracion_s"], "cortes": res["cortes"], "lufs": a_.get("lufs"),
                      "pico_dbtp": a_.get("pico_dbtp"), "choques_texto": len(choques),
                      "cortes_dentro_de_palabra": len(res["cortes_en_palabra"]["dentro_de_palabra"]),
                      "keyframes_fuera": res["keyframes"]["n_fuera"],
                      "ref": {k: res["referencia"][k] for k in ("duracion_s", "cortes")} if a.ref else None,
                      "ref_lufs": res["referencia"]["audio"].get("lufs") if a.ref else None}, ensure_ascii=False))


def curves(a, b, out):
    W, H, pad = 1100, 360, 40
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    n = max(len(a), len(b), 1)
    lo, hi = -40, -5

    def pt(i, v):
        return pad + i * (W - 2 * pad) / max(1, n - 1), pad + (hi - max(lo, min(hi, v))) * (H - 2 * pad) / (hi - lo)
    for db in range(lo, hi + 1, 5):
        y = pt(0, db)[1]
        d.line([(pad, y), (W - pad, y)], fill="#DDDDDD")
        d.text((4, y - 6), str(db), fill="#666666")
    for serie, col in ((b, "#888888"), (a, "#E07000")):
        if len(serie) > 1:
            d.line([pt(i, v) for i, v in enumerate(serie)], fill=col, width=3)
    d.text((pad, 8), "LUFS a corto plazo por segundo · naranja = automático · gris = referencia", fill="#000000")
    im.save(out)
    return str(out)


if __name__ == "__main__":
    main()
