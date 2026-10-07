#!/usr/bin/env bash
# Regenerate the demo's fine-tuned checkpoints from the seeded corpus (deterministic data;
# training itself is single-run, matching the documented demo numbers).
# Env overrides: LAYA_PY, EPOCHS (default 3).
set -euo pipefail
cd "$(dirname "$0")"
LAYA_PY="${LAYA_PY:-$(pwd)/../.venv-laya/bin/python}"
EPOCHS="${EPOCHS:-3}"

# 1) corpus (seeded; skip if present and non-empty)
if [ ! -s data/train.jsonl ]; then
  echo "[train] generating corpus (seeded, deterministic)"
  "$LAYA_PY" gen_corpus.py
else
  echo "[train] corpus present — delete data/ to regenerate (SHA-identical by seed)"
fi

# 2) English fine-tune (served as Engine B)
echo "[train] fine-tuning ENGLISH checkpoint (${EPOCHS} epochs)"
"$LAYA_PY" -m laya.train_cli --data data/train.jsonl --base convaiinnovations/laya \
  --out laya-ft-ckpt --loss soft-ce --shuffle-options --epochs "$EPOCHS" --device "${DEVICE:-cuda}"

echo "[train] done. Checkpoint: laya-ft-ckpt/ (the multilingual variant is intentionally not"
echo "trained here — see DEMO_MANUAL.md §6: English-only supervision degrades cross-lingual use.)"
