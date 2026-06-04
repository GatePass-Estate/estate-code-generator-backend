#!/usr/bin/env sh
# Security scanner wrapper.
# Runs security_scanner.py with sane defaults, works on Linux / macOS / WSL.
#
# Usage:
#   ./scripts/scan.sh               # quick scan of cwd
#   ./scripts/scan.sh --all         # full scan + harden
#   ./scripts/scan.sh --ci          # CI mode (JSON, exits 1 on any finding)
#   ./scripts/scan.sh --changed-only # only files changed since last commit
#   CI=true ./scripts/scan.sh       # same as --ci (auto-detected in GitHub Actions)

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCANNER="$SCRIPT_DIR/security_scanner.py"

# Prefer python3; fall back to python.
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "ERROR: python3 (or python) not found. Install Python 3.8+ and retry." >&2
    exit 2
fi

# Require Python 3.8+
PY_VER=$("$PY" -c "import sys; print(sys.version_info >= (3,8))" 2>/dev/null || echo "False")
if [ "$PY_VER" != "True" ]; then
    echo "ERROR: Python 3.8 or newer is required." >&2
    exit 2
fi

# Pass all arguments straight through so every scanner flag is accessible.
exec "$PY" "$SCANNER" "$@"
