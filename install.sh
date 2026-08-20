#!/usr/bin/env bash
# Installs the herdr-fanout configurator onto this machine.
#
# Usage:
#   ./install.sh
#
# Copies herdr_fanout.py to ~/.local/bin/herdr-fanout. Run this script from
# a checkout of this herdr-fanout directory (it installs its own sibling
# file, wherever that checkout lives).

set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${HOME}/.local/bin"
DEST="${DEST_DIR}/herdr-fanout"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required, not found on PATH" >&2
  exit 1
fi

if ! python3 -c "import yaml" >/dev/null 2>&1; then
  echo "PyYAML not found, installing..."
  python3 -m pip install --user pyyaml
fi

if ! command -v herdr >/dev/null 2>&1; then
  echo "warning: herdr is not on PATH. Install herdr first: https://herdr.dev" >&2
fi

mkdir -p "$DEST_DIR"
cp "${SRC_DIR}/herdr_fanout.py" "$DEST"
chmod +x "$DEST"

echo "installed: $DEST"
case ":$PATH:" in
  *":${DEST_DIR}:"*) ;;
  *) echo "note: ${DEST_DIR} is not on your PATH. Add it in your shell profile." ;;
esac

echo
echo "next:"
echo "  herdr-fanout init my-fanout.yaml   # write an example config"
echo "  herdr-fanout apply my-fanout.yaml  # build the layout (run inside a herdr pane)"
