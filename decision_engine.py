import os
import sys
from pathlib import Path
from typing import Dict, Any

from system_controller import SystemController

class LayaDecisionEngine:
    """
    Deterministic rule-based intent router (Laya replacement, zero external ML dependencies).
    """
    def __init__(self):
        print("[DecisionEngine] Initializing Deterministic Intent Router (Zero-Dependency)...")
        self.controller = SystemController()
        print("[DecisionEngine] Deterministic Intent Router ready.")

    def decide(self, command_text: str) -> Dict[str, Any]:
        """
        Evaluate text command deterministically in sub-millisecond time.
        """
        decision = self.controller.parse_command(command_text)
        print(f"[DecisionEngine] Parsed: {decision['action']} -> {decision['target']}")
        return decision

# Alias for clean naming
DecisionEngine = LayaDecisionEngine

if __name__ == "__main__":
    engine = DecisionEngine()
    test_cmd = sys.argv[1] if len(sys.argv) > 1 else "Increase system volume"
    print(engine.decide(test_cmd))
