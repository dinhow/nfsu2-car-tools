"""Tabela de grupos de material das pecas KIT00/BASE do carro original."""
import collections
import json
import sys

sys.path.insert(0, __file__.rsplit("\\", 2)[0])
from nfsu2_geom import Geometry, bhash  # noqa: E402
import tpk  # noqa: E402

game = sys.argv[1]
g = Geometry(game + r"\CARS\SENTRA\GEOMETRY.BIN")
names = {}
for path in (game + r"\CARS\SENTRA\TEXTURES.BIN", game + r"\CARS\TEXTURES.BIN"):
    for h, t in tpk.load(path).items():
        names[h] = t.name or f"<{'SENTRA' if 'SENTRA' in path else 'CARS'}:{h:08X}>"

# nomes provaveis de shaders (light materials) para tentar identificar os hashes
shader_guess = ["CARSKIN", "CARSKIN2", "CHROME", "WINDOW", "WINDOW_FRONT", "WINDOW_REAR", "GLASS", "DULLPLASTIC",
                "PLASTIC", "RUBBER", "TIRE", "RIM", "BADGING", "HEADLIGHT", "BRAKELIGHT", "DECAL", "INTERIOR",
                "ENGINE", "METAL", "CALIPER", "BRAKEDISC", "SHADOW", "BLACK", "CARBONFIBRE", "CARBON", "MAGSILVER",
                "MAGCHROME", "MAGGUNMETAL", "WHEEL", "SPINNER", "CAR", "CAR_SKIN", "PAINT", "BODY", "DEFAULT",
                "SPOILER", "NEON", "LIGHTGLASS", "HEADLIGHTGLASS", "HEADLIGHT_GLASS", "GRILL", "GRILLE",
                "UNDERCARRIAGE", "LICENSE", "LICENSEPLATE", "DRIVER", "CARLIGHTS", "REFLECTIVE"]
sh_names = {bhash(s): s for s in shader_guess}

rows = []
usage = collections.Counter()
for o in g.objects:
    if not (o.name.startswith("SENTRA_KIT00_") or o.name.startswith("SENTRA_BASE")) or not o.name.endswith("_A") and "KIT00" in o.name and not o.name[-2:] in ("_A",):
        pass
    if not o.name.endswith("_A") and not o.name.endswith(("_LEF", "_RIG", "_LEFT", "_RIGH", "MIRR", "_MIR", "_UN")):
        continue
    if not (o.name.startswith("SENTRA_KIT00_") or o.name.startswith("SENTRA_BASE")):
        continue
    for k, gr in enumerate(o.groups):
        tex = names.get(o.textures[gr.f[0]], f"?{o.textures[gr.f[0]]:08X}") if gr.f[0] < len(o.textures) else "?"
        shh = o.shaders[gr.f[1]] if gr.f[1] < len(o.shaders) else None
        sh = sh_names.get(shh, f"{shh:08X}" if shh is not None else "?")
        rows.append((o.name, k, gr.count // 3, tex, sh, gr.f, hex(gr.flags)))
        usage[(tex, sh)] += gr.count // 3

for r in rows:
    print(f"{r[0][:30]:30} g{r[1]:<2} tris={r[2]:5} tex={r[3]:30} shader={r[4]:12} f={r[5]} flags={r[6]}")
print("\nCOMBINACOES (textura, shader) por triangulos:")
for (t, s), n in usage.most_common():
    print(f"  {n:6}  {t:32} {s}")
json.dump([list(map(str, r)) for r in rows], open("export/stock_material_table.json", "w"), indent=0)
