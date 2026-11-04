---
description: Crea un video promocional de un repositorio o de su última versión, renderizado por código con un design system de promo
argument-hint: <repo o ruta> [--estilo promo-brasa-escarcha|promo-blueprint|promo-riso] [--formato 16:9|9:16]
---

Sigue la skill `promo-codigo`. Entrada: $ARGUMENTS

1. Lee qué trae la versión (CHANGELOG, tags, release) y propone la idea central y 3–4 capacidades con su fuente. Confirma las afirmaciones comparativas contra medidas del repo antes de escribirlas.
2. Graba la terminal real con VHS y mide en qué fotograma sale cada resultado.
3. Si no hay estilo, enseña dos fotogramas fijos por cada DS `promo-*` (o uno nuevo) y deja elegir.
4. Escribe la línea de tiempo en beats, las escenas y el audio partiendo de `${CLAUDE_PLUGIN_ROOT}/promo/kindling-v0.20/`; verifica con la hoja de fotogramas y `ebur128`; entrega el MP4 (SendUserFile) y limpia lo que creaste en el daemon.
