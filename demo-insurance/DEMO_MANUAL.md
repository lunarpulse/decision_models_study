# Demo operator & presenter manual — Insurance Claims Decision Console

Session development record (including operator Q&A and the failure ledger): `DEVELOPMENT_LOG.md`.
Run from the repo's `demo-insurance/` directory. · Console: **http://127.0.0.1:8901**
Runs on one machine with a CUDA GPU (~10 GB VRAM with all engines resident; author measurements used an RTX 5090 — see docs/ for provenance).

## 1. Start / stop

```bash
bash start_demo.sh   (from demo-insurance/)   # starts services if down, prints URLs
bash stop_demo.sh    (from demo-insurance/)    # stops services + cloudflared tunnel
```

- **laya service** `:8901` — serves the console AND both Laya engines: zero-shot Router
  (auto language routing) + fine-tuned English + fine-tuned multilingual checkpoints.
- **decider service** `:8902` — decider-4b v2.1, always untrained (that is the point of Engine C).
- Logs: `laya-service.log`, `decider-service.log`. Health dots in the top bar; `?mode=` URLs are
  shareable (`day1`, `after`, `compare`).
- First request after a cold start takes ~1–2 s (CUDA warm-up); afterwards 10–30 ms per decision.

## 2. Sharing online (cloudflared)

```bash
cloudflared tunnel --url http://localhost:8901 > cloudflared.log 2>&1 &   # install: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' cloudflared.log | head -1
```

The printed `https://…trycloudflare.com` URL is the public demo link (no account needed; URL is
ephemeral — regenerate per session; a named Cloudflare tunnel can make it stable). The console,
both Laya engines and the decider proxy all flow through that one origin.

**Exposure notes (read before sharing widely):** no authentication on the demo; anyone with the
link can run inferences on your GPU. Inputs are not logged by the services; cloudflared and your
network see traffic metadata. Fine for a session with known recipients; revoke with `stop_demo.sh`.

## 3. What to show — the 8-minute arc

1. **Frame (1 min):** "Every claim triggers three small decisions — which unit, fraud or not, how
   urgent. Today people make them; a decision model makes them in milliseconds and shows you the
   probability it is acting on."
2. **Day 1 (3 min):** open `?mode=day1`. Run 2 standard presets — out-of-box Laya misses some.
   Then run a **FRAUD** preset: Laya says YES/NO with high confidence on the wrong side.
   decider-4b is right — "the bigger generalist is decent with zero data; the small one is lost."
3. **The reveal (1 min):** press the green **"⚡ Train on 12,000 past claims"** button — same claim,
   trained engine, all three answers correct with sharp probabilities. "Fifteen minutes of training
   on this machine, before the session. Nothing you are watching is recorded or staged."
4. **Multilingual (1 min):** compare mode, run 🇰🇷 Korean / 🇯🇵 Japanese presets — the zero-shot
   engine auto-routes to its multilingual checkpoint; the trained engine now also switches
   checkpoints per language (badge: `trained checkpoint: multilingual-finetuned`).
5. **Audience drives (2 min):** hand over the free-text box — paste any claim; discuss the
   probability bars. Scoreboard tallies preset hits per engine; Reset clears.

## 4. Numbers you may quote (measured on 500 unseen claims, this machine)

| Engine | Accuracy | All-three-correct rows |
|---|---:|---:|
| Laya out-of-box | 37.8% | 0/500 |
| Laya fine-tuned (12k claims) | 100.0% | 500/500 |
| decider-4b (no training) | 74.1% | 256/500 |

Study context: on the prior sealed corpus Laya-ft beat the adapted 8B CLM model on every endpoint
(`LAYA_DECIDER_EXPERIMENT_REPORT.md`).

## 5. Language handling (measured, and why Engine B is English-only)

The English fine-tuned checkpoint **trades away language robustness**: on a Spanish claim it
scored 1/3 where the untrained base scored 2/3 — fine-tuning to zero loss on templated English
narrows the model (catastrophic forgetting of anything off-distribution). A second checkpoint
fine-tuned from the multilingual base on the same English data gave mixed cross-lingual results
(Korean/Japanese improved, Hindi regressed; 8/9 vs 7/9 on the four multilingual presets). Per
operator decision, the demo therefore shows the **English fine-tune only**; non-English claims
get an explicit note and Engine A's zero-shot multilingual checkpoint answers them. To build a
proper multilingual fine-tune you need multilingual training rows (translated or per-language
synthetic data), not English-only data.


## 6. Q&A cheatsheet

- *"Is the fine-tuned model always right?"* — On this claim family it maxed the exam; the planning
  number is always the unseen-distribution figure (92% on the study corpus). Never quote 100% as
  a deployment promise.
- *"Why does trained Laya show 100% confidence?"* — Its yes/no calibration is uncalibrated after
  fine-tuning (training warning retained); show probabilities, recalibrate before real thresholds.
- *"Does it write answers?"* — No. Options in, probabilities out; a wrong format is impossible.
- *"Who acts?"* — Nobody. Thresholds route: ≥0.9 auto, 0.6–0.9 review, below escalate; people keep
  authority (same recommend–authorize–execute pattern as the study decks).
- *"Where does training data come from?"* — 12,000 synthetic past claims with rule-computed answers
  (`gen_corpus.py`); in production this would be your historical labeled claims.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| Top-bar dot red | service down → `start_demo.sh`; check `*-service.log` |
| First answer slow | CUDA warm-up; second run is milliseconds |
| Multilingual preset shows note instead of answers | multilingual fine-tuned checkpoint missing → it fell back; retrain with `laya.train_cli --base <laya snapshot>/multilingual` |
| Tunnel URL dead | quick tunnels are ephemeral → restart cloudflared, share the new URL |
| GPU busy / other ML work running | stop_demo.sh first; engines need ~10 GB VRAM |
