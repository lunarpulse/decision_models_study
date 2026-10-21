# Insurance-claims live demo — decision console

Audience-facing demo of the study's engines on an insurance-claims user journey.
Insurance fine-tuning happens **before** the session (`bash train_laya.sh`); the Domain Builder tab
runs a real, presenter-gated fine-tune live (studio service, ~1½ min click to result). Five tabs: day1 · after · compare · ops · domain.

## Start

```bash
cd demo-insurance && bash start_demo.sh
```

Then open **http://127.0.0.1:8901/** (ops floor; `?mode=day1` for the narrated opener). The laya
service serves the console itself.

Services: `laya_service.py` :8901 (zero-shot Router + fine-tuned checkpoint, console, proxies) ·
`decider_service.py` :8902 (decider-4b v2.1) · `studio_service.py` :8903 (Domain Builder; token-gated
teach). Supervised operation (systemd user units, `sync_live.sh`, logs, pre-show checklist): see
`DEMO_MANUAL.md` §1.

## The audience experience (engineered flow)

1. **Day 1 tab** — engines untrained. Run presets; watch out-of-box Laya miss decisions
   (measured 46.4% avg per decision, 1/500 claims all-7 correct) while decider holds 70.8%.
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

| Engine | Avg per decision (7) | Claims all-7-correct |
|---|---:|---:|
| Laya out-of-box | 46.4% | 1 / 500 |
| **Laya fine-tuned (12k claims, ~15 min on this machine)** | **100.0%** | **500 / 500** |
| decider-4b (zero training) | 70.8% | 21 / 500 |

Train and holdout share one templated generator (in-distribution); see DEMO_MANUAL §4 for caveats.

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
3. All services bind 127.0.0.1 by default; the public path is the cloudflared tunnel to :8901.
   Mutating studio routes need the studio token; inference routes are open but size-capped
   and admission-controlled. GPU budget with everything resident: ~22 GB (+ ~10 GB peak during a teach).
