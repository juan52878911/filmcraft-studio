---
description: Hace cualquier video de punta a punta (promo, demo, tutorial, explainer, reel, entrevista, short, pitch…) con brief, guion por escenas, design system y ensamblado en FilmCraft
argument-hint: <qué video quieres> [--material carpeta] [--formato 16:9|9:16|1:1] [--modo headless|asistido]
---

Sigue la skill `director-video`. Entrada: $ARGUMENTS

1. Brief y tipo de video (`brief-video`, `director-video/references/tipos.md`). Pregunta una sola vez lo que cambie el video y no se pueda inferir.
2. Hechos con fuente y `guion.json`; enséñalo como tabla (en asistido, espera el visto bueno).
3. Design system: del catálogo o nuevo, con fotogramas fijos para elegir.
4. Produce cada escena con su motor (`motores.md`), ensambla en FilmCraft (`analyze_media` → `plan.json` → `plan_compile` → `apply_plan`) y verifica con `reglas.md`, `verify.py` y el agente `critico`.
5. Entrega el proyecto y el informe; exporta solo si lo piden.
