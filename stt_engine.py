import os
import sys
import numpy as np
from pathlib import Path
import config

# Ensure CUDA library directory is visible if present
if os.path.exists(config.CUDA_LIB_DIR):
    current_ld = os.environ.get("LD_LIBRARY_PATH", "")
    if config.CUDA_LIB_DIR not in current_ld:
        os.environ["LD_LIBRARY_PATH"] = f"{config.CUDA_LIB_DIR}:{current_ld}"

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

class STTEngine:
    def __init__(self, model_size: str = config.WHISPER_MODEL_SIZE):
        self.model_size = model_size
        self.model = None
        self._init_model()

    def _init_model(self):
        if WhisperModel is None:
            raise RuntimeError("faster-whisper is not installed in the active environment.")

        # Attempt CUDA initialization first (NVIDIA RTX 4070)
        try:
            print(f"[STT] Initializing faster-whisper ({self.model_size}) on CUDA...")
            self.model = WhisperModel(self.model_size, device="cuda", compute_type="float16")
            print("[STT] faster-whisper initialized on CUDA (float16).")
            return
        except Exception as e:
            print(f"[STT] CUDA init warning ({e}). Falling back to CPU (int8)...")

        # Fallback to CPU int8
        try:
            self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            print("[STT] faster-whisper initialized on CPU (int8).")
        except Exception as err:
            raise RuntimeError(f"Failed to load faster-whisper model: {err}")

    def transcribe(self, audio_data) -> str:
        """
        Transcribe audio input.
        audio_data can be a file path (str/Path) or a 1D numpy array of float32 samples (16kHz).
        """
        if self.model is None:
            raise RuntimeError("STT model is not loaded.")

        if isinstance(audio_data, (str, Path)):
            audio_input = str(audio_data)
        elif isinstance(audio_data, np.ndarray):
            # Ensure float32 normalized between -1.0 and 1.0
            if audio_data.dtype != np.float32:
                audio_input = audio_data.astype(np.float32)
                max_val = np.max(np.abs(audio_input))
                if max_val > 1.0:
                    audio_input = audio_input / 32768.0
            else:
                audio_input = audio_data
        else:
            raise ValueError(f"Unsupported audio data type: {type(audio_data)}")

        segments, info = self.model.transcribe(
            audio_input,
            beam_size=5,
            language="en",
            condition_on_previous_text=False
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        print(f"[STT] Transcribed text: \"{text}\"")
        return text

if __name__ == "__main__":
    import sys
    engine = STTEngine()
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        result = engine.transcribe(sys.argv[1])
        print("Result:", result)
    else:
        print("STT Engine initialized successfully.")
