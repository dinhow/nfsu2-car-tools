"""Gera o TEXTURES.BIN do SENTRA colocando as texturas do B16 em VAGAS existentes (sem acrescentar entradas).

Regras aprendidas no jogo:
- texturas acrescentadas ao pacote nao aparecem;
- texturas de pecas de ESTILO so carregam com a peca equipada;
- a textura do motor so carrega na oficina (nao na corrida).
Por isso so usamos vagas de pecas EXTERNAS de serie (emblemas, farol, lanterna), que sao pequenas (<=128px).
Para manter nitidez, cada textura nova e um RECORTE da regiao realmente usada pelos UVs do B16; o compilador
remapeia os UVs para o recorte (crop gravado no JSON).

python build_textures.py <TEXTURES.BIN original> <pasta texturas AC> <saida TEXTURES.BIN> <mesh_dump.json>
"""
import io
import json
import math
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tpk  # noqa: E402
from tpk_write import TPK  # noqa: E402

src, texdir, dst, dump_path = sys.argv[1:5]
stock = tpk.load(src)

# nome logico -> (arquivo do AC, vaga, materiais do AC que usam essa textura)
SLOTS = {
    "SENTRA_B16_DETAIL_M": ("nodamage_lod0.png", 0x351DDF69, ["matte_colors"]),             # lanterna serie DXT1 128
    "SENTRA_B16_DETAIL_C": ("nodamage_lod0.png", 0xA43D9817, ["chrome", "emblem"]),         # emblemas DXT3 128
    "SENTRA_B16_LIGHTS0": ("lights_lod0.png", 0x9CF2BA76,
                           ["head_light", "reverse_light_lod0", "tail_light_lod0"]),        # farol serie DXT1 128x64
    "SENTRA_B16_LIGHTS1": ("lights_lod1.png", 0x90DFDF02,
                           ["textured_reflector", "reflector", "detail_glass_red", "tail_light2"]),  # lanterna DXT3 64
}
FOURCC = {0x22: "DXT1", 0x24: "DXT3"}

dump = json.load(open(dump_path))


def uv_crop(mats):
    """Caixa (u0,v0,u1,v1) na textura (v para baixo, ja 'embrulhado' em [0,1]) e deslocamento por material."""
    pts, shift = [], {}
    for name, o in dump.items():
        for mat, cs in o["tris"]:
            if mat in mats:
                for c in cs:
                    pts.append((mat, c[6], 1.0 - c[7]))
    for m in mats:
        mp = np.array([(u, v) for mm, u, v in pts if mm == m])
        if len(mp):
            shift[m] = (-math.floor(mp[:, 0].min() + 1e-6), -math.floor(mp[:, 1].min() + 1e-6))
    a = np.array([(u + shift[m][0], v + shift[m][1]) for m, u, v in pts])
    lo = np.clip(np.percentile(a, 0.5, axis=0) - 0.01, 0, 1)
    hi = np.clip(np.percentile(a, 99.5, axis=0) + 0.01, 0, 1)
    return [float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])], shift


def pixels_for(img_path, tr, crop):
    from PIL import Image

    w, h = struct.unpack_from("<2H", tr, 68)
    fmt = FOURCC[tr[74]]
    levels = max(1, tr[78])
    im = Image.open(img_path).convert("RGB").convert("RGBA")  # alfa do AC e mascara de reflexo: descarta
    W, H = im.size
    u0, v0, u1, v1 = crop
    im = im.crop((int(u0 * W), int(v0 * H), max(int(u0 * W) + 4, int(math.ceil(u1 * W))),
                  max(int(v0 * H) + 4, int(math.ceil(v1 * H)))))
    out = b""
    lw, lh = w, h
    for _ in range(levels):
        b = io.BytesIO()
        im.resize((lw, lh), Image.LANCZOS).save(b, format="DDS", pixel_format=fmt)
        out += b.getvalue()[128:]
        lw, lh = max(4, lw // 2), max(4, lh // 2)
    return out


t = TPK(src)
made = {}
for name, (fn, slot, mats) in SLOTS.items():
    st = stock[slot]
    assert st.codec == "JDLZ", hex(slot)
    crop, shift = uv_crop(mats)
    pix = pixels_for(os.path.join(texdir, fn), st.trailer, crop)
    assert len(pix) == st.usz - 156, (name, len(pix), st.usz - 156)
    t.replace(slot, pix + st.data[-156:])  # rodape original intacto
    w, h = struct.unpack_from("<2H", st.trailer, 68)
    made[name] = {"hash": f"{slot:08X}", "slot_name": st.name, "size": [w, h], "crop": crop,
                  "shift": {m: list(s) for m, s in shift.items()}, "materials": mats}
    print(f"{name:22} -> vaga {slot:08X} {w}x{h}  recorte u {crop[0]:.2f}..{crop[2]:.2f} v {crop[1]:.2f}..{crop[3]:.2f}")
t.save(dst)

again = tpk.load(dst)
assert len(again) == len(stock)
slots = {int(v["hash"], 16) for v in made.values()}
for h, s in stock.items():
    if h in slots:
        assert again[h].data[-156:] == s.data[-156:]
    else:
        assert again[h].raw == s.raw, hex(h)
print("texturas:", len(again), "(igual ao original); vagas trocadas:", len(slots))
json.dump(made, open(os.path.join(os.path.dirname(dump_path), "TEXTURES_new_textures.json"), "w"), indent=1)
