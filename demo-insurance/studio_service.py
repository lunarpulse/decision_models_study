"""Teaching Studio service (Domain Builder v3): change a domain's rulebook, re-teach its
production model live, and put the old and new model side by side.

Port 8903 (localhost by default). The demo console reaches it through the laya service's
/studio/* proxy, so one public origin serves everything and this service needs no CORS.
The mutating route (/studio/train) requires the studio token (env STUDIO_TOKEN; the presenter
types it once in the console — it is never baked into the page); the service refuses to start
without one unless STUDIO_ALLOW_OPEN=1. Wrong tokens are compared with hmac.compare_digest and
throttled: five misses buy a 60 s timeout (429).

Models per domain, both under studio-runs/<domain>/:
  prod-ckpt   "your model": Laya fine-tuned once on the domain's 2,000 training rows under
              today's rulebook (train_prod_ckpt.sh). Never written by this service.
  ft-ckpt     the re-taught model: prod-ckpt fine-tuned on the presenter's policy change.
              Its policy and exam result persist in last-result.json next to it.

A policy change is a rulebook edit (domain_factory.apply_policy: reassign / vip / risk). The
rules engine relabels corpus rows under the new rule (TEACH_CHANGED_ROWS rows the rule changes,
TEACH_SAME_ROWS it leaves alone), train_cli fine-tunes FROM prod-ckpt with the updated rule text
in the question instructions, and the result is an exam on unseen holdout rows (EXAM_CHANGED
the rule changes + EXAM_SAME it does not): production answers (cached once per checkpoint in
prod-holdout.json) against the re-taught model's answers, both scored against the NEW rule.

/studio/compare answers any ticket with both models (production under today's question text,
re-taught under its policy's text) plus the rules engine under both rulebooks — open to every
viewer, one inference at a time, 409 while training.

Memory discipline: only one domain's two engines are resident. Before a run the studio evicts
them, reads torch.cuda.mem_get_info() and refuses (503) below TEACH_MIN_FREE_GIB. The new
checkpoint trains into ft-ckpt.new and replaces ft-ckpt only on success.

Full train_cli output goes to studio-runs/<domain>/train-<YYYYmmdd-HHMMSS>.log; parsed progress
({epoch, epochs, step, steps}) and short messages are kept for /studio/status. Failures are
classified from the log (out_of_gpu_memory vs train_failed). The train PID persists in
studio-runs/<domain>/train.pid and the job state in studio-runs/last_job.json; on startup a
leftover train_cli process is killed — only after verifying its cmdline — and the interrupted
job is reported as failed with error_kind "lost".
"""
import copy
import gc
import hmac
import json
import math
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
from collections import Counter, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(os.environ.get("DEMO_ROOT", pathlib.Path(__file__).resolve().parent))
DATA = ROOT / "data"
OUT = pathlib.Path(os.environ.get("STUDIO_RUNS") or ROOT / "studio-runs")
OUT.mkdir(parents=True, exist_ok=True)
TOKEN = os.environ.get("STUDIO_TOKEN", "")
if not TOKEN and os.environ.get("STUDIO_ALLOW_OPEN") != "1":
    print("[studio] refusing to start without STUDIO_TOKEN "
          "(set STUDIO_ALLOW_OPEN=1 only for throwaway local tests)", flush=True)
    raise SystemExit(2)
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8903
PY = os.environ.get("STUDIO_PY", str(ROOT.parent / ".venv-laya" / "bin" / "python"))
DEVICE = os.environ.get("STUDIO_DEVICE", "cuda")
# Re-teach defaults measured on this machine (DEVELOPMENT_LOG Phase 10): 300 changed + 300
# unchanged corpus rows, ONE pass at micro-batch 8 from prod-ckpt — every changed decision on the
# 500-row holdout learned in 49–61 s of training; a second pass bought nothing.
TEACH_EPOCHS = int(os.environ.get("TEACH_EPOCHS", "1"))
TEACH_MICRO_BATCH = int(os.environ.get("TEACH_MICRO_BATCH", "8"))
TEACH_GRAD_ACCUM = int(os.environ.get("TEACH_GRAD_ACCUM", "2"))
TEACH_CHANGED_ROWS = int(os.environ.get("TEACH_CHANGED_ROWS", "300"))
TEACH_SAME_ROWS = int(os.environ.get("TEACH_SAME_ROWS", "300"))
_max_len = os.environ.get("TEACH_MAX_LEN", "").strip()
TEACH_MAX_LEN = int(_max_len) if _max_len else None   # unset = flag not passed
TEACH_MIN_FREE_GIB = float(os.environ.get("TEACH_MIN_FREE_GIB", "11.5"))
TEACH_ENCODER_LR = os.environ.get("TEACH_ENCODER_LR", "").strip() or None  # unset = laya default
TEACH_HEAD_LR = os.environ.get("TEACH_HEAD_LR", "").strip() or None        # unset = laya default
EXAM_CHANGED = 12
EXAM_SAME = 12
SHOWCASE_N = 5
BODY_CAP = 64 * 1024
STATE_CAP = 4000
TOKEN_MISSES_ALLOWED = 5
THROTTLE_S = 60.0
COMPARE_WAIT_S = 15.0
# The out-of-the-box model (laya's zero-shot Router — the same engine the portfolio's "zero"
# numbers measured) is resident in the laya service; the studio asks it instead of loading a copy.
LAYA_PREDICT = f"http://127.0.0.1:{os.environ.get('LAYA_PORT', '8901')}/predict"
ZERO_TIMEOUT_S = 10.0
WARM_UP = os.environ.get("STUDIO_WARMUP", "1").strip().lower() not in ("0", "false", "no", "off")

sys.path.insert(0, str(ROOT))
from domains import DOMAINS as DOM                                   # noqa: E402
from domain_factory import (URGENCY_NAMES, apply_policy, changed_decisions,  # noqa: E402
                            decide, normalize_policy, policy_choices, policy_exam,
                            policy_is_noop, policy_sentence, policy_training_rows, rule_gold)

import laya                                                          # noqa: E402

_lock = threading.RLock()
_messages = deque(maxlen=20)
_job = {"state": "idle", "domain": None, "policy": None, "sentence": None, "started": None,
        "started_epoch": None, "ended_epoch": None, "pid": None, "progress": None,
        "error_kind": None, "error": None}          # "result" added when a run finishes
_warm_done = threading.Event()     # production answers cached: no warm-up pass can race a teach
_token_state = {"misses": 0, "blocked_until": 0.0}
_eng = {"domain": None, "prod": None, "taught": None}   # ONE domain's engines resident
_eng_lock = threading.Lock()
_compare_sem = threading.BoundedSemaphore(1)
_data, _data_lock = {}, threading.Lock()
_prod_vals, _prod_lock = {}, threading.Lock()
_impact_cache, _impact_lock = {}, threading.Lock()

_STEP_RE = re.compile(r"epoch (\d+)/(\d+) step (\d+)")
_MEAN_RE = re.compile(r"epoch (\d+)/(\d+) mean loss")
_ITEMS_RE = re.compile(r"train items (\d+)")


def _msg(text):
    _messages.append(text[:200])


def prod_ckpt(domain):
    return OUT / domain / "prod-ckpt"


def taught_ckpt(domain):
    return OUT / domain / "ft-ckpt"


# ------------------------------------------------------------------ answers & scoring

def answer_value(a):
    """Engine answer → gold-comparable value (bool / int / option key); None if missing."""
    if not isinstance(a, dict):
        return None
    if a.get("type") == "noul":
        return float(a.get("noul", 0)) > 0.5
    if a.get("type") == "score":
        return int(round(float(a["score"]))) if a.get("score") is not None else None
    return a.get("choice")


def answer_conf(a):
    """Confidence in the chosen value (0..1) where the engine reports one."""
    try:
        if a.get("type") == "noul":
            p = float(a.get("noul", 0))
            return round(max(p, 1 - p), 3)
        probs = a.get("probabilities") or {}
        key = a.get("choice") if a.get("type") == "choice" else str(answer_value(a))
        return round(float(probs[key]), 3) if key in probs else None
    except Exception:
        return None


def values(answers):
    return {q: answer_value(a) for q, a in (answers or {}).items()}


def zero_answers(state, defs):
    """Out-of-the-box answers {answers: {qid: {v, c}}, ms} from the laya service, or None."""
    try:
        req = urllib.request.Request(LAYA_PREDICT, data=json.dumps({"state": state, "questions": defs}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=ZERO_TIMEOUT_S) as r:
            z = json.load(r)["zero"]
        return {"answers": {q: {"v": answer_value(a), "c": a.get("confidence")} for q, a in z["answers"].items()},
                "ms": round(z.get("ms") or 0)}
    except Exception:
        traceback.print_exc()
        return None


def rules_view(spec, state):
    """Rules-engine answers ('unparsed' kept) with evidence, for the compare panel."""
    res = decide(spec, state)
    out = {}
    for q, a in res["answers"].items():
        v = a.get("choice") if a["type"] == "choice" else answer_value(a)
        out[q] = {"v": v, "why": res["evidence"].get(q, [])}
    return out


def tally(rows, key):
    """{changed, kept, all7} as [ok, n] for exam rows scored against new_gold."""
    ch = [0, 0]; kept = [0, 0]; all7 = [0, 0]
    for r in rows:
        ans = r.get(key) or {}
        diff = set(r["changed"])
        all7[1] += 1
        all7[0] += all(ans.get(q) == g for q, g in r["new_gold"].items())
        for q, g in r["new_gold"].items():
            bucket = ch if q in diff else kept
            bucket[1] += 1
            bucket[0] += ans.get(q) == g
    return {"changed": ch, "kept": kept, "all7": all7}


# ------------------------------------------------------------------ domain data (CPU)

def data(domain):
    """Training/holdout rows and the zero-shot portfolio answers, loaded once per domain."""
    with _data_lock:
        got = _data.get(domain)
        if got is not None:
            return got
        train = [json.loads(l) for l in open(DATA / domain / "train.jsonl")]
        hold = [json.loads(l) for l in open(DATA / domain / "holdout_eval.jsonl")]
        zero, summary = {}, {}
        try:
            pkg = json.load(open(DATA / domain / "portfolio_results.json"))
            summary = pkg.get("summary", {})
            zero = {c["id"]: values(c["arms"]["zero"]["answers"]) for c in pkg.get("claims", [])
                    if "zero" in c.get("arms", {})}
        except FileNotFoundError:
            pass
        got = {"train": train, "hold": hold, "zero": zero, "summary": summary}
        _data[domain] = got
        return got


def warning_signs(spec):
    """The warning signs as the routing instruction lists them (its first parenthesis)."""
    text = spec["questions"]["defs"][spec["questions"]["archetypes"]["routing"]]["instructions"]
    m = re.search(r"\(([^)]*)\)", text)
    if not m:
        return []
    return [s.strip() for s in re.split(r",\s+(?:or\s+)?|\s+or\s+", m.group(1)) if s.strip()]


# ------------------------------------------------------------------ engines (GPU)

def _empty_cache():
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def engines(domain, want_taught=True):
    """(production, re-taught) engines for `domain`; loading a domain evicts the previous one.

    The re-taught checkpoint loads only once its result is published (last-result.json names
    its policy); train_worker installs the fresh one itself for the exam."""
    with _eng_lock:
        if _eng["domain"] != domain:
            _eng.update(domain=None, prod=None, taught=None)
            _empty_cache()
            _eng["domain"] = domain
        if _eng["prod"] is None and prod_ckpt(domain).exists():
            _eng["prod"] = laya.load(str(prod_ckpt(domain)), device=DEVICE)
        if want_taught and _eng["taught"] is None and last_result(domain) is not None:
            _eng["taught"] = laya.load(str(taught_ckpt(domain)), device=DEVICE)
        return _eng["prod"], _eng["taught"]


def free_own_memory():
    """Evict both resident engines before a training run."""
    with _eng_lock:
        _eng.update(domain=None, prod=None, taught=None)
    _empty_cache()


def gpu_info():
    """{free_gib, total_gib} or None when no CUDA device is visible to this process."""
    try:
        import torch
        if not torch.cuda.is_available():
            return None
        free, total = torch.cuda.mem_get_info()
        return {"free_gib": round(free / 2**30, 2), "total_gib": round(total / 2**30, 2)}
    except Exception:
        return None


def prod_values(domain):
    """Production answers for every holdout row (list aligned with holdout order).

    Computed once per checkpoint and cached in studio-runs/<domain>/prod-holdout.json, keyed
    by the checkpoint's mtime and size; None when the domain has no production checkpoint."""
    with _prod_lock:
        if domain in _prod_vals:
            return _prod_vals[domain]
        weights = prod_ckpt(domain) / "model.safetensors"
        if not weights.exists():
            return None
        st = weights.stat()
        key = f"{st.st_mtime_ns}:{st.st_size}"
        cache = OUT / domain / "prod-holdout.json"
        try:
            got = json.load(open(cache))
            if got.get("key") == key:
                _prod_vals[domain] = got["answers"]
                return got["answers"]
        except Exception:
            pass
        hold = data(domain)["hold"]
        prod, _ = engines(domain, want_taught=False)
        t = time.time()
        res = prod.predict_batch([r["state"] for r in hold], DOM[domain]["questions"]["defs"],
                                 batch_size=16)
        vals = [values(r.get("answers")) for r in res]
        cache.write_text(json.dumps({"key": key, "answers": vals}))
        print(f"[studio] production answers for {domain}: {len(vals)} rows in "
              f"{time.time() - t:.1f}s", flush=True)
        _prod_vals[domain] = vals
        return vals


def warm_up():
    """Cache production answers for every domain so sessions and exams never wait on the GPU."""
    try:
        for domain in DOM:
            try:
                if prod_values(domain) is not None:
                    print(f"[studio] warmed {domain}", flush=True)
            except Exception:
                traceback.print_exc()
    finally:
        _warm_done.set()


# ------------------------------------------------------------------ session / impact

def arm_summary(summary, arm):
    acc = (summary.get("accuracy") or {}).get(arm)
    if not acc:
        return None
    return {"avg": round(sum(acc.values()) / len(acc), 4),
            "all7": (summary.get("all_correct") or {}).get(arm)}


def last_result(domain):
    """The persisted result of the checkpoint in ft-ckpt, or None."""
    if not (taught_ckpt(domain) / "model.safetensors").exists():
        return None
    try:
        return json.load(open(OUT / domain / "last-result.json"))
    except Exception:
        return None


def session_payload(domain):
    spec = DOM[domain]
    d = data(domain)
    hold, zero = d["hold"], d["zero"]
    pv = _prod_vals.get(domain)
    if pv is None and _warm_done.is_set() and not busy():
        pv = prod_values(domain)
    prod = None
    if pv is not None:
        per_q = Counter()
        all7 = 0
        for r, v in zip(hold, pv):
            ok = {q: v.get(q) == g for q, g in r["gold"].items()}
            per_q.update(q for q, good in ok.items() if good)
            all7 += all(ok.values())
        n = len(hold)
        prod = {"avg": round(sum(per_q.values()) / (n * len(hold[0]["gold"])), 4), "all7": all7}
    show = []
    for i, r in enumerate(hold):
        z = zero.get(r["id"])
        if not z:
            continue
        z_wrong = sum(z.get(q) != g for q, g in r["gold"].items())
        p_ok = pv is not None and all(pv[i].get(q) == g for q, g in r["gold"].items())
        if z_wrong >= 3 and (p_ok or pv is None):
            show.append({"id": r["id"], "state": r["state"], "gold": r["gold"], "zero": z,
                         "prod": pv[i] if pv is not None else None})
            if len(show) >= SHOWCASE_N:
                break
    choices = policy_choices(spec)
    presets = []
    for p in spec.get("policies", []):
        pol = normalize_policy(spec, p)
        presets.append({**pol, "title": p.get("title", ""), "story": p.get("story", ""),
                        "sentence": policy_sentence(spec, pol)})
    lr = last_result(domain)
    return {
        "domain": domain, "noun_plural": spec.get("noun_plural", "cases"),
        "questions": spec["questions"]["defs"], "stages": spec["stages"],
        "archetypes": spec["questions"]["archetypes"],
        "current": {"units": {k: c["unit"] for k, c in spec["categories"].items()},
                    "flag_markers": spec["signals"].get("flag_markers", 2),
                    "warning_signs": warning_signs(spec)},
        "choices": choices, "urgency_names": URGENCY_NAMES, "presets": presets,
        "baseline": {"n": len(hold), "zero": arm_summary(d["summary"], "zero"),
                     "dec": arm_summary(d["summary"], "dec"), "prod": prod},
        "showcase": show,
        "prod_ready": prod_ckpt(domain).exists(),
        "taught": lr,
        # for the console's ticket highlighter and one-click edits ("try to break it")
        "text": {"parsers": spec["parsers"], "doc_missing": spec["doc_missing_phrase"],
                 "doc_missing_marker": spec["doc_missing_marker"],
                 "doc_ok_prefix": spec["doc_ok_template"].split("{")[0].strip(),
                 "things": {k: c["things"] for k, c in spec["categories"].items()},
                 "today": spec["signals"]["today"].isoformat(),
                 "fresh_days": spec["signals"]["fresh_days"],
                 "large_amount": spec["signals"]["large_amount"]},
        "probes": [{"label": p["label"], "state": p["state"]} for p in spec.get("paraphrase_probes", [])],
    }


def impact(domain, pol):
    """What a policy changes (CPU only): corpus/holdout counts, per-decision counts, the exam."""
    key = (domain, json.dumps(pol, sort_keys=True))
    with _impact_lock:
        if key in _impact_cache:
            return copy.deepcopy(_impact_cache[key])
    spec = DOM[domain]
    d = data(domain)
    new_spec = apply_policy(spec, pol)
    corpus_changed = sum(1 for t in d["train"]
                         if changed_decisions(t["expected"], rule_gold(new_spec, t["state"]) or t["expected"]))
    by_q, hold_changed = Counter(), 0
    for r in d["hold"]:
        diff = changed_decisions(r["gold"], rule_gold(new_spec, r["state"]) or r["gold"])
        hold_changed += bool(diff)
        by_q.update(diff)
    exam = policy_exam(spec, d["hold"], pol, EXAM_CHANGED, EXAM_SAME)
    pv = _prod_vals.get(domain)
    if pv is not None:
        idx = {r["id"]: i for i, r in enumerate(d["hold"])}
        for e in exam:
            e["before"] = pv[idx[e["id"]]]
    for e in exam:                    # out-of-the-box answers, measured once for the portfolio
        e["zero"] = d["zero"].get(e["id"])
    out = {"policy": pol, "sentence": policy_sentence(spec, pol), "noop": policy_is_noop(spec, pol),
           "corpus": {"changed": corpus_changed, "total": len(d["train"])},
           "holdout": {"changed": hold_changed, "total": len(d["hold"]), "by_decision": dict(by_q)},
           "teach": {"changed_rows": min(TEACH_CHANGED_ROWS, corpus_changed),
                     "same_rows": min(TEACH_SAME_ROWS, len(d["train"]) - corpus_changed),
                     "epochs": TEACH_EPOCHS},
           "exam": exam}
    if pv is not None:                # never cache an exam without production answers
        with _impact_lock:
            _impact_cache[key] = out
    return copy.deepcopy(out)


# ------------------------------------------------------------------ preflight & failures

def vram_error(free_gib):
    return (f"Not enough GPU memory free ({free_gib:g} GiB free, {TEACH_MIN_FREE_GIB:g} GiB "
            "needed) — no audience traffic is lost; close other GPU jobs and retry Teach.")


def preflight_gpu_free():
    """Call AFTER free_own_memory(). None = may launch; else the 503 payload."""
    try:
        import torch
        if not torch.cuda.is_available():
            return {"error_kind": "out_of_gpu_memory",
                    "error": "No GPU is visible to the studio service — Teach needs the GPU "
                             f"(service is running with STUDIO_DEVICE={DEVICE}).",
                    "free_gib": None, "need_gib": TEACH_MIN_FREE_GIB}
        free, _total = torch.cuda.mem_get_info()
        free_gib = round(free / 2**30, 2)
        if free_gib < TEACH_MIN_FREE_GIB:
            return {"error_kind": "out_of_gpu_memory", "error": vram_error(free_gib),
                    "free_gib": free_gib, "need_gib": TEACH_MIN_FREE_GIB}
        return None
    except Exception:
        traceback.print_exc()
        return {"error_kind": "out_of_gpu_memory",
                "error": "Could not read free GPU memory — refusing to start Teach rather than "
                         "risk an out-of-memory failure.",
                "free_gib": None, "need_gib": TEACH_MIN_FREE_GIB}


def classify_failure(log_text):
    low = (log_text or "").lower()
    if "oom" in low or "outofmemoryerror" in low or "memory mapping failed" in low:
        return "out_of_gpu_memory"
    return "train_failed"


def _plain_train_error(kind, log_path):
    name = pathlib.Path(log_path).name if log_path else "train-<ts>.log"
    if kind == "out_of_gpu_memory":
        return (f"Not enough GPU memory free — the trainer needs about {TEACH_MIN_FREE_GIB:g} GiB. "
                f"No audience traffic is lost; close other GPU jobs and retry. Full log: {name}")
    return (f"Training failed — no audience traffic is lost; the full log is in "
            f"studio-runs/<domain>/{name}.")


# ------------------------------------------------------------------ job persistence

def _persist_job():
    with _lock:
        snap = {k: _job.get(k) for k in ("state", "domain", "policy", "started", "started_epoch",
                                         "ended_epoch", "pid", "error_kind", "error")}
    try:
        (OUT / "last_job.json").write_text(json.dumps(snap, indent=1))
    except Exception:
        traceback.print_exc()


def _write_pid(domain, pid):
    try:
        run_dir = OUT / domain
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "train.pid").write_text(f"{pid}\n")
    except Exception:
        traceback.print_exc()


def _unlink_pid(domain):
    try:
        (OUT / domain / "train.pid").unlink()
    except FileNotFoundError:
        pass
    except Exception:
        traceback.print_exc()


def _pid_cmdline(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().decode(errors="replace").replace("\x00", " ")
    except Exception:
        return ""


def kill_stale_train(domain):
    """Kill a leftover train_cli for `domain` — only after verifying its cmdline."""
    candidates = []
    try:
        candidates.append(int((OUT / domain / "train.pid").read_text().strip()))
    except Exception:
        pass
    with _lock:
        pid = _job.get("pid")
    if pid:
        candidates.append(pid)
    killed = False
    for pid in candidates:
        if not pid or pid <= 1:
            continue
        if "laya.train_cli" not in _pid_cmdline(pid):
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(20):
                time.sleep(0.25)
                try:
                    os.kill(pid, 0)
                except OSError:
                    break
            else:
                os.kill(pid, signal.SIGKILL)
            print(f"[studio] killed stale train_cli pid {pid} (domain {domain})", flush=True)
            killed = True
        except ProcessLookupError:
            pass
        except Exception:
            traceback.print_exc()
    _unlink_pid(domain)
    return killed


def recover_stale_job():
    """Startup: a previous studio process died mid-Teach — stop the orphan and say so."""
    for d in DOM:
        shutil.rmtree(OUT / d / "ft-ckpt.new", ignore_errors=True)
    try:
        prev = json.load(open(OUT / "last_job.json"))
    except Exception:
        return
    if prev.get("state") not in ("training", "evaluating"):
        return
    domain = prev.get("domain")
    killed = kill_stale_train(domain) if domain in DOM else False
    with _lock:
        _job.update(state="failed", domain=domain, policy=prev.get("policy"),
                    started=prev.get("started"), started_epoch=prev.get("started_epoch"),
                    ended_epoch=time.time(), pid=None, progress=None, error_kind="lost",
                    error=("The studio restarted during Teach; the training process was "
                           + ("stopped." if killed else "already gone.")
                           + " No audience traffic was lost — start Teach again."))
        _messages.clear()
        _msg("previous training job lost by a studio restart")
    _persist_job()
    print(f"[studio] recovered: previous Teach on {domain!r} reported as lost", flush=True)


def _token_check(header_value):
    """None when allowed, else (code, payload). compare_digest + 5-miss throttle."""
    if not TOKEN:
        return None
    now = time.time()
    with _lock:
        if now < _token_state["blocked_until"]:
            return 429, {"error_kind": "throttled", "error": "too many bad tokens — wait a minute"}
        if isinstance(header_value, str) and hmac.compare_digest(header_value, TOKEN):
            _token_state["misses"] = 0
            return None
        _token_state["misses"] += 1
        if _token_state["misses"] > TOKEN_MISSES_ALLOWED:
            return 429, {"error_kind": "throttled", "error": "too many bad tokens — wait a minute"}
        if _token_state["misses"] == TOKEN_MISSES_ALLOWED:
            _token_state["blocked_until"] = now + THROTTLE_S
            _token_state["misses"] = 0   # after the timeout lapses, five fresh tries
    print("[studio] token miss (studio/train)", flush=True)
    return 403, {"error_kind": "token", "error": "studio token required"}


def busy():
    with _lock:
        return _job["state"] in ("training", "evaluating")


# ------------------------------------------------------------------ the re-teach

def _fail(domain, kind, error, note):
    _msg(note)
    with _lock:
        _job.update(state="failed", ended_epoch=time.time(), pid=None, error_kind=kind, error=error)
    _persist_job()
    _unlink_pid(domain)
    shutil.rmtree(OUT / domain / "ft-ckpt.new", ignore_errors=True)


def train_worker(domain, pol, rows, corpus_changed):
    t_start = _job.get("started_epoch") or time.time()
    spec = DOM[domain]
    try:
        run_dir = OUT / domain
        run_dir.mkdir(parents=True, exist_ok=True)
        data_path = run_dir / "session.jsonl"
        with open(data_path, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        new_ckpt = run_dir / "ft-ckpt.new"
        shutil.rmtree(new_ckpt, ignore_errors=True)
        log_path = run_dir / f"train-{time.strftime('%Y%m%d-%H%M%S')}.log"
        cmd = [PY, "-m", "laya.train_cli", "--data", str(data_path),
               "--base", str(prod_ckpt(domain)), "--out", str(new_ckpt),
               "--loss", "soft-ce", "--shuffle-options",
               "--epochs", str(TEACH_EPOCHS), "--micro-batch", str(TEACH_MICRO_BATCH),
               "--grad-accum", str(TEACH_GRAD_ACCUM), "--device", DEVICE]
        if TEACH_MAX_LEN:
            cmd += ["--max-len", str(TEACH_MAX_LEN)]
        if TEACH_ENCODER_LR:
            cmd += ["--encoder-lr", TEACH_ENCODER_LR]
        if TEACH_HEAD_LR:
            cmd += ["--head-lr", TEACH_HEAD_LR]
        _msg(f"re-teaching your model on {len(rows)} relabeled rows ({DEVICE})")
        t0 = time.time()
        with open(log_path, "w") as logf:
            logf.write("# " + " ".join(cmd) + "\n")
            proc = subprocess.Popen(cmd, cwd=str(run_dir), stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True,
                                    env={**os.environ, "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"})
            with _lock:
                _job["pid"] = proc.pid
            _write_pid(domain, proc.pid)
            steps = max(1, math.ceil(len(rows) / TEACH_MICRO_BATCH))
            for line in proc.stdout:
                logf.write(f"[{time.time() - t0:7.1f}s] {line}")   # phase timing in the log
                logf.flush()
                line = line.strip()
                if not line:
                    continue
                m = _STEP_RE.match(line)
                if m:
                    epoch, epochs, step = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    with _lock:
                        _job["progress"] = {"epoch": epoch, "epochs": epochs,
                                            "step": step, "steps": steps}
                    continue
                m = _ITEMS_RE.match(line)
                if m:   # exact item count → exact step total
                    steps = max(1, math.ceil(int(m.group(1)) / TEACH_MICRO_BATCH))
                    with _lock:
                        _job["progress"] = {"epoch": 1, "epochs": TEACH_EPOCHS, "step": 0, "steps": steps}
                if _MEAN_RE.match(line) or m:
                    _msg(line)
        rc = proc.wait()
        train_s = round(time.time() - t0, 1)
        if rc != 0:
            kind = classify_failure(log_path.read_text(errors="replace"))
            _fail(domain, kind, _plain_train_error(kind, log_path),
                  f"training failed ({kind}) after {train_s}s — see {log_path.name}")
            return
        # The trainer also writes a per-epoch copy byte-identical to the final save; drop it.
        shutil.rmtree(new_ckpt / "checkpoint_latest", ignore_errors=True)
        with _lock:
            _job["state"] = "evaluating"
            _job["progress"] = None
        _persist_job()
        _msg(f"training done in {train_s}s; taking the exam")
        t_eval = time.time()
        shutil.rmtree(taught_ckpt(domain), ignore_errors=True)
        new_ckpt.rename(taught_ckpt(domain))
        (OUT / domain / "last-result.json").unlink(missing_ok=True)
        taught = laya.load(str(taught_ckpt(domain)), device=DEVICE)   # the exam needs only this one
        with _eng_lock:
            if _eng["domain"] != domain:
                _eng.update(domain=domain, prod=None, taught=None)
            _eng["taught"] = taught
        new_spec = apply_policy(spec, pol)
        exam = impact(domain, pol)["exam"]
        res = taught.predict_batch([e["state"] for e in exam], new_spec["questions"]["defs"],
                                   batch_size=16)
        for e, r in zip(exam, res):
            e["after"] = values(r.get("answers"))
        t_done = time.time()
        result = {
            "domain": domain, "policy": pol, "sentence": policy_sentence(spec, pol),
            "train_seconds": train_s, "train_rows": len(rows), "corpus_changed": corpus_changed,
            "exam": exam,
            "summary": {"zero": tally(exam, "zero"), "before": tally(exam, "before"),
                        "after": tally(exam, "after")},
            "config": {"changed_rows": TEACH_CHANGED_ROWS, "same_rows": TEACH_SAME_ROWS,
                       "epochs": TEACH_EPOCHS, "micro_batch": TEACH_MICRO_BATCH,
                       "grad_accum": TEACH_GRAD_ACCUM, "base": "prod-ckpt",
                       "log": log_path.name},
            "timing": {"prepare_s": round(t0 - t_start, 1), "train_s": train_s,
                       "evaluate_s": round(t_done - t_eval, 1),
                       "total_s": round(t_done - t_start, 1)},
            "finished": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        (OUT / domain / "last-result.json").write_text(json.dumps(result))
        with _lock:
            _job["result"] = result
            _job.update(state="done", ended_epoch=t_done, pid=None)
        _msg(f"done in {result['timing']['total_s']}s")
        _persist_job()
        _unlink_pid(domain)
        threading.Thread(target=engines, args=(domain,), daemon=True).start()   # prod back for compare
    except Exception:
        traceback.print_exc()
        _fail(domain, _job.get("error_kind") or "train_failed",
              _job.get("error") or "Teach hit an unexpected error — the studio log on the host has details.",
              "failed: unexpected error")


def status_snapshot():
    with _lock:
        started_epoch = _job["started_epoch"]
        elapsed = (round((_job["ended_epoch"] or time.time()) - started_epoch, 1)
                   if started_epoch else None)
        out = {"state": _job["state"], "domain": _job["domain"], "policy": _job["policy"],
               "sentence": _job["sentence"], "started": _job["started"],
               "started_epoch": started_epoch, "elapsed_s": elapsed,
               "progress": _job["progress"], "messages": list(_messages),
               "error_kind": _job["error_kind"], "error": _job["error"]}
        if _job.get("result"):
            out["result"] = _job["result"]
        return out


def _unknown_domain(domain):
    shown = domain if isinstance(domain, str) else type(domain).__name__
    return 404, {"error_kind": "unknown_domain", "error": f"unknown domain {shown[:40]!r}"}


class H(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urllib.parse.urlsplit(self.path).path
        if p in ("/health", "/studio/health"):
            with _lock:
                job_state = _job["state"]
            self._send(200, {"ok": True, "job": job_state, "token_required": bool(TOKEN),
                             "gpu": gpu_info(), "teach_min_free_gib": TEACH_MIN_FREE_GIB,
                             "resident": _eng["domain"], "warm": _warm_done.is_set(),
                             "prod_ready": {d: prod_ckpt(d).exists() for d in DOM}})
        elif p == "/studio/domains":
            self._send(200, {"domains": {k: {"stages": v["stages"],
                                             "noun_plural": v.get("noun_plural", "cases")}
                                         for k, v in DOM.items()}})
        elif p == "/studio/status":
            self._send(200, status_snapshot())
        else:
            self._send(404, {"error_kind": "not_found", "error": "no such route"})

    def _body(self):
        """Parsed JSON object, or None after sending the 400/413."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if n < 0:
            self.close_connection = True
            self._send(400, {"error_kind": "bad_json", "error": "invalid Content-Length"})
            return None
        if n > BODY_CAP:
            self.close_connection = True
            self._send(413, {"error_kind": "too_large", "error": "request body exceeds the 64 KB cap"})
            return None
        raw = self.rfile.read(n) if n else b""
        try:
            body = json.loads(raw or b"{}")
            if not isinstance(body, dict):
                raise ValueError("not an object")
        except (ValueError, UnicodeDecodeError):
            self._send(400, {"error_kind": "bad_json", "error": "request body is not a JSON object"})
            return None
        return body

    def _policy(self, domain, body):
        try:
            return normalize_policy(DOM[domain], body.get("policy"))
        except ValueError as e:
            self._send(400, {"error_kind": "bad_policy", "error": str(e)})
            return None

    def do_POST(self):
        p = urllib.parse.urlsplit(self.path).path
        body = self._body()
        if body is None:
            return
        domain = body.get("domain")
        if p not in ("/studio/session", "/studio/impact", "/studio/train", "/studio/compare"):
            self._send(404, {"error_kind": "not_found", "error": "no such route"})
            return
        if domain not in DOM:
            self._send(*_unknown_domain(domain))
            return

        if p == "/studio/session":
            if not _warm_done.is_set() and domain not in _prod_vals and prod_ckpt(domain).exists():
                self._send(503, {"error_kind": "warming_up",
                                 "error": "the studio is measuring your model after a restart — retry in a few seconds"})
                return
            self._send(200, session_payload(domain))
            if not busy():     # have both engines resident by the time the room tries a ticket
                threading.Thread(target=engines, args=(domain,), daemon=True).start()
            return

        if p == "/studio/impact":
            pol = self._policy(domain, body)
            if pol:
                self._send(200, impact(domain, pol))
            return

        if p == "/studio/train":
            bad = _token_check(self.headers.get("X-Studio-Token"))
            if bad:
                self._send(*bad)
                return
            pol = self._policy(domain, body)
            if not pol:
                return
            spec = DOM[domain]
            if policy_is_noop(spec, pol):
                self._send(400, {"error_kind": "noop",
                                 "error": "that is today's rule — change a value first"})
                return
            if not (prod_ckpt(domain) / "model.safetensors").exists():
                self._send(503, {"error_kind": "no_prod",
                                 "error": "no production model for this domain on this host (train_prod_ckpt.sh)"})
                return
            if not _warm_done.wait(20):
                self._send(503, {"error_kind": "warming_up",
                                 "error": "the studio is still warming up after a restart — retry in a few seconds"})
                return
            prod_values(domain)               # production answers cached before the GPU is lent out
            impact(domain, pol)               # exam rows with those answers
            rows, n_changed, _ = policy_training_rows(spec, data(domain)["train"], pol,
                                                      TEACH_CHANGED_ROWS, TEACH_SAME_ROWS)
            with _lock:                       # claim first: nothing reloads an engine from here on
                if _job["state"] in ("training", "evaluating"):
                    self._send(409, {"error_kind": "busy", "error": "a training job is already running"})
                    return
                prev = copy.deepcopy(_job)
                _job.update(state="training", domain=domain, policy=pol,
                            sentence=policy_sentence(spec, pol),
                            started=time.strftime("%H:%M:%S"), started_epoch=time.time(),
                            ended_epoch=None, pid=None, progress=None, error_kind=None, error=None)
                _job.pop("result", None)
            with _compare_sem:                # no inference mid-eviction
                free_own_memory()
            refuse = preflight_gpu_free()
            if refuse:
                with _lock:
                    _job.clear()
                    _job.update(prev)
                threading.Thread(target=engines, args=(domain,), daemon=True).start()
                self._send(503, refuse)
                return
            _messages.clear()
            _persist_job()
            threading.Thread(target=train_worker, args=(domain, pol, rows, n_changed),
                             daemon=True).start()
            self._send(200, {"started": True, "rows": len(rows), "corpus_changed": n_changed})
            return

        # /studio/compare — any ticket, both models, both rulebooks
        state = body.get("state")
        if not isinstance(state, str) or not state.strip():
            self._send(400, {"error_kind": "bad_request", "error": "state is required"})
            return
        if len(state) > STATE_CAP:
            self._send(400, {"error_kind": "bad_request", "error": f"state longer than {STATE_CAP} chars"})
            return
        if busy():
            self._send(409, {"error_kind": "busy", "error": "the model is being re-taught — try again when it finishes"})
            return
        if not _compare_sem.acquire(timeout=COMPARE_WAIT_S):
            self._send(503, {"error_kind": "busy", "error": "many people are asking at once — try again"})
            return
        try:
            if busy():
                self._send(409, {"error_kind": "busy", "error": "the model is being re-taught — try again when it finishes"})
                return
            spec = DOM[domain]
            prod, taught = engines(domain)
            if prod is None:
                self._send(404, {"error_kind": "no_prod", "error": "no production model for this domain on this host"})
                return
            lr = last_result(domain)
            out = {"policy": lr["policy"] if lr else None, "sentence": lr["sentence"] if lr else None,
                   "rules_old": rules_view(spec, state), "rules_new": None, "after": None}
            zero_box = {}
            zt = threading.Thread(target=lambda: zero_box.update(r=zero_answers(state, spec["questions"]["defs"])))
            zt.start()                        # the untrained model answers on the laya service meanwhile
            t = time.time()
            ans = prod.predict(state, spec["questions"]["defs"]).get("answers", {})
            out["before"] = {"answers": {q: {"v": answer_value(a), "c": answer_conf(a)} for q, a in ans.items()},
                             "ms": round(1000 * (time.time() - t))}
            if taught is not None and lr:
                new_spec = apply_policy(spec, lr["policy"])
                out["rules_new"] = rules_view(new_spec, state)
                t = time.time()
                ans = taught.predict(state, new_spec["questions"]["defs"]).get("answers", {})
                out["after"] = {"answers": {q: {"v": answer_value(a), "c": answer_conf(a)} for q, a in ans.items()},
                                "ms": round(1000 * (time.time() - t))}
            zt.join(ZERO_TIMEOUT_S + 1)
            out["zero"] = zero_box.get("r")
            self._send(200, out)
        except Exception:
            traceback.print_exc()
            self._send(500, {"error_kind": "internal", "error": "the model could not answer — try again"})
        finally:
            _compare_sem.release()


if __name__ == "__main__":
    host = os.environ.get("STUDIO_HOST", "127.0.0.1")
    recover_stale_job()
    if WARM_UP:
        threading.Thread(target=warm_up, daemon=True).start()
    else:
        _warm_done.set()
    print(f"[studio] serving on {host}:{PORT} "
          f"(token {'required' if TOKEN else 'OPEN — STUDIO_ALLOW_OPEN=1'}; device {DEVICE})",
          flush=True)
    ThreadingHTTPServer((host, PORT), H).serve_forever()
