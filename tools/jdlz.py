"""JDLZ (compressor LZ da EA usado nos TPK do NFSU2/MW)."""
import struct


def decompress(src):
    assert src[:4] == b"JDLZ", src[:4]
    out_len, in_len = struct.unpack_from("<II", src, 8)
    out = bytearray(out_len)
    ip, op = 16, 0
    f1 = f2 = 1
    end = min(len(src), in_len)
    while ip < end and op < out_len:
        if f1 == 1:
            f1 = src[ip] | 0x100
            ip += 1
        if f2 == 1:
            f2 = src[ip] | 0x100
            ip += 1
        if f1 & 1:
            if f2 & 1:
                length = (src[ip + 1] | ((src[ip] & 0xF0) << 4)) + 3
                dist = (src[ip] & 0x0F) + 1
            else:
                dist = (src[ip + 1] | ((src[ip] & 0xE0) << 3)) + 17
                length = (src[ip] & 0x1F) + 3
            ip += 2
            for i in range(length):
                out[op + i] = out[op + i - dist]
            op += length
            f2 >>= 1
        else:
            out[op] = src[ip]
            op += 1
            ip += 1
        f1 >>= 1
    return bytes(out), op


def compress_literal(data):
    """Fluxo JDLZ valido so com literais (sem busca de repeticoes): simples e seguro."""
    body = bytearray()
    body += b"\x00\x00"  # f1 (8 literais) e f2 (nunca usado)
    n = 0
    for b in data:
        if n == 8:
            body += b"\x00"
            n = 0
        body.append(b)
        n += 1
    hdr = b"JDLZ" + bytes([0x02, 0x10, 0, 0]) + struct.pack("<II", len(data), 16 + len(body))
    return hdr + bytes(body)
