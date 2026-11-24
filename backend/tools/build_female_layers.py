# FERRAMENTA DE MANUTENÇÃO (não roda no site). Requer numpy.
# Uso: .venv\Scripts\python backend\tools\build_female_layers.py
"""Leva os MÚSCULOS e o ESQUELETO COMPLETO do corpo masculino (BodyParts3D) para o corpo feminino (HuBMAP).

O modelo feminino gratuito não tem músculos e tem só parte do esqueleto. Aqui deformamos os músculos e
ossos do modelo masculino para caberem no corpo feminino usando os pontos de acupuntura como marcadores:
cada ponto existe nos dois corpos (frontend/models/*/acupoints3d.json), então sabemos para onde cada
região (braço, perna, cabeça…) precisa ir. A deformação é uma "thin-plate spline" (suave, sem rasgos).

Saída: frontend/models/anatomy-f/muscles.bin e bones.bin (+ entradas no anatomy.json, com bounds próprios).
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
M = ROOT / "frontend" / "models" / "anatomy"
F = ROOT / "frontend" / "models" / "anatomy-f"
SMOOTH = 2e-4  # suavização da deformação (marcadores imperfeitos não "puxam" a malha)


def read_layer(folder, manifest, key):
    info = manifest["layers"][key]
    buf = (folder / info["file"]).read_bytes()
    q = np.frombuffer(buf, dtype=np.uint16, count=info["vertexCount"] * 3).reshape(-1, 3).astype(np.float64)
    lo, hi = (np.array(b) for b in info.get("bounds", manifest["bounds"]))
    v = lo + q / 65535.0 * (hi - lo)
    idx = np.frombuffer(buf, dtype=np.uint32, count=info["indexCount"], offset=info["indexOffset"])
    return v, idx, info


def write_layer(folder, name, v, idx):
    lo, hi = v.min(axis=0) - 1e-4, v.max(axis=0) + 1e-4
    q = np.round((v - lo) / (hi - lo) * 65535).astype(np.uint16)
    head = q.tobytes()
    pad = (-len(head)) % 4
    (folder / name).write_bytes(head + b"\0" * pad + idx.astype(np.uint32).tobytes())
    return {"vertexCount": len(v), "indexCount": len(idx), "indexOffset": len(head) + pad,
            "bounds": [lo.tolist(), hi.tolist()]}


def landmarks():
    m = json.loads((M / "acupoints3d.json").read_text(encoding="utf-8"))
    f = json.loads((F / "acupoints3d.json").read_text(encoding="utf-8"))
    src, dst = [], []
    for code, sides in m.items():
        for a, b in zip(sides, f.get(code, [])):
            src.append(a[:3])
            dst.append(b[:3])
    return np.array(src), np.array(dst)


def fit_tps(src, dst):
    n = len(src)
    K = np.linalg.norm(src[:, None] - src[None], axis=2) + SMOOTH * np.eye(n)
    P = np.hstack([np.ones((n, 1)), src])
    A = np.zeros((n + 4, n + 4))
    A[:n, :n], A[:n, n:], A[n:, :n] = K, P, P.T
    sol = np.linalg.solve(A, np.vstack([dst, np.zeros((4, 3))]))
    return sol[:n], sol[n:]


def apply_tps(v, src, w, a, chunk=20000):
    out = np.empty_like(v)
    for i in range(0, len(v), chunk):
        part = v[i:i + chunk]
        out[i:i + chunk] = np.linalg.norm(part[:, None] - src[None], axis=2) @ w + a[0] + part @ a[1:]
    return out


def main():
    mman = json.loads((M / "anatomy.json").read_text(encoding="utf-8"))
    fman = json.loads((F / "anatomy.json").read_text(encoding="utf-8"))
    src, dst = landmarks()
    w, a = fit_tps(src, dst)
    err = np.linalg.norm(apply_tps(src, src, w, a) - dst, axis=1)
    print(f"{len(src)} marcadores · erro médio {err.mean() * 1000:.1f} mm · máx {err.max() * 1000:.1f} mm")
    for key, label in (("muscles", "Músculos"), ("bones", "Ossos")):
        v, idx, info = read_layer(M, mman, key)
        out = write_layer(F, f"{key}.bin", apply_tps(v, src, w, a), idx)
        fman["layers"][key] = {"label": label, "file": f"{key}.bin", **out, "parts": info["parts"]}
        print(f"{key}: {out['vertexCount']} vértices, {len(info['parts'])} partes")
    fman["note"] = ("Músculos e ossos: BodyParts3D 4.0 (DBCLS, CC BY 4.0) adaptados ao corpo feminino "
                    "por deformação guiada pelos pontos de acupuntura (backend/tools/build_female_layers.py).")
    (F / "anatomy.json").write_text(json.dumps(fman, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
