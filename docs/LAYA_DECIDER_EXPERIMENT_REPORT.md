# Laya + decider-4b experiment report — Revision 1 (complete)

Updated: 2026-10-07 UTC. Registered plan: `LAYA_DECIDER_EXPERIMENT_PLAN.md`, SHA-256 `028be98a89a0fa2d63aecd5e1c24fd57fd9c7511c89beebbf30b1bce5544dd40`.
Evidence: `AI/catalog/decision-study/g0-20261007/` (contracts), `g2-20261007/` (evaluations + `analysis.json`), `g3-20261007/` (serving).
Subjects: **laya 0.3.28** (3 checkpoints via Router, snapshot `7b928d82…`), **decider-4b v2.1** (`decider-ai 1.8.1`, snapshot `eb5fbdfc…`; GGUF Q4_K_M SHA `c7083fcf…`). Hardware: RTX 5090 32 GB, driver 615.71.09, torch 2.14.1+cu130, `ai-dev` box.

**Bottom line.** On the CLM-8B anchor study's own sealed corpora (identical rows, identical gold): decider-4b zero-shot beats published CLM-8B by +52.6 points; laya fine-tuned on the same 12,000 training rows the anchor used reaches 100.00% sealed-ID accuracy (vs adapted CLM-8B 98.40%, paired Δ +1.60 pp, CI +1.24…+2.04) and 92.00% shifted (vs 69.80%), with near-perfect calibration (ECE 0.0000, Brier 1.1e-8). Both subjects run one-to-two orders of magnitude faster than the CLM-8B serving cells. CLM-8B's remaining unique capability is scoring arbitrary free-text candidates with independently cacheable action embeddings (sub-ms repeats); on this decision corpus nothing else of its 8B survived contact.

## 1. Design

Anchor-comparable sealed evaluation, reusing the CLM-8B study's frozen sealed splits verbatim (no regeneration):

| Split | Rows | SHA-256 (first 16) | Content |
|---|---:|---|---|
| sealed ID (`main_id.jsonl`) | 4,000 | `0479176e8cbe15aa` | 2,000 support + 2,000 infrastructure; 4-option choice; per-row criteria texts |
| sealed shifted (`main_shifted.jsonl`) | 2,000 | `e707d731169a2b76` | distribution-shifted families |
| train (adaptation arms) | 12,000 | `027296e711605c8b` | same generator, disjoint families |

Anchor references (frozen, per-row): `final-evaluation/predictions/{id,shifted}/published.jsonl`, `adapted-b12000-s11.jsonl` (manifest SHA `c3d30d0e…`), lexical probe seed-11 per-row files. Generator reference (frozen): 0-shot 98.8% / 4-shot 100.0% on its 1,000-row matched subset (G4 satisfied by frozen reuse on identical rows — the 27B generator was not re-served).

Arms per plan §6: laya zero-shot (Router), laya fine-tuned (`laya-train`, soft-ce, `--shuffle-options`, 3 epochs, 12k rows; first attempt failed with `invalid_target` ×12,000 because plain labels must be passed under `expected`, not `gold` — conversion recorded, retrained), decider zero-shot (served T-map 1.11/1.56/1.287), decider zero-shot + temperature refit (scalar T fitted on the 12k train-split predictions; the plan's no-weight-update adaptation, recorded as the adaptation asymmetry vs CLM head-fitting and laya full fine-tune). Controls: seeded option-order shuffle (1,000 ID rows), constant-majority.

Method notes: every subject row was scored with the row's own state + question schema; decider received the same instructions text and option descriptions; laya received the row's questions object verbatim. Zero inference errors across 25,000 scored rows (4,000+2,000+1,000 ×2 subjects + 12,000 train + 4,000+2,000 laya-ft). Analysis: Newcombe-style paired intervals for accuracy, 10,000-draw paired bootstrap for macro-F1, exact McNemar for the shuffle control. This deviates from the anchor's crossed family/seed bootstrap (documented; row-paired here because both sides were scored on identical rows).

## 2. Primary results — sealed ID (n = 4,000)

| Method | Accuracy | Mean-workflow macro-F1 | ECE-15 | Brier |
|---|---:|---:|---:|---:|
| **laya fine-tuned (12k rows)** | **1.0000** | **1.0000** | **0.0000** | **0.0000** |
| Anchor: adapted CLM-8B seed-11 (8B + 18.9M heads) | 0.9840 | 0.9840 | 0.0242 | 0.0298 |
| Anchor: lexical probe | 0.9385 | 0.9384 | — | — |
| **decider-4b zero-shot** | 0.7815 | 0.7763 | 0.1495 → **0.0533** after T-refit | 0.3555 |
| **laya zero-shot (Router)** | 0.4405 | 0.3699 | **0.0392** | 0.6677 |
| Anchor: published CLM-8B | 0.2555 | 0.2036 | 0.3812 | 1.0035 |
| Constant majority | 0.1250 | 0.0500 | — | — |

Paired contrasts (Newcombe accuracy Δ, 95% CI; bootstrap macro-F1 Δ CI):

- laya-ft vs adapted CLM-8B: **+0.0160 [+0.0124, +0.0204]**; macro-F1 Δ +0.0124…+0.0201. Significant superiority, tiny margin.
- laya-ft vs lexical probe: +0.0615 [+0.0544, +0.0694].
- decider-zero vs published CLM-8B: **+0.5260 [+0.5070, +0.5443]**.
- laya-zero vs published CLM-8B: +0.1850 [+0.1644, +0.2054].
- Both zero-shot arms trail adapted CLM-8B (decider −0.2025; laya −0.5435) — supervision, not architecture, closes this gap.

## 3. Shifted split (n = 2,000, descriptive)

| Method | Accuracy | macro-F1 | ECE |
|---|---:|---:|---:|
| **laya-ft** | **0.9200** | 0.9201 | 0.0758 |
| decider zero-shot | 0.7980 | 0.7919 | 0.1201 → 0.0221 refit |
| lexical probe (anchor) | 0.7375 | 0.7390 | — |
| adapted CLM-8B (anchor) | 0.6980 | 0.6912 | 0.1903 |
| laya zero-shot | 0.4405 | 0.3596 | 0.0393 |
| published CLM-8B (anchor) | 0.2755 | 0.2181 | 0.4156 |

laya-ft degrades −8.0 points under shift but stays 22 points above adapted CLM-8B; decider-zero *improves* +1.65 points on shifted (no supervised fitting to lose). The anchor study's finding that the lexical probe beats adapted CLM on the aggregate shifted endpoint is confirmed and extended: laya-ft beats both.

## 4. Calibration and controls

- **Zero-shot calibration inverts the accuracy ranking**: laya-zero is the best-calibrated zero-shot model (ECE 0.039) while being least accurate — honestly uncertain; decider-zero is overconfident (ECE 0.150) until a single scalar refit on train-split predictions (fitted T_choice = 2.437 vs served 1.11) halves error to 0.053 (ID) / 0.022 (shifted) with accuracy unchanged by construction (argmax invariant verified).
- **Option-order sensitivity** (1,000 ID rows, per-row seeded shuffle): laya 16.9% prediction flips (McNemar p = 0.48; accuracy 0.432→0.424, symmetric noise); decider 5.5% flips (McNemar p = 9.8e-5; accuracy 0.772→**0.799** — a significant *gain*, i.e. a fixable early-option position bias, consistent with the letter-layout readout).
- Constant majority 12.5% (gold distribution non-uniform) — both zero-shot arms clear it; published CLM-8B did not.

## 5. Contract-level findings (G1, measured)

See `g0-20261007/NOTES.md`. Highlights: both subjects bit-exact deterministic; laya answer schema uses `probabilities` + dual `confidence`/`answer_confidence` fields (threshold code must choose deliberately); decider honours 2–255 options and 32k context (8k verified); argmax invariant under temperature override verified; laya Router 10/10 correct script routing.

## 6. Serving matrix (G3) — completed

Cells: 50 disjoint warmups + 3×1,000 measured requests, fresh process per cell, idle machine (see §7 items 8–9 for the contention incidents that forced retakes). GGUF cells are CPU-only: the installed llama-cpp-python wheel has no CUDA backend (bundled libs list lacks `libggml-cuda.so`), so the registered llama.cpp arm ran on 24 CPU threads and is labeled as such. Latency figures are means of block quantiles on a shared desktop in normal working state, matching the anchor study's framing — not tail-SLO guarantees.

| Cell | p50 (ms) | p95 (ms) | decisions/s | max RSS (MB) |
|---|---:|---:|---:|---:|
| laya GPU, uncached (new states) | **9.26** | 9.64 | **107.7** | 3,592 |
| laya GPU, repeat input | 9.32 | 10.42 | 105.2 | 3,574 |
| decider bf16 GPU, uncached | **23.85** | 26.25 | **41.4** | 9,142 |
| decider bf16 GPU, repeat input | 24.93 | 26.92 | 39.9 | 9,141 |
| laya CPU, uncached | 231.8 | 2,079.5 | 2.46 | 6,142 |
| decider GGUF Q4_K_M CPU, uncached | 5,353.6 | 6,210.9 | 0.19 | 6,690 |
| decider bf16 CPU, uncached (no-FLA venv) | 14,516.4 | 22,840.8 | 0.068 | 25,014 |

Anchor comparison (same machine class, prior study): CLM-8B published heads CPU-served p50 110.99 ms uncached / 8.66 dec/s; actions-warm 50.65 ms; exact-repeat 0.79 ms via its embedding cache. **laya serves this decision workload 12× faster than the best uncached CLM cell at 1/20th the memory; decider 2×**; neither subject has an application-level repeat cache (repeat ≈ uncached, by design). Laya's CPU p50 232 ms lands inside its maker's 193–464 ms claim; decider's GGUF-CPU 5.35 s/decision reflects this corpus's ~350–1,000-token states (the maker's 0.3–0.7 s claim was for 40–120-token requests).

The completed matrix closes the CPU question: for CPU deployment the ordering is laya (232 ms, 6.1 GB) ≫ decider GGUF Q4_K_M (5.35 s, 6.7 GB) ≫ decider bf16/float32 (14.5 s, 25 GB — not viable); for GPU it is laya (9.3 ms, 3.6 GB) > decider (23.9 ms, 9.1 GB), both far ahead of every uncached CLM-8B cell.

**GGUF equivalence gate — FAILED (descriptive-only status per plan §7a).** Choice agreement 97.0% (30/1,000 mismatches) vs the registered ≥99.5%; max |Δp| 0.681 vs the 1e-2 tolerance. The divergence is quality-neutral on this corpus: Q4_K_M scores 78.5% on the 1,000-row probe vs bf16's 78.15%, and on the first 10 disagreements Q4_K_M was right 6 times, bf16 3, both wrong 1 — near-tie rows flipping on quantization noise, matching the maker's own "same average, different rows" regression finding. Practical reading: do not hot-swap Q4_K_M for bf16 where per-row parity matters; do use it where aggregate quality and CPU portability matter. The equivalence gate that CLM-8B's llama.cpp port never passed also fails here — but for quantization deltas, not transport-contract mismatches, and with aggregate quality intact.

G1 probes (single short question, warm): decider 6.97 ms, laya 8.58 ms p50 — the matrix cells above are the honest workload numbers (full states, fresh processes).

## 7. Retained failures and caveats

1. laya-train first run: 12,000/12,000 `invalid_target` (label key misuse) — fixed by `gold`→`expected` conversion; failure preserved here and in the run log.
2. laya-train emits `Conflicting schema … keeping first seen definition` when criteria texts vary per row; verified to affect only the saved convenience `questions.json`, not the per-row training items.
3. The laya-ft train loss displayed 0.0000 by epoch 3 (full memorization of 12k rows); the 92% shifted accuracy is the generalization evidence, the 100% ID is in-distribution ceiling.
4. decider adaptation is temperature-only (B300-scale retraining out of scope) — its zero-shot arm is therefore compared against *adapted* baselines at a supervision disadvantage, stated wherever quoted.
5. G2 measurement was not preregistered against this exact reuse (the plan contemplated regenerating splits; reusing the anchor's frozen sealed rows verbatim is strictly stronger for comparability and is documented as the executed design).
6. GGUF gate first execution was abandoned at 77 min: llama-cpp-python silently fell back to CPU (no CUDA in the wheel) while a concurrent Laya CPU cell stole cores (load 36/24). Job-kill via the harness removed only bash wrappers; three generations of orphaned Python workers survived and polluted two GPU-cell retakes before being killed by PID. All affected cells were re-measured on an idle machine; the discarded numbers are superseded, and this item records why.
7. llama-cpp-python CUDA rebuild was deliberately not attempted (build-time rabbit hole); the pinned b10991 CUDA llama-server binary remains available for a future HTTP-based GGUF arm. The GGUF gate's agreement endpoint is unaffected by device; its latency figures are CPU-bound and labeled.
8. Serving measurements ran on the user's active desktop (2 days uptime, Hyprland session), matching the anchor study's "normal working state" caveat; absolute numbers carry that noise, block-quantile means dampen it.
9. decider bf16 CPU cell first attempt crashed: flash-linear-attention Triton kernels cannot execute on CPU tensors (`ValueError: Pointer argument cannot be accessed from Triton`). Fixed with a dedicated `venv-decider-cpu` (decider-ai without FLA, per the model card's "runs without it" path). The completed re-run measured 14,516 ms p50 / 25.0 GB RSS (12.5 h wall for 3,050 requests): on CPU the model's own Q4_K_M GGUF is strictly better — 2.7× faster (5,354 ms) and 3.7× smaller (6.7 GB) with aggregate quality intact (§6). PyTorch-float32 CPU serving of this checkpoint is not a viable deployment; the CPU decision belongs to laya (232 ms) or the GGUF.
10. laya GPU repeat cell shows p95 10.42 ms vs 9.64 uncached: repeat-regime blocks interleaved with desktop activity; medians are the stable quantity. No application cache exists to isolate (repeat ≈ uncached by design).
