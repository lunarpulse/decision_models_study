"""G2 runner — subject: laya. Run under the repo's .venv-laya/bin/python (see ../README.md).

Usage: g2_laya.py --split FILE --out FILE [--model PATH_OR_ID] [--shuffle-control] [--limit N]
Writes one JSONL row per decision: {id, workflow, gold, pred, probabilities, ms, error?}
"""
import os as _os, pathlib as _pl
_STUDY_ROOT = _pl.Path(_os.environ.get("DECISION_STUDY_ROOT", _pl.Path(__file__).resolve().parents[1]))
_ANCHOR = _pl.Path(_os.environ.get("CLM8B_ANCHOR_ROOT", _STUDY_ROOT / "study" / "anchor-corpus"))
_MODELS = _pl.Path(_os.environ.get("DECIDER_MODELS_DIR", _STUDY_ROOT / "models"))

import argparse, json, random, time, pathlib, sys

p = argparse.ArgumentParser()
p.add_argument("--split", required=True)
p.add_argument("--out", required=True)
p.add_argument("--model", default=None, help="direct checkpoint path (bypasses Router)")
p.add_argument("--shuffle-control", action="store_true")
p.add_argument("--limit", type=int, default=None)
args = p.parse_args()

rows = [json.loads(l) for l in open(args.split)]
if args.shuffle_control:
    rows = rows[:1000]
elif args.limit:
    rows = rows[:args.limit]

if args.model:
    import laya
    eng = laya.load(args.model, device="cuda")
    engine_name = f"direct:{args.model}"
else:
    from laya import Router
    eng = Router(preload=True)
    engine_name = "router:convaiinnovations/laya"

out = open(args.out, "w")
t_start = time.time()
n_err = 0
for i, r in enumerate(rows):
    q = r["questions"]
    if args.shuffle_control:
        rng = random.Random(11000 + i)  # seeded per-row; control is reproducible
        for qid, qq in q.items():
            crit = qq.get("criteria")
            if isinstance(crit, dict):
                items = list(crit.items()); rng.shuffle(items)
                qq["criteria"] = dict(items)
            elif isinstance(crit, list):
                rng.shuffle(crit)
    t0 = time.perf_counter()
    try:
        res = eng.predict(r["state"], q)
        a = res["answers"]["decision"]
        probs = {str(k): float(v) for k, v in a.get("probabilities", {}).items()}
        pred = a.get("choice")
        rec = {"id": r["id"], "workflow": r["workflow"], "gold": r["gold"]["decision"],
               "pred": pred, "probabilities": probs, "ms": round((time.perf_counter() - t0) * 1000, 3)}
    except Exception as e:
        n_err += 1
        rec = {"id": r["id"], "workflow": r["workflow"], "gold": r["gold"]["decision"],
               "pred": None, "probabilities": {}, "ms": round((time.perf_counter() - t0) * 1000, 3),
               "error": repr(e)[:200]}
    out.write(json.dumps(rec) + "\n")
    if (i + 1) % 500 == 0:
        out.flush(); print(f"{i+1}/{len(rows)} rows, errs={n_err}", flush=True)
out.close()
print(json.dumps({"engine": engine_name, "split": args.split, "out": args.out,
                  "rows": len(rows), "errors": n_err,
                  "shuffle_control": args.shuffle_control,
                  "wall_s": round(time.time() - t_start, 1)}))
