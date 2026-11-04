#!/usr/bin/env bash
# Ensambla en FilmCraft (headless) escenas renderizadas por código: gancho (brasa) + demo (blueprint) + cierre del DS.
# Uso: ./ensamblar.sh   (después de ../render.sh brasa y ../render.sh blueprint)
set -euo pipefail
cd "$(dirname "$0")"
S=$(cd ../../../scripts && pwd)
B=../build
W=${WORK_DIR:-work}
mkdir -p "$W/escenas" "$W/cat"

# 1. Escenas sin audio a partir de los renders; la música va aparte.
ffmpeg -v error -y -i "$B/brasa-video.mp4" -t 3.58 -c:v libx264 -crf 18 -an "$W/escenas/gancho.mp4"
ffmpeg -v error -y -ss 3.58 -i "$B/blueprint-video.mp4" -t 8.95 -c:v libx264 -crf 18 -an "$W/escenas/demo.mp4"

# 2. Copia del DS con la mezcla del motor de código como música.
rm -rf "$W/cat/promo-brasa-escarcha"
cp -R ../../../design-systems/promo-brasa-escarcha "$W/cat/"
python3 - "$W" "$B" <<'PY'
import json, sys, pathlib
w, b = sys.argv[1:]
p = pathlib.Path(w, "cat/promo-brasa-escarcha/ds.json")
d = json.loads(p.read_text())
d["musica"]["archivo"] = str(pathlib.Path(b, "brasa.wav").resolve())
p.write_text(json.dumps(d, ensure_ascii=False, indent=1))
PY
export FILMCRAFT_DS_CATALOGO="$PWD/$W/cat"

# 3. Análisis, compilación, aplicación y verificación.
python3 "$S/analyze_media.py" --out "$W/analisis" --videos "$W/escenas/gancho.mp4" "$W/escenas/demo.mp4" --sin-vision
python3 "$S/plan_compile.py" plan.json --analisis "$W/analisis" --out "$W/compiled.json"
python3 "$S/apply_plan.py" "$W/compiled.json" --headless --out "$W/ensamblado.fcproj" --work "$W"
python3 "$S/render_sheet.py" "$W/ensamblado.fcproj" "$W/hoja.jpg" 0.8 2.5 4.5 7.0 10.0 12.8 13.6 14.8 --cols 4 --scale 0.3
python3 "$S/verify.py" "$W/ensamblado.fcproj" --compiled "$W/compiled.json" --analisis "$W/analisis" --out "$W/verificacion"
