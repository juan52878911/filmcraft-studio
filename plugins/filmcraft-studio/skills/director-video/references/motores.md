# Motores de producción

Cada escena del guion la hace un motor. Todos entregan archivos al **lienzo y los fps del DS** (`lienzo.ancho`, `lienzo.alto`, `lienzo.fps`), y todos terminan como fuentes de FilmCraft: `analyze_media.py` primero y `plan.json` después.

| Motor | Para qué | Herramientas | Entra en FilmCraft como |
|---|---|---|---|
| `camara` | Personas, eventos, entrevistas, B-roll filmado | El material del usuario; voz con `procesar_voz.sh` | Fuente con análisis completo: transcripción, caras, movimiento |
| `pantalla` | Producto real: terminal, app, web | **VHS** (`.tape` reproducible, terminal), **Screen Studio** o **Cap** (app o web, con auto-zoom), `screencapture -v` | Fuente; `--sin-vision`. Mide en qué fotograma pasa cada cosa |
| `codigo` | Gráficos, tipografía cinética, diagramas, cifras, la cámara sobre una grabación, estilos de impresión | Python (PIL + numpy) como en `promo/kindling-v0.20/`. Alternativas: **Remotion** (React; licencia de empresa a partir de 4 personas), **HyperFrames** (HTML + GSAP a MP4, con skills para Claude Code), **Manim** (matemáticas y diagramas) | MP4 sin música (`-an`) y con el texto quemado; la música va aparte, en la rejilla |
| `ia` | 2–4 planos de relleno que no se pueden grabar | Kling 3.0, Veo 3.1, Seedance 2.x, MiniMax-H3, Runway Gen-4.5, Wan / LTX (pesos abiertos) | Fuente como cualquier otra; el grade y el grano del DS la igualan |
| `foto` | Fotos del evento o capturas | — | Bloque `fotos` del plan |
| `tarjeta` | Título, cierre, rótulo de pantalla completa | El compilador, desde `marca` y `fondos` del DS | Bloques `tarjeta`/`titulo`/`cierre` |
| voz | Voz en off | Grabación del usuario (lo mejor); TTS con el MCP de ElevenLabs si está conectado; `say -v Monica` solo para borradores | Fuente de audio con transcripción: los textos se anclan a sus palabras |
| música | Base musical | `musica.generador` del DS (síntesis en la rejilla), `music_bed.py` o un archivo con licencia (Epidemic, Artlist, Uppbeat) | `musica.archivo`; el compilador hace el ducking bajo la voz |

## Cómo se usa cada motor

**pantalla**
- **Terminal**: un `.tape` con comandos reales contra el sistema real y un `rc.sh` con un prompt mínimo, con la fuente y el tema del DS. Si quieres enseñar el arranque en caliente, haz antes un primer arranque y dilo en el informe.
- **Apps**: graba a 2x, sin notificaciones ni datos personales, con el cursor visible.
- **Medir**: el diff de filas por fotograma dice cuándo sale cada resultado, para que caiga en un beat.

**codigo**
- La escena es una función del tiempo, con la línea de tiempo en beats compartida con el audio.
- Revisa con fotogramas fijos en los tiempos clave antes de hacer el render completo.
- Usa las fuentes y la paleta del DS (`fuentes.*.archivo`, `paleta`), no valores sueltos.

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

```bash
S=${CLAUDE_PLUGIN_ROOT}/scripts
python3 $S/analyze_media.py --out WORK/analisis --videos escenas/*.mp4 camara/*.mp4 [--sin-vision]
# plan.json: un bloque por escena (src = archivo de la escena); musica.archivo si la música va aparte
python3 $S/plan_compile.py WORK/plan.json --analisis WORK/analisis --out WORK/compiled.json
python3 $S/apply_plan.py WORK/compiled.json --headless --out WORK/video.fcproj --work WORK
python3 $S/verify.py …   # ver editor-filmcraft/references/verificacion.md
```

En vivo (`--live`) se ve en la app abierta, bloque a bloque, con las puertas de `montaje-asistido`.
