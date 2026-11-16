---
name: montaje-asistido
description: "Monta material grabado en la app FilmCraft abierta, paso a paso, con puertas de aprobación (estilo, brief, estrategia, cada bloque). Úsala con «reel de una charla o evento conmigo», «edítalo conmigo», «paso a paso», /filmcraft-studio:editar o /filmcraft-studio:montar --modo asistido."
---

# Montaje asistido (puertas G0–G7)

Si se entra por `/filmcraft-studio:editar` (o por su flujo conversado, `${CLAUDE_PLUGIN_ROOT}/commands/editar.md`), G1 y G2 ya se hicieron: haz G0 (preflight, conexión y respaldo; el análisis ya está) y sigue en G3.

Mismo motor que el headless (`plan_compile.py` + `apply_plan.py`), pero aplicado **en vivo por el canal de control** (socket 9876) y deteniéndose en cada puerta. **En cada puerta, para y espera la respuesta del usuario.** No avances con silencio ni con suposiciones; pregunta con opciones concretas (`AskUserQuestion` si está disponible; si no, opciones numeradas en texto).

**Orden en este modo:** el usuario elige el estilo (G1) y después se completa el brief con ese DS (G2). En headless es al revés: el brief elige el DS.

Antes de cada llamada a un script (el estado del shell no persiste entre llamadas):

```bash
S=${CLAUDE_PLUGIN_ROOT}/scripts
export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}
W="<carpeta del evento>/06 - FilmCraft/asistido/<slug>"   # regla de W en skills/preproduccion/SKILL.md
A="<carpeta del evento>/06 - FilmCraft/analisis"          # caché única, compartida con headless
```

La regla de `W` está en `${CLAUDE_PLUGIN_ROOT}/skills/preproduccion/SKILL.md` («Carpeta de trabajo W»). Formato del plan: `${CLAUDE_PLUGIN_ROOT}/skills/montaje-headless/references/plan.md`. Oficio y reglas duras: skill `editor-filmcraft`.

## Reglas en vivo

- Todo cambio va por el socket (`apply_plan.py --live` o el MCP `filmcraft`). **Nunca** escribas en headless el `.fcproj` que la app tiene abierto.
- Para mirar, guarda en la app (`file.save`, lo hace `apply_plan.py`) y renderiza en headless desde el `.fcproj` guardado (solo lectura): `render_sheet.py`.
- Cada bloque queda registrado en `W/estado.json`: si el usuario lo rechaza, `--deshacer <bloque>` lo borra entero.

## Puertas

**G0 · Diagnóstico, conexión y respaldo.**
- Preflight: `python3 $S/herramientas.py --doctor --para camara [--ds <id>]` (o `/filmcraft-studio:doctor --para camara`; con `--para camara` whisper-cli y su modelo son obligatorios). Si sale con 1, di qué falta y para.
- ¿Escucha la app? `python3 -c "import sys; sys.path.insert(0,'$S'); from fclib import app_listening; print(app_listening())"`. Si no: `open -a FilmCraft --args --control 9876` y espera unos segundos.
- Si hay un proyecto abierto con cambios, `file.save` y copia su `.fcproj` a `…/_respaldos/<nombre>-<fecha>.fcproj`.
- Análisis (`analyze_media.py --out "$A" …`, con caché) como en headless, con su aviso de tiempo si el material es largo. Mientras corre, sigue con G1.

**G1 · Estilo (design system).** Catálogo con miniaturas (`ds_studio.py catalogo --hoja …`; para recomendar, `brief_infer.py --solo-ds --para camara --flyer …`) y elección entre los DS más «Crear uno nuevo»; el ciclo crear → vista previa → modificar → aprobar es el de la skill `design-system-video`. Espera OK.

**G2 · Brief.** `brief_infer.py --analisis "$A" --out "$W/brief.json" --dado '{"ds": "<aprobado>", …}'` y enseña una tabla corta (campo, valor, origen, confianza). Propón los valores inferidos y pregunta en una tanda lo que cambie o tenga confianza < 0,6. Guarda las respuestas con `--dado`. Espera OK.

**G3 · Estrategia.** Lanza **analista-material** y **director-montaje** (como en headless; si no hay subagentes, hazlo tú) para `W/plan.json`; compila. Presenta la estrategia en 4–8 frases y la tabla de bloques (id, tipo, segundos, resumen, transición de entrada, textos). Espera OK, reordenaciones o bloques a quitar; recompila tras cada cambio.

**G4 · Bloque a bloque en la app.**
1. Primera vez: proyecto nuevo con las pistas del DS y el fondo:
   ```bash
   python3 $S/apply_plan.py "$W/compiled.json" --live --nuevo "$W/<Nombre>.fcproj"
   python3 $S/apply_plan.py "$W/compiled.json" --live --bloques global --fases A    # solo el fondo; los planos van bloque a bloque
   ```
2. Para cada bloque, en orden: `python3 $S/apply_plan.py "$W/compiled.json" --live --bloques <id> --fases A,B,C,D`
3. Hoja del bloque (inicio, cada corte, pico de cada pop-up y final) con `render_sheet.py "$W/<Nombre>.fcproj" "$W/hojas/<id>.jpg" <segundos…>`; enséñala y di qué mirar. Pide al usuario que lo reproduzca en la app.
4. Espera **OK** o **notas**. Con notas: edita ese bloque en `plan.json`, recompila, `--deshacer <id>` y vuelve a aplicar. Si el cambio desplaza los bloques siguientes (duración distinta), avisa: hay que deshacer y reaplicar los posteriores ya aplicados.

**G5 · Pasadas globales.** `--bloques '*' --fases B,E` (música con ducking y grade). Subtítulos y loudness: enseña la mezcla `.wav` medida (`verify.py` da LUFS y pico). Espera OK.

**G6 · Verificación y crítico.** `verify.py … --analisis "$A"` + subagente **critico** + `report.py "$W"`. Presenta veredicto y los 5 arreglos; aplica los que el usuario elija.

**G7 · Export.** Solo si lo pide (en texto o con `/filmcraft-studio:entregar`): sigue `${CLAUDE_PLUGIN_ROOT}/commands/entregar.md`. Las notas sueltas tras G6, con `${CLAUDE_PLUGIN_ROOT}/commands/nota.md`.

## Si algo falla en vivo

- `RuntimeError … is not free here`: el bloque ya estaba aplicado; `--deshacer <id>` y repite.
- La app no responde: no la mates. Pide al usuario que la mire; el estado del plugin está en `estado.json`.
