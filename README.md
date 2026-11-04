<p align="center">
  <img src="docs/img/banner.png" alt="filmcraft-studio: design systems de video para montar en FilmCraft con Claude Code" width="100%">
</p>

<p align="center">
  <b>Plugin de Claude Code que monta videos en <a href="https://github.com/storytold/filmcraft">FilmCraft</a> a partir de un design system de video y un brief de intenciones.</b><br>
  Solo (headless, de punta a punta) o contigo al lado (asistido, puerta a puerta en la app).
</p>

<p align="center">
  <img alt="Claude Code plugin" src="https://img.shields.io/badge/Claude%20Code-plugin-FF52EA?style=flat-square&labelColor=161D27">
  <img alt="FilmCraft 0.8+" src="https://img.shields.io/badge/FilmCraft-0.8%2B-FF9900?style=flat-square&labelColor=161D27">
  <img alt="macOS" src="https://img.shields.io/badge/macOS-Apple%20Vision-AD5CFF?style=flat-square&labelColor=161D27">
  <img alt="MIT" src="https://img.shields.io/badge/licencia-MIT-FFFFFF?style=flat-square&labelColor=161D27">
</p>

---

## Qué hace

Le das una carpeta con el material crudo de un evento (videos, voz procesada, fotos y flyer). El plugin:

1. **Escucha y mira** el material: transcribe palabra por palabra con whisper.cpp, mide silencios y energía, detecta los barridos de cámara y localiza caras y personas con Apple Vision. Todo queda en caché.
2. **Elige o crea el estilo**, un *design system de video* (paleta, tipografías, roles de texto, animaciones, transiciones, SFX, música y grade). Lo puede sacar de un flyer por k-means o de una descripción, con vista previa y un ciclo de aprobación.
3. **Completa el brief**: objetivo, público, duración, tono, obligatorios y CTA. Cada campo lleva su origen y su confianza.
4. **Escribe un `plan.json`**, una EDL de *intención* en segundos de la fuente y por roles. Lo hace un subagente director a partir de los momentos que encuentra un subagente analista.
5. **Compila el plan de forma determinista**:
   - bordes ajustados a límite de palabra;
   - tiempos exactos de fotograma;
   - pop-ups colocados en **zonas libres** que no tapan a la gente;
   - subtítulos, barra de marca, SFX ligados a eventos, música con ducking y limitador en el máster.
6. **Lo aplica a FilmCraft** por fases: cortes, audio, textos, transiciones y grade. En headless trabaja sobre un proyecto nuevo; en vivo, por el canal de control de la app abierta.
7. **Verifica antes de enseñar**:
   - hojas de fotogramas con textos y sin ellos, con las caras detectadas;
   - keyframes y cortes en palabra;
   - loudness y pico de la mezcla `.wav`.

   Después pasa un **crítico** y escribe un `informe.md`.

No exporta video salvo que se lo pidas.

## Resultado real

Prueba headless con el material del **#RetoCertEAN · Sesión 5** (AWS Student Builder Group, Universidad EAN). Son 9 grabaciones 4K de un Pixel 8 Pro, comparadas con el reel que se montó a mano:

| | Automático | Manual |
|---|---|---|
| Duración | 53,6 s | 56,7 s |
| Cortes | 23 | 22 |
| Loudness | −14,5 LUFS | −14,7 LUFS |
| Pico | −1,5 dBFS | −0,1 dBFS |
| Obligatorios cubiertos | 5/5 | 5/5 |

- Ningún corte cae dentro de una palabra.
- Los 241 keyframes están dentro de su rango.
- De 22 pop-ups, ninguno tapa una cara.

Compilar y aplicar el plan tarda unos 4 s; la verificación, menos de 1 min. El veredicto del crítico fue *publicable con arreglos*.

<p align="center">
  <img src="plugins/filmcraft-studio/design-systems/sbg-brutalista-s5/preview.png" alt="Vista previa del design system sbg-brutalista-s5: maquetas y renders reales de FilmCraft" width="100%">
  <br><sub>Vista previa del DS precargado <code>sbg-brutalista-s5</code>: maquetas PIL, dos renders reales de FilmCraft, el flyer de referencia y la paleta con sus contrastes.</sub>
</p>

## Director de video: cualquier tipo de video

Desde la 0.2, la entrada general es `/filmcraft-studio:video <qué quieres>` (skill `director-video`). Sirve para un promo de repo o de una release, un lanzamiento, una demo, un tutorial, un explainer, un reel de evento, una entrevista, un short, un pitch, un changelog o un loop para el README. Todos siguen la misma cadena:

1. **Brief y tipo.** Cada tipo trae su plantilla de escenas, su duración y su formato ([`tipos.md`](plugins/filmcraft-studio/skills/director-video/references/tipos.md)).
2. **Hechos con fuente y `guion.json`.** Escenas con objetivo, texto en pantalla, voz, motor y beats ([`guion.md`](plugins/filmcraft-studio/skills/director-video/references/guion.md)).
3. **Design system.** Del catálogo o nuevo, con fotogramas fijos para elegir.
4. **Producción por escena**, cada una con su motor ([`motores.md`](plugins/filmcraft-studio/skills/director-video/references/motores.md)):
   - `camara`: material grabado, con análisis;
   - `codigo`: render reproducible con Python, Remotion, HyperFrames o Manim;
   - `pantalla`: VHS, Screen Studio o Cap;
   - `ia`: solo planos de relleno, desde imagen propia;
   - `foto`, `tarjeta`, voz y música.
5. **Ensamblado en FilmCraft.** Todas las escenas entran como fuentes del mismo `plan.json`; FilmCraft pone los subtítulos, la marca, los SFX, la música con ducking y el grade del DS.
6. **Verificación** con el listón profesional ([`reglas.md`](plugins/filmcraft-studio/skills/director-video/references/reglas.md)), `verify.py` y el agente crítico.

### Promos por código: kindling v0.20 en tres estilos

Los primeros videos hechos con el motor `codigo` (skill `promo-codigo`):
- la terminal es una **grabación real** con VHS, no una UI inventada;
- cada fotograma se dibuja con Python sobre una rejilla de 134 BPM;
- la música y los SFX se sintetizan en esa misma rejilla, sin licencias;
- el máster va a −14 LUFS.

Cada estilo es un design system del catálogo, con su gramática, su kit de SFX y sus fondos. El código completo y reproducible está en [`promo/kindling-v0.20/`](plugins/filmcraft-studio/promo/kindling-v0.20) (`./render.sh brasa|blueprint|riso|riso_v`).

**`promo-brasa-escarcha`** · temperatura@1 · 16:9 · UK garage. Lo que corre es brasa; lo congelado se vuelve escarcha, y la cámara y el grano se paran. [Ver video](docs/video/promo-brasa-escarcha.mp4)

<img src="docs/img/promo/promo-brasa-escarcha.png" alt="Fotogramas del promo de kindling en estilo brasa y escarcha" width="100%">

**`promo-blueprint`** · plano@1 · 16:9 · electrónica ambiental con lápiz y sellos. Un plano técnico que se dibuja solo, con cotas, anotaciones numeradas y rayado de sección al congelar. [Ver video](docs/video/promo-blueprint.mp4)

<img src="docs/img/promo/promo-blueprint.png" alt="Fotogramas del promo de kindling en estilo blueprint" width="100%">

**`promo-riso`** · riso@1 · 9:16 y 16:9 · breakbeat lo-fi. Dos tintas multiplicadas sobre papel; congelado = una sola tinta y la cinta frena. [Ver vertical](docs/video/promo-riso-9x16.mp4) · [ver 16:9](docs/video/promo-riso-16x9.mp4)

<img src="docs/img/promo/promo-riso-9x16.png" alt="Fotogramas del promo vertical de kindling en risografía" width="100%">

**Ensamblado en FilmCraft.** Prueba headless con [`promo/kindling-v0.20/ensamblado/`](plugins/filmcraft-studio/promo/kindling-v0.20/ensamblado):
- el gancho, renderizado en brasa, y la demo, renderizada en blueprint, entran como fuentes;
- el cierre es la tarjeta del DS;
- la música es la mezcla del motor de código.

Resultado: 15,5 s, 0 choques de texto, 0 cortes dentro de palabra y 0 keyframes fuera de rango. Mezcla a −17,9 LUFS con pico de −1,3 dBTP: queda por debajo del objetivo de −14 y conviene normalizar al entregar.

<img src="docs/img/promo/ensamblado-filmcraft.jpg" alt="Hoja de fotogramas renderizada por FilmCraft del ensamblado de escenas por código" width="100%">

Lo aprendido al hacerlos está en [`aprendido.md`](plugins/filmcraft-studio/skills/promo-codigo/references/aprendido.md): por qué un promo se ve genérico, qué funciona, música y licencias, cómo verificar las afirmaciones y los errores que detecta la hoja de fotogramas.

## Cómo funciona

```mermaid
flowchart LR
  M[Material crudo] --> A[analyze_media<br/>whisper · silencios · barridos · caras]
  F[Flyer / descripción] --> DS[Design system<br/>ds_studio · ds_preview]
  A --> B[brief_infer]
  DS --> B
  A --> D{{director-montaje}}
  B --> D
  D --> P[plan.json<br/>EDL de intención]
  P --> C[plan_compile<br/>palabras · fotogramas · zonas libres]
  C --> E[apply_plan<br/>fases A–E]
  E -->|headless| H[(proyecto nuevo .fcproj)]
  E -->|en vivo| L[FilmCraft abierto<br/>socket 9876]
  H --> V[verify · critico · report]
  L --> V
```

Un solo motor (`scripts/fcengine.py`) sirve para los dos modos. En headless es una sesión persistente de `filmcraft-cli mcp` que devuelve los ids entre comandos. En vivo usa el canal de control JSON por líneas de la app.

## Instalación

Requisitos (macOS):

- [FilmCraft](https://github.com/storytold/filmcraft) 0.8 o superior, con `filmcraft-cli` en `~/.local/bin/`.
- `ffmpeg` y `whisper-cpp` (`brew install ffmpeg whisper-cpp`), más un modelo ggml. Por defecto se usa `ggml-medium.bin`; indica otro con `FILMCRAFT_WHISPER_MODEL`.
- Python 3.11+ con `pillow`, `numpy` y `opencv-python`.
- Xcode Command Line Tools, para compilar `swiftc` y el detector de caras de Apple Vision; no descarga modelos.
- Las fuentes del DS que uses (el precargado pide IosevkaTerm Nerd Font Mono y Menlo).

En Claude Code:

```text
/plugin marketplace add juan52878911/filmcraft-studio
/plugin install filmcraft-studio@juan-local
```

O desde la terminal, con un clon local:

```bash
claude plugin marketplace add ./filmcraft-studio
claude plugin install filmcraft-studio@juan-local --scope user
```

## Uso

| Comando | Para qué |
|---|---|
| `/filmcraft-studio:video <qué video quieres>` | **Entrada general.** Brief → tipo → guion → DS → producción por motores → ensamblado y verificación en FilmCraft |
| `/filmcraft-studio:promo <repo>` | Promo de un repo o de su última versión, renderizado por código con un DS `promo-*` |
| `/filmcraft-studio:editar <carpeta>` | **Montaje de material grabado.** Pregunta qué quieres ver y sigue el orden estilo → intenciones → edición (asistida o automática) |
| `/filmcraft-studio:montar <carpeta> --modo headless` | De punta a punta y sin preguntas. Termina con `informe.md` |
| `/filmcraft-studio:montar <carpeta> --modo asistido` | En la app abierta, con puertas: G1 estilo, G2 brief, G3 estrategia, G4 cada bloque en vivo |
| `/filmcraft-studio:ds-crear <descripción o flyer>` | Crea un design system con vista previa y ciclo de aprobar o modificar |
| `/filmcraft-studio:ds-listar` | Catálogo de estilos con miniaturas |
| `/filmcraft-studio:analizar`, `brief`, `verificar`, `nota`, `entregar` | Pasos sueltos: análisis, brief, verificación, aplicar una nota y exportar (solo si lo pides) |

También vale pedirlo en lenguaje natural, por ejemplo: «edita el reel del evento con el estilo del flyer».

## Qué trae

```
plugins/filmcraft-studio/
├── skills/
│   ├── director-video/        entrada general: tipos de video, guion por escenas, motores, listón profesional
│   ├── promo-codigo/          motor de render por código: gramáticas de promo y lo aprendido
│   ├── editor-filmcraft/      el oficio: criterio de montaje, color, audio, transiciones con la cámara, reglas duras
│   ├── design-system-video/   catálogo y ciclo crear → vista previa → modificar → aprobar
│   ├── brief-video/           intenciones con origen y confianza
│   ├── montaje-headless/      pipeline autónomo y formato de plan.json
│   └── montaje-asistido/      puertas G0–G7 en la app
├── agents/                    analista-material · director-montaje · critico
├── commands/                  video · promo · editar · montar · ds-crear · ds-listar · ds-preview · analizar · brief · verificar · nota · entregar
├── scripts/                   fcengine · fcstyle · plan_compile · apply_plan · verify · report · analyze_media · freezones ·
│                              ds_studio · ds_from_image · ds_assets · ds_preview · ds_validate · music_bed · palmier/…
│                              promo_fondos · promo_sfx · promo_preview
├── promo/kindling-v0.20/      promo de ejemplo en tres estilos (VHS + Python + ffmpeg) y su ensamblado en FilmCraft
└── design-systems/
    ├── sbg-brutalista-s5/     DS de ejemplo completo: fondos, mattes y SFX sintetizados libres de derechos
    ├── promo-brasa-escarcha/  temperatura@1 · 16:9
    ├── promo-blueprint/       plano@1 · 16:9
    └── promo-riso/            riso@1 · 9:16
```

Lo que aprende el plugin sobre las trampas de FilmCraft queda escrito en [`filmcraft-operativa.md`](plugins/filmcraft-studio/skills/editor-filmcraft/references/filmcraft-operativa.md). Algunos ejemplos:

- los keyframes van en ticks de secuencia y la interpolación en tiempo de la fuente;
- las pistas de texto se pasan por índice entero;
- los videos 4K girados necesitan `scaleToFrameSize`;
- los tiempos que caen unos ticks antes del borde de fotograma se bajan al fotograma anterior.

El diseño completo está en [`docs/diseno.md`](docs/diseno.md).

## Créditos

La skill `editor-filmcraft` adapta ideas de tres proyectos MIT: [wonsukchoi/domain-experts](https://github.com/wonsukchoi/domain-experts), [samuelgursky/davinci-resolve-mcp](https://github.com/samuelgursky/davinci-resolve-mcp) y [browser-use/video-use](https://github.com/browser-use/video-use). Las atribuciones completas están en [`NOTICE.md`](plugins/filmcraft-studio/skills/editor-filmcraft/NOTICE.md).

Las recetas propias (estilo brutalista del AWS SBG EAN, gramáticas de promo, transiciones con el movimiento de la cámara, operativa de FilmCraft y scripts) son de Juan Bedoya, escritas junto con Claude.

Licencia [MIT](LICENSE).
