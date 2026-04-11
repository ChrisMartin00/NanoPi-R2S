#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-/usr/local/bin}"
TARGET_BIN="${TARGET_DIR}/upgrade-download-linux"
SOURCE_SCRIPT="${SCRIPT_DIR}/tools/upgrade_download_linux.py"

if [[ ! -f "${SOURCE_SCRIPT}" ]]; then
  echo "error: source script not found: ${SOURCE_SCRIPT}" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required" >&2
  exit 1
fi

mkdir -p "${TARGET_DIR}"
install -m 0755 "${SOURCE_SCRIPT}" "${TARGET_BIN}"

echo "Installed: ${TARGET_BIN}"
echo "Tip: install optional runtime dependency for serial probing:"
echo "  python3 -m pip install --user pyserial"
