---
name: brief-video
description: Completa el brief de intenciones de un video (objetivo, público, plataforma, duración, tono, obligatorios, evitar, CTA, design system, idioma) infiriendo lo que no se dé a partir del material y marcando origen y confianza de cada campo. Úsala con `/filmcraft-studio:brief`, al empezar cualquier montaje, o cuando pregunten "qué tiene que tener el reel", "cuánto debería durar", "qué no puede faltar".
---

# Brief de video

Cada campo lleva `valor`, `origen` (`dado`, `inferido`, `defecto`), `confianza` (0–1) y `por` (de dónde sale).

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/brief_infer.py --analisis W/analisis --out W/brief.json \
    [--dado '{"duracion_s": 55, "obligatorios": ["100 dólares", "SageMaker"], "ds": "sbg-brutalista-s5"}']
```

Necesita el análisis (`analyze_media.py`). Qué infiere:

| Campo | Cómo |
|---|---|
| `plataforma` | Aspecto del lienzo del DS (9:16 → Reels/TikTok/Shorts) |
| `duracion_s` | Centro del rango `estructura.duracion_s` del DS (defecto, confianza 0,5) |
| `tono` | Energía media del audio y `ritmo.energia` del DS |
| `obligatorios` | Cifras con unidad ("100 dólares"), servicios del `vocabulario` del DS y momentos de premio en la transcripción. `candidatos` guarda además nombres propios con su fuente y segundo |
| `ds` | Ranking por rutas y paleta del flyer (`--solo-ds` lo muestra) |
| `cta` | `marca.cta` del DS |
| `idioma` | Idioma de la transcripción |

Uso por modo:
- **Asistido:** pregunta SOLO los campos con confianza < 0,6, en una tanda (`AskUserQuestion`), y vuelve a correr con `--dado`.
- **Headless:** usa los valores tal cual; `report.py` los lista en "Preguntas pendientes".

Los obligatorios inferidos son candidatos: el director los revisa contra la transcripción (un número suelto no siempre es un mensaje).
