# FERRAMENTA DE MANUTENÇÃO (não roda no site). Regera frontend/models/anatomy-f/.
# Passos: baixar 3d-vh-f-united.glb (HuBMAP, CC BY 4.0) para esta pasta como female.glb,
# rodar extract_female.py e depois: python build_female.py <raiz do projeto>  (requer numpy e fast-simplification)
"""Gera o corpo FEMININO para o mapa 3D: frontend/models/anatomy-f/
Fonte: HuBMAP Human Reference Atlas, 3D Reference Organ Set for Female v1.5 (Kristen Browne & Heidi Schlehlein),
CC BY 4.0 — https://doi.org/10.48539/HBM352.BTSQ.586
"""
import json, sys, importlib.util
from pathlib import Path
import numpy as np
import fast_simplification

D = Path(__file__).parent
ROOT = Path(sys.argv[1])
OUT = ROOT / "frontend" / "models" / "anatomy-f"
OUT.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location("acu", ROOT / "backend" / "app" / "acupoints_data.py")
acu = importlib.util.module_from_spec(spec); spec.loader.exec_module(acu)

z = np.load(D / "female_raw.npz")
ymin = z["skin_v"][:, 1].min()
SHIFT = np.array([0.0, -ymin, 0.04])  # pés no chão (y=0), alinhada ao modelo masculino


def simplify(v, f, reduction):
    v2, f2 = fast_simplification.simplify(v.astype(np.float32), f.astype(np.int32), target_reduction=reduction)
    return v2.astype(np.float64), f2.astype(np.int64)


def vertex_normals(v, f):
    n = np.zeros_like(v)
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    for k in range(3):
        np.add.at(n, f[:, k], fn)
    return n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)


skin_v = z["skin_v"] + SHIFT
skin_f = z["skin_f"]
bones = []
for i, name in enumerate(z["bone_names"]):
    bones.append((str(name).replace("VH_F_", "").replace("_", " "), z[f"bv{i}"] + SHIFT, z[f"bf{i}"]))

allv = np.concatenate([skin_v] + [b[1] for b in bones])
bmin, bmax = allv.min(0) - 0.001, allv.max(0) + 0.001
span = bmax - bmin
manifest = {"source": "HuBMAP 3D Reference Organ Set for Female v1.5 (K. Browne & H. Schlehlein), CC BY 4.0 (adaptado)",
            "bounds": [bmin.tolist(), bmax.tolist()], "layers": {}}


def write_layer(key, label, parts):
    verts, idx, plist = [], [], []
    vcount = icount = 0
    for name, v, f in parts:
        plist.append({"name": name, "start": icount, "count": len(f) * 3})
        verts.append(v); idx.append(f + vcount)
        vcount += len(v); icount += len(f) * 3
    V = np.concatenate(verts); I = np.concatenate(idx).astype(np.uint32)
    q = np.round((V - bmin) / span * 65535).clip(0, 65535).astype(np.uint16)
    vb = q.tobytes(); vb += b"\0" * (-len(vb) % 4)
    (OUT / f"{key}.bin").write_bytes(vb + I.tobytes())
    manifest["layers"][key] = {"label": label, "file": f"{key}.bin", "vertexCount": int(vcount), "indexCount": int(icount),
                               "indexOffset": len(vb), "parts": plist}
    print(f"{key}: {len(plist)} peças, {icount // 3} triângulos, {(len(vb) + I.nbytes) / 1e6:.2f} MB")


sv, sf = simplify(skin_v, skin_f, 0.80)
write_layer("skin", "Pele", [("Skin", sv, sf)])
bparts = []
for name, v, f in bones:
    if len(f) > 400:
        v, f = simplify(v, f, 0.85)
    if len(f):
        bparts.append((name, v, f))
write_layer("bones", "Ossos (parcial)", bparts)
(OUT / "anatomy.json").write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

# ---------------------------------------------------------------- pontos: 2D -> 3D (mesma lógica do masculino)
SV = skin_v
SN = vertex_normals(skin_v, skin_f)
ymax = SV[:, 1].max()
S = (ymax - 0) / (707 - 22)
Y3 = lambda y: ymax - (y - 22) * S


def clusters(Y, tol=0.006, gap=0.01):
    xs = np.sort(SV[np.abs(SV[:, 1] - Y) < tol, 0])
    if not len(xs):
        return []
    out, start = [], xs[0]
    for a, b in zip(xs[:-1], xs[1:]):
        if b - a > gap:
            out.append((start, a)); start = b
    out.append((start, xs[-1]))
    return out


interp = lambda t, y: float(np.interp(y, [a for a, _ in t], [b for _, b in t]))
ARM_OUT = [(128, 100), (142, 93), (175, 87), (215, 82), (250, 72), (295, 64), (345, 60), (362, 53), (384, 49), (402, 52), (414, 60)]
ARM_IN = [(128, 112), (172, 104), (210, 99), (255, 93), (300, 85), (352, 79), (376, 78), (401, 76), (414, 69)]
TORSO = [(103, 141), (116, 139), (122, 120), (128, 103), (172, 104), (200, 103), (232, 105), (258, 106), (296, 102), (336, 97), (360, 100)]
LEG_OUT = [(345, 99), (380, 96), (440, 99), (505, 103), (560, 100), (620, 107), (652, 108), (680, 101), (707, 104)]
LEG_IN = [(345, 150), (372, 148), (440, 147), (505, 145), (552, 142), (600, 139), (655, 134), (682, 134), (707, 131)]
head_half = lambda y: 32 * np.sqrt(max(0.05, 1 - ((y - 62) / 41) ** 2))
# braço da modelo feminina (medido no modelo): Y das articulações, centro |X| e meia-largura
J2 = [128, 250, 350, 414]
ARM_Y = [1.35, 1.078, 0.866, 0.725]
ARM_C = [0.19, 0.27, 0.41, 0.43]
ARM_H = [0.05, 0.04, 0.032, 0.035]
ARM_PTS = {("LU", None), ("LI", range(1, 16)), ("HT", None), ("SI", range(1, 10)), ("PC", range(2, 10)), ("SJ", range(1, 14))}


def is_arm(m, n, x, y):
    return any(mm == m and (r is None or n in r) for mm, r in ARM_PTS) and 120 < y < 420 and x < 112


def place(x, y, view, arm):
    front = view == "front"
    sign = -1 if front else 1
    if arm:
        Yv = float(np.interp(y, J2, ARM_Y)); cX = float(np.interp(y, J2, ARM_C)); hX = float(np.interp(y, J2, ARM_H))
        o, i = interp(ARM_OUT, y), interp(ARM_IN, y)
        u = ((o + i) / 2 - x) / max(1, (i - o) / 2)
        X = sign * (cX + u * hX)
    elif y >= 345:
        o, i = interp(LEG_OUT, y), interp(LEG_IN, y)
        u = ((o + i) / 2 - x) / max(1, (i - o) / 2)
        Yv = Y3(y)
        legs = [k for k in clusters(Yv) if k[1] < 0.02 and k[0] > -0.25] or [(-0.15, -0.01)]
        c0, c1 = max(legs, key=lambda k: k[1] - k[0])
        X = sign * (abs((c0 + c1) / 2) + u * (c1 - c0) / 2)
    else:
        Yv = Y3(y)
        half2d = head_half(y) if y < 103 else 150 - interp(TORSO, y)
        body = [k for k in clusters(Yv) if k[0] < 0.005 < k[1]]
        h3 = max(abs(body[0][0]), body[0][1]) if body else half2d * S
        X = sign * abs(150 - x) / half2d * h3
    d2 = (SV[:, 0] - X) ** 2 + (SV[:, 1] - Yv) ** 2
    facing = (SN[:, 2] > 0.05 if front else SN[:, 2] < -0.05) if not arm else (SN[:, 2] > -0.4 if front else SN[:, 2] < 0.4)
    near = np.where((d2 < (0.016 if arm else 0.012) ** 2) & facing)[0]
    if not len(near):
        near = np.where(facing)[0]
        near = near[np.argsort(d2[near])[:6]]
    k = near[np.argmax(SV[near, 2])] if front else near[np.argmin(SV[near, 2])]
    return [round(float(v), 4) for v in (*SV[k], *SN[k])]


bilateral = {acu.PT_TO_CN[m[0]]: m[5] for m in acu.MERIDIANS}
pts3d = {}
for pt in acu.all_points():
    first = place(pt["x"], pt["y"], pt["view"], is_arm(pt["meridian"], pt["number"], pt["x"], pt["y"]))
    pts3d[pt["code"]] = [first, [-first[0], first[1], first[2], -first[3], first[4], first[5]]] if bilateral[pt["meridian"]] else [first]
(OUT / "acupoints3d.json").write_text(json.dumps(pts3d, separators=(",", ":")), encoding="utf-8")
print("pontos 3D:", len(pts3d), "| IG4", pts3d["IG4"][0][:3], "| VB20", pts3d["VB20"][0][:3], "| E36", pts3d["E36"][0][:3])
(OUT / "ATRIBUICAO.md").write_text(
    "# Modelo anatômico 3D feminino\n\n"
    "Kristen Browne e Heidi Schlehlein, Human Reference Atlas / HuBMAP, *3D Reference Organ Set for Female v1.5* (2023), "
    "licenciado sob [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).\n\n"
    "- DOI: https://doi.org/10.48539/HBM352.BTSQ.586\n"
    "- Adaptações para a Ajna: uso da pele e dos ossos disponíveis (o modelo não tem músculos esqueléticos nem "
    "ossos dos braços e do crânio); malhas simplificadas; coordenadas reposicionadas; posições quantizadas em 16 bits.\n"
    "- As posições 3D dos pontos de acupuntura são aproximações geradas a partir do mapa 2D da clínica.\n",
    encoding="utf-8")

