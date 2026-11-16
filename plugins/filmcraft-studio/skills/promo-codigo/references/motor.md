# Cómo se escribe el motor de una promo nueva

El plugin no trae una promo de ejemplo: cada promo se escribe desde cero en la carpeta de trabajo `W` (en un repo, `<repo>/video/<slug>/`) con este esqueleto. Las reglas de cada gramática están en `gramaticas.md` y los números de lo que ya se probó, en `aprendido.md`.

## Carpeta

```
W/
├── timeline.py        la rejilla: BPM, escenas en beats, REMAP salida → fuente. Lo importan imagen y audio
├── term.tape, rc.sh   grabación real con VHS (si hay algo que grabar)
├── escena.py          imagen fotograma a fotograma (una por estilo o por formato: escena_v.py para 9:16)
├── audio.py           música y SFX sintetizados en la misma rejilla
├── render.sh          material → audio → imagen → mezcla → medida
├── build/             intermedios reutilizables (grabaciones, fotogramas de la fuente, WAV sin masterizar)
└── salida/            lo que se entrega
```

`build/` y `salida/` no se versionan. Si la escena crece mucho, sepárala por escenas (`hook()`, `terminal()`, `stats()`, `end()`) dentro del mismo script antes que en varios ficheros: el orden y las transiciones se leen en un solo `scene(t)`.

## 1. La rejilla (`timeline.py`)

Todo lo que se ve o se oye cae en un beat. El fichero solo tiene constantes y funciones puras:

- `BPM` (el de `promo.bpm` del DS), `BEAT = 60 / BPM`, `FPS`, `W, H` (de `lienzo` del DS) y `TOTAL = n_beats * BEAT + cola` (cola de 1,4–1,6 s para el *sting*).
- `b(n)`: segundos del beat `n`. Escenas como tuplas en beats, en compases de 4: `HOOK = (0, 8)`, `TERM = (8, 28)`…
- Eventos de la grabación en segundos **medidos en la fuente** (no los de las constantes del tape: las salidas llegan después del tecleo).
- `REMAP`: lista de pares `(tiempo_salida, tiempo_fuente)`, lineal a trozos, para que cada resultado real caiga en un beat; `src_time(t)` y su inversa `out_time(s)`. La imagen pide a la fuente `src_time(t)`; el audio coloca los clics en `out_time(f / fps)`.
- Ventanas con significado (`FREEZE = (b(20), b(26))`): la imagen las usa para parar cámara y grano; el audio, para filtrar o frenar.

## 2. Material real (VHS)

- `term.tape` con `Set Shell "bash"`, fuente, tamaño, `Width/Height` (1600×900 en 16:9), `Framerate`, `TypingSpeed`, `CursorBlink false` y un `Theme` con la paleta del DS (fondo, texto y acento del cursor).
- Arranque escondido: `Hide`, `Type "source ./rc.sh; clear"`, `Enter`, `Show`. `rc.sh` deja un prompt mínimo con el acento (`PS1` con una flecha y nada más) y entra en la carpeta de la demo.
- Comandos de verdad contra el servicio real del proyecto. Para un arranque en caliente, haz antes un arranque y bájalo, y dilo en pantalla o en el informe. Al terminar, deja el sistema como estaba (`down -v`, borrar plantillas).
- **Mide** el fotograma de cada resultado: lee la grabación en gris con ffmpeg (`-f rawvideo -pix_fmt gray -`), recorta la franja de cada fila (`row_y(i)` = margen superior + alto de línea × i) y busca el primer fotograma en que su diferencia con el anterior supera un umbral. Esos fotogramas son los de `REMAP` y los de los clics de teclado. Anota los valores que imprime la terminal: el gancho usa esos números.

Sin nada que grabar (un clasificador, una librería), la escena es solo dibujo y lo dice en pantalla si es un esquema ilustrativo.

## 3. La escena (`escena.py`)

Contrato: `escena.py [fuente.mp4 dir_fotogramas] salida.mp4 [t1,t2,…]`.

- Lee el DS con `common.load_ds(id)`. La ruta de los scripts del plugin no se escribe a fuego (cambia al actualizarlo): llega por entorno (`export FILMCRAFT_STUDIO_SCRIPTS="$S"`, con `$S` del SKILL.md, antes de `render.sh` o de la escena) y la escena hace `sys.path.insert(0, os.environ["FILMCRAFT_STUDIO_SCRIPTS"])`. Del DS: paleta con `hex2rgb(ds["paleta"][rol])`, fuentes con `pil_font(ds["fuentes"]["titular"], tamaño)`, lienzo y `promo.mapas` si la gramática los tiene. Nada de hex ni rutas de fuentes sueltos en el script.
- Si hay grabación, extrae sus fotogramas una vez a `build/` (`ffmpeg -i fuente.mp4 dir/f%04d.png`) y lee el de `src_time(t)`.
- Una función pura `frame(t) -> np.ndarray uint8 (H, W, 3)`: `scene(t)` elige la escena por beats, compone con PIL y numpy, y al final aplica lo global (firma, grano, viñeta, barra de progreso, fundido). La firma es una función del tiempo (`temperatura(t)`, `congelado(t)`) que vale 0–1 con rampas cortas, no un `if`.
- Grano precalculado (unas pocas texturas de ruido) que avanza con el fotograma y **se para** en la firma si la gramática lo pide; viñeta precalculada.
- Con el último argumento (segundos separados por comas) escribe `salida_<t>.png` y no el video: así salen los fotogramas fijos para elegir estilo y la hoja de revisión sin renderizar todo.
- Video: `ffmpeg -f rawvideo -pix_fmt rgb24 -s WxH -r FPS -i - -c:v libx264 -crf 16 -pix_fmt yuv420p salida.mp4` alimentado por `stdin` con `frame(i / FPS).tobytes()`. Sin audio: se mezcla después.
- Utilidades que siempre hacen falta: `clamp`, `prog(t, t0, t1)`, curvas (`out_expo`, `in_out_cubic`, `out_back`), `lerp`, `mix` de colores, `text()` con tracking y `fit(s, ancho)` que baja el cuerpo hasta que cabe (imprescindible en 9:16). Caché de fuentes por `(ruta, tamaño)`.
- Cámara sobre la grabación: posición y zoom por *keyframes* en beats con easing, quieta en las pausas; un látigo (*whip*) de ~0,22 s entre escenas mezclando la escena saliente y la entrante con desenfoque de movimiento.
- Animaciones de dos en dos (15 fps) solo si la gramática lo dice (riso); el resto, a 30 fps.

## 4. El audio (`audio.py`)

Contrato: `audio.py [fuente.mp4] salida.wav`, 48 kHz estéreo, en la rejilla de `timeline.py`.

- Dos buffers `L, R` de `TOTAL * SR` muestras y un `add(señal, t, ganancia, pan)` con *panning* de potencia constante. Todo se coloca con `add(..., b(n))`.
- Instrumentos con numpy, cortos y deterministas (`rng = np.random.default_rng(semilla)`): kick con barrido de tono exponencial, clap de ruido filtrado, pad aditivo desafinado, stabs de acordes, sub con portamento, campana FM; filtro de un polo (`onepole_lp`, `hp = x - lp(x)`) para abrir y cerrar.
- El género, la tonalidad y los acordes salen de `musica.genero` del DS. El kick hace *sidechain* (una curva de ducking por golpe) antes de sumarse.
- SFX: el kit del DS (`promo_sfx.py <gramática> <ds>/assets/sfx`) o los mismos sintetizadores en el script. Un SFX por acción en pantalla; clics de teclado en los fotogramas medidos de cada fila de comando (`out_time((f + 1) / fps)`, pan aleatorio leve); *whoosh* antes de cada látigo, impacto en los golpes, la firma también suena (hielo, rayado, *tape stop*).
- Reverb barata: convolución por FFT con un IR de ruido que decae (~1,6 s) mezclado al 15–20 %. Fundido final, normaliza a pico ~0,89 y escribe PCM de 16 bits con `wave`.

## 5. `render.sh`

1. Material: graba solo si no existe `build/term.mp4` (las grabaciones se reutilizan entre estilos).
2. Audio y máster: `-14 LUFS`, `≤ -1 dBTP`. Dos pasadas de `loudnorm` (la primera con `print_format=json` mide; la segunda aplica `measured_*` con `linear=true`) y `alimiter` al final; consigna `TP=-1.5` para quedar por debajo de −1 medido.
3. Imagen: `python3 escena.py … build/video.mp4`, con `FILMCRAFT_STUDIO_SCRIPTS` exportada (la `$S` del SKILL.md). `render.sh` empieza con `: "${FILMCRAFT_STUDIO_SCRIPTS:?exporta la ruta de scripts/ del plugin}"`.
4. Mezcla: `-c:v libx264 -crf 22 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart -shortest`.
5. Medida: `"$FILMCRAFT_STUDIO_SCRIPTS/../bin/cine" medir-video salida.mp4 --out salida.medidas.json` e imprime `audio.lufs` y `audio.pico_dbtp` (la verificación usa ese mismo JSON).

Con `set -euo pipefail`, `cd "$(dirname "$0")"` y un argumento por estilo o formato (`./render.sh brasa|riso_v`, `FMTS=9x16 ./render.sh`).

## 6. Fase 3D (Blender)

`motor_blender.py ESCENA.py --ds DS --out x.mp4 --segundos S [--param k=v] [--escala 0.5] [--motor cycles|eevee] [--fotogramas 1,48]`. La escena 3D solo construye contenido y recibe todo por `--param` (texto, preset, formato, la carpeta de placas). Para vidrio: Cycles a media resolución para la refracción y una pasada Eevee de máscara a resolución completa; fuera de la máscara manda la placa nítida dibujada por código. Orden de render: placas → vidrio → video. Plantilla mínima: `scripts/blender/titular.py`.

## 7. Ensamblar en FilmCraft (opcional)

Cuando la promo se mezcla con otros motores o con material de cámara: corta las escenas sin audio (`-an`), copia el DS a un catálogo temporal (`FILMCRAFT_DS_CATALOGO`) con `musica.archivo` apuntando al WAV masterizado, y pasa `analyze_media.py --sin-vision` → `plan_compile.py plan.json` → `apply_plan.py --headless` → `render_sheet.py` → `verify.py`. El `plan.json` sigue `schemas/plan.schema.json`.

## Rendimiento medido

1080p30 de 23 s: ~45 s de render en un M4 (PIL + numpy, ~65 ms por fotograma); audio en menos de 3 s. Blender Cycles a media resolución con 64 muestras domina el tiempo de una fase de vidrio.
