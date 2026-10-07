"""G2 analysis — subjects vs frozen CLM-8B anchor on identical sealed splits.
Host python3, stdlib only. Run after runner outputs exist (missing files are skipped with a note).
"""
import os as _os, pathlib as _pl
_STUDY_ROOT = _pl.Path(_os.environ.get("DECISION_STUDY_ROOT", _pl.Path(__file__).resolve().parents[1]))
_ANCHOR = _pl.Path(_os.environ.get("CLM8B_ANCHOR_ROOT", _STUDY_ROOT / "anchor-corpus"))
_MODELS = _pl.Path(_os.environ.get("DECIDER_MODELS_DIR", _STUDY_ROOT / "models"))

import json, math, random, pathlib

G2 = pathlib.Path(str(_STUDY_ROOT / "g2-20261007"))
RUN = pathlib.Path(str(_ANCHOR))
BOOT_N = 10000
BOOT_SEED = 20261007

# ---------- loaders ----------

def load_ours(path):
    if not path.exists():
        return None
    rows = [json.loads(l) for l in open(path)]
    return {r["id"]: r for r in rows}

def load_anchor_pred(split, name):
    p = RUN / "final-evaluation" / "predictions" / split / f"{name}.jsonl"
    if not p.exists():
        return None
    out = {}
    for l in open(p):
        r = json.loads(l)
        probs = r.get("probabilities") or {}
        pred = max(probs, key=probs.get) if probs else r.get("predicted")
        out[r["id"]] = {"workflow": r["workflow"], "gold": r["gold"], "pred": pred,
                        "probabilities": probs, "correct": pred == r["gold"]}
    return out

def load_lexical(split, seed=11):
    base = RUN / "final-evaluation" / "probes" / split / "probe-lexical"
    if not base.exists():
        return None
    out = {}
    for wf in ("support", "infrastructure"):
        p = base / f"predictions-{wf}-seed-{seed}.jsonl"
        if not p.exists():
            continue
        for l in open(p):
            r = json.loads(l)
            out[r["id"]] = {"workflow": r["workflow"], "gold": r["gold_semantic_key"],
                            "pred": r["predicted_semantic_key"],
                            "probabilities": None,
                            "correct": r["gold_semantic_key"] == r["predicted_semantic_key"]}
    return out

# ---------- metrics ----------

def accuracy(rows):
    rs = list(rows)
    return sum(r["pred"] == r["gold"] for r in rs) / len(rs) if rs else None

def macro_f1(rows):
    classes = sorted({r["gold"] for r in rows} | {r["pred"] for r in rows if r.get("pred")})
    f1s = []
    for c in classes:
        tp = sum(r["gold"] == c and r["pred"] == c for r in rows)
        fp = sum(r["gold"] != c and r["pred"] == c for r in rows)
        fn = sum(r["gold"] == c and r["pred"] != c for r in rows)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return sum(f1s) / len(f1s) if f1s else None

def mean_workflow_macro_f1(rows):
    wfs = sorted({r["workflow"] for r in rows})
    vals = [macro_f1([r for r in rows if r["workflow"] == w]) for w in wfs]
    return sum(vals) / len(vals) if vals else None

def ece15(rows):
    pts = []
    for r in rows:
        p = r.get("probabilities") or {}
        if not p or r.get("pred") is None:
            continue
        conf = p.get(r["pred"], 0.0)
        pts.append((conf, 1.0 if r["pred"] == r["gold"] else 0.0))
    if not pts:
        return None
    bins = [(0.0, 0.1)] + [(i / 10, (i + 1) / 10) for i in range(1, 10)]
    ece = 0.0
    for lo, hi in bins:
        m = [pt for pt in pts if (lo < pt[0] <= hi) or (lo == 0.0 and pt[0] == 0.0)]
        if not m:
            continue
        conf = sum(x for x, _ in m) / len(m)
        acc = sum(y for _, y in m) / len(m)
        ece += len(m) / len(pts) * abs(acc - conf)
    return ece

def brier(rows):
    tot, n = 0.0, 0
    for r in rows:
        p = r.get("probabilities") or {}
        if not p:
            continue
        keys = sorted(p)
        tot += sum((p[k] - (1.0 if k == r["gold"] else 0.0)) ** 2 for k in keys)
        n += 1
    return tot / n if n else None

# ---------- inference ----------

def newcombe_paired(rows_a, rows_b):
    """Newcombe method-10 style hybrid-score CI for paired proportion difference."""
    n = len(rows_a)
    b = sum(a["correct"] and not bb["correct"] for a, bb in zip(rows_a, rows_b))
    c = sum(not a["correct"] and bb["correct"] for a, bb in zip(rows_a, rows_b))
    p1 = sum(a["correct"] for a in rows_a) / n
    p2 = sum(bb["correct"] for bb in rows_b) / n
    def wilson(k, nn, z=1.959964):
        ph = k / nn
        den = 1 + z * z / nn
        ctr = (ph + z * z / (2 * nn)) / den
        half = z * math.sqrt(ph * (1 - ph) / nn + z * z / (4 * nn * nn)) / den
        return ctr - half, ctr + half
    l1, u1 = wilson(sum(a["correct"] for a in rows_a), n)
    l2, u2 = wilson(sum(bb["correct"] for bb in rows_b), n)
    d = p1 - p2
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return {"diff": d, "ci95": [lo, hi], "discordant_b": b, "discordant_c": c}

def paired_bootstrap_metric(rows_a, rows_b, metric, n=BOOT_N, seed=BOOT_SEED):
    rng = random.Random(seed)
    diffs = []
    N = len(rows_a)
    for _ in range(n):
        idx = [rng.randrange(N) for _ in range(N)]
        ra = [rows_a[i] for i in idx]
        rb = [rows_b[i] for i in idx]
        diffs.append(metric(ra) - metric(rb))
    diffs.sort()
    return {"lo95": diffs[int(0.025 * n)], "hi95": diffs[int(0.975 * n)]}

def mcnemar_exact(rows_a, rows_b):
    b = sum(a["correct"] and not bb["correct"] for a, bb in zip(rows_a, rows_b))
    c = sum(not a["correct"] and bb["correct"] for a, bb in zip(rows_a, rows_b))
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "p_two_sided": 1.0}
    k = min(b, c)
    # exact two-sided binomial p = 2*P(X<=k), X~Bin(n,0.5), capped at 1
    p_one = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return {"b": b, "c": c, "p_two_sided": min(1.0, 2 * p_one)}

def softmax(xs):
    m = max(xs)
    es = [math.exp(x - m) for x in xs]
    s = sum(es)
    return [e / s for e in es]

def fit_temperature(probs_rows, served_T):
    """Fit scalar T by NLL over train rows; recovers logits = log(p)*served_T."""
    logits = []
    for r in probs_rows:
        p = r.get("probabilities") or {}
        keys = sorted(p)
        if not p or r.get("pred") is None:
            continue
        logits.append(([math.log(max(p[k], 1e-12)) * served_T for k in keys], keys.index(r["gold"])))
    def nll(T):
        s = 0.0
        for lg, gi in logits:
            pr = softmax([x / T for x in lg])
            s -= math.log(max(pr[gi], 1e-12))
        return s / len(logits)
    lo, hi = 0.05, 10.0
    for _ in range(200):  # golden-section
        m1 = lo + (hi - lo) / 3
        m2 = hi - (hi - lo) / 3
        if nll(m1) < nll(m2):
            hi = m2
        else:
            lo = m1
    return (lo + hi) / 2

def retemper_probs(r, T_new, T_old):
    p = r.get("probabilities") or {}
    if not p:
        return {}
    keys = sorted(p)
    lg = [math.log(max(p[k], 1e-12)) * T_old for k in keys]
    pr = softmax([x / T_new for x in lg])
    return dict(zip(keys, pr))

# ---------- main ----------

def ours_rows(split, name):
    d = load_ours(G2 / f"{name}-{split}.jsonl")
    if d is None:
        return None
    out = []
    for i, r in d.items():
        p = r.get("probabilities") or {}
        out.append({"id": i, "workflow": r["workflow"], "gold": r["gold"], "pred": r.get("pred"),
                    "probabilities": p, "correct": r.get("pred") == r["gold"]})
    return out

def report(name, rows):
    if rows is None:
        return None
    return {"n": len(rows), "accuracy": accuracy(rows),
            "mean_workflow_macro_f1": mean_workflow_macro_f1(rows),
            "ece15": ece15(rows), "brier": brier(rows)}

def main():
    res = {"boot_n": BOOT_N, "boot_seed": BOOT_SEED, "splits": {}, "contrasts": {}, "controls": {}}

    anchors = {}
    for split in ("id", "shifted"):
        anchors[split] = {
            "published": load_anchor_pred(split, "published"),
            "adapted_s11": load_anchor_pred(split, "adapted-b12000-s11"),
            "lexical_s11": load_lexical(split),
        }
        # majority baseline from gold key counts
        if anchors[split]["published"]:
            from collections import Counter
            golds = Counter(v["gold"] for v in anchors[split]["published"].values())
            mk, mc = golds.most_common(1)[0]
            anchors[split]["majority"] = {i: {"workflow": v["workflow"], "gold": v["gold"],
                                              "pred": mk, "probabilities": {}, "correct": v["gold"] == mk}
                                          for i, v in anchors[split]["published"].items()}

    subjects = ["laya-zero", "decider-zero", "laya-ft", "decider-zero-retuned"]
    for split in ("id", "shifted"):
        res["splits"][split] = {}
        for name in subjects:
            rows = ours_rows(split, name)
            if rows is not None:
                res["splits"][split][name] = report(name, rows)
        for aname, arows in anchors[split].items():
            if arows:
                res["splits"][split]["anchor_" + aname] = report(aname, list(arows.values()))

    # paired contrasts on ID: each subject vs anchor published / adapted / lexical
    for sname in subjects:
        rows = ours_rows("id", sname)
        if rows is None:
            continue
        by_id = {r["id"]: r for r in rows}
        for aname in ("published", "adapted_s11", "lexical_s11"):
            arows = anchors["id"][aname]
            if not arows:
                continue
            common = [i for i in by_id if i in arows]
            if len(common) < 100:
                continue
            ra = [by_id[i] for i in common]
            rb = [arows[i] for i in common]
            res["contrasts"][f"{sname}_vs_anchor_{aname}_id"] = {
                "n": len(common),
                "accuracy_newcombe_paired": newcombe_paired(ra, rb),
                "macro_f1_diff_bootstrap": paired_bootstrap_metric(ra, rb, mean_workflow_macro_f1),
            }

    # shuffle controls
    for sname, base in (("laya-zero", "laya-zero"), ("decider-zero", "decider-zero")):
        sh = load_ours(G2 / f"{sname}-id-shuffle.jsonl")
        bs = load_ours(G2 / f"{base}-id.jsonl")
        if sh and bs:
            common = [i for i in sh if i in bs]
            ra = [{"correct": sh[i]["pred"] == sh[i]["gold"], "pred": sh[i]["pred"], "gold": sh[i]["gold"],
                   "workflow": sh[i]["workflow"], "probabilities": sh[i].get("probabilities")} for i in common]
            rb = [{"correct": bs[i]["pred"] == bs[i]["gold"], "pred": bs[i]["pred"], "gold": bs[i]["gold"],
                   "workflow": bs[i]["workflow"], "probabilities": bs[i].get("probabilities")} for i in common]
            flips = sum(x["pred"] != y["pred"] for x, y in zip(ra, rb))
            res["controls"][sname + "_shuffle"] = {
                "n": len(common), "pred_flips": flips, "flip_rate": flips / len(common),
                "mcnemar": mcnemar_exact(ra, rb),
                "accuracy_shuffled": accuracy(ra), "accuracy_base": accuracy(rb),
            }

    # decider temperature refit from train-split predictions (served T_choice = 1.11)
    dtr = load_ours(G2 / "decider-zero-train.jsonl")
    if dtr:
        rows = list(dtr.values())
        T = fit_temperature(rows, 1.11)
        res["controls"]["decider_temperature_refit"] = {"fitted_T_choice": T, "train_rows": len(rows)}
        for split in ("id", "shifted"):
            rr = ours_rows(split, "decider-zero")
            if rr is None:
                continue
            ret = [dict(r, probabilities=retemper_probs(r, T, 1.11),
                        correct=r["correct"]) for r in rr]
            # argmax unchanged by monotone retemp; recompute correct for safety
            ret = [dict(r, correct=(max(r["probabilities"], key=r["probabilities"].get) == r["gold"]
                                    if r["probabilities"] else r["correct"])) for r in ret]
            res["splits"][split]["decider-zero-retuned"] = report("ret", ret)

    G2.mkdir(parents=True, exist_ok=True)
    out = G2 / "analysis.json"
    out.write_text(json.dumps(res, indent=2))
    print("wrote", out)
    print(json.dumps(res["splits"].get("id", {}), indent=1)[:1500])

if __name__ == "__main__":
    main()
