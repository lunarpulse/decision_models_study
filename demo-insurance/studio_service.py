"""Teaching Studio service (Domain Builder): live fine-tuning of laya on a chosen domain.

Port 8903 (localhost by default). The demo console reaches it through the laya service's
/studio/* proxy so one public origin serves everything. Mutating routes require the studio
token (env STUDIO_TOKEN; the presenter types it once in the console — it is never baked into
the page). One training job at a time; the subprocess uses the IDENTICAL flag set as
train_laya.sh (soft-ce loss, shuffled options), 1 epoch on ~1.7k rows.

Session policy relabeling (deterministic): an edit on a teach case propagates to corpus rows
with the same rule profile (category, docs_ok, fresh-account, large-amount) — "all cases like
this are now decided this way" — plus the 12 teach cases themselves repeated x20.
"""
import sys
import json, os, pathlib, random, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(os.environ.get("DEMO_ROOT", pathlib.Path(__file__).resolve().parent))
DATA = ROOT / "data"
OUT = ROOT / "studio-runs"
OUT.mkdir(exist_ok=True)
TOKEN = os.environ.get("STUDIO_TOKEN", "")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8903
PY = os.environ.get("STUDIO_PY", str(ROOT.parent / ".venv-laya" / "bin" / "python"))

import laya
from laya import Router

zero = Router(preload=True)
print("[studio] zero-shot Router loaded (for teach-case stratification)", flush=True)

_job = {"state": "idle", "domain": None, "started": None, "progress": [], "error": None}
_lock = threading.Lock()
_ft = {}          # domain -> laya engine (studio checkpoints)


def load_domains():
    import sys as _s
    _s.path.insert(0, str(ROOT))
    from domains import DOMAINS
    return DOMAINS


DOM = load_domains()


def stratified_cases(domain, n=12, err_n=6):
    """Teach cases: `err_n` where the zero-shot engine errs on >=1 question, rest random."""
    spec = DOM[domain]
    rows = [json.loads(l) for l in open(DATA / domain / "holdout_eval.jsonl")]
    rng = random.Random(7)
    errs, oks = [], []
    for r in rows:
        res = zero.predict(r["state"], spec["questions"]["defs"]).get("answers", {})
        wrong = 0
        for qid, g in r["gold"].items():
            a = res.get(qid, {})
            v = a.get("choice", a.get("score"))
            if a.get("type") == "noul":
                v = int(a.get("noul", 0) > 0.5)
            gv = g if not isinstance(g, bool) else int(g)
            wrong += (v != gv)
        (errs if wrong else oks).append(r)
    rng.shuffle(errs); rng.shuffle(oks)
    cases = errs[:err_n] + oks[: n - err_n]
    rng.shuffle(cases)
    return [{"id": r["id"], "state": r["state"], "gold": r["gold"], "meta": r["meta"]} for r in cases]


def profile(meta):
    return (meta.get("cat"), bool(meta.get("docs_ok")),
            meta.get("age_days", meta.get("policy_days", 999)) <= 30,
            meta.get("amount", 0) >= 18500)


def build_training_set(domain, cases, edits, n_rows=1500, upsample=20):
    """Corpus rows relabeled under the session policy + teach cases (with edits) x N."""
    spec = DOM[domain]
    rng = random.Random(11)
    train = [json.loads(l) for l in open(DATA / domain / "train.jsonl")]
    hold = {c["id"] for c in cases}
    raw = [json.loads(l) for l in open(DATA / domain / "holdout_eval.jsonl")]
    meta_by_state = {r["state"]: r["meta"] for r in raw}
    by_id = {r["id"]: r for r in raw}

    edit_map = {(e["case_id"], e["qid"]): e["to"] for e in edits}
    edited_profiles = {}
    for e in edits:
        r = by_id.get(e["case_id"])
        if r:
            edited_profiles.setdefault(profile(r["meta"]), {})[e["qid"]] = e["to"]

    # relabel corpus rows whose profile matches an edited profile
    out_rows = []
    cand = rng.sample(train, min(n_rows, len(train)))
    for t in cand:
        m = meta_by_state.get(t["state"])
        exp = dict(t["expected"])
        if m and profile(m) in edited_profiles:
            for qid, to in edited_profiles[profile(m)].items():
                exp[qid] = to
        out_rows.append({"state": t["state"], "questions": t["questions"], "expected": exp})

    for c in cases:
        exp = dict(c["gold"])
        for (cid, qid), to in edit_map.items():
            if cid == c["id"]:
                exp[qid] = to
        for _ in range(upsample):
            out_rows.append({"state": c["state"], "questions": spec["questions"]["defs"], "expected": exp})
    return out_rows


def run_eval(domain, eng, cases, probes):
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


def train_worker(domain, rows):
    global _ft
    try:
        run_dir = OUT / domain
        run_dir.mkdir(exist_ok=True)
        data_path = run_dir / "session.jsonl"
        with open(data_path, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        ckpt = run_dir / "ft-ckpt"
        _job["progress"].append("training subprocess started")
        t0 = time.time()
        cmd = [PY, "-m", "laya.train_cli", "--data", str(data_path),
               "--base", "convaiinnovations/laya", "--out", str(ckpt),
               "--loss", "soft-ce", "--shuffle-options", "--epochs", "1", "--device", "cuda"]
        proc = subprocess.Popen(cmd, cwd=str(run_dir), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            line = line.strip()
            if line:
                _job["progress"].append(line[-200:])
        rc = proc.wait()
        train_s = round(time.time() - t0, 1)
        if rc != 0:
            _job.update(state="failed", error=f"train_cli exit {rc}")
            return
        _job["progress"].append(f"training done in {train_s}s; loading studio checkpoint")
        eng = laya.load(str(ckpt))
        _ft[domain] = eng
        _job["progress"].append("checkpoint loaded; evaluating")
        cases = stratified_cases(domain)
        fresh = [{"id": r["id"], "state": r["state"], "gold": r["gold"]}
                 for r in (json.loads(l) for l in open(DATA / domain / "holdout_eval.jsonl"))][:30]
        probes = json.load(open(DATA / domain / "demo_presets.json")).get("paraphrase_probes", [])
        _job["result"] = {
            "train_seconds": train_s, "train_rows": len(rows),
            "before": run_eval(domain, zero, cases, probes),
            "after": run_eval(domain, eng, cases, probes),
            "fresh_holdout": run_eval(domain, eng, fresh, probes),
            "paraphrase_probes": run_eval(domain, eng, probes, probes),
        }
        _job["state"] = "done"
    except Exception as e:
        _job.update(state="failed", error=repr(e)[:300])


class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Studio-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code); self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        import urllib.parse as up
        u = up.urlsplit(self.path)
        p, qs = u.path, dict(up.parse_qsl(u.query))
        if p == "/health":
            self._send(200, {"ok": True, "job": _job["state"], "token_required": bool(TOKEN)})
        elif p == "/studio/domains":
            self._send(200, {"domains": {k: {"stages": v["stages"]} for k, v in DOM.items()}})
        elif p == "/studio/status":
            self._send(200, {k: _job[k] for k in ("state", "domain", "started", "progress", "error")}
                       | ({"result": _job["result"]} if _job.get("result") else {}))
        elif p == "/studio/presets":
            try:
                pkg = json.load(open(DATA / qs["domain"] / "demo_presets.json"))
                self._send(200, pkg)
            except (KeyError, FileNotFoundError):
                self._send(404, {"error": "unknown domain"})
        elif p == "/studio/portfolio":
            try:
                pkg = json.load(open(DATA / qs["domain"] / "portfolio_results.json"))
                self._send(200, pkg)
            except (KeyError, FileNotFoundError):
                self._send(404, {"error": "no portfolio for this domain yet"})
        else:
            self.send_response(404); self._cors(); self.end_headers()

    def do_POST(self):
        global _job
        p = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if p == "/studio/session":
            try:
                cases = stratified_cases(body["domain"])
                self._send(200, {"cases": cases,
                                 "questions": DOM[body["domain"]]["questions"]["defs"]})
            except KeyError:
                self._send(404, {"error": "unknown domain"})
            return
        if p == "/studio/train":
            if TOKEN and self.headers.get("X-Studio-Token") != TOKEN:
                self._send(403, {"error": "studio token required"})
                return
            with _lock:
                if _job["state"] == "training":
                    self._send(409, {"error": "a training job is already running"})
                    return
                rows = build_training_set(body["domain"], body["cases"], body.get("edits", []))
                _job = {"state": "training", "domain": body["domain"],
                        "started": time.strftime("%H:%M:%S"), "progress": [], "error": None}
            threading.Thread(target=train_worker, args=(body["domain"], rows), daemon=True).start()
            self._send(200, {"started": True, "rows": len(rows)})
            return
        if p == "/studio/predict":
            eng = _ft.get(body["domain"])
            if not eng:
                self._send(404, {"error": "no studio checkpoint for this domain yet"})
                return
            spec = DOM[body["domain"]]
            res = eng.predict(body["state"], spec["questions"]["defs"]).get("answers", {})
            out = {}
            for qid, a in res.items():
                d = {"type": a.get("type")}
                for k in ("choice", "score", "noul"):
                    if k in a: d[k] = a[k]
                if isinstance(a.get("probabilities"), dict):
                    d["probabilities"] = {str(k): round(float(v), 4) for k, v in a["probabilities"].items()}
                out[qid] = d
            self._send(200, {"answers": out})
            return
        if p == "/studio/drift":
            # "A year later": the policy changed (deductibles doubled). Measured decay of the
            # taught engine on 30 fresh rows from the drifted spec, versus the zero-shot base.
            domain = body["domain"]
            spec = DOM[domain]
            eng = _ft.get(domain)
            if not eng:
                self._send(404, {"error": "no studio checkpoint for this domain yet"})
                return
            import copy, random as _r
            from domain_factory import make_row
            drifted = copy.deepcopy(spec)
            drifted["deductibles"] = {k: 2 * v for k, v in spec["deductibles"].items()}
            rng = _r.Random(4242)
            rows = [make_row(drifted, rng, 700000 + i) for i in range(30)]
            cases = [{"id": r["id"], "state": r["state"], "gold": r["gold"]} for r in rows]
            self._send(200, {"drift": "deductibles doubled",
                             "taught": run_eval(domain, eng, cases, []),
                             "zero": run_eval(domain, zero, cases, [])})
            return
        self.send_response(404); self._cors(); self.end_headers()


if __name__ == "__main__":
    host = os.environ.get("STUDIO_HOST", "127.0.0.1")
    print(f"[studio] serving on {host}:{PORT} (token {'set' if TOKEN else 'NOT set — mutating routes open'})", flush=True)
    ThreadingHTTPServer((host, PORT), H).serve_forever()
