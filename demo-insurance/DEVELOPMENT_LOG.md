# Development log — Insurance-claims live demo (session record)

Covers the demo build sessions of 2026-10-07 → 2026-10-08, including the operator's questions,
the answers given, and every measured result and retained failure. Companion documents:
`DEMO_MANUAL.md` (operations & presenter guide) · `README.md` (technical notes) ·
`../LAYA_DECIDER_EXPERIMENT_REPORT.md` (the underlying study).

---

## Phase 1 — Request and design

**Operator request (verbatim intent):** build a live demo with laya/decider on an insurance-company
claims user journey; use the 12k-training-deck concept; show performance before vs after
fine-tuning; design it so a non-technical audience can observe what is asked and what is returned,
and "feel" how the models perform on real business use cases.

**Built:**
- `gen_corpus.py` — seeded synthetic claims corpus with rule-computed gold answers
  (routing / fraud flag / urgency, mirroring the study's question types):
  12,000 train + 2,000 validation + 500 holdout + 20 curated presets (16 English incl. 4 fraud
  scenarios, 4 multilingual: Korean, Japanese, Hindi, Spanish).
- `laya_service.py` (:8901) — zero-shot Router + fine-tuned checkpoint(s) behind one HTTP API;
  `decider_service.py` (:8902) — decider-4b v2.1, always untrained (Engine C's role by design).
- `index.html` — audience console: "what we asked" (exact request) and "what came back"
  (answer + probability bars + confidence + latency + ✓/✗ vs the claims manual), free-text box,
  live per-engine scoreboard, measured-study stat cards.
- Fine-tune of the English checkpoint: `laya-train` (soft-ce, `--shuffle-options`, 3 epochs, ~15 min
  on this machine). Retained failure: first run rejected all 12,000 rows (`invalid_target`) —
  plain labels must be passed under `expected`, not `gold`; conversion recorded.

**Measured through the live services (500-claim holdout):**

| Engine | Per-question accuracy | Rows all-3-correct |
|---|---:|---:|
| Laya out-of-box | 37.8% | 0/500 |
| Laya fine-tuned (12k) | **100.0%** | **500/500** |
| decider-4b (no training) | 74.1% | 256/500 |

Verified in a browser: preset run → verdict chips; reveal flow; free text → "no rule answer".

## Phase 2 — Two-era experience (operator interjection)

**Operator question:** can we serve two instances — before fine-tune and after fine-tune — so the
~15-minute fine-tune never runs in front of a busy C-suite? Fine-tune before the session; let the
audience experience the difference. "Engineer the audience experiences."

**Answer/implementation:** both eras already coexist in one service process (checkpoints ~0.8 GB
each; ~10 GB VRAM total with decider). Re-engineered the console into an authored arc:
- **Day 1 tab** — untrained engines only; run claims and watch out-of-box Laya fail (e.g., fraud
  preset: wrong YES at 70.6%).
- **The reveal button** — "⚡ Train on 12,000 past claims — and re-run this claim": switches era and
  re-runs the *same* claim on the trained engine (all correct, sharp probabilities).
- **After tab** and **side-by-side Compare tab** with per-engine live scoreboard.
Verified end-to-end in-browser (fraud preset: Day-1 all wrong → after-training `special_investigations`,
`YES p=100%`).

## Phase 3 — Manual, public hosting, multilingual

**Operator questions:** where are the demo manuals (start/stop/what to show)? Can we bind 0.0.0.0
and host via cloudflared so others can test online? And why did multilingual claims "all fail after
fine-tune" — did fine-tuning damage Laya's multilingual capability?

**Answers & work:**
- `DEMO_MANUAL.md` (operator/presenter guide: start/stop, 8-minute show arc, quotable numbers,
  Q&A cheatsheet, troubleshooting) + `stop_demo.sh`.
- Services re-bound to 0.0.0.0; console made same-origin aware; decider proxied through :8901 so a
  single tunnel origin serves everything; cloudflared 2026.10.0 quick tunnel stood up —
  public URL verified end-to-end (page + both predict routes).
- **Multilingual explanation (with evidence):** nothing was damaged. The fine-tune was applied to
  the *English-only* ModernBERT checkpoint (50k-token English vocab shreds non-Latin scripts —
  the study quotes the maker's sweep: Khmer 0% accuracy at 0.95 confidence). Laya's multilingual
  ability lives in a separate mmBERT checkpoint that our fine-tune never touched; the demo was
  showing an honest "English-only" note rather than guessing.
- **Fix attempted:** fine-tuned a second checkpoint from the multilingual base on the same English
  12k (11 min) and auto-routed by script. Retained measurement on the 4 multilingual presets:
  mixed — Korean/Japanese improved (2 urgency errors fixed), Hindi regressed (1), 8/9 vs the
  zero-shot 7/9. English-only supervision transfers cross-lingually only partially.

## Phase 4 — "Accuracy went down to 91%" (operator observation)

**Operator question:** if multilingual fine-tune degrades the English fine-tune's performance,
prefer showing the English-only fine-tuned model as before — "I see laya accuracy went down to 91%
from 100% (actually 100 percent is absurd..). Why did the multilingual fine-tune degrade Laya?"

**Answer (measured, not asserted):**
- The English checkpoint had **not** degraded: fresh 500-row holdout re-run — 100.0%, 500/500
  (unchanged; it is a separate file nothing touched).
- The 91% was scoreboard contamination from a **routing gap**: script detection only caught
  non-Latin scripts, so the **Spanish preset (Latin script) was answered by the English fine-tuned
  checkpoint** — which scored 1/3 where the untrained base scored 2/3. Those misses landed in the
  live tally.
- Mechanism: fine-tuning to zero loss on templated English narrows the model
  (catastrophic forgetting of off-distribution inputs). The same force that lifts 44%→100%
  in-domain strips the base's language robustness.
- On "100% is absurd": correct as a *deployment* claim; it is the expected i.i.d. ceiling of a
  rule-labeled synthetic family (the anchor study's adapted CLM showed the same shape at 98.46%).
  The planning number is the unseen-distribution figure (92% on the study corpus). The manual's
  Q&A already forbids quoting 100% as a promise.
- **Action taken per operator preference:** Engine B reverted to English-only; non-English claims
  (preset language tags + script detection) get an explicit note citing the measured 1/3-vs-2/3
  robustness loss, and Engine A's zero-shot multilingual checkpoint answers them. Multilingual
  fine-tuned checkpoint retained on disk (`laya-ft-ml-ckpt/`), not served. Verified live:
  Spanish/Korean → note; English → answers; stats regenerated (37.8 / 100.0 / 74.1).

## Phase 5 — "It does not seem to do anything" (operator report)

**Operator questions:** check the services — they occupy RAM but nothing happens; test actual
inferences with the demo scenes (explain in Korean). Then: what do the top-bar items mean, where
does the percentage come from, and why does decider show a red dot — "check the real service now."

**Findings & fixes:**
- Services were healthy (processes, ports, GPU residency, tunnel) and every inference path tested
  clean on real presets: English 176 ms, fraud ft-correct at 79 ms, Korean 14 ms (routed
  multilingual), decider proxy 30 ms, tunnel 155–163 ms.
- **Root cause 1 (page hang):** the console's fetches had no timeout — a request issued during a
  service restart could pend forever with the Run button stuck disabled ("occupies RAM, does
  nothing"). Fixed with `AbortSignal.timeout(60000)`; deployed to localhost and tunnel.
- **Root cause 2 (red dot):** the page polled decider health at `/dec/predict/health` — a URL that
  never existed through the proxy — so a working service showed red. Fixed by adding a
  `/dec/health` proxy route and correcting the page's poll base (`DECBASE`). Verified green on
  both origins after hard reload.
- **Top bar explained:** dots = 15-second service health polls; percentage cells = live scoreboard
  of preset-claim verdicts for the current page session (free text excluded; Reset/reload clears);
  the three fixed stat cards = the pre-session measured study numbers. The operator's observed
  44% (4/9) / 100% (9/9) / 67% (6/9) matches 3 English presets run in Compare mode and is
  consistent with the measured 37.8/100/74.1.

## Engineering failure ledger (all retained, none hidden)

1. `laya_service.py` lost its `__main__` server-start block in an edit → loaded engines then exited
   cleanly (looked healthy in logs). Restored; lesson: verify *serving*, not just loading.
2. Same file: success-path response line eaten by an edit → `UnboundLocalError` on first predict.
   Restored; caught by an actual inference test, not health checks.
3. `decider_service.py`: `port` assignment eaten by an edit → `NameError` at startup. Restored.
4. Orphaned-process incident (from the study phase, same machine): harness job-kill removed bash
   wrappers only; three generations of Python workers kept running (load 36/24) and polluted two
   GPU latency cells before being killed by PID. Retaken on an idle machine.
5. Fetch hang + wrong health URL (Phase 5, both fixed).
6. Latin-script language gap routed Spanish to the English fine-tune (Phase 4, fixed by
   language-tag + script policy).
7. Training warning (both fine-tunes): noul (yes/no) calibration fit stayed at 1.0 — the trained
   engines' yes/no confidences are uncalibrated; the console therefore displays probabilities,
   not just argmax, and the manual flags recalibration before real thresholds.
8. Decider-LoRA save bug (v2): `inject_adapter_in_model` leaves projections wrapped as
   `q_proj.base_layer`, so `save_pretrained` wrote wrong key names — the saved checkpoint
   reloaded with **randomly initialized projections** (29.5% on presets, silent except for a
   transformers MISSING-keys warning). Caught because the presets eval ran before celebrating;
   recovered without retraining by rewriting the state-dict keys (drop `.lora_*`, strip
   `.base_layer`, remap the `model.language_model.` prefix) — after which the same checkpoint
   scored 140/140. Trainer fixed to restore base module names before saving.
9. The full decider fine-tune launched with bare `nohup … &` died ~60 s in, silently, when the
   tool call's process group ended (no step ever logged). Relaunched as a managed async job.
   Lesson already in the ledger's spirit: a launch is not a run — verify the first log lines.

## Phase 6 — Demo v2: journey questions, ops floor, Engine D, decider parity (2026-10-13)

Goal set by operator: make the demo *realistic and business-attractive*, and fine-tune the local
decision model to maximize its value. Research pass (industry KPIs: leakage, STP rate, cycle
time, touches/claim; McKinsey/CLARA/SAS framing) shaped four tracks: full claim journey, money
layer, STP/adjuster ops floor, rules-engine baseline — plus supervised parity for decider-4b.

1. **Corpus v2** (`gen_corpus.py`): four new rule-verifiable questions — coverage eligibility
   (policy-active date logic, 2-day review window, flood/tier exclusion), net payable band
   (deductible arithmetic per line), subrogation (identified third party), expected adjuster
   touches (complication count, fraud → 4+). Journey stages emitted in `demo_presets.json`.
   Independent validation: a *text-replay checker* (regex/date parse of the claim text, no
   generator internals) reproduces generator gold **500/500 rows, all fields**. Hindi preset
   amount adjusted 18,500→17,500 (the original fell under the fraud rule by two markers — the
   curated "clean high-value" story was inconsistent with the written rule).
2. **Engine D** (`rules_engine.py`, served at `/rules`): the incumbent implemented honestly —
   the same written policy via keyword/date parsing, every answer carrying its evidence
   (audit trail). **100.0% on the English holdout** (it must be: the rules are the gold
   generator) and `unparsed` on non-English input — the incumbent's real shape, shown in the
   console rather than argued.
3. **Ops floor** (`?mode=ops`): money cards, confidence-threshold slider driving STP counters,
   adjuster queue with approve/flag/review overrides, per-engine calibration strips, ROI
   annualization input. Backed by `build_portfolio.py` — all arms measured once on the sealed
   holdout (offline, study-style), written to `portfolio_results.json`, served at `/portfolio`.
4. **Console failures found and fixed during v2**: `MODE_ENGINES` missing the `ops` key made
   `renderEngineCards` throw mid-`setMode` (ops floor silently blank — the pageerror listener
   never surfaced it; found by DOM-trace instrumentation); TDZ bug (`setMode("ops")` ran before
   `let OPS` initialized); boot line (`const m = …`) lost in an edit.
5. **VRAM sequencing**: portfolio builder originally loaded decider *after* the laya arms and
   OOM'd (live stack 18 GB resident); reordered to load/free the 8.4 GB decider first.

## Phase 7 — Domain Builder (demo v3): plan → independent review → factory, three domains, live studio (2026-10-15)

1. **Plan reviewed independently** (`docs/PLAN_DOMAIN_BUILDER.md`, v2): a reviewer agent found two
   blocking flaws (unspecified studio training pipeline; eligibility archetype unmapped — the loan
   domain forces a credit decision) and majors (open GPU-job trigger behind the tunnel, unmeasured
   VRAM claims, flag-set divergence from train_laya.sh, hard-coded qid/meta couplings). All folded
   in: loans deferred, studio token-gated, timing/VRAM measured not asserted, factory domains ship
   2k train rows with SHA-digest CI.
2. **Domain factory** (`domain_factory.py` + `domains.py`): insurance generator left untouched
   (rng order frozen); new domains use fresh streams and a canonical draw order. Shipped
   `support_tickets`, `logistics_exceptions`, `hr_exceptions` — same 7-archetype journey,
   domain-worded. Replay validators: **3500/3500 (500/500 per question set) for each domain**,
   now enforced in CI alongside byte-reproducible regeneration.
3. **Unplanned finding — cross-domain transfer**: the decider-4b LoRA trained *only on insurance*
   scores 81.4% / 93.3% / 89.9% on support / logistics / HR holdouts (zero-shot: 60.7% / 69.7% /
   70.9%). The 7-archetype journey transfers; one supervised domain buys most of the next ones.
4. **Teaching Studio** (`studio_service.py`, :8903, localhost; proxied through :8901): session →
   12 stratified teach cases (6 measured zero-shot errors + 6) → bulk-accept + deliberate edit →
   real fine-tune (train_cli, flag-identical to train_laya.sh, `--micro-batch 2 --epochs 2`,
   subprocess with expandable segments) → before/after eval + paraphrase probes + drift beat
   (deductibles doubled → measured decay → re-teach = the retainer story).
5. **Measured (this machine, live stack resident)**: teach-case session 15 s; training
   162 s/epoch at micro-batch 4 (1 epoch under-trained: 6/12), 2 epochs at micro-batch 2 ≈ 10 min
   wall — over the plan's 2.5-min target; VRAM peak 32.1 GiB of 32.6 (zero headroom — the
   micro-batch reduction buys ~1 GiB); live insurance /predict during training stayed in the
   tens of ms. The taught checkpoint scores **59/60 on the support-tickets holdout** (12 cases +
   1,500 corpus rows, 2 epochs) and **0/3 on the hand-written paraphrase probes** — the honesty
   beat works: in-template perfection, out-of-template humility.
6. **Comparator bug, found the hard way (ledger #10)**: laya emits near-integer score floats
   (1.0001); exact-equality against int gold silently failed *every* score question — the first
   studio eval read 0/12 while the model was near-perfect, and the insurance portfolio's "497/500"
   was the same artifact (truly 500/500). Fixed with rounding in every comparator; all portfolios
   rebuilt. Lesson: when an eval reports exactly-zero agreement, suspect the comparator before the
   model.
7. Also fixed en route: session returned 6 cases not 12 (zero-shot almost never gets all 7 right,
   so the "all-correct" pool was empty — fill from the error pool); studio died twice under the
   tool-call process-group reaper (relaunched as a managed service — same lesson as ledger #9);
   edited teach-cases were scored against the rule gold instead of the edited policy (the model
   had *learned* the edit; the eval hadn't).

## Final state at log time

- Services: `laya_service.py` :8901 (zero-shot Router + English fine-tune; 0.0.0.0; serves console,
  presets, stats, decider proxy) · `decider_service.py` :8902 (0.0.0.0).
- Public URL (ephemeral quick tunnel): see `tunnel-url.txt`; refresh procedure in `DEMO_MANUAL.md` §2.
- Start/stop: `start_demo.sh` / `stop_demo.sh`.
- Data: `data/` (corpus + presets + measured `stats.json`); checkpoints `laya-ft-ckpt/` (served),
  `laya-ft-ml-ckpt/` (retained, unserved).
- Headline measured numbers: **37.8% → 100.0% (Laya, 12k-claim fine-tune) · 74.1% (decider, zero
  training)** on the 500-claim holdout; language-robustness finding: English fine-tune 1/3 vs base
  2/3 on a Spanish claim.
