# Herramientas open source por necesidad

`python3 $S/herramientas.py [--para motor]` (`S` viene del SKILL.md de `director-video`) dice qué hay instalado aquí, con la versión y cómo instalar lo que falta. Ofrece solo lo instalado. Lo demás se instala con el permiso del usuario.

Para todas las herramientas rige el mismo **contrato de salida**:
- archivos al lienzo y los fps del DS;
- video H.264 sin audio, o PNG con alfa si va encima de otra cosa;
- la música y la voz van aparte, en la rejilla de beats;
- todo termina como fuente de FilmCraft.

Licencias: revísalas al usar cada herramienta. Las de los modelos de IA cambian con frecuencia.

| Necesidad | Herramienta | Motor | Sin interfaz | Notas |
|---|---|---|---|---|
| Montaje, subtítulos, color, mezcla, ensamblado | **FilmCraft** | todos | `apply_plan.py --headless`, MCP `filmcraft` | El destino de todo. Apache-2.0 |
| 3D: titulares extruidos, productos, vidrio, partículas, cámara física | **Blender** | `3d` | `motor_blender.py ESCENA.py --ds DS` | GPL. Eevee para rápido; Cycles + Metal para vidrio y refracción |
| 2D con Grease Pencil, compositor por nodos | **Blender** | `2d` | igual, desde la escena bpy | El compositor también sirve para desenfoque, glow y máscaras |
| Gráficos, tipografía cinética, efectos por píxel, estilos de impresión | **Python (PIL + numpy, OpenCV)** | `codigo` | esqueleto en `skills/promo-codigo/references/motor.md` | El más controlable; la cámara sobre grabaciones |
| Tarjetas, tipografía y bloques de video en YAML (4:5, 9:16) con export FCPXML/EDL | **bloques** (si está instalado) | `codigo` | `bloques render\|fotograma\|hoja\|validar` | Escribe el YAML (su `GUIA-IA.md`) en vez de un script. Salida MP4 + WAV aparte |
| Diagramas, matemáticas, explicaciones | **Manim** | `codigo` | `manim -qh escena.py Clase` | MIT. Fondo y colores desde la paleta del DS |
| Motion design con código TypeScript | **Motion Canvas** | `codigo` | render desde su editor en el navegador | MIT. Bueno para animaciones de UI esquemática (no de producto real) |
| Composiciones HTML/CSS + GSAP a MP4 | **HyperFrames** | `codigo` | su CLI con `npx` | Webs y tarjetas. Remotion es una alternativa *source-available*, con licencia de empresa a partir de 4 personas |
| Animación vectorial con huesos | **Synfig** | `2d` | `synfig archivo.sifz -t png -o f.png` | GPL |
| Lottie y vectores animados | **Glaxnimate** | `2d` | exporta Lottie/MP4 | GPL. Lottie también sirve para la web |
| SVG a PNG, ilustración | **Inkscape** | `2d` | `inkscape in.svg -o out.png -w 1080` | GPL |
| Animación cuadro a cuadro pintada | **Krita** | `2d` | exporta secuencia | GPL. Para texturas y fondos pintados |
| Operaciones de imagen por lotes | **ImageMagick** | `codigo` | `magick …` | Apache-2.0 |
| Terminal real | **VHS** | `pantalla` | `vhs term.tape` | MIT. Reproducible y con el tema del DS |
| Pantalla, app, cámara, escenas compuestas | **OBS Studio** | `pantalla`, `camara` | — (manual) | GPL. `screencapture -v` para algo rápido en macOS |
| Montaje alternativo | **Kdenlive / MLT** | montaje | `melt proyecto.mlt -consumer avformat:out.mp4` | GPL. Si el usuario lo prefiere a FilmCraft |
| Composición por nodos | **Natron** | montaje | `NatronRenderer` | GPL; desarrollo lento. El compositor de Blender suele bastar |
| Codificar, escalar, recortar, filtros, loudness | **ffmpeg** | todos | `ffmpeg …` | `ebur128` para medir, `loudnorm` + `alimiter` para el máster |
| Transcripción con tiempos por palabra | **whisper.cpp** | voz | `whisper-cli` (lo usa `analyze_media.py`) | MIT |
| Voz TTS local | **Kokoro** / **Piper** | voz | API de Python (Kokoro), CLI `piper` | Kokoro tiene pesos Apache-2.0. Piper: revisa la licencia de cada voz |
| Música y SFX sintetizados | **numpy** (`promo_sfx.py`, scripts de audio), **SuperCollider** | música | scripts | Sin licencias. Cuadra con la rejilla al fotograma |
| Secuenciador o edición a mano | **LMMS**, **Audacity** | música | — | GPL |
| IA local de imagen y video | **ComfyUI** + Wan 2.x / LTX-Video | `ia` | API de ComfyUI | Solo con permiso y desde imagen propia; revisa la licencia de cada modelo |

## Elegir

- **Lo real primero**: si existe la grabación o el dato, se usa (`pantalla`, `camara`). Lo dibujado explica lo que no se puede grabar.
- **Un motor por escena**, el más simple que dé el resultado. El 3D solo cuando la materia de la dirección lo pide (vidrio, volumen, luz física), no para decorar.
- **Revisión fija antes del render completo**: cada motor tiene su forma de sacar fotogramas sueltos:
  - `motor_blender.py --fotogramas`;
  - `manim -s`;
  - `render_frame` de FilmCraft;
  - una función `frame(t)` en los scripts de código.
- **Igualar motores**: el grade, el grano y la tipografía del DS se aplican a todos. El paso final en FilmCraft (Lumetri y LUT del DS) los cose. Si un motor no carga la tipografía del DS, compón ese texto por código encima o usa la variante `.ttf`/`.otf` de la misma familia.
