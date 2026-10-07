# G0/G1 contract notes — laya 0.3.28 vs decider-ai 1.8.1 (decider-4b v2.1)

Run: 2026-10-07 UTC, ai-dev box, RTX 5090 (driver 615.71.09), torch 2.14.1+cu130, transformers 5.18.0.
Ledgers: `contract-laya.json`, `contract-decider.json` (this directory). Plan: `LAYA_DECIDER_EXPERIMENT_PLAN.md` SHA `028be98a…`.

## Pinned identities

| Artifact | Identity |
|---|---|
| convaiinnovations/laya | snapshot `7b928d828b7b0e022f929d9bd2e44165aa270148` (EN 804 MB + multilingual 614 MB + typed-decisions 804 MB) |
| Mapika/decider-4b | snapshot `eb5fbdfc9448473ec25e399882912863afbdb70e`, `decider_config.json` version `4b-v2.1`, T-map 1.11/1.56/1.287 |
| Mapika/decider-4b-GGUF | snapshot `b79f09d9ba7837f1b744295ea267b55d08e958ec`, `decider-4b-v2.1-Q4_K_M.gguf` SHA-256 `c7083fcfc93f650cd66caeade4a3840ef9eeeeb1e80920907c554f70619d7c56` (2.6 GB) |

## Contract semantics discovered

- **Laya answer schema**: choice → `{choice, probabilities{opt:p}, confidence, answer_confidence, action{act_probability}}`; score → `{score, legend, probabilities{level:p}, confidence, answer_confidence}`; noul → `{noul, confidence, answer_confidence}`. Two distinct confidence fields: `confidence` (distribution concentration) vs `answer_confidence` (top probability). G2 calibration must state which field feeds thresholds — we will use `probabilities` directly.
- **decider answer schema**: `{choice, confidence, probs{opt:p}}`; probs sum exactly 1.0.
- Both subjects: **bit-exact determinism** (max |Δp| = 0.0 over repeated identical calls).
- **Option boundaries**: Laya returns clean distributions at 2/20/21 options (21 accepted mechanically; quality beyond 20 is a G2 measurement, per maker's documented budget). decider verified at 2/20/21/**255**.
- **Temperature override (decider)**: argmax invariant confirmed; max prob delta map-vs-global 0.00227 on the probe.
- **Routing (Laya)**: 10/10 correct on the fixed probe — all 8 non-Latin scripts → multilingual checkpoint; English/German/Spanish → English checkpoint.
- **Option-order sensitivity (5-state probe)**: Laya 0/5 flips, decider 0/5 flips (the published outside-eval sensitivity finding did not reproduce on this small benign probe; G2 uses the registered shuffle control at scale).
- **Long state**: Laya accepted a >512-token state (truncation behaviour internal); decider accepted ~8k tokens, chose "infrastructure" for a gateway-latency log.

## Latency probes (informational, single GPU process, warm)

| Probe | Laya (Router, EN) | decider-4b v2.1 bf16 |
|---|---|---|
| p50, 1 question × 50 calls | 8.58 ms | 6.97 ms |
| p95 | 9.03 ms | 7.69 ms |
| First call after load | ~15.6 s (kernel compile) | ~25.3 s (load+graph capture) |
| Warm 20-option choice | 10.88 ms | 12.85 ms |
| 255-option choice | n/a (documented ≤20 budget) | 9.50 s (fresh shape, graph re-capture) |

Context vs CLM-8B anchor (same machine, prior study): published CLM CPU-heads uncached p50 ≈ 111 ms; actions-warm ≈ 51 ms; exact-repeat cache ≈ 0.7–0.8 ms. Both new subjects beat every uncached CLM cell by an order of magnitude on this hardware; CLM retains the only sub-ms repeat surface (embedding cache).

## G1 discrepancies retained

- First laya run recorded `t3_determinism_max_abs_diff` over zero values (wrong dict key, `probs` vs `probabilities`); script repaired and re-run — corrected values above. Original ledger overwritten; this note preserves the failure cause.
- decider `package` version string reads "unknown" via `importlib.metadata` in-process (`decider-ai 1.8.1` recorded from pip in `env-snapshot.txt`).
