"""decider-4b demo service. POST /predict {state, questions} -> {decider: {...}}
Run under the repo's .venv-decider/bin/python.
"""
import json, time, sys, os, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from decider.infer import Decider

import os
DECIDER_MODEL = os.environ.get("DECIDER_MODEL", "Mapika/decider-4b")  # hub id or local path
d = Decider(DECIDER_MODEL)
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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/health":
            self.send_response(200); self._cors()
            self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path != "/predict":
            self.send_response(404); self.end_headers(); return
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        try:
            resp = {"decider": run(body["state"], body.get("questions"))}
            code = 200
        except Exception as e:
            resp = {"error": repr(e)[:300]}; code = 500
        payload = json.dumps(resp).encode()
        self.send_response(code); self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload))); self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8902
    print(f"[decider-service] serving on 0.0.0.0:{port}", flush=True)
    HOST = os.environ.get("DEMO_HOST", "127.0.0.1")  # set DEMO_HOST=0.0.0.0 to expose on the LAN (no auth!)
    ThreadingHTTPServer((HOST, port), H).serve_forever()
