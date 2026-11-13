#!/usr/bin/env bash
set -euo pipefail

# Atomic symlink release with automatic rollback on failed healthcheck.
# Usage:
#   ./deploy/atomic_release.sh /opt/app/releases/v1.2.3 /opt/app/current "curl -fsS http://127.0.0.1:8000/health"

if [ "$#" -lt 3 ]; then
  echo "Usage: $0 <release_dir> <current_symlink> <healthcheck_cmd>" >&2
  exit 2
fi

RELEASE_DIR="$1"
CURRENT_LINK="$2"
HEALTHCHECK_CMD="$3"

if [ ! -d "$RELEASE_DIR" ]; then
  echo "Release directory does not exist: $RELEASE_DIR" >&2
  exit 2
fi

PREV_TARGET=""
if [ -L "$CURRENT_LINK" ]; then
  PREV_TARGET="$(readlink "$CURRENT_LINK")"
fi

rollback() {
  if [ -n "$PREV_TARGET" ] && [ -d "$PREV_TARGET" ]; then
    ln -sfn "$PREV_TARGET" "$CURRENT_LINK"
    echo "Rollback executed: restored $CURRENT_LINK -> $PREV_TARGET" >&2
  else
    rm -f "$CURRENT_LINK"
    echo "Rollback executed: removed failed symlink $CURRENT_LINK" >&2
  fi
}

ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
echo "Switched $CURRENT_LINK -> $RELEASE_DIR"

if ! bash -c "$HEALTHCHECK_CMD"; then
  echo "Healthcheck failed after switching to $RELEASE_DIR" >&2
  rollback
  exit 1
fi

echo "Release verified and active: $RELEASE_DIR"
