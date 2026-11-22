"""Tenta nomear hashes de marcadores do NFSU2 com bStringHash (h = h*33 + c, inicio 0xFFFFFFFF)."""
import itertools
import json
import sys


def bhash(s):
    h = 0xFFFFFFFF
    for c in s.encode():
        h = (h * 33 + c) & 0xFFFFFFFF
    return h


words_side = ["FRONT_LEFT", "FRONT_RIGHT", "REAR_LEFT", "REAR_RIGHT", "LEFT", "RIGHT", "FRONT", "REAR", "CENTER", ""]
words_obj = ["WHEEL", "TIRE", "BRAKE", "EXHAUST", "EXHAUST_TIP", "SPOILER", "ROOF", "ROOF_SCOOP", "MIRROR", "SIDE_MIRROR",
             "HEADLIGHT", "BRAKELIGHT", "TAILLIGHT", "LICENSE_PLATE", "PLATE", "ENGINE", "DRIVER", "STEERING_WHEEL",
             "NOS", "NEON", "TRUNK", "AUDIO", "HOOD", "DOOR", "BUMPER", "SKIRT", "SMOKE", "FLAME", "BACKFIRE",
             "HUD", "CAMERA", "DAMAGE", "LIGHT", "POSITION", "MARKER", "SPOILER_MOUNT", "ROOF_MOUNT", "WINDOW",
             "INTERIOR", "SEAT", "DASH", "SHIFTER", "COPLIGHT", "COPLIGHTS", "ANTENNA", "MUFFLER", "CV", "AXLE",
             "HEADLIGHT_FLARE", "BRAKELIGHT_FLARE", "REVERSE", "REVERSELIGHT", "SIGNAL", "UNDERGLOW",
             "LICENSE", "DECAL", "VINYL", "SPOILER_POSITION", "ROOF_POSITION", "EXHAUST_POSITION"]
cands = set()
for a in words_side:
    for b in words_obj:
        for sep in ("_",):
            for name in (f"{a}{sep}{b}" if a else b, f"{b}{sep}{a}" if a else b):
                cands.add(name)
                for i in range(0, 5):
                    cands.add(f"{name}{i}")
                    cands.add(f"{name}_{i}")
                    cands.add(f"{name}{i:02d}")
                    cands.add(f"{name}_{i:02d}")
for extra in sys.argv[2:]:
    cands.add(extra)
table = {f"{bhash(c):08X}": c for c in cands}
table.update({f"{bhash(c.lower()):08X}": c.lower() for c in cands})

objs = json.load(open(sys.argv[1]))
seen = {}
for o in objs:
    for m in o.get("markers", []):
        seen.setdefault(m["hash"], []).append((o["name"], m["pos"]))
for h, uses in sorted(seen.items(), key=lambda kv: kv[1][0][0]):
    names = sorted({u[0].rsplit("_", 1)[0] for u in uses})
    print(f"{h} -> {table.get(h, '?'):26} pos={uses[0][1]}  em {len(uses)} objs ex: {names[:3]}")
