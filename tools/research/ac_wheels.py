"""Mede rodas e limites do modelo AC (coordenadas do KN5: X lateral, Y cima, Z frente)."""
import sys

sys.path.insert(0, __file__.rsplit("\\", 2)[0])
from kn5_export import parse, xform  # noqa: E402

_, _, mats, nodes, _ = parse(sys.argv[1])
meshes = [n for n in nodes if n["class"] in (2, 3)]


def bbox(ns):
    pts = [xform(v[:3], n["world"]) for n in ns for v in n["verts"]]
    mn = [min(p[i] for p in pts) for i in range(3)]
    mx = [max(p[i] for p in pts) for i in range(3)]
    return mn, mx


mn, mx = bbox(meshes)
print("carro inteiro min", [round(v, 3) for v in mn], "max", [round(v, 3) for v in mx])
ext = [n for n in meshes if "cockpit_interior" not in n["name"]]
for n in meshes:
    if n["name"].startswith("WHEEL_") or "_rim_" in n["name"] or "rim___" in n["name"]:
        a, b = bbox([n])
        c = [round((x + y) / 2, 4) for x, y in zip(a, b)]
        size = [round(y - x, 4) for x, y in zip(a, b)]
        print(f"{n['name'][:40]:40} centro={c} tamanho={size} path={'/'.join(n['path'][-3:-1])}")
