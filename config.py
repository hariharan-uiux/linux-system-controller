import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Python / Lib Environment
VENV_PYTHON = BASE_DIR / ".venv" / "bin" / "python"
CUDA_LIB_DIR = "/usr/local/lib/ollama/cuda_v12"

# Piper TTS Configuration
MODELS_DIR = BASE_DIR / "models"
PIPER_MODEL_PATH = MODELS_DIR / "piper" / "en_US-lessac-medium.onnx"
PIPER_CONFIG_PATH = MODELS_DIR / "piper" / "en_US-lessac-medium.onnx.json"
PIPER_BINARY = (
    str(BASE_DIR / ".venv" / "bin" / "piper")
    if (BASE_DIR / ".venv" / "bin" / "piper").exists()
    else (shutil.which("piper") or "piper")
)

# System Control Defaults
HOME = Path.home()
APP_PATHS = {
    "chrome": str(HOME / "opt/google/chrome/chrome") if (HOME / "opt/google/chrome/chrome").exists() else (shutil.which("google-chrome") or shutil.which("chromium-browser") or "google-chrome"),
    "terminal": shutil.which("ptyxis") or shutil.which("gnome-terminal") or "/usr/bin/ptyxis",
    "obsidian": shutil.which("obsidian") or "/usr/bin/obsidian",
    "files": shutil.which("nautilus") or "/usr/bin/nautilus",
    "opencode": str(HOME / ".local/bin/opencode") if (HOME / ".local/bin/opencode").exists() else (shutil.which("opencode") or "opencode")
}
