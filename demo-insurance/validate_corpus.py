"""Replay validator for factory domains: recompute gold from raw state text, diff vs corpus.

Usage: python validate_corpus.py support_tickets [logistics_exceptions ...]
Passes when every holdout row's gold equals the rules replayed from the state text alone
(Engine D logic). This is the same standard the insurance corpus meets (500/500).
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from domains import DOMAINS
from domain_factory import decide


def validate(name, root=None):
    spec = DOMAINS[name]
    d = (root or pathlib.Path(__file__).resolve().parent / "data") / name
    rows = [json.loads(l) for l in open(d / "holdout_eval.jsonl")]
    per = {}
    bad = []
    for r in rows:
        out = decide(spec, r["state"])
        for qid, g in r["gold"].items():
            a = out["answers"].get(qid)
            v = a.get("choice", a.get("score")) if a else None
            if a and a.get("type") == "noul":
                v = int(a["noul"] > 0.5)
            gv = g if not isinstance(g, bool) else int(g)
            per.setdefault(qid, [0, 0])
            per[qid][0] += (v == gv)
            per[qid][1] += 1
            if v != gv and len(bad) < 5:
                bad.append((r["id"], qid, v, gv))
    ok = sum(v[0] for v in per.values())
    tot = sum(v[1] for v in per.values())
    print(f"[{name}] replay: {ok}/{tot} = {ok/tot:.4f}")
    for qid, (a, b) in per.items():
        flag = "" if a == b else "  <-- MISMATCH"
        print(f"    {qid}: {a}/{b}{flag}")
    if bad:
        print("  examples:", bad)
    return ok == tot


if __name__ == "__main__":
    names = sys.argv[1:] or list(DOMAINS)
    results = [validate(n) for n in names]
    sys.exit(0 if all(results) else 1)
