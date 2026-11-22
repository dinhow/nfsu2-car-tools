"""Abre o .blend gerado e renderiza um LOD com cor por peca + rodas/freios replicados nas 4 posicoes.
blender -b <blend> -P check_render.py -- <LOD> <saida_prefixo> <front_x> <rear_x> <y> <z> [stock_geometry_parts.json]
"""
import json
import math
import sys

import bpy
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
LOD, OUT = a[0], a[1]
fx, rx, wy, wz = map(float, a[2:6])
scene = bpy.context.scene
for c in list(scene.collection.children):
    c.hide_render = c.name != f"LOD_{LOD}"

coll = bpy.data.collections[f"LOD_{LOD}"]
wheel = next(o for o in coll.objects if "FRONT_WHEEL" in o.name)
fb = next(o for o in coll.objects if "FRONT_BRAKE" in o.name)
rb = next(o for o in coll.objects if "REAR_BRAKE" in o.name)
# replica roda/freio nas 4 posicoes (lado direito espelhado em Y)
for x, src in ((fx, fb), (rx, rb)):
    for side in (1, -1):
        for s in (wheel, src):
            if side == 1 and ((s is wheel and x == fx) or s is src):
                continue
            inst = s.copy()
            coll.objects.link(inst)
            inst.location = Vector((x, side * (wy - 0.0), wz))
            inst.location.y = side * s.location.y
            inst.scale.y = side
# move o original da roda para a posicao dianteira esquerda (ja esta)

scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = sys.argv[-1] if sys.argv[-1] in ("RANDOM", "TEXTURE", "MATERIAL") else "RANDOM"
scene.render.resolution_x, scene.render.resolution_y = 1280, 720
scene.world = bpy.data.worlds.new("w")
scene.world.color = (0.2, 0.2, 0.22)

# chao na altura do pneu
ground_z = wz - 0.3172
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, ground_z))

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam)
scene.camera = cam
center = Vector((0.05, 0, 0.45))
for name, az, el, d in (("front34", 35, 18, 7.5), ("rear34", 215, 18, 7.5), ("side", 90, 2, 7.0), ("top", 90, 89, 7.5)):
    ar, er = math.radians(az), math.radians(el)
    # azimute medido a partir de +X (frente do carro)
    cam.location = center + Vector((math.cos(ar) * math.cos(er), math.sin(ar) * math.cos(er), math.sin(er))) * d
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = f"{OUT}_{name}.png"
    bpy.ops.render.render(write_still=True)
