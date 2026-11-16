---
description: "Hace un video nuevo de punta a punta: preproducción con biblia, producción por motores y verificación"
argument-hint: "<qué video quieres> [--refs archivos|carpetas|URLs] [--material carpeta] [--formato 16:9|9:16|1:1] [--modo headless|asistido] [--sin-preguntas] [--expres]"
disable-model-invocation: true
---

Sigue la skill `director-video`. Entrada: $ARGUMENTS

`S=${CLAUDE_PLUGIN_ROOT}/scripts`; antes de cada script, `export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}`.

El flujo (preproducción con biblia → producción por escena → ensamblado en FilmCraft → verificación contra la biblia → entrega) y sus reglas están en la skill: no los repitas de memoria. Atajos:
- Si solo hay que montar material grabado (reel o resumen de una charla o un evento), pregunta «¿lo monto solo o contigo?» y pasa a `montaje-headless` o `montaje-asistido`.
- Si el encargo es animar una sola imagen, skill `imagen-a-video`.
- `--expres` o «exprés»: modo exprés de `preproduccion`; `--sin-preguntas`: todo inferido y marcado.
- Solo se exporta si lo piden.
