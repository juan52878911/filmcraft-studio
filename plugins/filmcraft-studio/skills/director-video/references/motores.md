# Motores de producción

`S` (carpeta de scripts) y `CLAUDE_PLUGIN_DATA` vienen del SKILL.md de `director-video`.

Cada escena del guion la hace un motor. Qué herramienta open source cubre cada necesidad, y cómo se usa sin interfaz: `herramientas.md`; qué hay instalado: `herramientas.py`. Todos entregan archivos al **lienzo y los fps del DS** (`lienzo.ancho`, `lienzo.alto`, `lienzo.fps`), y todos terminan como fuentes de FilmCraft: `analyze_media.py` primero y `plan.json` después.

| Motor | Para qué | Herramientas | Entra en FilmCraft como |
|---|---|---|---|
| `camara` | Personas, eventos, entrevistas, B-roll filmado | El material del usuario; voz con `procesar_voz.sh` | Fuente con análisis completo: transcripción, caras, movimiento |
| `pantalla` | Producto real: terminal, app, web | **VHS** (`.tape` reproducible, terminal), **Screen Studio** o **Cap** (app o web, con auto-zoom), `screencapture -v` | Fuente; `--sin-vision`. Mide en qué fotograma pasa cada cosa |
| `codigo` | Gráficos, tipografía cinética, diagramas, cifras, la cámara sobre una grabación, estilos de impresión | Python (PIL + numpy) con el esqueleto de `skills/promo-codigo/references/motor.md`; **bloques** si está instalado (tarjetas y tipografía en YAML). Alternativas: **Remotion** (React; licencia de empresa a partir de 4 personas), **HyperFrames** (HTML + GSAP a MP4, con skills para Claude Code), **Manim** (matemáticas y diagramas) | MP4 sin música (`-an`) y con el texto quemado; la música va aparte, en la rejilla |
| `3d` | Titulares extruidos, objetos, vidrio y refracción, partículas, cámara física | **Blender** sin interfaz con `motor_blender.py` (Eevee o Cycles + Metal) | MP4 sin audio o PNG con alfa |
| `2d` | Animación vectorial, personajes con huesos, Grease Pencil, Lottie | Blender (Grease Pencil), **Synfig**, **Glaxnimate**, **Manim** | MP4 sin audio o PNG con alfa |
| `ia` | 2–4 planos de relleno que no se pueden grabar | Kling 3.0, Veo 3.1, Seedance 2.x, MiniMax-H3, Runway Gen-4.5, Wan / LTX (pesos abiertos) | Fuente como cualquier otra; el grade y el grano del DS la igualan |
| `foto` | Fotos del evento o capturas | — | Bloque `fotos` del plan |
| `imagen` | Animar una imagen fija (referencia, ilustración, captura, foto) de forma coherente con su composición | `imagen_a_video.py` (kenburns, parallax, capas, ciclo, revelado) guiado por la ficha de `ref_metricas.py`; ver `imagen-a-video.md` | MP4 sin audio |
| `tarjeta` | Título, cierre, rótulo de pantalla completa | El compilador, desde `marca` y `fondos` del DS | Bloques `tarjeta`/`titulo`/`cierre` |
| voz | Voz en off | Grabación del usuario (lo mejor); TTS con el MCP de ElevenLabs si está conectado; `say -v Monica` solo para borradores | Fuente de audio con transcripción: los textos se anclan a sus palabras |
| música | Base musical | síntesis con numpy en la rejilla de beats según `musica.genero` del DS (ver `skills/promo-codigo/references/motor.md`), `music_bed.py` o un archivo con licencia (Epidemic, Artlist, Uppbeat) | `musica.archivo`; el compilador hace el ducking bajo la voz |

## Cómo se usa cada motor

**pantalla**
- **Terminal**: un `.tape` con comandos reales contra el sistema real y un `rc.sh` con un prompt mínimo, con la fuente y el tema del DS. Si quieres enseñar el arranque en caliente, haz antes un primer arranque y dilo en el informe.
- **Apps**: graba a 2x, sin notificaciones ni datos personales, con el cursor visible.
- **Medir**: el diff de filas por fotograma dice cuándo sale cada resultado, para que caiga en un beat.

**codigo**
- La escena es una función del tiempo, con la línea de tiempo en beats compartida con el audio.
- Revisa con fotogramas fijos en los tiempos clave antes de hacer el render completo: la escena (contrato de `promo-codigo/references/motor.md`) acepta los segundos como último argumento (`… 0.6,9.2`) y escriben un PNG por tiempo.
- Usa las fuentes y la paleta del DS (`fuentes.*.archivo`, `paleta`), no valores sueltos.

**3d** (Blender)
- La escena es un script de bpy que solo construye el contenido. `motor_blender.py` prepara el lienzo, los fps y el rango, y fija la gestión de color en «Standard» para que los hex del DS salgan tal cual. A la escena le pasa `fc`, con `fc.color(rol)`, `fc.fuente(rol)`, `fc.material(rol)`, `fc.fondo()`, `fc.f(segundos)`, `fc.ease()` y `fc.p` (los `--param`).
- Plantilla: `$S/blender/titular.py` (`$S/blender/fcblender.py` es el puente interno que da `fc`; no se toca). Cópiala junto al guion y cámbiala por escena.
- Primero `--fotogramas 1,48,96 --escala 0.5`, que da una hoja para revisar; después el render completo.
- Cycles con vidrio necesita muestras (64–128) y tarda: mide un fotograma antes de lanzar la animación y lánzala en segundo plano.

```bash
python3 $S/motor_blender.py escenas/titulo.py --ds DS --out escenas/titulo.mp4 \
    --segundos 3 [--fotogramas 1,30,90 --escala 0.5] [--motor cycles --muestras 96] --param texto=KINDLING
```

**ia** (solo con permiso)
- **Siempre de imagen a video**, desde un fotograma propio o del DS. Con solo texto se obtiene la estética media del modelo.
- **Prompt de director de fotografía**: lente, luz y un movimiento de cámara motivado. Planos de 2–4 s y 2–3 tomas de cada uno.
- **Nunca** para la interfaz del producto, ni para personas reales, ni para logos.
- **Pasa por el grade del DS**: LUT al 50–70 % y grano.
- **Anota en el informe** el modelo, el prompt y la licencia de lo generado.

**voz**
- El guion fija el texto. Mide las palabras por segundo antes de generar.
- Normaliza la voz a −16 LUFS antes de mezclar (`procesar_voz.sh`).

**música**
- **Elige un micro-género con BPM** que encaje con el tipo:
  - promo: UK garage, breakbeat lo-fi o electrónica con pulsos;
  - tutorial: ambiente sin percusión fuerte;
  - reel de evento: la energía del DS.
- **IA musical**: Suno da buen sonido pero tiene riesgo de licencia; ElevenLabs Music y Lyria tienen licencias más claras. Nunca nombres de artistas.

## Ensamblado

`WORK` es la carpeta de trabajo `W` del resto de skills (sin evento, el análisis puede ir en `WORK/analisis`; con evento, usa la caché única `<evento>/06 - FilmCraft/analisis/`). Entrecomilla las rutas si llevan espacios.

```bash
python3 $S/analyze_media.py --out WORK/analisis --videos escenas/*.mp4 camara/*.mp4 [--sin-vision]
# plan.json: un bloque por escena (src = archivo de la escena); musica.archivo si la música va aparte
python3 $S/plan_compile.py WORK/plan.json --analisis WORK/analisis --out WORK/compiled.json
python3 $S/apply_plan.py WORK/compiled.json --headless --out WORK/video.fcproj --work WORK
python3 $S/verify.py …   # ver skills/editor-filmcraft/references/verificacion.md del plugin
```

En vivo (`--live`) se ve en la app abierta, bloque a bloque, con las puertas de `montaje-asistido`.
