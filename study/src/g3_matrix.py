"""G3 serving matrix cell runner.
Usage: g3_matrix.py --subject {laya|decider|decider-gguf} --placement {cuda|cpu} --regime {uncached|repeat} --out FILE
50 disjoint warmups, then 3 blocks x 1000 measured requests (fresh process per cell by design).
"""
import os as _os, pathlib as _pl
_STUDY_ROOT = _pl.Path(_os.environ.get("DECISION_STUDY_ROOT", _pl.Path(__file__).resolve().parents[1]))
_ANCHOR = _pl.Path(_os.environ.get("CLM8B_ANCHOR_ROOT", _STUDY_ROOT / "anchor-corpus"))
_MODELS = _pl.Path(_os.environ.get("DECIDER_MODELS_DIR", _STUDY_ROOT / "models"))

import argparse, json, time, statistics, os, subprocess

p = argparse.ArgumentParser()
p.add_argument("--subject", required=True, choices=["laya", "decider", "decider-gguf"])
p.add_argument("--placement", required=True, choices=["cuda", "cpu"])
p.add_argument("--regime", required=True, choices=["uncached", "repeat"])
p.add_argument("--out", required=True)
p.add_argument("--split", default=str(_ANCHOR / "main-data" / "main_id.jsonl"))
p.add_argument("--gguf-repo", default=str(_MODELS / "decider-4b-GGUF"))
args = p.parse_args()

rows = [json.loads(l) for l in open(args.split)][:1105]  # 50 warmup + 3x1000 cycle (reuse allowed: regimes differ by intent)

def build_engine():
    if args.subject == "laya":
        if args.placement == "cpu":
            from laya import Router
            return Router(preload=True, device="cpu"), "router-cpu"
        from laya import Router
        return Router(preload=True), "router-gpu"
    if args.subject == "decider":
        from decider.infer import Decider
        kw = {"device": "cuda" if args.placement == "cuda" else "cpu"}
        return Decider(str(_MODELS / "decider-4b"), **kw), "decider-bf16"
    from decider.infer import Decider
    kw = {"device": "cuda" if args.placement == "cuda" else "cpu"}
    gg = os.path.join(args.gguf_repo, "decider-4b-v2.1-Q4_K_M.gguf")
    return Decider(args.gguf_repo, gguf_file=gg, **kw), "decider-gguf-q4km"

eng, eng_name = build_engine()

def one(i):
    r = rows[i % 1055]
    q = r["questions"]["decision"]
    if args.subject == "laya":
        eng.predict(r["state"], r["questions"])
    else:
        crit = q["criteria"]
        eng.decide(r["state"], [{"question": q["instructions"], "options": [crit[k] for k in crit]}])

for i in range(50):  # disjoint warmups
    one(i + 1000)

blocks = []
for b in range(3):
    lat = []
    t0 = time.time()
    for i in range(1000):
        idx = i if args.regime == "uncached" else 7  # repeat regime: same input every request
        t1 = time.perf_counter()
        one(idx)
        lat.append((time.perf_counter() - t1) * 1000)
    wall = time.time() - t0
    lat.sort()
    blocks.append({"block": b, "n": 1000, "wall_s": round(wall, 2),
                   "p50_ms": round(lat[499], 3), "p95_ms": round(lat[949], 3),
                   "decisions_per_s": round(1000 / wall, 3)})

vram = None
if args.placement == "cuda":
    try:
        vram = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        pass

import resource
out = {"subject": args.subject, "engine": eng_name, "placement": args.placement,
       "regime": args.regime, "blocks": blocks,
       "p50_mean_of_blocks": round(statistics.mean(b["p50_ms"] for b in blocks), 3),
       "p95_mean_of_blocks": round(statistics.mean(b["p95_ms"] for b in blocks), 3),
       "dec_per_s_mean": round(statistics.mean(b["decisions_per_s"] for b in blocks), 3),
       "vram_used_mib_end": vram, "max_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}
open(args.out, "w").write(json.dumps(out, indent=2))
print(json.dumps(out))
