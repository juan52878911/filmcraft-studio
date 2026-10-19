---
description: Punto de entrada conversacional para editar un video en FilmCraft: estilo → intenciones → edición (asistida o automática)
argument-hint: <carpeta del material> [lo que quieres ver]
---

Editar el video del material en: $ARGUMENTS

Orden obligatorio: **estilo → intenciones → edición**. En cada paso espera la respuesta del usuario antes de seguir (salvo que diga "decide tú": entonces sigue la skill `montaje-headless` sin preguntas).

`S=${CLAUDE_PLUGIN_ROOT}/scripts`. Carpeta de trabajo `W` = `<evento>/06 - FilmCraft/<auto|asistido>/<slug>/`.

## 0. Arranque (sin preguntar)
- Inventaria la carpeta (crudo, voz `_voz`, fotos, gráfica, flyer) y lanza el análisis en segundo plano: `python3 $S/analyze_media.py --out $W/analisis …` (skill `montaje-headless`, paso 2). Mientras corre, conversa.

## 1. ¿Qué te gustaría ver?
Una pregunta abierta y corta: qué video imagina (para quién, qué tiene que contar, qué no puede faltar). Si ya lo dijo en los argumentos, resume lo entendido en una línea y pasa al estilo.

## 2. Estilo (design system)
- Catálogo: `python3 $S/ds_studio.py catalogo --hoja $W/catalogo.png`. Enseña la hoja (Read + SendUserFile) y pregunta con `AskUserQuestion`: una opción por DS (nombre y descripción en una línea; recomienda el que mejor encaje según `brief_infer.py --solo-ds --flyer … --ruta …`) más **"Crear uno nuevo"**.
- Crear uno nuevo (o catálogo vacío): pide que describa cómo lo quiere (colores, tipografía, energía, referencias) y acepta un flyer, logo o imagen. Traduce la descripción a un `spec` (ver `ds_studio.py`) y:
  `python3 $S/ds_studio.py crear --id <slug> --spec '<json>' [--flyer F] --frame <foto real del material>`
  Enseña `preview.png` (Read + SendUserFile) y la paleta. **Ciclo:** si pide cambios, `ds_studio.py modificar <id> --spec '<solo lo que cambia>'` y vuelve a enseñar. Repite hasta que diga que lo aprueba.
- Al aprobar: `python3 $S/ds_studio.py aprobar <id>` (valida y lo pasa al catálogo). Si eligió uno del catálogo, ya está aprobado.
- Las fuentes deben estar instaladas en el Mac (ds_validate lo comprueba); si la que pide no está, propone la más parecida instalada.

## 3. Intenciones (brief)
Cuando el análisis termine: `python3 $S/brief_infer.py --analisis $W/analisis --out $W/brief.json --dado '{"ds": "<id aprobado>", …lo que dijo en el paso 1…}'`. Propón los valores inferidos en una tabla corta (objetivo, público, plataforma, duración, tono, obligatorios, CTA) y pide confirmación o cambios en una sola pregunta. Guarda lo confirmado con `--dado`.

## 4. Edición
Pregunta el modo con `AskUserQuestion`:
- **Asistido** (recomendado si la app está abierta y el usuario está delante): skill `montaje-asistido` desde G3; G1 (estilo) y G2 (brief) ya están hechos.
- **Automático**: skill `montaje-headless` desde el paso 5 con el DS y el brief aprobados.

No exportes video salvo que lo pida (`/filmcraft-studio:entregar`).
