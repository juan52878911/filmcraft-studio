# plan.json — EDL de intención

El director escribe la intención; `plan_compile.py` resuelve lo mecánico (límites de palabra, fotogramas, zonas libres, subtítulos, marca, SFX, música, grade). **Todo tiempo de plano va en segundos de la FUENTE** (los de `analisis/transcripcion.md`).

```json
{
 "version": 1,
 "titulo": "Reel #RetoCertEAN S5 (auto)",
 "ds": "sbg-brutalista-s5",
 "estrategia": "4–8 frases: estructura, tomas, ritmo, transiciones, color, audio, duración.",
 "correcciones": {"rekoñicion": "Rekognition", "Reko": "Rekognition"},
 "bloques": [
  {"id": "gancho", "tipo": "gancho", "resumen": "100 USD + 20 por misión",
   "planos": [
     {"src": "PXL_20261016_192857298_voz", "in": 53.5, "out": 55.3},
     {"src": "PXL_20261016_192857298_voz", "in": 57.9, "out": 61.0}
   ],
   "textos": [
     {"rol": "eco", "texto": "100 USD", "palabra": "100"},
     {"rol": "eco", "texto": "20 USD", "palabra": "20"}
   ]},
  {"id": "titulo", "tipo": "tarjeta", "dur": 2.5, "transicion": "matte"},
  {"id": "sagemaker", "tipo": "contenido", "transicion": "flash",
   "planos": [{"src": "PXL_20261016_194307337_voz", "in": 0.0, "out": 4.3},
              {"src": "PXL_20261016_194307337_voz", "in": 10.6, "out": 12.2}],
   "textos": [{"rol": "etiqueta", "texto": "SAGEMAKER", "palabra": "SageMaker"},
              {"rol": "etiqueta", "texto": "¿KIRO?", "palabra": "Kiro", "variante": 1}]},
  {"id": "premio", "tipo": "humano",
   "planos": [{"src": "PXL_…", "in": 1.75, "out": 3.3, "zoom": {"a": 180, "ancla": [0.85, 0.45]}},
              {"src": "PXL_…", "in": 3.3, "out": 5.45, "speed": 4, "entrada": "barrido"}],
   "textos": [{"rol": "eco", "texto": "¡GANÓ!", "t": 0.5}],
   "sfx": [{"tipo": "premio", "t": 0.4}]},
  {"id": "invitada", "tipo": "invitados",
   "planos": [{"src": "PXL_…", "in": 16.5, "out": 28.6}],
   "textos": [{"rol": "nombre", "texto": "NATALIA ALARCÓN\nFUNDADORA · GEEKCODEY", "palabra": "Corazón"}],
   "capas": [{"fondo": "cap", "pista": "Tarjeta", "t": 3.4, "dur": 4.6, "sfx": null},
             {"img": "/ruta/producto1.png", "t": 3.4, "dur": 1.5, "entra": "der"},
             {"img": "/ruta/producto2.png", "t": 4.9, "dur": 1.5, "entra": "der"}]},
  {"id": "fotos", "tipo": "fotos", "fotos": ["/ruta/a.jpg", "/ruta/b.jpg"], "f": 20},
  {"id": "cierre", "tipo": "cierre", "dur": 3}
 ]
}
```

## Bloques

| Campo | Para qué |
|---|---|
| `id` | Único y corto: lo usan el asistido (G4) y `--deshacer` |
| `tipo` | `gancho`, `contenido`, `humano`, `invitados` (con `planos`); `tarjeta`/`titulo` y `cierre` (con `dur` y textos por defecto del DS); `fotos` |
| `transicion` | Cómo se entra al bloque: `corte`, `flash`, `matte`, `glitch`, `barrido`, `zoom_crash`, `entrada` (continuidad: escala 1,08 → 1 y fundido) |
| `planos` | Tomas en orden (ver abajo) |
| `textos` | Rótulos del bloque (ver abajo). En `tarjeta` y `cierre`, si se omiten, salen de `marca` del DS |
| `sfx` | Extras `{"tipo": clave de ds.sfx.mapa, "t": desfase, "db": opcional}`. Los de animaciones y transiciones se ponen solos |
| `capas` | Imágenes encima del plano: `{"img"|"fondo", "pista": "Producto"|"Tarjeta", "t", "dur", "entra": "der"|"izq", "escala", "pos"}` |
| `subtitulos` | `false` para no subtitular el bloque |
| `resumen` | Una línea para el informe y la tabla de G3 |

## Planos

| Campo | Para qué |
|---|---|
| `src` | Nombre (stem) del video analizado; prefiere la versión `_voz` |
| `in`, `out` | Segundos de la fuente. Se ajustan solos a límite de palabra (queda registrado en `ajustes_corte`) |
| `speed` | 4 = speed ramp ×4 con flujo óptico; sin audio salvo `"mute": false` |
| `punch` | Escala estática en % (por defecto: 112 alterno en jump cuts del mismo ponente) |
| `zoom` | `{"a": 180, "ancla": [x, y], "desde": 0, "hasta": 1}` zoom dirigido anclado en (x, y) normalizados |
| `entrada` | Transición de ENTRADA a este plano (como `transicion`). Por defecto: `jump` si sigue al anterior en la misma fuente, `entrada` si cambia de toma |
| `mute` | Silencia el audio del plano |
| `nota` | Por qué está (para el crítico) |

**Barrido de cámara** (`"entrada": "barrido"`): pon el `out` del saliente y el `in` del entrante en el pico de sus barridos (`analisis/*.motion.json`, afina con `camera_motion.py fine`). El compilador añade desenfoque de salida y entrada y el whoosh.

## Textos

| Campo | Para qué |
|---|---|
| `rol` | Un rol de `ds.roles_texto`: `etiqueta`, `concepto`, `escalon`, `eco`, `pill`, `tag`, `nombre`, `rotulo`, `titulo`, `cierre`, `meta`, `pie` |
| `texto` | Con `\n` para varias líneas |
| `palabra` | 1–3 palabras de la transcripción: el texto entra cuando se dicen (busca dentro de los planos del bloque; `plano` para fijar uno) |
| `t` | Alternativa: desfase en segundos desde el inicio del bloque |
| `dur` | Por defecto, hasta el final del plano (0,8–3,5 s) |
| `pos` | `[cx, cy]` fijo. Si se omite en roles con `zona: libre`, se calcula la zona libre con las caras y personas de la toma |
| `preferir` | `[cx, cy]` preferido para la zona libre |
| `variante` | Índice del color de fondo del rol (alterna naranja/rosa/morado) |
| `grupo` | Mismo valor en varios `escalon` = escalera (cada uno baja `paso_y` y se desplaza `paso_x`) |

Subtítulos, barra de marca, música con ducking, fundidos de audio en cada corte y grade NO van en el plan: los pone el compilador desde el DS.
