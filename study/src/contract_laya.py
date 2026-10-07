"""G1 contract tests — subject: laya (plan §4). Run under the repo's .venv-laya/bin/python (see ../../README.md and ../README.md)."""
import os as _os, pathlib as _pl
_STUDY_ROOT = _pl.Path(_os.environ.get("DECISION_STUDY_ROOT", _pl.Path(__file__).resolve().parents[1]))
_ANCHOR = _pl.Path(_os.environ.get("CLM8B_ANCHOR_ROOT", _STUDY_ROOT / "anchor-corpus"))
_MODELS = _pl.Path(_os.environ.get("DECIDER_MODELS_DIR", _STUDY_ROOT / "models"))

import sys, statistics, random
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
from contract_common import STATES, CHOICE_OPTS, SCORE_LEVELS, dump, Timer

res = {"subject": "laya"}

import laya
from laya import Router
res["package"] = getattr(laya, "__version__", "unknown")

router = Router(preload=True)

QUESTIONS = {
    "queue": {"type": "choice", "instructions": "Which team should handle this?",
              "criteria": {o: d for o, d in zip(CHOICE_OPTS, [
                  "server outages, network downtime, database failures",
                  "refunds, duplicate charges, invoice disputes",
                  "breaches, vulnerability reports, suspicious access",
                  "general how-to and account inquiries"])},
              },
    "urgency": {"type": "score", "instructions": "How urgent is this?",
                "criteria": SCORE_LEVELS},
    "churn": {"type": "noul", "instructions": "Does the sender threaten to cancel or escalate?"},
}

# t1 schema round-trip + t4 multi-question single pass
with Timer() as tm:
    out = router.predict(STATES[0], QUESTIONS)
res["t1_roundtrip_ms"] = round(tm.ms, 2)
res["t1_routing"] = out.get("routing", {})
ans = out["answers"]
res["t1_answers"] = {k: {kk: vv for kk, vv in v.items() if kk != "probs"} | {
    "probs_sum": round(sum(v.get("probs", {}).values()), 6) if isinstance(v.get("probs"), dict) else None}
    for k, v in ans.items()}
ok_keys = set(ans) == {"queue", "urgency", "churn"}
res["t1_keys_ok"] = ok_keys

# t3 determinism
out2 = router.predict(STATES[0], QUESTIONS)
def flat(o):
    vals = []
    for k, v in o["answers"].items():
        if isinstance(v.get("probabilities"), dict): vals += list(v["probabilities"].values())
        if "noul" in v: vals.append(v["noul"])
    return vals
f1, f2 = flat(out), flat(out2)
res["t3_determinism_max_abs_diff"] = max((abs(a - b) for a, b in zip(f1, f2)), default=None)
res["t3_n_values_compared"] = len(f1)

# t2 option-count boundary: 2, 20, 21 options
for n in (2, 20, 21):
    crit = {f"opt{i}": f"description number {i}" for i in range(n)}
    q = {"q": {"type": "choice", "instructions": "Pick the matching option.", "criteria": crit}}
    try:
        with Timer() as tm:
            o = router.predict(STATES[1], q)
        res[f"t2_options_{n}"] = {"ok": True, "ms": round(tm.ms, 2),
                                  "n_opts_returned": len(o["answers"]["q"].get("probabilities", {}))}
    except Exception as e:
        res[f"t2_options_{n}"] = {"ok": False, "error": repr(e)[:200]}

# t5 context cap: state longer than 512 tokens (English checkpoint budget)
long_state = {"body": "The customer writes: " + ("payment gateway latency spike incident report continuation. " * 90)}
try:
    o = router.predict(long_state, {"q": QUESTIONS["churn"]})
    res["t5_long_state"] = {"ok": True, "routing": o.get("routing", {})}
except Exception as e:
    res["t5_long_state"] = {"ok": False, "error": repr(e)[:200]}

# t6 routing audit on fixed multilingual probe
LANG_PROBE = {
    "english": "I need a refund for the duplicate charge.",
    "hindi": "मुझसे दो बार शुल्क लिया गया, कृपया पैसे वापस करें।",
    "arabic": "لقد تم خصم المبلغ مرتين، أريد استرداد المال.",
    "russian": "Меня списали дважды, пожалуйста, верните деньги.",
    "hebrew": "חייבו אותי פעמיים, אנא החזירו את הכסף.",
    "thai": "ฉันถูกคิดเงินสองครั้ง กรุณาคืนเงิน",
    "japanese": "二重に請求されました。返金してください。",
    "korean": "이중으로 청구되었습니다. 환불해 주세요.",
    "german": "Mir wurde doppelt abgebucht, bitte erstatten Sie den Betrag.",
    "spanish": "Me cobraron dos veces, por favor devuelvan el dinero.",
}
routing_map = {}
for lang, text in LANG_PROBE.items():
    o = router.predict({"body": text}, {"q": QUESTIONS["churn"]})
    routing_map[lang] = o.get("routing", {}).get("model", o.get("routing"))
res["t6_routing"] = routing_map

# t7 option-order sensitivity on 5 states
flips = 0
rng = random.Random(11)
for st in STATES:
    base = router.predict(st, {"q": QUESTIONS["queue"]})["answers"]["q"].get("choice")
    opts = list(CHOICE_OPTS); rng.shuffle(opts)
    q = {"q": {"type": "choice", "instructions": "Which team should handle this?",
               "criteria": {o: d for o, d in zip(opts, [
                   "server outages, network downtime, database failures",
                   "refunds, duplicate charges, invoice disputes",
                   "breaches, vulnerability reports, suspicious access",
                   "general how-to and account inquiries"])}}}
    shuf = router.predict(st, q)["answers"]["q"].get("choice")
    if base != shuf: flips += 1
res["t7_order_flips_of_5"] = flips

# latency probe: p50 of 50 single-question GPU calls
lat = []
q1 = {"q": QUESTIONS["queue"]}
for _ in range(50):
    with Timer() as tm: router.predict(STATES[2], q1)
    lat.append(tm.ms)
res["latency_p50_ms_50calls"] = round(statistics.median(lat), 2)
res["latency_p95_ms_50calls"] = round(sorted(lat)[int(0.95 * len(lat)) - 1], 2)

dump("laya", res)
print("LAYA CONTRACT DONE")
