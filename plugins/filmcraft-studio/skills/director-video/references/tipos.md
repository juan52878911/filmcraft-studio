# Tipos de video

Cada tipo fija una **plantilla de escenas**, una duración, un formato por defecto y sus reglas propias. Las duraciones de escena son orientativas; en piezas con música, cuadra cada escena a compases (4 beats). Motores: `camara`, `codigo`, `pantalla`, `ia`, `foto`, `tarjeta` (ver `motores.md`).

| Tipo | Para qué | Duración | Formato | DS de partida |
|---|---|---|---|---|
| `promo-repo` | Un repositorio o lo nuevo de una release | 20–30 s | 16:9 y 9:16 | `promo-*` |
| `lanzamiento` | Anuncio de un producto o funcionalidad | 30–60 s | 16:9 + 9:16 | `promo-*` o uno de marca |
| `demo` | Enseñar el producto haciendo una tarea | 45–120 s | 16:9 | `promo-blueprint` |
| `tutorial` | Que alguien aprenda a hacer X | 2–8 min (o 60 s en vertical) | 16:9 | uno sobrio, de marca |
| `explainer` | Explicar un concepto o una arquitectura | 60–120 s | 16:9 | `promo-blueprint` |
| `reel-evento` | Resumen de una charla o un evento | 45–60 s | 9:16 | `sbg-brutalista-s5` o uno desde el flyer |
| `entrevista` | Testimonio o conversación | 60–180 s (+ clips de 20–40 s) | 16:9 + 9:16 | sobrio |
| `short` | Un consejo o una idea, nativo de vertical | 15–45 s | 9:16 | cualquiera |
| `pitch` | Contar un proyecto a inversores o a un jurado | 60–120 s | 16:9 | de marca |
| `changelog` | Novedades de una semana o de una versión, en serie | 30–45 s | 16:9 o 1:1 | el mismo DS en cada entrega |
| `readme-loop` | Loop sin audio para un README o una web | 6–15 s | 16:9 | el del proyecto |

## Plantillas

**promo-repo / lanzamiento**
1. Gancho, 1–4 s: el resultado ya pasando (cifra real, salida de terminal). `codigo` o `pantalla`.
2. Qué es, 2–4 s: una frase y quién lo usa. `codigo` o `tarjeta`.
3. Demo real, 8–12 s: la cámara sobre la grabación, una acción cada vez. `pantalla` + `codigo`.
4. Firma, 2–4 s: lo único que hace este proyecto (en kindling, congelarse).
5. Capacidades, 3–4 escenas de 2–3 s: cifras absolutas con fuente.
6. Ecosistema o compatibilidad, 2–4 s: integraciones y plataformas, con texto y sin logos de terceros.
7. Cierre, 2–4 s: nombre, versión, cómo instalar y URL.

**demo**
1. El problema en una frase, 3–5 s.
2. El resultado final, 3 s.
3. La tarea paso a paso en tiempo real, con zooms y rótulos en cada clic.
4. El resultado otra vez.
5. CTA.

Sin cortes que escondan esperas: si algo tarda, se acelera y se dice.

**tutorial**
1. Qué vas a lograr, con el resultado delante.
2. Requisitos.
3. Pasos numerados, uno por escena, cada uno con su comando o su clic y la verificación de que funcionó.
4. Errores típicos.
5. Resumen.
6. Siguiente paso.

Voz en off o subtítulos completos. Capítulos con marca de tiempo en la descripción.

**explainer**
1. Pregunta o tensión.
2. El modelo mental en un diagrama que se construye.
3. Un ejemplo concreto.
4. Qué cambia para el espectador.
5. Cierre.

Un diagrama que crece vale más que muchos textos.

**reel-evento**
Sigue la estructura del DS (`estructura.orden`):
1. Gancho: la frase más fuerte.
2. Título.
3. Contenido.
4. Lo humano.
5. Invitados.
6. Fotos.
7. Cierre.

Material de `camara` con análisis; el montaje es `montaje-headless` o `montaje-asistido`.

**entrevista**
1. Pregunta en pantalla.
2. Respuesta en planos de 5–15 s, cortados en palabra, con *jump cuts* con *punch*.
3. Rótulo con nombre y cargo al primer plano de cada persona.
4. B-roll que ilustra lo que se dice.
5. Cierre.

**short**
1. Gancho de 1 s con texto grande.
2. Una sola idea en 3–5 golpes.
3. Payoff.
4. Loop o CTA.

Titulares ajustados al ancho y franja de rótulos lejos de la interfaz de la app.

**pitch**
1. Problema.
2. Por qué ahora.
3. Solución con demo.
4. Tracción (cifras con fuente).
5. Equipo.
6. Lo que pides.

**changelog**
Una plantilla fija por entrega, para que la serie se reconozca:
1. Cabecera con la versión.
2. 3 cambios, uno por escena.
3. Cómo actualizar.

**readme-loop**
La demo más corta que enseña el valor, sin audio. El primer y el último fotograma coinciden. Ocupa menos de 10 MB.

## Reglas comunes

- El gancho enseña, no promete. El producto aparece en el primer segundo, no en el 18 (la media del sector en 2026).
- Una idea por escena. Si una escena necesita dos frases, son dos escenas.
- El texto en pantalla se lee: unas 3 palabras por segundo y al menos 1 s por rótulo. Si no da tiempo, sobra texto.
- Cada video tiene un solo CTA.
