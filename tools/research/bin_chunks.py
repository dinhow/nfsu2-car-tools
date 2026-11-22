"""Percorre a arvore de chunks de um .BIN do NFSU2 (bChunk: id u32, size u32).
Uso: python bin_chunks.py <arquivo> [profundidade_max]
"""
import collections
import struct
import sys

data = open(sys.argv[1], "rb").read()
maxdepth = int(sys.argv[2]) if len(sys.argv) > 2 else 3
counts = collections.Counter()


def walk(start, end, depth, path):
    p = start
    while p + 8 <= end:
        cid, size = struct.unpack_from("<II", data, p)
        body = p + 8
        if body + size > end:
            print("  " * depth + f"!! chunk {cid:08X} estoura limite em {p}")
            return
        counts[cid] += 1
        if depth <= maxdepth and (counts[cid] <= 3 or cid & 0x80000000):
            print("  " * depth + f"{cid:08X} size={size} @ {p}")
        if cid & 0x80000000:
            walk(body, body + size, depth + 1, path + [cid])
        p = body + size


walk(0, len(data), 0, [])
print("\nCONTAGEM POR ID:")
for cid, n in sorted(counts.items()):
    print(f"  {cid:08X}: {n}")
