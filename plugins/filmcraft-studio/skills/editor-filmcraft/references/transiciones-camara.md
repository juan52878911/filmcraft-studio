# Transiciones con los movimientos de la cámara

Técnica propia probada en el reel #RetoCertEAN. Juan graba con el móvil y hace paneos rápidos entre el ponente, la pantalla y el público. Esos barridos son transiciones gratis, más orgánicas que cualquier matte.

## 1. Detectar los barridos

```bash
python3 scripts/camera_motion.py scan VIDEO.mp4             # escaneo grueso cada 0,5 s
python3 scripts/camera_motion.py fine VIDEO.mp4 32.4 34.6   # afinado por fotograma en una ventana
```

- `scan` lista ventanas con desplazamiento global grande (dx, dy en px/s sobre un fotograma reducido) o mucha diferencia entre fotogramas.
- `fine` da la velocidad cada ~0,1 s y una barra visual. El pico de la barra es el mejor punto de corte.
- **Signo:** `dx < 0` significa que el contenido se mueve a la izquierda (la cámara gira a la derecha). Para transicionar importa la dirección del contenido.
- El escaneo grueso cada 0,5 s puede dar falsos picos: confirma siempre con `fine` y una hoja de fotogramas.

## 2. Tipos de transición

| Situación | Técnica |
|---|---|
| Dos tomas con barrido en la misma dirección | **Corte a mitad de barrido:** la saliente acaba en el pico de su barrido y la entrante empieza en el pico del suyo. Desenfoque 0 → ~20 de salida y ~20 → 0 de entrada, más `whoosh-largo` |
| Las dos tomas pasan por pared blanca o fondo neutro desenfocado | **Match cut sobre el desenfoque.** Fue el mejor del reel: barrido a la pared blanca → la pared de la otra toma |
| Solo la entrante tiene barrido | **Continuación sintética:** la saliente se desliza en la dirección del barrido entrante (posición 0 → +0,45 del ancho en ~14 f) con desenfoque creciente. Debajo hay un fondo (rejilla navy), así que nunca aparece negro |
| La cámara se aleja de algo y luego vuelve | **Insertar gráficos durante el alejamiento:** un carrusel de producto que entra en el sentido del paneo y sale en el del siguiente. Al volver, el plano real revela la escena (Natalia entregando regalos) |
| Reencuadre lento y largo entre dos momentos | **Speed ramp ×4** del tramo intermedio, con desenfoque 22 → 0. Usa `interpolation: opticalFlow` y silencia su audio |
| Celebración pequeña o lejana dentro del plano | **Zoom dirigido:** escala hasta ~1,8 anclada al borde donde está la persona (posición `1 − s` en x) mientras la cámara se acerca. Así el sujeto entra al centro solo |

## 3. Reglas

- La dirección del contenido saliente y la del entrante deben coincidir (o la del gráfico que se inserta). Si no coinciden, la transición se nota "rota".
- Un barrido con habla encima no se recorta a ciegas. Comprueba en la transcripción que no partes una palabra; si la hay, silencia el audio del barrido y cubre con whoosh.
- El fondo de la secuencia (pista 0) debe ser la rejilla de marca, para que cualquier deslizamiento muestre diseño y no negro.
- Verifica cada transición con 3–4 fotogramas: antes, pico, después.
