# Insurance-claims live demo — decision console

Audience-facing demo of the study's engines on an insurance-claims user journey.
Insurance fine-tuning happens **before** the session (`bash train_laya.sh`); the Domain Builder tab
changes one rule of a business's rulebook and re-teaches that business's production model live
(studio service, presenter-gated, 51–64 s click to result). Five tabs: day1 · after · compare · ops · domain.
Every mode shares one design system, documented in [`_bmad-output/ux-demo-site/`](../_bmad-output/ux-demo-site/).

## Start

```bash
cd demo-insurance && bash start_demo.sh
```

Then open **http://127.0.0.1:8901/** (ops floor; `?mode=day1` for the narrated opener). The laya
service serves the console itself.

Services: `laya_service.py` :8901 (zero-shot Router + fine-tuned checkpoint, console, proxies) ·
`decider_service.py` :8902 (decider-4b v2.1) · `studio_service.py` :8903 (Domain Builder: token-gated
re-teach, open side-by-side compare; needs `studio-runs/<domain>/prod-ckpt` from `train_prod_ckpt.sh`).
Supervised operation (systemd user units, `sync_live.sh`, logs, pre-show checklist): see
`DEMO_MANUAL.md` §1 — including "Parking the demo" (free the GPU, keep or stop the tunnel, bring it back).

## The audience experience (engineered flow)

1. **Pick a claim** from compact standard, fraud or multilingual chips (three per group, "+N more" expands), or expand
   **paste your own claim**. The selected claim card highlights policy type, dates, amount and
   documents; the story strip tracks Pick → Day 1 → After → Compare.
2. **Day 1** runs that claim in one seven-decision table: Laya out-of-box and decider-4b beside
   the claims-manual answer, with ✓/✗ and per-engine scores out of seven. The holdout summary
   reports 46.4% average per decision and 1/500 all-seven for Laya, versus 70.8% and 21/500
   for decider-4b.
3. **Reveal** with **"Show the same claim after training on 12,000 past claims →"**. After
   re-runs the same claim and highlights fine-tuned answers that differ from Day 1, with
   "was …" for the earlier answer. Training took about 15 minutes before the session, not
   during the reveal. Without a prior run, reveal selects and runs the first preset. Fine-tuned
   Laya measured 100.0% average per decision and 500/500 all-seven on the holdout.
4. **Compare** shows Laya out-of-box, Laya fine-tuned, decider-4b and the rules engine together
   with the manual in the same table; rules evidence is available on demand. Rules measured
   100% for English phrasing only.
5. **Explore** multilingual presets (Korean, Japanese, Hindi and Spanish): out-of-box Laya
   answers and the fine-tuned column displays its English-only note. For pasted text without a
   manual answer, the table shows answers without ✓/✗ and asks the audience to judge.
   **Show confidence & probabilities** reveals bars for every cell at once; fine print holds the measurements'
   caveats.

## The Domain Builder (`?mode=domain`) — change one rule, watch the model change

Three businesses (support desk, logistics exceptions, HR exceptions), each with a written rulebook,
2,000 training and 500 sealed test cases, seven decisions per case.

1. **Your model today** — out-of-the-box Laya gets 5 / 0 / 10 of 500 cases fully right (support /
   logistics / HR); the same Laya trained once on the 2,000 (`train_prod_ckpt.sh`, ~7 min per
   business) gets 487 / 498 / 493.
2. **Change a rule** — three presets with editable values: send a whole category to another desk,
   give a tier a minimum urgency, flag at 1 warning sign instead of 2. The rules engine re-decides
   every case under the new rule and shows what changes, plus a 24-case exam (12 changed, 12 not).
3. **Re-teach** — fine-tunes the production model on 300 changed + 300 unchanged relabeled cases,
   one pass; the new rule is also written into the question text.
4. **What changed** — the exam flips: today's model follows the old rule, the re-taught one the new.
5. **Try to break it** — any case, Laya out of the box, your model and the re-taught model side by
   side with the rulebook as referee; one-click
   edits (tier, evidence, amount, start date, category) and hand-written rewordings.

Measured on all 500 test cases per business and preset (`measure_policy_teach.py`): every decision
the rule changes is right after one pass (88/88 … 899/899, from 0–2 before); untouched decisions
stay 99.1–99.9% right (production model on the same decisions: 99.4–99.9%); 46–61 s of training.
Full table: DEVELOPMENT_LOG Phase 10.

## What the audience sees per run

- A highlighted claim card and one table of seven decisions grouped into four journey stages.
- The engines for the selected mode and a claims-manual column; answers carry ✓/✗ against the
  manual and engine score chips show correct decisions out of seven when a manual answer exists.
- Confidence and probability bars on demand; rules evidence on demand in Compare. After marks
  fine-tuned answers changed from Day 1 with "was …". Unavailable engines and unparsed rules
  are identified rather than mistaken for answers.
- A slim holdout summary and a fine-print disclosure for caveats, including Wilson confidence
  intervals, the in-distribution 100% result, English-only rules and uncalibrated confidence.
  For free text with no manual answer, answers appear without verdicts: judge them yourself.

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
- `index.html` — markup shell served at `/`
- `assets/theme.css` — shared design system; `assets/console.css`, `assets/ops.css` and `assets/domain.css` — per-mode styles
- `assets/core.js` → `console.js` → `ops.js` → `domain.js` → `main.js` — classic scripts sharing one scope, served at `/assets/`

## Retained caveats

1. `laya.train` warned the fine-tuned checkpoint's noul (yes/no) calibration fit stayed at 1.0 —
   yes/no confidences from the trained engine are uncalibrated (visible as very sharp probabilities;
   demo shows probabilities, not just argmax, so this is observable, not hidden).
2. The "via <checkpoint>" routing badge on engine A renders from the engine-level payload field.
3. All services bind 127.0.0.1 by default; the public path is the cloudflared tunnel to :8901.
   The studio's re-teach route needs the studio token; inference routes (including the Domain
   Builder compare) are open but size-capped and admission-controlled. GPU: 27.6 GiB peak for the
   whole card during a re-teach with every service resident.
