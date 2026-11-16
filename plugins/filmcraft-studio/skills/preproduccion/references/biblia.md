# La biblia

`W/preproduccion/biblia.json` es la fuente de verdad del video (`W` según «Carpeta de trabajo W» del SKILL.md de la skill). Las rutas de dentro (`fotogramas`, `guion`, `referencias`) son relativas a `W`. `biblia.md` es la misma información en tablas para el usuario. La producción la lee y la verificación final la recorre criterio a criterio.

```json
{
 "version": 1,
 "estado": "borrador",
 "iteracion": 3,
 "pedido": "promo vertical de la v0.20 de kindling",
 "respuestas": {
  "plataforma": {"valor": "Reels 9:16, 25 s", "origen": "dado", "ronda": "A"},
  "publico": {"valor": "devs que ya usan Docker Compose", "origen": "inferido", "por": "README:12"}
 },
 "referencias": [
  {"archivo": "referencias/gradient-maps-vol02.jpg", "ficha": "preproduccion/referencias/fichas/gradient-maps-vol02.json",
   "medida": {"paleta": ["#E9E4D4", "#3466E0"], "luz": 0.71},
   "aspecto": "…", "regla": "mapa de temperatura sobre la intensidad",
   "significado": "calor = energía", "donde_no": "lo frío queda nítido con filo rojo; < 30 % caliente",
   "variacion": "baja a la mitad cada dos letras desde la fuente", "anatomia": "halo 22–30 px corrido (−10, +8)",
   "tomar": ["la escala de temperatura", "el desregistro"], "no_tomar": ["la composición del poster", "su texto"]}
 ],
 "anti_referencias": ["gradiente morado + Inter", "tarjetas de feature en rejilla"],
 "concepto": {
  "idea": "Tu docker compose, en microVMs que se congelan solas.",
  "metafora": "temperatura = estado: caliente corre, frío congelado",
  "reglas": ["el calor es del lugar, no de la letra", "lo frío queda nítido con su filo", "el cierre acaba congelado"]
 },
 "ds": {"id": "promo-gradient-map", "estado": "aprobado", "gramatica": "termo@1",
        "fotogramas": ["preproduccion/direcciones/b_gancho.png", "preproduccion/direcciones/b_firma.png"]},
 "movimientos": [
  {"nombre": "frente_llama", "significa": "arranque: todo se enciende", "escenas": ["gancho"]},
  {"nombre": "hielo_que_sube", "significa": "congelar: la VM se duerme", "escenas": ["terminal", "cierre"]}
 ],
 "sonido": {"musica": "sintetizada", "genero": "UK garage 2-step", "bpm": 134,
            "firma": "filtro a 180 Hz + campana FM al congelar", "sfx": ["chispa", "ignicion", "congelar"],
            "master": "-14 LUFS, -1 dBTP"},
 "guion": "guion.json",
 "motores": [
  {"escena": "gancho", "motor": "codigo", "herramienta": "PIL + numpy"},
  {"escena": "terminal", "motor": "pantalla", "herramienta": "VHS"},
  {"escena": "titulo-3d", "motor": "3d", "herramienta": "Blender (motor_blender.py)"}
 ],
 "entregables": [{"archivo": "promo-9x16.mp4", "lienzo": "1080x1920", "fps": 30, "max_mb": 30}],
 "modo": "asistido",
 "criterios": [
  {"id": "c1", "que": "1080x1920, 23–27 s", "como": "ffprobe"},
  {"id": "c2", "que": "'0.5s' visible antes de 1,5 s", "como": "hoja de fotogramas a 0,5/1,0/1,5 s"},
  {"id": "c3", "que": "ningún plano con halo en todo el texto", "como": "hoja + critico-estilo"},
  {"id": "c5", "que": "estilo de la referencia: ≥ 75 % de las métricas de estilo dentro de tolerancia; sin riesgo de clon",
   "como": "referencias.py --comparar referencias/gradient-maps-vol02.jpg <fotograma firma>"},
  {"id": "c6", "que": "clave alta (mediana de luminancia 0,85–0,95) y temperatura −0,1 ± 0,15 en gancho y cierre",
   "como": "ref_metricas.py <fotograma> --json → valores.mediana, color.temperatura"},
  {"id": "c4", "que": "-14 LUFS ±1, pico ≤ -1 dBTP", "como": "ebur128"}
 ],
 "criticas": [{"iteracion": 2, "veredicto": "correcto pero genérico", "cambios": ["cifras a sangre", "…"]}],
 "pendientes": [],
 "cambios": [{"iteracion": 3, "que": "el cierre acaba congelado", "pedido_por": "usuario"}]
}
```

## Reglas

- **Estados de la biblia:**
  - `borrador` mientras se pregunta;
  - `propuesta` cuando se enseña para aprobar;
  - `aprobada` solo con un sí explícito del usuario;
  - `inferida` en el modo sin preguntas;
  - `expres` en el modo exprés (respuestas `inferido`/`defecto` y criterios por defecto de `preguntas.md`).
- **`origen` de cada respuesta:** `dado`, `inferido` (con `por`) o `defecto`.
- **Referencias:** `ficha` apunta a la ficha completa (`schemas/referencia.schema.json`): las métricas, la capa `filosofia` y la traducción a video. Los campos `regla`, `significado`, `donde_no`, `variacion`, `anatomia`, `tomar` y `no_tomar` de la biblia son el resumen de esa capa.
- **Criterios medibles de estilo:** salen de `agregado.json` → `comunes` (lo que comparten todas las referencias) o de `reproducir` de una ficha: métrica, objetivo y tolerancia. Solo entran los del grupo `estilo`. Los del grupo `composicion` se usan al revés: si un fotograma propio coincide con una referencia en la maqueta (`riesgo_clon`), es un fallo. Dos o tres criterios bastan; elige los que sostienen la metáfora.
- **Criterios:** cada uno dice qué se comprueba y cómo. Al entregar, `informe.md` lleva una tabla con los criterios cumplidos, los que no y los que no se pudieron comprobar, cada uno con su evidencia.
- **Brief:** la producción genera `W/brief.json` de `respuestas` (ver `director-video`, paso 4). Si difieren, manda la biblia.
- **Cambios:** cada nota del usuario después de aprobar suma una entrada en `cambios` y sube `iteracion`. Si contradice un criterio, el criterio se actualiza en la misma entrada.
