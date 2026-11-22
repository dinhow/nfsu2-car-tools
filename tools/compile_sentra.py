"""Compila o GEOMETRY.BIN do SENTRA com o B16, usando o arquivo original como molde.

python compile_sentra.py <GEOMETRY.BIN original> <mesh_dump.json> <build_report.json> <new_textures.json> <saida>
"""
import collections
import copy
import json
import math
import struct
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from nfsu2_geom import Geometry, Group, bhash  # noqa: E402

SRC, DUMP, REPORT, NEWTEX, OUT = sys.argv[1:6]
# rodas e freios: ficam os originais do B15 (testados no jogo, encaixam certo nas caixas do B16)
DIAG_STOCK_WHEELS = "--b16-wheels" not in sys.argv
NO_MORPH = "--no-kit-morph" in sys.argv  # volta ao comportamento antigo (kits = copia da peca de serie)
LB_PATH = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--widebody=")), None)
B16F_PATH = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--b16front=")), None)
g = Geometry(SRC)
stock = Geometry(SRC)  # copia intocada para referencia
dump = json.load(open(DUMP))
report = json.load(open(REPORT))
newtex = {k: int(v["hash"], 16) for k, v in json.load(open(NEWTEX)).items()}
CAR = "SENTRA"


# ------------------------------------------------------------------ combinacoes de material de referencia
def ref(obj, gi):
    o = stock.by_name(obj)
    gr = o.groups[gi]
    idx = o.indices[gr.start:gr.start + gr.count]
    color = collections.Counter(o.verts[i][6] for i in idx).most_common(1)[0][0]
    return {"tex": o.textures[gr.f[0]], "sh": o.shaders[gr.f[1]], "flags": gr.flags, "color": color}


R = {
    "PAINT": ref("SENTRA_KIT00_BODY_A", 0),
    "DULL": ref("SENTRA_KIT00_BODY_A", 2),
    "DARK": ref("SENTRA_KIT00_BODY_A", 3),
    "CHROME_STOCK": ref("SENTRA_KIT00_LEFT_SIDE_MIRROR_A", 1),
    "HL_LENS_L": ref("SENTRA_KIT00_HEADLIGHT_LEFT_A", 0),
    "HL_LENS_R": ref("SENTRA_KIT00_HEADLIGHT_RIGHT_A", 0),
    "HL_LIGHT": ref("SENTRA_KIT00_HEADLIGHT_LEFT_A", 2),
    "HL_CHROME": ref("SENTRA_KIT00_HEADLIGHT_LEFT_A", 3),
    "BRAKE_LIGHT": ref("SENTRA_KIT00_BRAKELIGHT_A", 2),
    "BRAKE_LENS": ref("SENTRA_KIT00_BRAKELIGHT_A", 0),
    "WIN_FRONT": ref("SENTRA_BASE_A", 6),
    "WIN_REAR": ref("SENTRA_BASE_A", 2),
    "WIN_L": ref("SENTRA_BASE_A", 8),
    "WIN_R": ref("SENTRA_BASE_A", 9),
    "INTERIOR": ref("SENTRA_BASE_A", 4),
    "RIM": ref("SENTRA_KIT00_FRONT_WHEEL_A", 1),
    "TIRE": ref("SENTRA_KIT00_FRONT_WHEEL_A", 0),
    "ROTOR": ref("SENTRA_KIT00_FRONT_BRAKE_A", 0),
    "CALIPER": ref("SENTRA_KIT00_FRONT_BRAKE_A", 1),
    "DETAIL_DULL": dict(ref("SENTRA_KIT00_ENGINE_A", 0)),
    "DETAIL_CHROME": dict(ref("SENTRA_KIT00_ENGINE_A", 4)),
}
# combinacoes que usam texturas novas (troca so a textura)
NEWTEX_INFO = json.load(open(NEWTEX))
R["BRAKE_LIGHT0"] = dict(R["BRAKE_LIGHT"])
R["BRAKE_LIGHT1"] = dict(R["BRAKE_LIGHT"])
# combinacao -> textura nova (recortada); rodas/freios sao os do B15, entao RIM/TIRE/ROTOR/CALIPER nao sao usados
TEX_OF = {"DETAIL_DULL": "SENTRA_B16_DETAIL_M", "DETAIL_CHROME": "SENTRA_B16_DETAIL_C",
          "HL_LIGHT": "SENTRA_B16_LIGHTS0", "BRAKE_LIGHT0": "SENTRA_B16_LIGHTS0",
          "HL_CHROME": "SENTRA_B16_LIGHTS1", "BRAKE_LIGHT1": "SENTRA_B16_LIGHTS1"}
for k, tname in TEX_OF.items():
    R[k] = dict(R[k], tex=newtex[tname])
CROP = {k: NEWTEX_INFO[t]["crop"] for k, t in TEX_OF.items()}


def remap_uv(key, corners):
    """UVs (jogo) do triangulo -> UVs dentro do recorte da textura nova; mesmo deslocamento p/ os 3 cantos."""
    uvs = [(k[6], 1.0 - k[7]) for k in corners]
    if key not in CROP:
        return uvs
    u0, v0, u1, v1 = CROP[key]
    su = -math.floor(min(u for u, _ in uvs) + 1e-6)
    sv = -math.floor(min(v for _, v in uvs) + 1e-6)
    return [(min(1.0, max(0.0, (u + su - u0) / (u1 - u0))), min(1.0, max(0.0, (v + sv - v0) / (v1 - v0))))
            for u, v in uvs]

PAINT_UV = (0.852, 0.391)  # centro da pintura do capo original na pele do carro
DULL_MATS = {"black", "frame", "rubber_trim", "weatherstrip", "plastic", "plastic2", "bumper_frame", "bottom",
             "undercarriage", "rubber", "defrost_lines", "solid"}
LIGHTS0 = {"head_light", "reverse_light_lod0", "tail_light_lod0"}
warn = collections.Counter()


def combo(part, mat, c):
    """part = nome da peca sem prefixo/LOD; mat = material do AC; c = centroide (x,y,z) + normal media (nx,ny,nz)."""
    if mat in ("body", "body_2", "lb_paint"):
        return "PAINT"
    if mat == "lb_rivet":
        return "CHROME_STOCK"
    if mat == "lb_black":
        return "DULL"
    if mat == "fog_glass":
        return "HL_LENS_L"
    if part == "BASE":
        if mat in ("black_glass", "window", "glass"):
            nx, ny = c[3], c[4]
            if abs(ny) > 0.6:  # vidro lateral: normal aponta para o lado
                return "WIN_L" if ny > 0 else "WIN_R"
            return "WIN_FRONT" if nx > 0 else "WIN_REAR"
        return "INTERIOR"
    if part == "FRONT_BUMPER" and mat == "glass":
        return "HL_LENS_L"  # lente dos farois de neblina
    if part.startswith("HEADLIGHT"):
        if mat in ("glass", "detail_glass_clear", "detail_glass_amber"):
            return "HL_LENS_L" if part.endswith("LEFT") else "HL_LENS_R"
        if mat == "head_light":
            return "HL_LIGHT"
        if mat in ("textured_reflector", "reflector"):
            return "HL_CHROME"
    if part == "BRAKELIGHT":
        if mat in ("glass", "detail_glass_clear"):
            return "BRAKE_LENS"
        if mat in LIGHTS0:
            return "BRAKE_LIGHT0"
        if mat in ("detail_glass_red", "tail_light2", "textured_reflector", "reflector", "detail_glass_amber"):
            return "BRAKE_LIGHT1"
    if mat in LIGHTS0:
        return "BRAKE_LIGHT0" if mat != "head_light" else "HL_LIGHT"
    if mat.startswith("Material #3") or mat.startswith("Material #4"):
        return "CHROME_STOCK"  # vidro dos retrovisores
    if mat in ("rim", "inner_rim", "outer_rim", "wheel_black"):
        return "RIM"
    if mat == "Material_#56":
        return "TIRE"
    if mat in ("Material #12", "Material #13", "Material #14", "Material #15"):
        return "ROTOR"
    if mat == "caliper":
        return "CALIPER"
    if mat == "matte_colors":
        return "DETAIL_DULL"
    if mat in ("chrome", "emblem"):
        return "DETAIL_CHROME"
    if mat in DULL_MATS:
        return "DULL"
    warn[(part, mat)] += 1
    return "DULL"


# ------------------------------------------------------------------ construcao da malha
def build_mesh(dump_obj, part):
    groups = collections.OrderedDict()
    for mat, corners in dump_obj["tris"]:
        c = [sum(k[i] for k in corners) / 3 for i in range(6)]  # centroide + normal media
        key = combo(part, mat, c)
        groups.setdefault(key, []).append(corners)
    # roda: pneu primeiro, como em todas as rodas originais
    order = sorted(groups, key=lambda k: 0 if k == "TIRE" else 1) if part == "FRONT_WHEEL" else list(groups)
    verts, indices, glist, texs, shs = [], [], [], [], []
    for key in order:
        tris = groups[key]
        r = R[key]
        if r["tex"] not in texs:
            texs.append(r["tex"])
        if r["sh"] not in shs:
            shs.append(r["sh"])
        vmap = {}
        start = len(indices)
        gv = []
        for corners in tris:
            tuv = remap_uv(key, corners)
            for k, (tu, tv) in zip(corners, tuv):
                kk = (k[0], k[1], k[2], k[3], k[4], k[5], round(tu, 6), round(tv, 6))
                if kk not in vmap:
                    vmap[kk] = len(verts)
                    if key == "PAINT":
                        # a pele do carro (CARSKIN) tem o layout do B15; aponta tudo para um ponto liso dela
                        u, v = PAINT_UV
                    else:
                        u, v = tu, tv
                    verts.append((k[0], k[1], k[2], k[3], k[4], k[5], r["color"], u, v))
                    gv.append(verts[-1])
                indices.append(vmap[kk])
        gr = Group(b"\0" * 60)
        gr.bmin = [min(v[i] for v in gv) for i in range(3)]
        gr.bmax = [max(v[i] for v in gv) for i in range(3)]
        gr.count = len(indices) - start
        gr.f = [texs.index(r["tex"]), shs.index(r["sh"]), 0, 0, 0, 0, start]
        gr.flags = r["flags"]
        glist.append(gr)
    assert len(verts) < 65536, (part, len(verts))
    return {"verts": verts, "indices": indices, "groups": glist, "textures": texs, "shaders": shs}


def placeholder_mesh():
    r = R["DULL"]
    verts = [(0, 0, -0.2, 0, 0, 1, r["color"], 0, 0), (0.001, 0, -0.2, 0, 0, 1, r["color"], 0, 0),
             (0, 0.001, -0.2, 0, 0, 1, r["color"], 0, 0)]
    gr = Group(b"\0" * 60)
    gr.bmin, gr.bmax, gr.count = [0, 0, -0.2], [0.001, 0.001, -0.2], 3
    gr.f, gr.flags = [0, 0, 0, 0, 0, 0, 0], r["flags"]
    return {"verts": verts, "indices": [0, 1, 2], "groups": [gr], "textures": [r["tex"]], "shaders": [r["sh"]]}


# ------------------------------------------------------------------ marcadores
def bbox_of(geom, prefix_list):
    pts = []
    for o in geom.objects:
        if o.name.endswith("_A") and any(o.name.startswith(p) for p in prefix_list):
            t = o.translation
            pts += [(v[0] + t[0], v[1] + t[1], v[2] + t[2]) for v in o.verts]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


WORLD_PARTS = ["SENTRA_KIT00_BODY", "SENTRA_KIT00_ROOF", "SENTRA_KIT00_FRONT_BUMPER", "SENTRA_KIT00_REAR_BUMPER",
               "SENTRA_KIT00_SKIRT", "SENTRA_KIT00_HOOD_A", "SENTRA_KIT00_TRUNK_A"]
old_min, old_max = bbox_of(stock, WORLD_PARTS)
new_pts = []
for nm in ("BODY", "ROOF", "FRONT_BUMPER", "REAR_BUMPER", "SKIRT", "HOOD", "TRUNK"):
    new_pts += [c[:3] for _, cs in dump[f"SENTRA_KIT00_{nm}_A"]["tris"] for c in cs]
new_min = [min(p[i] for p in new_pts) for i in range(3)]
new_max = [max(p[i] for p in new_pts) for i in range(3)]


def remap(p):
    return [new_min[i] + (p[i] - old_min[i]) / (old_max[i] - old_min[i]) * (new_max[i] - new_min[i]) for i in range(3)]


KNOWN = {bhash(k): v for k, v in report["markers"].items() if v}


# --- marcadores calculados pela mesma regra que o B15 segue em relacao a propria geometria
def pts_of(name):
    return [c[:3] for _, cs in dump[name]["tris"] for c in cs]


def stock_pts(name):
    return [v[:3] for v in stock.by_name(name).verts]


# retrovisor: x = meio do espelho, y = face interna, z = meio - 0.015 (B15: 0.6155/0.7472/0.7579)
mp = pts_of("SENTRA_KIT00_LEFT_SIDE_MIRROR_A")
mx = (min(p[0] for p in mp) + max(p[0] for p in mp)) / 2
my = min(p[1] for p in mp)
mz = (min(p[2] for p in mp) + max(p[2] for p in mp)) / 2 - 0.015
KNOWN[0x9B971511] = [mx, my, mz]    # retrovisor esquerdo (+Y)
KNOWN[0x0EE87EC4] = [mx, -my, mz]   # retrovisor direito


def roof_scoop(pts, frac=None, marker=None):
    zmax = max(p[2] for p in pts)
    top = [p for p in pts if p[2] > zmax - 0.12 and abs(p[1]) < 0.4]
    x0, x1 = min(p[0] for p in top), max(p[0] for p in top)
    if marker is not None:  # calibra no B15: fracao ao longo do topo e folga ate a superficie
        frac = (marker[0] - x0) / (x1 - x0)
    x = x0 + frac * (x1 - x0)
    near = [p for p in pts if abs(p[0] - x) < 0.08 and abs(p[1]) < 0.15]
    surf = max(p[2] for p in near)
    return frac, x, surf


SCOOP_B15 = (0.1763, 0.0, 1.1531)
frac, _, surf15 = roof_scoop(stock_pts("SENTRA_KIT00_ROOF_A"), marker=SCOOP_B15)
_, sx, surf16 = roof_scoop(pts_of("SENTRA_KIT00_ROOF_A"), frac=frac)
KNOWN[bhash("ROOF_SCOOP")] = [sx, 0.0, surf16 - (surf15 - SCOOP_B15[2])]
print("retrovisor esq:", [round(v, 3) for v in KNOWN[0x9B971511]], "| entrada de ar:",
      [round(v, 3) for v in KNOWN[bhash("ROOF_SCOOP")]], f"(fracao do teto {frac:.2f})")
marker_log = {}


def update_markers(obj, local_part):
    new_extra = []
    for cid, body in obj.extra:
        if cid in (0x00134017, 0x00134018, 0x00134019):
            continue  # normais de emenda do B15: nao valem para a malha nova
        if cid == 0x0013401A and not local_part:
            raw = bytearray(body)  # o leitor ja removeu o preenchimento pela posicao
            for k in range(len(raw) // 80):
                h = struct.unpack_from("<I", raw, k * 80)[0]
                pos = struct.unpack_from("<3f", raw, k * 80 + 16 + 48)
                newp = KNOWN.get(h) or remap(pos)
                struct.pack_into("<3f", raw, k * 80 + 16 + 48, *newp)
                marker_log[f"{obj.name}:{h:08X}"] = ("conhecido" if h in KNOWN else "proporcional", [round(x, 3) for x in pos], [round(x, 3) for x in newp])
            body = bytes(raw)
        new_extra.append((cid, body))
    obj.extra = new_extra
    obj.order = [c for c in obj.order if c not in (0x00134017, 0x00134018, 0x00134019)]


def apply(obj, mesh, translation=(0.0, 0.0, 0.0), local_part=False):
    obj.verts = mesh["verts"]
    idx = list(mesh["indices"])
    if len(idx) % 2:
        idx.append(0)
    obj.indices = idx
    obj.groups = copy.deepcopy(mesh["groups"])
    obj.textures = list(mesh["textures"])
    obj.shaders = list(mesh["shaders"])
    tris = sum(gr.count for gr in obj.groups) // 3
    vs = obj.verts
    obj.set_bbox([min(v[i] for v in vs) for i in range(3)], [max(v[i] for v in vs) for i in range(3)])
    obj.set_translation(translation)
    struct.pack_into("<I", obj.header, 20, tris)
    b24 = bytearray(obj.header[24:28])
    b24[1], b24[2] = len(obj.textures), len(obj.shaders)
    obj.header[24:28] = b24
    struct.pack_into("<I", obj.desc, 16, len(obj.groups))
    struct.pack_into("<I", obj.desc, 36, tris)
    struct.pack_into("<I", obj.desc, 52, len(obj.verts))
    update_markers(obj, local_part)


# ------------------------------------------------------------------ compila as pecas KIT00 / BASE
PLACE = {"DOOR_LEFT", "DOOR_RIGHT", "DOOR_PANEL_LEFT", "DOOR_PANEL_RIGHT", "DOOR_SILL_LEFT", "DOOR_SILL_RIGHT",
         "ENGINE", "ENGINE_UNLIT", "TRUNK_AUDIO", "TRUNK_AUDIO_UNLIT"}
LOCAL = {"FRONT_WHEEL", "FRONT_BRAKE", "REAR_BRAKE", "EXHAUST"}
meshes = {}
for name, d in dump.items():
    base, lod = name.rsplit("_", 1)
    part = "BASE" if base == "SENTRA_BASE" else base.replace("SENTRA_KIT00_", "")
    if part in PLACE:
        continue
    meshes[(part, lod)] = (build_mesh(d, part), d["location"])
PH = placeholder_mesh()

# --- para-choques dianteiros "do B16 de verdade": para-choque de serie + labio/splitter (+ grade escurecida)
B16F = {}
if B16F_PATH:
    for kitn, lods in json.load(open(B16F_PATH)).items():
        for lod, kd in lods.items():
            tris = []
            for mat, cs in dump[f"SENTRA_KIT00_FRONT_BUMPER_{lod}"]["tris"]:
                c = [sum(k[i] for k in cs) / 3 for i in range(3)]
                if kd["black_grille"] and mat == "chrome" and c[0] >= 2.0 and abs(c[1]) <= 0.45 \
                        and 0.28 <= c[2] <= 0.50 and not (abs(c[1]) < 0.09 and c[2] > 0.33):
                    mat = "lb_black"  # moldura da grade preta; o emblema central continua cromado
                tris.append([mat, cs])
            B16F[(kitn, lod)] = build_mesh({"tris": tris + kd["tris"]}, "FRONT_BUMPER")

# --- widebody (KITW01-04): carroceria inteira do B16 (carroceria + para-choques + saia) + body kit gerado
LB = json.load(open(LB_PATH)) if LB_PATH else {}
WIDE = {}
for kitw, lods in LB.items():
    for lod, kd in lods.items():
        tris = []
        for nm in ("BODY", "FRONT_BUMPER", "REAR_BUMPER", "SKIRT"):
            for mat, cs in dump[f"SENTRA_KIT00_{nm}_{lod}"]["tris"]:
                if nm == "FRONT_BUMPER" and mat == "glass":
                    mat = "fog_glass"  # lente dos farois de milha
                tris.append([mat, cs])
        tris += kd["tris"]
        WIDE[(kitw, lod)] = build_mesh({"tris": tris}, "BODY")


def our(part, lod):
    lod = "C" if lod == "D" else lod
    if part in PLACE or part is None:
        return PH, (0, 0, 0)
    m, loc = meshes[(part, lod)]
    return m, (tuple(loc) if part == "SPOILER" else (0.0, 0.0, 0.0))


ALL_PARTS = ["BODY", "BRAKELIGHT", "DOOR_LEFT", "DOOR_RIGHT", "DOOR_PANEL_LEFT", "DOOR_PANEL_RIGHT", "DOOR_SILL_LEFT",
             "DOOR_SILL_RIGHT", "ENGINE", "ENGINE_UNLIT", "EXHAUST", "FRONT_BRAKE", "FRONT_BUMPER", "FRONT_WHEEL",
             "HEADLIGHT_LEFT", "HEADLIGHT_RIGHT", "HOOD", "HOOD_UNDER", "HOOD_LEFT", "HOOD_RIGHT", "HOOD_UNDER_LEFT",
             "HOOD_UNDER_RIGHT", "LEFT_SIDE_MIRROR", "RIGHT_SIDE_MIRROR", "REAR_BRAKE", "REAR_BUMPER", "ROOF", "SKIRT",
             "SPOILER", "TRUNK", "TRUNK_AUDIO", "TRUNK_AUDIO_UNLIT", "TRUNK_UNDER"]
KITS = [f"KIT{i:02d}" for i in range(30)] + [f"KITW{i:02d}" for i in range(1, 5)] + [f"STYLE{i:02d}" for i in range(1, 30)]
FULL = {}
for kit in KITS:
    for p in ALL_PARTS:
        for lod in "ABCD":
            nm = f"{CAR}_{kit}_{p}_{lod}"
            FULL[bhash(nm)] = nm
for lod in "ABCD":
    FULL[bhash(f"{CAR}_BASE_{lod}")] = f"{CAR}_BASE_{lod}"


def full_name(o):
    return FULL.get(o.hash, o.name)


def target_part(objname):
    """Decide qual peca do B16 vai em cada objeto do arquivo (None = placeholder, 'KEEP' = mantem)."""
    n = objname[len(CAR) + 1:]
    base, lod = n.rsplit("_", 1)
    if base == "BASE":
        return "BASE", lod
    if base.startswith(("W01_CV", "W02_CV", "W03_CV", "W04_CV")):
        return "KEEP", lod
    if "DECAL" in base:
        return None, lod
    kit, _, rest = base.partition("_")
    if kit.startswith("KITW"):
        return ("BODY" if rest == "BODY" else None), lod
    if kit.startswith("STYLE"):
        if rest in ("HOOD", "HOOD_LEFT") or (rest == "HOOD_RIGHT" and not NO_MORPH):
            return "HOOD", lod
        if rest in ("HEADLIGHT_LEFT", "HEADLIGHT_RIGHT", "BRAKELIGHT"):
            return rest, lod
        return None, lod  # motores e metade direita de capo dividido
    if kit.startswith("KIT"):
        if rest in PLACE:
            return None, lod
        if rest == "HOOD_UNDER_LEFT" or (rest == "HOOD_UNDER_RIGHT" and not NO_MORPH):
            return "HOOD_UNDER", lod
        if rest == "HOOD_UNDER_RIGHT":
            return None, lod
        return rest, lod
    return "KEEP", lod


# ------------------------------------------------------------------ kits do B15 adaptados ao B16 por deformacao
import numpy as np  # noqa: E402
from kit_morph import Morph  # noqa: E402

MORPHABLE = {"FRONT_BUMPER", "REAR_BUMPER", "SKIRT", "HOOD", "HOOD_UNDER", "HEADLIGHT_LEFT", "HEADLIGHT_RIGHT",
             "BRAKELIGHT"}
# vagas de textura do carro reaproveitadas pelo B16: grupos de kit que as usam sao removidos
OVERWRITTEN = {int(v["hash"], 16) for v in json.load(open(NEWTEX)).values()}
_morphs = {}


B15_AXLES, B16_AXLES = (1.32, -1.22), (1.3996, -1.2996)


def morph_for(part):
    if part not in _morphs:
        src = stock.by_name(f"SENTRA_KIT00_{part}_A")
        sp = np.array([v[:3] for v in src.verts]) + np.array(src.translation)
        if part == "SKIRT":
            # a "saia" do B16 que veio do AC e so uma faixa curta: o alvo e a parte baixa da lateral da
            # carroceria (+ faixa), e o comprimento acompanha o entre-eixos (rodas B15 -> rodas B16)
            tris = np.array([[c[:3] for c in cs] for nm in ("BODY", "SKIRT")
                             for _, cs in dump[f"SENTRA_KIT00_{nm}_A"]["tris"]])
            cen = tris.mean(1)
            tris = tris[(np.abs(cen[:, 1]) > 0.6) & (cen[:, 2] < 0.35) & (np.abs(cen[:, 0]) < 1.9)]
            k = (B16_AXLES[0] - B16_AXLES[1]) / (B15_AXLES[0] - B15_AXLES[1])
            ys = 0.88 / 0.86
            affine = ([k, ys, 1.0], [B16_AXLES[0] - B15_AXLES[0] * k, 0.0, -0.05])
            _morphs[part] = Morph(sp, tris, smoothing=0.1, affine=affine,
                                  src_mask=lambda p: np.abs(p[:, 1]) > 0.75)
        else:
            tris = np.array([[c[:3] for c in cs] for _, cs in dump[f"SENTRA_KIT00_{part}_A"]["tris"]])
            _morphs[part] = Morph(sp, tris, smoothing=0.05)
        err = _morphs[part].fit_error(sp)
        print(f"  deformacao {part}: erro medio {err[0] * 100:.1f} cm, p95 {err[1] * 100:.1f} cm")
    return _morphs[part]


GRILLE_BOX = ((2.0, 3.0), (-0.45, 0.45), (0.28, 0.50))  # grade superior do B16 (x, y, z)


def in_box(c, box=GRILLE_BOX):
    return all(lo <= c[i] <= hi for i, (lo, hi) in enumerate(box))


def transplant_grille(obj, lod):
    """Remove a grade (do B15) do kit e coloca as faces da grade do B16 no lugar."""
    # 1) tira triangulos do kit cujo centro cai na regiao da grade
    t = obj.translation
    new_groups, idx = [], []
    for gr in obj.groups:
        seg = obj.indices[gr.start:gr.start + gr.count]
        kept = []
        for i in range(0, len(seg), 3):
            c = [sum(obj.verts[seg[i + j]][a] + t[a] for j in range(3)) / 3 for a in range(3)]
            if not in_box(c):
                kept += seg[i:i + 3]
        if kept:
            gr.f[6] = len(idx)
            gr.count = len(kept)
            idx += kept
            new_groups.append(gr)
    obj.groups = new_groups
    # 2) acrescenta as faces da grade do B16 (do para-choque de serie compilado, mesmo LOD)
    mesh, _ = meshes[("FRONT_BUMPER", "C" if lod == "D" else lod)]
    verts = list(obj.verts)
    for gr in mesh["groups"]:
        tri_idx = mesh["indices"][gr.f[6]:gr.f[6] + gr.count]
        sel = []
        for i in range(0, len(tri_idx), 3):
            c = [sum(mesh["verts"][tri_idx[i + j]][a] for j in range(3)) / 3 for a in range(3)]
            if in_box(c):
                sel += tri_idx[i:i + 3]
        if not sel:
            continue
        th, sh = mesh["textures"][gr.f[0]], mesh["shaders"][gr.f[1]]
        if th not in obj.textures:
            obj.textures.append(th)
        if sh not in obj.shaders:
            obj.shaders.append(sh)
        remap = {}
        for vi in sel:
            if vi not in remap:
                v = mesh["verts"][vi]
                remap[vi] = len(verts)
                verts.append((v[0] - t[0], v[1] - t[1], v[2] - t[2]) + tuple(v[3:]))
        ng = copy.deepcopy(gr)
        ng.f = [obj.textures.index(th), obj.shaders.index(sh), 0, 0, 0, 0, len(idx)]
        ng.count = len(sel)
        idx += [remap[vi] for vi in sel]
        obj.groups.append(ng)
    obj.verts = verts
    if len(idx) % 2:
        idx.append(0)
    obj.indices = idx
    gs = sum(gr.count for gr in obj.groups)
    struct.pack_into("<I", obj.header, 20, gs // 3)
    b24 = bytearray(obj.header[24:28])
    b24[1], b24[2] = len(obj.textures), len(obj.shaders)
    obj.header[24:28] = b24
    struct.pack_into("<I", obj.desc, 16, len(obj.groups))
    struct.pack_into("<I", obj.desc, 36, gs // 3)
    struct.pack_into("<I", obj.desc, 52, len(obj.verts))
    assert len(obj.verts) < 65536


def morph_kit(obj, part, lod="A"):
    m = morph_for(part)
    t = np.array(obj.translation)
    P = np.array([v[:3] for v in obj.verts]) + t
    N = np.array([v[3:6] for v in obj.verts])
    P2 = m.apply(P) - t
    N2 = m.apply_normals(P, N)
    obj.verts = [(p[0], p[1], p[2], n[0], n[1], n[2], v[6], v[7], v[8]) for p, n, v in zip(P2, N2, obj.verts)]
    # remove grupos que usam texturas reaproveitadas (ex.: emblema SENTRA_BADGING)
    gs = sum(gr.count for gr in obj.groups)
    keep = [gr for gr in obj.groups if obj.textures[gr.f[0]] not in OVERWRITTEN]
    if len(keep) != len(obj.groups):
        idx = []
        for gr in keep:
            seg = obj.indices[gr.start:gr.start + gr.count]
            gr.f[6] = len(idx)
            idx += seg
        obj.groups = keep
        if len(idx) % 2:
            idx.append(0)
        obj.indices = idx
        gs = sum(gr.count for gr in keep)
        struct.pack_into("<I", obj.header, 20, gs // 3)
        struct.pack_into("<I", obj.desc, 16, len(keep))
        struct.pack_into("<I", obj.desc, 36, gs // 3)
        stats["grupos de emblema removidos"] += 1
    if not obj.groups or sum(gr.count for gr in obj.groups) == 0:
        stats["kit so de emblema -> placeholder"] += 1
        apply(obj, PH, (0.0, 0.0, 0.0), local_part=True)
        return
    if part == "FRONT_BUMPER":
        transplant_grille(obj, lod)
        stats["grade do B16 nos kits"] += 1
    for gr in obj.groups:
        vs = [obj.verts[i] for i in obj.indices[gr.start:gr.start + gr.count]]
        if vs:
            gr.bmin = [min(v[i] for v in vs) for i in range(3)]
            gr.bmax = [max(v[i] for v in vs) for i in range(3)]
    vs = obj.verts
    obj.set_bbox([min(v[i] for v in vs) for i in range(3)], [max(v[i] for v in vs) for i in range(3)])
    # marcadores do kit (neon, escape, placa...) seguem a mesma deformacao; normais de emenda do B15 saem
    new_extra = []
    for cid, body in obj.extra:
        if cid in (0x00134017, 0x00134018, 0x00134019):
            continue
        if cid == 0x0013401A:
            raw = bytearray(body)
            for k in range(len(raw) // 80):
                pos = np.array(struct.unpack_from("<3f", raw, k * 80 + 64)) + t
                struct.pack_into("<3f", raw, k * 80 + 64, *(m.apply(pos[None])[0] - t))
            body = bytes(raw)
        new_extra.append((cid, body))
    obj.extra = new_extra
    obj.order = [c for c in obj.order if c not in (0x00134017, 0x00134018, 0x00134019)]


stats = collections.Counter()
unresolved =sorted({o.name for o in g.objects if o.hash not in FULL and "DECAL" not in o.name and "_CV" not in o.name})
assert not unresolved, unresolved
for o in g.objects:
    part, lod = target_part(full_name(o))
    if DIAG_STOCK_WHEELS and part in ("FRONT_WHEEL", "FRONT_BRAKE", "REAR_BRAKE"):
        part = "KEEP"  # diagnostico: mantem roda/freios originais do B15
    if part == "KEEP":
        stats["mantido"] += 1
        continue
    fname = full_name(o)
    is_stock_slot = "_KIT00_" in fname or "_BASE_" in fname
    kw = fname[len(CAR) + 1:].split("_")[0]
    if part == "FRONT_BUMPER" and (kw, "C" if lod == "D" else lod) in B16F:
        apply(o, B16F[(kw, "C" if lod == "D" else lod)], (0.0, 0.0, 0.0))
        stats["para-choque B16 com labio"] += 1
        continue
    if kw.startswith("KITW") and part == "BODY" and (kw, "C" if lod == "D" else lod) in WIDE:
        apply(o, WIDE[(kw, "C" if lod == "D" else lod)], (0.0, 0.0, 0.0))
        stats["widebody estilo overfender"] += 1
        continue
    if not is_stock_slot and part in MORPHABLE and not NO_MORPH:
        morph_kit(o, part, lod)  # mantem o kit do B15 (materiais, UVs) e deforma para o B16
        stats["kit B15 adaptado"] += 1
        continue
    # copias de kit usam a versao leve (LOD C) para o arquivo nao estourar a memoria do jogo
    # rodas: o jogo usa ~500-650 vertices por roda em todos os carros; a versao leve (584) fica nessa faixa
    use_lod = "C" if (not is_stock_slot or part == "FRONT_WHEEL") else lod
    mesh, t = our(part, use_lod)
    apply(o, mesh, t, local_part=part in LOCAL or part == "SPOILER")
    stats["placeholder" if mesh is PH else ("KIT00/BASE" if "KIT00" in o.name or "BASE" in o.name else "kit->serie")] += 1

g.save(OUT)
print("objetos:", dict(stats))
print("avisos de material:", dict(warn))
json.dump({"stats": stats, "markers": marker_log, "warn": {f"{a}|{b}": n for (a, b), n in warn.items()},
           "bbox_old": [old_min, old_max], "bbox_new": [new_min, new_max]},
          open(OUT + ".log.json", "w"), indent=1)
