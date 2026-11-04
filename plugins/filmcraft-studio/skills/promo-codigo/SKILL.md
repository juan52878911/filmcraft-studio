---
name: promo-codigo
description: Crea videos promocionales de un repositorio o de una release (lo nuevo de una versión) renderizados por código, sin cámara ni FilmCraft — terminal real grabada con VHS, escenas dibujadas fotograma a fotograma con Python, música y SFX sintetizados en la misma rejilla de beats y máster a -14 LUFS — con un design system de promo (brasa y escarcha, blueprint, risografía u otro nuevo). Úsala cuando pidan "un video para promocionar mi repo", "promo de la nueva versión", "video de lanzamiento", "algo para X/LinkedIn/Reels sobre el proyecto", "pásalo a 9:16", "otro estilo para el promo", o `/filmcraft-studio:promo`. Para montar material de cámara (eventos, entrevistas) usa montaje-headless o montaje-asistido.
---

# Promo por código

Un promo de repo no tiene material de cámara: el producto *es* la terminal y los datos del repo. Sus escenas se **renderizan**: una línea de tiempo en beats manda sobre la imagen y el audio, y todo sale de scripts reproducibles. Es el motor `codigo` de la skill `director-video`. Un promo puede salir directamente del render, o sus escenas pueden entrar como fuentes en FilmCraft junto a otros motores (ejemplo en `promo/kindling-v0.20/ensamblado/`).

Ejemplo completo y probado: `${CLAUDE_PLUGIN_ROOT}/promo/kindling-v0.20/` (tres estilos, 16:9 y 9:16, `render.sh <estilo>`). Lo aprendido haciéndolo, con datos: `${CLAUDE_SKILL_DIR}/references/aprendido.md`. Reglas de cada gramática: `${CLAUDE_SKILL_DIR}/references/gramaticas.md`.

## Flujo

1. **Qué es nuevo, con fuente.** Lee `CHANGELOG.md`, tags y `gh release view` de la versión; en repos grandes delega en un subagente que devuelva cifras con `fichero:línea`. Elige 1 idea central + 3–4 capacidades llamativas en **cifras absolutas** de la versión actual (no "antes/después" salvo que lo pidan). Comprueba cada afirmación comparativa contra una medida del repo; si no se sostiene, dilo al usuario y escribe la versión defendible (p. ej. "mismo orden de magnitud que…" con su fuente en pantalla).
2. **Material real.** Graba la terminal con VHS (`term.tape` + `rc.sh` con un prompt mínimo, comandos de verdad contra el daemon real). Haz un primer `up` antes de grabar si quieres mostrar el arranque en caliente, y dilo. Mide en qué fotograma aparece cada resultado (diff por filas: `row_y`, ver el ejemplo) y anota los valores reales que salen (0.4 s, 375 ms…): el gancho usa *esos* números.
3. **Design system de promo.** `ds_studio.py catalogo` y elige uno `promo-*`, o crea otro (gramática nueva = nueva sección en `gramaticas.md`). Antes de animar, enseña 2 fotogramas fijos por estilo (gancho y momento firma) para elegir. Un DS de promo nuevo necesita:
   - los fondos de su gramática: `promo_fondos.py <id>`, no los brutalistas de `ds_assets.py`;
   - su kit de SFX: `promo_sfx.py <gramatica> <ds>/assets/sfx`;
   - las pistas canónicas de FilmCraft (`Main`, `Dialogue`, `Music`…), para poder ensamblarlo.
4. **Guion en beats.** `timeline.py`: BPM, escenas en beats (compases de 4) y `REMAP` salida → fuente para que cada resultado real caiga en un beat. Estructura base (≈23–27 s): gancho con el resultado en ≤ 1 s → demo real con la cámara encima → firma (lo único que hace este proyecto) → cifras/capacidades → ecosistema → cierre con instalación y URL.
5. **Escenas.** Un script de imagen por estilo (`brasa.py`, `blueprint.py`, `riso.py`, `riso_v.py`). Cámara sobre la grabación con easing y quieta en los momentos de pausa; textos de cartel ajustados al ancho (`fit`) en vertical; rótulos en una franja libre.
6. **Audio.** Un script por estilo en la misma rejilla: micro-género con BPM, clics de teclado sacados de los fotogramas en que cambia cada fila de comando, un SFX por acción en pantalla, la firma también suena (hielo, rayado, *tape stop*). Máster `loudnorm=I=-14:TP=-1.5` + limitador. Kit de SFX del DS: `promo_sfx.py`.
7. **Verificar antes de enseñar.** Hoja de fotogramas en los tiempos clave (no al azar): texto que se sale, glifos que la fuente no tiene, rótulos sobre texto de la terminal, contraste. Mide LUFS y pico con `ebur128`. Corrige y vuelve a renderizar *solo* lo afectado. No digas que el audio está bien si no lo has escuchado: di que está medido.
8. **Entregar.** MP4 H.264 + AAC con `+faststart`; < 30 MB si se va a ver en el móvil. Para la doc: `promo_preview.py <ds> <video>` (hoja + paleta) y una copia a 540–960 px. Al terminar, borra lo que creaste en el daemon (proyectos y plantillas de la demo).

## Reglas duras

- Nunca UI inventada: lo que se ve del producto es una grabación real o datos reales del repo. La IA generativa de video, si entra, solo para 2–4 planos de relleno desde fotogramas propios.
- Ningún logo de terceros (Apple, Docker, HOL…): marca registrada. Se dice con texto descriptivo y un pictograma genérico (chip, escudo).
- Cada cifra en pantalla lleva su contexto (p50, máquina, fuente). Las cifras "STALE" o de montajes distintos no se comparan como si fueran un cara a cara.
- Fuentes con glifos limitados (Helvetica Neue Condensed Black no trae `→ ′ ✓`): dibújalos o cambia el texto; revísalo en la hoja.
- El render no exporta nada que el usuario no pidió y no publica: entrega el archivo.

## Rendimiento

1080p30 de 23 s: ~45 s de render en un M4 (PIL + numpy, ~65 ms/fotograma); audio < 3 s. Las grabaciones VHS se reutilizan entre estilos (`build/`).
