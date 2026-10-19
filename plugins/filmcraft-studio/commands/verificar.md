---
description: Verifica un montaje de FilmCraft (hojas, textos frente a caras, keyframes, cortes en palabra, loudness) y opcionalmente lo compara con otro
argument-hint: <proyecto.fcproj> [--ref otro.fcproj]
---

Verifica sin escribir el proyecto. Argumentos: $ARGUMENTS

1. Si la app tiene ese proyecto abierto, guarda por el socket (`file.save`) antes de leerlo.
2. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify.py <proyecto> --compiled <trabajo>/compiled.json --analisis <trabajo>/analisis --out <trabajo>/verificacion [--ref …]`. Si el proyecto no se hizo con el plugin (sin compiled.json), usa `render_sheet.py` y mide la mezcla `.wav` a mano (ver `editor-filmcraft/references/verificacion.md`).
3. Mira las hojas (Read) antes de opinar. Lanza el subagente `critico` si es para publicar.
4. Informa cifras y evidencias; di lo que no se pudo verificar.
