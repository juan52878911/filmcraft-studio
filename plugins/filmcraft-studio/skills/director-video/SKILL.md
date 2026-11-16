---
name: director-video
description: "Entrada para hacer un video nuevo (explainer, tutorial, demo, lanzamiento, short o pitch en video): preproducción con biblia, producción por escena con el mejor motor y verificación. Úsala con «hazme un video…» o /filmcraft-studio:video. Con material grabado: montaje-*; promo de repo: promo-codigo."
---

# Director de video

**Material grabado (reel o resumen de una charla o un evento):** no sigas aquí. Pregunta una vez «¿lo monto solo o contigo?» y pasa a `montaje-headless` o `montaje-asistido`, sin biblia larga; la preproducción solo entra si la piden o si no hay estilo. **Animar una sola imagen:** skill `imagen-a-video`.

Todo video sale de la misma cadena: **preproducción (preguntas, referencias, design system, guion y biblia aprobada) → producción por escena → ensamblado en FilmCraft → verificación contra la biblia → entrega**. Lo que cambia según el tipo es la plantilla del guion y qué motor hace cada escena. Esta skill decide y coordina; el oficio fino vive en `editor-filmcraft`, los estilos en `design-system-video` y el render por código en `promo-codigo`.

Referencias (léelas cuando toque, no todas de golpe):
- `${CLAUDE_SKILL_DIR}/references/tipos.md`: los tipos de video, cada uno con su estructura, duración, formato y reglas.
- `${CLAUDE_SKILL_DIR}/references/guion.md`: cómo escribir el guion y el formato de `guion.json`.
- `${CLAUDE_SKILL_DIR}/references/motores.md`: qué motor hace qué escena, con qué herramienta y cómo entra en FilmCraft.
- `${CLAUDE_SKILL_DIR}/references/imagen-a-video.md`: animar una imagen fija (cámara por los focos, paralaje, capas, bucle, revelado), cuándo usar cada modo y cuándo delegar en IA generativa o en Blender.
- `${CLAUDE_SKILL_DIR}/references/herramientas.md`: herramientas open source por necesidad (Blender, FilmCraft, Manim, Synfig, VHS, OBS, ffmpeg, whisper, TTS local, ComfyUI…) y cómo usarlas sin interfaz.
- `${CLAUDE_SKILL_DIR}/references/reglas.md`: el listón profesional y la lista de verificación.

Antes de cada llamada a un script (el estado del shell no persiste entre llamadas; las referencias usan `$S` y heredan `CLAUDE_PLUGIN_DATA` de aquí):

```bash
S=${CLAUDE_PLUGIN_ROOT}/scripts
export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}
python3 $S/herramientas.py --doctor     # preflight (o /filmcraft-studio:doctor); con material grabado: --doctor --para camara
```

`W` es la carpeta de trabajo definida en `${CLAUDE_PLUGIN_ROOT}/skills/preproduccion/SKILL.md` («Carpeta de trabajo W»).

## Flujo

1. **Preproducción** con la skill `preproduccion` (con «exprés» o `--expres`, su modo exprés), salvo que ya exista `W/preproduccion/biblia.json` aprobada. Allí se pregunta todo por rondas y se leen las referencias. También se cierran:
   - las respuestas del brief, el tipo y el formato;
   - los hechos con fuente;
   - el concepto y su metáfora;
   - el design system, con sus movimientos, su sonido y los fotogramas elegidos;
   - la crítica de originalidad;
   - `guion.json` con motor y herramienta por escena;
   - los criterios de aceptación.

   No se produce ninguna escena sin la biblia aprobada. En headless, la biblia queda `inferida` y lo que se habría preguntado va al informe.
2. **Herramientas.** `herramientas.py` dice qué motores hay. Si la biblia pide uno que no está instalado, pide permiso para instalarlo o propón otro y anótalo en la biblia.
3. **Producción por escena** según `${CLAUDE_SKILL_DIR}/references/motores.md` y la biblia. Cada escena termina siendo un archivo de video, imagen o audio al lienzo y fps del DS:
   - `camara`: material grabado, que pasa por análisis.
   - `codigo`: render reproducible.
   - **imagen → video** (dentro de `codigo`): un fotograma aprobado, un poster o una foto se vuelve plano con `python3 $S/imagen_a_video.py IMG --modo kenburns|parallax|capas|ciclo|revelado --dur S --fps N --out escena.mp4`. El movimiento sale de la ficha de la imagen (`ref_metricas.py`), no se inventa. Revisa antes con `--fotogramas` y comprueba el último fotograma con `referencias.py --comparar` (`imagen-a-video.md`). Si el encargo es solo ese plano, sin biblia: skill `imagen-a-video`.
   - `pantalla`: grabación real con VHS, OBS, Screen Studio o Cap.
   - `3d`: Blender sin interfaz con `motor_blender.py`, con la paleta y las fuentes del DS.
   - `2d`: Grease Pencil, Synfig, Glaxnimate o Manim.
   - `ia`: solo planos de relleno, desde imagen propia y con permiso.
   - `foto` y `tarjeta`: se resuelven en el compilador.
   - Voz (TTS o grabada) y música, en la rejilla de beats del guion.
4. **Ensamblado en FilmCraft.** Primero `analyze_media.py` sobre todas las fuentes, incluidas las renderizadas (`--sin-vision` si no tienen personas). Después `W/brief.json` sale de la biblia: con material de cámara, `python3 $S/brief_infer.py --analisis "<caché de análisis>" --dado '<respuestas de la biblia>' --out "$W/brief.json"`; sin material, el mismo script sin `--analisis`: `python3 $S/brief_infer.py --dado '<respuestas de la biblia>' --out "$W/brief.json"` (mismo formato: `valor`, `origen`, `confianza`, `por`). Si difieren, manda la biblia. Después un `plan.json` con un bloque por escena (formato en `${CLAUDE_PLUGIN_ROOT}/skills/montaje-headless/references/plan.md`), y luego `plan_compile.py` y `apply_plan.py`, en `--headless` o `--live`. FilmCraft pone los subtítulos, la barra de marca, los SFX ligados a eventos, la música con ducking, el grade y el limitador desde el DS. Si la música se generó por código para todo el video, pásala en `musica.archivo`.
5. **Verificación.** El bucle de `${CLAUDE_SKILL_DIR}/references/reglas.md` («Verificación»), con la lista de esa misma página delante:
   - medir: `verify.py … --out "$W/verificacion/vN"` sobre el proyecto de FilmCraft y, por cada escena o entregable ya renderizado, `${CLAUDE_PLUGIN_ROOT}/bin/cine medir-video <video> --out "$W/verificacion/vN/medidas-<nombre>.json"`; hojas de fotogramas en los tiempos clave; los criterios de estilo con `python3 $S/referencias.py --comparar <referencia o ficha> <fotograma> --json --out "$W/verificacion/vN/comparaciones/<ref>__<fotograma>.json"`;
   - `cine puntuar --ds <id> --biblia "$W/preproduccion/biblia.json" --compiled "$W/compiled.json" --verificacion "$W/verificacion/vN/verificacion.json" --medidas … --comparaciones "$W/verificacion/vN/comparaciones" --out "$W/verificacion/vN/ejes.json"`;
   - subagente `critico-juicio` con `ejes.json` y `W` → `juicio.json` (historia, copy, originalidad contra la biblia y las referencias, y los criterios `juicio`);
   - `cine nota --ejes … --juicio … > nota.json` → veredicto y los 5 arreglos; en la vuelta siguiente, `--mejor <nota> --bloq-anterior si|no`: si es Regresión, vuelve a la mejor; A/B solo si `ab_necesario`. Para con «publicable» o con un Empate y di lo que queda.

   Arregla y vuelve a compilar solo lo afectado. Cuando el usuario dé una nota (en texto o con `/filmcraft-studio:nota`), sigue `${CLAUDE_PLUGIN_ROOT}/commands/nota.md`; cada una se anota en la biblia (`cambios`, sube `iteracion`).
6. **Entrega.** Exporta solo cuando lo pidan, en texto o con `/filmcraft-studio:entregar` (sigue `${CLAUDE_PLUGIN_ROOT}/commands/entregar.md`, que mide cada archivo con `cine medir-video`), en los formatos de la plataforma. FilmCraft también entrega subtítulos SRT (`captions.export`; VTT con `ffmpeg -i x.srt x.vtt`) e intercambio OTIO/FCPXML/EDL (`file.exportInterchange`) si se piden. Escribe `informe.md` con:
   - la tabla de criterios de la biblia, que sale de `${CLAUDE_PLUGIN_ROOT}/bin/cine criterios --biblia "$W/preproduccion/biblia.json" --medidas <medidas de cada entregable> --md`; las filas `juicio` se completan con `criterios` de `juicio.json`;
   - la nota y el veredicto de `nota.json`;
   - el guion, las fuentes de cada afirmación, los motores usados y lo que no se pudo verificar (`sin_medir`; por ejemplo, el audio sin escuchar).

## Otras herramientas

`python3 $S/herramientas.py` detecta lo instalado; ofrece solo eso y pide permiso para instalar lo demás. Si existe **bloques** (orden `bloques` en el PATH, `$BLOQUES_HOME/bin/bloques` o `~/Documents/GitHub/bloques`), úsalo para escenas de tipografía y tarjetas: escribe su YAML (lee su `GUIA-IA.md`) en vez de un script nuevo. Si hay skills o MCP de **Remotion**, **HyperFrames**, **ElevenLabs** (voz) o **Suno** (música, revisa la licencia), ofrécelos para su motor pasándoles el contrato de `herramientas.md` (lienzo y fps del DS, paleta y fuentes, duración en beats, salida en `W/escenas/`). Tú conservas la biblia, el ensamblado y la verificación. Si el entregable es un deck, un PDF o una página, no es un video: pasa a la skill de ese formato con la biblia como entrada.

## Reglas que no se negocian

- Lo que el video dice del producto o del evento es real: grabación, dato con fuente o cita. Nada de UI inventada ni cifras sin origen.
- No se usan logos ni marcas de terceros, salvo material con licencia que aporte el usuario. Se nombran con texto descriptivo.
- La IA generativa (video, voz clonada, música) solo entra con permiso, sin imitar a personas reales ni a artistas, y respetando la licencia de la herramienta.
- Nada se publica ni se sube: se entrega el archivo o el proyecto.
- Si algo no se pudo comprobar, se dice en la entrega en vez de darlo por bueno.
