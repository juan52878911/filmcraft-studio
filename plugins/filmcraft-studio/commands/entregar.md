---
description: Exporta el montaje a video (solo cuando el usuario lo pide) y mide el resultado
argument-hint: <proyecto.fcproj> [--destino ruta.mp4]
---

Exporta SOLO porque el usuario lo pidió. Argumentos: $ARGUMENTS

1. Confirma destino y nombre. Sin destino explícito, pregunta: nunca escribas en las carpetas de Juan sin que lo diga.
2. Si la app tiene el proyecto abierto, `file.save` por el socket. Lanza en segundo plano (≈7 min por minuto en 4K → 1080):
   `~/.local/bin/filmcraft-cli --project <proyecto> export <destino>.mp4`
3. Al terminar, mide: duración (ffprobe), loudness integrada y pico real (`ffmpeg -af ebur128=peak=true`). Si está fuera de −14 ± 1 LUFS o el pico supera −1 dBTP, dilo y propón el arreglo.
