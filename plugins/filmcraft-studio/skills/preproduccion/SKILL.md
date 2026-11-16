---
name: preproduccion
description: "Preproducción de un video: preguntas por rondas, lectura de referencias, design system con fotogramas para elegir, crítica de originalidad y biblia aprobada con criterios. Úsala con /filmcraft-studio:preproduccion, «pregúntame antes», «tengo referencias para el video» o «video exprés»."
argument-hint: "<qué video quieres> [--refs archivos|carpetas|URLs] [--material carpeta] [--sin-preguntas] [--expres]"
---

# Preproducción

Entrada: $ARGUMENTS

El video se decide aquí y se fabrica después. Al salir de esta skill hay una **biblia aprobada** por el usuario: respuestas, lectura de referencias, concepto, design system, movimientos, sonido, guion, motores, entregables y los **criterios de aceptación** con los que se verificará el video final. No se produce ninguna escena hasta que la biblia está aprobada. Solo se hacen antes los fotogramas fijos que sirven para elegir. Para producirla: `/filmcraft-studio:video` (o `/filmcraft-studio:promo`), que la lee en vez de volver a preguntar.

Referencias de la skill (léelas cuando toque):
- `${CLAUDE_SKILL_DIR}/references/preguntas.md`: banco de preguntas por rondas, con cuándo saltarse cada una y sus opciones.
- `${CLAUDE_SKILL_DIR}/references/referencias.md`: cómo leer una referencia con su ficha de tres capas (métricas medidas, filosofía, traducción a video), qué tomar y qué no.
- `${CLAUDE_SKILL_DIR}/references/originalidad.md`: la crítica contra lo genérico y contra el clon.
- `${CLAUDE_SKILL_DIR}/references/biblia.md`: formato de `biblia.json` y de `biblia.md`.
- Herramientas y motores: `${CLAUDE_PLUGIN_ROOT}/skills/director-video/references/herramientas.md` y `${CLAUDE_PLUGIN_ROOT}/skills/director-video/references/motores.md`.

Antes de cada llamada a un script (el estado del shell no persiste entre llamadas):

```bash
S=${CLAUDE_PLUGIN_ROOT}/scripts
export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}
W="<carpeta de trabajo>"                        # ver «Carpeta de trabajo W»
python3 $S/herramientas.py --doctor              # preflight: sale 1 si falta algo obligatorio; en una promo, --para promo
python3 $S/herramientas.py                       # qué motores hay instalados aquí
python3 $S/referencias.py "$W/referencias" --out "$W/preproduccion/referencias"   # medir: ficha y hoja por imagen, agregado.json
python3 $S/referencias.py --comparar REFERENCIA FOTOGRAMA                          # distancia de un fotograma propio a una referencia
```

## Carpeta de trabajo `W`

Se define aquí y las demás skills remiten a esta definición:
- Con material grabado (`--material` o una carpeta de evento): `W=<carpeta del material>/06 - FilmCraft/<slug>/`. Los montajes usan `<slug>` = `auto/<nombre>` (headless) o `asistido/<nombre>`. La caché de análisis es una sola por evento y la comparten todos los modos: `<carpeta del material>/06 - FilmCraft/analisis/`.
- En un repositorio (promo, demo, changelog): `W=<repo>/video/<slug>/`.
- Si no hay ninguna de las dos, pregunta dónde. Nunca dentro de la carpeta del plugin.

## Flujo

0. **Preflight y carpeta.** `herramientas.py --doctor`; si sale con 1, di qué falta y cómo instalarlo antes de seguir. Crea `W/referencias/` y `W/preproduccion/`. Si el usuario dio archivos o carpetas, cópialos o enlázalos en `W/referencias/`; nunca los muevas.
1. **Lo que ya se sabe.** Lee el pedido, el material, el repo (en uno grande, con un subagente si los hay, que devuelva hechos con `fichero:línea`), el catálogo de DS (`ds_studio.py catalogo`), `herramientas.py` y lo aprendido en promos anteriores (`${CLAUDE_PLUGIN_ROOT}/skills/promo-codigo/references/aprendido.md`). Rellena todas las respuestas que se puedan inferir y marca cada una como `inferido`, con su porqué. Lo inferido no se pregunta: se enseña en el resumen de cada ronda para que se pueda corregir.
2. **Referencias.** Pide siempre, en la primera ronda, que pase referencias: imágenes, videos, posters, webs, música, tipografías, y también **anti-referencias** (lo que no quiere que parezca). Mídelas con `referencias.py`: cada imagen recibe su **ficha** (`fichas/<nombre>.json`: color, valores y notan, composición, textura, bordes, profundidad y texto, con objetivo y tolerancia) y su hoja de diagnóstico (`fichas/<nombre>_hoja.png`). Mira la imagen y la hoja con Read y rellena en la ficha la capa `filosofia` y `video.plan` según `referencias.md`, citando la cifra que apoya cada afirmación. Con varias referencias, `agregado.json` separa lo común (el estilo) de lo idiosincrásico (de una pieza). Lo importante es la **filosofía**: la regla que genera el aspecto, qué significa, dónde actúa y dónde no, y cómo varía. Las URLs se abren con el navegador si hay uno disponible; guarda la captura en `W/referencias/`. Descargar algo necesita el permiso del usuario.
3. **Rondas de preguntas** (`preguntas.md`). Usa `AskUserQuestion` si está disponible; si no, pregunta en texto con opciones numeradas y espera la respuesta.
   - **Formato de cada ronda:** como mucho 4 preguntas, cada una con 2–4 opciones concretas. Primero va la recomendada, marcada «(Recomendado)» y con su porqué en la descripción. Usa `preview` cuando la diferencia sea visual (un fotograma, una paleta o una maqueta en texto).
   - **Primera pregunta de la ronda A**, si el usuario no lo dijo: «¿exprés o completo?» (exprés: una ronda y una hoja de 2 fotogramas; completo: hasta 5 rondas).
   - **Orden de las rondas:** A, intención; B, contenido; C, estilo (después de leer las referencias); D, movimiento y sonido; E, producción y entrega.
   - **Qué se salta:** lo ya respondido o inferido con confianza alta.
   - **Después de cada ronda:** un resumen de una tabla con lo decidido.
   - **Límite:** cinco rondas como mucho y una pregunta abierta final («¿algo más que deba saber?»).
4. **Concepto.** Antes de los colores, escribe la idea en una frase y la **metáfora** que liga el estilo al producto: qué representa cada variable visual (p. ej., la temperatura indica si un proceso corre o está congelado; o la confianza de un clasificador). Saca tres reglas de la filosofía de las referencias, traducidas a este producto. Si no hay metáfora, el estilo queda como un filtro.
5. **Design system.** Créalo o adáptalo con la skill `design-system-video`. Los promos por código llevan además su sección `promo` y su gramática en `${CLAUDE_PLUGIN_ROOT}/skills/promo-codigo/references/gramaticas.md`. Además de la paleta y las fuentes, el DS fija:
   - el **vocabulario de movimientos**: cada movimiento con nombre, qué significa y en qué escena va;
   - las 1–2 transiciones firma;
   - el kit de SFX y la música (micro-género y BPM);
   - el lienzo de cada entregable.
6. **Direcciones en fotogramas fijos.** Haz 2–3 direcciones distintas, o una sola si las referencias ya la fijan. De cada una, dos fotogramas: el gancho y el momento firma. Hazlos con el motor que de verdad producirá esa escena:
   - escena por código (promo): escribe antes `timeline.py` y una `escena.py` mínima con gancho y firma (esqueleto de `${CLAUDE_PLUGIN_ROOT}/skills/promo-codigo/references/motor.md`; la grabación VHS puede llegar después) y llámala con los segundos como último argumento, `python3 escena.py … 0.6,9.2` (escribe un PNG por tiempo);
   - 3D: `motor_blender.py --fotogramas`;
   - DS de FilmCraft: `ds_studio.py crear|modificar` (su `preview.png`) o `render_frame` de FilmCraft.

   `promo_preview.py` necesita un video ya renderizado: es para la entrega, no para este paso. Enseña los fotogramas con Read y, si la herramienta `SendUserFile` está disponible, envíalos; si no, da la ruta absoluta. Itera hasta que el usuario elija. No apruebes por él.
7. **Crítica de originalidad** (`originalidad.md`). Antes de proponer aprobar:
   1. **Mide.** `python3 $S/referencias.py --comparar <ref> <fotograma> --json --out "$W/preproduccion/comparaciones/<ref>__<fotograma>.json"` de cada fotograma contra cada referencia y cada anti-referencia. «Clon probable» o «misma maqueta» se arregla antes de la crítica; «estilo distinto» contra la referencia que se quería reproducir, también.
   2. **Puntúa.** `${CLAUDE_PLUGIN_ROOT}/bin/cine puntuar --ds <id> --biblia "$W/preproduccion/biblia.json" --comparaciones "$W/preproduccion/comparaciones" --out "$W/preproduccion/ejes.json"` (la biblia en borrador). Fija los techos de la originalidad y deja en `para_ia` los criterios de juicio.
   3. **Juzga.** Lanza el subagente `critico-juicio` con `ejes.json` y la carpeta `W` (fotogramas de las direcciones, biblia, `referencias/`, comparaciones), sin tus conclusiones. Guarda su JSON en `W/preproduccion/juicio.json`. Si su modelo no está, lánzalo con `model: opus`; si no hay subagentes, juzga tú en un paso aparte releyendo solo lo que `agents/critico-juicio.md` dice que recibe.
   4. **Nota.** `${CLAUDE_PLUGIN_ROOT}/bin/cine nota --ejes "$W/preproduccion/ejes.json" --juicio "$W/preproduccion/juicio.json"` da la nota (con los techos de la originalidad aplicados), el veredicto y los 5 arreglos; el `veredicto_estilo` (distinto, correcto pero genérico o clon) está en `juicio.json`. Aplícalos, rehaz los fotogramas y enséñale al usuario el antes y el después. Anota en la biblia (`criticas`) la iteración, el veredicto y qué cambió.
8. **Guion y motores.** Escribe `guion.json` con `${CLAUDE_PLUGIN_ROOT}/skills/director-video/references/guion.md` y asigna motor y herramienta a cada escena (`motores.md`, `herramientas.md`), solo entre las que estén instaladas o tengan permiso para instalarse.
9. **Biblia y aprobación.** Escribe `W/preproduccion/biblia.json` y `biblia.md` (`biblia.md` de la skill). Enséñale al usuario:
   - una tabla por bloque;
   - los fotogramas elegidos;
   - los **criterios de aceptación**. Los de estilo son medibles: salen de `agregado.json` → `comunes` (o de `reproducir` de la ficha) y se comprueban con `referencias.py --comparar` (`biblia.md`).

   Pide la aprobación explícita. Cualquier cambio posterior entra en la biblia: sube `iteracion` y anota el cambio. La producción (`director-video` o `promo-codigo`) lee la biblia, genera de ella `W/brief.json` y la verificación final la compara criterio a criterio. Si biblia y brief difieren, manda la biblia.

## Modo exprés

Con `--expres`, «video exprés», «rápido», «lo antes posible» o «exprés» como respuesta a la primera pregunta. La calidad no baja: se conservan hechos con fuente, fotogramas antes de animar, criterios y crítica; se quitan rondas, direcciones múltiples y la creación de DS.
1. Infiere todo (pedido, repo, CHANGELOG, material, `herramientas.py --json`) sin preguntar.
2. **Una ronda de ≤ 3 preguntas**, con lo inferido como recomendado: `idea` (2–3 frases candidatas con fuente), `plataforma` (formato y duración) y `estilo` (los 2–3 DS del catálogo que mejor casan, con su miniatura, más «tengo referencias», que devuelve al flujo completo).
3. DS del catálogo tal cual, sin crear ni modificar; en una promo, la escena mínima con el esqueleto de `${CLAUDE_PLUGIN_ROOT}/skills/promo-codigo/references/motor.md`.
4. **Una hoja de 2 fotogramas** (gancho y firma) con los textos reales. Aprobación = «sigue» o una nota.
5. Biblia en estado `expres`, respuestas marcadas `inferido`/`defecto` y criterios por defecto (`preguntas.md`, «Criterios por defecto»).
6. Render, `cine medir-video` y `cine criterios` y **una** vuelta de `cine puntuar` → `critico-juicio` → `cine nota` al final, sobre la hoja del video; sus arreglos se ofrecen como notas, no bloquean (un criterio que no cumple, sí).

Si el usuario trae referencias o rechaza los fotogramas dos veces, pasa al flujo completo desde la ronda C.

## Modo sin preguntas

Con `--sin-preguntas` o en headless, todo se infiere y se marca con su origen. Los fotogramas y la crítica se hacen igual. Lo que habría preguntado va a `pendientes` en la biblia y al informe final. Nunca se finge una aprobación: el estado de la biblia queda en `inferida`.

## Reglas

- Pregunta decisiones con opciones, no cuestionarios abiertos. Si una respuesta del usuario contradice una referencia o un hecho del repo, dilo y propone la salida.
- Las referencias inspiran, no se copian. No se recrea una obra, un personaje, una marca, un artista ni una película concretos, aunque se renombren. Se toma la regla, no el resultado.
- Ninguna afirmación del guion entra sin fuente. Ninguna herramienta se instala ni se descarga nada sin permiso.
- La biblia es la fuente de verdad. Si algo no está ahí, no se hace. Si se hace, se añade.
