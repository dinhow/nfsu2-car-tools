"""Exporta objetos de um GEOMETRY.BIN para OBJ (material = indice do shader do grupo).
python geom_to_obj.py <GEOMETRY.BIN> <saida.obj> <prefixo1> [prefixo2 ...]   (apenas nomes terminados em _A)
"""
import sys

sys.path.insert(0, __file__.rsplit("\\", 2)[0])
from nfsu2_geom import Geometry  # noqa: E402

g = Geometry(sys.argv[1])
prefixes = sys.argv[3:]
with open(sys.argv[2], "w") as f:
    off = 1
    for o in g.objects:
        if not any(o.name.startswith(p) for p in prefixes):
            continue
        if o.name.endswith(("_B", "_C", "_D")):
            continue
        t = o.translation
        f.write(f"o {o.name}\n")
        for v in o.verts:
            f.write(f"v {v[0] + t[0]:.5f} {v[1] + t[1]:.5f} {v[2] + t[2]:.5f}\n")
        for v in o.verts:
            f.write(f"vn {v[3]:.4f} {v[4]:.4f} {v[5]:.4f}\n")
        for gr in o.groups:
            f.write(f"usemtl s{o.shaders[gr.f[1]]:08X}\n")
            for i in range(gr.start, gr.start + gr.count, 3):
                a, b, c = (o.indices[i + k] + off for k in range(3))
                f.write(f"f {a}//{a} {b}//{b} {c}//{c}\n")
        off += len(o.verts)
print("ok")
