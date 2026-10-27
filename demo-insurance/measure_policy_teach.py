"""Measure the Domain Builder's policy re-teach offline (DEVELOPMENT_LOG Phase 10).

For each domain policy preset: relabel corpus rows under the new rule
(domain_factory.policy_training_rows), fine-tune FROM the domain's production checkpoint
(studio-runs/<domain>/prod-ckpt, trained once on the current rulebook), then score the full
500-row holdout and the 24-row live exam:

  changed decisions   (row, question) pairs whose rule answer the policy changes:
                      production model vs taught model, both against the NEW rule
  kept decisions      every other pair: does the taught model keep what production got right?
  all 7 right         per row, under the new rulebook

Run inside the laya venv with the GPU free of other training:
  python measure_policy_teach.py --domain support_tickets [--policy vip] [--epochs 1]
Results append to <out>/results.jsonl (default studio-runs/policy-measure/); production answers
cache to <out>/<domain>-prod.json.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(os.environ.get("DEMO_ROOT", pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from domains import DOMAINS                                                   # noqa: E402
from domain_factory import (apply_policy, normalize_policy, policy_exam,      # noqa: E402
                            policy_training_rows, rule_gold, changed_decisions)


def value(a):
    if a.get("type") == "noul":
        return a.get("noul", 0) > 0.5
    if a.get("type") == "score":
        return int(round(float(a.get("score", -1))))
    return a.get("choice")


def predict_all(ckpt, states, defs, device):
    import laya
    import torch
    eng = laya.load(str(ckpt), device=device)
    out = [{q: value(a) for q, a in r.get("answers", {}).items()}
           for r in eng.predict_batch(states, defs, batch_size=16)]
    del eng
    torch.cuda.empty_cache()
    return out


def score(rows, preds, gold_key):
    changed_ok = changed_n = kept_ok = kept_n = all7 = 0
    for r, p in zip(rows, preds):
        new = r[gold_key]
        diff = set(r["changed"])
        all7 += all(p.get(q) == g for q, g in new.items())
        for q, g in new.items():
            if q in diff:
                changed_n += 1; changed_ok += p.get(q) == g
            else:
                kept_n += 1; kept_ok += p.get(q) == g
    return {"changed": [changed_ok, changed_n], "kept": [kept_ok, kept_n], "all7": [all7, len(rows)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True, choices=sorted(DOMAINS))
    ap.add_argument("--policy", default="all", help="kind (reassign|vip|risk) or 'all'")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--n-changed", type=int, default=300)
    ap.add_argument("--n-same", type=int, default=300)
    ap.add_argument("--micro-batch", type=int, default=8)
    ap.add_argument("--grad-accum", type=int, default=2)
    ap.add_argument("--out", default=str(ROOT / "studio-runs" / "policy-measure"))
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    spec = DOMAINS[args.domain]
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    prod = ROOT / "studio-runs" / args.domain / "prod-ckpt"
    train = [json.loads(l) for l in open(ROOT / "data" / args.domain / "train.jsonl")]
    hold = [json.loads(l) for l in open(ROOT / "data" / args.domain / "holdout_eval.jsonl")]
    states = [r["state"] for r in hold]

    cache = out / f"{args.domain}-prod.json"
    if cache.exists():
        prod_preds = json.load(open(cache))
    else:
        t = time.time()
        prod_preds = predict_all(prod, states, spec["questions"]["defs"], args.device)
        json.dump(prod_preds, open(cache, "w"))
        print(f"[prod] predicted 500 in {time.time() - t:.1f}s", flush=True)
    base_rows = [{"old_gold": r["gold"], "new_gold": r["gold"], "changed": []} for r in hold]
    print("[prod] current rulebook:", score(base_rows, prod_preds, "new_gold"), flush=True)

    for pol in spec["policies"]:
        if args.policy not in ("all", pol["kind"]):
            continue
        p = normalize_policy(spec, pol)
        new_spec = apply_policy(spec, p)
        run = out / f"{args.domain}-{p['kind']}-e{args.epochs}-c{args.n_changed}-s{args.n_same}"
        run.mkdir(exist_ok=True)
        rows, n_ch, n_same = policy_training_rows(spec, train, p, args.n_changed, args.n_same)
        with open(run / "session.jsonl", "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        cmd = [sys.executable, "-m", "laya.train_cli", "--data", str(run / "session.jsonl"),
               "--base", str(prod), "--out", str(run / "ckpt"), "--loss", "soft-ce",
               "--shuffle-options", "--epochs", str(args.epochs),
               "--micro-batch", str(args.micro_batch), "--grad-accum", str(args.grad_accum),
               "--device", args.device]
        t = time.time()
        with open(run / "train.log", "w") as log:
            rc = subprocess.call(cmd, stdout=log, stderr=subprocess.STDOUT,
                                 env={**os.environ, "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"})
        train_s = round(time.time() - t, 1)
        if rc:
            print(f"[{p['kind']}] train failed rc={rc} — see {run / 'train.log'}", flush=True)
            continue
        t = time.time()
        after = predict_all(run / "ckpt", states, new_spec["questions"]["defs"], args.device)
        eval_s = round(time.time() - t, 1)
        full = []
        for r in hold:
            new = rule_gold(new_spec, r["state"])
            full.append({"id": r["id"], "old_gold": r["gold"], "new_gold": new,
                         "changed": changed_decisions(r["gold"], new)})
        exam_ids = {e["id"] for e in policy_exam(spec, hold, p)}
        idx = [i for i, r in enumerate(hold) if r["id"] in exam_ids]
        res = {"domain": args.domain, "policy": p, "epochs": args.epochs,
               "n_changed": args.n_changed, "n_same": args.n_same, "train_rows": len(rows),
               "corpus_changed": n_ch, "train_s": train_s, "eval500_s": eval_s,
               "holdout": {"before": score(full, prod_preds, "new_gold"),
                           "after": score(full, after, "new_gold")},
               "exam": {"before": score([full[i] for i in idx], [prod_preds[i] for i in idx], "new_gold"),
                        "after": score([full[i] for i in idx], [after[i] for i in idx], "new_gold")}}
        with open(out / "results.jsonl", "a") as f:
            f.write(json.dumps(res) + "\n")
        print(json.dumps(res), flush=True)
        import shutil
        shutil.rmtree(run / "ckpt", ignore_errors=True)


if __name__ == "__main__":
    main()
