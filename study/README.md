# Study harness (G1–G3)

Scripts transformed for portability from the measurement workstation. Run them from the repo
root with the venv named in each docstring (`../.venv-laya` / `../.venv-decider` — created by
`../setup.sh`), or set `LAYA_PY`/`DECIDER_PY`.

## Order (see `../docs/LAYA_DECIDER_EXPERIMENT_PLAN.md` for the registered protocol)

```bash
LAYA=.venv-laya/bin/python; DEC=.venv-decider/bin/python
ANCHOR=study/anchor-corpus/main-data

# G1 contract tests
$LAYA study/src/contract_laya.py
$DEC  study/src/contract_decider.py

# G2 sealed evaluation (outputs MUST land in study/g2-20261007/ with these exact names)
for split in id shifted; do
  $LAYA study/src/g2_laya.py    --split $ANCHOR/main_$split.jsonl --out study/g2-20261007/laya-zero-$split.jsonl
  $DEC  study/src/g2_decider.py --split $ANCHOR/main_$split.jsonl --out study/g2-20261007/decider-zero-$split.jsonl
done
$LAYA study/src/g2_laya.py    --split $ANCHOR/main_id.jsonl   --out study/g2-20261007/laya-zero-id-shuffle.jsonl --shuffle-control
$DEC  study/src/g2_decider.py --split $ANCHOR/main_id.jsonl   --out study/g2-20261007/decider-zero-id-shuffle.jsonl --shuffle-control
$DEC  study/src/g2_decider.py --split $ANCHOR/main_train.jsonl --out study/g2-20261007/decider-zero-train.jsonl
python3 study/src/g2_analyze.py          # -> study/g2-20261007/analysis.json (anchor rows degrade gracefully)

# G3 serving matrix + GGUF gate (needs study/models/decider-4b[-GGUF] or DECIDER_MODELS_DIR;
# the GGUF gate additionally needs decider-ai[gguf] and the G2 output above)
$DEC  study/src/g3_matrix.py --subject laya    --placement cuda --regime uncached --out study/g3-20261007/laya-cuda-uncached.json
$DEC  study/src/g3_matrix.py --subject decider --placement cuda --regime uncached --out study/g3-20261007/decider-cuda-uncached.json
$DEC  study/src/g3_gguf_gate.py
```

Env: `DECISION_STUDY_ROOT` (repo root), `CLM8B_ANCHOR_ROOT` (defaults to `study/anchor-corpus`),
`DECIDER_MODELS_DIR` (defaults to `study/models`; put `decider-4b` and `decider-4b-GGUF` there or
let hub downloads land in the HF cache and set `DECIDER_MODEL`).
