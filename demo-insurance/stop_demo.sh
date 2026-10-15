#!/usr/bin/env bash
# Stop the insurance-claims demo: studio (and the laya.train_cli it spawned), laya,
# decider, cloudflared tunnel.
#
# Usage: stop_demo.sh [--yes]
#   without --yes  print exactly what would be stopped and exit (nothing is killed)
#   with --yes     stop it — by explicit PID (or systemd unit name) only
#
# Kills are attributed: service PIDs come from pgrep scoped to the ports this script
# was told (LAYA_PORT/DECIDER_PORT/STUDIO_PORT, default 8901/8902/8903), the training
# child from the studio's own studio-runs/<domain>/train.pid files (cmdline-verified)
# plus — while the studio is still up — train_cli descended from a studio process.
# laya.train_cli is never killed by machine-wide pattern: unrelated training runs
# (VRAM measurements) must survive. Env overrides: LAYA_PORT, DECIDER_PORT, STUDIO_PORT.
set -u
cd "$(dirname "$0")"
HERE="$(pwd)"
LAYA_PORT="${LAYA_PORT:-8901}"
DECIDER_PORT="${DECIDER_PORT:-8902}"
STUDIO_PORT="${STUDIO_PORT:-8903}"

case "${1:-}" in
  "" ) PLAN_ONLY=1 ;;
  --yes | -y) PLAN_ONLY=0 ;;
  *) echo "[demo] usage: stop_demo.sh [--yes]"; exit 2 ;;
esac

# ---------------------------------------------------------------- collect (read-only)
TRAIN_PIDS=""
for pf in "$HERE"/studio-runs/*/train.pid; do
  [ -s "$pf" ] || continue
  tp="$(cat "$pf")"
  case "$(tr '\0' ' ' <"/proc/$tp/cmdline" 2>/dev/null)" in
    *laya.train_cli*) case " $TRAIN_PIDS " in *" $tp "*) ;; *) TRAIN_PIDS="$TRAIN_PIDS $tp" ;; esac ;;
  esac
done
for tp in $(pgrep -f "laya[.]train_cli"); do
  case " $TRAIN_PIDS " in *" $tp "*) continue ;; esac
  pp="$tp"
  for _ in 1 2 3 4 5 6 7 8; do
    pp="$(ps -o ppid= -p "$pp" 2>/dev/null | tr -d ' ')"
    case "$pp" in '' | *[!0-9]*) break ;; esac
    [ "$pp" -gt 1 ] || break
    case "$(tr '\0' ' ' <"/proc/$pp/cmdline" 2>/dev/null)" in
      *studio_service.py*) TRAIN_PIDS="$TRAIN_PIDS $tp"; break ;;
    esac
  done
done

STUDIO_PIDS="$(pgrep -f "studio_service.py $STUDIO_PORT")"
LAYA_PIDS="$(pgrep -f "laya_service.py $LAYA_PORT")"
DECIDER_PIDS="$(pgrep -f "decider_service.py $DECIDER_PORT")"
CF_PIDS="$(pgrep -f "cloudflared tunnel --url http://(127[.]0[.]0[.]1|localhost):$LAYA_PORT")"

ACTIVE_UNITS=""
SYSTEMCTL="$(command -v systemctl 2>/dev/null || true)"
if [ -n "$SYSTEMCTL" ]; then
  for u in decision-demo-tunnel.service decision-demo-studio.service \
           decision-demo-laya.service decision-demo-decider.service; do
    systemctl --user is-active --quiet "$u" 2>/dev/null && ACTIVE_UNITS="$ACTIVE_UNITS $u"
  done
fi

# ---------------------------------------------------------------- plan
show() { # show <label> <pids...>
  if [ -n "$2" ]; then
    echo "  $1: pids$2"
  else
    echo "  $1: down"
  fi
}
echo "[demo] stop plan (read from pid files in $HERE/studio-runs and ports $LAYA_PORT/$DECIDER_PORT/$STUDIO_PORT):"
if [ -n "$ACTIVE_UNITS" ]; then echo "  systemd units:$ACTIVE_UNITS"; else echo "  systemd units: none active"; fi
show "  laya :$LAYA_PORT" "$LAYA_PIDS"
show "  decider :$DECIDER_PORT" "$DECIDER_PIDS"
show "  studio :$STUDIO_PORT" "$STUDIO_PIDS"
show "  cloudflared -> :$LAYA_PORT" "$CF_PIDS"
show "  studio train_cli (pid files + studio ancestry)" "$TRAIN_PIDS"

if [ "$PLAN_ONLY" = 1 ]; then
  echo "[demo] nothing stopped — re-run with --yes to stop the above."
  exit 0
fi

# ---------------------------------------------------------------- execute
unit_stop() {
  if [ -n "$SYSTEMCTL" ] && systemctl --user is-active --quiet "$1" 2>/dev/null; then
    echo "[demo] stopping unit $1"
    systemctl --user stop "$1"
  fi
}
for u in $ACTIVE_UNITS; do unit_stop "$u"; done

ALL_PIDS="$TRAIN_PIDS $STUDIO_PIDS $LAYA_PIDS $DECIDER_PIDS $CF_PIDS"
for tp in $ALL_PIDS; do kill "$tp" 2>/dev/null; done
sleep 2
for tp in $ALL_PIDS; do
  kill -0 "$tp" 2>/dev/null && kill -9 "$tp" 2>/dev/null
done

for p in "$LAYA_PORT" "$DECIDER_PORT" "$STUDIO_PORT"; do
  if curl -s -m 2 "http://127.0.0.1:$p/health" >/dev/null 2>&1; then
    echo ":$p STILL UP — check: pgrep -af '(laya|decider|studio)_service'"
  else
    echo ":$p stopped"
  fi
done
if pgrep -f "cloudflared tunnel --url" >/dev/null 2>&1; then
  echo "cloudflared still up — check: pgrep -af cloudflared"
else
  echo "cloudflared stopped; GPU memory freed when processes exit."
fi
if pgrep -f "laya[.]train_cli" >/dev/null 2>&1; then
  echo "note: a laya.train_cli is still running but was not attributable to this demo's studio — left untouched"
fi
