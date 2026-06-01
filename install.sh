#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: $PYTHON_BIN is not available." >&2
  exit 1
fi

if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  echo "Error: pip is not available for $PYTHON_BIN." >&2
  exit 1
fi

INSTALL_ARGS=()
INSTALL_TARGET="the active Python environment"

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  INSTALL_ARGS+=(--user)
  INSTALL_TARGET="your user site-packages"
fi

echo "Installing panalyzer from $ROOT_DIR into $INSTALL_TARGET"
if ! "$PYTHON_BIN" -m pip install "${INSTALL_ARGS[@]}" "$ROOT_DIR"; then
  echo "Standard install failed. Retrying without build isolation for offline/local installs."
  "$PYTHON_BIN" -m pip install "${INSTALL_ARGS[@]}" --no-build-isolation "$ROOT_DIR"
fi

SCRIPT_DIR="$("$PYTHON_BIN" - <<'PY'
import os
import site
import sys
from pathlib import Path

if os.environ.get("VIRTUAL_ENV"):
    print(Path(sys.executable).resolve().parent)
else:
    print(site.getuserbase())
PY
)"

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  BIN_DIR="$SCRIPT_DIR/bin"
  echo "Installed script path: $BIN_DIR/panalyzer"
  echo "If 'panalyzer' is not found, add this to your shell profile:"
  echo "  export PATH=\"$BIN_DIR:\$PATH\""
else
  echo "Installed script path: $SCRIPT_DIR/panalyzer"
fi

echo
echo "Smoke test:"
echo "  panalyzer \"$ROOT_DIR\""
