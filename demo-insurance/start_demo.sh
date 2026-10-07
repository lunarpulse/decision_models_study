#!/usr/bin/env bash
# Start the insurance-claims demo. Auto-detects venvs created by ../setup.sh.
# Env overrides: LAYA_PY, DECIDER_PY (absolute python paths), LAYA_PORT (default 8901), DECIDER_PORT (8902).
set -u
cd "$(dirname "$0")"
HERE="$(pwd)"

LAYA_PY="${LAYA_PY:-$HERE/../.venv-laya/bin/python}"
DEC_PY="${DECIDER_PY:-$HERE/../.venv-decider/bin/python}"
LAYA_PORT="${LAYA_PORT:-8901}"
DECIDER_PORT="${DECIDER_PORT:-8902}"

[ -x "$LAYA_PY" ] || { echo "[demo] laya python not found: $LAYA_PY — run ../setup.sh or set LAYA_PY"; exit 1; }
[ -x "$DEC_PY" ] || { echo "[demo] decider python not found: $DEC_PY — run ../setup.sh or set DECIDER_PY"; exit 1; }

up() { curl -s -m 2 "http://127.0.0.1:$1/health" >/dev/null 2>&1; }

if ! up "$LAYA_PORT"; then
  echo "[demo] starting laya service on :$LAYA_PORT (loads 2 checkpoints; ~1 min first time)"
  LAYA_PORT="$LAYA_PORT" nohup "$LAYA_PY" laya_service.py "$LAYA_PORT" > laya-service.log 2>&1 &
fi
if ! up "$DECIDER_PORT"; then
  echo "[demo] starting decider service on :$DECIDER_PORT (downloads ~8 GB on first run)"
  nohup "$DEC_PY" decider_service.py "$DECIDER_PORT" > decider-service.log 2>&1 &
fi

for spec in "$LAYA_PORT:$DECIDER_PORT"; do
  for port in ${spec//:/ }; do
    for i in $(seq 60); do up "$port" && break; sleep 2; done
    if up "$port"; then echo "[demo] :$port up"; else echo "[demo] :$port FAILED — see *-service.log"; fi
  done
done

echo
echo "Demo console:  http://127.0.0.1:$LAYA_PORT/?mode=day1     (Day 1 — nothing trained)"
echo "               http://127.0.0.1:$LAYA_PORT/?mode=after    (after 12,000-claim training)"
echo "               http://127.0.0.1:$LAYA_PORT/?mode=compare  (all three engines)"
echo "Note: the fine-tuned checkpoints must exist — run ./train_laya.sh once (~15 min GPU)."
