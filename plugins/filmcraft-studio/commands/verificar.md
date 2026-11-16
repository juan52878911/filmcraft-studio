---
description: "Verifica un montaje de FilmCraft (hojas, textos y caras, keyframes, cortes, loudness); opcionalmente compara"
argument-hint: "<proyecto.fcproj> [--ref otro.fcproj]"
disable-model-invocation: true
allowed-tools: Bash(python3:*), Bash(export:*), Bash(ffmpeg:*), Bash(ffprobe:*), Read, Glob, Agent
---

Verifica sin escribir el proyecto. Argumentos: $ARGUMENTS

1. Si la app tiene ese proyecto abierto, guarda por el socket (`file.save`) antes de leerlo.
2. `export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}; python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify.py <proyecto> --compiled <trabajo>/compiled.json --analisis "<evento>/06 - FilmCraft/analisis" --out <trabajo>/verificacion [--ref …]`. Si el proyecto no se hizo con el plugin (sin compiled.json), usa `render_sheet.py` y mide la mezcla `.wav` a mano (ver `${CLAUDE_PLUGIN_ROOT}/skills/editor-filmcraft/references/verificacion.md`).
   Si sale con **2**, la verificación está incompleta (`verificado: false`): lee `fallos` en `verificacion.json`, dilo tal cual y no lo des por verificado.
3. Mira las hojas (Read) antes de opinar. Lanza el subagente `critico` si es para publicar.
4. Informa cifras y evidencias; di lo que no se pudo verificar.
