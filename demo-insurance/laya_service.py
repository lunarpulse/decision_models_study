"""Laya demo service: zero-shot Router + fine-tuned checkpoint, one process.
GET /health -> ok; POST /predict {state, questions} -> {zero: {...}, ft: {...}}
CORS only for file:// (Origin: null) and localhost/127.0.0.1 pages.
Run under the repo's .venv-laya/bin/python.
"""
import json, time, sys, re, os, pathlib, threading, traceback, urllib.parse, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_DEC_PORT = os.environ.get("DECIDER_PORT", "8902")
_STUDIO_PORT = os.environ.get("STUDIO_PORT", "8903")

MAX_BODY = 64 * 1024        # request body cap -> 413 beyond
MAX_STATE = 4000            # claim text cap -> 400 beyond
MAX_QUESTIONS = 12          # served schema has 7; reject bigger client lists
BUSY_TIMEOUT_S = 20         # how long a request may wait for a model slot -> 503
REPORT_NAME = "LAYA_DECIDER_EXPERIMENT_REPORT.md"

ROOT = pathlib.Path(os.environ.get("DEMO_ROOT", pathlib.Path(__file__).resolve().parent))
FT_PATH = os.environ.get("LAYA_FT_CKPT", str(ROOT / "laya-ft-ckpt"))

_MODEL_SEM = threading.BoundedSemaphore(2)  # one slot per model: zero-shot + fine-tuned
_LITE_CACHE = {}                            # portfolio path -> (mtime, lite bytes)

# The console runs from file:// (Origin: null), localhost dev servers, or the tunnel
# (same-origin: no CORS header needed). Anything else gets no CORS headers.
_LOCAL_ORIGIN = re.compile(r"^http://(127\.0\.0\.1|localhost)(:\d+)?$")


def _cors_ok(origin):
    return origin == "null" or bool(origin and _LOCAL_ORIGIN.match(origin))


def _strip_probabilities(node):
    if isinstance(node, dict):
        node.pop("probabilities", None)
        for v in node.values():
            _strip_probabilities(v)
    elif isinstance(node, list):
        for v in node:
            _strip_probabilities(v)


def _version():
    try:
        return (ROOT / "VERSION").read_text().strip() or None
    except OSError:
        return None

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
        origin = self.headers.get("Origin")
        if _cors_ok(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def _send(self, code, ctype, payload):
        self.send_response(code); self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload))); self.end_headers()
        self.wfile.write(payload)

    def _read_raw(self):
        """(raw bytes, None) capped at MAX_BODY; (None, (code, payload)) on failure."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None, (400, b'{"error":"bad request"}')
        if n < 0:
            return None, (400, b'{"error":"bad request"}')
        if n > MAX_BODY:
            return None, (413, b'{"error":"request too large"}')
        return (self.rfile.read(n) if n else b""), None

    def _read_body(self):
        """(body, None) on success; (None, (code, payload)) on oversized/bad bodies."""
        raw, err = self._read_raw()
        if err:
            return None, err
        try:
            body = json.loads(raw or b"{}")
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

    def _proxy(self, url, data=None, headers=None, timeout=30):
        """Forward to a local service; pass status codes/bodies through unchanged."""
        try:
            req = urllib.request.Request(url, data=data, headers=headers or {})
            with urllib.request.urlopen(req, timeout=timeout) as r2:
                return r2.status, r2.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except Exception:
            traceback.print_exc(file=sys.stderr)
            return 502, b'{"error":"upstream unavailable"}'

    def do_GET(self):
        split = urllib.parse.urlsplit(self.path)
        path, query = split.path, split.query
        base = str(ROOT)
        if path == "/health":
            self._send(200, "application/json", b'{"ok":true}')
            return
        if path == "/dec/health":  # proxied decider health for single-origin pages
            code, payload = self._proxy(f"http://127.0.0.1:{_DEC_PORT}/health", timeout=10)
            self._send(code, "application/json", payload)
            return
        if path.startswith("/studio/"):  # proxy GETs to the Teaching Studio
            url = f"http://127.0.0.1:{_STUDIO_PORT}{path}" + ("?" + query if query else "")
            code, payload = self._proxy(url)
            self._send(code, "application/json", payload)
            return
        if path == "/stats":
            try:
                stats = json.load(open(base + "/data/stats.json"))
                stats["version"] = _version()
                self._send(200, "application/json", json.dumps(stats).encode())
            except FileNotFoundError:
                self.send_response(404); self._cors(); self.end_headers()
            except Exception:
                traceback.print_exc(file=sys.stderr)
                self._send(500, "application/json", b'{"error":"internal error"}')
            return
        if path == "/report":
            for cand in (ROOT.parent / "docs" / REPORT_NAME, ROOT / "docs" / REPORT_NAME):
                if cand.is_file():
                    self._send(200, "text/plain; charset=utf-8", cand.read_bytes())
                    return
            self.send_response(404); self._cors(); self.end_headers()
            return
        if path == "/portfolio":
            fp = base + "/data/portfolio_results.json"
            lite = urllib.parse.parse_qs(query).get("lite", ["0"])[0] in ("1", "true")
            try:
                if lite:  # same JSON, probabilities stripped from every answer dict
                    mtime = os.path.getmtime(fp)
                    cached = _LITE_CACHE.get(fp)
                    if not cached or cached[0] != mtime:
                        doc = json.load(open(fp))
                        _strip_probabilities(doc)
                        cached = (mtime, json.dumps(doc).encode())
                        _LITE_CACHE[fp] = cached
                    payload = cached[1]
                else:
                    payload = open(fp, "rb").read()
                self._send(200, "application/json", payload)
            except FileNotFoundError:
                self.send_response(404); self._cors(); self.end_headers()
            except Exception:
                traceback.print_exc(file=sys.stderr)
                self._send(500, "application/json", b'{"error":"internal error"}')
            return
        routes = {
            "/": ("text/html; charset=utf-8", base + "/index.html"),
            "/presets": ("application/json", base + "/data/demo_presets.json"),
        }
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

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/dec/predict":  # proxy to decider service (single-origin tunneling)
            raw, err = self._read_raw()
            if err:
                self._send(err[0], "application/json", err[1]); return
            code, payload = self._proxy(f"http://127.0.0.1:{_DEC_PORT}/predict", data=raw or None,
                                        headers={"Content-Type": "application/json"}, timeout=120)
            self._send(code, "application/json", payload)
            return
        if path.startswith("/studio/"):  # proxy to the Teaching Studio (single-origin tunneling)
            raw, err = self._read_raw()
            if err:
                self._send(err[0], "application/json", err[1]); return
            hdrs = {"Content-Type": "application/json"}
            if self.headers.get("X-Studio-Token"):
                hdrs["X-Studio-Token"] = self.headers["X-Studio-Token"]
            code, payload = self._proxy(f"http://127.0.0.1:{_STUDIO_PORT}{path}", data=raw or None, headers=hdrs)
            self._send(code, "application/json", payload)
            return
        if path == "/rules":  # Engine D: incumbent rules engine (pure Python, no GPU)
            body, err = self._read_body()
            if err:
                self._send(err[0], "application/json", err[1]); return
            if not self._claim_ok(body):
                self._send(400, "application/json", b'{"error":"bad request"}'); return
            try:
                import rules_engine
                resp = rules_engine.decide(body["state"], body.get("questions"))
                self._send(200, "application/json", json.dumps(resp).encode())
            except Exception:
                traceback.print_exc(file=sys.stderr)
                self._send(500, "application/json", b'{"error":"internal error"}')
            return
        if path != "/predict":
            self.send_response(404); self._cors(); self.end_headers(); return
        body, err = self._read_body()
        if err:
            self._send(err[0], "application/json", err[1]); return
        if not self._claim_ok(body):
            self._send(400, "application/json", b'{"error":"bad request"}'); return
        state, questions, lang = body["state"], body.get("questions"), body.get("lang")
        if not _MODEL_SEM.acquire(timeout=BUSY_TIMEOUT_S):
            self._send(503, "application/json", b'{"error":"engine busy, retry"}')
            return
        try:
            eng, which = ft_engine_for(state, lang)
            if eng is None:
                ft_res = {"note": which}
            else:
                ft_res = run_engine(eng, state, questions)
                ft_res["ft_checkpoint"] = which
            resp = {"zero": run_engine(router, state, questions), "ft": ft_res}
            code, ctype, payload = 200, "application/json", json.dumps(resp).encode()
        except Exception:
            traceback.print_exc(file=sys.stderr)
            code, ctype, payload = 500, "application/json", b'{"error":"internal error"}'
        finally:
            _MODEL_SEM.release()
        self._send(code, ctype, payload)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8901
    print(f"[laya-service] serving on {os.environ.get('DEMO_HOST', '127.0.0.1')}:{port}", flush=True)
    HOST = os.environ.get("DEMO_HOST", "127.0.0.1")  # set DEMO_HOST=0.0.0.0 to expose on the LAN (no auth!)
    ThreadingHTTPServer((HOST, port), H).serve_forever()
