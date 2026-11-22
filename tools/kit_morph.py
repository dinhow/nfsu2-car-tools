"""Adapta pecas de kit do B15 ao formato do B16 por deformacao suave.

Campo = mapeamento afim (caixa do B15 -> caixa do B16)  +  residuo suave (thin-plate spline com suavizacao)
O residuo puxa a peca de serie do B15 ate a superficie do B16 (amostrada densamente nos triangulos);
aplicado aos kits, eles "vestem" o B16 mantendo labios, entradas de ar etc.
"""
import numpy as np
from scipy.interpolate import RBFInterpolator
from scipy.spatial import cKDTree


def sample_triangles(tris, per_m2=40000, seed=0):
    """tris: array (n,3,3). Amostra pontos uniformes na superficie."""
    rng = np.random.default_rng(seed)
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    n = np.maximum(1, (area * per_m2).astype(int))
    idx = np.repeat(np.arange(len(tris)), n)
    r1, r2 = rng.random(len(idx)), rng.random(len(idx))
    s = np.sqrt(r1)
    pts = (1 - s)[:, None] * a[idx] + (s * (1 - r2))[:, None] * b[idx] + (s * r2)[:, None] * c[idx]
    return np.vstack([pts, tris.reshape(-1, 3)])


class Morph:
    def __init__(self, src_pts, dst_tris, smoothing=0.02, max_samples=600, seed=0, affine=None, src_mask=None):
        """affine: (escala[3], deslocamento[3]) proprios em vez do mapeamento de caixa a caixa.
        src_mask: funcao(pontos)->bool escolhendo quais pontos da peca de serie puxam o residuo."""
        src = np.unique(np.asarray(src_pts, float).round(5), axis=0)
        dst = sample_triangles(np.asarray(dst_tris, float))
        self.smin, self.smax = src.min(0), src.max(0)
        self.dmin, self.dmax = dst.min(0), dst.max(0)
        self.scale = (self.dmax - self.dmin) / np.maximum(self.smax - self.smin, 1e-6)
        if affine is not None:
            sc, of = np.asarray(affine[0], float), np.asarray(affine[1], float)
            self.scale, self.smin, self.dmin = sc, np.zeros(3), of
        if src_mask is not None:
            src = src[src_mask(src)]
        self.tree = cKDTree(dst)
        if len(src) > max_samples:
            rng = np.random.default_rng(seed)
            src = src[rng.choice(len(src), max_samples, replace=False)]
        aff = self.affine(src)
        _, idx = self.tree.query(aff)
        resid = dst[idx] - aff
        self.rbf = RBFInterpolator(aff, resid, kernel="thin_plate_spline", smoothing=smoothing)

    def affine(self, p):
        return self.dmin + (np.asarray(p, float) - self.smin) * self.scale

    def apply(self, pts):
        a = self.affine(pts)
        return a + self.rbf(a)

    def apply_normals(self, pts, nrm, h=1e-3):
        p = np.asarray(pts, float)
        base = self.apply(p)
        J = np.empty((len(p), 3, 3))
        for k in range(3):
            dp = p.copy()
            dp[:, k] += h
            J[:, :, k] = (self.apply(dp) - base) / h
        out = np.einsum("nij,nj->ni", np.linalg.inv(J).transpose(0, 2, 1), np.asarray(nrm, float))
        return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)

    def fit_error(self, src_full):
        d, _ = self.tree.query(self.apply(src_full))
        return float(np.mean(d)), float(np.percentile(d, 95)), float(d.max())
