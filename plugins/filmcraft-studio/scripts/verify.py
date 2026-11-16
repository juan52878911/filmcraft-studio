#!/usr/bin/env python3
"""Verificación headless de un montaje: hojas, textos frente a caras, keyframes, cortes en palabra y audio.

Uso:
    verify.py PROYECTO.fcproj --compiled WORK/compiled.json --analisis WORK/analisis --out WORK/verificacion
              [--ref REFERENCIA.fcproj] [--segundos 1.2 6.4 …]

No escribe el proyecto: renderiza desde él y, para las hojas sin textos, desde una COPIA temporal con
las pistas de texto desactivadas. Con --ref compara con otro montaje en los mismos segundos (hojas,
curva de loudness por segundo, número de cortes y obligatorios). Resultado: OUT/verificacion.json.

La verificación puede FALLAR: si el CLI no renderiza los fotogramas pedidos, el detector de caras falla o
no hay cifra de loudness, `verificado` es false, `fallos` dice qué no se midió y sale con código 2
(«0 choques» solo significa algo cuando los fotogramas existen y se miraron).
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from common import ErrorExterno, cubre, detect, ds_del_compilado, jload, jsave, parse_ebur128  # noqa: E402
from fclib import CLI, TPS  # noqa: E402

TEXT_TRACKS = ["Brand", "Captions", "Labels", "Pills", "Tags", "Eco", "Mattes", "Producto", "Tarjeta"]


def text_tracks(ds):
    """Pistas que llevan textos o gráficos encima de la imagen: las fijas más las de los roles del DS."""
    out = list(TEXT_TRACKS)
    for r in (ds or {}).get("roles_texto", {}).values():
        if isinstance(r, dict):
            for t in ([r.get("pista")] if r.get("pista") else []) + list(r.get("pistas") or []):
                if t and t not in out:
                    out.append(t)
    return out


def seq_of(fcproj):
    j = jload(fcproj)
    items = j["project"]["items"]
    seq = [v for v in items.values() if "Sequence" in v.get("kind", {})]
    if not seq:
        sys.exit(f"{fcproj}: el proyecto no tiene ninguna secuencia")
    seq = seq[0]["kind"]["Sequence"]
    paths = {}
    for k, v in items.items():
        m = v.get("kind", {}).get("Media", {}).get("media", {})
        if (m.get("File") or {}).get("path"):
            paths[int(k)] = m["File"]["path"]
    return seq, paths, items


def clips(track):
    return track.get("clips") or track.get("items") or []


def render(project, secs, outdir, scale=0.25, errores=None):
    """{segundo: png} de los que el CLI renderizó; los que fallan van a `errores` (lista) con su stderr."""
    outdir.mkdir(parents=True, exist_ok=True)
    res = {}
    for t in secs:
        png = outdir / f"{t:08.3f}.png"
        err = ""
        if not png.exists():
            try:
                r = subprocess.run([CLI, "--project", str(project), "render", "--seconds", f"{t:.3f}", "--scale", str(scale),
                                    "--out", str(png), "--allow-offline"], capture_output=True, text=True)
                err = f"código {r.returncode}: {r.stderr.strip()[-200:]}" if r.returncode else ""
            except OSError as ex:
                err = f"no se pudo ejecutar {CLI}: {ex}"
        if png.exists() and png.stat().st_size > 0:
            res[t] = png
        elif errores is not None:
            errores.append({"t": t, "proyecto": str(project), "error": err or "el CLI no escribió el fotograma"})
    return res


def sheet(frames, out, labels=None, cols=8, boxes=None):
    """frames: [(t, png)] o [(t, png, etiqueta)]."""
    ims = []
    for fr_ in frames:
        t, p = fr_[0], fr_[1]
        im = Image.open(p).convert("RGB")
        im.thumbnail((270, 480))
        d = ImageDraw.Draw(im)
        for b, col in (boxes or {}).get(t, []):
            W, H = im.size
            d.rectangle([b[0] * W, b[1] * H, b[2] * W, b[3] * H], outline=col, width=2)
        d.rectangle([0, 0, 92, 15], fill="black")
        d.text((3, 2), fr_[2] if len(fr_) > 2 else (labels or {}).get(t, f"{t:.2f}"), fill="yellow")
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
    Path(out_wav).unlink(missing_ok=True)                 # una mezcla vieja no vale como medida nueva
    try:
        r = subprocess.run([CLI, "--project", str(project), "export", str(out_wav), "--allow-offline"],
                           capture_output=True, text=True)
    except OSError as ex:
        return {"lufs": None, "error": f"no se pudo ejecutar {CLI}: {ex}"}
    if r.returncode or not Path(out_wav).exists():
        return {"lufs": None, "error": f"export de la mezcla falló (código {r.returncode}): {r.stderr.strip()[-300:]}"}
    return medir_wav(out_wav)


def medir_wav(out_wav):
    """Loudness, pico y curva por segundo de una mezcla. Pide a ffmpeg el corto plazo (S) Y el momentáneo (M):
    con solo S los 3 primeros segundos salen mudos (S necesita 3 s de señal) aunque el gancho tenga voz."""
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(out_wav), "-af", "ebur128=peak=true:metadata=1,"
                            "ametadata=print:file=-", "-f", "null", "-"], capture_output=True, text=True)
    except OSError as ex:
        return {"lufs": None, "error": f"ffmpeg no disponible: {ex}", "wav": str(out_wav)}
    res = parse_ebur128(r.stderr, r.stdout)
    res["wav"] = str(out_wav)
    if r.returncode or res["lufs"] is None:
        res["error"] = f"ebur128 no dio loudness (código {r.returncode}): {r.stderr.strip()[-200:]}"
    return res


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
    out, n, sin = [], 0, []
    for tr in seq["audio_tracks"]:
        if tr.get("name") != "Dialogue":
            continue
        for c in clips(tr):
            p = paths.get(c["item"])
            if not p:
                continue
            pj = Path(analisis) / f"{Path(p).stem}.palabras.json"
            if not pj.exists():
                sin.append({"clip": c["id"], "fuente": Path(p).name})     # no medido: no cuenta como «0 dentro»
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
    return {"bordes": n, "dentro_de_palabra": out, "clips_sin_palabras": sin, "medido": not sin}


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


def no_text_copy(project, tmp, tracks=TEXT_TRACKS):
    """Copia del proyecto con las pistas de texto desactivadas; None (y el motivo) si el CLI falla."""
    cp = Path(tmp) / "sin_textos.fcproj"
    seq, _, _ = seq_of(project)
    names = [t.get("name") for t in seq["video_tracks"]]
    lines = [json.dumps({"id": "timeline.setTrack", "params": {"track": f"V{i + 1}", "enabled": False}})
             for i, n in enumerate(names) if n in tracks]
    js = Path(tmp) / "off.jsonl"
    js.write_text("\n".join(lines) + "\n")
    try:
        r = subprocess.run([CLI, "--project", str(project), "--save-as", str(cp), "run", str(js)], capture_output=True, text=True)
    except OSError as ex:
        return None, f"no se pudo ejecutar {CLI}: {ex}"
    if r.returncode or not cp.exists():
        return None, f"copia sin textos falló (código {r.returncode}): {r.stderr.strip()[-200:]}"
    return cp, None


def seq_end(seq):
    # también el audio: un SFX que pasa del último plano alarga el export (negro al final) y cuenta
    ends = [(c["start"] + c["duration"]) / TPS for k in ("video_tracks", "audio_tracks")
            for tr in seq.get(k, []) for c in clips(tr)]
    return max(ends) if ends else 0.0


def main():
    ap = argparse.ArgumentParser(description="Verificación headless de un montaje de FilmCraft (sale con 2 si no se pudo medir).")
    ap.add_argument("project")
    ap.add_argument("--compiled", required=True)
    ap.add_argument("--analisis", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ref")
    ap.add_argument("--segundos", nargs="*", type=float)
    ap.add_argument("--conservar-temporales", action="store_true", help="no borrar los fotogramas renderizados")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    comp = jload(a.compiled)
    avisos = []
    try:
        ds = ds_del_compilado(comp)
    except (FileNotFoundError, KeyError, SystemExit) as ex:
        ds = None
        avisos.append(f"no cargo el DS {comp.get('ds')!r} ({ex}): uso solo las pistas de texto fijas")
    tracks = text_tracks(ds)
    ef = Path(a.compiled).parent / "estado.json"
    estado = jload(ef) if ef.exists() else {}
    seq, paths, _ = seq_of(a.project)
    fallos = []
    res = {"proyecto": a.project, "modo": estado.get("modo")}
    if not ef.exists():
        fallos.append("no hay estado.json junto a compiled.json: no sé dónde están los pop-ups")
    dur = seq_end(seq)
    if dur <= 0:
        fallos.append("la secuencia está vacía")
    res["duracion_s"] = round(dur, 2)
    dcomp = comp.get("duracion")
    res["duracion_compilada_s"] = dcomp
    fotograma = 1 / (comp.get("fps") or 30)
    if dcomp and dur > dcomp + fotograma + 1e-6:
        # algo (un SFX, una capa, un eco) pasa del final: el export acaba en negro con la cola del sonido
        fallos.append(f"la secuencia dura {dur:.2f} s y el compilado {dcomp:.2f} s: algo pasa del final")
    cuts, nmain = main_cuts(seq)
    res["cortes"] = len(cuts)
    res["planos"] = nmain

    tmp_ctx = tempfile.TemporaryDirectory(prefix="fcs_ver_")
    tmpd = Path(tmp_ctx.name)
    errores = []
    # hojas: cortes (antes/después) y transiciones
    tc = sorted({round(max(0, t - 0.25), 3) for t in cuts} | {round(t + 0.25, 3) for t in cuts if t + 0.25 < dur})
    fr = render(a.project, tc, tmpd / "cortes", errores=errores)
    res["hoja_cortes"] = sheet(sorted(fr.items()), out / "hoja_cortes.jpg", cols=10)

    # pop-ups: con textos y sin textos + caras
    pops = [(k, v) for k, v in estado.get("textos", {}).items() if v.get("rol") in
            ("etiqueta", "concepto", "escalon", "eco", "nombre", "tag", "pill")]
    mids = {}
    for k, v in pops:
        mids.setdefault(round(v["start"] + min(v["dur"], 3) / 2, 3), []).append((k, v))
    tm = sorted(mids)
    fr_t = render(a.project, tm, tmpd / "pop", errores=errores)
    fr_n, det, vision_ok = {}, {}, not tm
    if tm:
        cp, err = no_text_copy(a.project, tmpd, tracks)
        if cp is None:
            fallos.append(err)
        else:
            fr_n = render(cp, tm, tmpd / "pop_sin", errores=errores)
        if fr_n:
            try:
                det = detect(list(fr_n.values()))
                vision_ok = True
            except ErrorExterno as ex:
                fallos.append(f"detector de caras: {ex}")
    choques, boxes = [], {}
    medidos = 0
    for t in tm:
        if t not in fr_n:
            continue
        d = det.get(str(Path(fr_n[t]).resolve()))
        if d is None or d.get("error"):
            continue
        medidos += 1
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
    res["textos_vs_caras"] = {"popups": len(pops), "momentos": len(tm), "momentos_renderizados": len(fr_n),
                              "momentos_medidos": medidos, "medido": vision_ok and medidos == len(tm),
                              "choques": choques}
    if medidos < len(tm):
        fallos.append(f"textos frente a caras: solo se midieron {medidos} de {len(tm)} momentos")
    if len(fr) < len(tc):
        fallos.append(f"hoja de cortes: {len(fr)} de {len(tc)} fotogramas")
    if len(fr_t) < len(tm):
        fallos.append(f"hoja de pop-ups: {len(fr_t)} de {len(tm)} fotogramas")

    res["keyframes"] = kf_check(seq)
    res["cortes_en_palabra"] = cut_check(seq, paths, a.analisis)
    sinp = res["cortes_en_palabra"]["clips_sin_palabras"]
    if sinp:
        fallos.append(f"cortes en palabra: {len(sinp)} clip(s) de diálogo sin <fuente>.palabras.json en {a.analisis} "
                      f"({', '.join(sorted({x['fuente'] for x in sinp})[:3])})")
    res["audio"] = loudness(a.project, out / "mezcla.wav")
    if res["audio"].get("lufs") is None:
        fallos.append(f"loudness: {res['audio'].get('error', 'sin cifra')}")
    res["cobertura"] = comp.get("cobertura", {})

    if a.ref:
        rseq, rpaths, _ = seq_of(a.ref)
        rcuts, rn = main_cuts(rseq)
        rdur = seq_end(rseq)
        secs = a.segundos or [round(x, 2) for x in [1.5, 4.5, 7.5, 11.0, 13.8, 16.0, 19.5, 24.0, 27.0, 30.0, 34.0,
                                                    36.5, 40.0, 44.0, 49.0, 52.5, 55.0] if x < max(dur, rdur)]
        fa = render(a.project, [s for s in secs if s < dur], tmpd / "cmp_a", errores=errores)
        fb = render(a.ref, [s for s in secs if s < rdur], tmpd / "cmp_b", errores=errores)
        pares = []
        for s in secs:
            if s in fb:
                pares.append((s, fb[s], f"REF {s:.1f}"))
            if s in fa:
                pares.append((s, fa[s], f"AUTO {s:.1f}"))
        res["hoja_comparacion"] = sheet(pares, out / "hoja_comparacion.jpg", cols=8)
        ra = loudness(a.ref, out / "mezcla_ref.wav")
        pa, pb = [s for s in secs if s < dur], [s for s in secs if s < rdur]
        if len(fa) < len(pa) or len(fb) < len(pb):
            fallos.append(f"comparación con la referencia: {len(fa)} de {len(pa)} fotogramas propios y "
                          f"{len(fb)} de {len(pb)} de la referencia")
        if ra.get("lufs") is None:
            fallos.append(f"loudness de la referencia: {ra.get('error', 'sin cifra')}")
        rtexts = texts_of(rseq)
        obl = list(res["cobertura"].keys())
        res["referencia"] = {"proyecto": a.ref, "duracion_s": round(rdur, 2), "cortes": len(rcuts), "planos": rn,
                             "audio": ra, "obligatorios": {o: cubre(o, rtexts) for o in obl}}
        res["hoja_curvas"] = curves(res["audio"].get("curva_s", []), ra.get("curva_s", []), out / "curvas_lufs.png")
    if a.conservar_temporales:
        res["temporales"] = str(tmpd)
    else:
        tmp_ctx.cleanup()
    res["errores_render"] = errores[:20]
    res["avisos"] = avisos
    res["fallos"] = fallos
    res["verificado"] = not fallos
    jsave(out / "verificacion.json", res)
    a_ = res["audio"]
    print(json.dumps({"estado": "ok" if res["verificado"] else "error", "fallos": fallos,
                      "duracion_s": res["duracion_s"], "cortes": res["cortes"], "lufs": a_.get("lufs"),
                      "pico_dbtp": a_.get("pico_dbtp"),
                      "choques_texto": len(choques) if res["textos_vs_caras"]["medido"] else None,
                      "cortes_dentro_de_palabra": len(res["cortes_en_palabra"]["dentro_de_palabra"]),
                      "keyframes_fuera": res["keyframes"]["n_fuera"],
                      "ref": {k: res["referencia"][k] for k in ("duracion_s", "cortes")} if a.ref else None,
                      "ref_lufs": res["referencia"]["audio"].get("lufs") if a.ref else None}, ensure_ascii=False))
    if fallos:
        print("verificación incompleta: " + "; ".join(fallos), file=sys.stderr)
        sys.exit(2)


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
