#!/usr/bin/env bash
# Stop the insurance-claims demo services.
pkill -f "laya_service.py 8901" 2>/dev/null
pkill -f "decider_service.py 8902" 2>/dev/null
pkill -f "cloudflared.*8901" 2>/dev/null
sleep 1
for p in 8901 8902; do
  if curl -s -m 2 "http://127.0.0.1:$p/health" >/dev/null 2>&1; then
    echo ":$p still up — check: pgrep -af '(laya|decider)_service'"
  else
    echo ":$p stopped"
  fi
done
echo "cloudflared (if any) stopped; GPU memory freed when processes exit."
