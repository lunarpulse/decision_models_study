"""Teaching Studio service (Domain Builder): live fine-tuning of laya on a chosen domain.

Port 8903 (localhost by default). The demo console reaches it through the laya service's
/studio/* proxy, so one public origin serves everything and this service needs no CORS.
Mutating routes (/studio/train, /studio/drift) require the studio token (env STUDIO_TOKEN;
the presenter types it once in the console — it is never baked into the page); the service
refuses to start without one unless STUDIO_ALLOW_OPEN=1. Wrong tokens are compared with
hmac.compare_digest and throttled: five misses buy a 60 s timeout (429).

One training job at a time; the subprocess uses the IDENTICAL flag set as train_laya.sh
(soft-ce loss, shuffled options), TEACH_EPOCHS epochs (default 2) over TEACH_BG_ROWS
background rows (default 1500) plus the teach cases upsampled x20.

Memory discipline (the live OOM fix): before launching a run the studio evicts everything it
holds on the accelerator — all taught checkpoints and the zero-shot Router — then reads
torch.cuda.mem_get_info() and refuses (503) below TEACH_MIN_FREE_GIB (default 11.5 GiB).
laya's Router has no in-place device move, so "move the router to CPU during training" is
implemented as Router.unload() — which frees the checkpoint and its VRAM outright — and a
rebuild from the local cache after training; that is strictly less resident memory than a
CPU copy would be. Only ONE taught checkpoint is ever resident: /studio/predict and
/studio/drift lazy-load studio-runs/<domain>/ft-ckpt and loading one evicts the others.

Full train_cli output goes to studio-runs/<domain>/train-<YYYYmmdd-HHMMSS>.log; only parsed
progress ({epoch, epochs, step, steps}) and short human messages are kept in memory for
/studio/status. Failures are classified from the log (out_of_gpu_memory vs train_failed) and
reported as a plain sentence. The train PID persists in studio-runs/<domain>/train.pid and
the job state in studio-runs/last_job.json; on startup a leftover train_cli process is
killed — only after verifying its cmdline — and the interrupted job is reported as failed
with error_kind "lost", so the console can re-enable Teach immediately.

Session policy relabeling (deterministic): an edit on a teach case propagates to corpus rows
with the same rule profile (category, docs_ok, fresh-account, large-amount) — "all cases like
this are now decided this way" — plus the teach cases themselves repeated x20. Corpus rows
carry no meta, so every profile is parsed from the row's own state text
(domain_factory.parse_state); the old holdout-meta lookup keyed on state text never matched a
single train row, which is exactly the bug this replaces.
"""
import copy
import gc
import hmac
import json
import math
import os
import pathlib
import random
import re
import signal
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
from collections import deque
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
TEACH_EPOCHS = int(os.environ.get("TEACH_EPOCHS", "2"))
TEACH_MICRO_BATCH = int(os.environ.get("TEACH_MICRO_BATCH", "2"))
TEACH_GRAD_ACCUM = int(os.environ.get("TEACH_GRAD_ACCUM", "8"))
TEACH_BG_ROWS = int(os.environ.get("TEACH_BG_ROWS", "1500"))
_max_len = os.environ.get("TEACH_MAX_LEN", "").strip()
TEACH_MAX_LEN = int(_max_len) if _max_len else None   # unset = flag not passed
TEACH_MIN_FREE_GIB = float(os.environ.get("TEACH_MIN_FREE_GIB", "11.5"))
BODY_CAP = 64 * 1024
STATE_CAP = 4000
TOKEN_MISSES_ALLOWED = 5
THROTTLE_S = 60.0
WARM_UP = os.environ.get("STUDIO_WARMUP", "1").strip().lower() not in ("0", "false", "no", "off")

sys.path.insert(0, str(ROOT))
from domains import DOMAINS as DOM                                   # noqa: E402
from domain_factory import parse_state                               # noqa: E402

import laya                                                          # noqa: E402
from laya import Router                                              # noqa: E402

zero = Router(preload=True, device=DEVICE)
print(f"[studio] zero-shot Router loaded on {DEVICE} (for teach-case stratification)", flush=True)

_lock = threading.RLock()
_ft = {}                       # taught engines; at most ONE resident (see get_engine)
_ft_lock = threading.Lock()
_resident = {"domain": None}   # which taught checkpoint is loaded right now
_messages = deque(maxlen=20)
_job = {"state": "idle", "domain": None, "started": None, "started_epoch": None,
        "ended_epoch": None, "pid": None, "progress": None,
        "error_kind": None, "error": None}          # "result" added when a run finishes
_token_state = {"misses": 0, "blocked_until": 0.0}

_STEP_RE = re.compile(r"epoch (\d+)/(\d+) step (\d+)")
_MEAN_RE = re.compile(r"epoch (\d+)/(\d+) mean loss")
_ITEMS_RE = re.compile(r"train items (\d+)")


def _msg(text):
    _messages.append(text[:200])


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


def free_own_memory():
    """Evict everything the studio itself holds on the accelerator (plan 0.3).

    The Router cannot move a resident checkpoint to CPU in place, and unload() beats a CPU
    copy anyway: it frees the weights and their VRAM (it runs gc + empty_cache itself) and
    the next predict rebuilds the checkpoint from the local HF cache."""
    with _ft_lock:
        _ft.clear()
        _resident["domain"] = None
    try:
        zero.unload()
    except Exception:
        traceback.print_exc()
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def restore_router_async():
    threading.Thread(target=_restore_router, daemon=True).start()


def _restore_router():
    """Bring the zero-shot checkpoints back after a train (rebuild from the local cache)."""
    try:
        zero.preload()
        _msg("zero-shot engine back in memory")
    except Exception:
        traceback.print_exc()


def get_engine(domain):
    """The taught engine for `domain`, lazy-loaded from studio-runs/<domain>/ft-ckpt.

    Only one taught checkpoint stays resident: loading one drops the others (plan 0.3)."""
    eng = _ft.get(domain)
    if eng is not None:
        return eng
    ckpt = OUT / domain / "ft-ckpt"
    if not ckpt.exists():
        return None
    with _ft_lock:
        eng = _ft.get(domain)
        if eng is not None:
            return eng
        eng = laya.load(str(ckpt), device=DEVICE)
        _ft.clear()
        _ft[domain] = eng
        _resident["domain"] = domain
        return eng


def busy():
    with _lock:
        return _job["state"] in ("training", "evaluating")


def stratified_cases(domain, n=12, err_n=6):
    """Teach cases: `err_n` where the zero-shot engine errs on >=1 question, rest random.

    Deterministic: fixed holdout order, Random(7) shuffles, one batched pass. cached_cases()
    computes this once per domain and deep-copies from then on."""
    spec = DOM[domain]
    rows = [json.loads(l) for l in open(DATA / domain / "holdout_eval.jsonl")]
    reqs = [{"state": r["state"], "questions": spec["questions"]["defs"]} for r in rows]
    answers = [d.get("answers", {}) for d in zero.predict_batch(reqs, batch_size=16)]
    rng = random.Random(7)
    errs, oks = [], []
    for r, res in zip(rows, answers):
        wrong = 0
        for qid, g in r["gold"].items():
            a = res.get(qid, {})
            v = a.get("choice", a.get("score"))
            if a.get("type") == "noul":
                v = int(a.get("noul", 0) > 0.5)
            elif a.get("type") == "score" and v is not None:
                v = int(round(float(v)))
            gv = g if not isinstance(g, bool) else int(g)
            wrong += (v != gv)
        (errs if wrong else oks).append(r)
    rng.shuffle(errs); rng.shuffle(oks)
    cases = errs[:err_n] + oks[: n - err_n]
    for r in errs[err_n:]:          # fill up if too few all-correct rows
        if len(cases) >= n:
            break
        cases.append(r)
    rng.shuffle(cases)
    try:
        import torch
        torch.cuda.empty_cache()    # free the stratification pass before any training subprocess
    except Exception:
        pass
    return [{"id": r["id"], "state": r["state"], "gold": r["gold"], "meta": r["meta"]} for r in cases]


_cases = {}                        # domain -> pristine teach-case list
_cases_lock = threading.Lock()


def cached_cases(domain):
    """stratified_cases per domain, computed once (deterministic), deep-copied per call (0.5).

    Concurrent first callers share one computation; nobody re-runs the zero-shot pass."""
    with _cases_lock:
        got = _cases.get(domain)
    if got is not None:
        return copy.deepcopy(got)
    with _cases_lock:
        got = _cases.get(domain)
        if got is None:
            got = _cases[domain] = stratified_cases(domain)
    return copy.deepcopy(got)


def warm_up():
    """Optional background warm-up: precompute teach cases so the first card opens fast."""
    for domain in DOM:
        try:
            cached_cases(domain)
            print(f"[studio] warmed teach cases for {domain}", flush=True)
        except Exception:
            traceback.print_exc()


def state_profile(spec, state):
    """Rule profile of a raw state: (category, docs_ok, fresh account, large amount).

    Parsed from the text itself (domain_factory.parse_state) so train rows — which carry no
    meta — and holdout rows land in the same key space (fixes plan 1.4)."""
    p = parse_state(spec, state)
    start = p.get("start")
    fresh = bool(start) and (spec["signals"]["today"] - start).days <= spec["signals"]["fresh_days"]
    return (p.get("cat"), bool(p.get("docs_ok")), bool(fresh),
            p.get("amount", 0) >= spec["signals"]["large_amount"])


def profile_label(prof):
    cat, docs_ok, fresh, large = prof
    return (f"{cat or 'unparsed'} · docs {'attached' if docs_ok else 'missing'} · "
            f"{'fresh' if fresh else 'aged'} account · {'large' if large else 'normal'} amount")


def _coerce(to, like):
    """Keep the gold value's type when applying an edit (bool stays bool)."""
    return (to in ("yes", "True", True)) if isinstance(like, bool) else to


def build_training_set(domain, cases, edits, n_rows=None, upsample=20):
    """Corpus rows relabeled under the session policy + teach cases (with edits) x N.

    Returns (rows, relabeled_rows, edited_profiles). Each corpus row's profile is parsed from
    its own state text; a row is relabeled when an edited teach case shares that profile, and
    relabeled_rows counts the corpus rows that actually changed (plan 1.4)."""
    spec = DOM[domain]
    rng = random.Random(11)
    n_rows = n_rows or TEACH_BG_ROWS
    train = [json.loads(l) for l in open(DATA / domain / "train.jsonl")]
    edit_map = {(e["case_id"], e["qid"]): e["to"] for e in edits}

    edited_profiles = {}
    for c in cases:
        for (cid, qid), to in edit_map.items():
            if cid == c["id"]:
                edited_profiles.setdefault(state_profile(spec, c["state"]), {})[qid] = to

    out_rows, relabeled = [], 0
    cand = rng.sample(train, min(n_rows, len(train)))
    for t in cand:
        exp = dict(t["expected"])
        if edited_profiles and state_profile(spec, t["state"]) in edited_profiles:
            touched = False
            for qid, to in edited_profiles[state_profile(spec, t["state"])].items():
                if exp.get(qid) != to:
                    exp[qid] = _coerce(to, exp.get(qid))
                    touched = True
            relabeled += touched
        out_rows.append({"state": t["state"], "questions": t["questions"], "expected": exp})

    for c in cases:
        exp = dict(c["gold"])
        for (cid, qid), to in edit_map.items():
            if cid == c["id"]:
                exp[qid] = _coerce(to, exp.get(qid))
        for _ in range(upsample):
            out_rows.append({"state": c["state"], "questions": spec["questions"]["defs"], "expected": exp})
    return out_rows, relabeled, edited_profiles


def fresh_holdout(domain, cases, edited_profiles):
    """The headline sample: the first 30 holdout rows EXCLUDING the teach-case ids (plan 1.5).

    Rows whose rule profile was edited stay in the sample but are scored against the EDITED
    gold, not the original. That is the honest choice, deliberately: scoring the original gold
    would fail the model for exactly the policy change the session taught, while excluding the
    rows would hide whether the edit propagated to unseen same-profile states. The relabeling
    is disclosed to the user via result.edited_profiles."""
    spec = DOM[domain]
    teach_ids = {c["id"] for c in cases}
    out = []
    for r in (json.loads(l) for l in open(DATA / domain / "holdout_eval.jsonl")):
        if r["id"] in teach_ids:
            continue
        gold = dict(r["gold"])
        prof = state_profile(spec, r["state"])
        if prof in edited_profiles:
            for qid, to in edited_profiles[prof].items():
                gold[qid] = _coerce(to, gold.get(qid))
        out.append({"id": r["id"], "state": r["state"], "gold": gold})
        if len(out) >= 30:
            break
    return out


def apply_edits(cases, edits):
    """Fold the session's edits into the teach cases' gold (what the model was taught)."""
    for c in cases:
        for e in edits:
            if e["case_id"] == c["id"]:
                c["gold"][e["qid"]] = _coerce(e["to"], c["gold"].get(e["qid"]))


def run_eval(domain, eng, cases):
    spec = DOM[domain]
    results = []
    for c in cases:
        res = eng.predict(c["state"], spec["questions"]["defs"]).get("answers", {})
        row = {"id": c.get("id", "?"), "label": c.get("label", ""), "questions": {}}
        ok_all = True
        for qid, g in c["gold"].items():
            a = res.get(qid, {})
            v = a.get("choice", a.get("score"))
            if a.get("type") == "noul":
                v = int(a.get("noul", 0) > 0.5)
            elif a.get("type") == "score" and v is not None:
                v = int(round(float(v)))
            gv = g if not isinstance(g, bool) else int(g)
            ok = v == gv
            ok_all &= ok
            row["questions"][qid] = {"pred": v if not isinstance(v, float) else round(v, 2),
                                     "gold": gv, "ok": ok,
                                     "prob": round(float(a.get("probabilities", {}).get(
                                         str(g if not isinstance(g, bool) else int(g)), 0) or 0), 3)}
        row["ok_all"] = ok_all
        results.append(row)
    return results


def lite_portfolio(pkg):
    """Lite portfolio: the same JSON minus the `probabilities` key in every answer dict."""
    pkg = copy.deepcopy(pkg)
    for claim in pkg.get("claims", []):
        for arm in (claim.get("arms") or {}).values():
            for a in (arm.get("answers") or {}).values():
                a.pop("probabilities", None)
    return pkg


def vram_error(free_gib):
    return (f"Not enough GPU memory free ({free_gib:g} GiB free, {TEACH_MIN_FREE_GIB:g} GiB "
            "needed) — no audience traffic is lost; close other GPU jobs and retry Teach.")


def preflight_gpu_free():
    """Plan 0.2 — call AFTER free_own_memory(). None = may launch; else the 503 payload."""
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


# --------------------------------------------------------------- job persistence (0.9)

def _persist_job():
    with _lock:
        snap = {k: _job.get(k) for k in ("state", "domain", "started", "started_epoch",
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
    """Kill a leftover train_cli for `domain` — only after verifying its cmdline (plan 0.9)."""
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
    """Startup: a previous studio process died mid-Teach — stop the orphan and say so (0.9)."""
    try:
        prev = json.load(open(OUT / "last_job.json"))
    except Exception:
        return
    if prev.get("state") not in ("training", "evaluating"):
        return
    domain = prev.get("domain")
    if domain and domain in DOM:
        killed = kill_stale_train(domain)
    else:
        killed = False
    with _lock:
        _job.update(state="failed", domain=domain, started=prev.get("started"),
                    started_epoch=prev.get("started_epoch"), ended_epoch=time.time(),
                    pid=None, progress=None, error_kind="lost",
                    error=("The studio restarted during Teach; the training process was "
                           + ("stopped." if killed else "already gone.")
                           + " No audience traffic was lost — start Teach again."))
        _messages.clear()
        _msg("previous training job lost by a studio restart")
    _persist_job()
    print(f"[studio] recovered: previous Teach on {domain!r} reported as lost", flush=True)


def _token_check(header_value):
    """None when allowed, else (code, payload). compare_digest + 5-miss throttle (plan 4.5)."""
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
    print("[studio] token miss (studio_train/drift)", flush=True)
    return 403, {"error_kind": "token", "error": "studio token required"}


def train_worker(domain, rows, edits, relabeled_rows, edited_profiles):
    try:
        run_dir = OUT / domain
        run_dir.mkdir(parents=True, exist_ok=True)
        data_path = run_dir / "session.jsonl"
        with open(data_path, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        ckpt = run_dir / "ft-ckpt"
        log_path = run_dir / f"train-{time.strftime('%Y%m%d-%H%M%S')}.log"
        cmd = [PY, "-m", "laya.train_cli", "--data", str(data_path),
               "--base", "convaiinnovations/laya", "--out", str(ckpt),
               "--loss", "soft-ce", "--shuffle-options",
               "--epochs", str(TEACH_EPOCHS), "--micro-batch", str(TEACH_MICRO_BATCH),
               "--grad-accum", str(TEACH_GRAD_ACCUM), "--device", DEVICE]
        if TEACH_MAX_LEN:
            cmd += ["--max-len", str(TEACH_MAX_LEN)]
        _msg(f"training subprocess started on {DEVICE}")
        t0 = time.time()
        with open(log_path, "w") as logf:
            proc = subprocess.Popen(cmd, cwd=str(run_dir), stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True,
                                    env={**os.environ, "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"})
            with _lock:
                _job["pid"] = proc.pid
            _write_pid(domain, proc.pid)
            steps = max(1, math.ceil(len(rows) / TEACH_MICRO_BATCH))
            for line in proc.stdout:
                logf.write(line)
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
                if _MEAN_RE.match(line) or m:
                    _msg(line)
        rc = proc.wait()
        train_s = round(time.time() - t0, 1)
        if rc != 0:
            kind = classify_failure(log_path.read_text(errors="replace"))
            _msg(f"training failed ({kind}) after {train_s}s — see {log_path.name}")
            with _lock:
                _job.update(state="failed", ended_epoch=time.time(), pid=None, error_kind=kind,
                            error=_plain_train_error(kind, log_path))
            _persist_job()
            _unlink_pid(domain)
            return
        _msg(f"training done in {train_s}s; loading studio checkpoint")
        with _lock:
            _job["state"] = "evaluating"
            _job["progress"] = None
        _persist_job()
        _restore_router()                     # zero-shot back before "before" scores
        eng = laya.load(str(ckpt), device=DEVICE)
        with _ft_lock:
            _ft.clear()
            _ft[domain] = eng
            _resident["domain"] = domain
        _msg("checkpoint loaded; evaluating")
        cases = cached_cases(domain)
        apply_edits(cases, edits)
        before = run_eval(domain, zero, cases)
        after = run_eval(domain, eng, cases)
        fresh = fresh_holdout(domain, cases, edited_profiles)
        probes = json.load(open(DATA / domain / "demo_presets.json")).get("paraphrase_probes", [])
        result = {
            "train_seconds": train_s, "train_rows": len(rows),
            "relabeled_rows": relabeled_rows,
            "edited_profiles": [{"profile": profile_label(p), "questions": sorted(qs)}
                                for p, qs in edited_profiles.items()],
            "before": before, "after": after,
            "fresh_holdout": fresh,
            "paraphrase_probes": run_eval(domain, eng, probes),
        }
        with _lock:
            _job["result"] = result
            _job.update(state="done", ended_epoch=time.time(), pid=None)
        _msg("done")
        _persist_job()
        _unlink_pid(domain)
    except Exception:
        traceback.print_exc()
        with _lock:
            _job.update(state="failed", ended_epoch=time.time(), pid=None,
                        error_kind=_job.get("error_kind") or "train_failed",
                        error=_job.get("error") or
                        "Teach hit an unexpected error — the studio log on the host has details.")
        _msg("failed: unexpected error")
        _persist_job()
        _unlink_pid(domain)


def status_snapshot():
    with _lock:
        started_epoch = _job["started_epoch"]
        elapsed = (round((_job["ended_epoch"] or time.time()) - started_epoch, 1)
                   if started_epoch else None)
        out = {"state": _job["state"], "domain": _job["domain"], "started": _job["started"],
               "started_epoch": started_epoch, "elapsed_s": elapsed,
               "progress": _job["progress"], "messages": list(_messages),
               "error_kind": _job["error_kind"], "error": _job["error"]}
        if _job.get("result"):
            out["result"] = _job["result"]
        return out


def _unknown_domain(domain):
    shown = domain if isinstance(domain, str) else type(domain).__name__
    return 404, {"error_kind": "unknown_domain",
                 "error": f"unknown domain {shown[:40]!r}"}


class H(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        p, qs = u.path, dict(urllib.parse.parse_qsl(u.query))
        if p in ("/health", "/studio/health"):
            with _lock:
                job_state = _job["state"]
            self._send(200, {"ok": True, "job": job_state, "token_required": bool(TOKEN),
                             "gpu": gpu_info(), "teach_min_free_gib": TEACH_MIN_FREE_GIB,
                             "resident_ckpt": _resident["domain"]})
        elif p == "/studio/domains":
            self._send(200, {"domains": {k: {"stages": v["stages"]} for k, v in DOM.items()}})
        elif p == "/studio/status":
            self._send(200, status_snapshot())
        elif p == "/studio/presets":
            domain = qs.get("domain")
            if domain not in DOM:
                self._send(*_unknown_domain(domain))
                return
            try:
                self._send(200, json.load(open(DATA / domain / "demo_presets.json")))
            except FileNotFoundError:
                self._send(404, {"error_kind": "no_presets",
                                 "error": "no presets file for this domain yet"})
        elif p == "/studio/portfolio":
            domain = qs.get("domain")
            if domain not in DOM:
                self._send(*_unknown_domain(domain))
                return
            try:
                pkg = json.load(open(DATA / domain / "portfolio_results.json"))
            except FileNotFoundError:
                self._send(404, {"error_kind": "no_portfolio",
                                 "error": "no portfolio for this domain yet"})
                return
            if qs.get("lite") in ("1", "true"):
                pkg = lite_portfolio(pkg)
            self._send(200, pkg)
        else:
            self._send(404, {"error_kind": "not_found", "error": "no such route"})

    def do_POST(self):
        u = urllib.parse.urlsplit(self.path)
        p, qs = u.path, dict(urllib.parse.parse_qsl(u.query))
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if n < 0:
            self.close_connection = True
            self._send(400, {"error_kind": "bad_json", "error": "invalid Content-Length"})
            return
        if n > BODY_CAP:
            self.close_connection = True
            self._send(413, {"error_kind": "too_large",
                             "error": "request body exceeds the 64 KB cap"})
            return
        raw = self.rfile.read(n) if n else b""
        try:
            body = json.loads(raw or b"{}")
            if not isinstance(body, dict):
                raise ValueError("not an object")
        except (ValueError, UnicodeDecodeError):
            self._send(400, {"error_kind": "bad_json",
                             "error": "request body is not a JSON object"})
            return

        if p == "/studio/session":
            domain = body.get("domain")
            if domain not in DOM:
                self._send(*_unknown_domain(domain))
                return
            if busy():
                self._send(409, {"error_kind": "busy",
                                 "error": "teach is running — the studio pauses other GPU work"})
                return
            cases = cached_cases(domain)
            self._send(200, {"cases": cases,
                             "questions": DOM[domain]["questions"]["defs"]})
            return

        if p == "/studio/train":
            domain = body.get("domain")
            if domain not in DOM:
                self._send(*_unknown_domain(domain))
                return
            bad = _token_check(self.headers.get("X-Studio-Token"))
            if bad:
                self._send(*bad)
                return
            cases = body.get("cases")
            if (not isinstance(cases, list) or not cases
                    or not all(isinstance(c, dict) and {"id", "state", "gold"} <= set(c)
                               for c in cases)):
                self._send(400, {"error_kind": "bad_request",
                                 "error": "cases must be the teach cases from /studio/session"})
                return
            edits = body.get("edits", [])
            if not isinstance(edits, list) or not all(
                    isinstance(e, dict) and {"case_id", "qid", "to"} <= set(e) for e in edits):
                self._send(400, {"error_kind": "bad_request",
                                 "error": "edits must be {case_id, qid, to} objects"})
                return
            rows, relabeled, edited_profiles = build_training_set(domain, cases, edits)
            free_own_memory()                 # plan 0.3: evict before measuring (0.2)
            refuse = preflight_gpu_free()
            if refuse:
                restore_router_async()        # keep the console's zero-shot cards warm
                self._send(503, refuse)
                return
            with _lock:
                if _job["state"] in ("training", "evaluating"):
                    self._send(409, {"error_kind": "busy",
                                     "error": "a training job is already running"})
                    return
                _job.update(state="training", domain=domain,
                            started=time.strftime("%H:%M:%S"), started_epoch=time.time(),
                            ended_epoch=None, pid=None, progress=None,
                            error_kind=None, error=None)
                _job.pop("result", None)
                _messages.clear()
            threading.Thread(target=train_worker,
                             args=(domain, rows, edits, relabeled, edited_profiles),
                             daemon=True).start()
            self._send(200, {"started": True, "rows": len(rows), "relabeled_rows": relabeled})
            return

        if p == "/studio/predict":
            domain = body.get("domain")
            if domain not in DOM:
                self._send(*_unknown_domain(domain))
                return
            if busy():
                self._send(409, {"error_kind": "busy",
                                 "error": "teach is running — try again when it finishes"})
                return
            eng = get_engine(domain)
            if not eng:
                self._send(404, {"error_kind": "no_ckpt",
                                 "error": "no studio checkpoint for this domain yet"})
                return
            state = body.get("state")
            if not isinstance(state, str) or not state:
                self._send(400, {"error_kind": "bad_request", "error": "state is required"})
                return
            if len(state) > STATE_CAP:
                self._send(400, {"error_kind": "bad_request",
                                 "error": f"state longer than {STATE_CAP} chars"})
                return
            spec = DOM[domain]
            res = eng.predict(state, spec["questions"]["defs"]).get("answers", {})
            out = {}
            for qid, a in res.items():
                d = {"type": a.get("type")}
                for k in ("choice", "score", "noul"):
                    if k in a:
                        d[k] = a[k]
                if isinstance(a.get("probabilities"), dict):
                    d["probabilities"] = {str(k): round(float(v), 4)
                                          for k, v in a["probabilities"].items()}
                out[qid] = d
            self._send(200, {"answers": out})
            return

        if p == "/studio/drift":
            # "A year later": the policy changed (deductibles doubled). Measured decay of the
            # taught engine on 30 fresh rows from the drifted spec, versus the zero-shot base.
            domain = body.get("domain")
            if domain not in DOM:
                self._send(*_unknown_domain(domain))
                return
            bad = _token_check(self.headers.get("X-Studio-Token"))
            if bad:
                self._send(*bad)
                return
            if busy():
                self._send(409, {"error_kind": "busy",
                                 "error": "teach is running — try again when it finishes"})
                return
            eng = get_engine(domain)
            if not eng:
                self._send(404, {"error_kind": "no_ckpt",
                                 "error": "no studio checkpoint for this domain yet"})
                return
            spec = DOM[domain]
            from domain_factory import make_row
            drifted = copy.deepcopy(spec)
            drifted["deductibles"] = {k: 2 * v for k, v in spec["deductibles"].items()}
            rng = random.Random(4242)
            rows = [make_row(drifted, rng, 700000 + i) for i in range(30)]
            cases = [{"id": r["id"], "state": r["state"], "gold": r["gold"]} for r in rows]
            self._send(200, {"drift": "deductibles doubled",
                             "taught": run_eval(domain, eng, cases),
                             "zero": run_eval(domain, zero, cases)})
            return

        self._send(404, {"error_kind": "not_found", "error": "no such route"})


if __name__ == "__main__":
    host = os.environ.get("STUDIO_HOST", "127.0.0.1")
    recover_stale_job()
    if WARM_UP:
        threading.Thread(target=warm_up, daemon=True).start()
    print(f"[studio] serving on {host}:{PORT} "
          f"(token {'required' if TOKEN else 'OPEN — STUDIO_ALLOW_OPEN=1'}; device {DEVICE})",
          flush=True)
    ThreadingHTTPServer((host, PORT), H).serve_forever()
