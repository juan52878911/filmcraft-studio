---
description: Completa el brief de intenciones de un montaje (con origen y confianza por campo)
argument-hint: <carpeta de trabajo> [campos dados en texto libre]
---

Sigue la skill `brief-video`. Argumentos: $ARGUMENTS

1. Si no hay `analisis/` en la carpeta de trabajo, ejecuta antes `/filmcraft-studio:analizar`.
2. Pasa a `--dado` lo que el usuario haya dicho (duración, obligatorios, DS, CTA…) y corre `brief_infer.py`.
3. Enseña una tabla (campo, valor, origen, confianza) y pregunta solo lo que tenga confianza < 0,6.
