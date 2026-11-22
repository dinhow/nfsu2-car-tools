"""Blender headless: importa OBJ e renderiza vistas de conferencia.
blender -b -P preview_render.py -- <obj> <saida_prefixo>
"""
import math
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
obj_path, out_prefix = args[0], args[1]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=obj_path, forward_axis="NEGATIVE_Z", up_axis="Y")

objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
mn = Vector((1e9, 1e9, 1e9))
mx = Vector((-1e9, -1e9, -1e9))
for o in objs:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        mn = Vector(map(min, mn, w))
        mx = Vector(map(max, mx, w))
center = (mn + mx) / 2
size = mx - mn
print(f"BBOX min={tuple(round(v, 3) for v in mn)} max={tuple(round(v, 3) for v in mx)} size={tuple(round(v, 3) for v in size)}")

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.world = bpy.data.worlds.new("w")
scene.world.color = (0.18, 0.18, 0.2)

cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
dist = max(size) * 1.6

views = {"front34": (35, 20), "rear34": (215, 20), "side": (90, 5)}
for name, (az, el) in views.items():
    a, e = math.radians(az), math.radians(el)
    cam.location = center + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = f"{out_prefix}_{name}.png"
    bpy.ops.render.render(write_still=True)
