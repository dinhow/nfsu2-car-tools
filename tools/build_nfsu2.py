"""Monta o Sentra B16 (KN5 do AC) no padrao de pecas do NFSU2, dentro do Blender.

blender -b -P build_nfsu2.py -- <sentra.kn5> <pasta_texturas> <pasta_saida>

Saida:
  sentra_nfsu2.blend          cena com colecoes LOD_A / LOD_B / LOD_C
  SENTRA_LOD_A.fbx/.obj ...   uma exportacao por LOD, coordenadas do NFSU2 (X frente, Y esquerda, Z cima)
  build_report.json           triangulos por peca, marcadores e posicoes sugeridas das rodas
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
KN5, TEXDIR, OUT = args[0], args[1], args[2]
# --budget=0.45 reduz o orcamento de triangulos (menos peso de FPS); 1.0 = padrao
BUDGET_SCALE = float(next((a.split("=", 1)[1] for a in args if a.startswith("--budget=")), 1.0))
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kn5_export import parse, xform, xnorm  # noqa: E402

CAR = "SENTRA"
# Rodas do B16 medidas no KN5 (eixo Z do AC): dianteira 1.3615, traseira -1.3377, centro Y(AC)=0.1528.
# Centraliza o entre-eixos no mesmo ponto medio do original (1.32 / -1.22 -> 0.05) e
# alinha a altura do cubo com o original (Z=0.08).
AC_FRONT, AC_REAR, AC_HUB_Y = 1.3615, -1.3377, 0.1528
DX = 0.05 - (AC_FRONT + AC_REAR) / 2
DZ = 0.08 - AC_HUB_Y


def to_nfs(p):
    return (p[2] + DX, p[0], p[1] + DZ)


def nrm_nfs(n):
    return (n[2], n[0], n[1])


# ---------------------------------------------------------------- classificacao das malhas do AC
def classify(name, path):
    n = name.lower()
    pth = "/".join(path).lower()
    if "rim_lf" in pth or "tyre_lf" in pth:
        return "FRONT_WHEEL"
    if any(k in pth for k in ("rim_lr", "rim_rf", "rim_rr", "tyre_lr", "tyre_rf", "tyre_rr")):
        return None  # roda unica, o jogo replica
    if "caliperlf" in n or "rotorlf" in n:
        return "FRONT_BRAKE"
    if "caliperlr" in n or "rotorlr" in n:
        return "REAR_BRAKE"
    if any(k in n for k in ("caliperrf", "caliperrr", "rotorrf", "rotorrr")):
        return None
    # glassLHL/RHL = vidro do farol (HeadLight), glassLTL/RTL = vidro da lanterna (TailLight)
    if "_lod0_glasslhl" in n:
        return "HEADLIGHT_LEFT"
    if "_lod0_glassrhl" in n:
        return "HEADLIGHT_RIGHT"
    if "_lod0_glassltl" in n or "_lod0_glassrtl" in n:
        return "BRAKELIGHT"
    if n.startswith("intlod") or "cockpit_glass" in n or "_lod0_glassr_" in n or "defrost_lines" in n:
        return "BASE"
    if "cockpit_mirrorl" in n:
        return "LEFT_SIDE_MIRROR"
    if "cockpit_mirrorr" in n:
        return "RIGHT_SIDE_MIRROR"
    if "cockpit_hooda" in n:
        return "HOOD"
    if "cockpit" in n or n.startswith("fuel_led"):
        return None  # interior detalhado fica de fora (BASE usa o intlod)
    if "_bumperfa_" in n or "bumperframef" in n:
        return "FRONT_BUMPER"
    if "_bumperra_" in n or "bumperframer" in n:
        return "REAR_BUMPER"
    if "_skirtla_" in n or "_skirtra_" in n:
        return "SKIRT"
    if "_trunk_" in n:
        return "TRUNK"
    if "_wingb_" in n:
        return "SPOILER"
    if "headlightl" in n:
        return "HEADLIGHT_LEFT"
    if "headlightr" in n:
        return "HEADLIGHT_RIGHT"
    if "taillight" in n:
        return "BRAKELIGHT"
    if "_exhausta_" in n:
        return "EXHAUST"
    if "_body_" in n or "undercarriage" in n:
        return "BODY"
    return "UNMAPPED"


# Orcamento de triangulos do LOD A por peca; B e C sao fracoes dele.
BUDGET_A = {
    "BODY": 9000, "ROOF": 2500, "FRONT_BUMPER": 5000, "REAR_BUMPER": 3500, "HOOD": 1500, "HOOD_UNDER": 600,
    "TRUNK": 2500, "TRUNK_UNDER": 600, "SKIRT": 1200, "SPOILER": 1500, "HEADLIGHT_LEFT": 2500,
    "HEADLIGHT_RIGHT": 2500, "BRAKELIGHT": 3000, "LEFT_SIDE_MIRROR": 1200, "RIGHT_SIDE_MIRROR": 1200,
    "FRONT_WHEEL": 3000, "FRONT_BRAKE": 1200, "REAR_BRAKE": 1200, "EXHAUST": 600, "BASE": 7000,
}
LOD_FACTOR = {"A": 1.0, "B": 0.45, "C": 0.18}
PLACEHOLDERS = ["DOOR_LEFT", "DOOR_RIGHT", "DOOR_PANEL_LEFT", "DOOR_PANEL_RIGHT", "DOOR_SILL_LEFT",
                "DOOR_SILL_RIGHT", "ENGINE", "ENGINE_UNLIT", "TRUNK_AUDIO", "TRUNK_AUDIO_UNLIT"]

# ---------------------------------------------------------------- leitura
_, textures, materials, nodes, leftover = parse(KN5)
assert leftover == 0
meshes = [n for n in nodes if n["class"] in (2, 3)]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# materiais
mat_cache = {}


def get_mat(idx):
    if idx in mat_cache:
        return mat_cache[idx]
    m = materials[idx]
    bm = bpy.data.materials.new(m["name"])
    bm.use_nodes = True
    bsdf = bm.node_tree.nodes.get("Principled BSDF")
    diff = m["samplers"].get("txDiffuse")
    if diff:
        fp = os.path.join(TEXDIR, "".join(c if c.isalnum() or c in "-_." else "_" for c in diff))
        if os.path.exists(fp):
            img = bpy.data.images.load(fp, check_existing=True)
            tex = bm.node_tree.nodes.new("ShaderNodeTexImage")
            tex.image = img
            bm.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
            if m["alpha_blend"] or m["alpha_tested"]:
                bm.node_tree.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    bm["ac_shader"] = m["shader"]
    bm["ac_texture"] = diff or ""
    mat_cache[idx] = bm
    return bm


def make_obj(name, n):
    verts = [to_nfs(xform(v[:3], n["world"])) for v in n["verts"]]
    idx = n["idx"]
    faces = [(idx[i], idx[i + 1], idx[i + 2]) for i in range(0, len(idx), 3)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            u, v = n["verts"][vi][6], n["verts"][vi][7]
            uv.data[li].uv = (u, 1 - v)
    me.materials.append(get_mat(n["material"]))
    me.validate()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


groups = {}
unmapped = []
for n in meshes:
    part = classify(n["name"], n["path"])
    if part is None:
        continue
    if part == "UNMAPPED":
        unmapped.append(n["name"])
        continue
    groups.setdefault(part, []).append(make_obj(n["name"], n))


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    # solda vertices duplicados (o KN5 separa por UV/normal) para o decimate nao rasgar
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


parts = {p: join(o, p) for p, o in groups.items()}


def bbox(ob):
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return (Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)]))


# ---------------------------------------------------------------- teto separado da carroceria
side_glass = [o for o in bpy.data.objects if False]
glass_min_z = None
for n in meshes:
    nm = n["name"].lower()
    if "cockpit_glasslf_window" in nm:  # vidro lateral dianteiro: a borda de baixo e a linha de cintura
        z = min(to_nfs(xform(v[:3], n["world"]))[2] for v in n["verts"])
        glass_min_z = z if glass_min_z is None else min(glass_min_z, z)
belt = glass_min_z - 0.01
body = parts["BODY"]
bm = bmesh.new()
bm.from_mesh(body.data)
roof_faces = [f for f in bm.faces if f.calc_center_median().z > belt]
roof_geom = bmesh.ops.split(bm, geom=roof_faces)  # noqa: F841
bm.to_mesh(body.data)
bm.free()
bpy.ops.object.select_all(action="DESELECT")
body.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="DESELECT")
bpy.ops.object.mode_set(mode="OBJECT")
for p in body.data.polygons:
    p.select = sum((body.data.vertices[v].co.z for v in p.vertices)) / len(p.vertices) > belt
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.separate(type="SELECTED")
bpy.ops.object.mode_set(mode="OBJECT")
roof = [o for o in bpy.context.selected_objects if o != body][0]
roof.name = roof.data.name = "ROOF"
parts["ROOF"] = roof


# ---------------------------------------------------------------- copias "UNDER" (lado de baixo de capo/porta-malas)
def under_copy(src, name):
    ob = src.copy()
    ob.data = src.data.copy()
    ob.name = ob.data.name = name
    scene.collection.objects.link(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    # 4 mm causava z-fighting na camera do jogo (manchas escuras no capo): 2 cm abaixo e um pouco menor
    cx = sum(v.co.x for v in bm.verts) / len(bm.verts)
    cy = sum(v.co.y for v in bm.verts) / len(bm.verts)
    for v in bm.verts:
        v.co.x = cx + (v.co.x - cx) * 0.98
        v.co.y = cy + (v.co.y - cy) * 0.98
        v.co.z -= 0.02
    bm.to_mesh(ob.data)
    bm.free()
    return ob


parts["HOOD_UNDER"] = under_copy(parts["HOOD"], "HOOD_UNDER")
parts["TRUNK_UNDER"] = under_copy(parts["TRUNK"], "TRUNK_UNDER")


# ---------------------------------------------------------------- terceira luz de freio: sai do aerofolio, vai pro teto
# a malha "wingb" do AC junta o aerofolio da tampa e a faixa da luz de freio no alto do vidro traseiro.
sp_ob = parts["SPOILER"]
bpy.ops.object.select_all(action="DESELECT")
sp_ob.select_set(True)
bpy.context.view_layer.objects.active = sp_ob
bpy.ops.mesh.separate(type="LOOSE")
pieces = list(bpy.context.selected_objects)
sp_min_x = min(min((o.matrix_world @ v.co).x for v in o.data.vertices) for o in pieces)
keep, to_roof = [], []
for o in pieces:
    cx = sum((o.matrix_world @ v.co).x for v in o.data.vertices) / len(o.data.vertices)
    (to_roof if cx > sp_min_x + 0.45 else keep).append(o)
parts["SPOILER"] = join(keep, "SPOILER")
if to_roof:
    parts["ROOF"] = join([parts["ROOF"]] + to_roof, "ROOF")
print(f"SPOILER_SPLIT pecas={len(pieces)} aerofolio={len(keep)} para_teto={len(to_roof)}")

# ---------------------------------------------------------------- pecas em espaco local
def localize(ob, origin):
    for v in ob.data.vertices:
        v.co -= origin
    ob.location = origin


lf_center = Vector(to_nfs((0.7548, AC_HUB_Y, AC_FRONT)))
lr_center = Vector(to_nfs((0.7539, AC_HUB_Y, AC_REAR)))
wheel = parts["FRONT_WHEEL"]
wmin, wmax = bbox(wheel)
# convencao do original: eixo da roda em Y, face interna em Y=-0.01, roda cresce para +Y
wheel_origin = Vector((lf_center.x, wmin.y + 0.01, lf_center.z))
localize(wheel, wheel_origin)
localize(parts["FRONT_BRAKE"], Vector((lf_center.x, wheel_origin.y, lf_center.z)))
localize(parts["REAR_BRAKE"], Vector((lr_center.x, wheel_origin.y, lr_center.z)))

ex = parts["EXHAUST"]
emin, emax = bbox(ex)
ex_tip = Vector((emin.x, (emin.y + emax.y) / 2, (emin.z + emax.z) / 2))
localize(ex, ex_tip)

sp = parts["SPOILER"]
smin, smax = bbox(sp)
spoiler_mark = Vector((smin.x + 0.12, 0.0, smin.z + 0.05))
localize(sp, spoiler_mark)


# ---------------------------------------------------------------- marcadores
def center(ob):
    a, b = bbox(ob)
    return (a + b) / 2


tmin, tmax = bbox(parts["TRUNK"])
rmin, rmax = bbox(parts["ROOF"])
hl, hr, bl = center(parts["HEADLIGHT_LEFT"]), center(parts["HEADLIGHT_RIGHT"]), bbox(parts["BRAKELIGHT"])
glass_front = glass_rear = None
for n in meshes:
    nm = n["name"].lower()
    pts = [Vector(to_nfs(xform(v[:3], n["world"]))) for v in n["verts"]]
    c = sum(pts, Vector()) / len(pts)
    if "cockpit_glassf_" in nm:
        glass_front = c
    if "_lod0_glassr_" in nm:
        glass_rear = c
markers = {
    "SPOILER": list(spoiler_mark),
    "ROOF_SCOOP": [(rmin.x + rmax.x) / 2, 0.0, rmax.z],
    "LEFT_HEADLIGHT": list(hl), "RIGHT_HEADLIGHT": list(hr),
    "LEFT_BRAKELIGHT": [(bl[0].x + bl[1].x) / 2, bl[1].y * 0.8, (bl[0].z + bl[1].z) / 2],
    "RIGHT_BRAKELIGHT": [(bl[0].x + bl[1].x) / 2, -bl[1].y * 0.8, (bl[0].z + bl[1].z) / 2],
    "RIGHT_EXHAUST": list(ex_tip),
    "REAR_LICENSE_PLATE": [tmin.x, 0.0, (tmin.z + tmax.z) / 2],
    "FRONT_WINDOW": list(glass_front) if glass_front else None,
    "REAR_WINDOW": list(glass_rear) if glass_rear else None,
}

# ---------------------------------------------------------------- placeholders (1 triangulo minusculo)
for p in PLACEHOLDERS:
    me = bpy.data.meshes.new(p)
    me.from_pydata([(0, 0, -0.2), (0.001, 0, -0.2), (0, 0.001, -0.2)], [], [(0, 1, 2)])
    ob = bpy.data.objects.new(p, me)
    scene.collection.objects.link(ob)
    parts[p] = ob

# ---------------------------------------------------------------- suavizacao, LODs e nomes finais
def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


report = {"parts": {}, "markers": markers, "unmapped_meshes": unmapped, "belt_z": belt,
          "offset_ac_to_nfs": {"DX": DX, "DZ": DZ, "map": "nfs(X,Y,Z) = (ac.z+DX, ac.x, ac.y+DZ)"}}
for lod in LOD_FACTOR:
    coll = bpy.data.collections.new(f"LOD_{lod}")
    scene.collection.children.link(coll)

for p, ob in list(parts.items()):
    for v in ob.data.polygons:
        v.use_smooth = True
    try:
        ob.data.set_sharp_from_angle(angle=math.radians(40))
    except Exception:
        pass
    src_tris = tris(ob)
    report["parts"][p] = {"source_tris": src_tris}
    for lod, fac in LOD_FACTOR.items():
        o2 = ob.copy()
        o2.data = ob.data.copy()
        name = f"{CAR}_BASE_{lod}" if p == "BASE" else f"{CAR}_KIT00_{p}_{lod}"
        o2.name = o2.data.name = name
        bpy.data.collections[f"LOD_{lod}"].objects.link(o2)
        if p not in PLACEHOLDERS:
            # superficies grandes e lisas (capo, teto, vidros) mostram facetas no reflexo: ficam com orcamento cheio
            scale = 1.0 if p in ("HOOD", "ROOF", "BASE") else BUDGET_SCALE
            target = BUDGET_A.get(p, 2000) * fac * scale
            ratio = min(1.0, target / max(src_tris, 1))
            if ratio < 1.0:
                mod = o2.modifiers.new("dec", "DECIMATE")
                mod.ratio = ratio
                mod.use_collapse_triangulate = True
                bpy.context.view_layer.objects.active = o2
                bpy.ops.object.select_all(action="DESELECT")
                o2.select_set(True)
                bpy.ops.object.modifier_apply(modifier="dec")
        report["parts"][p][lod] = tris(o2)
    bpy.data.objects.remove(ob, do_unlink=True)

for lod in LOD_FACTOR:
    report[f"total_{lod}"] = sum(v[lod] for v in report["parts"].values())

# posicoes de roda sugeridas para o CarTypeInfo (X frente, Y lateral, Z cubo)
report["cartypeinfo_wheels_suggested"] = {
    "front_x": round(lf_center.x, 4), "rear_x": round(lr_center.x, 4), "hub_z": round(lf_center.z, 4),
    "track_half_y_center": round(lf_center.y, 4), "wheel_origin_y": round(wheel_origin.y, 4),
    "stock": {"front_x": 1.32, "rear_x": -1.22, "y": 0.75, "z": 0.08, "radius": 0.3172},
}

# ---------------------------------------------------------------- exportacao
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "sentra_nfsu2.blend"))
for lod in LOD_FACTOR:
    bpy.ops.object.select_all(action="DESELECT")
    for o in bpy.data.collections[f"LOD_{lod}"].objects:
        o.select_set(True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, f"{CAR}_LOD_{lod}.fbx"), use_selection=True,
                             axis_forward="Y", axis_up="Z", bake_space_transform=False, path_mode="COPY",
                             embed_textures=False, mesh_smooth_type="FACE")
    bpy.ops.wm.obj_export(filepath=os.path.join(OUT, f"{CAR}_LOD_{lod}.obj"), export_selected_objects=True,
                          forward_axis="Y", up_axis="Z", path_mode="COPY", export_triangulated_mesh=True)
json.dump(report, open(os.path.join(OUT, "build_report.json"), "w"), indent=1)
print("BUILD_OK", json.dumps({k: report[k] for k in ("total_A", "total_B", "total_C")}), "unmapped:", len(unmapped))
