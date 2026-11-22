"""Exporta cada objeto do sentra_nfsu2.blend em um OBJ proprio (uma pasta por LOD).
Pecas locais (roda, freios, aerofolio, escape) saem com a origem zerada.
blender -b <blend> -P export_parts.py -- <pasta_saida>
"""
import json
import os
import sys

import bpy
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1]
LOCAL = ("FRONT_WHEEL", "FRONT_BRAKE", "REAR_BRAKE", "SPOILER", "EXHAUST")
index = {}
for coll in bpy.data.collections:
    if not coll.name.startswith("LOD_"):
        continue
    d = os.path.join(OUT, coll.name)
    os.makedirs(d, exist_ok=True)
    for ob in coll.objects:
        is_local = any(k in ob.name for k in LOCAL)
        saved = ob.location.copy()
        if is_local:
            ob.location = Vector((0, 0, 0))
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        fp = os.path.join(d, ob.name + ".obj")
        bpy.ops.wm.obj_export(filepath=fp, export_selected_objects=True, forward_axis="Y", up_axis="Z",
                              path_mode="RELATIVE", export_triangulated_mesh=True, export_materials=True)
        ob.location = saved
        index[ob.name] = {"file": os.path.relpath(fp, OUT), "local": is_local,
                          "origin_translation": [round(v, 4) for v in saved] if is_local else [0, 0, 0],
                          "tris": sum(len(p.vertices) - 2 for p in ob.data.polygons)}
json.dump(index, open(os.path.join(OUT, "parts_index.json"), "w"), indent=1)
print("EXPORT_OK", len(index))
