---
description: "Aplica una nota de revisión sobre un video ya hecho («el gancho es largo», «quita el bloque X») y rehace solo lo afectado"
argument-hint: "<nota en texto libre>"
---

Nota del usuario: $ARGUMENTS

1. **Localiza la carpeta de trabajo `W` activa**: la de esta conversación si ya se trabajó en una; si no, la más reciente (por fecha de modificación) con `preproduccion/biblia.json` o `plan.json` bajo la carpeta actual: `<evento>/06 - FilmCraft/auto|asistido/<slug>/` en montajes y `<repo>/video/<slug>/` en videos y promos (`find . -maxdepth 5 \( -name biblia.json -o -name plan.json \)`). Si hay varias candidatas, pregunta cuál.
2. Traduce la nota a cambios concretos y dilos en una línea:
   - **Montaje con `plan.json`**: bloque, campo y valor. Recompila. En asistido: `apply_plan.py --live --deshacer <bloque>` y vuelve a aplicar ese bloque (y los siguientes si cambió la duración). En headless: aplica a un proyecto nuevo `…-vN.fcproj`.
   - **Promo por código** (sin `plan.json`): edita la línea de tiempo o la escena afectada (`timeline.py`, el script de la escena) y rehaz solo esa escena y el máster.
3. **Si hay biblia**, añade la entrada a `cambios` (nota, qué se cambió, fecha) y sube `iteracion`. Si la nota contradice un criterio de aceptación, dilo y pregunta antes de cambiar la biblia.
4. Verifica solo lo afectado (hoja del bloque o de la escena, LUFS si tocaste audio, el criterio de la biblia que toque) y enséñalo.
