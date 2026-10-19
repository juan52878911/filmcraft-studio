#!/usr/bin/env python3
"""Transcribe medios de un proyecto FilmCraft con whisper.cpp y prepara su importación (transcript.set).

Uso:
    transcribe_fc.py PROYECTO.fcproj --out DIR [--match _voz] [--lang es]
                     [--prompt "SageMaker, Rekognition, Kiro"] [--model RUTA.bin] [--apply]

- Transcribe cada video del proyecto cuyo nombre contenga --match (por defecto, todos los .mp4/.mov).
- Usa DTW (-dtw <preset> -nfa): los tiempos de segmento de whisper.cpp se adelantan hasta ~1,8 s;
  el t_dtw por token es fiable (≈ fin del token) y cada palabra va del t_dtw anterior al suyo.
- Escribe DIR/import.jsonl. Con --apply lo importa en headless (FilmCraft debe estar CERRADO).
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fclib import CLI, TPS, headless  # noqa: E402

from common import WHISPER_MODEL as DEFAULT_MODEL  # noqa: E402


def words_from_whisper(json_path):
    j = json.load(open(json_path))
    out, prev_end = [], None
    for seg in j["transcription"]:
        seg_start = seg["offsets"]["from"] / 1000
        cur = None
        for t in seg.get("tokens", []):
            txt = t["text"]
            if txt.startswith("[_") or t.get("t_dtw", -1) < 0:
                continue
            te = t["t_dtw"] / 100
            if re.fullmatch(r"[\.\,\?\!\:\;…]+", txt.strip()) and cur:
                cur[0] += txt.strip()
                continue
            if txt.startswith(" ") or cur is None:
                if cur:
                    out.append(cur)
                start = prev_end if prev_end is not None and prev_end <= te else seg_start
                cur = [txt.strip(), max(start, te - 1.2), te]
            else:
                cur[0] += txt
                cur[2] = te
            prev_end = te
        if cur:
            out.append(cur)
    return [w for w in out if w[0] and w[0] != "-"]


def media_items(project):
    p = headless(project, "inspect", "project")
    p = p.get("project", p)
    items = {}

    def walk(n):
        for c in n.get("children", []):
            if "children" in c:
                walk(c)
            else:
                items[c["name"]] = (c["item"], c.get("path"))
    walk(p["root"])
    return items


def source_path(project, name):
    """Ruta real del medio, leída del .fcproj."""
    j = json.load(open(project))
    for it in j["project"]["items"].values():
        if it.get("name") == name:
            media = it.get("kind", {}).get("Media", {}).get("media", {})
            return (media.get("File") or {}).get("path")
    return None


def whisper_words(src, stem, model=DEFAULT_MODEL, lang="es", prompt="", dtw="medium"):
    """Transcribe un medio con whisper.cpp y devuelve [[palabra, inicio_s, fin_s], ...] (tiempos de la fuente)."""
    stem = Path(stem)
    wav = stem.with_suffix(".wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", str(wav)], check=True)
    cmd = ["whisper-cli", "-m", model, "-l", lang, "-ojf", "-dtw", dtw, "-nfa", "-of", str(stem), "-t", "8", "-np", str(wav)]
    if prompt:
        cmd += ["--prompt", prompt]
    subprocess.run(cmd, check=True, capture_output=True)
    wav.unlink(missing_ok=True)
    return words_from_whisper(f"{stem}.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--out", required=True)
    ap.add_argument("--match", default="")
    ap.add_argument("--lang", default="es")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--dtw", default="medium", help="preset DTW acorde al modelo (tiny, base, small, medium, large.v3…)")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    lines = []
    for name, (item, _) in sorted(media_items(a.project).items()):
        if not name.lower().endswith((".mp4", ".mov", ".m4v", ".wav", ".mp3")) or a.match not in name:
            continue
        src = source_path(a.project, name)
        if not src or not Path(src).exists():
            print(f"sin ruta para {name}; salto", file=sys.stderr)
            continue
        ws = whisper_words(src, out / Path(name).stem, a.model, a.lang, a.prompt, a.dtw)
        lines.append({"id": "transcript.set", "params": {"item": item, "transcript": {
            "language": a.lang, "speakers": [{"name": "Ponente"}],
            "words": [{"text": w, "start": round(s * TPS), "end": round(max(e, s + 0.05) * TPS), "speaker": 0} for w, s, e in ws]}}})
        print(f"{name}: item {item}, {len(ws)} palabras")

    jl = out / "import.jsonl"
    jl.write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in lines) + "\n")
    print("JSONL:", jl)
    if a.apply:
        r = subprocess.run([CLI, "--project", a.project, "--save", "run", str(jl), "--compact"], capture_output=True, text=True)
        ok = r.stdout.count('"ok":true')
        print(f"importadas {ok}/{len(lines)} transcripciones" + ("" if ok == len(lines) else f"\n{r.stdout[-400:]}{r.stderr[-400:]}"))


if __name__ == "__main__":
    main()
