# Esquema de ds.json

Rutas `assets/…` son relativas a la carpeta del DS; `~/` se expande. Colores: un hex o el nombre de un color de `paleta`.

| Clave | Contenido |
|---|---|
| `id`, `nombre`, `version`, `gramatica`, `descripcion` | Identidad. `gramatica` nombra el conjunto de reglas (`brutalista@1`) |
| `match` | `rutas` (subcadenas de la carpeta del material), `palabras`, `flyer`, `paleta_ref`: para elegir el DS solo |
| `lienzo` | `ancho`, `alto`, `fps` de la secuencia, `plataforma` |
| `paleta` | `fondo`, `rejilla`, `oscuro`, `claro`, `acento1`, `acento2`, `acento3` |
| `fuentes` | `titular`, `ui`, `meta`: `familia` y `estilo` como los nombra macOS (FilmCraft) y `archivo` para PIL |
| `marca` | Textos fijos: `barra`, `handle`, `hashtag`, `cta`, `titulo` (con `\n`), `titulo_pill`, `cierre_palabras`, `cierre_linea`, `cierre_pie` |
| `pistas` | `video` (abajo → arriba, índices 0-based), `audio`, `sfx` (pistas de audio donde caben los SFX, por orden de preferencia) |
| `roles_texto.<rol>` | `fuente`, `tam` (px a 1080 de ancho), `color`, `fondo` (uno o lista para variantes), `margen` (`background_size`), `pista` (o `pistas` por variante), `pos` fija o `zona: libre`, `align`, `anim` (`popIn`, `wordReveal`, `eco`, `ninguna`), `sfx`, extras por rol (`max_chars`, `paso_y`, `paso_x`, `colores`, `frames`, `x`, `y`, `interlinea`) |
| `animaciones` | `base_fps` en que están escritos los fotogramas; `popIn` (escala y opacidad), `wordReveal` (`paso_f`, `fade_f`, `dy`), `eco` (`frames`) |
| `continuidad` | `entrada` (escala y fundido de toma nueva), `jump_cut.punch`, `salida`, `zoom_crash` |
| `transiciones` | `preferencia` y la configuración de `flash`, `matte`, `glitch`, `barrido_camara`, `corte` (fotogramas a `base_fps`, matte, SFX) |
| `fondos`, `mattes` | `titulo`, `plano`, `cap`, `cierre`; `blanco`, `acento1..3` |
| `sfx` | `dir`, `nivel_db`, `mapa` evento → archivo (gancho, cierre, riser, flash, matte, glitch, barrido, titulo, pop, slide, tecla, blip, nombre, premio, foto…) |
| `musica` | `generador` o `archivo`, `bpm`, `bajo_voz_db`, `sin_voz_db`, `rampa_s`, `salida_s` |
| `grade` | Parámetros de `lumetri`, `sharpen`, `unsharp_mask`, `noise` |
| `audio` | `lufs`, `pico_dbtp`, `fade_corte_f`, `dialogo_db` |
| `estructura` | `duracion_s` [min, max], `orden`, `gancho_s`, `titulo_s`, `cierre_s`, `foto_f`, `fotos_max` |
| `ritmo` | `plano_s`, `margen_corte_ms`, `energia` |
| `zonas` | `evitar_y` (franjas reservadas: marca y subtítulos), `margen`, `y_min_bloque` |
| `vocabulario` | Prompt de whisper: nombres propios y términos del evento |

Todo lo que va en fotogramas está a `animaciones.base_fps`; el motor lo pasa a segundos y lo redondea a los fps reales de la secuencia.
