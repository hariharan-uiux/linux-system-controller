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
    if command -v python3 >/dev/null 2>&1; then
        echo "[Info] .venv not found. Auto-creating virtual environment..."
        python3 -m venv "$SCRIPT_DIR/.venv" 2>/dev/null || true
        if [ -f "$SCRIPT_DIR/.venv/bin/pip" ] && [ -f "$SCRIPT_DIR/requirements.txt" ]; then
            "$SCRIPT_DIR/.venv/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt" || true
        fi
    fi
fi

if [ ! -f "$PYTHON_BIN" ]; then
    if command -v python3 >/dev/null 2>&1; then
        echo "[Warn] Falling back to system python3"
        PYTHON_BIN="python3"
    else
        echo "[Error] Python virtualenv binary not found at $PYTHON_BIN and system python3 is not available"
        exit 1
    fi
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/main.py" "$@"
