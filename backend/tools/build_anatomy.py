# FERRAMENTA DE MANUTENÇÃO (não roda no site). Regera frontend/models/anatomy/.
# Requer: pip install numpy fast-simplification  (num ambiente separado)
# Entrada: atlas.json + body-*.bin.gz do projeto Human Atlas
#   (https://github.com/ashemag/human-atlas/tree/main/public/models) na mesma pasta deste script.
# Uso: python build_anatomy.py <raiz do projeto>
"""Gera as camadas 3D leves (pele, músculos, ossos) e a posição 3D dos pontos de acupuntura.

Fonte: BodyParts3D 4.0 (CC BY 4.0), via pacote simplificado do projeto Human Atlas.
Saída: frontend/models/anatomy/{skin,muscles,bones}.bin + anatomy.json + acupoints3d.json
"""
import gzip, json, sys
from pathlib import Path

import fast_simplification
import numpy as np

D = Path(__file__).parent
ROOT = Path(sys.argv[1])
OUT = ROOT / "frontend" / "models" / "anatomy"
OUT.mkdir(parents=True, exist_ok=True)
import importlib.util  # carrega só o arquivo de dados, sem iniciar o Flask
_spec = importlib.util.spec_from_file_location("acupoints_data", ROOT / "backend" / "app" / "acupoints_data.py")
_mod = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_mod)
all_points, MERIDIANS = _mod.all_points, _mod.MERIDIANS

atlas = json.loads((D / "atlas.json").read_text())
chunks = [gzip.decompress((D / "models" / f"body-{i}.bin.gz").read_bytes()) for i in range(len(atlas["chunks"]))]


def load(p):
    buf = chunks[p["chunk"]]
    v = np.frombuffer(buf, np.float32, p["vertexCount"] * 3, p["positions"]).reshape(-1, 3).astype(np.float64)
    n = np.frombuffer(buf, np.int16, p["vertexCount"] * 3, p["normals"]).reshape(-1, 3).astype(np.float64) / 32767
    i = np.frombuffer(buf, np.uint32, p["indexCount"], p["indices"]).reshape(-1, 3).astype(np.int64)
    return v, n, i


# ---------------------------------------------------------------- camadas
LAYERS = {
    "skin": {"systems": {"integumentary"}, "extra": {"External ear"}, "reduction": 0.0, "label": "Pele"},
    "muscles": {"systems": {"muscular"}, "reduction": 0.72, "label": "Músculos"},
    "bones": {"systems": {"skeletal"}, "reduction": 0.62, "label": "Ossos"},
}
bmin = np.array([1e9] * 3); bmax = -bmin
for p in atlas["parts"]:
    b = np.array(p["bounds"]); bmin = np.minimum(bmin, b[0]); bmax = np.maximum(bmax, b[1])
span = bmax - bmin

manifest = {"source": "BodyParts3D 4.0 © The Database Center for Life Science, CC BY 4.0 (adaptado)",
            "bounds": [bmin.tolist(), bmax.tolist()], "layers": {}}
for key, cfg in LAYERS.items():
    verts, idx, parts = [], [], []
    vcount = icount = 0
    for p in atlas["parts"]:
        if p["system"] not in cfg["systems"] and p["name"] not in cfg.get("extra", ()):
            continue
        v, _, f = load(p)
        tris = len(f)
        if cfg["reduction"] and tris > 120:
            target = cfg["reduction"] if tris > 800 else cfg["reduction"] * 0.6
            try:
                v, f = fast_simplification.simplify(v.astype(np.float32), f.astype(np.int32), target_reduction=target)
                v = v.astype(np.float64); f = f.astype(np.int64)
            except Exception as e:  # mantém a peça original se não der para simplificar
                print("aviso", p["name"], e)
        if not len(f):
            continue
        parts.append({"name": p["name"], "start": icount, "count": len(f) * 3})
        verts.append(v); idx.append(f + vcount)
        vcount += len(v); icount += len(f) * 3
    V = np.concatenate(verts); I = np.concatenate(idx).astype(np.uint32)
    q = np.round((V - bmin) / span * 65535).clip(0, 65535).astype(np.uint16)
    vbytes = q.tobytes()
    vbytes += b"\0" * (-len(vbytes) % 4)  # índices (Uint32) precisam começar em múltiplo de 4 bytes
    data = vbytes + I.tobytes()
    (OUT / f"{key}.bin").write_bytes(data)
    manifest["layers"][key] = {"label": cfg["label"], "file": f"{key}.bin", "vertexCount": int(vcount),
                               "indexCount": int(icount), "indexOffset": int(len(vbytes)), "parts": parts}
    print(f"{key}: {len(parts)} peças, {icount // 3} triângulos, {len(data) / 1e6:.2f} MB")
(OUT / "anatomy.json").write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

# ---------------------------------------------------------------- pontos 2D -> 3D
SV_list, SN_list = [], []
for nm in ("Skin", "External ear"):
    v_, n_, _ = load(next(p for p in atlas["parts"] if p["name"] == nm))
    SV_list.append(v_); SN_list.append(n_)
SV, SN = np.concatenate(SV_list), np.concatenate(SN_list)
ymin, ymax = SV[:, 1].min(), SV[:, 1].max()
S = (ymax - ymin) / (707 - 22)   # metros por unidade do desenho 2D


def Y3(y):
    return ymax - (y - 22) * S


def clusters(Y, tol=0.008, gap=0.012):
    """Intervalos de X ocupados pela pele numa altura (cabeça, tronco, braços, pernas)."""
    xs = np.sort(SV[np.abs(SV[:, 1] - Y) < tol, 0])
    if not len(xs):
        return []
    out, start = [], xs[0]
    for a, b in zip(xs[:-1], xs[1:]):
        if b - a > gap:
            out.append((start, a)); start = b
    out.append((start, xs[-1]))
    return out


def interp(table, y):
    ys = [t[0] for t in table]; vs = [t[1] for t in table]
    return float(np.interp(y, ys, vs))


# Desenho 2D (lado esquerdo da tela): bordas de cada segmento
ARM_OUT = [(128, 100), (142, 93), (175, 87), (215, 82), (250, 72), (295, 64), (345, 60), (362, 53), (384, 49), (402, 52), (414, 60)]
ARM_IN = [(128, 112), (172, 104), (210, 99), (255, 93), (300, 85), (352, 79), (376, 78), (401, 76), (414, 69)]
TORSO = [(103, 141), (116, 139), (122, 120), (128, 103), (172, 104), (200, 103), (232, 105), (258, 106), (296, 102), (336, 97), (360, 100)]
LEG_OUT = [(345, 99), (380, 96), (440, 99), (505, 103), (560, 100), (620, 107), (652, 108), (680, 101), (707, 104)]
LEG_IN = [(345, 150), (372, 148), (440, 147), (505, 145), (552, 142), (600, 139), (655, 134), (682, 134), (707, 131)]


def head_half(y):
    t = (y - 62) / 41
    return 32 * np.sqrt(max(0.05, 1 - t * t))


# Braço 3D: centro e meia-largura por altura (lado direito do paciente = X negativo)
ARM_Y_TOP, ARM_Y_TIP = 1.40, None
def arm3d(Y):
    c = [k for k in clusters(Y) if k[1] < -0.05]  # do lado direito
    if not c:
        return None
    a = min(c, key=lambda k: k[0])  # o mais externo = braço
    return (a[0] + a[1]) / 2, (a[1] - a[0]) / 2


# ponta dos dedos do braço 3D
ys = np.linspace(1.40, 0.55, 300)
tip = next((Y for Y in ys if arm3d(Y) is None or (arm3d(Y)[0] > -0.12)), 0.68)
for Y in ys:
    c = [k for k in clusters(Y) if k[1] < -0.05]
    if len(c) >= 2 or (c and min(k[0] for k in c) < -0.2):
        lowest_arm = Y
ARM_Y_TIP = lowest_arm
print("braço 3D de", ARM_Y_TOP, "até", round(ARM_Y_TIP, 3))

ARM_PTS = {("LU", None), ("LI", range(1, 16)), ("HT", None), ("SI", range(1, 10)), ("PC", range(2, 10)), ("SJ", range(1, 14))}


def is_arm(code_m, n, x, y):
    for m, rng in ARM_PTS:
        if m == code_m and (rng is None or n in rng):
            return 120 < y < 420 and x < 112
    return False


def place(x, y, view, arm):
    """Posição 3D (x, y, z, nx, ny, nz) para um ponto do lado ESQUERDO DA TELA."""
    front = view == "front"
    sign = -1 if front else 1          # lado esquerdo da tela = direito do paciente (frente) / esquerdo (costas)
    if arm:
        # articulações: 2D (y) -> 3D (Y, centro |X|, meia-largura)
        J2 = [128, 250, 350, 414]
        Yv = float(np.interp(y, J2, [1.40, 1.107, 0.88, 0.726]))
        cX = float(np.interp(y, J2, [0.19, 0.228, 0.262, 0.285]))
        hX = float(np.interp(y, J2, [0.05, 0.034, 0.027, 0.03]))
        o, i = interp(ARM_OUT, y), interp(ARM_IN, y)
        u = ((o + i) / 2 - x) / max(1, (i - o) / 2)       # +1 = borda externa
        X = sign * (cX + u * hX)
    elif y >= 345:
        o, i = interp(LEG_OUT, y), interp(LEG_IN, y)
        u = ((o + i) / 2 - x) / max(1, (i - o) / 2)
        Yv = Y3(y)
        legs = [k for k in clusters(Yv) if k[1] < 0.02 and k[0] > -0.2] or [(-0.15, -0.01)]
        c0, c1 = max(legs, key=lambda k: k[1] - k[0])
        X = sign * (abs((c0 + c1) / 2) + u * (c1 - c0) / 2)
    else:
        Yv = Y3(y)
        half2d = head_half(y) if y < 103 else 150 - interp(TORSO, y)
        body = [k for k in clusters(Yv) if k[0] < 0.005 < k[1]]
        h3 = max(abs(body[0][0]), body[0][1]) if body else half2d * S
        X = sign * (150 - x) / half2d * h3 * -1 * -1
        X = sign * abs(150 - x) / half2d * h3
    # ponto da pele mais próximo, do lado visível (frente: maior z; costas: menor z)
    d2 = (SV[:, 0] - X) ** 2 + (SV[:, 1] - Yv) ** 2
    facing = (SN[:, 2] > 0.05 if front else SN[:, 2] < -0.05) if not arm else (SN[:, 2] > -0.4 if front else SN[:, 2] < 0.4)
    near = np.where((d2 < (0.016 if arm else 0.012) ** 2) & facing)[0]
    if not len(near):
        near = np.where(facing)[0]
        near = near[np.argsort(d2[near])[:6]]
    k = near[np.argmax(SV[near, 2])] if front else near[np.argmin(SV[near, 2])]
    pos, nrm = SV[k], SN[k] / (np.linalg.norm(SN[k]) or 1)
    return [round(float(v), 4) for v in (*pos, *nrm)]


bilateral = {_mod.PT_TO_CN[m[0]]: m[5] for m in MERIDIANS}
points3d = {}
for pt in all_points():
    m, n, x, y, view = pt["meridian"], pt["number"], pt["x"], pt["y"], pt["view"]
    arm = is_arm(m, n, x, y)
    first = place(x, y, view, arm)
    if bilateral[m]:
        mirror = [-first[0], first[1], first[2], -first[3], first[4], first[5]]
        points3d[pt["code"]] = [first, mirror]
    else:
        points3d[pt["code"]] = [first]
(OUT / "acupoints3d.json").write_text(json.dumps(points3d, separators=(",", ":")), encoding="utf-8")
print("pontos 3D:", len(points3d))
(OUT / "ATRIBUICAO.md").write_text(
    "# Modelo anatômico 3D\n\nBodyParts3D 4.0, © The Database Center for Life Science, licenciado sob "
    "[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).\n\n"
    "- Fonte: https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html\n"
    "- Pacote simplificado de origem: projeto Human Atlas (https://github.com/ashemag/human-atlas), código MIT.\n"
    "- Adaptações para a Ajna: seleção das camadas pele, músculos e ossos; simplificação adicional das malhas "
    "(fast-simplification); posições quantizadas em 16 bits.\n"
    "- As posições 3D dos pontos de acupuntura são aproximações geradas a partir do mapa 2D da clínica "
    "e não fazem parte do BodyParts3D.\n", encoding="utf-8")

