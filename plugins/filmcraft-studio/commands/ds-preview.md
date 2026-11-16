---
description: "Vista previa de un design system de video (maquetas PIL y render real de FilmCraft)"
argument-hint: "<ds> [--frame foto.jpg]"
disable-model-invocation: true
allowed-tools: Bash(python3:*), Bash(export:*), Read
---

Genera la vista previa del DS: `export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}; python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ds_preview.py $ARGUMENTS --fc`.

La lámina sale en `<datos>/previews/<id>/preview.png` (`<datos>` = `$CLAUDE_PLUGIN_DATA` o `~/.cache/filmcraft-studio`; la ruta exacta es la última línea que imprime el script): no pisa la `preview.png` de la carpeta del DS. Enséñala con Read y, si la herramienta `SendUserFile` está disponible, envíala; si no, da la ruta absoluta. Comenta en 2–3 líneas: contraste de los textos sobre los acentos, si el render de FilmCraft coincide con la maqueta y cualquier aviso de `ds_validate.py`. Para un DS `promo-*`, la vista previa fiel son los fotogramas del motor de código (`promo_preview.py`, skill `promo-codigo`); si `ds_preview.py` falla con él, dilo y usa esa vía.
