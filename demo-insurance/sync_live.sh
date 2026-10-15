#!/usr/bin/env bash
# Deploy the repo demo tree to the live demo tree (rsync --checksum --delete).
#
#   sync_live.sh [--dry-run] [TARGET_DIR]
#
# TARGET_DIR defaults to $DEMO_LIVE_DIR, then the live machine path
# /home/lunarpulse/AI/catalog/decision-study/demo-insurance.
# Preserved on the target (never deleted/overwritten): checkpoints (*ckpt*),
# studio-runs/, logs, studio-token.txt, tunnel-url.txt, VERSION (rewritten here),
# __pycache__/, .venv*.
# Also syncs ../docs/LAYA_DECIDER_EXPERIMENT_REPORT.md into <target>/../docs/ and
# writes `git rev-parse --short HEAD` (+ "-dirty" if the repo tree is dirty) to
# <target>/VERSION — shown by GET /stats and the console footer.
# --dry-run lists what would change and exits 1 while anything differs (CI-usable).
set -euo pipefail
cd "$(dirname "$0")"
SRC="$(pwd -P)"

DRY_RUN=0
TARGET=""
for a in "$@"; do
  case "$a" in
    --dry-run) DRY_RUN=1 ;;
    -h | --help)
      sed -n '2,10p' "$0"
      exit 0
      ;;
    *)
      [ -z "$TARGET" ] || { echo "[sync] unexpected extra argument: $a"; exit 2; }
      TARGET="$a"
      ;;
  esac
done
TARGET="${TARGET:-${DEMO_LIVE_DIR:-/home/lunarpulse/AI/catalog/decision-study/demo-insurance}}"

command -v rsync >/dev/null || { echo "[sync] rsync not found"; exit 1; }
command -v git >/dev/null || { echo "[sync] git not found"; exit 1; }
SRC_T="$(realpath "$SRC")"
TGT_T="$(realpath -m "$TARGET")"
[ -d "$TGT_T" ] || { echo "[sync] target is not a directory: $TGT_T (create it first)"; exit 1; }
[ "$SRC_T" != "$TGT_T" ] || { echo "[sync] refusing: target equals the repo source tree"; exit 1; }

EXCL=(
  --exclude '*ckpt*'
  --exclude 'studio-runs/'
  --exclude '*.log'
  --exclude 'studio-token.txt'
  --exclude 'tunnel-url.txt'
  --exclude 'VERSION'
  --exclude '__pycache__/'
  --exclude '.venv*'
)

DOC_SRC="$SRC/../docs/LAYA_DECIDER_EXPERIMENT_REPORT.md"
DOC_TGT_DIR="$TGT_T/../docs"

HEAD="$(git -C "$SRC" rev-parse --short HEAD)"
[ -n "$(git -C "$SRC" status --porcelain)" ] && VER="$HEAD-dirty" || VER="$HEAD"

fail=0

# --- main tree ---------------------------------------------------------------
LIST="$(rsync -a --checksum --delete --omit-dir-times --dry-run --itemize-changes "${EXCL[@]}" "$SRC/" "$TGT_T/")"
if [ -n "$LIST" ]; then
  fail=1
  echo "[sync] demo tree changes:"
  printf '%s\n' "$LIST"
else
  echo "[sync] demo tree in sync."
fi

# --- experiment report -------------------------------------------------------
if [ -f "$DOC_SRC" ]; then
  if ! cmp -s "$DOC_SRC" "$DOC_TGT_DIR/LAYA_DECIDER_EXPERIMENT_REPORT.md"; then
    fail=1
    echo "[sync] report differs: $DOC_SRC -> $DOC_TGT_DIR/"
  else
    echo "[sync] report in sync."
  fi
else
  echo "[sync] WARNING: $DOC_SRC missing — /report will 404"
fi

# --- VERSION -----------------------------------------------------------------
if [ -f "$TGT_T/VERSION" ] && [ "$(cat "$TGT_T/VERSION")" = "$VER" ]; then
  echo "[sync] VERSION already $VER"
else
  fail=1
  echo "[sync] VERSION would be: $VER (was: $(cat "$TGT_T/VERSION" 2>/dev/null || echo '<none>'))"
fi

if [ "$DRY_RUN" = 1 ]; then
  [ "$fail" = 0 ] && echo "[sync] dry-run: nothing to do."
  exit "$fail"
fi

rsync -a --checksum --delete --omit-dir-times "${EXCL[@]}" "$SRC/" "$TGT_T/"
if [ -f "$DOC_SRC" ]; then
  mkdir -p "$DOC_TGT_DIR"
  rsync -a --checksum "$DOC_SRC" "$DOC_TGT_DIR/"
fi
printf '%s\n' "$VER" >"$TGT_T/.VERSION.tmp"
mv "$TGT_T/.VERSION.tmp" "$TGT_T/VERSION"
echo "[sync] deployed to $TGT_T (VERSION=$VER). Restart services to pick up code changes:"
echo "[sync]   systemctl --user restart decision-demo-laya decision-demo-decider decision-demo-studio"
