# Esquema de ds.json

Esquema formal (JSON Schema 2020-12): `schemas/ds.schema.json` (en la raíz del plugin; desde Bash, `$S/../schemas/ds.schema.json`). `ds_validate.py` lo aplica si `jsonschema` está instalado y, además, comprueba lo que un esquema no expresa: rol → pista declarada, rol/transición → SFX presente en `sfx.mapa`, animación del rol definida en `animaciones`, transición de `preferencia` definida, fondos y mattes que existen y miden como el lienzo, contraste y fuentes instaladas (`ds_validate.py --todos` recorre el catálogo; `--estricto` convierte los avisos en errores).

Rutas `assets/…` son relativas a la carpeta del DS; `~/` se expande. Colores: un hex o el nombre de un color de `paleta`. Las claves marcadas *(informativa)* no las lee ningún script: son guía para quien monta o escribe la escena.

| Clave | Contenido |
|---|---|
| `id`, `nombre`, `version`, `gramatica`, `descripcion` | Identidad. `id` es un slug `[a-z0-9-]` (es el nombre de la carpeta). `gramatica` nombra el conjunto de reglas (`brutalista@1`, `riso@1`, `tres-fases@1`…) |
| `match` | `rutas` (subcadenas de la carpeta del material), `palabras`, `flyer`, `paleta_ref`: para elegir el DS solo |
| `lienzo` | `ancho`, `alto`, `fps` de la secuencia, `plataforma`; opcional `variantes` `{nombre: {ancho, alto, nota}}` con otros formatos que produce el mismo DS (p. ej. `9x16` de un DS 16:9). Fondos y mattes miden como el lienzo; si miden como una variante, `ds_validate` avisa |
| `paleta` | `fondo`, `oscuro`, `claro`, `acento1` obligatorios; `rejilla`, `acento2`, `acento3` recomendados. **`claro` es siempre el color luminoso** (texto sobre cajas oscuras) y **`oscuro` el de las cajas y el texto oscuro**, también con un fondo claro: en un tema claro, `claro` ≈ `fondo` y `oscuro` es el color de la tinta |
| `fuentes` | `titular`, `ui`, `meta`: `familia` y `estilo` como los nombra el sistema (FilmCraft las pide por familia) y `archivo` para PIL. Un `archivo` en `~/` no estará en otra máquina (aviso) |
| `marca` | Textos fijos. Obligatorios `barra`, `titulo` (con `\n`), `cta`; los leen `plan_compile`/`ds_preview`: `hashtag`, `titulo_pill`, `cierre_palabras` (lista), `cierre_linea`, `cierre_pie`. `handle` *(informativa)* |
| `pistas` | `video` (abajo → arriba, índices 0-based), `audio`, `sfx` (pistas de audio donde caben los SFX, por orden de preferencia) |
| `roles_texto.<rol>` | `fuente`, `tam` (px a 1080 del lado corto), `color`, `fondo` (uno o lista para variantes), `margen` (`background_size`), `pista` (o `pistas` por variante), `pos` fija o `zona: libre`, `align`, `anim` (`popIn`, `wordReveal`, `eco`, `calorEntra`, `ninguna`; tiene que estar definida en `animaciones`), `sfx` (clave de `sfx.mapa`), extras por rol (`max_chars`, `paso_y`, `paso_x`, `colores`, `frames`, `x`, `y`, `interlinea`) |
| roles obligatorios | `marca`, `subtitulo`, `etiqueta`, `eco`, `pill`, `tag`, `titulo`, `cierre`, `meta`, `pie` (tarjeta y cierre). `marca` y `subtitulo` necesitan `pos`. Opcionales: `concepto`, `escalon`, `nombre`, `rotulo` (los usa el plan de un reel de evento: un plan con esos roles sobre un DS que no los tenga falla en `plan_compile`), `cifra`, `comando` (DS de promo) |
| `animaciones` | `base_fps` en que están escritos los fotogramas; `popIn` (escala y opacidad), `wordReveal` (`paso_f`, `fade_f`, `dy`), `eco` (`frames`); opcional `calorEntra` (gramática termo: la lee `fcstyle.py`) |
| `continuidad` | `entrada` y `zoom_crash` (obligatorias: `apply_plan`/`plan_compile` las leen sin `.get`), `jump_cut.punch`, `salida` |
| `transiciones` | `preferencia` y la configuración de cada una: `corte` (obligatoria), `flash`, `matte`, `glitch`, `barrido_camara`, `frente_llama`/`frente_hielo` (termo) — fotogramas a `base_fps`, matte, `sfx` (clave de `sfx.mapa`) |
| `fondos`, `mattes` | `titulo`, `plano`, `cap`, `cierre`; `blanco`, `acento1..3`. Al tamaño del lienzo. DS de FilmCraft: `ds_assets.py`; DS de promo: `promo_fondos.py` (piel de la gramática + mattes) |
| `sfx` | `dir`, `nivel_db`, `mapa` evento → archivo (gancho, cierre, riser, flash, matte, glitch, barrido, titulo, pop, slide, tecla, blip, nombre, premio, foto…). Kits de promo: `promo_sfx.py GRAMATICA DIR [--solo a,b]` |
| `musica` | `bpm`, `bajo_voz_db` y `sin_voz_db` (obligatorias), `rampa_s`, `salida_s`, `nota` (la lee `plan_compile`); `archivo`; `genero` *(informativa: describe la música que se sintetiza en la rejilla)* |
| `grade` | Parámetros de `lumetri`, `sharpen`, `unsharp_mask`, `noise` |
| `audio` | `lufs`, `pico_dbtp` (obligatorias), `fade_corte_f`, `dialogo_db` |
| `estructura` | `duracion_s` [min, max] (obligatoria), `titulo_s`, `cierre_s`, `foto_f`, `fotos_max`; `orden` y `gancho_s` *(informativas)* |
| `ritmo` | `margen_corte_ms`, `energia` (`baja|media|alta`); `plano_s` *(informativa)* |
| `zonas` | `evitar_y` (franjas reservadas: marca y subtítulos), `margen`, `y_min_bloque` |
| `vocabulario` | Prompt de whisper: nombres propios y términos del evento |
| `promo` | Solo DS de promo por código. `bpm` (obligatorio; `promo_preview.py`), `mapas` `{caliente, frio}` de pares `[posición, hex]` (obligatorio en termo y tres-fases; `promo_gradmap.py`), `firma`, `motor`, `timeline` y el resto: prosa para quien escribe la escena *(informativas)* |
| `termo` | Guía en prosa de la gramática termo *(informativa)* |
| `estado` | La escribe `ds_studio.py`: `borrador`, `creado`/`aprobado`, `iteracion` (borrador) o `iteraciones` (aprobado), `spec`, `cambios` |
| `derivado_de` | La escriben `ds_studio.py`/`ds_from_image.py`: `base` (id del DS de origen), `descripcion`, `flyer` (solo el nombre), `recorte`, `clusters`, `acentos_derivados` |

No hay otras claves: el esquema rechaza las desconocidas en la raíz, en `lienzo`, `pistas`, `sfx`, `match` y en cada rol (así un `tamm` mal escrito no pasa en silencio).

Todo lo que va en fotogramas está a `animaciones.base_fps`; el motor lo pasa a segundos y lo redondea a los fps reales de la secuencia.

Otros esquemas del plugin (básicos, para validar desde otra herramienta): `schemas/plan.schema.json`, `brief.schema.json`, `biblia.schema.json`, `guion.schema.json`.
