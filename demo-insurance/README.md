# Insurance-claims live demo — decision console

Audience-facing demo of the study's engines on an insurance-claims user journey.
Fine-tuning happens **before** the session (`bash train_laya.sh`); nothing trains live. Two "eras" are served side by side.

## Start

```bash
cd demo-insurance && bash start_demo.sh
```

Then open **http://127.0.0.1:8901/?mode=day1** (the Laya service serves the console itself).

Services: `laya_service.py` :8901 (zero-shot Router + fine-tuned checkpoint in one process, venv-laya) ·
`decider_service.py` :8902 (decider-4b v2.1, venv-decider). Logs: `*-service.log`.

## The audience experience (engineered flow)

1. **Day 1 tab** — engines untrained. Run presets; watch out-of-box Laya miss fraud flags
   (measured 37.8% on 500 unseen claims) while decider holds ~74%.
2. **The reveal button** — "⚡ Train on 12,000 past claims — and re-run this claim" switches to the
   after-era and re-runs the *same* claim on the trained engine: correct answers with sharp
   probabilities (100.0% measured).
3. **After tab / Compare tab** — trained engine, or all three side by side with a live scoreboard
   (preset hits per visible engine; Reset clears).
4. **Free-text box** — paste any claim; engines answer with probabilities, verdict shows
   "no rule answer" honestly.
5. Preset groups: standard claims · fraud-flag scenarios · multilingual (Korean/Japanese/Hindi/Spanish,
   auto-routed to Laya's multilingual checkpoint; the fine-tuned engine correctly shows its
   English-only note instead of guessing).

## What the audience sees per run

- The exact request (claim text + questions schema with the routing rule and answer options).
- Per engine, per question: chosen answer, probability bars over all options, confidence, latency.
- Verdict chips against the claims-manual rule (✓ / ✗ / no rule answer).

## Measured on the 500-claim holdout (through the live services)

| Engine | Per-question accuracy | Rows all-3-correct |
|---|---:|---:|
| Laya out-of-box | 37.8% | 0 / 500 |
| **Laya fine-tuned (12k claims, ~15 min on this machine)** | **100.0%** | **500 / 500** |
| decider-4b (zero training) | 74.1% | 256 / 500 |

## Assets

- `gen_corpus.py` → `data/` (train 12k / val 2k / holdout 500 / 20 curated presets; rule-computed gold)
- `laya-ft-ckpt/` — the trained checkpoint (soft-ce, `--shuffle-options`, 3 epochs)
- `eval_via_http.py` — re-runs the holdout through the services, rewrites `data/stats.json`
- `index.html` — the console (also served at `/`)

## Retained caveats

1. `laya.train` warned the fine-tuned checkpoint's noul (yes/no) calibration fit stayed at 1.0 —
   yes/no confidences from the trained engine are uncalibrated (visible as very sharp probabilities;
   demo shows probabilities, not just argmax, so this is observable, not hidden).
2. The "via <checkpoint>" routing badge on engine A renders from the engine-level payload field.
3. Both services bind 127.0.0.1 by default (set `DEMO_HOST=0.0.0.0` to expose on the LAN —
   there is no authentication; anyone who can reach the port can run inferences on your GPU).
   GPU budget with all engines resident: ~10 GB.
