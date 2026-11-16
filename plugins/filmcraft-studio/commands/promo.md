---
description: "Crea un video promocional de un repositorio o de su última versión, renderizado por código con un DS de promo"
argument-hint: "<repo o ruta> [--estilo promo-*] [--refs referencias] [--formato 16:9|9:16] [--sin-preguntas] [--expres]"
disable-model-invocation: true
---

Sigue la skill `promo-codigo`. Entrada: $ARGUMENTS

`S=${CLAUDE_PLUGIN_ROOT}/scripts`; antes de cada script, `export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}`.

El orden y las reglas están en la skill (no los repitas de memoria):
1. Preflight `herramientas.py --doctor --para promo` (FilmCraft no es obligatorio; VHS sí se comprueba).
2. **Preproducción** (skill `preproduccion`, exprés si se pide o se elige en la primera pregunta), salvo que ya haya una biblia aprobada: qué trae la versión con fuente, rondas, concepto, DS `promo-*` y biblia.
3. Para sus fotogramas fijos, `timeline.py` y una `escena.py` mínima (gancho y firma) con el esqueleto de `${CLAUDE_PLUGIN_ROOT}/skills/promo-codigo/references/motor.md`; la grabación VHS de la terminal real puede ir después.
4. Grabación VHS medida, escenas completas, audio, verificación (`cine medir-video` por formato, hoja, `cine puntuar` → `critico-juicio` → `cine nota`, criterios de la biblia con `cine criterios`; paso 7 de la skill) y entrega del MP4 (si `SendUserFile` está disponible, envíalo; si no, la ruta absoluta). Limpia lo que la demo haya creado.
