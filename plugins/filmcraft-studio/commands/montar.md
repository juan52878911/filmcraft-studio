---
description: Monta un video en FilmCraft con design system y brief, en modo headless (autónomo) o asistido (puertas en la app)
argument-hint: <carpeta del evento> [--modo headless|asistido] [--ds id] [--ref proyecto.fcproj] [indicaciones]
---

Monta el video. Argumentos: $ARGUMENTS

- `--modo headless` (por defecto si no se dice y no hay app abierta): sigue la skill `montaje-headless` de punta a punta, sin preguntas, en un proyecto nuevo bajo `06 - FilmCraft/auto/<slug>/`. Con `--ref`, compara con ese montaje (solo lectura).
- `--modo asistido`: sigue la skill `montaje-asistido`. Para en cada puerta (G1 brief, G2 DS, G3 estrategia, G4 cada bloque) y espera la respuesta del usuario.

Lo que el usuario diga en texto libre entra al brief como `dado`. No exportes video.
