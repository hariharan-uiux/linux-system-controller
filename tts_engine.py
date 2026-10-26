import os
import subprocess
import tempfile
import threading
from pathlib import Path
import config

class TTSEngine:
    def __init__(self, model_path: Path = config.PIPER_MODEL_PATH, config_path: Path = config.PIPER_CONFIG_PATH):
        self.model_path = str(model_path)
        self.config_path = str(config_path)
        self.piper_bin = str(config.PIPER_BINARY)
        self._validate_setup()

    def _validate_setup(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Piper model not found at {self.model_path}")
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Piper config not found at {self.config_path}")

    def speak(self, text: str, block: bool = True):
        """Synthesize text and play audio locally."""
        if not text or not text.strip():
            return

        text = text.strip()
        print(f"[TTS] Speaking: \"{text}\"")

        def _run():
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_wav = tmp_file.name

            try:
                # Run Piper TTS
                cmd = [
                    self.piper_bin,
                    "-m", self.model_path,
                    "-c", self.config_path,
                    "-f", tmp_wav
                ]
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True
                )
                proc.communicate(input=text)

                if proc.returncode == 0 and os.path.exists(tmp_wav):
                    # Play via pw-play or aplay
                    player = "pw-play" if os.path.exists("/usr/bin/pw-play") else "aplay"
                    env = os.environ.copy()
                    if "XDG_RUNTIME_DIR" not in env:
                        env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
                    subprocess.run([player, tmp_wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
            finally:
                if os.path.exists(tmp_wav):
                    try:
                        os.remove(tmp_wav)
                    except OSError:
                        pass

        if block:
            _run()
        else:
            threading.Thread(target=_run, daemon=True).start()

if __name__ == "__main__":
    import sys
    engine = TTSEngine()
    msg = sys.argv[1] if len(sys.argv) > 1 else "Piper local neural voice engine is online."
    engine.speak(msg)
