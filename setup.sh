#!/usr/bin/env bash
# Setup for the decision-study public repo. Creates two virtualenvs and installs engines.
# Requires: Python 3.11–3.13, ~20 GB peak disk (wheels + CUDA libs + weights + HF cache) downloaded on first run,
# a CUDA GPU (>= 16 GB recommended) for the default demo; CPU-only works for Laya.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
command -v uv >/dev/null 2>&1 && HAVE_UV=1 || HAVE_UV=0
if [ "$HAVE_UV" != "1" ]; then
  # no uv: the fallback venv inherits $PY, so enforce the supported range ourselves
  "$PY" -c 'import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] <= (3,13) else 1)' \
    || { echo "[setup] need Python 3.11–3.13; set PYTHON=/path/to/python3.12 (or install uv)"; exit 1; }
fi

make_venv() { # $1 name, $2 requirements file
  if [ "$HAVE_UV" = "1" ]; then
    uv venv --python "${PYTHON_VERSION:-3.12}" ".venv-$1"
    uv pip install --python ".venv-$1/bin/python" -r "$2"
  else
    "$PY" -m venv ".venv-$1"
    ".venv-$1/bin/pip" install --upgrade pip
    ".venv-$1/bin/pip" install -r "$2"
  fi
  echo "[setup] .venv-$1 ready"
}

make_venv laya requirements/laya.txt
make_venv decider requirements/decider.txt

echo
echo "[setup] done. Next steps:"
echo "  1) cd demo-insurance && bash train_laya.sh     # ~15 min GPU; regenerates fine-tuned checkpoints"
echo "  2) bash start_demo.sh                           # serves http://127.0.0.1:8901"
echo "Models (convaiinnovations/laya, Mapika/decider-4b) download from Hugging Face on first use (~10.5 GB; ~20 GB peak disk with wheels and caches)."
