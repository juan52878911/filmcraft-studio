# Operar FilmCraft

FilmCraft 0.8.x: NLE de código abierto en Rust (github.com/storytold/filmcraft, Apache-2.0), con objetivo de paridad con Premiere Pro. Documentación del repositorio: `docs/agents.md`, `docs/control-protocol.md`, `docs/graphics.md` y `docs/transcripts.md`.

## Índice
1. Formas de control
2. Tiempo y unidades
3. Descubrir comandos
4. Proyecto y pistas
5. Clips y movimiento
6. Efectos y keyframes
7. Gráficos y textos
8. Transcripción
9. Exportar y renderizar
10. Trampas conocidas
11. Migrar desde Palmier

## 1. Formas de control

| Modo | Cómo | Cuándo |
|---|---|---|
| App en vivo | `open -a FilmCraft --args --control 9876`; MCP de usuario `filmcraft` (`filmcraft-cli mcp --bridge 127.0.0.1:9876`) o `scripts/fclib.py` (socket JSON por líneas) | El usuario mira la ventana; ediciones interactivas |
| Headless | `filmcraft-cli --project P.fcproj [--save \| --save-as X] exec <id> '<json>'`, `run script.jsonl`, `inspect`, `render`, `export` | Lotes, verificación y renders sin tocar la ventana |

- El CLI está en `~/.local/bin/filmcraft-cli`. Si `claude` es una función o alias de shell, llama al binario directo (`~/.local/bin/claude`) para `claude mcp …`.
- Con la app abierta, `render` del CLI con `--bridge` no funciona: guarda (`file.save`) y renderiza en headless con `--project`.
- No escribas el `.fcproj` en headless mientras la app lo tiene abierto, porque su autoguardado lo pisa.
- El proyecto es JSON legible (`format: filmcraft.project`). Puedes leerlo para verificar keyframes y estructura. Edítalo solo mediante comandos.

## 2. Tiempo y unidades

- 254016000000 ticks por segundo. La mayoría de comandos aceptan también `seconds=`, `frame=` o `timecode=`.
- Las respuestas de `sequence.inspect` dan `start`/`end` en ticks y `startFrame`/`endFrame` en fotogramas de la secuencia.
- Los fps de la secuencia pueden cambiar (el usuario pasó un reel de 30 a 60 fps y todos los fotogramas se duplicaron). Relee `inspect` antes de usar números de fotograma.
- Posiciones en píxeles del lienzo (1080×1920 en vertical). La escala va en %.

## 3. Descubrir comandos

- `filmcraft-cli … commands [filtro]` lista unos 700 comandos con sus parámetros.
- `describe <id>` muestra un comando en JSON.
- `effects.list {"kind":"Video|Audio|VideoTransition|AudioTransition","detail":true}` lista efectos con sus parámetros.
- Comandos de selección: muchos actúan sobre la selección y aceptan `clips`/`clip`. Si no, selecciona antes con `timeline.select {"clips":[…]}`.

## 4. Proyecto y pistas

- `file.newProject`, `file.open`, `file.save`, `file.saveAs`, `file.import {"paths":[…]}` (devuelve los `items`).
- `file.newSequence` (ancho, alto, fps), `sequence.settings`, `sequence.addTracks {"video":n,"videoAfter":"V2"}`, `sequence.deleteTrack`, `timeline.setTrack {"track":"V1","name":…}`.
- En video, el índice 0 es la pista de abajo (V1) y las de encima tapan a las de abajo.
- `timeline.place {"item","track":"V2","frame"|"time","duration","audio":false}` coloca clips. Aquí `track` sí acepta "V2" o un id.
- Mover: `timeline.move {"moves":[{"clip","track","time"}],"insert":false,"linked":false}`.
- Borrar: `edit.clear {"clips":[…]}`; con ripple, `edit.rippleDelete`.

## 5. Clips y movimiento

- **Video 4K en secuencia 1080:** `timeline.select` y luego `clip.scaleToFrameSize`. Con eso el 100 % equivale a encajar en el lienzo y las escalas de Palmier (1.12 → 112 %) se trasladan directo.
- Las imágenes no lo necesitan: la escala es `encajar × 100`, con encajar = `min(W/ancho, H/alto)`.
- Efecto `motion`: `position` [x, y] es el centro en píxeles del lienzo (ancla = centro de la fuente), `scale` en %, `rotation`. Una posición "top-left normalizada" de Palmier (a, b) con tamaño s se convierte en `((a + s/2)·W, (b + s/2)·H)`.
- Velocidad: `clip.speedDuration {"clips","speed":400,"ripple":true,"interpolation":"opticalFlow"}`. Con flujo óptico los speed ramps quedan suaves.
- Estabilizar: efecto `warp_stabilizer`. Reencuadrar: `auto_reframe`.

## 6. Efectos y keyframes

- Aplicar: `effects.apply {"clips":[…],"effect":"gaussian_blur"}`. Ajustar: `effects.setParam {"clip","effect":"<id>|<índice>","param","value"}`.
- **Keyframe:** `effects.setParam` con `"keyframe":true` y `"time"` en **ticks de la secuencia** (inicio del clip + desfase).
- **Interpolación:** `effects.setInterpolation {"clip","effect","param","mediaTime","interpolation":"linear|bezier|autoBezier|hold|easeIn|easeOut"}`, con `mediaTime` = **`source_in + desfase × speed`**. En imágenes, `source_in` es 0.
- Para borrar keyframes de un parámetro: `effects.toggleAnimation` (lo deja estático).
- Efectos útiles:
  - Color: `lumetri`.
  - Desenfoque: `gaussian_blur` (`blurriness`, `repeat_edge`) y `directional_blur`.
  - Recorte: `crop` (left, top, right, bottom en %).
  - Opacidad: efecto `opacity`.
  - Textura: `noise` (grano), `sharpen`, `unsharp_mask`.
  - Estilo: `rgb_split`, `camera_shake`, `light_leaks`, `echo`, `glow`.
- Transiciones nativas (`effects.list {"kind":"VideoTransition"}`): `glitch`, `zoom_blur`, `directional_blur_transition`, `flash`, `push`, `slide`, `light_leak`, `cross_zoom`, `dip_to_white`…

## 7. Gráficos y textos

- Crear: `graphics.newText {"text","position","size","font","fontStyle","seconds","track":<índice 0-based>,"time"}`. Devuelve `{clip, layer}`.
  - Con `"clip": id`, añade una capa al mismo gráfico. Así las palabras de un texto animado viven en un solo clip.
- **`track` debe ser un número.** Una cadena como "V7" se ignora en silencio y el texto cae en la primera pista libre: puede quedar por encima de los mattes.
- Estilo: `graphics.set {"clip","layer","props":{…}}` con `align` (Left/Center/Right), `fill_color`, `background`, `background_color`, `background_opacity` (100), `background_size` (margen), `background_radius` (0), `shadow`, `anchor`, `position`, `scale`, `opacity`.
- Medir: `graphics.list {"clip"}` → `localBounds` [x0, y0, x1, y1] y `quad`.
  - Para centrar un bloque en (cx, cy): `anchor` = centro de `localBounds`, `position` = (cx, cy).
- Animar capas: `effects.setParam` con `effect` = `effectIndex` de la capa (lo da `graphics.list`) y `param` = scale, opacity o position, con keyframes.
  - popIn: escala 60 → 108 → 100 en 0/8/14 f y opacidad 0 → 100 en 6 f.
  - Aparición por palabras: una capa por palabra, escalonada cada ~10 f.
- Fuentes: los nombres de familia de macOS ("IosevkaTerm Nerd Font Mono" + estilo "Heavy", "Menlo" + "Bold"). Compruébalo con `graphics.fonts.used`.
- **Escala desde Palmier:** el tamaño de fuente y los márgenes de Palmier se dibujan a 1920/1080 ≈ 1,78× los px de FilmCraft. El `transform` del texto en Palmier es la caja con el margen incluido; su centro sirve como (cx, cy).

## 8. Transcripción

- La versión publicada no trae transcripción (`transcript.generate` deshabilitado), pero sí `transcript.set`, `search`, `inspect`, `removePauses`, `removeFillers`, `extract`, `lift` y `createCaptions`.
- Usa `scripts/transcribe_fc.py` (whisper.cpp con DTW y vocabulario) y luego `filmcraft-cli --project P --save run import.jsonl`.
- `transcript.search {"query"}` devuelve rangos en ticks de la secuencia: sirve para localizar frases en el montaje.
  - Ignora mayúsculas y puntuación, pero exige la secuencia exacta de palabras: "alguno conoce Kiro" no encuentra "¿Alguno conoce a Kiro?". Busca por 1–3 palabras clave y amplía si hace falta.
- `transcript.createCaptions {"maxChars":20,"lines":1,…}` crea una pista de subtítulos. Pruébalo primero en una copia. `captions.export {"path":"x.srt"}` exporta el SRT.

## 9. Exportar y renderizar

- Fotograma: `filmcraft-cli --project P render --seconds S --out f.png --scale 0.25 --allow-offline`, o `scripts/render_sheet.py` para varios.
- Video: `filmcraft-cli --project P export out.mp4` (formato por la extensión), o `file.exportMedia` con `preset`, `crf`, `bitrateMode` (`vbr2Pass`), `proresProfile`, `loudnessLufs`, `hardwareEncoding`, `range`, `wait`.
  - Es lento: unos 7 min para 57 s 4K→1080 con GPU parcial. Lánzalo en segundo plano.
- Intercambio: `file.exportInterchange {"format":"xml|fcpxml|otio|aaf|edl"}`.

## 10. Trampas conocidas

| Síntoma | Causa | Arreglo |
|---|---|---|
| Todo se ve ampliado ×2 | Clip 4K sin escalar a fotograma | `clip.scaleToFrameSize` |
| Las animaciones importadas no se mueven o se quedan en su último valor | Keyframes de FCPXML con tiempo relativo al clip | Reescribirlos con la base `source_in` |
| `setInterpolation`: "no keyframe at that time" | `mediaTime` sin `source_in` o sin multiplicar por `speed` | `mediaTime = source_in + desfase × speed` |
| Textos repartidos en pistas raras | `track` como cadena en `graphics.newText` | Índice numérico |
| Música a 0 dB | El FCPXML perdió el ducking | Keyframes de `volume.level` |
| Diálogo mezclado con efectos de sonido | Importador | `timeline.move` con `linked:false` a la pista de diálogo |
| FCPXML sin imágenes ni títulos | El importador se salta `<video>` y `<title>` | Recrear con `timeline.place` y `graphics.newText` |
| Bloques de texto más altos que en Palmier | `background_size` es un margen único | Aceptarlo o ajustar a mano |
| `graphics.newText`/`timeline.place`: "V6 is not free here" con clips seguidos | Un `time` unos ticks antes del borde de fotograma se baja al fotograma anterior y pisa al clip previo | Convierte segundos a ticks exactos de fotograma (`fcengine.Engine.tk`) |
| Cambios headless perdidos | La app abierta autoguardó encima | Cerrar la app antes, o usar el canal de control |

## 11. Migrar desde Palmier

Los conversores probados están en `scripts/palmier/` del plugin (configura `PALMIER_PROJECT`, `PALMIER_TIMELINE` y `PALMIER_GRAFICA`):
- `palmier.py`: lector del `project.json` (los fotogramas usan los fps de la timeline de Palmier).
- `convert_stills.py`, `convert_fx.py`, `convert_motion.py`, `convert_texts.py`, `convert_audio.py`, `word_reveal.py`.
- Para las hojas de comparación, `scripts/render_sheet.py`.

Flujo:
1. Exportar FCPXML desde Palmier (`export_project mode=fcpxml`) e importarlo en un proyecto nuevo.
2. Activar `scaleToFrameSize` en el video principal.
3. Ejecutar los conversores.
4. Comparar fotograma a fotograma contra el export de Palmier.
