import os
import sys
from typing import Optional, Dict, Any, Tuple

from system_controller import SystemController
from decision_engine import DecisionEngine
import config

class LocalSystemAgent:
    """
    Local Linux System Agent for system hardware telemetry, volume, display,
    power profiles, application launcher, and connectivity control.
    """
    def __init__(self, init_audio_listener: bool = False):
        print("=== Initializing Local System Agent ===")
        self.system = SystemController()
        self.decision_engine = DecisionEngine()
        print("=== Local System Agent Ready ===")

    def process_text_command(self, text: str) -> str:
        """Run text command directly through deterministic parser -> System Execution."""
        if not text or not text.strip():
            return "No command provided."

        print(f"\n[Command Received] \"{text}\"")
        decision = self.decision_engine.decide(text)
        success, feedback = self.system.execute_decision(decision)
        print(f"[System Execution] Success: {success} | Feedback: \"{feedback}\"")
        return feedback

# Backwards compatibility alias
LocalVoiceAgent = LocalSystemAgent

if __name__ == "__main__":
    agent = LocalSystemAgent()
    agent.process_text_command("Check current time")
