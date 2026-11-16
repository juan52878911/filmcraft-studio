---
name: promo-codigo
description: "Promo de un repositorio o de una release renderizada por código, sin cámara: terminal grabada con VHS, escenas en Python, música y SFX sintetizados. Úsala con «video para promocionar mi repo», «promo de la versión», «pásalo a 9:16» o /filmcraft-studio:promo. No para material grabado (montaje-*)."
---

# Promo por código

Un promo de repo no tiene material de cámara: el producto *es* la terminal y los datos del repo. Sus escenas se **renderizan**: una línea de tiempo en beats manda sobre la imagen y el audio, y todo sale de scripts reproducibles. Es el motor `codigo` de la skill `director-video`. Un promo puede salir directamente del render, o sus escenas pueden entrar como fuentes en FilmCraft junto a otros motores.

El plugin no trae promos de ejemplo: el motor de cada una se escribe en la carpeta de trabajo con el esqueleto de `${CLAUDE_SKILL_DIR}/references/motor.md` (carpeta, `timeline.py`, grabación VHS y su medida, contrato de la escena y del audio, `render.sh`, fase 3D y ensamblado en FilmCraft). Léelo antes de escribir la primera línea.

Lo aprendido haciendo las primeras promos, con datos: `${CLAUDE_SKILL_DIR}/references/aprendido.md` y, si existe, la capa del usuario `${CLAUDE_PLUGIN_DATA}/aprendido.md`. Reglas de cada gramática: `${CLAUDE_SKILL_DIR}/references/gramaticas.md`.

Antes de cada llamada a un script (el estado del shell no persiste entre llamadas):

```bash
S=${CLAUDE_PLUGIN_ROOT}/scripts
export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}
python3 $S/herramientas.py --doctor --para promo   # preflight: FilmCraft solo recomendado, comprueba VHS; sale 1 si falta algo obligatorio
```

`W` (carpeta de trabajo) sigue la regla de `${CLAUDE_PLUGIN_ROOT}/skills/preproduccion/SKILL.md`: en un repo, `<repo>/video/<slug>/`.

## Flujo

0. **Preproducción** con la skill `preproduccion` (con «exprés» o `--expres`, su modo exprés): preguntas por rondas, referencias leídas por su filosofía, concepto y metáfora, DS, crítica de originalidad y biblia aprobada con criterios de aceptación. Los pasos 1 y 3 se hacen dentro de ella; si ya hay biblia aprobada, se leen de ahí. **Orden real:** para los fotogramas fijos de la preproducción, escribe antes `timeline.py` y una `escena.py` mínima (gancho y firma, con el esqueleto de `motor.md`); la grabación VHS (paso 2) puede ir después: hasta entonces la escena usa un fondo o un fotograma de prueba y lo dice. Si el usuario no ha dicho nada, ofrece el modo exprés en la primera pregunta.
1. **Qué es nuevo, con fuente.** Lee `CHANGELOG.md`, tags y `gh release view` de la versión; en repos grandes delega en un subagente (si los hay) que devuelva cifras con `fichero:línea`. Elige 1 idea central + 3–4 capacidades llamativas en **cifras absolutas** de la versión actual (no "antes/después" salvo que lo pidan). Comprueba cada afirmación comparativa contra una medida del repo; si no se sostiene, dilo al usuario y escribe la versión defendible (p. ej. "mismo orden de magnitud que…" con su fuente en pantalla).
2. **Material real.** Graba la terminal con VHS (`term.tape` + `rc.sh` con un prompt mínimo, comandos de verdad contra el servicio real del proyecto; p. ej. un daemon o una CLI). Si quieres mostrar un arranque en caliente, haz antes un primer arranque y dilo. Mide en qué fotograma aparece cada resultado (diff por filas: `row_y`, en `motor.md`) y anota los valores reales que salen (0.4 s, 375 ms…): el gancho usa *esos* números. Sin nada que grabar, la promo es solo escenas dibujadas y lo que sea un esquema ilustrativo lo dice en pantalla.
3. **Design system de promo.** `ds_studio.py catalogo` y elige uno `promo-*`, o crea otro (gramática nueva = nueva sección en `gramaticas.md`). Una gramática nueva escribe primero su **filosofía**: la regla que genera el aspecto, qué significa del producto, dónde no actúa y cómo varía. Después su vocabulario de movimientos, cada uno con su significado. Antes de animar, enseña 2 fotogramas fijos por estilo (gancho y momento firma) para elegir y pásalos por el agente `critico-estilo`. **Cómo sacarlos:** la escena acepta como último argumento los segundos separados por comas y escribe `<salida>_<t>.png` en vez del video (`python3 escena.py build/term.mp4 build/f build/e 0.6,9.2`); junta los PNG en una hoja con PIL o `render_sheet.py` si ya está en FilmCraft. Un DS de promo nuevo necesita:
   - los fondos de su gramática: `promo_fondos.py <id>`, no los brutalistas de `ds_assets.py`;
   - su kit de SFX: `promo_sfx.py <gramatica> <ds>/assets/sfx`;
   - las pistas canónicas de FilmCraft (`Main`, `Dialogue`, `Music`…), para poder ensamblarlo.
4. **Guion en beats.** `timeline.py` (ver `motor.md`): BPM, escenas en beats (compases de 4) y `REMAP` salida → fuente para que cada resultado real caiga en un beat. Estructura base (≈23–27 s): gancho con el resultado en ≤ 1 s → demo real con la cámara encima → firma (lo único que hace este proyecto) → cifras/capacidades → ecosistema → cierre con instalación y URL.
5. **Escenas.** Un script de imagen por estilo o formato (`escena.py`, `escena_v.py`), con el contrato de `motor.md`. La escena lee paleta, fuentes y BPM del DS; nada de hex sueltos en el script. Cámara sobre la grabación con easing y quieta en los momentos de pausa; textos de cartel ajustados al ancho (`fit`) en vertical; rótulos en una franja libre.
6. **Audio.** Un script por estilo en la misma rejilla: micro-género con BPM, clics de teclado sacados de los fotogramas en que cambia cada fila de comando, un SFX por acción en pantalla, la firma también suena (hielo, rayado, *tape stop*). Máster `loudnorm=I=-14:TP=-1.5` + limitador: −1,5 es la consigna para quedar ≤ −1 dBTP medido. Kit de SFX del DS: `promo_sfx.py`.
7. **Verificar antes de enseñar.** Comprueba cada criterio de aceptación de la biblia y pasa otra vez `critico-estilo` sobre la hoja del video. Hoja de fotogramas en los tiempos clave (no al azar): texto que se sale, glifos que la fuente no tiene, rótulos sobre texto de la terminal, contraste. Mide LUFS y pico real con `ebur128`. Corrige y vuelve a renderizar *solo* lo afectado. No digas que el audio está bien si no lo has escuchado: di que está medido.
8. **Entregar.** MP4 H.264 + AAC con `+faststart`; < 30 MB si se va a ver en el móvil. Para la doc: `promo_preview.py <ds> <video>` (hoja + paleta) y una copia a 540–960 px. Enséñalo con `SendUserFile` si está disponible; si no, da la ruta absoluta. Al terminar, limpia lo que la demo haya creado (proyectos, plantillas, contenedores) y añade 1–3 líneas con fecha y proyecto a `${CLAUDE_PLUGIN_DATA}/aprendido.md` si aprendiste algo nuevo.

## Otras herramientas

`python3 $S/herramientas.py` dice qué hay. Si existe **bloques** (orden `bloques` en el PATH, `$BLOQUES_HOME/bin/bloques` o `~/Documents/GitHub/bloques`) y la dirección cabe en su biblioteca, escribe su YAML (lee su `GUIA-IA.md`) en vez de un script de escena; el contrato de salida es el mismo: MP4 al lienzo del DS y WAV aparte. Si hay skills o MCP de **Remotion** o **HyperFrames** (escenas), **ElevenLabs** (voz) o **Suno** (música; revisa la licencia), ofrécelos. Si piden subtítulos o el proyecto para otro editor, ensambla en FilmCraft y entrega SRT/VTT u OTIO/FCPXML desde allí (sigue `${CLAUDE_PLUGIN_ROOT}/commands/entregar.md`). Las notas de revisión («el gancho es largo»), con `${CLAUDE_PLUGIN_ROOT}/commands/nota.md`.

## Reglas duras

- Nunca UI inventada: lo que se ve del producto es una grabación real o datos reales del repo. La IA generativa de video, si entra, solo para 2–4 planos de relleno desde fotogramas propios.
- Ningún logo de terceros (Apple, Docker…): marca registrada. Se dice con texto descriptivo y un pictograma genérico (chip, escudo).
- Cada cifra en pantalla lleva su contexto (p50, máquina, fuente). Las cifras "STALE" o de montajes distintos no se comparan como si fueran un cara a cara.
- Fuentes con glifos limitados (Helvetica Neue Condensed Black no trae `→ ′ ✓`): dibújalos o cambia el texto; revísalo en la hoja.
- El render no exporta nada que el usuario no pidió y no publica: entrega el archivo.

## Rendimiento

1080p30 de 23 s: ~45 s de render en un M4 (PIL + numpy, ~65 ms/fotograma); audio < 3 s. Las grabaciones VHS se reutilizan entre estilos (`build/`).
