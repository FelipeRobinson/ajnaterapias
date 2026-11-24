# FERRAMENTA DE MANUTENÇÃO (não roda no site). Regera frontend/models/anatomy-f/.
# Passos: baixar 3d-vh-f-united.glb (HuBMAP, CC BY 4.0) para esta pasta como female.glb,
# rodar extract_female.py e depois: python build_female.py <raiz do projeto>  (requer numpy e fast-simplification)
"""Extrai pele e ossos do modelo feminino (HuBMAP VH female v1.5, CC BY 4.0) em coordenadas do mundo."""
import json, struct
from pathlib import Path
import numpy as np

D = Path(__file__).parent
data = (D / "female.glb").read_bytes()
jlen = struct.unpack_from("<I", data, 12)[0]
g = json.loads(data[20:20 + jlen])
bin_off = 20 + jlen + 8
BIN = memoryview(data)[bin_off:]
CT = {5126: (np.float32, 4), 5125: (np.uint32, 4), 5123: (np.uint16, 2), 5121: (np.uint8, 1)}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def accessor(i):
    a = g["accessors"][i]
    bv = g["bufferViews"][a["bufferView"]]
    dt, size = CT[a["componentType"]]
    n = NC[a["type"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride", 0)
    if stride and stride != size * n:
        raw = np.frombuffer(BIN, np.uint8, stride * a["count"], start).reshape(a["count"], stride)
        arr = raw[:, :size * n].copy().view(dt).reshape(a["count"], n)
    else:
        arr = np.frombuffer(BIN, dt, a["count"] * n, start).reshape(a["count"], n)
    return arr.astype(np.float64) if dt == np.float32 else arr.astype(np.int64)


def local(nd):
    if "matrix" in nd:
        return np.array(nd["matrix"]).reshape(4, 4).T
    t = np.array(nd.get("translation", [0, 0, 0]))
    q = nd.get("rotation", [0, 0, 0, 1]); x, y, z, w = q
    r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    s = np.array(nd.get("scale", [1, 1, 1]))
    m = np.eye(4); m[:3, :3] = r * s; m[:3, 3] = t
    return m


world = {}
def walk(i, parent):
    m = parent @ local(g["nodes"][i]); world[i] = m
    for c in g["nodes"][i].get("children", []):
        walk(c, m)
for r in g["scenes"][g.get("scene", 0)]["nodes"]:
    walk(r, np.eye(4))


def mesh_world(name_filter):
    out = []
    for i, nd in enumerate(g["nodes"]):
        if nd.get("mesh") is None:
            continue
        mesh = g["meshes"][nd["mesh"]]
        if not name_filter(mesh["name"]):
            continue
        for pr in mesh["primitives"]:
            v = accessor(pr["attributes"]["POSITION"])
            f = accessor(pr["indices"]).reshape(-1, 3) if "indices" in pr else np.arange(len(v)).reshape(-1, 3)
            m = world[i]
            vw = (np.c_[v, np.ones(len(v))] @ m.T)[:, :3]
            out.append((mesh["name"], vw, f))
    return out


BONES = ["vertebra", "femur", "fibula", "tibia", "ilium", "ischium", "pubis", "patella", "sacrum", "coccyx", "rib", "sternum"]
skin = mesh_world(lambda n: n == "VH_F_skin")
bones = mesh_world(lambda n: n.startswith("VH_F_") and any(k in n.lower() for k in BONES) and "ligament" not in n.lower())
V = np.concatenate([v for _, v, _ in skin])
print("skin verts", len(V), "bounds", V.min(0).round(3), V.max(0).round(3))
np.savez_compressed(D / "female_raw.npz",
                    skin_v=V, skin_f=np.concatenate([f for _, _, f in skin]),
                    bone_names=np.array([n for n, _, _ in bones]),
                    **{f"bv{i}": v for i, (_, v, _) in enumerate(bones)},
                    **{f"bf{i}": f for i, (_, _, f) in enumerate(bones)})
print("ossos", len(bones), "peças:", sorted(set(n.replace("_L", "").replace("_R", "") for n, _, _ in bones))[:40])