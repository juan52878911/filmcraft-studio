---
description: "Edita material grabado conversando: estilo, intenciones y edición (asistida o automática) en FilmCraft"
argument-hint: "<carpeta del material> [lo que quieres ver]"
disable-model-invocation: true
---

Editar el video del material en: $ARGUMENTS

Orden obligatorio: **estilo → intenciones → edición**. En cada paso espera la respuesta del usuario antes de seguir (salvo que diga «decide tú»: entonces sigue la skill `montaje-headless` sin preguntas).

`S=${CLAUDE_PLUGIN_ROOT}/scripts`; antes de cada script, `export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}`. Análisis (caché única del evento): `A=<evento>/06 - FilmCraft/analisis/`. Carpeta de trabajo `W=<evento>/06 - FilmCraft/<auto|asistido>/<slug>/`. Si el material no sigue esa estructura de carpetas, pregunta dónde está cada cosa y dónde escribir.

Para preguntar usa `AskUserQuestion` si está disponible; si no, pregunta en texto con opciones numeradas y espera. Para enseñar una imagen: Read y, si `SendUserFile` está disponible, envíala; si no, da la ruta absoluta.

## 0. Arranque (sin preguntar)
- Preflight: `python3 $S/herramientas.py --doctor --para camara` (whisper-cli y su modelo son obligatorios para analizar el material). Si sale con 1, di qué falta y cómo arreglarlo antes de seguir.
- Inventaria la carpeta (crudo, voz `_voz`, fotos, gráfica, flyer). Si `$A` no existe, mide la duración total con `ffprobe`, di el tiempo estimado (≈ 3 min por minuto de 4K) y lanza el análisis en segundo plano: `python3 $S/analyze_media.py --out "$A" …` (skill `montaje-headless`, paso 2). Mientras corre, conversa.
- **Al terminar el análisis, lanza el subagente `analista-material`** sobre `$A` (y el brief cuando exista): sus momentos los necesita el plan, tanto en asistido como en automático.

## 1. ¿Qué te gustaría ver? y modo
Una pregunta abierta y corta: qué video imagina (para quién, qué tiene que contar, qué no puede faltar). Si ya lo dijo en los argumentos, resume lo entendido en una línea. En la misma tanda, el modo de edición (fija `W`):
- **Asistido** (recomendado si la app está abierta y el usuario está delante): `W=…/asistido/<slug>/`.
- **Automático**: `W=…/auto/<slug>/`.

## 2. Estilo (design system)
Sigue el ciclo de la skill `design-system-video` (catálogo con hoja → elegir uno o «Crear uno nuevo» → vista previa → modificar → aprobar). Recomienda el que mejor encaje según `${CLAUDE_PLUGIN_ROOT}/bin/cine elegir-ds --para camara --flyer … --ruta …` (sin `--ruta` la puntuación es solo el parecido de color: ≥ 0,9 es el mismo estilo). No avances hasta que el usuario elija uno del catálogo o apruebe el nuevo.

## 3. Intenciones (brief)
Cuando el análisis termine: `python3 $S/brief_infer.py --analisis "$A" --out "$W/brief.json" --dado '{"ds": "<id aprobado>", …lo que dijo en el paso 1…}'`. Propón los valores inferidos en una tabla corta (objetivo, público, plataforma, duración, tono, obligatorios, CTA) y pide confirmación o cambios en una sola pregunta. Guarda lo confirmado con `--dado`.

## 4. Edición
En el modo elegido en el paso 1:
- **Asistido**: skill `montaje-asistido`: haz G0 (conexión con la app y respaldo; el preflight y el análisis ya están) y sigue en G3; G1 (estilo) y G2 (brief) ya están hechos.
- **Automático**: skill `montaje-headless` desde el paso 5 (D3 · Plan con `director-montaje`), con el DS, el brief y los momentos del analista ya hechos.

No exportes video salvo que lo pida (en texto o con `/filmcraft-studio:entregar`: sigue `${CLAUDE_PLUGIN_ROOT}/commands/entregar.md`). Las notas, con `${CLAUDE_PLUGIN_ROOT}/commands/nota.md`.
