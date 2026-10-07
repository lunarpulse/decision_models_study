# Laya & "Decipher" research brief — pre-study online research

Updated: 2026-10-07 UTC. Phase 0 of the Laya/decider study (mirrors the CLM-8B study sequence: research → registered plan → execution → report).
All numbers below are quoted from the named external source or from our own completed CLM-8B study documents; nothing has been re-measured locally yet.

---

## 1. Identity resolution: "Decipher" → `decider` (Mapika)

No model named "Decipher" exists in the Jev/System-One decision-model class:

- Hugging Face model search `decipher` returns only unrelated artifacts (2024 cipher tools, an NLP course assignment, a 0-download Qwen adapter). Nothing current, nothing in this class.
- JevBench v1.6.1 (88 ranked open-weights systems) and the HF Jev Decision Index (~70 entries) contain no "Decipher".
- `Mapika/decider` matches the description exactly: **high third-party standing at less than half CLM-8B's size** (4.2B vs 8B; see §4).

Working assumption (pending user confirmation): study subject = **decider-4b v2.1**, with decider-2b v11 GGUF as the llama.cpp/CPU arm (mirrors the CLM-8B production-backend preference).

## 2. Ecosystem map (as of 2026-10-07)

```
TypeSafe Jev 1.13.0 (2026-09-15, closed API, "System One", RLCD)
├── Encoder family:  Laya (ConvAI, 322–421M, Apache-2.0)
├── Decoder family:  decider (Mapika, 0.8B–35B, Apache-2.0)
│                    Kev (Jared Palmer, 0.8B/4B/9B), Bespoke Nimble-9B,
│                    JevK5, OpenJev, open-alternative-jev (layer, not model), …
└── Contrastive family: CLM-8B (Contrastive-LM, Qwen3-8B frozen encoder + heads)
```

Sources: [TypeSafe launch](https://typesafe.ai/blog/introducing-system-one-models-and-jev) · [JevBench](https://benchmarkheaven.com/jev-models) · [HF Jev Decision Index](https://huggingface.co/spaces/multimodalart/jev-decision-index) · [Invide roundup](https://blog.invidelabs.com/system-one-models-jev-laya-open-alternatives/) · [Rohit Raj roundup](https://rohitraj.tech/notes/jev-alternatives-open-weights-decision-models-2026)

## 3. Feature comparison — CLM-8B vs Laya vs decider-4b

| Feature | CLM-8B (prior study) | Laya (ConvAI) | decider-4b v2.1 (Mapika) |
|---|---|---|---|
| Architecture | Frozen Qwen3-8B decoder as encoder + 2 small projection heads (18.9M trainable); state/action cosine contrast | ModernBERT-large **bidirectional encoder** (421M) + decision head (2 transformer layers, option-marker scorer at `[MASK]` tokens) | Qwen3.5-4B-Base **decoder** (4.2B; 8 full-attention + 24 gated-delta-net layers), slot readout: option-letter logits softmaxed at `Answer k: (` slot |
| Decision mechanism | Cosine similarity between independently embedded state and free-text candidate actions | Schema-conditioned classification; softmax within question | Schema-conditioned classification; softmax over option letters |
| Primitives | Choice over free-text candidates | choice / score / noul, calibrated probs | choice (2–255 opts) / score (2–10 levels) / noul |
| Params / weights | 8B encoder (frozen) + 18.9M head pair | 421M (EN, typed) / 322M (multilingual); ~808 MB / ~647 MB per checkpoint | 4.2B dense, 8.4 GB bf16; GGUF Q4_K_M 2.7 GB |
| Context | 2,048 (explicit tail arrays in our reference) | 512 (EN) / 1024→8k (multilingual) / 1024 (typed) | 32k tokens |
| Languages | English (Qwen3 tokenizer) | 100+ via script router (sub-ms pure-Python `Router(preload=True)`) | English |
| Training | 60M Nemotron DQA + 30M hard negatives + 1M agentic trajectories (contrastive) | RLCD + proper scoring rules; temperature fit 0.466→0.081 ECE | Supervised only, no RL: stage 1 cross-entropy 742M tokens (mixture v2), stage 2 LoRA r64 merged; per-type temperatures (choice 1.110 / noul 1.560 / score 1.287) |
| Serving surfaces | Own repo server (`--embed-url` path); llama.cpp portability **failed in our study** | `pip install laya`, Router, HF Space; OpenVINO INT8 CPU demo; AXERA AX650 NPU port | `pip install decider-ai`, `POST /v1/systemone` (TypeSafe-compatible), vLLM, **llama.cpp GGUF** |
| License | (see prior study card) | Apache-2.0 | Apache-2.0 |
| Unique strength | Candidate texts are free-form and **embed independently** (action-embedding cache; 0.7 ms exact-repeat p50 in our matrix) | Multilingual routing; smallest footprint; CPU-viable (193–464 ms) | Best third-party accuracy/calibration per GB; 32k context; agentic/browser/game play (MiniWoB++ 93.2% sampled) |
| Published weaknesses | Published heads ≈ random on our sealed ID set (25.55%); JevBench Intelligence 0 | >20 choice options collapse (Banking77 0.425 vs Jev 0.870); zero-shot base ≈ 0.35 on typed-decisions; adversarial English eval 40.3% (majority constant 53.1%), 54% of ≥0.9-confidence answers wrong, option-order sensitivity ~1/5 | v2.1 disclosed regressions: form-filling case c_1 wrong, BabyAI-GoTo 0.19 (v1 0.54), hard-tier calibration ECE 0.184 (v2 0.104); knowledge area 0.18 behind Jev (35B variant) |

## 4. Third-party standings (not maker-claimed)

**JevBench v1.6.1** (Benchmark Heaven; 1,500 decisions/system; chance-corrected gated board: Intelligence/Calibration/Speed/Knowledge):

| System | Gated score | I | C | S | K | $/1k decisions |
|---|---:|---:|---:|---:|---:|---:|
| Jev 1.13.0 (reference, unranked) | — | 63.6 | 90.6 | — | — | $0.032 |
| **decider-4b v2** | **41.2** | 40 | 90 | 92 | 65 | $0.015 (est.) |
| Laya typed-decisions | 0.2 | 5 | 83 | 71 | 83 | $0.0038 |
| Laya (English) | 0.0 | 2 | 63 | 73 | 85 | $0.0032 |
| Laya multilingual | 0.0 | 0 | 34 | 78 | 82 | $0.0039 |
| **CLM-8B** | **0.0** | 0 | 40 | 93 | 51 | $0.045 |

- decider-4b v2: official **#8** on the capability board (77.6-scale not shown here), #3 overall in v1.4.2.2 with score 64.1 vs Jev's 63.3.
- Capability board (open-weights): decider-4b v2 well inside top-10; Laya English #59 / typed #20-with-latency-cap-violation; CLM-8B #57.
- **This independently corroborates our own sealed finding**: published CLM-8B heads scored 25.55% on 4-way sealed ID (random = 25%).

**Decision Index v0.2.1** (multimodalart; 40 benchmarks, chance-corrected): decider-4b 40.70 (#19, ECE 0.084); decider-chat-gemma4-31b (stock weights + readout) 57.33 (#2, ECE 0.047) vs Jev 57.91. Laya/CLM not ranked in the excerpt we read.

**decider-4b v2.1 maker numbers** (model card, pre-registered release rules, disclosed failures): regression set 0.831 in-task / 0.784 held-out; JevBench public hard tier 0.649 (12b sibling: 0.712); MiniWoB++ live 93.2% sampled.

**Laya maker numbers** (official site, T4): 32.8 ms/question GPU, 7.2 ms/q batched; typed-decisions 0.766 (fine-tuned; teacher ceiling 0.735); AG News 0.950; Enron spam 0.993 (ECE 0.013); phishing 0.980; ToxicChat guardrails 0.755–0.762 (0.931 at 50% selective coverage).

## 5. Capability assessment vs CLM-8B (research-phase judgment)

1. **Output type**: all three return typed answers + probabilities, no text generation. CLM-8B is the odd one out mechanically — it scores *arbitrary free-text candidate descriptions* by embedding cosine (candidates cacheable independently), while Laya/decider score *schema-supplied options* in one conditioned pass. CLM's contract is more flexible for "interpret any new policy text"; Laya/decider are stronger as drop-in Jev replacements.
2. **Intelligence per GB**: third parties put decider-4b far above both CLM-8B and Laya on chance-corrected decision accuracy. The user's premise ("high performance, lower size than CLM-8") is supported by two independent boards.
3. **Calibration**: decider-4b C=90 ≈ Jev 90.6; Laya typed C=83 (ECE 0.081 after temperature fit, maker-reported); CLM-8B C=40 — consistent with our study's finding that its published heads are uncalibrated for direct use.
4. **Production surfaces**: decider ships TypeSafe-compatible HTTP + GGUF (direct llama.cpp path that CLM-8B lacked — our G2 llama.cpp equivalence failed). Laya ships CPU/OpenVINO/NPU paths (edge) but 512–1024 token context and ≤20-option budgets. CLM-8B's unique asset is the action-embedding cache (sub-ms repeat decisions).
5. **Honest-disclosure quality**: decider's card is the most rigorous (pre-registered release rules, per-regression listing, contamination checks); Laya publishes explicit limits; CLM-8B's headline agentic claims (DeepSWE 81.6%) were community-disputed as best-of-selection over Opus samples, and our study showed published heads at chance.

## 6. Proposed study plan (mirrors CLM-8B Revision-2 methodology)

- **G0**: pin sources (`pip install laya==0.3.3+`, `decider-ai` + Mapika/decider checkout commit; HF revisions for all checkpoints), record identities/hashes.
- **G1**: acquisition + contract tests (request/response schemas, option limits, context caps, temperature semantics; verify decider's TypeSafe-compatible `/v1/systemone` and Laya's Router routing decisions).
- **G2 (primary)**: sealed ID + shifted evaluation on the CLM-8B study's decision families, adapted for option-schema format; published vs adapted/fine-tuned arms where applicable; CLM-8B frozen results reused as the anchor comparator.
- **G3**: serving matrix (uncached/warm/exact-repeat; CPU vs GPU; llama.cpp GGUF arm for decider — the path that failed for CLM).
- **G4**: matched generator comparison (reuse frozen Qwen3.8-27B NVFP4 Q4_K_M setup) + lexical/embedding probe baselines.
- **G5**: report + (optional, on request) Korean business presentation mirroring the CLM8B deck.

Open item blocking G0: user confirmation that "Decipher" = Mapika `decider` (and preferred checkpoint).

## 7. Source ledger

| Claim | Source |
|---|---|
| Laya architecture/checkpoints/benchmarks/limits | https://laya.convaiinnovations.com/ (official, Sep 2026) |
| Laya HF hub | https://huggingface.co/convaiinnovations/laya |
| Laya package | https://pypi.org/project/laya/ |
| Laya adversarial outside eval | https://huggingface.co/convaiinnovations/laya/discussions/3 |
| decider README/model cards, standings | https://github.com/Mapika/decider · https://huggingface.co/Mapika/decider-4b |
| JevBench v1.6.1 board + Jev-vs-decider | https://benchmarkheaven.com/jev-models · /jev-models/jev-vs-decider-4b-v2 |
| Decision Index | https://huggingface.co/spaces/multimodalart/jev-decision-index |
| CLM-8B claims + community critique | https://github.com/Contrastive-LM/CLM · HN 49826221 |
| CLM-8B local measurements | `CLM8B_EXPERIMENT_REPORT.md` (this folder) |
| Ecosystem roundups | blog.invidelabs.com · rohitraj.tech (Sep 2026) |

## 8. Measured results from this study (supersedes §4–§5 judgments where they overlap)

Executed 2026-10-07 on the CLM-8B anchor study's own sealed splits (identical rows and gold; see `LAYA_DECIDER_EXPERIMENT_REPORT.md` and `AI/catalog/decision-study/g2-20261007/analysis.json`).

| Arm (sealed ID, n=4,000) | Accuracy | macro-F1 | ECE-15 | Shifted acc (n=2,000) |
|---|---:|---:|---:|---:|
| laya fine-tuned on anchor's 12k train rows | **1.0000** | 1.0000 | 0.0000 | **0.9200** |
| anchor adapted CLM-8B seed-11 | 0.9840 | 0.9840 | 0.0242 | 0.6980 |
| anchor lexical probe | 0.9385 | 0.9384 | — | 0.7375 |
| decider-4b v2.1 zero-shot | 0.7815 | 0.7763 | 0.1495 (0.0533 refit) | 0.7980 |
| laya zero-shot (Router) | 0.4405 | 0.3699 | **0.0392** | 0.4405 |
| anchor published CLM-8B | 0.2555 | 0.2036 | 0.3812 | 0.2755 |

Key measured facts: laya-ft beats adapted CLM-8B on ID (+1.60 pp, paired CI +1.24…+2.04) and shifted (+22.2 pp) at 1/20th the parameters; decider zero-shot beats *published* CLM-8B by +52.6 pp without any domain supervision; laya zero-shot is the best-calibrated unsupervised arm (honestly uncertain); decider's served temperatures are overconfident for this domain until a one-scalar refit (T 1.11→2.44 halves ECE); option-order shuffling flips 16.9% of laya answers (symmetric noise) and 5.5% of decider answers (positional bias — shuffling *improves* decider accuracy 0.772→0.799, McNemar p=9.8e-5). Frozen generator reference on identical rows: 0-shot 98.8% / 4-shot 100.0%.

**Serving (G3, idle desktop, 3×1,000-request blocks):** laya GPU 9.26 ms p50 / 107.7 dec/s (CPU 232 ms); decider bf16 GPU 23.85 ms / 41.4 dec/s; decider Q4_K_M GGUF on 24 CPU threads 5.35 s/decision. Anchor CLM-8B best uncached cell: 50.7 ms / 18.8 dec/s. **GGUF equivalence gate FAILED** (97.0% choice agreement vs ≥99.5% required, max Δp 0.68) but is quality-neutral (78.5% vs 78.15% on the probe; of the first 10 disagreements Q4_K_M was right 6, bf16 3): aggregate-safe, per-row-unsafe quantization. CLM-8B's unique sub-ms exact-repeat embedding cache has no analogue in either subject.
