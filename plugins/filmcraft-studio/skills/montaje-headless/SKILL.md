---
name: montaje-headless
description: Monta un video de evento de punta a punta en FilmCraft sin ventana (headless) a partir de material crudo, un design system de video y un brief, y entrega un proyecto NUEVO verificado con informe. Úsala cuando se pida "monta el reel solo", "hazlo automático", "headless", "sin abrir la app" o `/filmcraft-studio:montar --modo headless`, o cuando haya carpetas de material (videos, voz procesada, fotos, flyer) y se quiera un primer montaje completo sin preguntas.
---

# Montaje headless

Pipeline autónomo. Decide lo que no te den (brief y DS), lo marca en el informe y no pregunta. El oficio y las reglas duras están en la skill `editor-filmcraft` (léela si no la tienes cargada): este flujo las aplica, no las sustituye.

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/`. Formato del plan: `${CLAUDE_SKILL_DIR}/references/plan.md`.

## Reglas

- **Solo proyectos nuevos.** Salida en `<carpeta del evento>/06 - FilmCraft/auto/<slug>/`. Nunca abras ni escribas un `.fcproj` existente (la referencia manual es solo lectura).
- **Sin export de video** salvo que lo pidan (`/filmcraft-studio:entregar`). Para verificar: hojas headless y mezcla `.wav`.
- Si la app está abierta no pasa nada: headless trabaja sobre rutas nuevas con su propio motor (`filmcraft-cli mcp`).
- No digas "verificado" sin hojas renderizadas y LUFS medidos.

## Pasos

Usa `S=${CLAUDE_PLUGIN_ROOT}/scripts` y `W=<carpeta de trabajo>`.

0. **Preflight.** `~/.local/bin/filmcraft-cli --version`, `whisper-cli`, `ffmpeg`, fuentes del DS (`ds_validate.py`). Si falta algo, dilo y para.
1. **Inventario.** Localiza: 01 crudo, 02 voz `_voz`, 03 fotos (y subcarpetas como `Geekcodey/`), 04 gráfica, flyer.
2. **Análisis** (con caché, minutos la primera vez; lánzalo en segundo plano):
   ```bash
   python3 $S/analyze_media.py --out $W/analisis --videos "<02 voz>" --fotos "<03 fotos>" --grafica "<04>" --flyer "<flyer>" --prompt "<vocabulario del DS>"
   ```
   Luego lanza el subagente **analista-material** con `$W/analisis/transcripcion.md` y `material.json`: devuelve los momentos con peso, cita y tiempos.
3. **D1 · Brief:** `python3 $S/brief_infer.py --analisis $W/analisis --out $W/brief.json [--dado '{…lo que dio el usuario…}']`.
4. **D2 · DS:** el que eligió el brief. Si ninguno encaja (puntuación < 0,5) y hay flyer, créalo con `ds_from_image.py` (skill `design-system-video`). Valida con `ds_validate.py`.
5. **D3 · Plan:** lanza el subagente **director-montaje** con brief, DS, análisis y momentos. Escribe `$W/plan.json` según `references/plan.md`: columna de audio primero, obligatorios cubiertos, barridos de cámara antes que mattes.
6. **Compilar:** `python3 $S/plan_compile.py $W/plan.json --analisis $W/analisis --brief $W/brief.json`. Lee `avisos` y `cobertura`; si falta un obligatorio o un pop-up tapa caras, corrige el plan y recompila.
7. **Aplicar** (fases A–E en un proyecto nuevo):
   `python3 $S/apply_plan.py $W/compiled.json --headless --out "$W/<Nombre>.fcproj"`
8. **Verificar** (máximo 3 pasadas de arreglo):
   `python3 $S/verify.py "$W/<Nombre>.fcproj" --compiled $W/compiled.json --analisis $W/analisis --out $W/verificacion [--ref <manual.fcproj>]`
   Mira las hojas (`hoja_cortes`, `hoja_popups`, `hoja_popups_sin_textos` con cajas verde/naranja/roja). Si hay que arreglar: cambia el plan, recompila y aplica a un nombre nuevo (`…-v2.fcproj`).
9. **Crítica:** lanza el subagente **critico** con el informe provisional y las hojas; guarda su respuesta en `$W/critica.md`.
10. **Informe:** `python3 $S/report.py $W` → `$W/informe.md`. Resume al usuario: qué se hizo, cifras, qué no se verificó y las preguntas de baja confianza.

## Tiempos de referencia (Mac de Juan)

Análisis de ~5 min de material 4K: ~15 min la primera vez (whisper medium + visión + barridos), segundos después. Compilar y aplicar: < 5 s. Verificar: ~1 min. Export de video: ~7 min por minuto (no lo hagas sin permiso).
