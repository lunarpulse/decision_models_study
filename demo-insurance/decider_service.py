"""decider-4b demo service. POST /predict {state, questions} -> {decider: {...}}
Run under the repo's .venv-decider/bin/python.
"""
import json, time, sys, os, re, threading, traceback, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from decider.infer import Decider

DECIDER_MODEL = os.environ.get("DECIDER_MODEL", "Mapika/decider-4b")  # hub id or local path
DEVICE = os.environ.get("DEVICE", "cuda")  # DEVICE=cpu needs a FLA-free venv (see README CPU row)

MAX_BODY = 64 * 1024        # request body cap -> 413 beyond
MAX_STATE = 4000            # claim text cap -> 400 beyond
MAX_QUESTIONS = 12          # served schema has 7; reject bigger client lists
BUSY_TIMEOUT_S = 20         # how long a request may wait for the model slot -> 503

_MODEL_SEM = threading.BoundedSemaphore(1)  # one decider pass at a time

# CORS only for file:// (Origin: null) and localhost/127.0.0.1 pages; anything else gets
# no CORS headers (same-origin traffic never needs them).
_LOCAL_ORIGIN = re.compile(r"^http://(127\.0\.0\.1|localhost)(:\d+)?$")


def _cors_ok(origin):
    return origin == "null" or bool(origin and _LOCAL_ORIGIN.match(origin))

d = Decider(DECIDER_MODEL, device=DEVICE)
print("[decider-service] decider-4b v2.1 loaded", flush=True)

def score_question(q):
    crit = q.get("criteria")
    if q["type"] == "noul":
        return None, ["no", "yes"]
    if isinstance(crit, dict):
        keys = list(crit.keys())
        return keys, [crit[k] for k in keys]
    return list(crit), list(crit)


def run(state, questions):
    t0 = time.perf_counter()
    answers = {}
    # decider scores all questions in one pass
    qs, metas = [], []
    for qid, q in questions.items():
        keys, opts = score_question(q)
        qs.append({"question": q["instructions"], "options": opts or ["no", "yes"]})
        metas.append((qid, q["type"], keys, opts))
    res = d.decide(state, qs)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    for (qid, qtype, keys, opts), a in zip(metas, res):
        entry = {"type": qtype}
        if qtype == "noul":
            probs = a.get("probs", {})
            entry["noul"] = round(float(probs.get("yes", 0.0)), 4)
            entry["probabilities"] = {"no": round(1.0 - entry["noul"], 4), "yes": entry["noul"]}
            entry["confidence"] = max(entry["probabilities"].values())
        else:
            desc2key = {o: (keys[i] if keys else i) for i, o in enumerate(opts)}
            probs = {str(desc2key.get(o, o)): round(float(p), 4) for o, p in a.get("probs", {}).items()}
            entry["probabilities"] = probs
            if qtype == "choice":
                entry["choice"] = desc2key.get(a.get("choice"), a.get("choice"))
            else:
                lv = a.get("choice")
                idx = opts.index(lv) if lv in opts else None
                entry["score"] = idx
            entry["confidence"] = round(float(a.get("confidence", max(probs.values()))), 4)
        answers[qid] = entry
    return {"ms": ms, "answers": answers}


class H(BaseHTTPRequestHandler):
    def _cors(self):
        origin = self.headers.get("Origin")
        if _cors_ok(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def do_OPTIONS(self):
        self.t0 = time.perf_counter()
        self.send_response(204); self._cors(); self.end_headers()

    def _send(self, code, payload):
        self.send_response(code); self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload))); self.end_headers()
        self.wfile.write(payload)

    def _read_body(self):
        """(body, None) on success; (None, (code, payload)) on oversized/bad bodies."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n < 0:
                raise ValueError("negative Content-Length")
            if n > MAX_BODY:
                return None, (413, b'{"error":"request too large"}')
            body = json.loads(self.rfile.read(n) if n else b"{}")
        except Exception:
            return None, (400, b'{"error":"bad request"}')
        if not isinstance(body, dict):
            return None, (400, b'{"error":"bad request"}')
        return body, None

    def _claim_ok(self, body):
        state = body.get("state")
        questions = body.get("questions")
        if not isinstance(state, str) or len(state) > MAX_STATE:
            return False
        if not isinstance(questions, dict) or len(questions) > MAX_QUESTIONS:
            return False
        return True

    def do_GET(self):
        self.t0 = time.perf_counter()
        path = urllib.parse.urlsplit(self.path).path
        if path == "/health":
            self._send(200, b'{"ok":true}')
        else:
            self.send_response(404); self._cors(); self.end_headers()

    def do_POST(self):
        self.t0 = time.perf_counter()
        path = urllib.parse.urlsplit(self.path).path
        if path != "/predict":
            self.send_response(404); self._cors(); self.end_headers(); return
        body, err = self._read_body()
        if err:
            self._send(err[0], err[1]); return
        if not self._claim_ok(body):
            self._send(400, b'{"error":"bad request"}'); return
        if not _MODEL_SEM.acquire(timeout=BUSY_TIMEOUT_S):
            self._send(503, b'{"error":"engine busy, retry"}'); return
        try:
            resp = {"decider": run(body["state"], body.get("questions"))}
            code, payload = 200, json.dumps(resp).encode()
        except Exception:
            traceback.print_exc(file=sys.stderr)
            code, payload = 500, b'{"error":"internal error"}'
        finally:
            _MODEL_SEM.release()
        self._send(code, payload)

    def log_request(self, code="-", size="-"):
        ms = round((time.perf_counter() - self.t0) * 1000, 1) if getattr(self, "t0", None) else 0.0
        sys.stderr.write(f"[decider-service] {self.command} {self.path} {code} {ms}ms\n")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8902
    HOST = os.environ.get("DEMO_HOST", "127.0.0.1")  # set DEMO_HOST=0.0.0.0 to expose on the LAN (no auth!)
    print(f"[decider-service] serving on {HOST}:{port}", flush=True)
    ThreadingHTTPServer((HOST, port), H).serve_forever()
