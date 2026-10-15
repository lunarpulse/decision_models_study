# Journey C — The Domain Builder (demo v3): detailed plan (v2, review-revised)

**Goal:** let an audience pick a business domain (not insurance), watch a seeded decision corpus
generate instantly, watch the zero-shot engines struggle (cases selected from *measured*
zero-shot errors), then teach a small model live (real fine-tune, measured time) and watch the
scoreboard flip — with the in-distribution honesty visible on screen throughout. Positioned as
the onboarding path of a "custom decision engine in a day" business.

**v2 changes from independent review (DomainPlanReviewer, 2026-10-14):** studio training-data
pipeline specified (was blocking); eligibility archetype mapped per domain and loan_prescreen
deferred (was blocking); studio routes token-gated behind the public tunnel; train command
pinned to train_laya.sh flags with a row-cut (not fractional-epoch) fallback; build_portfolio
and rules_engine de-hardcoding made an explicit task with archetype→qid/meta maps; new domains
ship 2k train rows with SHA-digest CI; P1 re-budgeted 2–3 days for 3 domains; rng freeze and
renderer/regex pairing called out; struggle beat and paraphrases made measured/hand-written;
drift/re-teach beat added (retainer story); ops-floor money semantics made per-spec; labeling
UX reduced to bulk-accept + one deliberate edit.

## What exists today (all measured on this machine)

- `demo-insurance/gen_corpus.py`: seeded (rng 20261008), rule-verifiable corpus: 12k train /
  2k val / 500 holdout / 20 curated presets. 7 questions across 4 journey stages. CI enforces
  byte-reproducibility (regenerate + git diff).
- Engines: laya 421M (zero-shot Router; fine-tune = 14.5 min for 12k×3ep with
  `--loss soft-ce --shuffle-options` per train_laya.sh — the studio uses the IDENTICAL flag
  set), decider-4b (zero-shot, 8.4 GB), rules engine (insurance keyword/date parser, 100% EN,
  `unparsed` non-EN).
- Portfolio infra: `build_portfolio.py` → `portfolio_results.json` → ops floor. NOTE (review):
  it hard-codes insurance qids (`fraud_review`) and meta keys (`amount`, `fraud`) for
  calibration and money cards, and single DATA paths — de-hardcoding is a named P1 task.
- Services: laya_service (zero + ft ckpt, /rules, /portfolio), decider_service, console.
- GPU budget: live stack ~18 GB. Studio-train VRAM is **unmeasured** — measuring it (plus
  concurrent inference latency) is the first P2 action; until then no GB claim is quoted.

## Architecture

### 1. Domain spec (declarative factory)

`domain_factory.py` consumes a DOMAIN SPEC and emits: corpus (train/val/holdout/presets),
journey stages, question definitions, a spec-driven rules instance, and the maps consumers
need: `archetype→qid` and `meta_key` (flag question id, money field, gold-flag field).
Insurance becomes spec #1 — output **byte-identical** to today. Constraint (review): this is
only achievable if the insurance rng draw order is frozen exactly (make_row draw sequence,
15,480-row dedup loop, shuffle, preset force-attempts) — new domains use their own fresh
seeded rng streams and must not touch the insurance stream. P0's estimate reflects that
brittleness.

Spec shape — placeholders are **renderer/regex pairs** (each rendered shape declares its own
capture pattern; no regex-from-template automation), because real rendering is conditional
(e.g. the ≥18,500 "asks for the policy limit" amount variant, doc-phrase conditional on
docs_ok):

```python
DOMAINS["logistics_exceptions"] = {
  "rng_seed": 20261015,               # fresh stream, never the insurance seed
  "state": {"template": "...", "renderers": {"amount": [...variants w/ regex...], ...}},
  "categories": {...routing targets + things/docs vocab...},
  "signals": {...}, "params": {...deductibles, bands, urgency rules...},
  "questions": {  # 7 archetypes, domain-worded; qids are domain-specific
     "routing": {...}, "abuse_review": {"type": "noul"}, "urgency": {"type": "score"},
     "liability_eligibility": {...}, "recovery_band": {...},
     "carrier_recovery": {"type": "noul"}, "expected_touches": {"type": "score"}},
  "maps": {"archetypes": {"risk_flag": "abuse_review", "money_band": "recovery_band",
            "third_party": "carrier_recovery", "eligibility": "liability_eligibility", ...},
           "meta": {"flag": "abuse", "money": "amount"}},
  "stages": [...4 stages...], "money_cards": {...labels + aggregation per domain...},
}
```

Question archetypes (fixed, 7 slots): routing (choice), risk-flag (noul), urgency (score),
**eligibility (choice — mapped per domain, see table)**, money-band (choice),
third-party-recovery (noul), touches (score).

### 2. Domains to ship (launch = 3 + insurance; loan deferred)

| domain | eligibility slot (review-required mapping) | money band | third party | notes |
|---|---|---|---|---|
| insurance_claims (exists) | coverage_eligibility (as today) | net payable | subrogation | unchanged |
| support_tickets | refund_eligibility: eligible / outside_window / plan_excluded / review_needed | refund band after plan cap | vendor-caused fault | cleanest fit |
| logistics_exceptions | liability_eligibility: contract_active / not_active / peril_excluded / review_required | recovery band after deductible | carrier recovery | closest to insurance |
| hr_exceptions | exception_eligibility: within_policy / outside_window / capped / review_required | exception band (advance cap) | external vendor | reduced money cards (see §6) |
| ~~loan_prescreen~~ | — deferred: an eligibility answer on a loan is inherently a credit decision, contradicting the routing-not-credit framing | | | revisit only with a per-domain non-credit 7th-slot design |

Patient-triage stays excluded (clinical framing risk).

### 3. Spec-driven rules engine (Engine D generalization)

`rules_engine.py` refactors from insurance regexes to spec-driven: field parsers built from
the declared renderer/regex pairs + domain keyword tables + the spec's numeric rules.
Non-English remains `unparsed` per domain. Per-domain replay validator (generator gold
recomputed from raw state text) must reach 500/500 before a domain ships.

### 4. The Teaching Studio (live fine-tune; the heart)

**Training-data pipeline (review blocking fix, now explicit):** a session trains on
**~1,500 stratified corpus rows relabeled under the session policy + the 12 audience teach
cases repeated ×20**. The session policy starts as the spec's rule policy; the audience's
edits on the teach cases map to (a) rule-parameter deltas where they match a knob
(threshold/band/window — the common case) which then relabel the 1,500 rows, or (b)
case-level overrides that ride along up-sampled. So the audience's visible change materially
moves the training distribution, and the before/after flip is attributable to it.

- `POST /studio/session {domain}` → returns 12 teach-cases (stratified: 6 measured zero-shot
  errors, 6 random) with rule gold.
- Labeling UX (review fix for dead air): **one bulk "accept rule gold" action**, then the
  presenter deliberately edits ONE decision on ONE case (the policy-differs moment). Under a
  minute of audience time.
- `POST /studio/train {domain, edits}` → single-job queue → subprocess
  `.venv-laya/bin/python -m laya.train_cli --data session.jsonl --base convaiinnovations/laya
  --out studio-ckpt-{domain} --loss soft-ce --shuffle-options --epochs 1 --device cuda`
  (flag-identical to the measured baseline; **row-count cut is the timing fallback** —
  fractional epochs unverified and not relied on). Wall-time target ≤2.5 min, MEASURED at
  P2 start and displayed live.
- **Security (review fix):** studio mutating routes require a per-service-start session
  token shown only in the presenter console (or localhost-bind + flagged proxy); queue cap
  = 1 pending job; session creation rate-limited. The public tunnel otherwise exposes an
  anonymous GPU-job trigger.
- **GPU honesty (review fix):** first P2 action measures train VRAM + concurrent serving
  latency; while a train job runs the console annotates/hides latency badges (the 9–24 ms
  quote does not hold mid-train and must not be shown as if it did). Checkpoint eviction:
  only the active domain's studio ckpt stays resident.
- On completion: re-run the 12 teach-cases + a fresh 30-case holdout sample → before/after
  scoreboard, **annotated "same-generator holdout — see paraphrase probe"**, with the
  calibration-floor caveat (confidences sharpen; T stuck at floor — DEVELOPMENT_LOG ledger
  item 7) shown next to flipped probabilities. Then the **hand-written paraphrase probe**
  (2–3 per domain, authored in P1 — template-generated rewordings are explicitly NOT
  acceptable) that the freshly-taught engine may miss; labeling more (30) and retraining
  shows the data-quantity curve honestly.
- **Drift beat (retainer story, review fix):** "a year later" — age the corpus with one
  changed policy parameter (moved deductible/window), show the taught engine's measured
  errors on drifted cases, offer a 30-case re-teach. This is the recurring-revenue moment.

### 5. Console: Domain tab

New top-level tab "🏭 Domain builder". Screens: (1) domain cards (4 at launch), (2) generate
→ corpus stats + 3 sample cases **selected from measured zero-shot errors** (guaranteed
struggle by construction once P1 portfolios exist; no "measured" claim printed before they
do), (3) teach screen (bulk-accept + one deliberate edit + ⚡Teach + live progress),
(4) annotated before/after + paraphrase probe + drift beat, (5) per-domain ops-floor link.
Insurance stays the default; /domain/* endpoints are additive and never touch the insurance
serving paths.

### 6. Per-domain portfolios & money semantics

Offline once per domain: `build_portfolio.py --domain X` (de-hardcoded: DATA path
`data/{domain}/`, flag/meta via spec maps) → zero/dec/rules arms. **Money cards become
spec-defined** (labels + aggregation); where money is not honest (hr_exceptions) the ops
floor shows the reduced KPI set (STP rate, touches, unattended accuracy) instead of
fraud-$ semantics it cannot support.

**Repo weight (review fix):** new domains ship **~2k train rows** (the studio trains ~1.7k)
and commit val/holdout/presets as blobs; train.jsonl is CI-verified by committed SHA digest
instead of git-diffing the blob. Insurance corpus (63 MB) unchanged.

### 7. Business-model packaging

- Onboarding = the studio (measured anchors: 12k rows → 14.5 min laya / 71 min decider-LoRA;
  both 99.9–100% in-domain — always stated with the in-distribution caveat).
- Deployment: on-prem, open weights, no API keys, 9–24 ms decisions (idle-GPU figure).
  **License verification task (P3):** confirm convaiinnovations/laya and Mapika/decider-4b
  licenses on their model cards before printing "Apache-2.0" on a sales screen (decider-4b
  card states apache-2.0; laya to be re-verified).
- Retainer = calibration custody + the drift beat (§4): we publish our own calibration
  floor; recalibration on drift is the recurring purchase.

## Workplan & sequencing (review-rebudgeted)

- **P0 (0.5–1 d):** spec schema incl. renderer/regex pairs + archetype/meta maps; factory
  refactor with frozen insurance rng order (byte-identical output, CI green); replay
  validator generalized.
- **P1 (2–3 d):** 3 domain specs + hand-written vocab (~40 rows each) + eligibility mappings;
  rules-engine generalization + 500/500 validators ×3; corpora (2k/2k/500) + presets;
  hand-written paraphrases (2–3 per domain); per-domain zero/dec/rules portfolios (~20 min
  GPU total incl. decider loads).
- **P2 (1–1.5 d):** measure train VRAM + concurrent latency FIRST; studio service
  (token-gated, single-job queue, subprocess isolation, ckpt hot-swap + eviction);
  session-policy relabeling pipeline; console teach screen + annotated scoreboard +
  paraphrase + drift beat; domain tab.
- **P3 (0.5 d):** presenter arc; DEVELOPMENT_LOG; README; license verification; commit/push;
  CI extension (per-domain reproducibility: git-diff for val/holdout/presets, SHA-digest for
  train.jsonl).

Risks (top): train wall-time >2.5 min → row-cut fallback (guaranteed mechanism); studio
train degrades live serving latency → measured, annotated, and the presenter arc schedules
teach during talk beats; rng-order trap in P0 → byte-diff CI catches immediately; domain
vocab realism → user + reviewer pass on phrasings before ship.

Success criteria: 4 domains (insurance + 3) generate reproducibly under CI; each new domain's
replay validator 500/500; studio end-to-end (pick → generate → bulk-accept + one edit →
train ≤2.5 min MEASURED → annotated flip → paraphrase probe → drift beat) works behind the
tunnel with token-gated mutating routes and without disturbing 8901/8902; train VRAM and
concurrent-latency numbers recorded in DEVELOPMENT_LOG; docs updated; all committed.
