# Auditoría: motor determinista (2026-11-16)

Objetivo, el mismo que en diseno-studio: quitar la IA de todo lo que se puede contar o comparar contra un
token o umbral y dejarla solo para el gusto, y sustituir Python por un binario compilado por plataforma
donde el coste o la decisión están en el Python. Resultado: binario `cine` (Rust, `plugins/filmcraft-studio/motor/`,
1,2 MB, dependencias `serde_json`, `png` y `jpeg-decoder`; sin tokio, sin clap, sin regex: JSON Schema y
patrones con un subconjunto propio, con tests) y un único crítico con IA, `critico-juicio`.

## 1. Inventario

### Dónde decidía una IA

| Punto (fichero) | Qué decidía | Veces por video | Clase | Ahora |
|---|---|---|---|---|
| `agents/critico.md` · Audio | LUFS fuera de −14 ± 1, pico > −1 dBTP | 1 por pasada (≤ 3 en headless) | se puede medir | `cine puntuar` eje `audio` |
| `critico.md` · Obligatorios | los que faltan | idem | se puede medir | eje `obligatorios` (cobertura del compilado) |
| `critico.md` · Imagen | textos sobre caras, keyframes, negros y flashes en los cortes | idem | se puede medir (salvo «orden de capas») | eje `imagen` |
| `critico.md` · Ritmo | planos que se alargan, finales de frase cortados | idem | se puede medir | eje `ritmo` (planos frente a `ds.ritmo.plano_s`, cortes en palabra, duración frente al DS) |
| `critico.md` · Textos | faltas, rótulos que no dicen nada | idem | parte medible + gusto | `lectura` (≤ 3 palabras/s, ≥ 1 s) medido; el copy, al crítico |
| `critico.md` · Historia | gancho en 3 s, remate, CTA | idem | gusto | `critico-juicio` eje `historia` |
| `critico.md` · Estilo | lo que se aparta del DS | idem | parte medible + gusto | `cine validar-ds` + techos; el resto, `originalidad` |
| `critico.md` · Veredicto | publicable / con arreglos / no publicable, sin fórmula | idem | se puede calcular | `cine nota` (bloqueantes → no publicable; nota ≥ 4,2 sin ejes < 4 → publicable) |
| `agents/critico-estilo.md` | distinto / genérico / clon, 5 arreglos | 1 por iteración de direcciones + 1 al final | parte medible + gusto | clon y misma maqueta: `referencias.py --comparar` (ya existía) fija bloqueante y techo; «genérico», filosofía y metáfora: `critico-juicio` eje `originalidad` |
| Criterios de la biblia (`director-video` 5–6, `promo-codigo` 7, `nota.md`) | la IA recorría cada criterio y escribía la tabla del informe | 1 por pasada | parte medible + gusto | `cine criterios` (lienzo, duración, fps, LUFS, dBTP, MB, `medida`); los de gusto con `juicio: true` |
| Elección de DS (headless D2, asistido G1, exprés, promo-codigo 3) | ranking a ojo o con `match_ds` (distancia RGB) | 1 | se puede medir | `cine elegir-ds` (ΔE OKLab); exprés y promo ahora usan el ranking |
| Validación del DS (`ds-preview`: «comenta el contraste») | contraste, assets, fuentes | por iteración del DS | se puede medir | `cine validar-ds` |
| Medidas de entrega (`entregar.md`, criterios con `ffprobe`/`ebur128` a mano) | la IA lanzaba y leía ffprobe/ebur128 | 1 por entregable | se puede medir | `cine medir-video` |
| `agents/analista-material.md` | momentos con peso, gancho, descartes | 1 | parte medible + gusto | sin cambios: las señales ya llegan medidas por `analyze_media.py`; el peso es gusto |
| `agents/director-montaje.md` | estrategia, estructura, cortes, transiciones | 1 + rehechos | gusto (bucle con criterios ya medidos por `plan_compile`) | sin cambios |
| Preproducción: preguntas, concepto, guion, DS nuevo, capa 2 de las fichas | | 1 | gusto | sin cambios |

### Scripts Python y su coste

| Script | Líneas | Dónde está el coste | Decisión |
|---|---|---|---|
| `ds_validate.py` | 293 | intérprete + PIL + jsonschema (144 ms por DS) | **sustituido** por `cine validar-ds` y borrado |
| `brief_infer.match_ds` (+ `componentes`, `casa_ruta`, `hexd`) | ~100 | intérprete + PIL/numpy (k-means) | **sustituido** por `cine elegir-ds`; `match_ds` queda como envoltorio de 10 líneas |
| `brief_infer.py` (resto: candidatos, brief) | ~180 | intérprete | se queda: no decide nada que pase por la IA; portarlo no quita llamadas |
| `verify.py` | 414 | `filmcraft-cli` (render de fotogramas, copia sin textos), Vision (Swift) y ffmpeg | se queda: el coste está en las herramientas; sus comprobaciones ya eran código. Lo que el crítico hacía con su salida, ahora lo hace `cine puntuar` |
| `report.py` | 186 | intérprete | se queda; la tabla de criterios sale de `cine criterios --md` |
| `ref_metricas.py` | 1432 | OpenCV (Canny, Hough, Otsu, saliencia), 0,48 s por imagen | se queda: ya es determinista, no pasa por la IA y la paridad con OpenCV en Rust no es realista (remuestreos, Canny, Hough) |
| `referencias.py` | 587 | ref_metricas + ffmpeg | se queda; su `--comparar` alimenta `cine puntuar --comparaciones` |
| `analyze_media.py`, `transcribe_fc.py`, `camera_motion.py` | 597 | whisper.cpp, Vision, ffmpeg | se quedan (coste en la herramienta) |
| `plan_compile.py`, `apply_plan.py`, `fcengine.py`, `fclib.py`, `fcstyle.py`, `freezones.py` | 1700 | motor de FilmCraft (`filmcraft-cli`) | se quedan (el coste es el motor) |
| `motor_blender.py`, `scripts/blender/` | 151+ | Blender | se queda |
| `ds_from_image.py`, `ds_assets.py`, `ds_preview.py`, `ds_studio.py`, `promo_*.py`, `music_bed.py`, `imagen_a_video.py`, `render_sheet.py` | ~2400 | dibujo con PIL, síntesis con numpy, render con FilmCraft o ffmpeg | se quedan: generan imágenes y sonido (creatividad parametrizada), no deciden; candidatos a un segundo paso si se quiere quitar Python del todo |
| `herramientas.py`, `common.py` | 764 | intérprete | se quedan; `common.cine()` llama al binario y el doctor lo comprueba |

## 2. IA → determinista

| Antes (IA) | Ahora | Comando |
|---|---|---|
| `critico` entero salvo historia y copy | 6 ejes 1–5 con anclas fijas: `criterios`, `obligatorios`, `audio`, `imagen`, `ritmo`, `lectura`; bloqueantes y arreglos concretos (dB de ganancia, segundo del corte, texto y duración) | `cine puntuar` |
| veredicto del crítico, a ojo | nota ponderada y veredicto por regla; los 5 arreglos (los medidos primero) | `cine nota` |
| `critico-estilo`: clon y misma maqueta | veredicto de `referencias.py --comparar` → bloqueante y techo 2 de originalidad (3 si es «estilo distinto» de una referencia que se quería reproducir; reproducir una anti-referencia también es bloqueante) | `cine puntuar --comparaciones` |
| tabla de criterios del informe | criterios con cifra comprobados contra las medidas; inferencia de lo estándar del texto; `medida` explícita; `juicio: true` | `cine criterios [--md]` |
| ffprobe/ebur128 a mano | formato, peso, LUFS, LRA, pico, curva por segundo, cortes por escena, planos, negros y flashes | `cine medir-video` |
| elección del DS a ojo (exprés, promo) o por distancia RGB | ranking por rutas y ΔE OKLab | `cine elegir-ds` |
| validar el DS | mismas comprobaciones, JSON Schema propio | `cine validar-ds` |
| mejora o empeora la iteración (no existía) | Mejora / Regresión / Empate; un bloqueante nuevo es Regresión sin A/B; A/B a ciegas solo si \|Δ\| < 0,30 | `cine nota --mejor`, `cine ab` |
| **Sigue siendo IA** | historia, copy, originalidad (con su techo), criterios de juicio | `agents/critico-juicio.md` (`model: fable`) |

Llamadas a IA por pasada de verificación: de 2 (`critico` + `critico-estilo`, más la IA recorriendo los
criterios a mano) a 1 (`critico-juicio`), +1 solo si el A/B es necesario. En headless (≤ 3 pasadas): de 6
a entre 3 y 6. En la preproducción el número de críticas por iteración no cambia (1), pero ahora llegan
con las medidas y un techo.

## 3. Paridad y tiempos (datos reales, Mac M-series)

| Qué | Datos | Resultado | Tiempo Python → Rust |
|---|---|---|---|
| `validar-ds` frente a `ds_validate.py` | 8 DS del catálogo (7 del plugin + `ug-seguridad-nocturna`), 2 borradores, 1 versión anterior, 105 DS rotos (35 mutaciones × 3 DS) | **0 diferencias en 107 de 110**; en los 3 restantes (`tam` como texto) el Python petaba («forma que el validador no esperaba») y el Rust da el error de esquema y el de forma. Los 38 tests del validador pasan contra el binario | 144 → 12 ms por DS; 151 → 28 ms `--todos` |
| `elegir-ds` frente a `match_ds`, solo rutas | `/x/kindling/videos-1.0`, `--para promo` y los casos del test e2e | ranking idéntico | 33 → 14 ms |
| `elegir-ds` frente a `match_ds`, con flyer | el flyer de sbg y las 8 `preview.png` como «flyer» | top-1 correcto en 6 de 9 con los dos (no los mismos 6: Rust acierta blueprint, Python acierta brasa-escarcha; los dos fallan chispa y tres-fases y empatan riso/tres-fases). El propio DS saca ≥ 0,91 en Rust (0,94 en Python) y la separación con el segundo es mayor (sbg 0,94 frente a 0,81; Python 0,94 frente a 0,82) | 220 → 47 ms |
| paleta del flyer (k-means Rust en OKLab frente a numpy en RGB) | los mismos 9 | ΔE por rol, mediana: fondo 0,7, claro 0,3, acento1 0,8, acento2 2,9, acento3 2,7; 39 de 45 colores por debajo de ΔE 5. Las diferencias grandes son acentos secundarios de grupos pequeños (gradient-map acento2 57, sbg acento3 33) | — |
| `medir-video` frente a `common.ffprobe` + `common.loudness(curva=True)` + `referencias.cortes` | 5 videos de `docs/video` | **0 diferencias** (formato, cortes, LUFS, LRA, pico, curva por segundo) | 0,27–0,38 s → 0,52–0,74 s: el Rust hace una pasada más de ffmpeg (negros y flashes); el coste es ffmpeg |
| `criterios` frente al informe que escribió la IA | kindling-1.0 (biblia de 16 criterios, entregables 4:5 y 9:16) | c1 y c10, los dos con cifra estándar, igual que la IA (39,68 s, 60 fps, −13,8 LUFS, −2,0 dBTP); los otros 14 quedan para el crítico | < 10 ms |
| `criterios` | filmcraft-studio-0.3 (9:16 máster y ligero) | c8 «cumple en lo medido» (−14,1 LUFS, −1,1 dBTP) y deja «la música cambia de género» al crítico; c9 «9:16 < 30 MB» **no cumple** en el máster (96,1 MB) y sí en el ligero (21,9 MB): el criterio era ambiguo, ahora se nota; con `medida` y `archivo: "ligero"` se resuelve | < 10 ms |
| `puntuar` | kindling-1.0 + 5 comparaciones reales con sus anti-referencias | audio 5, ritmo 4 (14 de 18 planos en 1,2–5,5 s), criterios 5, imagen 4: encontró un negro de 0,1 s a 36,2 s en los dos formatos (quizá el pliegue final; queda como evidencia y arreglo, no bloqueante); las 5 comparaciones «estilo distinto» frente a anti-referencias, techo 5 | < 10 ms |
| `puntuar` + `nota` en montaje | `compiled.json` real de `plan_compile.py` (plan sintético de los tests) + `verificacion.json` con la forma de `verify.py` | lectura detecta 3 rótulos que no se leen (p. ej. «SESIÓN 5: IA Y MACHINE LEARNING EN AWS», 8 palabras en 2,5 s); nota, veredicto y clase calculados | < 10 ms |
| Suite Python | 281 tests | pasan | — |
| `cargo test` / `nix build` | 11 tests | pasan; `nix build` da el marketplace con `bin/darwin-arm64/cine` | — |

Diferencias deliberadas:
- `elegir-ds` mide el color con ΔE en OKLab (`1 − ΔE medio / 60`, recortado a 60) en vez de distancia
  RGB / 441,7. El tope 60 se calibró para que el propio DS siga por encima de 0,9 y el resto por debajo de
  0,85: los umbrales documentados (0,5 con ruta; ≥ 0,9 mismo estilo, < 0,7 crear) siguen valiendo.
- La paleta del flyer sale de un k-means determinista en OKLab con semillas de histograma (sin RNG), el
  mismo que diseno-studio, sobre un recorte y una reducción por promedio de cajas propios: no reproduce el
  remuestreo de PIL ni el k-means++ de numpy.
- `validar-ds` siempre aplica el esquema (antes, solo si `jsonschema` estaba instalado); `"esquema"` en
  la salida dice `cine (JSON Schema 2020-12, subconjunto)`. Los mensajes del esquema imitan los de
  `jsonschema` en los casos que usan los esquemas del plugin; en reprs complejos (flotantes en notación
  científica) pueden diferir.
- `sin_tildes` usa una tabla de vocales y ñ/ç en vez de la normalización NFD completa.

## 4. Cambios que ve Juan (para revisar)

- **Ya no existen los agentes `critico` y `critico-estilo`**: los sustituye `critico-juicio` (`model: fable`),
  que devuelve JSON en vez de prosa. El veredicto, la nota y los 5 arreglos los calcula `cine nota`.
- La verificación crea una carpeta por vuelta (`verificacion/vN/` con `ejes.json`, `juicio.json`, `nota.json`)
  y puede volver a la versión anterior si la nueva es Regresión.
- Los criterios de la biblia admiten `medida` y `juicio: true` (`schemas/biblia.schema.json`); los
  antiguos `{id, que, como}` siguen valiendo.
- `herramientas.py --doctor` exige el binario `cine` (sale con 1 si falta). Para instalar el plugin hace
  falta `nix build`, `sh plugins/filmcraft-studio/motor/compilar.sh` (Rust/cargo) o los binarios del CI.
- `jsonschema` deja de usarse en tiempo de ejecución (solo en los tests de esquemas).

## 5. Sin comprobar

- Un montaje real de punta a punta con `verify.py` y el bucle nuevo: no había material grabado ni
  `verificacion.json` reales a mano. `puntuar` en montaje se probó con un `compiled.json` real y un
  `verificacion.json` con la forma exacta de `verify.py`, no con uno producido por él.
- `critico-juicio` no se ha lanzado sobre un caso real; `juicio.json` de las pruebas es de muestra.
- Las anclas de `puntuar.rs` y los pesos de `nota.rs` salen de las rúbricas escritas y de dos campañas
  (kindling-1.0 y filmcraft-studio 0.3): recalibrar tras 3–4 videos.
- Detección de negros y flashes en promos con fundidos a negro deliberados: los del primer y último segundo
  se ignoran; uno a mitad (como el de kindling a 36,2 s) resta un punto aunque sea intencionado.
- Los binarios de Linux, Windows y macOS Intel y el job `nix` del workflow `.github/workflows/motor.yml`:
  escrito, no ejecutado. `bin/cine.cmd` (Windows) sin probar.
- La fidelidad de `elegir-ds` con flyers reales nuevos: el catálogo solo tiene un flyer de verdad (sbg);
  las demás pruebas usan las vistas previas de cada DS como flyer.

## 6. Siguientes pasos posibles

- Portar `report.py` a `cine informe` (lee `nota.json` y la tabla de criterios directamente).
- Si se quiere quitar Python del todo: los generadores (`ds_assets`, `promo_fondos`, `promo_sfx`,
  `music_bed`) y `ref_metricas` (la parte de color y valores es fácil; composición y bordes dependen de
  OpenCV).
