"""Recupera nomes completos de objetos truncados usando o hash do cabecalho (+16)."""
import struct
import sys


def bhash(s):
    h = 0xFFFFFFFF
    for c in s.encode():
        h = (h * 33 + c) & 0xFFFFFFFF
    return h


data = open(sys.argv[1], "rb").read()
pending = []


def walk(start, end):
    p = start
    while p + 8 <= end:
        cid, size = struct.unpack_from("<II", data, p)
        body = p + 8
        if cid == 0x00134011:
            hdr = data[body:body + size]
            name = hdr[164:hdr.index(b"\0", 164)].decode()
            h = struct.unpack_from("<I", hdr, 16)[0]
            pending.append((name, h))
        elif cid & 0x80000000:
            walk(body, body + size)
        p = body + size


walk(0, len(data))
ok = sum(1 for n, h in pending if bhash(n) == h)
print(f"{ok}/{len(pending)} nomes batem com o hash do cabecalho")

suffixes = ["LEFT", "RIGHT", "LEFT_A", "RIGHT_A", "MIRROR_A", "MIRROR_B", "MIRROR_C", "UNLIT_A", "UNLIT_B", "UNLIT_C",
            "UNDER_A", "UNDER_B", "UNDER_C"]
words = ["", "_A", "_B", "_C", "_D", "T_A", "T_B", "T_C", "HT_A", "HT_B", "HT_C", "IGHT_A", "IGHT_B", "IGHT_C",
         "FT_A", "FT_B", "FT_C", "EFT_A", "EFT_B", "EFT_C", "OR_A", "OR_B", "OR_C", "ROR_A", "ROR_B", "ROR_C",
         "RROR_A", "RROR_B", "RROR_C", "IRROR_A", "IRROR_B", "IRROR_C", "LIT_A", "LIT_B", "LIT_C", "NLIT_A",
         "NLIT_B", "NLIT_C", "DER_A", "DER_B", "DER_C", "ER_A", "ER_B", "ER_C", "R_A", "R_B", "R_C"]
resolved = {}
for n, h in pending:
    if bhash(n) == h:
        continue
    for w in words:
        if bhash(n + w) == h:
            resolved[n] = n + w
            break
for n, h in pending:
    if bhash(n) != h and "KIT00" in n or ("BASE" in n and bhash(n) != h):
        print(f"{n:30} -> {resolved.get(n, '??')}")
