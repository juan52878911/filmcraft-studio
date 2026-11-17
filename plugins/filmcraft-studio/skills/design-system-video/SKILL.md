---
name: design-system-video
description: "Catálogo de design systems de video y su ciclo crear → vista previa → modificar → aprobar (paleta, tipografías, animaciones, SFX, música, grade). Úsala con «qué estilos de video tengo», «crea el estilo del video desde este flyer o logo», «cambia los colores del video». No para UI ni webs."
---

# Design systems de video

Un DS es `design-systems/<id>/ds.json` + `assets/`. Separa dos capas:

- **Gramática** (`gramatica`, p. ej. `brutalista@1`): roles de texto, animaciones, zonas, continuidad, transiciones, mapa de SFX, música, grade, objetivos de audio, estructura y ritmo. Es el oficio; cambia poco.
- **Piel**: `paleta`, `fuentes`, `marca` (textos fijos), `fondos` y `mattes` generados. Cambia por evento.

Esquema comentado: `${CLAUDE_SKILL_DIR}/references/esquema.md`. Ejemplo completo y aprobado: `${CLAUDE_PLUGIN_ROOT}/design-systems/sbg-brutalista-s5/`.
Los DS que crea el usuario van a `${CLAUDE_PLUGIN_DATA}/design-systems/` (sobreviven a actualizaciones del plugin). La ruta se sustituye en este texto, pero el entorno de Bash no la trae: expórtala antes de los comandos (bloque de abajo); sin ella, los scripts caen en `~/.cache/filmcraft-studio/`. Si hay DS aprobados en `~/.cache/filmcraft-studio/design-systems/` y la carpeta de datos está vacía, ofrece copiarlos allí.

Gramáticas: `brutalista@1` (la del ejemplo), `termo@1` (promos) y `pegatina@1` (reel con presentador y rótulos tipo pegatina, tarjetas compuestas y subtítulos con palabra clave resaltada: `${CLAUDE_PLUGIN_ROOT}/skills/design-system-video/references/pegatina.md`).

## Catálogo y ciclo de aprobación (`ds_studio.py`)

Antes de cada llamada a un script (el estado del shell no persiste entre llamadas):

```bash
S=${CLAUDE_PLUGIN_ROOT}/scripts
export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}
python3 $S/ds_studio.py catalogo --hoja catalogo.png            # aprobados + precargados, con miniatura
python3 $S/ds_studio.py crear --id <slug> --spec '<json>' [--flyer F] [--base sbg-brutalista-s5] [--frame <foto real>] [--forzar]
python3 $S/ds_studio.py modificar <id> --spec '<solo lo que cambia>' [--frame <foto real>]
python3 $S/ds_studio.py aprobar <id>                            # valida y pasa al catálogo
python3 $S/ds_studio.py borradores                              # borradores sin aprobar
python3 $S/ds_studio.py ver <id>                                # dónde está (borrador/catálogo/precargado), paleta y vistas previas
python3 $S/ds_studio.py descartar <id>                          # tira un borrador (a la papelera, no se borra)
```

- **Desde una descripción**: tradúcela a un `spec` (formato en la cabecera de `ds_studio.py`): paleta en hex (5 colores: fondo, claro, 3 acentos; `claro` es siempre el color luminoso del texto y `oscuro` el de las cajas, también en temas claros), fuentes instaladas en el Mac (`familia` y `estilo` como los nombra macOS), `escala_texto`, `animacion` (`suave`, `normal`, `energica`) y TODOS los textos de `marca` (barra, hashtag, título en líneas cortas, pill, palabras y línea de cierre, pie, CTA). Lo que no des se hereda del DS base: dilo.
- **Desde un flyer o logo**: `--flyer` saca la paleta por k-means (k = 12, recorte automático de marcos y capturas, color "vivo" de cada grupo; acentos derivados por rotación de tono si faltan, anotados en `derivado_de`). El `spec` puede sobrescribir lo que quieras encima. Mira el flyer antes y copia de él los textos de marca (no hay OCR). `--frame` es opcional, pero con una foto real del evento la vista previa dice mucho más. `ds_from_image.py FLYER --solo-paleta` enseña los grupos de color.
- **Vista previa** (`preview.png` en la carpeta del borrador): maquetas PIL de título, contenido sobre un fotograma real, eco y cierre, más dos renders reales de FilmCraft y la paleta con contrastes. Si la columna FilmCraft difiere de la PIL, manda FilmCraft. Enséñala siempre: Read y, si la herramienta `SendUserFile` está disponible, envíala; si no, da la ruta absoluta.
- **Rehacer o tirar**: `crear` falla si el borrador ya existe; `--forzar` lo rehace. Tanto `--forzar` como `descartar` mueven el viejo a `<datos>/papelera/<id>-<fecha>` (`<datos>` = `$CLAUDE_PLUGIN_DATA` o `~/.cache/filmcraft-studio`): se recupera moviéndolo de vuelta a `<datos>/borradores/<id>`. `descartar` solo toca borradores.
- **Ciclo**: cada `modificar` sube `estado.iteracion` y guarda el cambio. No apruebes por el usuario: `aprobar` solo cuando lo diga. `aprobar` falla si `${CLAUDE_PLUGIN_ROOT}/bin/cine validar-ds <id>` da errores (contraste < 2,5:1, fuente no instalada, assets que faltan); `--estricto` trata los avisos como errores y `--todos` recorre el catálogo.
- Borradores en `<datos>/borradores/`, catálogo en `<datos>/design-systems/` (`<datos>` = `${CLAUDE_PLUGIN_DATA}` o `~/.cache/filmcraft-studio`; otra carpeta con `FILMCRAFT_DS_CATALOGO`). Modificar uno aprobado crea un borrador; al reaprobarlo, la versión anterior se guarda como `<id>.anterior-<fecha>`.

## DS de promo (render por código)

Los `promo-*` del catálogo (`ds_studio.py catalogo`; no los enumeres de memoria) sirven para promos de repos y lanzamientos (skill `promo-codigo`).
- **Mismo esquema**: valen para FilmCraft, con pistas canónicas, roles, tarjetas, SFX y grade, salvo los roles que solo trae el brutalista (`concepto`, `escalon`, `nombre`): un plan que los use sobre un DS de promo falla.
- **Clave `promo`**: lo que usa el render por código (BPM, firma, cámara, tintas).
- **Música ya masterizada**: el motor de código la entrega a −14 LUFS, así que `musica.sin_voz_db` = 0.

Herramientas propias:
- `promo_fondos.py <id>`: fondos de tarjeta con la piel de la gramática.
- `promo_sfx.py <gramatica> <dir>`: kit de SFX sintetizado.
- `promo_gradmap.py DS ENTRADA SALIDA`: pasada de gradient map (`promo.mapas`, gramática termo) sobre una imagen o un video.
- `promo_preview.py <id> <video>`: vista previa desde un render real (necesita el video ya hecho).
- Fotogramas fijos antes de animar: la escena con los segundos como último argumento (`… 0.6,9.2`), ver `promo-codigo`.

Las maquetas PIL (`ds_preview.py`, la vista previa de `crear`/`modificar`) son de la gramática brutalista: con un DS de promo pueden fallar o no reflejar el cambio. Para iterar un DS de promo, cambia su `ds.json` y saca fotogramas con la escena; no te fíes de su `preview.png`.

Reglas de cada gramática: `${CLAUDE_PLUGIN_ROOT}/skills/promo-codigo/references/gramaticas.md`.

## Adaptar un DS

Copia la carpeta, cambia `id`, `nombre`, `paleta` o `marca`, y regenera los fondos con `ds_assets.py <id>` (brutalista) o `promo_fondos.py <id>` (promo). No toques la gramática sin una razón de oficio (`${CLAUDE_PLUGIN_ROOT}/skills/editor-filmcraft/references/estilo-brutalista.md`).

## Elegir DS automáticamente

`${CLAUDE_PLUGIN_ROOT}/bin/cine elegir-ds --flyer F --ruta <carpeta> --para camara|promo [--json]` puntúa cada DS con la media de las señales que haya: rutas (`match.rutas`, palabras enteras en los nombres de carpeta) y parecido de paleta con el flyer (ΔE en OKLab; 50 % cada una si están las dos). Sin flyer, `--paleta "#a,#b"` da los colores a mano. `--para camara` deja fuera los `promo-*` (un plan de material grabado con roles brutalistas falla sobre ellos). Con `--ruta`, por debajo de 0,5 conviene crear uno nuevo; **sin `--ruta` la puntuación es solo el parecido de color** (≥ 0,9 es el mismo estilo; < 0,7, crea uno).
