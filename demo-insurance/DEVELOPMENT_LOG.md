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
17. Ops-floor overrides were mostly no-ops (operator report, 2026-10-21): the queue's "Flag fraud"
    stored a `flag` action the counters never read (anything not `auto` counted as review), "fraud $
    flagged" was computed from the model's probability alone (a fraud claim force-approved counted as
    both paid and held), and the queue showed only the 14 highest-p claims — all already in review,
    so "To review" could never change anything. The STP rule also compared the touches score with
    `<= 1` unrounded (Laya zero-shot 33 vs 151 straight-through). Fixed: three dispositions
    (auto-paid / flagged → SIU / adjuster review) drive every counter; views per engine disposition
    with stable rows, ↺ override marks, disabled current-action button, reset; rounded touches.
    Verified in the browser: each button moves the expected cards, reset restores 346/$1,205,920/68.
18. The Domain Builder did not land with an audience (operator review, 2026-10-28): no business
    reason to edit a cell in a 12 × 7 chip grid, "before" was an untrained model so *everything*
    differed and the taught change drowned in noise (0% → 47% all-7), and nothing could be tried
    afterwards. A design failure, not a crash. Replaced by v3 (Phase 10).
19. First live v3 re-teach crashed at the exam: the worker deleted `last-result.json`, then asked
    `engines()` for the re-taught model — which only loads once that file exists — and got None.
    Fixed: the worker installs the fresh engine itself. Caught by the first browser run, before
    any audience.
20. Two display bugs found in the same smoke run: the warning-sign list split "USD 18,500" at
    its thousands comma (split now needs ", " with a space); and the CTA bar showed on the Domain
    tab since Phase 8 because `.ctabar{display:flex}` beat the `hidden` attribute (global
    `[hidden]{display:none!important}`).
21. Measurement bookkeeping: the distrobox has its own `$HOME` (`~/.boxes/ai-dev`), so the first
    measurement runs wrote there; consolidating them overwrote the HR runs' `results.jsonl`, which
    was restored line-for-line from the run's console output. The script now defaults to
    `studio-runs/policy-measure/` in the demo tree.
22. The vanilla model was missing from the Domain Builder's live comparison (operator report,
    2026-10-28: "both model results are all the same for many scenarios"). The two columns were
    the production model and the re-taught model — identical by design on cases the new rule
    doesn't touch — while untrained Laya appeared only in step 1's precomputed numbers. Measured:
    untrained and production Laya agree on all 7 decisions for only 5 / 0 / 10 of 500 cases
    (support / logistics / HR). Fixed: `/studio/compare` also asks the untrained zero-shot Router
    already resident in the laya service (the engine behind the portfolio's out-of-box numbers),
    the panel shows out of the box · your model · re-taught · rulebook with a score chip each, exam
    tiles show the out-of-box score, and the result adds an out-of-box tile on the same exam
    (HR VIP run: 0/24 fully right out of the box vs 24/24 re-taught).
23. No way back to a fresh demo (operator, 2026-10-28): the re-taught model and its result
    persisted across reloads with no reset, and nothing on screen said whether a business was
    already re-taught. Added `/studio/reset {domain | "all"}` (token; 409 while training; deletes
    `ft-ckpt` + `last-result.json`, drops the engine — the production model is never written), a
    fresh/re-taught state bar with a reset button on each business page, a badge per business card
    and a "reset every business" button on the picker; `/studio/status`, `/health` and
    `/studio/domains` report what is active, so every open page re-syncs within ~2 s. Verified in
    two browsers: reset one → the other page switched to "Fresh start"; reset all → three fresh badges.
24. Claim-console clutter (operator, 2026-10-28) — see Phase 11. The removed top-bar scoreboard
    had counted every rerun of the same preset, so its percentages drifted with presenter
    clicks; per-claim k/7 chips replace it.
25. The ops floor had shown the insurance hero and two intros since Phase 6, and the domain page
    had shown two intros since Phase 10. Found in the site-wide revamp review and fixed.
26. `stop_demo.sh` could not see the live tunnel (found 2026-10-31 while parking the demo): it
    matched `cloudflared tunnel --url …`, but the tunnel runs as `cloudflared tunnel --no-autoupdate
    --url …`, so `--yes` would have left it running while printing "cloudflared stopped". Pattern now
    allows extra flags (checked read-only with `pgrep -f`; the script itself is not run on the live
    host). The demo was parked the same day — services stopped, `decision-demo.target` disabled,
    tunnel kept — and the park/restore runbook is DEMO_MANUAL §1 "Parking the demo".

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
   | **450 ×5, 2 epochs, mb 8 / ga 2 (default)** | **78–93 s** | **14–22/30** (support ×3, logistics, HR ×2; two driven from the browser via the tunnel: 88 s/14, 93 s/19) | 9–11/12 | 27.3 GiB |
   | old default: 1,500 ×20, mb 2 / ga 8 | ~11 min | 28–30/30 | 12/12 | 28.4 GiB |

   Every run's edit was learned. Zero-shot on the same fresh 30: 0/30 in every run. Live
   `/predict` under load: 0 errors, max 0.19 s. Findings: raised learning rates diverge at this
   step count; one epoch over twice the rows loses to two epochs; turning gradient checkpointing
   off buys only 8% for +2.1 GiB (not adopted — the wrapper trainer it needed was removed);
   same-config reruns vary by ±3–5 on the fresh 30, so ranges are quoted.
4. **Trade-off, stated plainly**: ~7–8× faster for roughly a third fewer fresh cases fully right
   (14–22/30 vs 28–30/30). The ~11-minute quality setting stays available via the env file
   (DEMO_MANUAL §3 operator notes).

## Phase 10 — Domain Builder v3: change one rule, watch the model change (2026-10-28)

Operator: "the domain page is boring — no definitive change between before and after, no clear
way to change the model interactively and see it behave differently. What would product sales
do?" Plan and reasoning: `docs/PLAN_DOMAIN_DEMO_V3.md`.

1. **Story**: your model today → change a rule → re-teach → what changed → try to break it.
   "Before" is now the business's *production model* (Laya trained once on its rulebook), so the
   only difference after a re-teach is the rule the room chose.
2. **Policy changes are rulebook edits** (`domain_factory.apply_policy`): reassign a category to
   another desk (routing), a tier's minimum urgency (urgency), warning signs needed for a review
   flag (routing, flag, money band, touches). New knobs `signals.flag_markers` and
   `urgency.tier_floor` default to today's rules — all three corpora regenerate byte-identical,
   and `decide()` replays 2,000/2,000 training and 500/500 test rows. Routing in `decide()` now
   picks the best category, then its desk (two categories may share one after a reassignment).
   The rule sentence is appended to the affected questions' instructions.
3. **Production checkpoints** (`train_prod_ckpt.sh`): 2,000 rows, 3 epochs, micro-batch 8 —
   437 / 433 / 424 s. Holdout all-7: support 487/500 (99.5% of decisions), logistics 498/500
   (99.8%), HR 493/500 (99.7%). Out-of-the-box Laya on the same: 5 / 0 / 10.
4. **Re-teach** = fine-tune from `prod-ckpt` on 300 changed + 300 unchanged rows relabeled by the
   rules engine. Measured on all 500 test rows (`measure_policy_teach.py`, results in
   `studio-runs/policy-measure/results.jsonl`):

   | business · rule | changed decisions before → after | untouched decisions after (prod) | all-7 before → after | train s |
   |---|---|---|---|---:|
   | support · account → T&S | 0/116 → 116/116 | 3,363/3,384 (3,365) | 372 → 490 | 49 |
   | support · Premium ≥ urgent | 0/107 → 107/107 | 3,362/3,393 (3,374) | 380 → 486 | 59 |
   | support · flag at 1 sign | 2/886 → 886/886 | 2,608/2,614 (2,604) | 261 → 496 | 61 |
   | logistics · customs → compliance | 0/111 → 111/111 | 3,372/3,389 (3,383) | 388 → 488 | 52 |
   | logistics · Premium ≥ urgent | 0/88 → 88/88 | 3,404/3,412 (3,406) | 410 → 496 | 46 |
   | logistics · flag at 1 sign | 0/843 → 843/843 | 2,655/2,657 (2,653) | 273 → 498 | 48 |
   | HR · conduct → ethics | 0/123 → 123/123 | 3,361/3,377 (3,366) | 371 → 488 | 61 |
   | HR · Premium ≥ urgent | 0/95 → 95/95 | 3,382/3,405 (3,394) | 399 → 491 | 59 |
   | HR · flag at 1 sign | 1/899 → 899/899 | 2,584/2,601 (2,593) | 257 → 485 | 54 |

   One pass, every changed decision learned; untouched decisions 99.1–99.9% (production model on
   the same: 99.4–99.9%) — a small, stated cost. Two passes (support, 93–101 s) learned the same
   and kept no more, so the default is one pass.
5. **Studio rewritten** (`studio_service.py`): `/studio/session` (rulebook, presets, baselines,
   showcase, last result), `/studio/impact` (CPU: what a rule changes + the 24-row exam with
   production answers cached once per checkpoint), `/studio/train {domain, policy}` (token),
   `/studio/compare` (both models + rulebook under both rules, open, one at a time, 409 while
   training). The zero-shot Router left the studio (its numbers come from the portfolio file):
   studio VRAM 7.0 → 4.5–4.8 GiB. New checkpoints train into `ft-ckpt.new` and replace `ft-ckpt`
   only on success. Removed with the old flow: teach-case stratification, cell edits, profile
   relabeling, the drift route, `/studio/presets`, `/studio/portfolio`, `/studio/predict`; the v2
   `ft-ckpt` directories were deleted.
6. **Console**: five-step page (sticky step bar), plain words ("your model", "the new rule",
   "tickets it never saw"), rule cards with dropdowns, instant impact, exam tiles that flip on
   the result, a facilitation prompt instead of an unmeasured "weeks" claim during the minute of
   training, side-by-side compare (untrained, trained and re-taught Laya plus the rulebook) with
   one-click edits and hand-written rewordings, watchers
   following a presenter's run (their page switches to the rule being taught), fine print with
   the table above. When the rulebook can't read a rewording it stops refereeing (no ✓/✗).
7. **Measured live** (full stack serving, via the tunnel, desktop and phone layouts): click →
   result 51–64 s over five runs; every changed exam decision right in every run (before 0);
   untouched 155/156 once, full marks otherwise; GPU peak 27.6 GiB for the whole card; `/predict`
   70/70 during a re-teach. Production models on the hand-reworded probes: support 0/3 fully
   right (16/21 decisions), logistics 3/3 (21/21), HR 2/3 (20/21); the rulebook can't read 26 of
   those 63 decisions.

## Phase 11 — Claim console revamp: one claim, side by side (2026-10-28)

Operator: make `day1`, `after` and `compare` "more organic, intuitive and less cluttered", using
BMad workflows. BMad was set up in the repo (`_bmad/`); the plan is
`_bmad-output/plan-claim-console-ux-revamp.md` and the UX spines are
`_bmad-output/ux-claim-console/{DESIGN,EXPERIENCE}.md`.

1. **Before**: three stat cards, a long preset list, a free-text box, per-engine cards each
   repeating seven questions with probability bars, a top-bar scoreboard that double-counted
   reruns, and a reveal button labelled "Train…" although training happened before the session.
   The audience had to scan two or four cards to find what changed.
2. **After**: a story strip (① pick a claim → ② Day 1 → ③ After → ④ Compare, done/now marks);
   compact preset chips (three per group, "+N more"), collapsing to "Claim: … · Change claim"
   once a claim runs; a claim card with the rule-relevant facts highlighted; ONE decision table
   for all three modes (rows = seven decisions by stage, columns = the mode's engines + the
   claims-manual answer, ✓/✗, k/7 chips) with a plain sentence on top — Day 1 "Out of the box,
   Laya gets 1 of 7; decider-4b gets 4 of 7", After "Training changed 6 of 7 decisions on this
   claim — 6 now match the claims manual" with "was …" under each changed answer, Compare "who
   gets 7/7". One toggle reveals confidence and probability bars (and rules evidence) for every
   cell. Measured numbers moved to a slim summary row; caveats to a fine-print disclosure. The
   reveal reads "Show the same claim after training on 12,000 past claims →" and runs the first
   preset when no claim was run. Phones get stacked per-decision cards and a scrolling tab row;
   `:focus-visible` rings and `prefers-reduced-motion` were added site-wide.
3. **Verified in the browser through the tunnel** (desktop 1366 and phone 390): day1 → reveal →
   after → compare on a fraud preset, a Korean preset (fine-tuned column shows the English-only
   note) and pasted text (no ✓/✗); no page-level horizontal overflow; zero page errors; ops
   counters and the Domain Builder render unchanged. Two review rounds fixed clipped chips, raw
   manual answers, per-cell "Details" clutter, the missing after-mode change sentence, the phone
   table, and a picker that pushed the table below the fold.

## Phase 12 — Site-wide look and feel (2026-10-28)

1. **Why**: the demo had grown mode by mode, leaving inconsistent styles and duplicated
   introductions across the claim console, ops floor and Domain Builder.
2. **What changed**: split the `index.html` monolith into a markup shell, shared `theme.css`,
   per-mode `console.css`, `ops.css` and `domain.css`, and classic scripts `core.js` →
   `console.js` → `ops.js` → `domain.js` → `main.js`; the laya service serves whitelisted
   assets at `/assets/` with no-store. Restyled every mode with one design system: a product
   header, tabs and one status pill with service details on hover or focus, one intro per mode,
   shared components and no decorative emoji. On phones the tab row scrolls, claim decisions
   stack as cards, and the ops queue stacks as cards with all three override buttons visible.
3. **How**: the BMad plan `_bmad-output/plan-demo-site-revamp.md` and UX spines
   `_bmad-output/ux-demo-site/{DESIGN,EXPERIENCE}.md` set the contract; four parallel
   restylers worked on disjoint files. Two corrective rounds removed the duplicated ops and
   domain intros and the insurance hero on ops, exposed phone queue override buttons, fixed
   claim-card highlight spacing, and removed the holdout sentence repeated on Day 1.
4. **Verified**: staging and live through the public tunnel at 1366 and 390 px, all five modes,
   zero page errors and no page-level horizontal overflow. The claim reveal showed "Training
   changed 6 of 7 decisions…"; an ops override moved counters and reset restored them; Domain
   Builder impact and compare showed out of the box / your model / re-taught. One live support
   desk VIP re-teach took 64 s click to result, with 12/12 changed decisions and 12/12
   untouched cases fully right, then reset to fresh. The laya restart took ~11 s; the tunnel
   was untouched.

## Final state at log time

- Services (systemd user units `decision-demo-{laya,decider,studio}`, target `decision-demo`):
  `laya_service.py` :8901 (console, zero-shot + fine-tuned laya, proxies `/dec/*` `/studio/*`,
  `/report`), `decider_service.py` :8902, `studio_service.py` :8903 — all bound to 127.0.0.1.
- Public URL (ephemeral quick tunnel): see `tunnel-url.txt`; refresh procedure in `DEMO_MANUAL.md` §2.
- Deploy: `sync_live.sh` from the repo; `VERSION` in the live tree = deployed commit.
- Console: `index.html` markup shell and shared/per-mode CSS and classic scripts under `assets/`.
- Data: `data/` (corpus + presets + measured `stats.json`); checkpoints `laya-ft-ckpt/` (served),
  `laya-ft-ml-ckpt/` (retained, unserved), `studio-runs/<domain>/prod-ckpt` (Domain Builder
  production models) and `ft-ckpt` (last re-teach).
- Headline measured numbers (500-claim holdout, 7 decisions): Laya 46.4% → 100.0% after the
  12k-claim fine-tune (1/500 → 500/500 all-7); decider-4b zero-shot 70.8% (21/500), LoRA 100.0%;
  rules 100.0% English / `unparsed` otherwise. Domain Builder re-teach: 51–64 s click to result;
  every decision the new rule changes learned (all 500 test rows, all nine presets); untouched
  decisions 99.1–99.9%; production models 0–3/3 on reworded probes.
