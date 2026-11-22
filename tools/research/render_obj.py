"""blender -b -P render_obj.py -- <obj> <saida_prefixo> [MATERIAL|RANDOM]   (OBJ em coordenadas NFSU2: Z cima)"""
import math
import sys

import bpy
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
obj, out = a[0], a[1]
mode = a[2] if len(a) > 2 else "RANDOM"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=obj, forward_axis="Y", up_axis="Z")
import random  # noqa: E402

random.seed(3)
for m in bpy.data.materials:
    m.diffuse_color = (random.random(), random.random(), random.random(), 1)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = mode
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.world = bpy.data.worlds.new("w")
sc.world.color = (0.2, 0.2, 0.22)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
sc.camera = cam
c = Vector((0.05, 0, 0.45))
for name, az, el in (("front34", 35, 18), ("rear34", 215, 18)):
    ar, er = math.radians(az), math.radians(el)
    cam.location = c + Vector((math.cos(ar) * math.cos(er), math.sin(ar) * math.cos(er), math.sin(er))) * 7.5
    cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = f"{out}_{name}.png"
    bpy.ops.render.render(write_still=True)
