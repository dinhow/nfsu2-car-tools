"""Despeja as malhas das colecoes LOD_* em um JSON compacto para o compilador.
blender -b sentra_nfsu2.blend -P dump_blend.py -- <saida.json>
Por objeto: location, e lista de triangulos [material, [(x,y,z,nx,ny,nz,u,v) x3]] em coordenadas locais.
"""
import json
import sys

import bpy

out = sys.argv[sys.argv.index("--") + 1]
dg = bpy.context.evaluated_depsgraph_get()
res = {}
for coll in bpy.data.collections:
    if not coll.name.startswith("LOD_"):
        continue
    for ob in coll.objects:
        me = ob.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        uv = me.uv_layers.active.data if me.uv_layers.active else None
        cn = me.corner_normals
        mats = [m.name.split(".")[0] if m else "" for m in me.materials]
        tris = []
        for lt in me.loop_triangles:
            corners = []
            for li in lt.loops:
                vi = me.loops[li].vertex_index
                co = me.vertices[vi].co
                n = cn[li].vector
                u, v = (uv[li].uv if uv else (0.0, 0.0))
                corners.append([round(co.x, 6), round(co.y, 6), round(co.z, 6),
                                round(n.x, 5), round(n.y, 5), round(n.z, 5), round(u, 6), round(v, 6)])
            tris.append([mats[lt.material_index] if mats else "", corners])
        res[ob.name] = {"location": list(ob.location), "tris": tris}
        ob.evaluated_get(dg).to_mesh_clear()
json.dump(res, open(out, "w"))
print("DUMP_OK", len(res), sum(len(v["tris"]) for v in res.values()))
