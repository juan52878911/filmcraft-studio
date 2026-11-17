# Changelog

Formato: una sección por versión, de la más nueva a la más vieja.

## 0.4.0 — sin publicar

- **Gramática `pegatina@1`** (reel con presentador y rótulos tipo pegatina, medida fotograma a fotograma; `scripts/pegatina.py` y `skills/design-system-video/references/pegatina.md`):
  - cajas inclinadas con sombra dura;
  - entradas `golpe`, `desliza`, `caida`, `pop` y `escribe` (el kicker se escribe con un Crop), y salida en fundido;
  - el rótulo entra antes de su palabra y vive hasta el final del bloque;
  - subtítulos de 1-3 palabras con la palabra clave resaltada (cifras, nombres propios y la lista `resaltar` del plan);
  - tarjetas compuestas (`ponente`, `fecha`, `qr`, `logo`, `flecha`) dibujadas a la escala del lienzo, con reparto de pistas para que no se pisen;
  - DS sin música (`musica.ninguna`) y sin barra de marca (`marca.barra` vacía).

  Esquemas y `cine validar-ds` al día.
- **Arreglos**:
  - el inicio de los textos se redondea a fotogramas antes de medir lo que queda del bloque, y ya no se adelantan por un fotograma de más;
  - `apply_plan --work` crea la carpeta si no existe.

- **Motor determinista `cine`** (Rust, `motor/`, lanzador `bin/cine`): `validar-ds` (sustituye a `ds_validate.py`, que se borra), `elegir-ds` (sustituye al ranking de `brief_infer.match_ds`, con ΔE en OKLab), `medir-video`, `criterios` (comprueba los criterios de la biblia y da la tabla del informe), `puntuar` (6 ejes del crítico con reglas fijas), `nota` (veredicto, 5 arreglos y Mejora/Regresión/Empate) y `ab`. Se compila con `nix build` (flake en la raíz), `motor/compilar.sh` o el workflow `motor`; los binarios van en `bin/<so>-<arq>/` y no se suben.
- **Un solo crítico con IA**: `critico` y `critico-estilo` se funden en `critico-juicio`, que solo juzga historia, copy, originalidad y los criterios marcados `juicio`, con las medidas como evidencia y techo. A/B a ciegas solo si la nota es ambigua; un bloqueante nuevo es Regresión.
- **Criterios de la biblia** con `medida` y `juicio` (esquema ampliado; los `{id, que, como}` siguen valiendo). Detalle, paridad y tiempos en `AUDITORIA.md`.

## 0.3.0 — sin publicar

- **Uso en lenguaje natural**: «reel/resumen de una charla o evento» entra directo a `montaje-headless`/`montaje-asistido` (`director-video` lo desvía sin biblia larga); skill nueva `imagen-a-video` para animar una sola imagen; `analizar`, `nota` y `entregar` dejan de llevar `disable-model-invocation` y las skills los siguen por su ruta cuando el usuario lo pide en texto. `herramientas.py --doctor --para promo` (también `codigo`/`pantalla`): FilmCraft pasa a recomendado y se comprueba VHS. Promo: escena mínima antes de los fotogramas de la preproducción y «¿exprés o completo?» como primera pregunta. `/editar`: el modo se pregunta al principio (fija `W`) y el asistido hace G0 antes de G3. Avisos de tiempo de análisis en material largo y de que el ranking de DS sin `--ruta` no pasa de 0,5.
- **Preproducción**: skill `preproduccion` (invocable como `/filmcraft-studio:preproduccion`) con preguntas por rondas, lectura de referencias (`referencias.py`), design system con fotogramas para elegir, crítica de originalidad con el agente nuevo `critico-estilo` y biblia aprobada con criterios de aceptación.
- **Motores y herramientas**: `herramientas.py` (qué hay instalado y, con `--doctor`, qué falta) y el comando `/filmcraft-studio:doctor`; motor 3D con Blender sin interfaz (`motor_blender.py`, `scripts/blender/`).
- **Promos**: DS `promo-gradient-map` (termo@1), `promo-chispa` y `promo-tres-fases`.
- **Sin promos de prueba en el plugin**: se quita la carpeta `promo/` (los promos de kindling v0.20, Chispa y filmcraft-studio 0.3 eran pruebas). Lo útil queda en `skills/promo-codigo/references/motor.md`, el esqueleto para escribir el motor de una promo nueva desde cero (línea de tiempo en beats, grabación VHS y su medida, contrato de la escena y del audio, `render.sh`, fase 3D y ensamblado en FilmCraft). Los DS `promo-*` ya no apuntan a ese código: fuera `musica.generador` y `promo.ejemplo` (también del esquema); el género musical vive en `musica.genero`. Los tests de esquemas usan copias en `tests/fixtures/`.
- **Icono** del plugin (`.claude-plugin/icon.png`, fuente en `docs/img/icono.svg`) y README al día: empieza aquí, doctor con `--para`, modo exprés, esquemas y tests.
- **Arreglos**: frontmatter YAML estricto en todos los comandos; los comandos solo los lanza el usuario (`disable-model-invocation`); se quita el comando `preproduccion`, que chocaba con la skill del mismo nombre; caché de análisis única por evento (`06 - FilmCraft/analisis/`); `/nota` vale también para promos y anota los cambios en la biblia; el MCP respeta `FILMCRAFT_CLI` y `FILMCRAFT_PORT`; `requirements.txt`; `AGENTS.md` para otros agentes.

## 0.2.0 — 2026-11-03

- **Director de video generalista**: skill `director-video` y comando `/filmcraft-studio:video` (tipos de video, `guion.json` por escenas con hechos y fuentes, motores y listón profesional).
- **Render por código**: skill `promo-codigo` y comando `/filmcraft-studio:promo` (VHS + Python + ffmpeg), con lo aprendido.
- DS `promo-brasa-escarcha`, `promo-blueprint` y `promo-riso`, y un promo de ejemplo de kindling v0.20 con su ensamblado headless en FilmCraft (sacado del plugin en 0.3.0).
- Arreglos del flujo: la música solo se agacha en bloques con voz; `ds_studio crear` hereda los SFX del DS base; colores de texto ajustados contra el fondo del lienzo.

## 0.1.0 — 2026-10-19

- Primera versión: montaje de material de eventos en FilmCraft a partir de un design system de video y un brief, en modo headless o asistido.
- Análisis con caché (whisper.cpp, silencios, energía, barridos de cámara, caras con Apple Vision), `plan.json` como EDL de intención, compilador determinista, aplicación por fases y verificación con hojas de fotogramas, loudness y crítico.
- DS precargado `sbg-brutalista-s5` y ciclo crear → vista previa → modificar → aprobar.
