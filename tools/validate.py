"""Valida GEOMETRY.BIN + TEXTURES.BIN gerados contra as regras observadas no original.
python validate.py <pasta jogo> <GEOMETRY novo> <TEXTURES novo>
"""
import os
import struct
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nfsu2_geom import Geometry  # noqa: E402
import tpk  # noqa: E402

game, geo_path, tex_path = sys.argv[1:4]
errs = []
g = Geometry(geo_path)
stock = Geometry(sys.argv[4] if len(sys.argv) > 4 else game + r"\CARS\SENTRA\GEOMETRY.BIN")
assert len(g.objects) == len(stock.objects), "quantidade de objetos mudou"
assert sorted(o.hash for o in g.objects) == sorted(o.hash for o in stock.objects), "hashes mudaram"

# 1) consistencia de cada objeto
for o in g.objects:
    gs = sum(gr.count for gr in o.groups)
    tris = struct.unpack_from("<I", o.desc, 36)[0]
    if gs != tris * 3:
        errs.append(f"{o.name}: soma dos grupos {gs} != 3*tris {tris}")
    if len(o.indices) != gs + (gs % 2):
        errs.append(f"{o.name}: indices {len(o.indices)} vs grupos {gs}")
    if struct.unpack_from("<I", o.desc, 52)[0] != len(o.verts):
        errs.append(f"{o.name}: verts no desc")
    if struct.unpack_from("<I", o.desc, 16)[0] != len(o.groups):
        errs.append(f"{o.name}: grupos no desc")
    if o.indices and max(o.indices[:gs]) >= len(o.verts):
        errs.append(f"{o.name}: indice fora do buffer")
    if o.header[25] != len(o.textures) or o.header[26] != len(o.shaders):
        errs.append(f"{o.name}: contagem textura/shader no cabecalho")
    for gr in o.groups:
        if gr.f[0] >= len(o.textures) or gr.f[1] >= len(o.shaders):
            errs.append(f"{o.name}: grupo aponta textura/shader inexistente")
        if gr.start + gr.count > gs:
            errs.append(f"{o.name}: grupo passa do fim")
    for v in o.verts:
        if any(x != x or abs(x) > 1e4 for x in v[:6] + v[7:]):
            errs.append(f"{o.name}: NaN/valor absurdo em vertice")
            break

# 2) indice do solid list aponta para cada objeto
d = open(geo_path, "rb").read()
i = d.find(struct.pack("<I", 0x00134004))
size = struct.unpack_from("<I", d, i + 4)[0]
for k in range(size // 24):
    h, off, s1, s2, _, _ = struct.unpack_from("<6I", d, i + 8 + k * 24)
    cid, csz = struct.unpack_from("<II", d, off)
    if cid != 0x80134010 or csz + 8 != s1 or off % 128:
        errs.append(f"indice: objeto {h:08X} offset {off} invalido")
info = d.find(struct.pack("<I", 0x00134002))
after_off, after_size = struct.unpack_from("<II", d, info + 8 + 104)
if struct.unpack_from("<I", d, after_off)[0] != 0x80034020:
    errs.append("00134002 +104 nao aponta para o chunk 0x80034020")

# 3) gravacao deterministica: reler e regravar tem que dar o mesmo arquivo
tmp = os.path.join(tempfile.gettempdir(), "val_geo.bin")
g.save(tmp)
if open(tmp, "rb").read() != d:
    errs.append("regravacao do arquivo novo nao e identica")

# 4) texturas: tudo que a geometria usa existe em algum pacote
tex_new = tpk.load(tex_path)
tex_shared = tpk.load(game + r"\CARS\TEXTURES.BIN")
stock_used = {h for o in stock.objects for h in o.textures}
for t in tex_new.values():
    if t.codec not in ("JDLZ", "HUFF"):
        errs.append(f"textura {t.hash:08X}: dados nao comecam com JDLZ/HUFF ({t.codec})")
missing = set()
for o in g.objects:
    for h in o.textures:
        if h not in tex_new and h not in tex_shared and h not in stock_used:
            missing.add(h)
if missing:
    errs.append(f"texturas inexistentes: {[hex(x) for x in missing]}")

print("objetos:", len(g.objects), "| texturas no pacote novo:", len(tex_new), "| tamanho:", len(d))
print("ERROS:" if errs else "VALIDACAO OK - nenhum erro", *errs[:30], sep="\n  ")
