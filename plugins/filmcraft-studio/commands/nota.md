---
description: Aplica una nota de revisión ("el gancho es largo", "quita el bloque X", "el rótulo tapa a Natalia") al plan y rehace solo lo afectado
argument-hint: <nota en texto libre>
---

Nota del usuario: $ARGUMENTS

1. Localiza la carpeta de trabajo activa (último `plan.json` en `06 - FilmCraft/auto|asistido/`). Traduce la nota a cambios concretos en `plan.json` (bloque, campo, valor) y dilos en una línea.
2. Recompila. En asistido: `apply_plan.py --live --deshacer <bloque>` y vuelve a aplicar ese bloque (y los siguientes si cambió la duración). En headless: aplica a un proyecto nuevo `…-vN.fcproj`.
3. Verifica solo lo afectado (hoja del bloque, LUFS si tocaste audio) y enséñalo.
