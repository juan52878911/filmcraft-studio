"""Plantilla de escena 3D para motor_blender.py: un titular extruido con la fuente y la paleta del DS.

El titular entra girado 70° y se asienta en el primer segundo; la cámara se acerca despacio el resto del plano
y una luz de contra con el acento2 recorta el borde. Ajusta el ancho del texto al 86 % del encuadre.

Parámetros (--param): texto=KINDLING, rol=titular, color=acento1, contra=acento2, entrada=1.0 (segundos)
Ejemplo: motor_blender.py scripts/blender/titular.py --ds promo-riso --out t.mp4 --segundos 3 --param texto=HOLA
"""
import math

texto = fc.p.get("texto", "TITULAR")
entrada = float(fc.p.get("entrada", 1.0))
fc.fondo("fondo")

cu = bpy.data.curves.new("titular", type="FONT")
cu.body = texto
if fc.fuente(fc.p.get("rol", "titular")):
    cu.font = fc.fuente(fc.p.get("rol", "titular"))
cu.align_x, cu.align_y = "CENTER", "CENTER"
cu.extrude = 0.08
cu.bevel_depth = 0.006
txt = bpy.data.objects.new("titular", cu)
bpy.context.collection.objects.link(txt)
txt.data.materials.append(fc.material(fc.p.get("color", "acento1"), emision=0.15, rugosidad=0.35))
bpy.context.view_layer.update()

cam_data = bpy.data.cameras.new("cam")
cam_data.sensor_fit = "HORIZONTAL"
cam_data.lens = 50
cam = bpy.data.objects.new("cam", cam_data)
bpy.context.collection.objects.link(cam)
fc.escena.camera = cam
fov = 2 * math.atan(cam_data.sensor_width / 2 / cam_data.lens)
d = txt.dimensions.x / 0.86 / (2 * math.tan(fov / 2))       # distancia a la que el texto ocupa el 86 %

for nombre, rol, pos, fuerza, tam in (("clave", "claro", (-2, -3, 4), 900, 4),
                                     ("contra", fc.p.get("contra", "acento2"), (1.5, 3, -1), 1500, 2)):
    ld = bpy.data.lights.new(nombre, type="AREA")
    ld.color = fc.color(rol)[:3]
    ld.energy = fuerza * d * d / 16
    ld.size = tam
    lo = bpy.data.objects.new(nombre, ld)
    lo.location = tuple(v * d / 4 for v in pos)
    bpy.context.collection.objects.link(lo)
    tr = lo.constraints.new("TRACK_TO")
    tr.target = txt

# el texto vive en el plano XY y se lee desde +Z; la cámara mira hacia -Z sin rotar
fe = fc.f(entrada)
for f in range(1, fc.frames + 1):
    txt.rotation_euler = (0, fc.ease(math.radians(70), 0, (f - 1) / max(1, fe - 1)), 0)
    txt.keyframe_insert("rotation_euler", frame=f)
    cam.location = (0, 0, fc.ease(d * 1.12, d, (f - 1) / max(1, fc.frames - 1)))
    cam.keyframe_insert("location", frame=f)
