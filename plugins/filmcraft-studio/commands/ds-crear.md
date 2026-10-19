---
description: Crea un design system de video desde una descripción, un flyer o un logo, con vista previa y ciclo de aprobación
argument-hint: <descripción | flyer> [--id evento]
---

Crea un DS siguiendo la skill `design-system-video` (sección "Catálogo y ciclo de aprobación"). Entrada: $ARGUMENTS

1. Si hay imagen (flyer, logo), mírala (Read) y úsala con `--flyer`. Si hay descripción, tradúcela a un `spec` completo (paleta, fuentes instaladas, escala, animación y todos los textos de marca); pregunta lo que falte de marca.
2. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ds_studio.py crear --id <slug> --spec '…' [--flyer …] --frame <foto real del material si la hay>`.
3. Enseña `preview.png` (Read + SendUserFile), la paleta y los avisos de validación. Pregunta: ¿lo apruebas o qué cambio?
4. Cambios → `ds_studio.py modificar <id> --spec '<cambios>'` y vuelve al paso 3. Aprobado → `ds_studio.py aprobar <id>`.
