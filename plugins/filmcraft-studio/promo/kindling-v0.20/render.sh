#!/usr/bin/env bash
# Renderiza un estilo del promo de kindling v0.20 de punta a punta.
# Uso: ./render.sh brasa|blueprint|riso|riso_v [salida.mp4]
# Necesita: vhs, ffmpeg, python3 con numpy y Pillow, y un daemon de kling con la imagen redis:7-alpine.
set -euo pipefail
cd "$(dirname "$0")"
estilo=${1:?estilo: brasa, blueprint, riso o riso_v}
out=${2:-kindling-v0.20-$estilo.mp4}
build=${BUILD_DIR:-build}
mkdir -p "$build"

case $estilo in
  riso_v) tape=term_v.tape; term=term_v.mp4; video=riso_v.py; audio=audio_riso_v.py ;;
  brasa)  tape=term.tape;   term=term.mp4;   video=brasa.py;  audio=audio_brasa.py ;;
  *)      tape=term.tape;   term=term.mp4;   video=$estilo.py; audio=audio_$estilo.py ;;
esac

# 1. Material real. Un primer up crea la plantilla para que el grabado muestre el arranque en caliente.
if [ ! -f "$build/$term" ]; then
  (cd demo && kling compose up -d >/dev/null && kling compose down -v >/dev/null)
  vhs "$tape"
  mv "$term" "$build/$term"
  (cd demo && kling compose down -v >/dev/null 2>&1 || true)
fi

# 2. Audio en la misma rejilla de beats y máster a -14 LUFS.
python3 "$audio" "$build/$term" "$build/$estilo-raw.wav"
ffmpeg -v error -y -i "$build/$estilo-raw.wav" \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.84:level=false" -ar 48000 "$build/$estilo.wav"

# 3. Imagen fotograma a fotograma y mezcla final.
python3 "$video" "$build/$term" "$build/frames-${term%.mp4}" "$build/$estilo-video.mp4"
ffmpeg -v error -y -i "$build/$estilo-video.mp4" -i "$build/$estilo.wav" -c:v libx264 -preset slow -crf 22 \
  -pix_fmt yuv420p -c:a aac -b:a 256k -movflags +faststart -shortest "$out"
ffmpeg -hide_banner -i "$out" -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I:|Peak:)"
echo "$out"
