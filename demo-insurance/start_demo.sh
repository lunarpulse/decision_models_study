#!/usr/bin/env bash
# Start the insurance-claims demo: laya (:8901), decider (:8902), studio (:8903),
# and — with --tunnel — a cloudflared quick tunnel whose public URL lands in tunnel-url.txt.
# Idempotent: services already answering /health are left alone.
# Env overrides:
#   LAYA_PY / DECIDER_PY / STUDIO_PY   absolute python paths
#     (default: ../.venv-laya, ../.venv-decider — see ../setup.sh)
#   LAYA_PORT / DECIDER_PORT / STUDIO_PORT
#   BOX                                distrobox name: run the python services inside it
#     (live machine: BOX=ai-dev LAYA_PY=/opt/ai-tools/venv-laya/bin/python DECIDER_PY=/opt/ai-tools/venv-decider/bin/python)
#   CLOUDFLARED_BIN                    cloudflared path for --tunnel
# For supervised operation use deploy/install_units.sh + systemd --user instead of this script.
set -u
cd "$(dirname "$0")"
HERE="$(pwd)"

LAYA_PY="${LAYA_PY:-$HERE/../.venv-laya/bin/python}"
DEC_PY="${DECIDER_PY:-$HERE/../.venv-decider/bin/python}"
STUDIO_PY="${STUDIO_PY:-$LAYA_PY}"
LAYA_PORT="${LAYA_PORT:-8901}"
DECIDER_PORT="${DECIDER_PORT:-8902}"
STUDIO_PORT="${STUDIO_PORT:-8903}"
CLOUDFLARED_BIN="${CLOUDFLARED_BIN:-$(command -v cloudflared 2>/dev/null || true)}"
[ -n "$CLOUDFLARED_BIN" ] || CLOUDFLARED_BIN="$HOME/bin/cloudflared"

TUNNEL=0
for a in "$@"; do
  case "$a" in
    --tunnel) TUNNEL=1 ;;
    *) echo "[demo] unknown argument: $a (usage: start_demo.sh [--tunnel])"; exit 2 ;;
  esac
done

# enter(): prefix that runs a command inside distrobox $BOX, or plain on the host.
enter() {
  if [ -n "${BOX:-}" ]; then distrobox enter "$BOX" -- "$@"; else "$@"; fi
}
if [ -n "${BOX:-}" ]; then
  command -v distrobox >/dev/null || { echo "[demo] distrobox not found but BOX=$BOX is set"; exit 1; }
  enter test -x "$LAYA_PY"  || { echo "[demo] laya python not found in box $BOX: $LAYA_PY"; exit 1; }
  enter test -x "$DEC_PY"   || { echo "[demo] decider python not found in box $BOX: $DEC_PY"; exit 1; }
  enter test -x "$STUDIO_PY" || { echo "[demo] studio python not found in box $BOX: $STUDIO_PY"; exit 1; }
else
  [ -x "$LAYA_PY" ]  || { echo "[demo] laya python not found: $LAYA_PY — run ../setup.sh or set LAYA_PY"; exit 1; }
  [ -x "$DEC_PY" ]   || { echo "[demo] decider python not found: $DEC_PY — run ../setup.sh or set DECIDER_PY"; exit 1; }
  [ -x "$STUDIO_PY" ] || { echo "[demo] studio python not found: $STUDIO_PY — set STUDIO_PY"; exit 1; }
fi

# Studio token: generated once, chmod 600, never echoed.
if [ ! -s studio-token.txt ]; then
  TOK_TMP="$(mktemp "$HERE/.studio-token.XXXXXX")"
  LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24 >"$TOK_TMP"
  if [ ! -s "$TOK_TMP" ]; then echo "[demo] failed to generate a studio token"; rm -f "$TOK_TMP"; exit 1; fi
  chmod 600 "$TOK_TMP" && mv "$TOK_TMP" studio-token.txt
  echo "[demo] studio token saved to studio-token.txt (chmod 600 — type it into the console when teaching)"
else
  chmod 600 studio-token.txt
fi

up() { curl -s -m 2 "http://127.0.0.1:$1/health" >/dev/null 2>&1; }

if ! up "$LAYA_PORT"; then
  echo "[demo] starting laya service on :$LAYA_PORT (loads 2 checkpoints; ~1 min first time)"
  LAYA_PORT="$LAYA_PORT" nohup enter "$LAYA_PY" "$HERE/laya_service.py" "$LAYA_PORT" >laya-service.log 2>&1 &
fi
if ! up "$DECIDER_PORT"; then
  echo "[demo] starting decider service on :$DECIDER_PORT (downloads ~8 GB on first run)"
  DECIDER_PORT="$DECIDER_PORT" nohup enter "$DEC_PY" "$HERE/decider_service.py" "$DECIDER_PORT" >decider-service.log 2>&1 &
fi
if ! up "$STUDIO_PORT"; then
  echo "[demo] starting studio on :$STUDIO_PORT (token auth on)"
  DEMO_ROOT="$HERE" STUDIO_PY="$STUDIO_PY" STUDIO_TOKEN="$(cat studio-token.txt)" \
    nohup enter "$STUDIO_PY" "$HERE/studio_service.py" "$STUDIO_PORT" >studio-service.log 2>&1 &
fi

for port in "$LAYA_PORT" "$DECIDER_PORT" "$STUDIO_PORT"; do
  for _ in $(seq 60); do up "$port" && break; sleep 2; done
  if up "$port"; then echo "[demo] :$port up"; else echo "[demo] :$port FAILED — see *-service.log"; fi
done

if [ "$TUNNEL" = 1 ]; then
  if pgrep -f "cloudflared.*tunnel --url" >/dev/null 2>&1; then
    echo "[demo] cloudflared already running — $(cat tunnel-url.txt 2>/dev/null || echo 'no tunnel-url.txt')"
  elif [ ! -x "$CLOUDFLARED_BIN" ]; then
    echo "[demo] cloudflared not found (set CLOUDFLARED_BIN) — skipping tunnel"
  else
    : >cloudflared.log
    nohup "$CLOUDFLARED_BIN" tunnel --url "http://127.0.0.1:$LAYA_PORT" >>cloudflared.log 2>&1 &
    URL=""
    for _ in $(seq 1 30); do
      URL="$(grep -oE 'https://[a-z0-9-]+[.]trycloudflare[.]com' cloudflared.log | tail -1)"
      [ -n "$URL" ] && break
      sleep 2
    done
    if [ -n "$URL" ]; then
      printf '%s\n' "$URL" >tunnel-url.txt
      echo "[demo] public URL: $URL (saved to tunnel-url.txt)"
    else
      echo "[demo] tunnel URL not seen yet — check cloudflared.log"
    fi
  fi
fi

echo
echo "Demo console:  http://127.0.0.1:$LAYA_PORT/?mode=day1     (Day 1 — nothing trained)"
echo "               http://127.0.0.1:$LAYA_PORT/?mode=after    (after 12,000-claim training)"
echo "               http://127.0.0.1:$LAYA_PORT/?mode=compare  (all three engines)"
echo "               http://127.0.0.1:$LAYA_PORT/?mode=ops      (ops floor, sealed 500)"
echo "               http://127.0.0.1:$LAYA_PORT/?mode=domain   (Domain Builder + Teach)"
echo "Teach/drift need the studio token (studio-token.txt); train logs land in studio-runs/<domain>/."
