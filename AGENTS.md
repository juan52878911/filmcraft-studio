# filmcraft-studio para agentes

Guía para Codex CLI, opencode, Gemini CLI, Cursor y cualquier agente que no sea Claude Code. En Claude Code no hace falta: el plugin se instala y resuelve las rutas solo (ver `README.md`).

## Qué es

Un director de video: convierte un pedido en preproducción (preguntas, referencias, design system y una biblia aprobada con criterios de aceptación), produce cada escena con el motor adecuado (FilmCraft para material grabado, render por código en Python, Blender, grabación de pantalla, 2D, IA de relleno, voz y música), lo ensambla en [FilmCraft](https://github.com/storytold/filmcraft) y lo verifica contra la biblia. Todo vive en `plugins/filmcraft-studio/`.

## Mapa de skills

Cada skill es un `SKILL.md` con frontmatter estándar y una carpeta `references/` que se lee bajo demanda.

| Pedido | Skill (`plugins/filmcraft-studio/skills/…`) |
|---|---|
| Cualquier video nuevo, sin material grabado o con varios motores | `director-video` (empieza por `preproduccion`) |
| Decidir el estilo y cerrar la biblia antes de producir | `preproduccion` |
| Promo de un repo o de una release, sin cámara | `promo-codigo` (tras `preproduccion`) |
| Carpeta de material grabado, sin preguntas | `montaje-headless` |
| Carpeta de material grabado, en la app, paso a paso | `montaje-asistido` |
| Pulir un `.fcproj` existente: cortes, color, audio, subtítulos | `editor-filmcraft` |
| Ver, crear, cambiar o previsualizar estilos | `design-system-video` |
| Brief de un montaje con material | `brief-video` |
| Reel o resumen de una charla o un evento grabado | `montaje-headless` o `montaje-asistido` (pregunta cuál; sin biblia salvo que la pidan) |
| Animar una sola imagen (un plano) | `imagen-a-video` |

Los comandos de `plugins/filmcraft-studio/commands/*.md` son atajos de Claude Code; su cuerpo es un guion corto que también puedes seguir a mano. `doctor.md` es el diagnóstico de requisitos (`--para camara` con material grabado, `--para promo` en una promo). Las skills remiten a `analizar.md`, `nota.md`, `entregar.md` y `editar.md` para exportar, aplicar notas o conversar un montaje: síguelos cuando el usuario lo pida en texto. Los «agentes» de `plugins/filmcraft-studio/agents/*.md` son prompts de subagente (analista, director de montaje, crítico, crítico de estilo).

## Localizar los scripts sin Claude Code

Las skills escriben `${CLAUDE_PLUGIN_ROOT}/scripts/…`, `${CLAUDE_SKILL_DIR}/references/…` y `${CLAUDE_PLUGIN_DATA}`. Fuera de Claude Code no se sustituyen. Haz esto:

```bash
export FILMCRAFT_STUDIO_ROOT=/ruta/al/repo/plugins/filmcraft-studio   # o la ruta relativa desde aquí
export CLAUDE_PLUGIN_ROOT="$FILMCRAFT_STUDIO_ROOT"                     # para copiar los comandos tal cual
export CLAUDE_PLUGIN_DATA="${XDG_DATA_HOME:-$HOME/.local/share}/filmcraft-studio"   # catálogo de DS aprobados
```

- `${CLAUDE_PLUGIN_ROOT}` → `$FILMCRAFT_STUDIO_ROOT` (desde la raíz del repo: `plugins/filmcraft-studio`).
- `${CLAUDE_SKILL_DIR}` → la carpeta de la skill que estás leyendo (`$FILMCRAFT_STUDIO_ROOT/skills/<skill>`).
- Sin `CLAUDE_PLUGIN_DATA`, los scripts guardan en `~/.cache/filmcraft-studio/`. Otro catálogo de DS: `FILMCRAFT_DS_CATALOGO`.
- Los scripts calculan su raíz desde su propia ruta y no dependen del arnés: `python3 "$FILMCRAFT_STUDIO_ROOT/scripts/herramientas.py" --doctor`.

## Requisitos

- macOS para el montaje con FilmCraft (Apple Vision vía `swiftc`, la app en `/Applications`). El motor de código y Blender no dependen de macOS, pero en Linux no se han probado.
- FilmCraft ≥ 0.8 con `filmcraft-cli` en el PATH o en `FILMCRAFT_CLI`; puerto del canal de control en `FILMCRAFT_PORT` (9876). El servidor MCP es `filmcraft-cli mcp --bridge 127.0.0.1:9876`: regístralo en tu cliente con el nombre `filmcraft` si quieres usar sus herramientas.
- `ffmpeg`/`ffprobe`, `whisper-cpp` con un modelo ggml (`FILMCRAFT_WHISPER_MODEL`), Python 3.9+ con `pip install -r plugins/filmcraft-studio/requirements.txt`. Opcionales: Blender, VHS.
- Las fuentes que pida el design system.

Antes de empezar: `python3 "$FILMCRAFT_STUDIO_ROOT/scripts/herramientas.py" --doctor` (con `--ds <id>` revisa también las fuentes de ese estilo). Sale con 1 si falta algo imprescindible.

## Equivalencias de herramientas

Las skills nombran herramientas de Claude Code. Si tu agente no las tiene:

| La skill dice | Haz |
|---|---|
| `AskUserQuestion` | Pregunta en texto, con opciones numeradas y la recomendada primero, y espera la respuesta. Como mucho 4 preguntas por ronda. |
| `SendUserFile` (enseñar una imagen o un video) | Da la ruta absoluta del archivo; si tu cliente muestra imágenes, ábrela también. |
| Subagente (`analista-material`, `director-montaje`, `critico`, `critico-estilo`) | Lánzalo con tu mecanismo de subagentes pasándole el `.md` de `agents/` como prompt. Si no hay subagentes, hazlo tú en un paso aparte, releyendo solo lo que ese `.md` dice que recibe (así la crítica no hereda tus decisiones). |
| `model: fable` en `critico-estilo` | El modelo más capaz que tengas. |
| Carpeta de scratch | `mktemp -d`; nunca dentro del plugin. |

## Reglas que no se negocian

- No exportes video si el usuario no lo pide; nunca escribas en sus carpetas sin que lo diga.
- No instales nada sin permiso explícito.
- En headless, trabaja siempre sobre un proyecto **nuevo**; con la app abierta, solo por su canal de control.
- Mira las hojas de fotogramas antes de opinar sobre un montaje; informa con cifras y di lo que no se pudo verificar.
- Audio: −14 ± 1 LUFS integrados y pico real ≤ −1 dBTP.
- No inventes citas, cifras ni afirmaciones comparativas: cada dato del guion lleva su fuente.
- La biblia aprobada manda: el video final se verifica contra sus criterios de aceptación, y cada nota de revisión se anota en ella.
