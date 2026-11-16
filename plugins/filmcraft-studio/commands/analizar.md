---
description: "Analiza el material grabado de un evento (transcripción, silencios, energía, barridos, caras) con caché"
argument-hint: "<carpeta del evento> [--out carpeta]"
allowed-tools: Bash(python3:*), Bash(export:*), Bash(ls:*), Read, Glob
---

Analiza el material del evento en $ARGUMENTS.

1. Localiza las carpetas: videos crudos, voz procesada (`*_voz`), fotos (con subcarpetas), gráfica y flyer. Prefiere la voz procesada. Si el evento no sigue la estructura `01 … 06 - FilmCraft`, pregunta dónde está cada cosa.
2. La caché del análisis es única por evento: `<evento>/06 - FilmCraft/analisis/` (la comparten todos los modos y slugs; `--out` la cambia). Si ya existe, no reanalices. Si no, mide la duración total con `ffprobe`, di el tiempo estimado (≈ 3 min por minuto de 4K la primera vez; una charla de 45 min son más de 2 h) y lánzalo en segundo plano:
   `export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}; python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze_media.py --out "<evento>/06 - FilmCraft/analisis" --videos <voz> --fotos <fotos> --grafica <gráfica> --flyer <flyer> [--prompt "<vocabulario del DS>"]` (`--prompt` solo si el DS ya está elegido)
3. Al terminar, resume: nº de videos y duración total, palabras transcritas, barridos detectados y fotos con caras. Ofrece lanzar el subagente `analista-material`.
