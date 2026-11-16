# Guion

El guion es la intención por escenas: **qué tiene que entender el espectador en cada momento** y con qué se le enseña. No lleva tiempos de fuente: eso es `plan.json`, que se escribe después, cuando las escenas ya existen como archivos.

## guion.json

```json
{
 "version": 1,
 "titulo": "kindling v0.20 · vertical",
 "tipo": "promo-repo",
 "formato": "9:16",
 "duracion_s": 27,
 "bpm": 134,
 "ds": "promo-riso",
 "idea": "Tu docker compose, en microVMs que se congelan solas, nativo en tu Mac.",
 "cta": "kling upgrade · github.com/juan52878911/kindling",
 "hechos": [
  {"id": "arranque", "dato": "demo is up in 0.5s", "fuente": "grabación VHS term_v.mp4, fotograma 80"},
  {"id": "thaw-hv", "dato": "thaw + primer exec 36 ms p50 (M4, kling-hv)", "fuente": "kindling docs/backend-hv.md:233"}
 ],
 "escenas": [
  {"id": "gancho", "beats": 8, "objetivo": "ver el resultado antes de saber qué es",
   "pantalla": ["❯ kling compose up -d", "0.5s", "DOCKER / COMPOSE / EN MICROVMS. / EN TU MAC."],
   "voz": null, "motor": "codigo", "hechos": ["arranque"], "sfx": ["tecla", "gancho"]},
  {"id": "demo", "beats": 22, "objetivo": "creer que es real",
   "pantalla": ["ARRANQUE EN CALIENTE", "NATIVO EN APPLE SILICON", "CONGELADO · 0 RAM", "DESPIERTA SOLO"],
   "motor": "pantalla+codigo", "material": "VHS: compose up, uname -sm, stop, exec ping",
   "firma": "congelar = una sola tinta, la cinta frena"},
  {"id": "cierre", "beats": 4, "objetivo": "saber cómo probarlo", "pantalla": ["KINDLING v0.20", "brew · kling upgrade"],
   "motor": "codigo", "sfx": ["cierre"]}
 ]
}
```

| Campo | Para qué |
|---|---|
| `tipo`, `formato`, `duracion_s`, `bpm` | Del brief y de `tipos.md`. Sin música: `bpm` = null y duraciones en `s` |
| `idea` | Lo que el espectador debe repetir después de verlo, en una frase. Si no cabe en una frase, el guion no está listo |
| `hechos` | Cada afirmación con su fuente. Las escenas los citan por `id`; el informe los lista |
| `escenas[].beats` o `s` | Duración. Con música, en beats (compases de 4) |
| `objetivo` | Qué cambia en la cabeza del espectador. El crítico lo usa para juzgar la escena |
| `pantalla` | Textos en orden de aparición, ya con su redacción final |
| `voz` | Texto de la voz en off (o `null`). Cuenta unas 2,5 palabras por segundo |
| `motor` | `camara`, `codigo`, `pantalla`, `ia`, `foto`, `tarjeta` o combinaciones (`pantalla+codigo`) |
| `material` | Qué hay que grabar o qué fuente usar |
| `firma`, `sfx`, `transicion` | Lo que da carácter a la escena, en el vocabulario del DS |

## Cómo escribirlo

1. **La idea, primero.** Una frase. De ella salen el gancho y el cierre.
2. **El gancho enseña la prueba**: una cifra real, una salida de terminal, el antes y el después visual o la frase más fuerte del ponente. Nunca un logo animado ni un título.
3. **Una escena, un objetivo.** El texto en pantalla es corto y concreto: verbos y cifras, sin adjetivos de marketing ("potente", "revolucionario").
4. **Cifras absolutas de lo que hay hoy.** Los "antes y después" solo si el tema es la mejora. Cada cifra lleva su contexto (p50, máquina) en la escena o en el pie.
5. **Una firma.** Un recurso visual y sonoro ligado a lo que hace el producto, que vuelve dos veces (en la demo y en una capacidad).
6. **El final se puede copiar**: nombre, versión, un comando y una URL.
7. **Comprobación de lectura**: suma las palabras de pantalla y de voz de cada escena y comprueba que caben en su duración (3 palabras/s leídas, 2,5 dichas). Si no caben, recorta texto, no alargues la escena.

## Del guion al plan

Cuando cada escena tiene su archivo (`motores.md`), el `plan.json` lleva un bloque por escena:
- `src` es el archivo de la escena;
- `in` y `out` salen de su duración;
- `tipo` es `contenido`, o `tarjeta`/`cierre` si las hace el compilador con la marca del DS;
- `textos` son los rótulos que no van quemados en el render.

Si un motor ya dibujó el texto, el bloque no lo repite.
