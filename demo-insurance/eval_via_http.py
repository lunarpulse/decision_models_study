"""Holdout eval through the live services (also validates them end-to-end).
Writes data/stats.json: {zero, ft, dec} = per-question accuracy over 500 rows x 3 questions.
Host python3, stdlib only. Run after both services are up.
"""
import json, os, time, pathlib, urllib.request

HOLD = str(pathlib.Path(__file__).resolve().parent / "data" / "holdout_eval.jsonl")
OUT = str(pathlib.Path(__file__).resolve().parent / "data" / "stats.json")
LAYA = f"http://127.0.0.1:{os.environ.get('LAYA_PORT', '8901')}"
DEC = f"http://127.0.0.1:{os.environ.get('DECIDER_PORT', '8902')}"

def post(url, obj):
    req = urllib.request.Request(url + "/predict", data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

def ok(qid, a, g):
    if a is None: return False
    if "choice" in a: return a["choice"] == g
    if "noul" in a: return (a["noul"] >= 0.5) == bool(g)
    if "score" in a: return a["score"] == g
    return False

rows = [json.loads(l) for l in open(HOLD)]
qids = ["routing", "fraud_review", "urgency"]
stats = {"zero": [0, 0], "ft": [0, 0], "dec": [0, 0]}  # [correct, total]
row_all = {"zero": 0, "ft": 0, "dec": 0}
t0 = time.time()
for i, r in enumerate(rows):
    try:
        lr = post(LAYA, {"state": r["state"], "questions": r["questions"]})
        dr = post(DEC, {"state": r["state"], "questions": r["questions"]})
    except Exception as e:
        print("row", i, "service error:", repr(e)[:120]); continue
    for key, resp in (("zero", lr["zero"]), ("ft", lr["ft"]), ("dec", dr["decider"])):
        all_ok = True
        for qid in qids:
            a = resp["answers"].get(qid)
            good = ok(qid, a, r["gold"][qid])
            stats[key][0] += int(good); stats[key][1] += 1
            all_ok &= good
        row_all[key] += int(all_ok)
    if (i + 1) % 100 == 0:
        print(f"{i+1}/{len(rows)} elapsed {time.time()-t0:.0f}s "
              f"zero={stats['zero'][0]/stats['zero'][1]:.3f} ft={stats['ft'][0]/stats['ft'][1]:.3f} dec={stats['dec'][0]/stats['dec'][1]:.3f}", flush=True)

if stats["zero"][1] < len(rows) or stats["dec"][1] < len(rows):
    raise SystemExit(f"service errors detected ({len(rows) - stats['dec'][1]} decider / {len(rows) - stats['zero'][1]} laya rows) — aborting, stats.json NOT overwritten")
out = {"zero": stats["zero"][0] / stats["zero"][1], "ft": stats["ft"][0] / stats["ft"][1],
       "dec": stats["dec"][0] / stats["dec"][1], "n_rows": len(rows),
       "rows_all_correct": row_all, "elapsed_s": round(time.time() - t0, 1)}
open(OUT, "w").write(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
