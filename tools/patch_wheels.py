"""Gera COPIAS do GLOBALB com a posicao X das rodas do SENTRA ajustada para o entre-eixos do B16.
Nao altera os arquivos do jogo.

python patch_wheels.py <pasta GLOBAL do jogo> <pasta saida> <front_x> <rear_x>
"""
import os
import struct
import sys

src_dir, out_dir = sys.argv[1], sys.argv[2]
front_x, rear_x = float(sys.argv[3]), float(sys.argv[4])
REC = 2192
# offsets dentro do registro do carro: 4 rodas de 48 bytes a partir de +288 (X, Y, Z, ...)
WHEELS = {"FL": 288, "FR": 336, "RR": 384, "RL": 432}
STOCK = {"FL": (1.32, 0.75), "FR": (1.32, -0.75), "RR": (-1.22, -0.75), "RL": (-1.22, 0.75)}
os.makedirs(out_dir, exist_ok=True)


def find_record(data, car=b"SENTRA"):
    p = 0
    while p + 8 <= len(data):
        cid, size = struct.unpack_from("<II", data, p)
        if cid == 0x00034600:
            body = p + 8
            lead = size - REC * (size // REC)
            for k in range(size // REC):
                st = body + lead + k * REC
                if data[st:st + 32].split(b"\0")[0] == car:
                    return st
        p += 8 + size
    return None


for fname in ("GLOBALB.BUN", "GlobalB.lzc"):
    src = os.path.join(src_dir, fname)
    if not os.path.exists(src):
        print("ausente:", fname)
        continue
    data = bytearray(open(src, "rb").read())
    st = find_record(data)
    if st is None:
        print(f"{fname}: registro SENTRA nao encontrado (arquivo comprimido?) - nada feito")
        continue
    for w, off in WHEELS.items():
        x, y = struct.unpack_from("<2f", data, st + off)
        sx, sy = STOCK[w]
        if abs(x - sx) > 1e-3 or abs(y - sy) > 1e-3:
            raise SystemExit(f"{fname}: roda {w} = ({x:.4f},{y:.4f}), esperado ({sx},{sy}). Abortado.")
        nx = front_x if w in ("FL", "FR") else rear_x
        struct.pack_into("<f", data, st + off, nx)
    dst = os.path.join(out_dir, fname)
    open(dst, "wb").write(data)
    check = [round(struct.unpack_from("<f", data, st + o)[0], 4) for o in WHEELS.values()]
    print(f"{fname}: registro em +{st}, X das rodas FL/FR/RR/RL agora {check} -> {dst}")
