---
description: Enseña el catálogo de design systems con miniaturas y, con un flyer, los ordena por parecido
argument-hint: [--flyer F] [--ruta carpeta]
---

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ds_studio.py catalogo --hoja <scratchpad>/catalogo.png` y enseña la hoja (Read + SendUserFile). Lista también los borradores pendientes (`ds_studio.py borradores`).
2. Si hay flyer o ruta en `$ARGUMENTS`: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/brief_infer.py --solo-ds $ARGUMENTS`.
3. Responde con una tabla corta (id, nombre, gramática, puntuación si la hay) y recomienda uno; si ninguno pasa de 0,5, propone `/filmcraft-studio:ds-crear`.
