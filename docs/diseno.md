# filmcraft-studio — diseño (v0)

Plugin de Claude Code para editar video en FilmCraft a partir de un **design system de video** (DS) y un **brief de intenciones**. Funciona en dos modos: **headless** (autónomo, sobre copias) y **asistido** (en la app abierta, con puertas de confirmación). Diseñado con la skill experta `editor-filmcraft`, que se integra en el plugin.

## Idea central

DS + brief → `plan.json`: una EDL de intención, en segundos y por roles. Un compilador determinista lo traduce a comandos de FilmCraft. Un único motor (`fcengine.py`) los aplica en vivo (socket 9876) o en headless (`filmcraft-cli --project … mcp`, o `run` por fases). Los dos modos comparten todo salvo dónde se detienen a confirmar.

## Design system (`design-systems/<id>/ds.json` + `assets/`)

- **Gramática** (reglas reutilizables, por ejemplo `brutalista@1`): roles de texto, animaciones, colocación en zonas libres, continuidad, transiciones (prefiere el barrido de cámara), mapa de SFX, música, grade, objetivos de audio, estructura y ritmo.
- **Piel** (cambia por evento): paleta, fuentes, marca y fondos y mattes generados.
- **Ejemplo completo:** `sbg-brutalista-s5`, la paleta del flyer de la Sesión 5. Las reglas y los tamaños salen de `editor-filmcraft/references/estilo-brutalista.md`.
- **`match`** (rutas, flyer y similitud de color) permite elegir el DS de forma automática.

## Brief

Campos:
- `objetivo`
- `publico`
- `plataforma`
- `duracion_s`
- `tono`
- `obligatorios`
- `evitar`
- `cta`
- `ds`
- `idioma`

Cada uno lleva su `origen` (dado, inferido o defecto) y su `confianza`.

Se infieren solos: la plataforma (por el aspecto), la duración, el tono (por la energía del audio), los obligatorios candidatos (de la transcripción: números, premios, nombres), el DS y el CTA.

En modo asistido se pregunta lo que tenga poca confianza. En headless se usa el valor por defecto y queda marcado en el informe.

## Componentes del plugin

**Skills**
- `editor-filmcraft`: el oficio y las reglas duras; existe y se mueve al plugin.
- `design-system-video`
- `brief-video`
- `montaje-headless`
- `montaje-asistido`

**Comandos** (`/filmcraft-studio:…`)
- `ds-crear`
- `ds-preview`
- `ds-listar`
- `brief`
- `analizar`
- `montar` (`--modo headless|asistido`)
- `verificar`
- `nota`
- `entregar`

**Subagentes**
- `analista-material`: momentos con peso y cita.
- `director-montaje`: elige el DS, completa el brief y escribe `plan.json`.
- `critico`: veredicto y los 5 arreglos a hacer primero.

**Scripts**
- `fcengine.py`
- `analyze_media.py`: transcripción, silencios, movimiento de cámara y caras con YuNet, con caché.
- `freezones.py`
- `ds_from_image.py`
- `ds_assets.py`
- `ds_preview.py`
- `ds_validate.py`
- `plan_compile.py`
- `apply_plan.py`
- `music_bed.py`
- `verify.py`
- `report.py`

Se reutilizan `fclib`, `transcribe_fc`, `camera_motion`, `render_sheet`, los `convert_*`, `word_reveal`, `gen_bgs` y `synth_bed`.

## Pipeline headless

0. **Preflight:** CLI, app abierta, fuentes y medios offline.
1. **Inventario:** carpetas 01 crudo, 02 `_voz`, 03 fotos, 04 gráfica y el flyer.
2. **Análisis** con caché, más `analista-material`.
3. **D1:** brief.
4. **D2:** DS (registro o piel derivada del flyer), assets y validación.
5. **D3:** `plan.json`. Primero la columna de audio, cortes en límites de palabra, obligatorios cubiertos y transiciones con barrido de cámara primero.
6. **Zonas libres** por pop-up.
7. **Proyecto nuevo** en `06 - FilmCraft/auto/…`. Nunca se toca el `.fcproj` existente.
8. **Aplicar por fases** A–E: cortes y continuidad; audio y SFX; textos; transiciones; grade.
9. **Verificar** (como máximo 3 pasadas): hojas con y sin textos, texto frente a caras, keyframes, cortes en palabra, `.wav` con LUFS y pico real, duración. Termina con el `critico`.
10. **`informe.md`** con las decisiones D1–D3, las evidencias y las preguntas pendientes. Sin export salvo con `entregar`.

## Flujo de entrada conversacional (v0.1, pedido por Juan; manda sobre el orden anterior)

El punto de entrada es `/filmcraft-studio:editar <carpeta>`, o pedirlo en lenguaje natural. El orden es **estilo → intenciones → edición**:

1. **¿Qué te gustaría ver?** Pregunta abierta corta sobre el video que el usuario imagina.
2. **Elegir el estilo.**
   - Si hay design systems en el catálogo, muéstralos como opciones: nombre, descripción en una línea y miniatura de vista previa. Suma "crear uno nuevo".
   - Si no hay ninguno, o el usuario elige crear: que **describa** cómo lo quiere (también vale un flyer, un logo o una referencia). El plugin propone un DS (piel + gramática base) y genera la **vista previa** (`ds_preview`: fondos, mattes, cada rol de texto sobre un fotograma real del material).
   - **Ciclo de aprobación:** el usuario lo ve y lo aprueba, o pide cambios (colores, tipografía, tamaños, tono de las animaciones). Se itera hasta que lo apruebe.
   - **Al aprobarlo pasa al catálogo** (`${CLAUDE_PLUGIN_DATA}/design-systems/<id>/` o una carpeta de catálogo configurable con `userConfig`) y queda como opción para los siguientes videos. El DS `sbg-brutalista-s5` viene precargado.
3. **Intenciones.** Brief con objetivo, público, plataforma, duración, tono, obligatorios y llamada a la acción. Se proponen los valores inferidos del material para que el usuario los confirme o cambie.
4. **Edición.** El usuario elige el modo:
   - **asistido:** puertas G3–G7 de abajo;
   - **automático:** pipeline headless con el DS y el brief ya aprobados.

El modo headless puro (sin preguntas) sigue existiendo para lotes o cuando el usuario dice "decide tú". En ese caso se eligen el DS y el brief de forma automática y quedan marcados en el informe.

Esto entra en el MVP: catálogo de DS, creación desde una descripción o un flyer, vista previa y ciclo de aprobación.

## Flujo asistido (puertas)

- **G0:** conectar, guardar y respaldar.
- **G1:** DS elegido del catálogo, o creado y aprobado con su vista previa (ver "Flujo de entrada").
- **G2:** brief de intenciones.
- **G3:** estrategia y tabla de bloques.
- **G4:** cada bloque se aplica en vivo; guardar, hoja de fotogramas, OK o notas.
- **G5:** pasadas globales (subtítulos, música, grade, loudness).
- **G6:** verificación y crítico.
- **G7:** export solo si se pide.

## Riesgos de FilmCraft y mitigación

- **Base de tiempo de los keyframes:** se calcula solo en `fcengine.kf()` (`time` = ticks de secuencia, `mediaTime` = `source_in + desfase × speed`) y se relee el JSON después.
- **Pistas:** se resuelven por nombre y se pasan como enteros a `graphics.newText`.
- **4K con rotación:** `scaleToFrameSize`.
- **fps mezclados** (60, 59,94 y 56 VFR): los fotogramas salen de los fps de la secuencia; nunca se fija 60.
- **App abierta:** en headless solo se trabaja sobre rutas nuevas; en vivo solo por socket.
- **Export lento:** para verificar, hojas y `.wav`; vista previa a 0,5; el final en segundo plano.

## Estructura de repositorio y marketplace

```
filmcraft-studio/                      ← marketplace local
├── .claude-plugin/marketplace.json    {"name":"juan-local","owner":{"name":"Juan"},"plugins":[{"name":"filmcraft-studio","source":"./plugins/filmcraft-studio"}]}
├── docs/diseno.md
└── plugins/filmcraft-studio/
    ├── .claude-plugin/plugin.json
    ├── .mcp.json                      filmcraft: ~/.local/bin/filmcraft-cli mcp --bridge 127.0.0.1:9876 (ruta absoluta)
    ├── skills/{editor-filmcraft,design-system-video,brief-video,montaje-headless,montaje-asistido}/
    ├── commands/*.md
    ├── agents/{analista-material,director-montaje,critico}.md
    ├── scripts/*.py
    └── design-systems/sbg-brutalista-s5/{ds.json,assets/}
```

Instalación:

```bash
claude plugin validate .
claude plugin marketplace add .
claude plugin install filmcraft-studio@juan-local --scope user
```

Si `claude` es una función de shell, usa `~/.local/bin/claude`. Tras editar, `/reload-plugins`.

Trampas:
- Usa `${CLAUDE_PLUGIN_ROOT}` y `${CLAUDE_SKILL_DIR}` en los cuerpos; no están en el entorno de Bash.
- El estado va en `${CLAUDE_PLUGIN_DATA}`.
- Ningún nombre puede empezar por `claude-`.
- `~/.claude/skills/editor-filmcraft` quedaría duplicada: retirarla o renombrarla al instalar.
- Herramientas MCP del plugin: `mcp__plugin_filmcraft-studio_filmcraft__*`.

## MVP de esta iteración

- **Headless completo** con el DS `sbg-brutalista-s5` escrito a mano, sobre el material del Reto. Sale en `06 - FilmCraft/auto/` y se compara con el reel manual: hojas, curva de LUFS, número de cortes y obligatorios cubiertos.
- **Asistido básico:** puertas G1–G4 por socket en la app.
- **Flujo de entrada `editar`** (estilo → intenciones → edición), con **catálogo de DS**. Crear desde una **descripción** o un flyer (paleta por k-means, assets y vista previa), con un ciclo de aprobar o modificar; al aprobarlo, el DS pasa al catálogo.

Después:
- registro de DS y otras gramáticas;
- plantillas `.fcgt` y presets de efectos;
- reencuadre para varias plataformas;
- biblioteca musical;
- `applyMatch` con scopes;
- aprender del diff entre el montaje automático y la versión final.
