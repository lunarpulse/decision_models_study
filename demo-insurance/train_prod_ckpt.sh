#!/usr/bin/env bash
# Build the Domain Builder's production checkpoints ("your model"): Laya fine-tuned once per
# domain on its 2,000 seeded training rows under today's rulebook. The studio re-teaches policy
# changes FROM these (studio_service.py) and never writes them.
#   ./train_prod_ckpt.sh [domain ...]      default: every factory domain
# Env: LAYA_PY, EPOCHS (default 3), DEVICE (default cuda), STUDIO_RUNS (default ./studio-runs).
# Needs ~9 GiB free VRAM: stop the studio service first on a host that serves the demo.
set -euo pipefail
cd "$(dirname "$0")"
LAYA_PY="${LAYA_PY:-$(pwd)/../.venv-laya/bin/python}"
EPOCHS="${EPOCHS:-3}"
RUNS="${STUDIO_RUNS:-$(pwd)/studio-runs}"
[ -x "$LAYA_PY" ] || { echo "[prod] laya python not found: $LAYA_PY — run ../setup.sh or set LAYA_PY"; exit 1; }
[ $# -gt 0 ] || set -- support_tickets logistics_exceptions hr_exceptions

for d in "$@"; do
  [ -s "data/$d/train.jsonl" ] || { echo "[prod] no corpus for $d (python domains.py $d)"; exit 1; }
  mkdir -p "$RUNS/$d"
  echo "[prod] $d: fine-tuning on data/$d/train.jsonl (${EPOCHS} epochs) -> $RUNS/$d/prod-ckpt"
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$LAYA_PY" -m laya.train_cli \
    --data "data/$d/train.jsonl" --base convaiinnovations/laya --out "$RUNS/$d/prod-ckpt" \
    --loss soft-ce --shuffle-options --epochs "$EPOCHS" --micro-batch 8 --grad-accum 2 \
    --device "${DEVICE:-cuda}" > "$RUNS/$d/prod-train.log" 2>&1
  rm -rf "$RUNS/$d/prod-ckpt/checkpoint_latest" "$RUNS/$d/prod-holdout.json"
  grep "mean loss" "$RUNS/$d/prod-train.log" || true
done
echo "[prod] done — restart the studio service; it caches each model's holdout answers on start."
