"""Le o GEOMETRY.BIN, regenera tudo a partir dos campos decodificados e compara byte a byte."""
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from nfsu2_geom import Geometry  # noqa: E402

src, dst = sys.argv[1], sys.argv[2]
g = Geometry(src)
print("objetos:", len(g.objects), "verts:", sum(len(o.verts) for o in g.objects),
      "grupos:", sum(len(o.groups) for o in g.objects))
out = g.save(dst)
orig = g.data
print("tamanho original", len(orig), "regenerado", len(out))
if out == orig:
    print("IDENTICO byte a byte")
else:
    diff = next(i for i in range(min(len(out), len(orig))) if out[i] != orig[i])
    print("primeira diferenca em", diff)
    print(" orig:", orig[diff - 16:diff + 32].hex(" "))
    print(" novo:", out[diff - 16:diff + 32].hex(" "))
