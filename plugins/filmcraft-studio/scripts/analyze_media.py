#!/usr/bin/env python3
"""Inventario y análisis del material con caché: transcripción, silencios, energía, barridos y caras.

Uso:
    analyze_media.py --out WORK/analisis --videos DIR_O_ARCHIVOS... [--fotos DIR...] [--grafica DIR]
                     [--flyer F] [--prompt "SageMaker, Rekognition"] [--lang es] [--sin-vision] [--sin-movimiento]

- Las voces procesadas (`*_voz.mp4`) tienen prioridad: si hay `X_voz.mp4` y `X.mp4`, se analiza `X_voz`.
- Caché por archivo (tamaño + fecha) en OUT/<stem>.*.json: volver a correrlo solo analiza lo nuevo.
- Escribe OUT/material.json (índice) y OUT/transcripcion.md (frases con tiempos de la fuente, para leer).
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import IMAGE_EXT, VIDEO_EXT, WHISPER_MODEL, detect, ffprobe, jload, jsave  # noqa: E402


def stamp(p):
    st = Path(p).stat()
    return f"{st.st_size}-{int(st.st_mtime)}"


def cached(out, stem, kind, src, fn, extra=""):
    f = out / f"{stem}.{kind}.json"
    key = stamp(src) + extra
    if f.exists():
        j = jload(f)
        if j.get("_stamp") == key:
            return j["data"]
    data = fn()
    jsave(f, {"_stamp": key, "data": data})
    return data


def transcribe(src, out, stem, prompt, lang):
    from transcribe_fc import whisper_words
    ws = whisper_words(src, out / f"{stem}.whisper", WHISPER_MODEL, lang, prompt, "medium")
    return [{"w": w, "s": round(s, 3), "e": round(max(e, s + 0.05), 3)} for w, s, e in ws]


def silences(src, noise=-35, mind=0.35):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-vn", "-af",
                        f"silencedetect=noise={noise}dB:d={mind}", "-f", "null", "-"], capture_output=True, text=True)
    out, cur = [], None
    for line in r.stderr.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m:
            cur = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and cur is not None:
            out.append([round(cur, 3), round(float(m.group(1)), 3)])
            cur = None
    return out


def energy(src, step=0.5):
    """RMS en dBFS por ventana (para tono y momentos de energía: aplausos, risas, gritos)."""
    import numpy as np
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "8000",
                        "-f", "s16le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768
    n = int(8000 * step)
    out = []
    for i in range(0, len(x) - n + 1, n):
        rms = float(np.sqrt(np.mean(x[i:i + n] ** 2)) + 1e-9)
        out.append(round(20 * np.log10(rms), 1))
    return out


def motion(src):
    from camera_motion import scan_rows
    rows, _ = scan_rows(str(src))
    return rows


def vision_video(src, dur, every=1.0):
    """Caras y personas cada `every` s (tiempo de la fuente)."""
    tmp = Path(tempfile.mkdtemp(prefix="fcs_vis_"))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-hwaccel", "videotoolbox", "-i", str(src), "-vf",
                    f"fps=1/{every},scale=360:-2", "-q:v", "4", str(tmp / "f_%05d.jpg")], check=True)
    files = sorted(tmp.glob("f_*.jpg"))
    det = detect(files)
    out = []
    for i, f in enumerate(files):
        d = det.get(str(f.resolve()), {})
        # el filtro fps de ffmpeg toma el fotograma más cercano a i·every
        out.append({"t": round(i * every, 2), "faces": d.get("faces", []), "people": d.get("people", [])})
        f.unlink()
    tmp.rmdir()
    return out


def refine(words, sil):
    """Los tiempos de whisper (DTW) dan bien el FIN de cada palabra; el inicio se hereda del fin anterior
    y se come los silencios. Si un silencio medido cae dentro de la palabra, la palabra empieza al acabar."""
    out = []
    for w in words:
        s, e = w["s"], w["e"]
        for a, b in sil:
            if a < e and b > s and b < e - 0.04:
                s = max(s, b - 0.02)
        out.append({"w": w["w"], "s": round(s, 3), "e": e})
    return out


def sentences(words, sil, max_s=6.0):
    """Frases cortas para leer y elegir cortes: punto/interrogación, silencio ≥ 0,3 s o coma pasados 4 s."""
    out, cur = [], []
    starts = [b for a, b in sil if b - a >= 0.3]
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        dur = w["e"] - cur[0]["s"]
        pausa = nxt is not None and any(w["e"] - 0.15 <= b <= nxt["s"] + 0.2 for b in starts)
        if (nxt is None or re.search(r"[.?!…]$", w["w"]) or pausa or (dur > 4 and w["w"].endswith(","))
                or dur > max_s):
            out.append({"s": cur[0]["s"], "e": cur[-1]["e"], "texto": " ".join(x["w"] for x in cur),
                        "pausa_despues": bool(pausa)})
            cur = []
    return out


def collect(paths, exts):
    out = []
    for p in paths:
        p = Path(p).expanduser().resolve()
        if p.is_dir():
            out += [f for f in sorted(p.rglob("*")) if f.suffix.lower() in exts and not f.name.startswith("._")
                    and "RAW" not in f.parts]
        elif p.exists() and p.suffix.lower() in exts:
            out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--videos", nargs="+", required=True)
    ap.add_argument("--fotos", nargs="*", default=[])
    ap.add_argument("--grafica")
    ap.add_argument("--flyer")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--lang", default="es")
    ap.add_argument("--sin-vision", action="store_true")
    ap.add_argument("--sin-movimiento", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    vids = collect(a.videos, VIDEO_EXT)
    by_base = {}
    for v in vids:
        base = v.stem.removesuffix("_voz")
        if base not in by_base or v.stem.endswith("_voz"):
            by_base[base] = v
    mat = {"videos": [], "fotos": [], "grafica": [], "flyer": None}
    md = ["# Transcripción del material", "",
          "Tiempos en segundos de la FUENTE. Cada frase: [inicio–fin]. Silencios ≥ 0,4 s marcados con ·", ""]
    for base, v in sorted(by_base.items()):
        stem = v.stem
        info = ffprobe(v)
        print(f"· {v.name}: {info['dur']:.1f} s, {info['w']}x{info['h']} @ {info['fps']}", flush=True)
        words = cached(out, stem, "words", v, lambda: transcribe(v, out, stem, a.prompt, a.lang), a.prompt) if info["audio"] else []
        sil = cached(out, stem, "silences", v, lambda: silences(v)) if info["audio"] else []
        en = cached(out, stem, "energy", v, lambda: energy(v)) if info["audio"] else []
        mo = [] if a.sin_movimiento else cached(out, stem, "motion", v, lambda: motion(v))
        vi = [] if a.sin_vision else cached(out, stem, "vision", v, lambda: vision_video(v, info["dur"]))
        words = refine(words, sil)
        jsave(out / f"{stem}.palabras.json", words)
        sents = sentences(words, sil)
        loud = sorted(range(len(en)), key=lambda i: -en[i])[:5]
        mat["videos"].append({
            "stem": stem, "path": str(v), **info, "palabras": len(words), "frases": sents, "silencios": sil,
            "barridos": mo, "energia_media_db": round(sum(en) / len(en), 1) if en else None,
            "picos_energia_s": [round(i * 0.5, 1) for i in sorted(loud)],
            "vision": f"{stem}.vision.json" if vi else None, "palabras_json": f"{stem}.palabras.json" if words else None})
        md.append(f"## {stem}  ({info['dur']:.1f} s)")
        if mo:
            md.append("Barridos de cámara: " + ", ".join(f"{m['t']}s {m['dir']}" for m in mo))
        for s in sents:
            md.append(f"- [{s['s']:.2f}–{s['e']:.2f}] {s['texto']}{' ·' if s['pausa_despues'] else ''}")
        md.append("")
    fotos = collect(a.fotos, IMAGE_EXT)
    if fotos:
        from PIL import Image
        conv = out / "fotos"
        conv.mkdir(exist_ok=True)
        usable = []
        for f in fotos:
            p = f
            if f.suffix.lower() in (".avif", ".heic", ".webp"):
                p = conv / (f.stem[:40] + ".png")
                if not p.exists():
                    subprocess.run(["sips", "-s", "format", "png", str(f), "--out", str(p)], capture_output=True)
            if p.exists():
                usable.append((f, p))
        det = detect([p for _, p in usable])
        for f, p in usable:
            with Image.open(p) as im:
                w, h = im.size
            d = det.get(str(Path(p).resolve()), {})
            mat["fotos"].append({"path": str(p), "original": str(f), "w": w, "h": h,
                                 "caras": len(d.get("faces", [])), "personas": len(d.get("people", []))})
    if a.grafica:
        mat["grafica"] = [str(f) for f in collect([a.grafica], IMAGE_EXT)]
    if a.flyer:
        mat["flyer"] = str(Path(a.flyer).expanduser().resolve())
    jsave(out / "material.json", mat)
    (out / "transcripcion.md").write_text("\n".join(md) + "\n")
    print(f"material.json: {len(mat['videos'])} videos, {len(mat['fotos'])} fotos -> {out}")


if __name__ == "__main__":
    main()
