"""G1 contract tests — subject: decider-4b v2.1 (plan §4). Run under the repo's .venv-decider/bin/python (see ../README.md)."""
import os as _os, pathlib as _pl
_STUDY_ROOT = _pl.Path(_os.environ.get("DECISION_STUDY_ROOT", _pl.Path(__file__).resolve().parents[1]))
_ANCHOR = _pl.Path(_os.environ.get("CLM8B_ANCHOR_ROOT", _STUDY_ROOT / "study" / "anchor-corpus"))
_MODELS = _pl.Path(_os.environ.get("DECIDER_MODELS_DIR", _STUDY_ROOT / "models"))

import sys, statistics, random
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
from contract_common import STATES, CHOICE_OPTS, SCORE_LEVELS, dump, Timer

res = {"subject": "decider-4b-v2.1"}

import decider
from decider.infer import Decider
res["package"] = getattr(decider, "__version__", "unknown")

d = Decider(str(_MODELS / "decider-4b"))  # local snapshot path recorded by G0 ledger

QS = [
    {"question": "Which team should handle this?", "options": CHOICE_OPTS},
    {"question": "How urgent is this?", "options": SCORE_LEVELS},
    {"question": "Does the sender threaten to cancel or escalate?", "options": ["no", "yes"]},
]

# t1 schema round-trip + t4 multi-question single pass
with Timer() as tm:
    out = d.decide(STATES[0]["body"], QS)
res["t1_roundtrip_ms"] = round(tm.ms, 2)
res["t1_answers"] = [{"choice": a.get("choice"), "confidence": a.get("confidence"),
                      "probs_sum": round(sum(a.get("probs", {}).values()), 6)} for a in out]
res["t1_keys_ok"] = len(out) == 3

# t3 determinism
out2 = d.decide(STATES[0]["body"], QS)
def flat(o):
    vals = []
    for a in o: vals += list(a.get("probs", {}).values())
    return vals
f1, f2 = flat(out), flat(out2)
res["t3_determinism_max_abs_diff"] = max((abs(a - b) for a, b in zip(f1, f2)), default=None)

# t2 option-count boundary: 2, 20, 21, 255
for n in (2, 20, 21, 255):
    opts = [f"option {i}" for i in range(n)]
    try:
        with Timer() as tm:
            o = d.decide(STATES[1]["body"], [{"question": "Pick option 7.", "options": opts}])
        res[f"t2_options_{n}"] = {"ok": True, "ms": round(tm.ms, 2),
                                  "choice": o[0].get("choice"),
                                  "n_probs": len(o[0].get("probs", {}))}
    except Exception as e:
        res[f"t2_options_{n}"] = {"ok": False, "error": repr(e)[:200]}

# t4 temperature semantics: stored map vs global override; argmax invariant
a_map = d.decide(STATES[3]["body"], QS)
dG = Decider(str(_MODELS / "decider-4b"), temperature=1.099)
a_glob = dG.decide(STATES[3]["body"], QS)
amax_same = all(x.get("choice") == y.get("choice") for x, y in zip(a_map, a_glob))
pdiff = max((abs(p - q) for x, y in zip(a_map, a_glob)
             for p, q in zip(x.get("probs", {}).values(), y.get("probs", {}).values())), default=None)
res["t4_temperature"] = {"argmax_invariant": amax_same, "max_prob_diff_map_vs_global": pdiff}
del dG

# t5 context: ~8k-token state (32k claim; 8k informational)
long_body = "Incident log: " + ("payment gateway latency spike, retry storm, degraded checkout. " * 700)
try:
    with Timer() as tm:
        o = d.decide(long_body, [QS[0]])
    res["t5_long_state_8k"] = {"ok": True, "ms": round(tm.ms, 2), "choice": o[0].get("choice")}
except Exception as e:
    res["t5_long_state_8k"] = {"ok": False, "error": repr(e)[:200]}

# t7 option-order sensitivity on 5 states
flips = 0
rng = random.Random(11)
for st in STATES:
    base = d.decide(st["body"], [QS[0]])[0].get("choice")
    opts = list(CHOICE_OPTS); rng.shuffle(opts)
    shuf = d.decide(st["body"], [{"question": QS[0]["question"], "options": opts}])[0].get("choice")
    if base != shuf: flips += 1
res["t7_order_flips_of_5"] = flips

# latency probe: p50 of 50 single-question calls
lat = []
for _ in range(50):
    with Timer() as tm: d.decide(STATES[2]["body"], [QS[0]])
    lat.append(tm.ms)
res["latency_p50_ms_50calls"] = round(statistics.median(lat), 2)
res["latency_p95_ms_50calls"] = round(sorted(lat)[int(0.95 * len(lat)) - 1], 2)

dump("decider", res)
print("DECIDER CONTRACT DONE")
