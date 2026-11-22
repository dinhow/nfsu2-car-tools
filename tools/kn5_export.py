"""Leitor de KN5 (Assetto Corsa) -> OBJ/MTL + texturas + relatorio.

Uso: python kn5_export.py <arquivo.kn5> <pasta_saida>
"""
import json
import os
import struct
import sys


class Reader:
    def __init__(self, data):
        self.d = data
        self.p = 0

    def take(self, n):
        b = self.d[self.p:self.p + n]
        if len(b) != n:
            raise EOFError(f"fim inesperado em {self.p} (pedido {n})")
        self.p += n
        return b

    def u8(self):
        return self.take(1)[0]

    def i32(self):
        return struct.unpack("<i", self.take(4))[0]

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def f32(self, n=1):
        v = struct.unpack(f"<{n}f", self.take(4 * n))
        return v[0] if n == 1 else v

    def s(self):
        n = self.i32()
        return self.take(n).decode("utf-8", "replace")


def matmul(a, b):
    # matrizes 4x4 row-major, convencao DirectX (v * M)
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


IDENT = [[1 if i == j else 0 for j in range(4)] for i in range(4)]


def read_node(r, parent_world, out, path):
    cls = r.i32()
    name = r.s()
    nchild = r.i32()
    active = r.u8()
    node = {"class": cls, "name": name, "path": path + [name], "active": active}
    world = parent_world
    if cls == 1:  # dummy
        m = r.f32(16)
        local = [list(m[i * 4:i * 4 + 4]) for i in range(4)]
        world = matmul(local, parent_world)
    elif cls in (2, 3):  # mesh / skinned mesh
        node["cast_shadows"], node["visible"], node["transparent"] = r.u8(), r.u8(), r.u8()
        if cls == 3:
            nb = r.i32()
            node["bones"] = []
            for _ in range(nb):
                node["bones"].append(r.s())
                r.f32(16)
        nv = r.i32()
        stride = 44 if cls == 2 else 76
        raw = r.take(nv * stride)
        verts = []
        for i in range(nv):
            o = i * stride
            px, py, pz, nx, ny, nz, u, v = struct.unpack_from("<8f", raw, o)
            verts.append((px, py, pz, nx, ny, nz, u, v))
        ni = r.i32()
        idx = struct.unpack(f"<{ni}H", r.take(ni * 2))
        node["material"] = r.i32()
        if cls == 2:
            node["layer"] = r.i32()
            node["lod_in"], node["lod_out"] = r.f32(), r.f32()
            r.f32(4)  # bounding sphere
            node["renderable"] = r.u8()
        else:
            r.take(12)  # layer, lod in/out
        node["verts"] = verts
        node["idx"] = idx
        node["world"] = world
    else:
        raise ValueError(f"classe de no desconhecida {cls} em {r.p}")
    out.append(node)
    for _ in range(nchild):
        read_node(r, world, out, path + [name])


def parse(path):
    r = Reader(open(path, "rb").read())
    magic = r.take(6)
    assert magic == b"sc6969", magic
    version = r.i32()
    if version > 5:
        r.i32()
    textures = []
    for _ in range(r.i32()):
        active = r.i32()
        name = r.s()
        size = r.i32()
        textures.append({"name": name, "active": active, "data": r.take(size)})
    materials = []
    for _ in range(r.i32()):
        m = {"name": r.s(), "shader": r.s(), "alpha_blend": r.u8(), "alpha_tested": r.u8(),
             "depth_mode": r.i32(), "props": {}, "samplers": {}}
        for _ in range(r.i32()):
            pname = r.s()
            val = r.f32()
            r.take(36)  # vec2/vec3/vec4
            m["props"][pname] = val
        for _ in range(r.i32()):
            sname = r.s()
            r.i32()  # slot
            m["samplers"][sname] = r.s()
        materials.append(m)
    nodes = []
    read_node(r, IDENT, nodes, [])
    leftover = len(r.d) - r.p
    return version, textures, materials, nodes, leftover


def xform(p, m):
    x, y, z = p
    return (x * m[0][0] + y * m[1][0] + z * m[2][0] + m[3][0],
            x * m[0][1] + y * m[1][1] + z * m[2][1] + m[3][1],
            x * m[0][2] + y * m[1][2] + z * m[2][2] + m[3][2])


def xnorm(n, m):
    x, y, z = n
    return (x * m[0][0] + y * m[1][0] + z * m[2][0],
            x * m[0][1] + y * m[1][1] + z * m[2][1],
            x * m[0][2] + y * m[1][2] + z * m[2][2])


def safe(s):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in s)


def export(src, outdir):
    version, textures, materials, nodes, leftover = parse(src)
    os.makedirs(os.path.join(outdir, "textures"), exist_ok=True)
    for t in textures:
        with open(os.path.join(outdir, "textures", safe(t["name"])), "wb") as f:
            f.write(t["data"])

    base = os.path.splitext(os.path.basename(src))[0]
    with open(os.path.join(outdir, base + ".mtl"), "w", encoding="utf-8") as f:
        for m in materials:
            f.write(f"newmtl {safe(m['name'])}\n")
            diff = m["samplers"].get("txDiffuse")
            if diff:
                f.write(f"map_Kd textures/{safe(diff)}\n")
            if m["alpha_blend"] or m["alpha_tested"]:
                if diff:
                    f.write(f"map_d textures/{safe(diff)}\n")
            f.write("\n")

    meshes = [n for n in nodes if n["class"] in (2, 3)]
    with open(os.path.join(outdir, base + ".obj"), "w", encoding="utf-8") as f:
        f.write(f"mtllib {base}.mtl\n")
        off = 1
        for n in meshes:
            m = n["world"]
            f.write(f"o {safe(n['name'])}\n")
            for v in n["verts"]:
                x, y, z = xform(v[0:3], m)
                f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
            for v in n["verts"]:
                f.write(f"vt {v[6]:.6f} {1 - v[7]:.6f}\n")
            for v in n["verts"]:
                x, y, z = xnorm(v[3:6], m)
                f.write(f"vn {x:.5f} {y:.5f} {z:.5f}\n")
            f.write(f"usemtl {safe(materials[n['material']]['name'])}\n")
            idx = n["idx"]
            for i in range(0, len(idx), 3):
                a, b, c = idx[i] + off, idx[i + 1] + off, idx[i + 2] + off
                f.write(f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}\n")
            off += len(n["verts"])

    report = {
        "source": src, "kn5_version": version, "leftover_bytes": leftover,
        "textures": [{"name": t["name"], "bytes": len(t["data"])} for t in textures],
        "materials": [{k: m[k] for k in ("name", "shader", "alpha_blend", "alpha_tested", "samplers")} for m in materials],
        "meshes": [{"name": n["name"], "path": "/".join(n["path"]), "verts": len(n["verts"]),
                    "tris": len(n["idx"]) // 3, "material": materials[n["material"]]["name"],
                    "visible": n.get("visible"), "lod_out": n.get("lod_out")} for n in meshes],
        "total_tris": sum(len(n["idx"]) // 3 for n in meshes),
    }
    with open(os.path.join(outdir, base + "_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    return report


if __name__ == "__main__":
    rep = export(sys.argv[1], sys.argv[2])
    print(f"versao={rep['kn5_version']} sobra={rep['leftover_bytes']} bytes "
          f"texturas={len(rep['textures'])} materiais={len(rep['materials'])} "
          f"malhas={len(rep['meshes'])} triangulos={rep['total_tris']}")
