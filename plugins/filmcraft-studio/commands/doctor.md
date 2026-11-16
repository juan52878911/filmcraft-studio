---
description: "Comprueba que está todo lo necesario (FilmCraft, ffmpeg, whisper, Python, Blender, fuentes) y cómo arreglar lo que falte"
argument-hint: "[--ds id] [--para camara|promo|motor]"
disable-model-invocation: true
allowed-tools: Bash(python3:*), Bash(export:*), Read
---

Diagnóstico del entorno de filmcraft-studio. Argumentos: $ARGUMENTS

1. Ejecuta: `export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}; python3 ${CLAUDE_PLUGIN_ROOT}/scripts/herramientas.py --doctor $ARGUMENTS`
   Comprueba FilmCraft y `filmcraft-cli` (PATH o `$FILMCRAFT_CLI`), `ffmpeg`/`ffprobe`, whisper y su modelo ggml (`$FILMCRAFT_WHISPER_MODEL`, `<datos del plugin>/models/`, `~/.cache/filmcraft-studio/models/` o `~/.cache/whisper/`; obligatorios con `--para camara`, recomendados sin él), `swiftc`, Blender, los paquetes Python y, con `--ds <id>`, las fuentes de ese design system. Sale con 0 si todo lo imprescindible está y con 1 si falta algo. Antes de montar material grabado, `--para camara`; antes de una promo, `--para promo` (FilmCraft pasa a recomendado y se comprueba VHS). Un motor suelto en los argumentos (`camara`, `promo`…) se pasa como `--para <motor>`.
2. Responde con una tabla corta: requisito, estado (bien / falta / opcional), para qué sirve (montaje, preproducción, promo, 3D…).
3. Para cada cosa que falte, el arreglo concreto, por ejemplo:
   - `ffmpeg`, `whisper-cpp`: `brew install ffmpeg whisper-cpp`, más el modelo `ggml-medium.bin` en `~/.cache/whisper/` (o su ruta en `FILMCRAFT_WHISPER_MODEL`).
   - Paquetes Python: `python3 -m pip install -r ${CLAUDE_PLUGIN_ROOT}/requirements.txt`.
   - `swiftc`: `xcode-select --install`.
   - `filmcraft-cli`: instalar FilmCraft ≥ 0.8 y poner el CLI en el PATH, o exportar `FILMCRAFT_CLI=/ruta/al/filmcraft-cli`.
   - Fuentes del DS: instalarlas, o cambiar la fuente en el DS con la skill `design-system-video`.
4. No instales nada sin permiso explícito del usuario. Si sale con 2 por un argumento que no reconoce, revisa que el motor vaya tras `--para`; si es `--doctor` lo que no reconoce (versión antigua), ejecuta `herramientas.py` sin esa opción y di que el diagnóstico es parcial.
5. Termina con el siguiente paso: `/filmcraft-studio:video <qué quieres>` para un video nuevo, `/filmcraft-studio:promo <repo>` para una promo o `/filmcraft-studio:editar <carpeta>` para material grabado.
