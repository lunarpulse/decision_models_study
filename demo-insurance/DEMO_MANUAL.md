# Demo operator & presenter manual — Insurance Claims Decision Console

Session development record (including operator Q&A and the failure ledger): `DEVELOPMENT_LOG.md`.
Run from the repo's `demo-insurance/` directory. · Console: **http://127.0.0.1:8901**
Runs on one machine with a CUDA GPU (~10 GB VRAM with all engines resident; author measurements used an RTX 5090 — see docs/ for provenance).

## 1. Running the demo — dev, live, and supervision

**Portable (repo tree, any machine):**

```bash
bash start_demo.sh            # laya :8901, decider :8902, studio :8903 (skips ones already up)
bash start_demo.sh --tunnel   # + cloudflared quick tunnel; public URL printed and saved to tunnel-url.txt
bash stop_demo.sh             # prints what it would stop — plan only, kills nothing
bash stop_demo.sh --yes       # stops all of the above + the studio's train_cli child (PID-attributed)
```

Venvs auto-detect from `../.venv-laya` / `../.venv-decider` (run `../setup.sh` once); override
with `LAYA_PY` / `DECIDER_PY` / `STUDIO_PY` (absolute python paths) and `LAYA_PORT` /
`DECIDER_PORT` / `STUDIO_PORT`. On the live machine the interpreters live inside the distrobox
`ai-dev`: `BOX=ai-dev LAYA_PY=/opt/ai-tools/venv-laya/bin/python DECIDER_PY=/opt/ai-tools/venv-decider/bin/python`.

- **laya service** `:8901` — serves the console AND both Laya engines: zero-shot Router
  (auto language routing) + fine-tuned English + fine-tuned multilingual checkpoints.
  Also proxies `/dec/*` and `/studio/*` — one public origin.
- **decider service** `:8902` — decider-4b v2.1, always untrained (that is the point of Engine C).
- **studio service** `:8903` — Teach/drift/status for the Domain Builder. Mutating routes need the
  token in `studio-token.txt` (auto-generated with a random secret on first start, chmod 600, never
  echoed); the presenter types it once in the console.

**Supervised (live machine):** the same services run as systemd `--user` units
`decision-demo-{laya,decider,studio,tunnel}.service`, grouped by `decision-demo.target`
(`deploy/systemd/`; failed services restart after 5 s). One-time setup:

```bash
demo-insurance/sync_live.sh               # repo -> live tree (see below)
demo-insurance/deploy/install_units.sh    # copies units + env file; prints start commands, starts nothing
systemctl --user start decision-demo.target            # the three services
systemctl --user start decision-demo-tunnel.service    # optional public URL -> tunnel-url.txt
```

Machine parameters (demo dir, distrobox name, python paths, ports, cloudflared binary) live in
`deploy/demo.env` — copy `deploy/demo.env.example` and edit; `install_units.sh` installs it as
`~/.config/systemd/user/decision-demo.env`. The studio unit refuses to start without
`studio-token.txt`. Note: the token reaches the studio through the environment, so any local user
can read it from `ps` — acceptable on a single-user demo box; the tunnel link is the real gate.

**Deploying a change:** edit in the repo, then `sync_live.sh` from `demo-insurance/`. It rsyncs
the repo tree to the live tree (`--checksum --delete`), keeps checkpoints, `studio-runs/`, logs,
tokens and caches intact, syncs `../docs/LAYA_DECIDER_EXPERIMENT_REPORT.md` into
`<target>/../docs/` (that is what `/report` serves), and writes the repo HEAD (plus `-dirty` when
the tree is dirty) to `VERSION` — shown by `/stats` and the footer. `--dry-run` lists pending
changes and exits non-zero while anything differs. Restart to load new code:
`systemctl --user restart decision-demo-laya decision-demo-decider decision-demo-studio`
(the tunnel and its URL keep running).

**Logs:**
- supervised services: `journalctl --user -u decision-demo-laya` (also `-decider`, `-studio`, `-tunnel`)
- start_demo.sh runs: `laya-service.log`, `decider-service.log`, `studio-service.log`, `cloudflared.log`
- studio training: `studio-runs/<domain>/train-<YYYYmmdd-HHMMSS>.log` — the full train_cli output;
  `/studio/status` shows parsed progress only, so go to the log when a teach fails.

Health dots in the top bar; `?mode=` URLs are shareable (`day1`, `after`, `compare`, `ops`, `domain`).
First request after a cold start takes ~1–2 s (CUDA warm-up); afterwards 10–30 ms per decision.

### Pre-show checklist

1. Units green: `systemctl --user status decision-demo.target` — laya, decider, studio `active (running)` (tunnel too, if used).
2. Health ok: `curl -s :8901/health`, `:8901/dec/health`, `:8901/studio/health` all report ok.
3. GPU room to teach: `/studio/health` free GiB ≥ its `teach_min_free_gib`; `pgrep -af laya.train_cli` finds nothing.
4. One phone test on mobile data through the tunnel URL — page loads, one preset answers.
5. Domain card renders in `?mode=domain` (cards, struggle cases, no blank pane).
6. Wrong-token test: teach with a garbage token is rejected and re-prompts; the real token works.
7. `VERSION` in the live tree equals the repo HEAD you meant to ship.
8. Disk and logs sane: `df -h .`, `du -sh studio-runs`, journal not ballooning.
9. After any restart, run one warm-up predict — first answer is the slow CUDA one (~1–2 s).

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

### The ops floor (the executive close) — `?mode=ops`

6. **Flip to ops (3 min):** "One claim is a toy; here is the operation." The sealed 500-claim
   holdout, all engines, measured once before the session. Show the money cards (total claimed,
   fraud $ flagged, false-flag $), then hand the threshold slider to the audience: every τ move
   changes the straight-through rate, the unattended accuracy, and the fraud that slips through.
   Let an adjuster override a row — the counters follow. The calibration strip answers the only
   question that matters for automation: *when it says 80%, is it right 80% of the time?*
   Engine D (rules) is on the same table on purpose: it is perfect on the phrasing it was built
   for and `unparsed` on the Korean claim — that is the incumbent's real shape.

### The Domain Builder (the closer) — `?mode=domain`

7. **Pick a business (2 min):** support tickets, logistics exceptions, HR exceptions. A seeded
   corpus with rule-verifiable gold generates instantly (500/500 replay-validated per domain,
   enforced in CI). The measured-struggle screen shows zero-shot engines failing real cases from
   that domain — picked from measured errors, not staged. Point at the fourth card: the
   decider-4b *trained on insurance* scoring high here with zero domain training — the journey
   itself transfers.
8. **Teach it (10 min — a talk beat):** bulk-accept the rule gold, then deliberately change ONE
   decision on ONE case ("our policy differs"). Press ⚡ Teach: a real fine-tune runs on this
   machine (~1,500 corpus rows relabeled under your edit + your 12 cases ×20, 2 epochs). The
   progress line ticks live. Result: the scoreboard flips, *and* the hand-written paraphrase
   probe humbles it — in-template perfection, out-of-template honesty. Calibration caveat is on
   the card.
9. **The retainer (1 min):** press "A year later" — deductibles double, and the taught engine's
   measured decay shows on screen. The fix is a 30-case re-teach. That loop is the recurring
   business.

Studio notes for the operator: `STUDIO_TOKEN=… python studio_service.py` (localhost :8903,
proxied through :8901). Training needs the token — anonymous tunnel visitors can watch but not
teach. One training job at a time. GPU: peak ~32 GiB of 32.6 with the full live stack resident —
teach during talk beats, not during latency demos.

## 4. Numbers you may quote (measured on 500 unseen claims, 7 questions each, this machine)

| Engine | accuracy | All-seven-correct rows |
|---|---:|---:|
| Laya out-of-box | 46.4% | 1/500 |
| decider-4b (no training) | 70.8% | 21/500 |
| **Laya fine-tuned (12k claims)** | **100.0%** | **500/500** |
| **decider-4b + LoRA (same 12k)** | **100.0%** | **500/500** |
| Rules engine (Engine D) | 100.0% *English phrasing only* | 500/500 — `unparsed` on non-English |

(An earlier run quoted 99.9%/497: a comparator bug — laya emits near-integer score floats like
1.0001 — not a model error; see DEVELOPMENT_LOG ledger #10.)

**Cross-domain transfer (decider-4b LoRA trained ONLY on insurance, never on these domains):**
support tickets 81.4% · logistics exceptions 93.3% · HR exceptions 89.9% (zero-shot base:
60.7% / 69.7% / 70.9%; laya zero-shot: 53.5% / 40.7% / 58.4%). The 7-decision journey itself
transfers — one supervised process buys most of the next one.

**The parity result (what fine-tuning does to the decider):** the same 12,000 rows that took
Laya from 46.4% to 100.0% took decider-4b from 70.8% to **100.0%** (LoRA rank 64, 2 epochs,
71 minutes, merged to bf16) — and it **kept its languages**: 140/140 preset questions including
Korean, Japanese, Hindi and Spanish. Caveats, stated plainly: train and holdout come from the
same templated generator (in-distribution); post-training confidences hit the calibration floor
(razor-sharp — treat thresholds as uncalibrated until recalibrated on real data); no
general-benchmark regression was re-run on the merged weights.

Ops floor (τ = 0.80, fine-tuned Laya as the working engine): 69.4% straight-through (347
claims, $2.29M), every auto-approved claim correct on all seven decisions (347/347), one fraud
claim below threshold (the τ-slider's cautionary tale), $1.21M fraud-$ flagged with $0
false-flagged.

v1 comparison (3-question era, same corpus seed): 37.8% / 100.0% / 74.1%. Study context: on the
prior sealed corpus Laya-ft beat the adapted 8B CLM model on every endpoint
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
