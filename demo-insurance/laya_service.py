"""Laya demo service: zero-shot Router + fine-tuned checkpoint, one process.
GET /health -> ok; POST /predict {state, questions} -> {zero: {...}, ft: {...}}
CORS open for file:// frontend. Run under the repo's .venv-laya/bin/python.
"""
import json, time, sys, re, os, pathlib, urllib.parse, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_DEC_PORT = os.environ.get("DECIDER_PORT", "8902")
_STUDIO_PORT = os.environ.get("STUDIO_PORT", "8903")

ROOT = pathlib.Path(os.environ.get("DEMO_ROOT", pathlib.Path(__file__).resolve().parent))
FT_PATH = os.environ.get("LAYA_FT_CKPT", str(ROOT / "laya-ft-ckpt"))

import laya
from laya import Router

router = Router(preload=True)
DEVICE = os.environ.get("DEVICE", "cuda")
ft = laya.load(FT_PATH, device=DEVICE)
# (a multilingual fine-tuned checkpoint was evaluated and intentionally not served — see DEMO_MANUAL)

# Demo policy: Engine B shows ONLY the English fine-tuned checkpoint. Any non-English input
# (explicit lang hint or non-Latin script) gets an explicit note instead of a guessed answer.
_NONLATIN = re.compile(r"[\u3131-\uD79F\u3040-\u30FF\u4E00-\u9FFF\u0900-\u097F\u0600-\u06FF\u0590-\u05FF\u0E00-\u0E7F]")
_NON_EN_HINTS = ("es", "fr", "de", "it", "pt", "nl", "ko", "ja", "hi", "zh", "ar", "he", "th", "ru")

def ft_engine_for(state, lang=None):
    if lang in _NON_EN_HINTS or (isinstance(state, str) and _NONLATIN.search(state)):
        return None, "english-only"
    return ft, "english-finetuned"

print("[laya-service] zero-shot Router + English fine-tuned checkpoint loaded", flush=True)


def run_engine(eng, state, questions):
    t0 = time.perf_counter()
    res = eng.predict(state, questions)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    out = {"ms": ms, "routing_model": (res.get("routing") or {}).get("model"), "answers": {}}
    for qid, a in res.get("answers", {}).items():
        d = {"type": a.get("type")}
        if "choice" in a: d["choice"] = a["choice"]
        if "score" in a: d["score"] = a["score"]
        if "noul" in a: d["noul"] = a["noul"]
        if isinstance(a.get("probabilities"), dict):
            d["probabilities"] = {str(k): round(float(v), 4) for k, v in a["probabilities"].items()}
            d["confidence"] = round(float(a.get("answer_confidence", max(d["probabilities"].values()))), 4)
        out["answers"][qid] = d
    return out


class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        base = str(ROOT)
        routes = {
            "/": ("text/html; charset=utf-8", base + "/index.html"),
            "/presets": ("application/json", base + "/data/demo_presets.json"),
            "/stats": ("application/json", base + "/data/stats.json"),
            "/portfolio": ("application/json", base + "/data/portfolio_results.json"),
        }
        if path == "/health":
            self._send(200, "application/json", b'{"ok":true}')
            return
        if path == "/dec/health":  # proxied decider health for single-origin pages
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{_DEC_PORT}/health", timeout=10) as r2:
                    self._send(200, "application/json", r2.read())
            except Exception as e:
                self._send(502, "application/json", json.dumps({"ok": False, "error": repr(e)[:120]}).encode())
            return
        if path.startswith("/studio/"):  # proxy GETs to the Teaching Studio
            try:
                full = urllib.parse.urlsplit(self.path)
                url = f"http://127.0.0.1:{_STUDIO_PORT}{full.path}"
                if full.query:
                    url += "?" + full.query
                with urllib.request.urlopen(url, timeout=60) as r2:
                    code, payload = 200, r2.read()
            except urllib.error.HTTPError as e:
                code, payload = e.code, e.read()
            except Exception as e:
                code, payload = 502, json.dumps({"error": repr(e)[:200]}).encode()
            self._send(code, "application/json", payload)
            return
        if path in routes:
            ctype, filepath = routes[path]
            try:
                payload = open(filepath, "rb").read()
                self.send_response(200); self._cors()
                self.send_header("Content-Type", ctype)
                if "text/html" in ctype:
                    self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload))); self.end_headers()
                self.wfile.write(payload)
            except FileNotFoundError:
                self.send_response(404); self._cors(); self.end_headers()
            return
        self.send_response(404); self._cors(); self.end_headers()

    def _send(self, code, ctype, payload):
        self.send_response(code); self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload))); self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/dec/predict":  # proxy to decider service (single-origin tunneling)
            try:
                n = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(n)
                req = urllib.request.Request(f"http://127.0.0.1:{_DEC_PORT}/predict", data=body,
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=120) as r2:
                    code, payload = 200, r2.read()
            except urllib.error.HTTPError as e:
                code, payload = e.code, e.read()
            except Exception as e:
                code, payload = 502, json.dumps({"error": repr(e)[:200]}).encode()
            self._send(code, "application/json", payload)
            return
        if path.startswith("/studio/"):  # proxy to the Teaching Studio (single-origin tunneling)
            sub = path[len("/studio/"):]
            try:
                n = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(n) if n else None
                hdrs = {"Content-Type": "application/json"}
                if self.headers.get("X-Studio-Token"):
                    hdrs["X-Studio-Token"] = self.headers["X-Studio-Token"]
                req = urllib.request.Request(f"http://127.0.0.1:{_STUDIO_PORT}/studio/{sub}",
                                             data=body, headers=hdrs)
                with urllib.request.urlopen(req, timeout=1800) as r2:
                    code, payload = 200, r2.read()
            except urllib.error.HTTPError as e:
                code, payload = e.code, e.read()
            except Exception as e:
                code, payload = 502, json.dumps({"error": repr(e)[:200]}).encode()
            self._send(code, "application/json", payload)
            return
        if path == "/rules":  # Engine D: incumbent rules engine (pure Python, no GPU)
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            try:
                import rules_engine
                resp = rules_engine.decide(body.get("state", ""), body.get("questions"))
                self._send(200, "application/json", json.dumps(resp).encode())
            except Exception as e:
                self._send(500, "application/json", json.dumps({"error": repr(e)[:300]}).encode())
            return
        if path != "/predict":
            self.send_response(404); self._cors(); self.end_headers(); return
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        state = body["state"]; questions = body.get("questions"); lang = body.get("lang")
        try:
            eng, which = ft_engine_for(state, lang)
            if eng is None:
                ft_res = {"note": which}
            else:
                ft_res = run_engine(eng, state, questions)
                ft_res["ft_checkpoint"] = which
            resp = {"zero": run_engine(router, state, questions), "ft": ft_res}
            code, ctype, payload = 200, "application/json", json.dumps(resp).encode()
        except Exception as e:
            code, ctype, payload = 500, "application/json", json.dumps({"error": repr(e)[:300]}).encode()
        self._send(code, ctype, payload)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8901
    print(f"[laya-service] serving on {os.environ.get('DEMO_HOST', '127.0.0.1')}:{port}", flush=True)
    HOST = os.environ.get("DEMO_HOST", "127.0.0.1")  # set DEMO_HOST=0.0.0.0 to expose on the LAN (no auth!)
    ThreadingHTTPServer((HOST, port), H).serve_forever()
