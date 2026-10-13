"""Evaluate a decider checkpoint (base or fine-tuned) on the 20 demo presets.

Usage:
    python eval_presets.py Mapika/decider-4b
    python eval_presets.py decider-ft-ckpt/model
Prints per-preset verdicts and accuracy on the 16 English presets (the multilingual four are
informational — the zero-shot arm routes them via Engine A in the live demo).
"""
import json, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from decider.infer import Decider

def render(q):
    if q["type"] == "noul":
        return {"question": q["instructions"], "options": ["no", "yes"]}, None
    crit = q["criteria"]
    if isinstance(crit, dict):
        keys = list(crit.keys())
        return {"question": q["instructions"], "options": keys}, keys
    return {"question": q["instructions"], "options": list(crit)}, list(crit)

def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "Mapika/decider-4b"
    d = Decider(model, device="cuda" if __import__("torch").cuda.is_available() else "cpu")
    pkg = json.load(open(ROOT / "data/demo_presets.json"))
    presets, questions = pkg["presets"], pkg["questions"]

    ok = tot = 0; en_ok = en_tot = 0
    for p in presets:
        qs, metas = [], []
        for qid, q in questions.items():
            qq, keys = render(q)
            qs.append(qq); metas.append((qid, q["type"], keys))
        t0 = time.perf_counter()
        res = d.decide(p["state"], qs)
        ms = (time.perf_counter() - t0) * 1000
        row_ok = True; parts = []
        for (qid, qtype, keys), a, (gqid, g) in zip(metas, res, p["gold"].items()):
            gold = g if not isinstance(g, bool) else int(g)
            if qtype == "noul":
                v = int(a["probs"].get("yes", 0) > 0.5)
                hit = v == gold
                parts.append(f"{qid}:{'✓' if hit else '✗'} p={a['probs'].get('yes', 0):.2f}")
            else:
                ch = a.get("choice")
                v = keys.index(ch) if (qtype == "score" and keys and ch in keys) else ch
                hit = v == gold
                parts.append(f"{qid}:{'✓' if hit else '✗'}")
            tot += 1; ok += hit
            row_ok &= hit
        if p.get("lang") is None:
            en_tot += len(parts); en_ok += sum('✓' in x for x in parts)
        print(("✓" if row_ok else "✗"), f"{p['label'][:36]:38s}", " ".join(parts), f"{ms:.0f}ms")
    print(f"\noverall {ok}/{tot} = {ok/tot:.3f} | English presets {en_ok}/{en_tot} = {en_ok/en_tot:.3f}")

if __name__ == "__main__":
    main()
