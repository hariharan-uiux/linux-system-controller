#!/usr/bin/env bash
set -e

# Base directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configure Runtime Environment for PipeWire Audio and CUDA
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export LD_LIBRARY_PATH="/usr/local/lib/ollama/cuda_v12:${LD_LIBRARY_PATH:-}"

# Dedicated Python Virtual Environment for System Controller
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"

if [ ! -f "$PYTHON_BIN" ]; then
    echo "[Error] Python virtualenv binary not found at $PYTHON_BIN"
    exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/main.py" "$@"
