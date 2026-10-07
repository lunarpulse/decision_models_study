"""G2 runner — subject: decider-4b v2.1. Run under the repo's .venv-decider/bin/python (see ../../README.md and ../README.md).

Usage: g2_decider.py --split FILE --out FILE [--shuffle-control] [--limit N] [--temperature T]
Writes one JSONL row per decision: {id, workflow, gold, pred, probabilities, ms, error?}
"""
import os as _os, pathlib as _pl
_STUDY_ROOT = _pl.Path(_os.environ.get("DECISION_STUDY_ROOT", _pl.Path(__file__).resolve().parents[1]))
_ANCHOR = _pl.Path(_os.environ.get("CLM8B_ANCHOR_ROOT", _STUDY_ROOT / "anchor-corpus"))
_MODELS = _pl.Path(_os.environ.get("DECIDER_MODELS_DIR", _STUDY_ROOT / "models"))

import argparse, json, random, time

p = argparse.ArgumentParser()
p.add_argument("--split", required=True)
p.add_argument("--out", required=True)
p.add_argument("--model", default=str(_MODELS / "decider-4b"))
p.add_argument("--shuffle-control", action="store_true")
p.add_argument("--limit", type=int, default=None)
p.add_argument("--temperature", type=float, default=None)
args = p.parse_args()

rows = [json.loads(l) for l in open(args.split)]
if args.shuffle_control:
    rows = rows[:1000]
elif args.limit:
    rows = rows[:args.limit]

from decider.infer import Decider
kwargs = {}
if args.temperature is not None:
    kwargs["temperature"] = args.temperature
d = Decider(args.model, **kwargs)

out = open(args.out, "w")
t_start = time.time()
n_err = 0
for i, r in enumerate(rows):
    q = r["questions"]["decision"]
    crit = q["criteria"]
    keys = list(crit.keys())
    if args.shuffle_control:
        rng = random.Random(11000 + i)
        rng.shuffle(keys)
    opts = [crit[k] for k in keys]
    desc2key = {}
    for k in keys:
        desc2key.setdefault(crit[k], k)
    t0 = time.perf_counter()
    try:
        a = d.decide(r["state"], [{"question": q["instructions"], "options": opts}])[0]
        probs = {}
        for opt_name, pr in a.get("probs", {}).items():
            kk = desc2key.get(opt_name)
            if kk is not None:
                probs[kk] = probs.get(kk, 0.0) + float(pr)
        pred = desc2key.get(a.get("choice"))
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
print(json.dumps({"engine": "decider-4b-v2.1" + (f"@T={args.temperature}" if args.temperature else ""),
                  "split": args.split, "out": args.out, "rows": len(rows), "errors": n_err,
                  "shuffle_control": args.shuffle_control,
                  "wall_s": round(time.time() - t_start, 1)}))
