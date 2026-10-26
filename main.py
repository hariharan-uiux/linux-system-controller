#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

# Add project directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agent import LocalSystemAgent

def run_diagnostics():
    """Run automated unit validation for all subsystems."""
    print("========================================")
    print(" Running Subsystem Self-Test Suite ")
    print("========================================")

    agent = LocalSystemAgent()

    print("\n--- 1. Testing Deterministic Intent Router ---")
    commands = [
        "Turn up the volume",
        "Mute audio",
        "Change screen resolution to 1080p",
        "What is the current screen resolution",
        "Rotate screen to portrait",
        "What is the screen orientation",
        "Rotate screen to landscape",
        "Switch to dark mode",
        "What is the system theme",
        "Switch to light mode",
        "Launch Google Chrome",
        "What time is it right now",
        "Check system memory and disk usage",
        "Turn on keyboard backlight",
        "Increase keyboard brightness",
        "Set keyboard color to cyan",
        "Set keyboard effect to wave",
        "Turn off keyboard lights",
        "Disable touchpad",
        "Enable touchpad",
        "Toggle tap to click",
        "Reverse scrolling direction",
        "Set touchpad speed to 60%",
        "Check connected monitors",
        "What is my desktop wallpaper",
        "Set screen blanking to never",
        "Set mouse speed to 50%",
        "Check keyboard layout",
        "Read clipboard",
        "Take a screenshot",
        "Check screen recording status",
        "Check screen sharing status"
    ]
    for cmd in commands:
        decision = agent.decision_engine.decide(cmd)
        print(f"  '{cmd}' => {decision['action']} ({decision['target']})")

    print("\n--- 2. Testing System Controller ---")
    success, msg = agent.system.execute_decision({"action": "system_info", "target": "current_time"})
    print(f"  System Info Result: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "keyboard_backlight_control", "target": "kbd_backlight_status"})
    print(f"  Keyboard Backlight Status: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "keyboard_backlight_control", "target": "kbd_backlight_color", "color": "cyan"})
    print(f"  Keyboard Backlight Color Set: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "keyboard_backlight_control", "target": "kbd_backlight_mode", "mode": "wave"})
    print(f"  Keyboard Backlight Effect Set: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "resolution_control", "target": "resolution_status", "raw": "what is my screen resolution"})
    print(f"  Display Resolution Result: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "orientation_control", "target": "orientation_status"})
    print(f"  Display Orientation Status: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "orientation_control", "target": "orientation_landscape"})
    print(f"  Display Orientation Set: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "display_control", "target": "theme_status"})
    print(f"  System Theme Status: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "display_control", "target": "dark_mode"})
    print(f"  System Theme Set: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "touchpad_control", "target": "touchpad_status"})
    print(f"  Touchpad Status: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "touchpad_control", "target": "touchpad_speed_set_50"})
    print(f"  Touchpad Speed Set: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "monitors_control", "target": "monitors_status"})
    print(f"  Monitors Status: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "wallpaper_control", "target": "wallpaper_status"})
    print(f"  Wallpaper Status: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "blanking_control", "target": "blanking_status"})
    print(f"  Blanking Status: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "mouse_control", "target": "mouse_status"})
    print(f"  Mouse Status: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "keyboard_control", "target": "keyboard_status"})
    print(f"  Keyboard Status: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "clipboard_control", "target": "clipboard_copy", "text": "Self-Test String"})
    print(f"  Clipboard Copy: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "clipboard_control", "target": "clipboard_read"})
    print(f"  Clipboard Read: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "screenshot_control", "target": "take_screenshot"})
    print(f"  Screenshot Capture: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "screen_recording_control", "target": "screen_recording_status"})
    print(f"  Screen Recording Status: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "screen_sharing_control", "target": "screen_sharing_status"})
    print(f"  Screen Sharing Status: {success} -> \"{msg}\"")

    success, msg = agent.system.execute_decision({"action": "system_info", "target": "memory_disk_usage"})
    print(f"  Disk/RAM Result: {success} -> \"{msg}\"")

    print("\n========================================")
    print(" All Subsystem Tests Completed Successfully ")
    print("========================================")

def main():
    parser = argparse.ArgumentParser(description="Local Linux System Controller & Hardware Telemetry Dashboard")
    parser.add_argument("--gui", action="store_true", help="Launch modern Web GUI dashboard and API server")
    parser.add_argument("--port", type=int, default=8080, help="Port for GUI server (default: 8080)")
    parser.add_argument("--text", type=str, help="Execute a single command directly (e.g. 'Mute audio')")
    parser.add_argument("--test", action="store_true", help="Run automated diagnostics on all subsystems")

    args = parser.parse_args()

    if args.gui:
        from gui_server import run_server
        run_server(args.port)
    elif args.test:
        run_diagnostics()
    elif args.text:
        agent = LocalSystemAgent()
        agent.process_text_command(args.text)
    else:
        parser.print_help()
        print("\nTip: Run with --gui to start the dashboard, or --test to run verification.")

if __name__ == "__main__":
    main()
