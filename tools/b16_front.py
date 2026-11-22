"""Variantes de para-choque dianteiro baseadas no para-choque REAL do B16 + acessorios que seguem o contorno:
labio fino, splitter, labio na cor do carro, aletas, placas laterais; grade original ou escurecida.

python b16_front.py <mesh_dump.json> <saida.json>
"""
import json
import math
import sys

import numpy as np
from scipy.ndimage import uniform_filter1d

dump = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
CX = 1.75  # centro de referencia para medir o contorno em angulo

VARIANTS = {
    "KIT01": dict(ext=0.030, dep=0.022, center=0.00, mat="lb_black", grille=False),
    "KIT02": dict(ext=0.055, dep=0.030, center=0.035, mat="lb_black", grille=False),
    "KIT03": dict(ext=0.030, dep=0.022, center=0.00, mat="lb_black", grille=True),
    "KIT04": dict(ext=0.055, dep=0.030, center=0.035, mat="lb_black", grille=True),
    "KIT05": dict(ext=0.040, dep=0.030, center=0.010, mat="lb_paint", grille=False),
    "KIT06": dict(ext=0.055, dep=0.030, center=0.035, mat="lb_black", grille=True, fins=True),
    "KIT07": dict(ext=0.040, dep=0.030, center=0.010, mat="lb_paint", grille=True),
    "KIT08": dict(ext=0.090, dep=0.025, center=0.020, mat="lb_black", grille=True, plates=True),
}
STEP = {"A": 3, "B": 6, "C": 12}


def contour(lod):
    P = np.array([c[:3] for _, cs in dump[f"SENTRA_KIT00_FRONT_BUMPER_{lod}"]["tris"] for c in cs])
    rel = P[:, :2] - [CX, 0]
    ang = np.degrees(np.arctan2(rel[:, 1], rel[:, 0]))
    out = []
    for phi in np.arange(-78, 78.1, 1.5):
        m = np.abs(ang - phi) < 2.5
        if m.sum() == 0:
            continue
        q = P[m]
        zb = q[:, 2].min()
        low = q[q[:, 2] < zb + 0.04]
        r = np.hypot(low[:, 0] - CX, low[:, 1]).max()
        t = math.radians(phi)
        out.append((phi, CX + r * math.cos(t), r * math.sin(t), zb))
    c = np.array(out)
    # curva limpa e simetrica: polinomio do raio e da altura em funcao do angulo, espelhando os dois lados
    phi = c[:, 0]
    r = np.hypot(c[:, 1] - CX, c[:, 2])
    zb = c[:, 3]
    P2 = np.concatenate([phi, -phi])
    rf = np.polyval(np.polyfit(P2, np.concatenate([r, r]), 6), phi)
    # altura: usa o ponto mais baixo de cada faixa, mas sem as reentrancias (envelope inferior suavizado)
    zlow = uniform_filter1d(np.minimum.accumulate(zb[::-1])[::-1] * 0 + zb, 9, mode="nearest")
    zf = np.polyval(np.polyfit(P2, np.concatenate([zlow, zlow]), 4), phi)
    t = np.radians(phi)
    return np.stack([phi, CX + rf * np.cos(t), rf * np.sin(t), zf], 1)


class Mesh:
    def __init__(self):
        self.tris = []

    def tri(self, mat, a, b, c, want):
        a, b, c = map(np.asarray, (a, b, c))
        n = np.cross(b - a, c - a)
        ln = np.linalg.norm(n)
        if ln < 1e-12:
            return
        n /= ln
        if np.dot(n, want) < 0:
            b, c, n = c, b, -n
        self.tris.append([mat, [list(map(float, p)) + list(map(float, n)) + [0.5, 0.5] for p in (a, b, c)]])

    def quad(self, mat, a, b, c, d, want):
        self.tri(mat, a, b, c, want)
        self.tri(mat, a, c, d, want)


def lip(M, C, v, step):
    sel = C[::max(1, int(round(step / 1.5)))]
    secs = []
    for phi, x, y, zb in sel:
        t = math.radians(phi)
        n = np.array([math.cos(t), math.sin(t), 0.0])  # normal para fora no plano
        ext = v["ext"] + v["center"] * math.cos(t) ** 6
        dep = v["dep"]
        base = np.array([x, y, zb])
        secs.append([base + n * -0.06 + [0, 0, 0.004], base + [0, 0, 0.002], base + n * ext + [0, 0, -dep * 0.45],
                     base + n * ext + [0, 0, -dep], base + n * -0.10 + [0, 0, -dep * 0.75]])
    G = np.array(secs)
    wants = [np.array([0, 0, 1.0]), np.array([0, 0, 1.0]), None, np.array([0, 0, -1.0])]
    for i in range(len(G) - 1):
        for j in range(4):
            if j == 2:  # borda frontal: normal para fora
                t = math.radians(sel[i][0])
                w = np.array([math.cos(t), math.sin(t), 0])
            else:
                w = wants[j]
            M.quad(v["mat"], G[i, j], G[i + 1, j], G[i + 1, j + 1], G[i, j + 1], w)
    for k, s in ((0, -1), (len(G) - 1, 1)):  # tampas nas pontas
        p = G[k]
        for j in range(1, 4):
            M.tri(v["mat"], p[0], p[j], p[j + 1], np.array([0, s, 0]))
    return sel


def fins(M, sel, v):
    for side in (1, -1):
        phi = 62 * side
        row = min(sel, key=lambda r: abs(r[0] - phi))
        _, x, y, zb = row
        t = math.radians(phi)
        n = np.array([math.cos(t), math.sin(t), 0])
        tang = np.array([-math.sin(t), math.cos(t), 0])
        base = np.array([x, y, zb]) + n * 0.01
        p = [base, base + n * (v["ext"] + 0.01) - [0, 0, v["dep"]], base + n * 0.0 + [0, 0, 0.11], base - n * 0.02 + [0, 0, 0.10]]
        M.quad("lb_black", p[0], p[1], p[2], p[3], tang)
        M.quad("lb_black", p[0], p[1], p[2], p[3], -tang)


def plates(M, sel, v):
    for side in (1, -1):
        row = min(sel, key=lambda r: abs(r[0] - 70 * side))
        _, x, y, zb = row
        a = [x + v["ext"], y + 0.01 * side, zb - v["dep"]]
        p = [a, [x - 0.30, y, zb - v["dep"]], [x - 0.30, y, zb + 0.08], [x + 0.02, y, zb + 0.06]]
        M.quad("lb_black", *p, np.array([0, side, 0]))
        M.quad("lb_black", *p, np.array([0, -side, 0]))


res = {}
for name, v in VARIANTS.items():
    res[name] = {}
    for lod, step in STEP.items():
        C = contour(lod)
        M = Mesh()
        sel = lip(M, C, v, step)
        if v.get("fins"):
            fins(M, sel, v)
        if v.get("plates"):
            plates(M, sel, v)
        res[name][lod] = {"tris": M.tris, "black_grille": v["grille"]}
    print(name, {lod: len(res[name][lod]["tris"]) for lod in STEP})
json.dump(res, open(OUT, "w"))
