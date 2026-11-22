"""Inspeciona o chunk CarTypeInfo (0x00034600) do GLOBALB.BUN do NFSU2.
Uso: python cartypeinfo.py <GLOBALB.BUN> <CARRO> [CARRO2 ...] [--diff]
Registros de 2192 bytes (46 carros); o chunk tem 8 bytes de alinhamento antes.
"""
import struct
import sys

REC = 2192
args = [a for a in sys.argv[2:] if not a.startswith("--")]
data = open(sys.argv[1], "rb").read()
p = 0
while p + 8 <= len(data):
    cid, size = struct.unpack_from("<II", data, p)
    if cid == 0x00034600:
        break
    p += 8 + size
body = p + 8
chunk = data[body:body + size]
lead = size - REC * (size // REC)
print(f"chunk CarTypeInfo @ arquivo+{body}, size={size}, alinhamento inicial={lead}, carros={size // REC}")


def rec_of(name):
    for k in range(size // REC):
        st = lead + k * REC
        nm = chunk[st:st + 32].split(b"\0")[0].decode(errors="replace")
        if nm.upper() == name.upper():
            return st, chunk[st:st + REC]
    return None, None


recs = {}
for car in args:
    st, r = rec_of(car)
    if r is None:
        print("nao achei", car)
        continue
    recs[car] = r
    print(f"{car}: registro em arquivo+{body + st}")

if "--diff" in sys.argv and len(recs) >= 2:
    a, b = list(recs.values())[:2]
    na, nb = list(recs.keys())[:2]
    print(f"\nfloats diferentes entre {na} e {nb} (offset: A | B):")
    for o in range(0, REC - 3, 4):
        fa, fb = struct.unpack_from("<f", a, o)[0], struct.unpack_from("<f", b, o)[0]
        if a[o:o + 4] != b[o:o + 4] and (0.01 < abs(fa) < 20 or 0.01 < abs(fb) < 20):
            print(f"  +{o:4}: {fa:9.4f} | {fb:9.4f}")
else:
    for car, r in recs.items():
        print(f"\n==== {car}")
        for o in range(0, REC, 16):
            vals = struct.unpack_from("<4f", r, o) if o + 16 <= REC else ()
            txt = "".join(chr(c) if 32 <= c < 127 else "." for c in r[o:o + 16])
            print(f"  +{o:4}: {' '.join(f'{v:9.4f}' if abs(v) < 1e5 else '      ---' for v in vals)}  {txt}")
