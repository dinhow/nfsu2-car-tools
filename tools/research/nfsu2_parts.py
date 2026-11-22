"""Lista objetos de um GEOMETRY.BIN do NFSU2: nome, bbox, matriz, marcadores, contagem de vertices/tris.
Uso: python nfsu2_parts.py <GEOMETRY.BIN> [filtro] [--markers] [--json saida.json]
"""
import json
import struct
import sys

args = sys.argv[1:]
path = args[0]
flt = args[1] if len(args) > 1 and not args[1].startswith("--") else ""
show_markers = "--markers" in args
json_out = args[args.index("--json") + 1] if "--json" in args else None
data = open(path, "rb").read()
objs = []


def sub(body, size):
    out = {}
    q = body
    while q + 8 <= body + size:
        c, s = struct.unpack_from("<II", data, q)
        out.setdefault(c, []).append((q + 8, s))
        if c & 0x80000000:
            for k, v in sub(q + 8, s).items():
                out.setdefault(k, []).extend(v)
        q += 8 + s
    return out


def walk(start, end):
    p = start
    while p + 8 <= end:
        cid, size = struct.unpack_from("<II", data, p)
        body = p + 8
        if cid == 0x80134010:
            ch = sub(body, size)
            hb, hs = ch[0x00134011][0]
            hdr = data[hb:hb + hs]
            nm_start = 164
            name = hdr[nm_start:hdr.index(b"\0", nm_start)].decode()
            bmin = struct.unpack_from("<3f", hdr, 32)
            bmax = struct.unpack_from("<3f", hdr, 48)
            mat = struct.unpack_from("<16f", hdr, 64)
            o = {"name": name, "min": [round(v, 4) for v in bmin], "max": [round(v, 4) for v in bmax],
                 "translation": [round(v, 4) for v in mat[12:15]],
                 "matrix_identity": all(abs(a - b) < 1e-5 for a, b in zip(mat[:12], (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0)))}
            # descricao da malha: 0x00134900
            if 0x00134B01 in ch:
                o["vbuf_bytes"] = sum(s for _, s in ch[0x00134B01])
            if 0x00134B03 in ch:
                o["ibuf_bytes"] = sum(s for _, s in ch[0x00134B03])
            if 0x0013401A in ch:
                mb, ms = ch[0x0013401A][0]
                raw = data[mb:mb + ms]
                pad = 0
                while pad < len(raw) and raw[pad] == 0x11:
                    pad += 1
                raw = raw[pad:]
                ms = len(raw)
                o["markers_raw_len"] = ms
                o["markers"] = []
                # tentativa: registros de 80 bytes = hash u32, 3x u32 pad, matriz 4x4 floats
                if ms % 80 == 0:
                    for i in range(ms // 80):
                        rec = raw[i * 80:(i + 1) * 80]
                        h = struct.unpack_from("<I", rec, 0)[0]
                        m = struct.unpack_from("<16f", rec, 16)
                        o["markers"].append({"hash": f"{h:08X}", "pos": [round(v, 4) for v in m[12:15]],
                                             "rot_rows": [[round(v, 3) for v in m[r * 4:r * 4 + 3]] for r in range(3)]})
                else:
                    o["markers_hex"] = raw[:160].hex(" ")
            objs.append(o)
        elif cid & 0x80000000:
            walk(body, body + size)
        p = body + size


walk(0, len(data))
for o in objs:
    if flt and flt not in o["name"]:
        continue
    size = [round(b - a, 3) for a, b in zip(o["min"], o["max"])]
    tri = o.get("ibuf_bytes", 0) // 2 // 3
    print(f"{o['name']:34} min={o['min']} max={o['max']} size={size} ~tris={tri} "
          f"{'' if o['matrix_identity'] else 'MATRIZ!'} T={o['translation']} mk={len(o.get('markers', [])) or o.get('markers_raw_len', '')}")
    if show_markers:
        for m in o.get("markers", []):
            print(f"     marker {m['hash']} pos={m['pos']} rot={m['rot_rows']}")
        if "markers_hex" in o:
            print("     raw:", o["markers_hex"])
if json_out:
    json.dump(objs, open(json_out, "w"), indent=1)
