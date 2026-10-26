import os
import sys
import time
import numpy as np
import sounddevice as sd
from typing import Optional, Callable
import config

# Ensure PipeWire/Pulse runtime socket is defined
if "XDG_RUNTIME_DIR" not in os.environ or not os.environ["XDG_RUNTIME_DIR"]:
    os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"

from openwakeword.model import Model

class AudioListener:
    def __init__(
        self,
        wake_words=config.WAKE_WORDS,
        threshold: float = config.WAKE_WORD_THRESHOLD,
        sample_rate: int = config.SAMPLE_RATE,
        chunk_size: int = config.AUDIO_CHUNK_SIZE
    ):
        self.wake_words = wake_words
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.is_running = False

        print("[AudioListener] Initializing openWakeWord models...")
        self.oww_model = Model()
        print(f"[AudioListener] Loaded wake models: {list(self.oww_model.models.keys())}")

    def listen_for_wake_word(self, on_wake: Optional[Callable] = None) -> np.ndarray:
        """
        Continuously listens to microphone until one of the configured wake words triggers.
        Once detected, captures the subsequent voice command until silence.
        Returns the captured speech audio as a float32 numpy array.
        """
        self.is_running = True
        print(f"[AudioListener] Listening for wake words: {self.wake_words} (threshold: {self.threshold})...")

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=config.AUDIO_CHANNELS,
            dtype="int16",
            blocksize=self.chunk_size
        ) as stream:
            while self.is_running:
                data, overflowed = stream.read(self.chunk_size)
                if overflowed:
                    pass

                chunk = data[:, 0]  # Mono 1D int16
                predictions = self.oww_model.predict(chunk)

                # Check if any target wake word crossed threshold
                for word in self.wake_words:
                    score = predictions.get(word, 0.0)
                    if score >= self.threshold:
                        print(f"\n[AudioListener] Wake word detected: '{word}' (score: {score:.2f})!")
                        if on_wake:
                            on_wake(word)
                        # Immediately record user's command
                        return self._record_voice_command(stream)

    def _record_voice_command(self, stream) -> np.ndarray:
        """Records speech until voice activity ceases (silence detection)."""
        print("[AudioListener] Listening for your command...")
        recorded_frames = []
        silence_start = None
        has_spoken = False
        start_time = time.time()
        max_duration = 10.0  # Cap command at 10 seconds

        while time.time() - start_time < max_duration:
            data, _ = stream.read(self.chunk_size)
            chunk = data[:, 0]
            recorded_frames.append(chunk)

            # Energy calculation (RMS)
            energy = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))

            if energy > config.ENERGY_THRESHOLD:
                has_spoken = True
                silence_start = None
            else:
                if has_spoken:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start >= config.VAD_SILENCE_DURATION:
                        print("[AudioListener] Silence detected, command captured.")
                        break

        if not recorded_frames:
            return np.zeros(0, dtype=np.float32)

        full_audio_int16 = np.concatenate(recorded_frames)
        # Normalize to float32 [-1.0, 1.0] for Whisper
        return full_audio_int16.astype(np.float32) / 32768.0

    def record_push_to_talk(self, duration_limit: float = 6.0) -> np.ndarray:
        """Record directly from microphone without wake word (Push-to-Talk)."""
        print("[AudioListener] Recording command (speak now)...")
        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=config.AUDIO_CHANNELS,
            dtype="int16",
            blocksize=self.chunk_size
        ) as stream:
            recorded_frames = []
            silence_start = None
            has_spoken = False
            start_time = time.time()

            while time.time() - start_time < duration_limit:
                data, _ = stream.read(self.chunk_size)
                chunk = data[:, 0]
                recorded_frames.append(chunk)

                energy = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
                if energy > config.ENERGY_THRESHOLD:
                    has_spoken = True
                    silence_start = None
                else:
                    if has_spoken:
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start >= config.VAD_SILENCE_DURATION:
                            break

        if not recorded_frames:
            return np.zeros(0, dtype=np.float32)

        full_audio_int16 = np.concatenate(recorded_frames)
        return full_audio_int16.astype(np.float32) / 32768.0

if __name__ == "__main__":
    listener = AudioListener()
    print("Testing Push-to-Talk recording for 3 seconds...")
    audio = listener.record_push_to_talk(duration_limit=3.0)
    print(f"Captured {len(audio)} samples ({len(audio)/16000:.2f}s).")
