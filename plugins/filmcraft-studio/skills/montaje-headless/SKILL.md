---
name: montaje-headless
description: "Monta solo, sin ventana ni preguntas, un video de material grabado (videos, voz, fotos, flyer) con DS y brief, y entrega un proyecto FilmCraft nuevo verificado. Úsala con «reel o resumen de una charla o evento», «móntalo solo», «automático», «headless» o /filmcraft-studio:montar --modo headless."
---

# Montaje headless

Pipeline autónomo. Decide lo que no te den (brief y DS), lo marca en el informe y no pregunta. El oficio y las reglas duras están en la skill `editor-filmcraft` (léela si no la tienes cargada): este flujo las aplica, no las sustituye.

Formato del plan: `${CLAUDE_SKILL_DIR}/references/plan.md`.

**Orden en este modo:** el brief va primero y elige el DS (D1 → D2). En asistido es al revés: el usuario elige el estilo (G1) y después se completa el brief (G2).

## Reglas

- **Solo proyectos nuevos.** Salida en `W` = `<carpeta del evento>/06 - FilmCraft/auto/<slug>/` (regla de `${CLAUDE_PLUGIN_ROOT}/skills/preproduccion/SKILL.md`, «Carpeta de trabajo W»). Nunca abras ni escribas un `.fcproj` existente (la referencia manual es solo lectura).
- **Sin export de video** salvo que lo pidan (en texto o con `/filmcraft-studio:entregar`: sigue `${CLAUDE_PLUGIN_ROOT}/commands/entregar.md`). Para verificar: hojas headless y mezcla `.wav`.
- Si la app está abierta no pasa nada: headless trabaja sobre rutas nuevas con su propio motor (`$FC mcp`).
- No digas "verificado" sin hojas renderizadas y LUFS medidos.

## Pasos

Antes de cada llamada a un script (el estado del shell no persiste entre llamadas):

```bash
S=${CLAUDE_PLUGIN_ROOT}/scripts
export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}
W="<carpeta del evento>/06 - FilmCraft/auto/<slug>"
A="<carpeta del evento>/06 - FilmCraft/analisis"     # caché única por evento, compartida con asistido
FC=${FILMCRAFT_CLI:-filmcraft-cli}
```

0. **Preflight.** `python3 $S/herramientas.py --doctor --para camara [--ds <id>]` (sale 1 si falta algo obligatorio: `$FC`, `whisper-cli` y su modelo —obligatorios solo con `--para camara`—, `ffmpeg`, fuentes del DS); `$FC --version`. Si falta algo, dilo y para.
1. **Inventario.** Si el evento sigue la estructura `01 crudo`, `02 voz` (`_voz`), `03 fotos` (con sus subcarpetas), `04 gráfica` y flyer, úsala; si no, busca cada cosa y, si no está clara, dilo en el informe.
2. **Análisis** (con caché; lánzalo en segundo plano). Si `$A` no existe, mide antes la duración total con `ffprobe` y di el tiempo estimado (≈ 3 min por minuto de 4K la primera vez: una charla de 45 min son más de 2 h) antes de lanzarlo:
   ```bash
   python3 $S/analyze_media.py --out "$A" --videos "<02 voz>" --fotos "<03 fotos>" --grafica "<04>" --flyer "<flyer>" [--prompt "<vocabulario del DS>"]   # --prompt solo si el DS ya está dado
   ```
   Luego lanza el subagente **analista-material** (si no hay subagentes, hazlo tú en un paso aparte) con `$A/transcripcion.md` y `material.json`: devuelve los momentos con peso, cita y tiempos.
3. **D1 · Brief:** `python3 $S/brief_infer.py --analisis "$A" --out "$W/brief.json" [--dado '{…lo que dio el usuario o la biblia…}']`. Si hay biblia (`W/preproduccion/biblia.json`), sus respuestas van en `--dado` y mandan.
4. **D2 · DS:** el que eligió el brief (ranking con `brief_infer.py --solo-ds --para camara`: los `promo-*` no valen para material grabado). Sin `--ruta` la puntuación es solo el parecido de color (≥ 0,9 es el mismo estilo). Si ninguno encaja y hay flyer, créalo con `ds_from_image.py` (skill `design-system-video`). Valida con `ds_validate.py`.
5. **D3 · Plan:** lanza el subagente **director-montaje** (o hazlo tú si no hay subagentes) con brief, DS, análisis y momentos. Escribe `$W/plan.json` según `${CLAUDE_SKILL_DIR}/references/plan.md`: columna de audio primero, obligatorios cubiertos, barridos de cámara antes que mattes.
6. **Compilar:** `python3 $S/plan_compile.py "$W/plan.json" --analisis "$A" --brief "$W/brief.json"`. Lee `avisos` y `cobertura`; si falta un obligatorio o un pop-up tapa caras, corrige el plan y recompila.
7. **Aplicar** (fases A–E en un proyecto nuevo):
   `python3 $S/apply_plan.py "$W/compiled.json" --headless --out "$W/<Nombre>.fcproj"`
8. **Verificar** (máximo 3 pasadas de arreglo):
   `python3 $S/verify.py "$W/<Nombre>.fcproj" --compiled "$W/compiled.json" --analisis "$A" --out "$W/verificacion" [--ref <manual.fcproj>]`
   Si sale con **2**, la verificación está incompleta (`verificado: false` en `verificacion.json`): lee `fallos`, arregla la causa (estado.json, detector de caras, loudness…) y repítela; no digas «verificado» ni cuentes esa vuelta como pasada de arreglo.
   Mira las hojas (`hoja_cortes`, `hoja_popups`, `hoja_popups_sin_textos` con cajas verde/naranja/roja). Si hay que arreglar: cambia el plan, recompila y aplica a un nombre nuevo (`…-v2.fcproj`).
9. **Crítica:** lanza el subagente **critico** con el informe provisional y las hojas; guarda su respuesta en `$W/critica.md`.
10. **Informe:** `python3 $S/report.py "$W"` → `$W/informe.md`. Resume al usuario: qué se hizo, cifras, qué no se verificó y las preguntas de baja confianza.

## Tiempos de referencia (Mac M4)

Análisis de ~5 min de material 4K: ~15 min la primera vez (whisper medium + visión + barridos), segundos después. Compilar y aplicar: < 5 s. Verificar: ~1 min. Export de video: ~7 min por minuto (no lo hagas sin permiso).
