---
name: director-video
description: Director generalista de video. Convierte cualquier pedido de video (promo de un repo o de una release, lanzamiento de producto, demo, tutorial, explainer, reel o resumen de un evento, entrevista o testimonio, short vertical, pitch, changelog, loop para un README…) en un brief, un guion por escenas con reglas de oficio y un plan de producción que reparte cada escena al mejor motor (FilmCraft para material de cámara, render por código, grabación de pantalla o terminal, IA generativa de relleno, voz y música), y lo ensambla y verifica en FilmCraft con un design system. Úsala como entrada cuando pidan "hazme un video de/para…", "quiero un video que explique…", "un reel", "un tutorial en video", "un anuncio", "un video para LinkedIn/X/Reels/YouTube", o `/filmcraft-studio:video`, aunque no digan qué herramienta usar.
---

# Director de video

Todo video sale de la misma cadena: **brief → tipo → guion → design system → producción por escena → ensamblado en FilmCraft → verificación → entrega**. Lo que cambia según el tipo es la plantilla del guion y qué motor hace cada escena. Esta skill decide y coordina; el oficio fino vive en `editor-filmcraft`, los estilos en `design-system-video` y el render por código en `promo-codigo`.

Referencias (léelas cuando toque, no todas de golpe):
- `${CLAUDE_SKILL_DIR}/references/tipos.md`: los tipos de video, cada uno con su estructura, duración, formato y reglas.
- `${CLAUDE_SKILL_DIR}/references/guion.md`: cómo escribir el guion y el formato de `guion.json`.
- `${CLAUDE_SKILL_DIR}/references/motores.md`: qué motor hace qué escena, con qué herramienta y cómo entra en FilmCraft.
- `${CLAUDE_SKILL_DIR}/references/reglas.md`: el listón profesional y la lista de verificación.

## Flujo

1. **Brief.** Completa el brief con la skill `brief-video`: objetivo, público, plataforma, duración, tono, obligatorios, lo que hay que evitar y CTA, cada campo con su origen. Añade `tipo` (de `tipos.md`) y `formato` (16:9, 9:16, 1:1). Si el pedido es ambiguo en algo que cambia el video (para quién es, dónde se publica), pregunta una sola vez. Todo lo demás se infiere y se marca.
2. **Inventario y hechos.** Lista el material que existe: videos, fotos, logos, el repo, la app, la voz. Saca los hechos que el video va a afirmar, cada uno con su fuente (`fichero:línea`, URL o la persona que lo dijo). Si hay mucho que leer, delega en un subagente. Ninguna cifra ni afirmación comparativa entra al guion sin fuente.
3. **Guion.** Escribe `guion.json` con la plantilla del tipo (`guion.md`): escenas con objetivo, duración, texto en pantalla, voz y motor. Enséñalo como tabla. En modo asistido, espera el visto bueno; en headless, sigue y déjalo anotado en el informe.
4. **Design system.** Elige uno del catálogo o crea otro (skill `design-system-video`). Para decidir entre estilos, enseña 2 fotogramas fijos por estilo: el gancho y la escena firma. El DS fija la paleta, las tipografías, los roles de texto, las transiciones, los SFX, la música, el grade y el audio de TODAS las escenas, sea cual sea el motor que las haga.
5. **Producción por escena** según `motores.md`. Cada escena termina siendo un archivo de video, imagen o audio al lienzo y fps del DS:
   - `camara`: material grabado, que pasa por análisis.
   - `codigo`: render reproducible.
   - `pantalla`: grabación real con VHS, Screen Studio o Cap.
   - `ia`: solo planos de relleno, desde imagen propia y con permiso.
   - `foto` y `tarjeta`: se resuelven en el compilador.
   - Voz (TTS o grabada) y música, en la rejilla de beats del guion.
6. **Ensamblado en FilmCraft.** `analyze_media.py` sobre todas las fuentes, incluidas las renderizadas (`--sin-vision` si no tienen personas). Después un `plan.json` con un bloque por escena (formato en `montaje-headless/references/plan.md`), y luego `plan_compile.py` y `apply_plan.py`, en `--headless` o `--live`. FilmCraft pone los subtítulos, la barra de marca, los SFX ligados a eventos, la música con ducking, el grade y el limitador desde el DS. Si la música se generó por código para todo el video, pásala en `musica.archivo`.
7. **Verificación.** `verify.py`, hojas de fotogramas en los tiempos clave, loudness y pico, y la lista de `reglas.md`. Al final pasa el agente `critico`. Arregla y vuelve a compilar solo lo afectado; las notas del usuario entran por la skill de notas (`/filmcraft-studio:nota`).
8. **Entrega.** Exporta solo cuando lo pidan (`/filmcraft-studio:entregar`), en los formatos de la plataforma. Escribe `informe.md` con el brief, el guion, las fuentes de cada afirmación, los motores usados, las medidas y lo que no se pudo verificar (por ejemplo, el audio sin escuchar).

## Reglas que no se negocian

- Lo que el video dice del producto o del evento es real: grabación, dato con fuente o cita. Nada de UI inventada ni cifras sin origen.
- No se usan logos ni marcas de terceros, salvo material con licencia que aporte el usuario. Se nombran con texto descriptivo.
- La IA generativa (video, voz clonada, música) solo entra con permiso, sin imitar a personas reales ni a artistas, y respetando la licencia de la herramienta.
- Nada se publica ni se sube: se entrega el archivo o el proyecto.
- Si algo no se pudo comprobar, se dice en la entrega en vez de darlo por bueno.
