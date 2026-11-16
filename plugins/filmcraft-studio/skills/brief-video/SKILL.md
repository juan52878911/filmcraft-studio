---
name: brief-video
description: "Completa el brief de un montaje con material grabado (objetivo, público, plataforma, duración, tono, obligatorios, CTA), infiriendo del análisis y marcando origen y confianza. Paso interno de montaje-*; úsala con /filmcraft-studio:brief o «qué no puede faltar en el video»."
---

# Brief de video

Cada campo lleva `valor`, `origen` (`dado`, `inferido`, `defecto`), `confianza` (0–1) y `por` (de dónde sale).

Antes de cada llamada a un script (el estado del shell no persiste entre llamadas):

```bash
S=${CLAUDE_PLUGIN_ROOT}/scripts
export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}
A="<carpeta del evento>/06 - FilmCraft/analisis"     # caché única por evento
python3 $S/brief_infer.py --analisis "$A" --out "$W/brief.json" \
    [--dado '{"duracion_s": 55, "obligatorios": ["100 dólares", "SageMaker"], "ds": "sbg-brutalista-s5"}']
# sin material grabado (promo, explainer): el mismo script sin --analisis
python3 $S/brief_infer.py --dado '<respuestas de la biblia>' --out "$W/brief.json"
```

Con material grabado usa el análisis (`analyze_media.py`; si no existe, sigue `${CLAUDE_PLUGIN_ROOT}/commands/analizar.md`). Sin él, lo que dependería del material (tono, obligatorios, idioma) sale con confianza baja si no viene en `--dado`. `W` es la carpeta de trabajo de `${CLAUDE_PLUGIN_ROOT}/skills/preproduccion/SKILL.md`.

**Con biblia** (`W/preproduccion/biblia.json`): sus `respuestas` entran en `--dado` y mandan sobre lo inferido.

Qué infiere:

| Campo | Cómo |
|---|---|
| `plataforma` | Aspecto del lienzo del DS (9:16 → Reels/TikTok/Shorts) |
| `duracion_s` | Centro del rango `estructura.duracion_s` del DS (defecto, confianza 0,5) |
| `tono` | Energía media del audio y `ritmo.energia` del DS |
| `obligatorios` | Cifras con unidad ("100 dólares"), servicios del `vocabulario` del DS y momentos de premio en la transcripción. `candidatos` guarda además nombres propios con su fuente y segundo |
| `ds` | Ranking por rutas y paleta del flyer (`${CLAUDE_PLUGIN_ROOT}/bin/cine elegir-ds --para camara --flyer F --ruta R` lo muestra; color por ΔE en OKLab; sin `--ruta` es solo el parecido de color: ≥ 0,9 es el mismo estilo) |
| `cta` | `marca.cta` del DS |
| `idioma` | Idioma de la transcripción |

Uso por modo:
- **Asistido:** pregunta SOLO los campos con confianza < 0,6, en una tanda (`AskUserQuestion` si está disponible; si no, opciones numeradas en texto), y vuelve a correr con `--dado`.
- **Headless:** usa los valores tal cual; `report.py` los lista en "Preguntas pendientes".

Los obligatorios inferidos son candidatos: el director los revisa contra la transcripción (un número suelto no siempre es un mensaje).
