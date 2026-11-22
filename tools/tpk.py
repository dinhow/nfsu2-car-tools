"""TPK (TEXTURES.BIN) do NFSU2: leitura das entradas, descompressao JDLZ e nomes."""
import struct
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from jdlz import decompress  # noqa: E402
from nfsu2_geom import bhash  # noqa: E402

TRAILER = 156  # TextureInfo (124) + bloco de formato (32)


class Tex:
    pass


def load(path):
    d = open(path, "rb").read()

    def body(cid):
        i = d.find(struct.pack("<I", cid))
        s = struct.unpack_from("<I", d, i + 4)[0]
        return i + 8, s

    io, isz = body(0x33310003)
    out = {}
    for k in range(isz // 24):
        h, off, csz, usz, flags, z = struct.unpack_from("<6I", d, io + k * 24)
        t = Tex()
        t.hash, t.off, t.csz, t.usz, t.flags = h, off, csz, usz, flags
        t.raw = d[off:off + csz]
        t.codec = t.raw[:4].decode(errors="replace")
        t.name = None
        t.data = None
        if t.codec == "JDLZ":
            t.data, n = decompress(t.raw)
            assert n == usz
            tr = t.data[-TRAILER:]
            t.trailer = tr
            # o nome fica antes do hash dentro do TextureInfo
            hp = tr.find(struct.pack("<I", h))
            if hp >= 24:
                for start in range(hp - 24, hp):
                    cand = tr[start:hp].split(b"\0")[0]
                    if cand and bhash(cand.decode(errors="replace")) == h:
                        t.name = cand.decode()
                        break
                t.info_off = hp  # offset do hash dentro do rodape
        out[h] = t
    return out


if __name__ == "__main__":
    texs = load(sys.argv[1])
    named = sum(1 for t in texs.values() if t.name)
    print(f"{len(texs)} texturas, {named} com nome confirmado pelo hash")
    show = [t for t in texs.values() if t.name][:3]
    for t in show:
        print(f"\n{t.name} usz={t.usz} hash@trailer+{t.info_off}")
        for o in range(0, TRAILER, 16):
            row = t.trailer[o:o + 16]
            print(f"  +{o:3}: {row.hex(' ')}  {struct.unpack_from('<4I', row)}")
