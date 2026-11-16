---
description: "Monta material grabado en FilmCraft con design system y brief, headless (autónomo) o asistido (en la app)"
argument-hint: "<carpeta del evento> [--modo headless|asistido] [--ds id] [--ref proyecto.fcproj] [indicaciones]"
disable-model-invocation: true
---

Monta el video. Argumentos: $ARGUMENTS

- Sin `--modo`: headless si la app FilmCraft no está abierta; **si está abierta, pregunta** qué modo quiere.
- `--modo headless`: sigue la skill `montaje-headless` de punta a punta, sin preguntas, en un proyecto nuevo bajo `06 - FilmCraft/auto/<slug>/`. Con `--ref`, compara con ese montaje (solo lectura).
- `--modo asistido`: sigue la skill `montaje-asistido`. Para en cada puerta (G1 estilo (DS), G2 brief, G3 estrategia, G4 cada bloque) y espera la respuesta del usuario.

El análisis se comparte entre modos en `<evento>/06 - FilmCraft/analisis/`. Lo que el usuario diga en texto libre entra al brief como `dado`. No exportes video.
