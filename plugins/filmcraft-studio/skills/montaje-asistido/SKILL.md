---
name: montaje-asistido
description: Monta un video en la app FilmCraft abierta, paso a paso, con puertas de confirmación (design system, brief, estrategia y cada bloque) para que el usuario vea y apruebe cada cambio en vivo. Úsala con `/filmcraft-studio:editar` o `/filmcraft-studio:montar --modo asistido`, o cuando pidan "edita este video conmigo", "vamos juntos", "paso a paso", "enséñame antes de aplicar", "en la app" o quieran revisar el montaje mientras se hace.
---

# Montaje asistido (puertas G0–G7)

Si se entra por `/filmcraft-studio:editar`, G1 y G2 ya se hicieron en la conversación de entrada: empieza en G3.

Mismo motor que el headless (`plan_compile.py` + `apply_plan.py`), pero aplicado **en vivo por el canal de control** (socket 9876) y deteniéndose en cada puerta. **En cada puerta, para y espera la respuesta del usuario.** No avances con silencio ni con suposiciones; usa `AskUserQuestion` con opciones concretas cuando ayude.

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (`S`). Carpeta de trabajo `W` = `<evento>/06 - FilmCraft/asistido/<slug>/`. Formato del plan: `${CLAUDE_PLUGIN_ROOT}/skills/montaje-headless/references/plan.md`. Oficio y reglas duras: skill `editor-filmcraft`.

## Reglas en vivo

- Todo cambio va por el socket (`apply_plan.py --live` o el MCP `filmcraft`). **Nunca** escribas en headless el `.fcproj` que la app tiene abierto.
- Para mirar, guarda en la app (`file.save`, lo hace `apply_plan.py`) y renderiza en headless desde el `.fcproj` guardado (solo lectura): `render_sheet.py`.
- Cada bloque queda registrado en `W/estado.json`: si el usuario lo rechaza, `--deshacer <bloque>` lo borra entero.

## Puertas

**G0 · Conectar y respaldar.**
- ¿Escucha la app? `python3 -c "import sys; sys.path.insert(0,'$S'); from fclib import app_listening; print(app_listening())"`. Si no: `open -a FilmCraft --args --control 9876` y espera unos segundos.
- Si hay un proyecto abierto con cambios, `file.save` y copia su `.fcproj` a `…/_respaldos/<nombre>-<fecha>.fcproj`.
- Análisis (`analyze_media.py`, con caché) como en headless. Mientras corre, sigue con G1.

**G1 · Estilo (design system).** Catálogo con miniaturas (`ds_studio.py catalogo --hoja …`) y `AskUserQuestion` con los DS más "Crear uno nuevo". Si crea: descripción, flyer o logo → `ds_studio.py crear` → vista previa → `modificar` hasta que lo apruebe → `aprobar` (pasa al catálogo). Detalle en `/filmcraft-studio:editar` y la skill `design-system-video`. Espera OK.

**G2 · Brief.** `brief_infer.py --dado '{"ds": "<aprobado>", …}'` y enseña una tabla corta (campo, valor, origen, confianza). Propón los valores inferidos y pregunta en una tanda lo que cambie o tenga confianza < 0,6. Guarda las respuestas con `--dado`. Espera OK.

**G3 · Estrategia.** Lanza **analista-material** y **director-montaje** (como en headless) para `W/plan.json`; compila. Presenta la estrategia en 4–8 frases y la tabla de bloques (id, tipo, segundos, resumen, transición de entrada, textos). Espera OK, reordenaciones o bloques a quitar; recompila tras cada cambio.

**G4 · Bloque a bloque en la app.**
1. Primera vez: proyecto nuevo con las pistas del DS y el fondo:
   ```bash
   python3 $S/apply_plan.py $W/compiled.json --live --nuevo "$W/<Nombre>.fcproj"
   python3 $S/apply_plan.py $W/compiled.json --live --bloques '*' --fases A
   ```
2. Para cada bloque, en orden: `python3 $S/apply_plan.py $W/compiled.json --live --bloques <id> --fases A,B,C,D`
3. Hoja del bloque (inicio, cada corte, pico de cada pop-up y final) con `render_sheet.py "$W/<Nombre>.fcproj" $W/hojas/<id>.jpg <segundos…>`; enséñala y di qué mirar. Pide al usuario que lo reproduzca en la app.
4. Espera **OK** o **notas**. Con notas: edita ese bloque en `plan.json`, recompila, `--deshacer <id>` y vuelve a aplicar. Si el cambio desplaza los bloques siguientes (duración distinta), avisa: hay que deshacer y reaplicar los posteriores ya aplicados.

**G5 · Pasadas globales.** `--bloques '*' --fases B,E` (música con ducking y grade). Subtítulos y loudness: enseña la mezcla `.wav` medida (`verify.py` da LUFS y pico). Espera OK.

**G6 · Verificación y crítico.** `verify.py` + subagente **critico** + `report.py`. Presenta veredicto y los 5 arreglos; aplica los que el usuario elija.

**G7 · Export.** Solo si lo pide, con `/filmcraft-studio:entregar`.

## Si algo falla en vivo

- `RuntimeError … is not free here`: el bloque ya estaba aplicado; `--deshacer <id>` y repite.
- La app no responde: no la mates. Pide al usuario que la mire; el estado del plugin está en `estado.json`.
