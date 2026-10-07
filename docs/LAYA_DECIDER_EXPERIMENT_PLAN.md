# Laya + decider-4b registered experiment plan — Revision 1

Status: registered before any sealed-split generation or model execution. Registered bytes SHA-256 recorded in `LAYA_DECIDER_EXPERIMENT_PLAN_REGISTERED.txt`.
Author environment: `ai-dev` distrobox, RTX 5090 32 GB, driver/host frozen at G0.

## 0. Scope and subjects

Comparative decision-model study with two subjects and one frozen anchor:

- **S1 — Laya** (Convai Innovations, Apache-2.0): all three bundled checkpoints via the official `Router` — `laya` (ModernBERT-large 421M, ctx 512), `multilingual` (mmBERT-base 322M, ctx 1024), `typed-decisions` (ModernBERT-large 421M, ctx 1024). Pinned HF revision recorded at G0.
- **S2 — decider-4b v2.1** (Mapika, Apache-2.0): bf16 weights (8.4 GB) via `decider-ai`, plus the `decider-4b-GGUF` Q4_K_M arm (2.7 GB) served by the pinned llama.cpp b10991 build already on this machine.
- **Anchor — CLM-8B**: frozen results from `reference-adaptation-20261005T041455Z` (published-heads 25.55% sealed ID; adapted seed-11 98.46% ID / 69.99% shifted; serving matrix; matched-generator comparison). CLM-8B is **not re-measured** except optional coexistence/memory checks in G3.

Non-goals: reproducing maker benchmark claims (JevBench, Decision Index, MASSIVE); multilingual breadth studies; vision variants; training any decoder from scratch; business recommendations before G2 completes.

## 1. Objectives and endpoints

1. **Primary (quality)**: sealed ID accuracy and mean-workflow macro-F1 of each subject's *published zero-shot* arm and *adapted* arm on the sealed corpus of §5, compared pairwise against the frozen CLM-8B anchor rows on the same families.
2. **Secondary (calibration)**: 15-bin ECE and Brier score per question type (choice/score/noul), reported separately from accuracy; option-order sensitivity (shuffle control) per subject.
3. **Tertiary (serving)**: p50/p95 latency, decisions/s, VRAM/RSS, cold-load and exact-repeat cache behaviour across the §7 matrix, including the decider llama.cpp GGUF equivalence gate.
4. **Comparison (features/capabilities)**: contract-level feature matrix (context caps, option limits, languages, caching surfaces, portability) validated by measurement, not documentation.

## 2. Preregistration discipline

- This plan's original bytes are hash-recorded before split generation. Any amendment becomes a numbered `*_AMENDMENT.md` with its own SHA; no silent edits.
- Sealed ID/shifted splits generated once by the fixed generator (§5), committed by receipt, opened exactly once by the authorized evaluator after model choices freeze. No test-driven model selection: checkpoint, temperature, and fine-tune recipe selection use validation splits only.
- Failed runs stay failed in the ledger; measurement-only repairs must preserve frozen artifacts and record before/after evidence.

## 3. Environment freeze (G0)

| Item | Pin |
|---|---|
| Box | `ai-dev` distrobox (archlinux), existing placement guards reused |
| Python envs | `/opt/ai-tools/venv-laya`, `/opt/ai-tools/venv-decider` (new, uv-created, pinned python) |
| `laya` PyPI | version recorded at install; HF hub revision SHA for `convaiinnovations/laya` |
| `decider-ai` PyPI | version recorded; `Mapika/decider-4b` revision `v2.1` main + `decider-4b-GGUF` file SHA-256 |
| llama.cpp | existing `llama-b10991` build (commit `930e2fa59`, build b10991) — same binary the CLM-8B study pinned |
| Anchor | `final-selection-manifest.json` SHA `c3d30d0e…` and frozen predictions from the CLM-8B RUN root |
| GPU/driver | recorded via `nvidia-smi -q` snapshot at G0 |

## 4. Contract tests (G1)

Per subject, before any corpus work:

- Request/response schema round-trip: choice / score / noul; multi-question single pass; JSON-state inputs.
- Option-count guardrails: Laya choice schemas capped at 20 options (documented collapse beyond); decider 2–255. Verify behaviour at boundary (2, 20, 21, 255 where applicable).
- Context caps: truncation behaviour at stated limits; record effective token budgets.
- Temperature semantics: decider per-type map (choice 1.110 / noul 1.560 / score 1.287) vs global override; Laya fitted scalar. Confirm served probabilities change, argmax does not (decider documented invariant).
- Determinism: same input twice → identical probabilities (fp tolerance 1e-6 in-process).
- TypeSafe `/v1/systemone` compatibility check for decider's HTTP server; Laya Router script-routing decisions audited on a fixed 20-language probe set.

## 5. Data

- Corpus contract: the CLM-8B study's generator (v1.1.2) family/workflow structure (support + infrastructure workflows, 24-candidate grids) converted to option-schema form: each family yields one state plus typed questions whose options are the candidate texts (≤20 options per Laya budget; full 24 for decider documented as an over-budget cell for Laya).
- Splits: 12,000 training rows / 3,000 families (adaptation arms only), 2,000 validation, sealed 4,000 ID families + 2,000 shifted families, mirroring prior counts for anchor comparability.
- Generation frozen (prompt/parser/profile/subset) before any subject inference; manifests hashed.

## 6. Arms

| Arm | Laya | decider-4b v2.1 |
|---|---|---|
| Published zero-shot | base checkpoints, maker temperatures | v2.1 with stored per-type map |
| Adapted | official fine-tune path on train split (Kaggle-notebook recipe), recipe selected on validation | temperature + per-type refit on train split only (no weight updates; B300-scale retraining out of scope — recorded as an adaptation asymmetry when comparing to CLM-8B head adaptation) |
| Controls | option-order shuffle; constant-majority; random-head where trainable | option-order shuffle; constant-majority |

CLM-8B anchor rows (published + adapted seed-11) are reused frozen; no new CLM inference in G2.

## 7. Serving matrix (G3)

Cells per subject × cache regime {uncached, options-warm/states-new, exact-repeat} × placement {GPU bf16, CPU} ; decider additionally × {llama.cpp GGUF Q4_K_M}. 3 blocks × 1,000 measured requests, 50 disjoint warmups, seeded shuffled configuration order, fresh process per cell. Record p50/p95 per block, decisions/s, VRAM peak, host RSS, cold-load time. Generator coexistence check (frozen Qwen3.8-27B NVFP4 Q4_K_M setup) where memory permits.

**Gates**: (a) decider GGUF-vs-bf16 choice agreement ≥ 99.5% on a 1,000-item fixed probe with probability tolerance 1e-2 — the equivalence gate CLM-8B never passed; (b) no cell may OOM with the generator resident; failure of (a) reverts GGUF to descriptive-only status.

## 8. Analysis

- Primary contrasts per endpoint: subject-zero-shot vs CLM-8B published; subject-adapted vs CLM-8B adapted seed-11. Newcombe method-10 paired-proportion intervals for accuracy; 10,000 crossed family/seed bootstrap draws for macro-F1 effects; one-sided workflow guards (support, infrastructure) at 97.5%.
- Multiplicity: two subjects × two arms × two endpoints pre-declared; Holm ordering fixed in the analysis script before unseal.
- Calibration (ECE/Brier) and order-sensitivity reported descriptively with bootstrap intervals; never merged into the accuracy endpoint.
- Shifted corpus descriptive only, as in the anchor study.

## 9. Deliverables

`LAYA_DECIDER_EXPERIMENT_REPORT.md` (results + feature/capability matrix vs CLM-8B), evidence root under `AI/catalog/decision-study/`, updated research brief, optional Korean business presentation on explicit request.

## 10. Cost and provenance

All acquisition commands, package versions, revision SHAs, file hashes, wall times and energy samples recorded in the G0 ledger before G1 begins. Desktop workload preserved; no host package changes without fresh entry records, matching prior-study placement discipline.
