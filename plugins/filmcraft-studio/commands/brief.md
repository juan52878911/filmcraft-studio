---
description: "Completa el brief de intenciones de un montaje con material grabado (origen y confianza por campo)"
argument-hint: "<carpeta de trabajo> [campos dados en texto libre]"
disable-model-invocation: true
---

Sigue la skill `brief-video`. Argumentos: $ARGUMENTS

1. El análisis vive en `<evento>/06 - FilmCraft/analisis/`. Si no existe, sigue antes `${CLAUDE_PLUGIN_ROOT}/commands/analizar.md`.
2. Si hay una biblia aprobada (`W/preproduccion/biblia.json`), sus respuestas mandan: pásalas a `--dado`. Añade lo que el usuario haya dicho (duración, obligatorios, DS, CTA…) y corre `brief_infer.py`.
3. Enseña una tabla (campo, valor, origen, confianza) y pregunta solo lo que tenga confianza < 0,6.
