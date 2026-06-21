#!/usr/bin/env bash
# Run ON a DGX box from inside the cloned hub repo. Commits + pushes ONLY the
# sanitized hub artifacts (inventory/, results/, configs/, plans/, ops logs).
# Refuses to push if a secret-looking value slipped through the .gitignore.
set -euo pipefail

BRANCH="claude/kind-wozniak-3x8eh3"
cd "$(git rev-parse --show-toplevel)"

git add spark-hub/ spark_ops_log.md 2>/dev/null || true

# ── tripwire: block obvious secret material before it leaves the box ──────────
STAGED="$(git diff --cached --name-only)"
if [ -z "$STAGED" ]; then echo "[push] nothing to sync"; exit 0; fi
if git diff --cached -U0 | grep -nE \
   'sk-ant-|sk-[A-Za-z0-9]{20}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY|eyJ[A-Za-z0-9_-]{20,}' ; then
  echo "[ABORT] secret-looking content in staged diff — NOT pushing. Sanitize first." >&2
  git reset -q
  exit 1
fi

git commit -q -m "hub sync from $(hostname -s) $(date +%F_%H:%M)" || { echo "[push] no change"; exit 0; }
for d in 2 4 8 16; do
  git push -u origin "$BRANCH" && { echo "[push] ok"; exit 0; }
  echo "[push] retry in ${d}s..."; sleep "$d"
done
echo "[push] FAILED after retries" >&2; exit 1
