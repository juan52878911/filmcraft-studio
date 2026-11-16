---
description: "Enseña el catálogo de design systems con miniaturas y, con un flyer, los ordena por parecido"
argument-hint: "[--flyer F] [--ruta carpeta]"
disable-model-invocation: true
allowed-tools: Bash(python3:*), Bash(export:*), Bash(mktemp:*), Read
---

`S=${CLAUDE_PLUGIN_ROOT}/scripts`. Antes de cada llamada: `export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}`.

1. `python3 $S/ds_studio.py catalogo --hoja <carpeta temporal>/catalogo.png` (la carpeta temporal de la sesión o `mktemp -d`; nunca dentro del plugin). Enseña la hoja con Read y, si `SendUserFile` está disponible, envíala; si no, da la ruta absoluta. Lista también los borradores pendientes (`ds_studio.py borradores`).
2. Si hay flyer o ruta en `$ARGUMENTS`: `python3 $S/brief_infer.py --solo-ds --para camara $ARGUMENTS` (`--para promo` si es para una promo).
3. Responde con una tabla corta (id, nombre, gramática, puntuación si la hay) y recomienda uno. Con `--ruta`, si ninguno pasa de 0,5, propone `/filmcraft-studio:ds-crear`; **sin `--ruta` la puntuación es solo el parecido de color** (≥ 0,9 es el mismo estilo; < 0,7, propone crear uno).
