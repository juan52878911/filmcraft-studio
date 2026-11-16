---
description: "Exporta un montaje o una promo a video solo cuando el usuario lo pide («expórtalo», «sácame el MP4») y mide duración, loudness y pico"
argument-hint: "<proyecto.fcproj> [--destino ruta.mp4]"
---

Exporta SOLO porque el usuario lo pidió (con este comando o en texto); si nadie lo pidió, no sigas. Argumentos: $ARGUMENTS

Una promo por código no tiene `.fcproj`: su entrega es el MP4 de `render.sh` (paso 8 de la skill `promo-codigo`); este comando vale para ella solo si se ensambló en FilmCraft.

1. Confirma destino y nombre. Sin destino explícito, pregunta: nunca escribas en las carpetas del usuario sin que lo diga.
2. Si la app tiene el proyecto abierto, `file.save` por el socket. Lanza en segundo plano (≈ 7 min por minuto en 4K → 1080):
   `"${FILMCRAFT_CLI:-$(command -v filmcraft-cli || echo "$HOME/.local/bin/filmcraft-cli")}" --project <proyecto> export <destino>.mp4`
   (mismo orden que `fclib.CLI`, el doctor y `.mcp.json`: `$FILMCRAFT_CLI` → `filmcraft-cli` del PATH → `~/.local/bin/filmcraft-cli`; si no aparece, `/filmcraft-studio:doctor`).
3. Al terminar, mide: duración (ffprobe), loudness integrada y pico real (`ffmpeg -af ebur128=peak=true`). Si está fuera de −14 ± 1 LUFS o el pico supera −1 dBTP, dilo y propón el arreglo.
