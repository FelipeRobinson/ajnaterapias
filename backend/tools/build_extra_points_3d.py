# FERRAMENTA DE MANUTENÇÃO (não roda no site). Requer numpy.
# Uso: .venv\Scripts\python backend\tools\build_extra_points_3d.py
"""Posições 3D dos 48 pontos extras da OMS (EX-HN, EX-CA, EX-B, EX-UE, EX-LE) nos dois corpos.

Cada ponto extra tem uma posição no mapa 2D. A posição 3D é a média ponderada dos pontos clássicos
mais próximos no 2D (mesma vista: frente ou costas), que já têm posição 3D. Pontos da linha média
(x = 150 no 2D) ficam com x = 0 no 3D e um ponto só; os demais ganham o espelho do outro lado.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("acu", ROOT / "backend" / "app" / "acupoints_data.py")
acu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acu)
K = 4


def main():
    classic = acu.all_points()
    for folder in ("anatomy", "anatomy-f"):
        path = ROOT / "frontend" / "models" / folder / "acupoints3d.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for ex in acu.extra_points():
            same = [p for p in classic if p["view"] == ex["view"] and p["code"] in data]
            xy = np.array([[p["x"], p["y"]] for p in same])
            d = np.linalg.norm(xy - [ex["x"], ex["y"]], axis=1)
            near = np.argsort(d)[:K]
            w = 1 / (d[near] + 1.0) ** 2
            v = np.array([data[same[i]["code"]][0] for i in near])
            pos = (v * w[:, None]).sum(0) / w.sum()
            pos[3:] /= np.linalg.norm(pos[3:]) or 1
            if ex["x"] >= 149.5:  # linha média
                pos[0] = 0.0
                pos[3] = 0.0
                pos[3:] /= np.linalg.norm(pos[3:]) or 1
                data[ex["code"]] = [[round(float(x), 4) for x in pos]]
            else:
                first = [round(float(x), 4) for x in pos]
                data[ex["code"]] = [first, [-first[0], first[1], first[2], -first[3], first[4], first[5]]]
        path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        print(folder, len(data), "pontos com posição 3D")


if __name__ == "__main__":
    main()
