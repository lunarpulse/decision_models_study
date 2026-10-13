"""Build portfolio_results.json: all engines measured once on the 500-claim sealed holdout.

Arms: laya zero-shot, laya fine-tuned (era-2 checkpoint), decider-4b zero-shot, rules engine
(Engine D). An optional fine-tuned decider arm (--dec-ft PATH) is appended when it exists.
Also regenerates data/stats.json (schema-compatible: zero/ft/dec + extras).

Run under the repo's .venv-laya python with the decider package importable
(UV_PROJECT_ENVIRONMENT=.venv-decider layout: copy this file's decider call or run twice).
Simplest supported invocation (single venv that has both laya and decider-ai, e.g. the box):

    python build_portfolio.py            # laya arms + rules (+ decider if importable)
    python build_portfolio.py --no-dec   # skip the decider arm
"""
import argparse, json, pathlib, time

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data"

import rules_engine


def ask_laya(eng, state, questions):
    t0 = time.perf_counter()
    res = eng.predict(state, questions).get("answers", {})
    ms = (time.perf_counter() - t0) * 1000
    out = {}
    for qid, a in res.items():
        d = {"type": a.get("type")}
        if a.get("type") == "noul":
            d["noul"] = round(float(a.get("noul", 0.0)), 4)
        if a.get("choice") is not None:
            d["choice"] = a["choice"]
        if a.get("score") is not None:
            d["score"] = a["score"]
        if a.get("probabilities"):
            d["probabilities"] = {k: round(float(v), 4) for k, v in a["probabilities"].items()}
        out[qid] = d
    return {"answers": out, "ms": round(ms, 1)}


def ask_decider(d, state, questions):
    def render(q):
        if q["type"] == "noul":
            return {"question": q["instructions"], "options": ["no", "yes"]}, None
        crit = q["criteria"]
        if isinstance(crit, dict):
            keys = list(crit.keys())
            return {"question": q["instructions"], "options": keys}, keys
        return {"question": q["instructions"], "options": list(crit)}, list(crit)

    t0 = time.perf_counter()
    qs, metas = [], []
    for qid, q in questions.items():
        qq, keys = render(q)
        qs.append(qq)
        metas.append((qid, q["type"], keys))
    res = d.decide(state, qs)
    ms = (time.perf_counter() - t0) * 1000
    out = {}
    for (qid, qtype, keys), a in zip(metas, res):
        probs = a.get("probs", {})
        d2 = {"type": qtype}
        if qtype == "noul":
            d2["noul"] = round(float(probs.get("yes", 0.0)), 4)
        elif qtype == "choice":
            d2["choice"] = a.get("choice")
        else:  # score: options are level labels; gold is the level index
            label = a.get("choice")
            d2["score"] = keys.index(label) if label in keys else -1
            d2["score_label"] = label
        d2["probabilities"] = {k: round(float(v), 4) for k, v in probs.items()}
        out[qid] = d2
    return {"answers": out, "ms": round(ms, 1)}


def correct(qid, gold, ans):
    if ans is None:
        return False
    g = gold if not isinstance(gold, bool) else int(gold)
    if ans.get("type") == "noul":
        return int(ans.get("noul", 0) > 0.5) == g
    v = ans.get("choice", ans.get("score"))
    if v is None:
        v = ans.get("score_key")
    return v == g


def calibration(pairs, bins=10):
    out = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(p, y) for p, y in pairs if lo <= p < hi or (b == bins - 1 and p == 1.0)]
        if sel:
            out.append({"lo": round(lo, 2), "hi": round(hi, 2), "n": len(sel),
                        "avg_p": round(sum(p for p, _ in sel) / len(sel), 3),
                        "acc": round(sum(y for _, y in sel) / len(sel), 3)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dec-ft", default=str(ROOT / "decider-ft-ckpt" / "model"))
    ap.add_argument("--no-dec", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(DATA / "holdout_eval.jsonl")]
    if a.limit:
        rows = rows[: a.limit]
    questions = json.load(open(DATA / "demo_presets.json"))["questions"]

    import gc, torch
    t0 = time.time()
    claims = [{"id": r["id"], "state": r["state"], "gold": r["gold"], "meta": r["meta"], "arms": {}}
              for r in rows]
    per = {}   # arm -> qid -> [ok, n]
    calib = {}
    def note(arm, qid, okv):
        per.setdefault(arm, {}).setdefault(qid, [0, 0])
        per[arm][qid][0] += int(okv); per[arm][qid][1] += 1

    # ---- decider arms FIRST (largest weights, loaded and freed before the laya arms) ----
    dec_specs = []
    if not a.no_dec:
        dec_specs.append(("dec", "Mapika/decider-4b"))
    if pathlib.Path(a.dec_ft).exists():
        dec_specs.append(("dec_ft", a.dec_ft))
    for arm_name, model_path in dec_specs:
        try:
            from decider.infer import Decider
            print(f"[decider] loading {model_path} ...", flush=True)
            eng = Decider(model_path, device="cuda")
        except Exception as e:
            print(f"[{arm_name}] load failed, skipping:", repr(e)[:120])
            continue
        for rec in claims:
            rec["arms"][arm_name] = ask_decider(eng, rec["state"], questions)
            for qid, g in rec["gold"].items():
                note(arm_name, qid, correct(qid, g, rec["arms"][arm_name]["answers"].get(qid)))
        calib[arm_name] = calibration([(rec["arms"][arm_name]["answers"]["fraud_review"]["noul"],
                                        int(rec["meta"]["fraud"])) for rec in claims])
        del eng
        gc.collect(); torch.cuda.empty_cache()

    # ---- laya arms + rules ----
    import laya
    from laya import Router
    zero = Router(preload=True)
    ft = laya.load(str(ROOT / "laya-ft-ckpt"))
    for r, rec in zip(rows, claims):
        for arm, eng in (("zero", zero), ("ft", ft)):
            rec["arms"][arm] = ask_laya(eng, r["state"], questions)
            for qid, g in r["gold"].items():
                note(arm, qid, correct(qid, g, rec["arms"][arm]["answers"].get(qid)))
        rr = rules_engine.decide(r["state"])
        rec["arms"]["rules"] = {"answers": rr["answers"], "evidence": rr["evidence"], "ms": rr["ms"]}
        for qid, g in r["gold"].items():
            note("rules", qid, correct(qid, g, rr["answers"].get(qid)))

    for arm in ("zero", "ft"):
        calib[arm] = calibration([(rec["arms"][arm]["answers"]["fraud_review"]["noul"],
                                   int(rec["meta"]["fraud"])) for rec in claims])

    # money aggregates at tau=0.8 on fraud flag
    money = {}
    for arm in per:
        if arm == "rules":
            flagged = [rec for rec in claims if rec["arms"]["rules"]["answers"]["fraud_review"]["noul"] > 0.5]
        else:
            flagged = [rec for rec in claims if rec["arms"].get(arm, {}).get("answers", {})
                       .get("fraud_review", {}).get("noul", 0) > 0.8]
        gold_fraud_usd = sum(rec["meta"]["amount"] for rec in claims if rec["meta"]["fraud"])
        tp = sum(rec["meta"]["amount"] for rec in flagged if rec["meta"]["fraud"])
        fp = sum(rec["meta"]["amount"] for rec in flagged if not rec["meta"]["fraud"])
        money[arm] = {"flagged_usd": tp + fp, "true_fraud_usd_caught": tp,
                      "false_flag_usd": fp, "gold_fraud_usd_total": gold_fraud_usd}

    summary = {"n": len(claims),
               "accuracy": {arm: {qid: round(v[0] / v[1], 4) for qid, v in qs.items()}
                            for arm, qs in per.items()},
               "all_correct": {arm: sum(all(correct(q, g, rec["arms"][arm]["answers"].get(q))
                                            for q, g in rec["gold"].items())
                                        for rec in claims if arm in rec["arms"])
                               for arm in per},
               "calibration": calib, "money_tau_0.8": money,
               "total_claimed_usd": sum(rec["meta"]["amount"] for rec in claims)}

    out = {"built": time.strftime("%Y-%m-%dT%H:%M:%S"), "n": len(claims),
           "summary": summary, "claims": claims}
    json.dump(out, open(DATA / "portfolio_results.json", "w"))

    stats = {"n_rows": len(claims),
             "rows_all_correct": summary["all_correct"],
             "per_question": summary["accuracy"], "elapsed_s": round(time.time() - t0, 1)}
    for arm in ("zero", "ft", "dec", "dec_ft", "rules"):
        if arm in summary["accuracy"]:
            accs = list(summary["accuracy"][arm].values())
            stats[arm if arm != "dec_ft" else "decft"] = round(sum(accs) / len(accs), 4)
    stats["zero"] = stats.get("zero", 0.0)
    json.dump(stats, open(DATA / "stats.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in stats.items() if k != "per_question"}, indent=1))
    print("wrote", DATA / "portfolio_results.json")


if __name__ == "__main__":
    main()
