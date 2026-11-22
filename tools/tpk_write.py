"""Gravador de TPK (TEXTURES.BIN de carro do NFSU2) e criacao de texturas novas.

Estrategia: mantem todos os dados originais intactos e acrescenta texturas novas no fim.
- 33310002 (lista de hashes) e 33310003 (entradas) sao regenerados em ordem de hash.
- O bloco de dados (B3320000) e realinhado em 128, entao todos os offsets absolutos andam
  um multiplo de 128 e nenhum alinhamento quebra.
"""
import io
import struct
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from jdlz import compress_literal, decompress  # noqa: E402
from nfsu2_geom import bhash  # noqa: E402


def chunks(d, start, end):
    p = start
    while p + 8 <= end:
        c, s = struct.unpack_from("<II", d, p)
        yield c, p, s
        p += 8 + s


class TPK:
    def __init__(self, path):
        d = open(path, "rb").read()
        self.d = d
        (c0, p0, s0), = [x for x in chunks(d, 0, len(d))][:1]
        assert c0 == 0xB3300000
        self.top_children = list(chunks(d, p0 + 8, p0 + 8 + s0))
        hdr = next(x for x in self.top_children if x[0] == 0xB3310000)
        dat = next(x for x in self.top_children if x[0] == 0xB3320000)
        self.hdr_children = {c: d[p + 8:p + 8 + s] for c, p, s in chunks(d, hdr[1] + 8, hdr[1] + 8 + hdr[2])}
        self.hdr_order = [c for c, _, _ in chunks(d, hdr[1] + 8, hdr[1] + 8 + hdr[2])]
        self.dat_children = list(chunks(d, dat[1] + 8, dat[1] + 8 + dat[2]))
        e = self.hdr_children[0x33310003]
        self.entries = [list(struct.unpack_from("<6I", e, k * 24)) for k in range(len(e) // 24)]
        db = next(x for x in self.dat_children if x[0] == 0x33320002)
        self.data_body = db[1] + 8
        self.data = bytearray(d[db[1] + 8:db[1] + 8 + db[2]])
        self.new = []  # (hash, blob, usz)

    def replace(self, h, raw):
        """Troca o conteudo (descomprimido) de uma textura existente, mantendo hash e tamanho."""
        e = next(e for e in self.entries if e[0] == h)
        assert len(raw) == e[3], (hex(h), len(raw), e[3])
        self.replaced = getattr(self, "replaced", {})
        self.replaced[h] = compress_literal(raw)

    def rebuild_data(self):
        """Reconstroi a regiao de dados na ordem original dos blobs (alinhados em 64), aplicando trocas."""
        rep = getattr(self, "replaced", {})
        order = sorted(self.entries, key=lambda e: e[1])
        data = bytearray()
        # o primeiro blob comeca no mesmo deslocamento relativo do original
        first_rel = order[0][1] - self.data_body
        data += b"\x11" * first_rel
        for e in order:
            while (len(data) + self.data_body) % 64:
                data += b"\x11"
            blob = rep.get(e[0]) or self.d[e[1]:e[1] + e[2]]
            e[1] = self.data_body + len(data)  # offset absoluto provisorio (ajustado no save)
            e[2] = len(blob)
            data += blob
        self.data = data

    def add(self, h, blob, usz):
        assert all(e[0] != h for e in self.entries), "hash ja existe"
        self.new.append((h, blob, usz))

    def save(self, path):
        if getattr(self, "replaced", None):
            self.rebuild_data()
        d = self.d
        # 1) dados: originais + novos (cada blob alinhado em 64 dentro do arquivo final)
        data = bytearray(self.data)
        entries = [e[:] for e in self.entries]
        rel = {}
        for h, blob, usz in self.new:
            # alinhamento relativo: o corpo de dados comeca alinhado em 128 (garantido abaixo)
            while (len(data) + (self.data_body % 128)) % 64:
                data += b"\x11"
            rel[h] = len(data)
            data += blob
            entries.append([h, None, len(blob), usz, 0x100, 0])
        while (len(data) + self.data_body) % 128:
            data += b"\x00"
        entries.sort(key=lambda e: e[0])
        # 2) cabecalho regenerado
        hdr = dict(self.hdr_children)
        hdr[0x33310002] = b"".join(struct.pack("<II", e[0], 0) for e in entries)

        def build_hdr(ent_bytes):
            hdr[0x33310003] = ent_bytes
            body = b"".join(struct.pack("<II", c, len(hdr[c])) + hdr[c] for c in self.hdr_order)
            return struct.pack("<II", 0xB3310000, len(body)) + body

        out = bytearray()
        out += b"\0" * 8
        new_data_body = None
        for c, p, s in self.top_children:
            if c == 0xB3310000:
                hdr_at = len(out)
                out += build_hdr(b"\0" * (24 * len(entries)))
            elif c == 0x00000000:
                # padding: o proximo chunk fica com o mesmo resto mod 128 que tinha no original
                target = (p + 8 + s) % 128
                pad = (target - (len(out) + 8)) % 128
                out += struct.pack("<II", 0, pad) + b"\0" * pad
            elif c == 0xB3320000:
                parts = b""
                start = len(out) + 8
                for c2, p2, s2 in self.dat_children:
                    if c2 == 0x33320002:
                        new_data_body = start + len(parts) + 8
                        parts += struct.pack("<II", c2, len(data)) + bytes(data)
                    else:
                        parts += d[p2:p2 + 8 + s2]
                out += struct.pack("<II", c, len(parts)) + parts
            else:
                out += d[p:p + 8 + s]
        struct.pack_into("<II", out, 0, 0xB3300000, len(out) - 8)
        delta = new_data_body - self.data_body
        assert delta % 128 == 0, delta
        for e in entries:
            if e[1] is None:
                e[1] = new_data_body + rel[e[0]]
            elif e[0] not in rel:
                e[1] = e[1] + delta
        ent_bytes = b"".join(struct.pack("<6I", *e) for e in entries)
        # reescreve o cabecalho com as entradas reais
        h = build_hdr(ent_bytes)
        out[hdr_at:hdr_at + len(h)] = h
        open(path, "wb").write(out)
        return bytes(out)


# ------------------------------------------------------------------ criacao de texturas
def _pow2_le(n, cap):
    p = 1
    while p * 2 <= min(n, cap):
        p *= 2
    return p


def make_texture(img_path, name, template_trailer, fmt="DXT1", max_size=512, min_mip=4, flip_v=False):
    """Retorna (hash, blob_jdlz, usz). template_trailer: rodape (156 bytes) de uma textura do mesmo formato."""
    from PIL import Image

    im = Image.open(img_path).convert("RGBA")
    w = _pow2_le(im.width, max_size)
    h = _pow2_le(im.height, max_size)
    im = im.resize((w, h), Image.LANCZOS)
    if flip_v:
        im = im.transpose(Image.FLIP_TOP_BOTTOM)
    levels = []
    lw, lh, cur = w, h, im
    while True:
        b = io.BytesIO()
        cur.save(b, format="DDS", pixel_format=fmt)
        levels.append(b.getvalue()[128:])
        if lw <= min_mip or lh <= min_mip:
            break
        lw, lh = max(1, lw // 2), max(1, lh // 2)
        cur = im.resize((lw, lh), Image.LANCZOS)
    pix = b"".join(levels)
    th = bhash(name)
    tr = bytearray(template_trailer)
    nb = name.encode()[:23]
    tr[12:36] = nb + b"\0" * (24 - len(nb))
    struct.pack_into("<I", tr, 36, th)
    struct.pack_into("<I", tr, 56, len(pix))
    struct.pack_into("<I", tr, 64, len(levels[0]))
    struct.pack_into("<2H", tr, 68, w, h)
    tr[72] = w.bit_length() - 1
    tr[73] = h.bit_length() - 1
    struct.pack_into("<H", tr, 76, len(levels))
    raw = pix + bytes(tr)
    blob = compress_literal(raw)
    back, n = decompress(blob)
    assert back == raw and n == len(raw)
    return th, blob, len(raw), tr


def set_virtual_offsets(trailers_existing_max_end, tr):
    """Coloca a textura nova depois do fim do layout virtual (+48/+52) das existentes."""
    off = (trailers_existing_max_end + 127) // 128 * 128
    size = struct.unpack_from("<I", tr, 56)[0]
    struct.pack_into("<I", tr, 48, off)
    struct.pack_into("<I", tr, 52, (off + size + 127) // 128 * 128)
    return struct.unpack_from("<I", tr, 52)[0]


if __name__ == "__main__":
    t = TPK(sys.argv[1])
    out = t.save(sys.argv[2])
    print("identico" if out == t.d else f"difere (orig {len(t.d)} novo {len(out)})")
