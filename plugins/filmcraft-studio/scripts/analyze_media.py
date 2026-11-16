#!/usr/bin/env python3
"""Inventario y análisis del material con caché: transcripción, silencios, energía, barridos y caras.

Uso:
    analyze_media.py --out WORK/analisis --videos DIR_O_ARCHIVOS... [--fotos DIR...] [--grafica DIR]
                     [--flyer F] [--prompt "SageMaker, Rekognition"] [--lang es] [--sin-vision] [--sin-movimiento]

- Las voces procesadas (`*_voz.mp4`) tienen prioridad: si hay `X_voz.mp4` y `X.mp4`, se analiza `X_voz`.
- Caché por archivo en OUT/<stem>.*.json, con clave = tamaño + fecha + parámetros (idioma, modelo y prompt
  para la transcripción) + versión del script: volver a correrlo solo analiza lo nuevo o lo que cambió.
  Un fallo de ffmpeg, whisper o Vision corta con error y NO se guarda en la caché.
- Fuera de macOS no hay detector de caras (Apple Vision): se avisa y se sigue como con --sin-vision.
- Escribe OUT/material.json (índice) y OUT/transcripcion.md (frases con tiempos de la fuente, para leer).
"""
import argparse
import hashlib
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (IMAGE_EXT, VIDEO_EXT, WHISPER_MODEL, ErrorExterno, cli, detect, es_macos, ffprobe,  # noqa: E402
                    jload, jsave, run)

CACHE_VERSION = "2"                     # súbela si cambia el formato o el cálculo de algo cacheado
ANOTACION = ("(", "[", "*", "♪")        # «(sonido distorsionado)», «[música]»: anotaciones de whisper, no voz


def stamp(p):
    st = Path(p).stat()
    return f"{st.st_size}-{int(st.st_mtime)}"


def cache_key(src, extra=""):
    return f"v{CACHE_VERSION}-{stamp(src)}" + (f"|{extra}" if extra else "")


def cached(out, stem, kind, src, fn, extra=""):
    """Devuelve el dato cacheado si la clave coincide; si no, lo calcula. Si fn() lanza, no se guarda nada."""
    f = out / f"{stem}.{kind}.json"
    key = cache_key(src, extra)
    if f.exists():
        try:
            j = jload(f)
        except ValueError:
            j = {}
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
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-vn", "-af",
             f"silencedetect=noise={noise}dB:d={mind}", "-f", "null", "-"], que=f"ffmpeg silencedetect {Path(src).name}",
            text=True)
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
    r = run(["ffmpeg", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "8000",
             "-f", "s16le", "-"], que=f"ffmpeg energía {Path(src).name}")
    if not r.stdout:
        raise ErrorExterno(f"ffmpeg no devolvió audio de {src}")
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
    try:
        hw = ["-hwaccel", "videotoolbox"] if es_macos() else []
        run(["ffmpeg", "-loglevel", "error", *hw, "-i", str(src), "-vf",
             f"fps=1/{every},scale=360:-2", "-q:v", "4", str(tmp / "f_%05d.jpg")], que=f"ffmpeg fotogramas {Path(src).name}")
        files = sorted(tmp.glob("f_*.jpg"))
        if not files and dur > 0.5:
            raise ErrorExterno(f"ffmpeg no sacó fotogramas de {src}")
        det = detect(files)
        out, fallidos = [], 0
        for i, f in enumerate(files):
            d = det.get(str(f.resolve()))
            # el filtro fps de ffmpeg toma el fotograma más cercano a i·every
            row = {"t": round(i * every, 2), "faces": (d or {}).get("faces", []), "people": (d or {}).get("people", [])}
            if d is None or d.get("error"):      # «sin caras» no medido: plan_compile avisa si un pop-up cae cerca
                row["error"] = (d or {}).get("error") or "el detector no devolvió este fotograma"
                fallidos += 1
            out.append(row)
        if files and fallidos == len(files):
            raise ErrorExterno(f"el detector de caras falló en los {len(files)} fotogramas de {Path(src).name}: "
                               f"{out[0]['error']}")
        if fallidos:
            print(f"aviso: el detector de caras falló en {fallidos} de {len(files)} fotogramas de {Path(src).name}",
                  file=sys.stderr)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


ANOTACION_MAX = 6          # palabras dentro de una anotación sin cerrar antes de darla por voz
ANOTACION_HUECO_S = 1.0    # un hueco así tras la anotación la cierra: lo que sigue es otra frase


def refine(words, sil, avisos=None):
    """Los tiempos de whisper (DTW) dan bien el FIN de cada palabra; el inicio se hereda del fin anterior
    y se come los silencios. Si un silencio medido cae dentro de la palabra, la palabra empieza al acabar.

    Las anotaciones de whisper («(aplausos)», «[música]», «♪ … ♪») se descartan. Una que whisper no cierra
    no se come el resto de la transcripción: se cierra sola tras un hueco de ANOTACION_HUECO_S o, si pasan
    ANOTACION_MAX palabras sin cierre, esas palabras se devuelven como voz (y va un aviso a `avisos`)."""
    out, dentro, buf, last_e = [], None, [], None
    cierre = {"(": ")", "[": "]", "*": "*", "♪": "♪"}
    avisos = avisos if avisos is not None else []

    def emit(w):
        s, e = w["s"], w["e"]
        for a, b in sil:
            if a < e and b > s and b < e - 0.04:
                s = max(s, b - 0.02)
        out.append({"w": w["w"], "s": round(s, 3), "e": e})

    for w in words:
        txt = (w["w"] or "").strip()
        if dentro is not None and last_e is not None and w["s"] - last_e > ANOTACION_HUECO_S:
            avisos.append(f"anotación sin cerrar en {last_e:.2f} s: la cierro en el hueco")
            dentro, buf = None, []
        # anotaciones de whisper («(sonido distorsionado)», «[música]», «♪ … ♪»): ni subtítulo ni «hay voz»
        if dentro is None and txt.startswith(ANOTACION):
            fin = cierre[txt[0]]
            if not (len(txt) > 1 and txt.rstrip(".,;:!?").endswith(fin)):
                dentro, buf = fin, []
            last_e = w["e"]
            continue
        if dentro is not None:
            last_e = w["e"]
            if txt.rstrip(".,;:!?").endswith(dentro):
                dentro, buf = None, []
                continue
            buf.append(w)
            if len(buf) > ANOTACION_MAX:      # no era una anotación: era voz tras un «(» suelto
                avisos.append(f"anotación sin cerrar en {buf[0]['s']:.2f} s: {len(buf)} palabras sin cierre, las doy por voz")
                for x in buf:
                    if (x["w"] or "").strip():
                        emit(x)
                dentro, buf = None, []
            continue
        if not txt:
            continue
        emit(w)
    if dentro is not None and buf:
        avisos.append(f"anotación sin cerrar al final ({len(buf)} palabras descartadas desde {buf[0]['s']:.2f} s)")
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
            # «RAW» se excluye DENTRO de la carpeta dada (no por la ruta absoluta: --videos …/RAW/evento vale)
            out += [f for f in sorted(p.rglob("*")) if f.suffix.lower() in exts and not f.name.startswith("._")
                    and "RAW" not in f.relative_to(p).parts]
        elif p.exists() and p.suffix.lower() in exts:
            out.append(p)
    return out


def to_png(f, conv):
    """Convierte HEIC/AVIF/WebP a PNG con un nombre único por ruta; rehace si el original cambia."""
    h = hashlib.sha1(str(f).encode()).hexdigest()[:8]
    p = conv / f"{f.stem[:40]}-{h}.png"
    if p.exists() and p.stat().st_mtime >= f.stat().st_mtime:
        return p
    try:
        from PIL import Image
        try:
            import pillow_heif  # noqa: F401  (opcional: HEIC/AVIF en Pillow)
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
        with Image.open(f) as im:
            im.save(p)
        return p
    except Exception as ex:                      # noqa: BLE001 — Pillow lanza tipos variados según el formato
        if es_macos() and shutil.which("sips"):
            run(["sips", "-s", "format", "png", str(f), "--out", str(p)], que=f"sips {f.name}")
            return p if p.exists() else None
        print(f"aviso: no puedo convertir {f.name} ({ex}); instala pillow-heif. La salto.", file=sys.stderr)
        return None


def main():
    ap = argparse.ArgumentParser(description="Inventario y análisis del material con caché.")
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
    if not a.sin_vision and not es_macos():
        print(f"aviso: el detector de caras necesita macOS (Apple Vision); en {sys.platform} sigo sin visión "
              "(los textos no sabrán dónde están las caras)", file=sys.stderr)
        a.sin_vision = True
    model_id = Path(WHISPER_MODEL).name

    vids = collect(a.videos, VIDEO_EXT)
    by_base = {}
    for v in vids:
        base = v.stem.removesuffix("_voz")
        if base in by_base and by_base[base].stem == v.stem:
            print(f"aviso: dos videos se llaman {v.name} ({by_base[base]} y {v}); analizo solo el primero. "
                  "Renombra uno para usar los dos.", file=sys.stderr)
            continue
        if base not in by_base or v.stem.endswith("_voz"):
            by_base[base] = v
    mat = {"videos": [], "fotos": [], "grafica": [], "flyer": None, "lang": a.lang, "modelo_whisper": model_id}
    md = ["# Transcripción del material", "",
          "Tiempos en segundos de la FUENTE. Cada frase: [inicio–fin]. Silencios ≥ 0,4 s marcados con ·", ""]
    for base, v in sorted(by_base.items()):
        stem = v.stem
        info = ffprobe(v, check=True)
        print(f"· {v.name}: {info['dur']:.1f} s, {info['w']}x{info['h']} @ {info['fps']}", flush=True)
        wkey = f"lang={a.lang}|modelo={model_id}|prompt={a.prompt}"
        words = cached(out, stem, "words", v, lambda: transcribe(v, out, stem, a.prompt, a.lang), wkey) if info["audio"] else []
        sil = cached(out, stem, "silences", v, lambda: silences(v)) if info["audio"] else []
        en = cached(out, stem, "energy", v, lambda: energy(v)) if info["audio"] else []
        mo = [] if a.sin_movimiento else cached(out, stem, "motion", v, lambda: motion(v))
        vi = [] if a.sin_vision else cached(out, stem, "vision", v, lambda: vision_video(v, info["dur"]))
        avisos_tr = []
        words = refine(words, sil, avisos_tr)
        for x in avisos_tr:
            print(f"aviso: {v.name}: {x}", file=sys.stderr)
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
                p = to_png(f, conv)
            if p and p.exists():
                usable.append((f, p))
        det = {} if a.sin_vision else detect([p for _, p in usable])
        for f, p in usable:
            with Image.open(p) as im:
                w, h = im.size
            d = det.get(str(Path(p).resolve()), {})
            mat["fotos"].append({"path": str(p), "original": str(f), "w": w, "h": h,
                                 "caras": None if a.sin_vision else len(d.get("faces", [])),
                                 "personas": None if a.sin_vision else len(d.get("people", []))})
    if a.grafica:
        mat["grafica"] = [str(f) for f in collect([a.grafica], IMAGE_EXT)]
    if a.flyer:
        mat["flyer"] = str(Path(a.flyer).expanduser().resolve())
    jsave(out / "material.json", mat)
    (out / "transcripcion.md").write_text("\n".join(md) + "\n")
    print(f"material.json: {len(mat['videos'])} videos, {len(mat['fotos'])} fotos -> {out}")


if __name__ == "__main__":
    cli(main)
