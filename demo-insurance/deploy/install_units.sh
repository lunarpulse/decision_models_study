#!/usr/bin/env bash
# Install the decision-demo systemd --user units.
# Copies deploy/systemd/* and the env file to ~/.config/systemd/user, then daemon-reloads.
# Does NOT start or enable anything — it prints the commands to do that.
# Machine parameters live in deploy/demo.env (copy from demo.env.example and edit).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"        # .../demo-insurance/deploy
UNIT_SRC="$HERE/systemd"
UNIT_DST="$HOME/.config/systemd/user"
ENV_DST="$UNIT_DST/decision-demo.env"

command -v systemctl >/dev/null || { echo "[install] systemctl not found"; exit 1; }
[ -d "$UNIT_SRC" ] || { echo "[install] missing $UNIT_SRC"; exit 1; }

mkdir -p "$UNIT_DST"

# --- env file ----------------------------------------------------------------
if [ -f "$HERE/demo.env" ]; then
  cp "$HERE/demo.env" "$ENV_DST"
  echo "[install] env: $HERE/demo.env -> $ENV_DST"
elif [ -f "$ENV_DST" ]; then
  echo "[install] env: keeping existing $ENV_DST"
else
  cp "$HERE/demo.env.example" "$ENV_DST"
  echo "[install] env: deploy/demo.env missing — installed the EXAMPLE as $ENV_DST"
  echo "[install]      -> EDIT IT (DEMO_DIR, python paths, ports) before starting."
fi
# shellcheck disable=SC1090
. "$ENV_DST"
DEMO_DIR="${DEMO_DIR:-}"
[ -d "$DEMO_DIR" ] || echo "[install] WARNING: DEMO_DIR does not exist yet: $DEMO_DIR"

# --- unit files --------------------------------------------------------------
for f in "$UNIT_SRC"/decision-demo-*.service "$UNIT_SRC"/decision-demo.target; do
  cp "$f" "$UNIT_DST/"
  echo "[install] unit: $(basename "$f") -> $UNIT_DST/"
done

systemctl --user daemon-reload
echo "[install] systemctl --user daemon-reload done."
echo
echo "Nothing was started or enabled. To run the demo:"
echo "  systemctl --user start decision-demo.target              # laya + decider + studio"
echo "  systemctl --user start decision-demo-tunnel.service      # optional public URL (writes tunnel-url.txt)"
echo "  systemctl --user enable --now decision-demo.target       # also start at login"
echo
echo "Status / logs:"
echo "  systemctl --user status decision-demo.target"
echo "  journalctl --user -u decision-demo-laya -f   # same for -decider, -studio, -tunnel"
echo "  cat \"\$DEMO_DIR/tunnel-url.txt\"               # public URL once the tunnel is up"
