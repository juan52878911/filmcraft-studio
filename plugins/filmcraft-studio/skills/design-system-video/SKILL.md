---
name: design-system-video
description: Catálogo de design systems de video y su ciclo crear → vista previa → modificar → aprobar (paleta, tipografías, roles de texto, animaciones, transiciones, SFX, música, grade y estructura) para montar en FilmCraft con un estilo coherente. Úsala cuando pidan "qué estilos tengo", "quiero un estilo cálido/minimal/…", "crea el estilo desde este flyer o logo", "cambia los colores", "misma gramática con otra paleta", "vista previa del estilo", o antes de montar un evento cuya marca no exista todavía.
---

# Design systems de video

Un DS es `design-systems/<id>/ds.json` + `assets/`. Separa dos capas:

- **Gramática** (`gramatica`, p. ej. `brutalista@1`): roles de texto, animaciones, zonas, continuidad, transiciones, mapa de SFX, música, grade, objetivos de audio, estructura y ritmo. Es el oficio; cambia poco.
- **Piel**: `paleta`, `fuentes`, `marca` (textos fijos), `fondos` y `mattes` generados. Cambia por evento.

Esquema comentado: `${CLAUDE_SKILL_DIR}/references/esquema.md`. Ejemplo completo y aprobado: `${CLAUDE_PLUGIN_ROOT}/design-systems/sbg-brutalista-s5/`.
Los DS que crea el usuario van a `${CLAUDE_PLUGIN_DATA}/design-systems/` (sobreviven a actualizaciones del plugin). En Bash esa variable no existe: los scripts usan `~/.cache/filmcraft-studio/` si no la reciben; pásala con `CLAUDE_PLUGIN_DATA=… python3 …` si quieres otra ruta.

## Catálogo y ciclo de aprobación (`ds_studio.py`)

```bash
S=${CLAUDE_PLUGIN_ROOT}/scripts
python3 $S/ds_studio.py catalogo --hoja catalogo.png            # aprobados + precargados, con miniatura
python3 $S/ds_studio.py crear --id <slug> --spec '<json>' [--flyer F] [--base sbg-brutalista-s5] --frame <foto real>
python3 $S/ds_studio.py modificar <id> --spec '<solo lo que cambia>' --frame <foto real>
python3 $S/ds_studio.py aprobar <id>                            # valida y pasa al catálogo
```

- **Desde una descripción**: tradúcela a un `spec` (formato en la cabecera de `ds_studio.py`): paleta en hex (5 colores: fondo, claro, 3 acentos), fuentes instaladas en el Mac (`familia` y `estilo` como los nombra macOS), `escala_texto`, `animacion` (`suave`, `normal`, `energica`) y TODOS los textos de `marca` (barra, hashtag, título en líneas cortas, pill, palabras y línea de cierre, pie, CTA). Lo que no des se hereda del DS base: dilo.
- **Desde un flyer o logo**: `--flyer` saca la paleta por k-means (k = 12, recorte automático de marcos y capturas, color "vivo" de cada grupo; acentos derivados por rotación de tono si faltan, anotados en `derivado_de`). El `spec` puede sobrescribir lo que quieras encima. Mira el flyer antes y copia de él los textos de marca (no hay OCR). `ds_from_image.py FLYER --solo-paleta` enseña los grupos de color.
- **Vista previa** (`preview.png` en la carpeta del borrador): maquetas PIL de título, contenido sobre un fotograma real, eco y cierre, más dos renders reales de FilmCraft y la paleta con contrastes. Si la columna FilmCraft difiere de la PIL, manda FilmCraft. Enséñala siempre (Read + SendUserFile).
- **Ciclo**: cada `modificar` sube `estado.iteracion` y guarda el cambio. No apruebes por el usuario: `aprobar` solo cuando lo diga. `aprobar` falla si `ds_validate.py` da errores (contraste < 2,5:1, fuente no instalada, assets que faltan).
- Borradores en `<datos>/borradores/`, catálogo en `<datos>/design-systems/` (`<datos>` = `${CLAUDE_PLUGIN_DATA}` o `~/.cache/filmcraft-studio`; otra carpeta con `FILMCRAFT_DS_CATALOGO`). Modificar uno aprobado crea un borrador; al reaprobarlo, la versión anterior se guarda como `<id>.anterior-<fecha>`.

## DS de promo (render por código)

`promo-brasa-escarcha` (temperatura@1, 16:9), `promo-blueprint` (plano@1, 16:9) y `promo-riso` (riso@1, 9:16 y 16:9) sirven para promos de repos y lanzamientos (skill `promo-codigo`).
- **Mismo esquema**: valen para FilmCraft, con pistas canónicas, roles, tarjetas, SFX y grade.
- **Clave `promo`**: lo que usa el render por código (BPM, firma, cámara, tintas).
- **Música ya masterizada**: el motor de código la entrega a −14 LUFS, así que `musica.sin_voz_db` = 0.

Herramientas propias:
- `promo_fondos.py <id>`: fondos de tarjeta con la piel de la gramática.
- `promo_sfx.py <gramatica> <dir>`: kit de SFX sintetizado.
- `promo_preview.py <id> <video>`: vista previa desde un render real, en lugar de las maquetas PIL.

Reglas de cada gramática: `promo-codigo/references/gramaticas.md`.

## Adaptar un DS

Copia la carpeta, cambia `id`, `nombre`, `paleta` o `marca`, y regenera los fondos con `ds_assets.py <id>`. No toques la gramática sin una razón de oficio (`editor-filmcraft/references/estilo-brutalista.md`).

## Elegir DS automáticamente

`brief_infer.py --solo-ds --flyer F --ruta <carpeta>` puntúa cada DS: 50 % rutas (`match.rutas`) y 50 % parecido de paleta con el flyer. Por debajo de 0,5 conviene crear uno nuevo.
