---
description: "Verifica un montaje de FilmCraft (hojas, textos y caras, keyframes, cortes, loudness); opcionalmente compara"
argument-hint: "<proyecto.fcproj> [--ref otro.fcproj]"
disable-model-invocation: true
allowed-tools: Bash(python3:*), Bash(${CLAUDE_PLUGIN_ROOT}/bin/cine:*), Bash(export:*), Bash(ffmpeg:*), Bash(ffprobe:*), Read, Glob, Agent
---

Verifica sin escribir el proyecto. Argumentos: $ARGUMENTS

1. Si la app tiene ese proyecto abierto, guarda por el socket (`file.save`) antes de leerlo.
2. `export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}; python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify.py <proyecto> --compiled <trabajo>/compiled.json --analisis "<evento>/06 - FilmCraft/analisis" --out <trabajo>/verificacion [--ref …]`. Si el proyecto no se hizo con el plugin (sin compiled.json), usa `render_sheet.py` y mide la mezcla `.wav` a mano (ver `${CLAUDE_PLUGIN_ROOT}/skills/editor-filmcraft/references/verificacion.md`).
   Si sale con **2**, la verificación está incompleta (`verificado: false`): lee `fallos` en `verificacion.json`, dilo tal cual y no lo des por verificado.
3. Puntúa sin IA: `${CLAUDE_PLUGIN_ROOT}/bin/cine puntuar --ds <id> --compiled <trabajo>/compiled.json --verificacion <trabajo>/verificacion/verificacion.json [--biblia <trabajo>/preproduccion/biblia.json] --out <trabajo>/verificacion/ejes.json`. Si hay biblia, `cine criterios --biblia … --verificacion … --compiled … --md` da la tabla de criterios.
4. Si es para publicar, lanza el subagente `critico-juicio` con `ejes.json` y la carpeta de trabajo (mira él las hojas; tú no le pases conclusiones) y guarda su JSON en `<trabajo>/verificacion/juicio.json`; después `cine nota --ejes … --juicio … > <trabajo>/verificacion/nota.json` da la nota, el veredicto y los 5 arreglos. Si no, enseña los ejes medidos y mira tú las hojas (Read) antes de opinar.
5. Informa cifras y evidencias; di lo que no se pudo verificar (`sin_medir`).
