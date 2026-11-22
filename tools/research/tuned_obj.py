"""Monta um OBJ do carro compilado com um conjunto de pecas escolhido (para conferir kits).
python tuned_obj.py <GEOMETRY.BIN> <saida.obj> KIT05 STYLE03 STYLE07
  -> para-choques/saias do KIT05, capo do STYLE03, farois/lanternas do STYLE07
"""
import sys

sys.path.insert(0, __file__.rsplit("\\", 2)[0])
from nfsu2_geom import Geometry, bhash  # noqa: E402

g = Geometry(sys.argv[1])
out, kit, hood, lights = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
C = "SENTRA"
names = [f"{C}_BASE_A"] + [f"{C}_KIT00_{p}_A" for p in ("BODY", "ROOF", "TRUNK", "SPOILER", "LEFT_SIDE_MIRROR",
                                                          "RIGHT_SIDE_MIRROR", "HOOD_UNDER")]
names += [f"{C}_{kit}_{p}_A" for p in ("FRONT_BUMPER", "REAR_BUMPER", "SKIRT")]
names += [f"{C}_{hood}_HOOD_A", f"{C}_{hood}_HOOD_LEFT_A", f"{C}_{hood}_HOOD_RIGHT_A"]
names += [f"{C}_{lights}_{p}_A" for p in ("HEADLIGHT_LEFT", "HEADLIGHT_RIGHT", "BRAKELIGHT")]
byhash = {o.hash: o for o in g.objects}
with open(out, "w") as f:
    off = 1
    for n in names:
        o = byhash.get(bhash(n))
        if o is None:
            continue
        t = o.translation
        f.write(f"o {n}\n")
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
