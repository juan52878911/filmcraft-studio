---
description: Analiza el material de un evento (transcripción, silencios, energía, barridos de cámara, caras) con caché
argument-hint: <carpeta del evento> [--out carpeta]
---

Analiza el material del evento en $ARGUMENTS.

1. Localiza las carpetas: videos crudos, voz procesada (`*_voz`), fotos (con subcarpetas), gráfica y flyer. Prefiere la voz procesada.
2. Lanza en segundo plano (puede tardar ~3 min por minuto de 4K la primera vez):
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze_media.py --out <trabajo>/analisis --videos <voz> --fotos <fotos> --grafica <gráfica> --flyer <flyer> --prompt "<vocabulario del DS>"`
   El trabajo por defecto es `<evento>/06 - FilmCraft/auto/analisis`.
3. Al terminar, resume: nº de videos y duración total, palabras transcritas, barridos detectados y fotos con caras. Ofrece lanzar el subagente `analista-material`.
