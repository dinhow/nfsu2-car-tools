"""Leitura e gravacao do GEOMETRY.BIN de carro do NFSU2 (solid list 0x80134000).

Modelo:
  Geometry.top        lista de chunks de topo (o solid list vira um objeto; os demais ficam crus)
  Geometry.header     chunks do 0x80134001 (info, tabela de hashes, indice)
  Geometry.objects    lista de Obj (na ordem do arquivo)
Obj:
  name, hash, header (bytes 192, editavel via props), textures [hash], shaders [hash],
  desc (bytes do 0x00134900), verts [(x,y,z,nx,ny,nz,color,u,v)], groups [Group], indices [int],
  extra [(id, bytes)] chunks apos a malha (marcadores, 17/18/19), order (ordem dos chunks)
"""
import struct

ALIGN_OBJ = 128
MESH_ALIGN = {0x00134900: 16, 0x00134B01: 128, 0x00134B02: 16, 0x00134B03: 16}
VERT = struct.Struct("<6fI2f")  # pos, normal, cor ARGB, uv
GROUP = struct.Struct("<3fI3f7II")  # bbox min, n_indices, bbox max, 7 campos, flags
assert VERT.size == 36 and GROUP.size == 60


def bhash(s):
    h = 0xFFFFFFFF
    for c in s.encode():
        h = (h * 33 + c) & 0xFFFFFFFF
    return h


def chunks(data, start, end):
    p = start
    while p + 8 <= end:
        cid, size = struct.unpack_from("<II", data, p)
        yield cid, p, size
        p += 8 + size


def strip_pad(blob):
    n = 0
    while n < len(blob) and blob[n] == 0x11:
        n += 1
    return blob[n:], n


class Group:
    def __init__(self, raw):
        v = GROUP.unpack(raw)
        self.bmin = list(v[0:3])
        self.count = v[3]
        self.bmax = list(v[4:7])
        self.f = list(v[7:14])  # f[0]=indice textura, f[1]=indice shader, f[6]=inicio no index buffer
        self.flags = v[14]

    @property
    def tex(self):
        return self.f[0]

    @property
    def start(self):
        return self.f[6]

    def pack(self):
        return GROUP.pack(*self.bmin, self.count, *self.bmax, *self.f, self.flags)


class Obj:
    def parse(self, data, p, size):
        self.order = []
        self.extra = []
        for cid, q, s in chunks(data, p + 8, p + 8 + size):
            body = data[q + 8:q + 8 + s]
            if cid == 0x00134011:
                self.header = bytearray(body)
            elif cid == 0x00134012:
                self.textures = [struct.unpack_from("<I", body, k * 8)[0] for k in range(s // 8)]
            elif cid == 0x00134013:
                self.shaders = [struct.unpack_from("<I", body, k * 8)[0] for k in range(s // 8)]
            elif cid == 0x80134100:
                self.mesh_order = []
                for c2, q2, s2 in chunks(data, q + 8, q + 8 + s):
                    b2 = data[q2 + 8:q2 + 8 + s2]
                    self.mesh_order.append(c2)
                    # preenchimento 0x11 ate alinhar os dados (pela posicao absoluta, nunca pelo conteudo)
                    align = MESH_ALIGN[c2]
                    pad = (-(q2 + 8)) % align
                    assert b2[:pad] == b"\x11" * pad, (self.name_hint(), hex(c2), pad, b2[:pad])
                    b2 = b2[pad:]
                    if c2 == 0x00134900:
                        self.desc = bytearray(b2)
                    elif c2 == 0x00134B01:
                        vb = b2
                        assert len(vb) % 36 == 0, (self.name_hint(), len(vb))
                        self.verts = [VERT.unpack_from(vb, k * 36) for k in range(len(vb) // 36)]
                    elif c2 == 0x00134B02:
                        gb = b2
                        assert len(gb) % 60 == 0, len(gb)
                        self.groups = [Group(gb[k * 60:(k + 1) * 60]) for k in range(len(gb) // 60)]
                    elif c2 == 0x00134B03:
                        self.indices = list(struct.unpack_from(f"<{len(b2) // 2}H", b2))
                    else:
                        raise ValueError(f"chunk de malha desconhecido {c2:08X}")
            elif cid == 0x0013401A:
                # marcadores: dados alinhados em 16; guarda so o conteudo
                pad = (-(q + 8)) % 16
                assert body[:pad] == b"\x11" * pad, (self.name_hint(), pad)
                self.extra.append((cid, body[pad:]))
            else:
                self.extra.append((cid, body))
            self.order.append(cid)
        self.name = self.header[164:self.header.index(b"\0", 164)].decode()
        self.hash = struct.unpack_from("<I", self.header, 16)[0]
        return self

    def name_hint(self):
        try:
            return self.header[164:self.header.index(b"\0", 164)].decode()
        except Exception:
            return "?"

    # campos do cabecalho
    def set_bbox(self, bmin, bmax):
        struct.pack_into("<3f", self.header, 32, *bmin)
        struct.pack_into("<3f", self.header, 48, *bmax)

    def set_translation(self, t):
        struct.pack_into("<3f", self.header, 112, *t)

    @property
    def translation(self):
        return struct.unpack_from("<3f", self.header, 112)

    def write(self, out_offset):
        """Gera o chunk 0x80134010 comecando no offset absoluto out_offset."""
        parts = []
        pos = out_offset + 8

        def emit(cid, body):
            nonlocal pos
            parts.append(struct.pack("<II", cid, len(body)) + body)
            pos += 8 + len(body)

        def padded(cid, payload, align):
            # preenche com 0x11 no inicio do corpo ate os dados ficarem alinhados
            body_at = pos + 8
            pad = (-body_at) % align
            emit(cid, b"\x11" * pad + payload)

        extra = iter(self.extra)
        for cid in self.order:
            if cid == 0x00134011:
                emit(cid, bytes(self.header))
            elif cid == 0x00134012:
                emit(cid, b"".join(struct.pack("<II", h, 0) for h in self.textures))
            elif cid == 0x00134013:
                emit(cid, b"".join(struct.pack("<II", h, 0) for h in self.shaders))
            elif cid == 0x80134100:
                start = pos
                parts.append(None)  # cabecalho do container preenchido depois
                idx_hdr = len(parts) - 1
                pos += 8
                for c2 in self.mesh_order:
                    if c2 == 0x00134900:
                        padded(c2, bytes(self.desc), 16)
                    elif c2 == 0x00134B01:
                        padded(c2, b"".join(VERT.pack(*v) for v in self.verts), 128)
                    elif c2 == 0x00134B02:
                        padded(c2, b"".join(g.pack() for g in self.groups), 16)
                    elif c2 == 0x00134B03:
                        padded(c2, struct.pack(f"<{len(self.indices)}H", *self.indices), 16)
                parts[idx_hdr] = struct.pack("<II", 0x80134100, pos - start - 8)
            else:
                ecid, body = next(extra)
                assert ecid == cid
                if cid == 0x0013401A:
                    padded(cid, body, 16)
                else:
                    emit(cid, body)
        body = b"".join(parts)
        return struct.pack("<II", 0x80134010, len(body)) + body


class Geometry:
    def __init__(self, path):
        data = open(path, "rb").read()
        self.data = data
        self.top = list(chunks(data, 0, len(data)))
        cid, p, size = self.top[0]
        assert cid == 0x80134000
        self.solid_children = []  # (cid, conteudo) em ordem; objetos viram ("OBJ", Obj)
        self.objects = []
        for c, q, s in chunks(data, p + 8, p + 8 + size):
            if c == 0x80134010:
                o = Obj().parse(data, q, s)
                self.objects.append(o)
                self.solid_children.append(("OBJ", o))
            elif c == 0x80134001:
                self.header = {c2: bytearray(data[q2 + 8:q2 + 8 + s2]) for c2, q2, s2 in chunks(data, q + 8, q + 8 + s)}
                self.header_order = [c2 for c2, _, _ in chunks(data, q + 8, q + 8 + s)]
                self.solid_children.append(("HDR", None))
            elif c == 0x00000000:
                self.solid_children.append(("PAD", s))
            else:
                self.solid_children.append(("RAW", (c, data[q + 8:q + 8 + s])))
        # chunks depois do solid list, com o offset onde o seguinte comeca no original
        self.after = [(c, data[q + 8:q + 8 + s], q + 8 + s) for c, q, s in self.top[1:]]

    def by_name(self, name):
        return next(o for o in self.objects if o.name == name or bhash(name) == o.hash)

    def save(self, path):
        out = bytearray()
        out += b"\0" * 8  # cabecalho do 0x80134000 (preenchido no fim)
        index = {}
        hdr_pos = None
        kids = self.solid_children
        for k, (kind, val) in enumerate(kids):
            if kind == "HDR":
                hdr_pos = len(out)
                out += self._header_bytes(index_placeholder=True)
            elif kind == "PAD":
                # recalcula: objetos alinham em 128, o cabecalho em 16
                nxt = kids[k + 1][0] if k + 1 < len(kids) else "OBJ"
                align = 16 if nxt == "HDR" else ALIGN_OBJ
                pad = (-(len(out) + 8)) % align
                out += struct.pack("<II", 0, pad) + b"\0" * pad
            elif kind == "RAW":
                c, b = val
                out += struct.pack("<II", c, len(b)) + b
            else:
                o = val
                if len(out) % ALIGN_OBJ:
                    pad = (-(len(out) + 8)) % ALIGN_OBJ
                    out += struct.pack("<II", 0, pad) + b"\0" * pad
                blob = o.write(len(out))
                index[o.hash] = (len(out), len(blob))
                out += blob
        struct.pack_into("<II", out, 0, 0x80134000, len(out) - 8)
        # chunks de topo seguintes (padding + 0x80034020 ...)
        after_pos = None
        for c, b, orig_end in self.after:
            if c == 0x00000000:
                # mantem o layout original quando cabe; senao alinha em 128
                if len(out) + 8 <= orig_end:
                    pad = orig_end - len(out) - 8
                else:
                    pad = (-(len(out) + 8)) % ALIGN_OBJ
                out += struct.pack("<II", 0, pad) + b"\0" * pad
            else:
                if after_pos is None:
                    after_pos = (len(out), len(b) + 8)
                out += struct.pack("<II", c, len(b)) + b
        # atualiza cabecalho com o indice real
        self._fill_header(out, hdr_pos, index, after_pos)
        open(path, "wb").write(out)
        return out

    def _header_bytes(self, index_placeholder):
        parts = b""
        for c in self.header_order:
            parts += struct.pack("<II", c, len(self.header[c])) + bytes(self.header[c])
        return struct.pack("<II", 0x80134001, len(parts)) + parts

    def _fill_header(self, out, hdr_pos, index, after_pos):
        p = hdr_pos + 8
        for c in self.header_order:
            size = len(self.header[c])
            body = p + 8
            if c == 0x00134002:
                struct.pack_into("<I", out, body + 12, len(self.objects))
                if after_pos:
                    struct.pack_into("<II", out, body + 104, *after_pos)
            elif c == 0x00134003:
                hashes = sorted(index)
                for k, h in enumerate(hashes):
                    struct.pack_into("<II", out, body + k * 8, h, 0)
            elif c == 0x00134004:
                for k, h in enumerate(sorted(index)):
                    off, sz = index[h]
                    rest = struct.unpack_from("<6I", self.header[c], k * 24)
                    struct.pack_into("<6I", out, body + k * 24, h, off, sz, sz, rest[4], rest[5])
            p = body + size
