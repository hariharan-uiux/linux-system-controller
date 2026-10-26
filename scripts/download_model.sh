#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

mkdir -p models/piper

MODEL_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
TARGET_FILE="models/piper/en_US-lessac-medium.onnx"

if [ -f "$TARGET_FILE" ]; then
    echo "[Info] Model already exists at $TARGET_FILE"
    exit 0
fi

echo "[Info] Downloading Piper TTS model..."
curl -L -o "$TARGET_FILE" "$MODEL_URL"
echo "[Success] Model downloaded to $TARGET_FILE"
