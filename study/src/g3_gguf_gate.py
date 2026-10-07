"""G3 GGUF equivalence gate: decider-4b-v2.1 Q4_K_M (llama.cpp) vs bf16 reference.
Gate (plan §7a): choice agreement >= 99.5% on 1,000 fixed sealed-ID rows, max |dp| reported against 1e-2 tolerance.
Run under venv-decider after the [gguf] extra is installed.
"""
import os as _os, pathlib as _pl
_STUDY_ROOT = _pl.Path(_os.environ.get("DECISION_STUDY_ROOT", _pl.Path(__file__).resolve().parents[1]))
_ANCHOR = _pl.Path(_os.environ.get("CLM8B_ANCHOR_ROOT", _STUDY_ROOT / "anchor-corpus"))
_MODELS = _pl.Path(_os.environ.get("DECIDER_MODELS_DIR", _STUDY_ROOT / "models"))

import json, time, os, statistics

SPLIT = str(_ANCHOR / "main-data" / "main_id.jsonl")
BF16 = str(_STUDY_ROOT / "g2-20261007" / "decider-zero-id.jsonl")
GGUF_REPO = str(_MODELS / "decider-4b-GGUF")
OUT = str(_STUDY_ROOT / "g3-20261007" / "gguf-gate.json")

rows = [json.loads(l) for l in open(SPLIT)][:1000]
bf = {json.loads(l)["id"]: json.loads(l) for l in open(BF16)}

from decider.infer import Decider
d = Decider(GGUF_REPO, gguf_file=os.path.join(GGUF_REPO, "decider-4b-v2.1-Q4_K_M.gguf"), device="cuda")

agree, mism, maxdp = 0, [], 0.0
acc = 0
lat = []
for i, r in enumerate(rows):
    q = r["questions"]["decision"]
    crit = q["criteria"]
    keys = list(crit)
    t0 = time.perf_counter()
    a = d.decide(r["state"], [{"question": q["instructions"], "options": [crit[k] for k in keys]}])[0]
    lat.append((time.perf_counter() - t0) * 1000)
    desc2key = {crit[k]: k for k in keys}
    pred = desc2key.get(a.get("choice"))
    b = bf.get(r["id"])
    if pred == b["pred"]:
        agree += 1
    else:
        mism.append({"id": r["id"], "gguf": pred, "bf16": b["pred"], "gold": r["gold"]["decision"]})
    for k in keys:
        pg = a.get("probs", {}).get(crit[k])
        pb = (b.get("probabilities") or {}).get(k)
        if pg is not None and pb is not None:
            maxdp = max(maxdp, abs(float(pg) - float(pb)))
    acc += pred == r["gold"]["decision"]

lat.sort()
res = {"n": len(rows), "choice_agreement": agree / len(rows),
       "gate_pass_995": agree / len(rows) >= 0.995,
       "max_abs_prob_diff": maxdp, "prob_tolerance_1e-2_pass": maxdp <= 1e-2,
       "gguf_accuracy": acc / len(rows),
       "mismatches_first_10": mism[:10], "n_mismatch": len(mism),
       "latency_p50_ms": round(lat[499], 3), "latency_p95_ms": round(lat[949], 3)}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w").write(json.dumps(res, indent=2))
print(json.dumps(res))
