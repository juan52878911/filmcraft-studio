---
description: "Crea un design system de video desde una descripción, un flyer o un logo, con vista previa y aprobación"
argument-hint: "<descripción | flyer> [--id evento]"
disable-model-invocation: true
---

Crea un DS siguiendo la skill `design-system-video` (sección «Catálogo y ciclo de aprobación»): el ciclo crear → vista previa → modificar → aprobar, los comandos de `ds_studio.py` y las reglas de fuentes están allí; no los repitas de memoria. Entrada: $ARGUMENTS

- Si hay imagen (flyer, logo), mírala con Read y pásala con `--flyer`. Si hay descripción, tradúcela al `spec` completo y pregunta lo que falte de marca.
- Antes de llamar a los scripts: `export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}` (así el DS aprobado va al catálogo del plugin y no a `~/.cache`). Scripts en `${CLAUDE_PLUGIN_ROOT}/scripts`.
- Para enseñar `preview.png`: Read y, si la herramienta `SendUserFile` está disponible, envíala; si no, da la ruta absoluta.
