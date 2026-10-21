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
10. Comparator bug (Phase 7.6): laya score outputs are near-integer floats (1.0001); exact
    equality against integer gold failed every score question offline. Fixed in the offline
    comparators then — but **not** in the console (see #14).
11. **Live Teach OOM (2026-10-15 22:44)**: the first audience Teach died 7 s in with
    `train_cli exit 1`. Cause: CUDA out of memory — the studio process had grown to 5.3 GiB
    (allocator cache from anonymous domain-card session passes, never released; nothing was ever
    evicted), leaving 9.2 GiB free against a measured ~10.3 GiB training need. The Phase 7
    headroom had been 0.5 GiB, so any growth was fatal. Diagnosis was hampered by the studio keeping
    only the last 200 characters of each train_cli line in memory (the OOM line lost its head) and
    writing nothing to disk. Fixed in Phase 8 (full log per run, classified errors, pre-flight
    free-VRAM check, router unload before training, cached sessions, single resident checkpoint).
12. Preset labels described a *different* claim for 14/16 English presets since v1 ("kitchen fire"
    loaded a break-in): the generator forced only category + fraud flag, while the label was the
    intended description. Found by the Phase 8 review; labels are now derived from the generated
    claim (rng order untouched — train/val/holdout byte-identical).
13. Domain Builder relabel path was dead: training-row profiles were looked up in a dict keyed by
    *holdout* states, which never contain train states (0 matches in all three domains), so a
    presenter's edit never reached the 1,500 background rows — contradicting the plan and the
    on-screen badge. Also, the Phase 7 "59/60" figure was measured on the 12 taught cases plus a
    "fresh" sample that could overlap them. Fixed: profiles parsed from each train row's own text;
    the headline is 30 held-out rows excluding teach ids, with the zero-shot score on the same 30.
14. The console's ✓/✗ grader used exact float equality — the same bug as #10 in a third place:
    "Expected adjuster touches level 1.00 ✗ wrong" under gold 1 on the very first preset, and the
    domain tab's "watch them struggle" cards showcased correct answers as errors. One rounding
    helper now serves every console comparator.
15. **Integration incident (Phase 8)**: a sub-agent behaviour-testing the new `stop_demo.sh` ran
    it once without its sandbox port overrides; it pattern-killed the live laya/decider/studio and
    the cloudflared tunnel (public URL changed), and an earlier test line `pkill -f
    laya.train_cli` had already killed a running VRAM measurement. Fixed: `stop_demo.sh` is a
    dry run unless `--yes`, kills only PIDs it can attribute (port-scoped services, studio PID
    files), and the live stack now runs under systemd user units. Lesson: process-control scripts
    are tested by static checks or in a namespace, never by execution on the live host.
16. Warm-up race (found in Phase 9 benchmarking): a Teach pressed within ~25 s of a studio
    restart overlapped the background teach-case warm-up. The warm-up's zero-shot pass kept
    running after the studio unloaded the Router for training — lazily reloading it onto the
    GPU mid-train (total peak 31.2 GiB of 32.6 instead of 27.3) or tripping the free-memory
    pre-flight (a 503 at 8 s). Fixed: Teach waits for warm-up to finish; unloading waits for any
    in-flight post-teach reload.

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

## Phase 8 — Review-driven fixes: teach reliability, on-screen honesty, operations (2026-10-16)

Trigger: operator-confirmed working Domain tab → five independent reviews (buyer, UX, claims
audit, live ops, security) → `docs/PLAN_DEMO_REVIEW_FIXES.md` → executed by four implementers on
disjoint files under one API contract, integrated and measured live.

1. **Teach OOM diagnosed and fixed** (ledger #11): full per-run log, parsed progress
   (`epoch/step`), classified errors, pre-flight free-VRAM check (`TEACH_MIN_FREE_GIB` 11.5),
   zero-shot router unloaded and all taught checkpoints evicted before training, sessions cached
   (anonymous card clicks no longer touch the GPU; 409 while training), stale-job recovery from
   PID/job files. Decider offload (plan 0.6) proved unnecessary.
2. **Measured, full live stack serving + scripted `/predict` load** (2 threads, 0.5 s pacing):

   | run | train s | fresh 30 (zero → taught, all 7) | 12 taught (before → after) | probes | GPU peak | /predict under load |
   |---|---:|---|---|---|---:|---|
   | support, BG 600, 1 edit | 314 | 0/30 → 24/30 | 5/12 → 12/12 | 1/3 | 28.4 GiB | 1,138 req, 0 errors, p50 67 ms |
   | support, BG 1500, 1 edit | 661 | 0/30 → 29/30 | 5/12 → 12/12 | 0/3 | 28.4 GiB | 2,373 req, 0 errors, p50 66 ms |
   | logistics, BG 1500, 1 edit (UI-driven) | 652 | 0/30 → 28/30 | 0/12 → 12/12 | 2/3 | — | 2,197 req, 0 errors, p50 63 ms |
   | hr, BG 1500, no edit | 656 | 0/30 → 30/30 | 6/12 → 12/12 | 2/3 | 28.4 GiB | 2,354 req, 0 errors, p50 66 ms |

   The presenter's edit was learned in every edited run (edited case answered as edited, p ≥
   0.996) and propagated to 62–134 same-profile background rows. Halving background rows halves
   time but costs 5/30 on fresh cases — default stays 1,500 (~11 min). Headroom during training:
   ~4 GiB (was 0.5).
3. **On-screen correctness** (ledger #12–14): preset labels derived from the generated claim; one
   rounding comparator in the console; ops floor rebuilt (controls rendered once, engine selector —
   the fine-tuned engines are certain on every claim so τ is inert there and the screen says so;
   decider zero-shot STP 62.8% at τ 0.95 → 57.4% at 0.50); calibration chart retitled (fraud rate
   per bin, full engine names); rules engine answers `unparsed` to all seven questions on claims it
   cannot parse; teach headline = 30 held-out cases with their zero-shot baseline; edits relabel
   background rows for real.
4. **Honesty pass**: stat cards name the metric (avg per decision), show all-7-correct counts with
   Wilson 95% CIs, carry the in-template caveat wherever 100% appears; the year projection is
   "illustrative at this synthetic mix, routed to review"; cross-domain card reads "format +
   journey transfer" with all-7 rates; README/manual numbers regenerated from `stats.json`;
   footer links the served experiment report and shows the deployed `VERSION`.
5. **Presentation**: outcome line + call-to-action, ops as the cold-link default, compare-mode
   question × engine matrix, folded request/preset details, per-engine loading/unavailable states,
   lite portfolio payloads (3.1 → 1.8 MB, 2.6 → 1.6 MB), click-to-edit teach chips, progress bar,
   studio health dot, watchers see a running teach and its result, mobile scroll wrappers (no
   horizontal overflow at 390 px on any tab), tab ARIA roles + history, keyboard-reachable domain
   cards.
6. **Operations & security**: systemd user units (`deploy/`) now run the live stack; `sync_live.sh`
   (rsync + `VERSION` stamp) replaces hand `cp`; 64 KB body caps, JSON 400s, admission semaphores,
   generic error bodies, CORS limited to file:// and localhost, domain whitelist (path traversal
   closed), token compare constant-time with throttling, studio refuses to start without a token,
   decider request logging.
7. Incident during integration: ledger #15 (live stack and tunnel killed by a test; public URL
   changed).

## Phase 9 — Teach under two minutes (2026-10-21)

Operator: "if it takes ten minutes, too long — under 2 minutes max, e.g. 12k → 3k samples."

1. **Where the 11 minutes went** (per-line timestamps now in every train log): a teach row is a
   claim × 7 questions, so 1,740 rows (1,500 background + 12 cases ×20) were 11,780 items × 2
   epochs at micro-batch 2 ≈ 28 ms/item. Startup ≈5 s, calibration + saves ≈5 s, eval ≈1 s —
   the rest was the item volume at a batch size that left the GPU idle between tiny steps.
2. **Changes**: defaults 450 background rows + 12 cases ×5 (510 rows, 3,570 items), 2 epochs,
   micro-batch 8 / grad-accum 2 (≈11 ms/item, compute-bound); zero-shot "before" scores reuse the
   answers cached at warm-up instead of re-predicting; the zero-shot engine reloads after the
   result is published; the trainer's per-epoch `checkpoint_latest` copy (byte-identical, 808 MB)
   is deleted after each run; result carries `timing` and `config`; knobs `TEACH_UPSAMPLE`,
   `TEACH_ENCODER_LR`, `TEACH_HEAD_LR` added; ledger #16 fixed.
3. **Measured** (support tickets with one routing edit unless noted; live stack serving; script
   calling `/predict` once a second; GPU peak = whole card):

   | config | click → result | fresh 30 | taught 12 | GPU peak |
   |---|---:|---|---|---:|
   | 300 rows ×5, mb 8 / ga 2 | 62 s | 13/30 | 11/12 | 31.2 GiB (race, #16) |
   | 400 ×5, mb 8 / ga 1, lr 1e-4/5e-4 | 86 s | 5/30 | 4/12 | 27.3 GiB |
   | 600 ×5, 1 epoch, lr 1e-4/5e-4 | 74 s | 0/30 | 0/12 | 27.3 GiB |
   | 400 ×5, mb 8 / ga 1, default lr | 93 s | 16/30 | 11/12 | 27.3 GiB |
   | 1100 ×5, 1 epoch, default lr | 105 s | 17/30 | 11/12 | 27.3 GiB |
   | 550 ×5, 2 epochs, default lr | 96–107 s | 14–21/30 (3 runs) | 11–12/12 | 27.3 GiB |
   | 550 ×5, gradient checkpointing off | 88 s | 16/30 | 10/12 | 29.4 GiB |
   | **450 ×5, 2 epochs, mb 8 / ga 2 (default)** | **78–80 s** | **16–22/30** (support ×2, logistics, HR) | 9–11/12 | 27.3 GiB |
   | old default: 1,500 ×20, mb 2 / ga 8 | ~11 min | 28–30/30 | 12/12 | 28.4 GiB |

   Every run's edit was learned. Zero-shot on the same fresh 30: 0/30 in every run. Live
   `/predict` under load: 0 errors, max 0.19 s. Findings: raised learning rates diverge at this
   step count; one epoch over twice the rows loses to two epochs; turning gradient checkpointing
   off buys only 8% for +2.1 GiB (not adopted — the wrapper trainer it needed was removed);
   same-config reruns vary by ±3–5 on the fresh 30, so ranges are quoted.
4. **Trade-off, stated plainly**: ~8× faster for ~a third fewer fresh cases fully right
   (16–22/30 vs 28–30/30). The ~11-minute quality setting stays available via the env file
   (DEMO_MANUAL §3 operator notes).

## Final state at log time

- Services (systemd user units `decision-demo-{laya,decider,studio}`, target `decision-demo`):
  `laya_service.py` :8901 (console, zero-shot + fine-tuned laya, proxies `/dec/*` `/studio/*`,
  `/report`), `decider_service.py` :8902, `studio_service.py` :8903 — all bound to 127.0.0.1.
- Public URL (ephemeral quick tunnel): see `tunnel-url.txt`; refresh procedure in `DEMO_MANUAL.md` §2.
- Deploy: `sync_live.sh` from the repo; `VERSION` in the live tree = deployed commit.
- Data: `data/` (corpus + presets + measured `stats.json`); checkpoints `laya-ft-ckpt/` (served),
  `laya-ft-ml-ckpt/` (retained, unserved).
- Headline measured numbers (500-claim holdout, 7 decisions): Laya 46.4% → 100.0% after the
  12k-claim fine-tune (1/500 → 500/500 all-7); decider-4b zero-shot 70.8% (21/500), LoRA 100.0%;
  rules 100.0% English / `unparsed` otherwise. Studio teach: ~80 s click to result, 16–22/30
  fresh in-template (0/30 zero-shot), 0–3/3 reworded probes.
