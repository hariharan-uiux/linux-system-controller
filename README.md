# Linux System Controller & Hardware Telemetry Dashboard

A local Linux desktop controller and hardware telemetry dashboard for Ubuntu Linux that controls system volume, display resolution, brightness, power profiles, media playback, application launching, and hardware vitals via a web interface and command CLI.

---

## Features

- **Hardware Telemetry:** Real-time GPU (RTX 4070 temp, load, VRAM, power draw), CPU utilization, RAM, NVMe storage, and battery metrics.
- **Display Management:** Native Wayland & X11 display resolution switching (`2560x1600`, `1920x1200`, `1080p`, etc.) via Mutter D-Bus & `xrandr`, panel brightness control (`brightnessctl`), and GNOME Night Light.
- **Audio & Media:** PipeWire volume & mic controls (`wpctl`), MPRIS media playback control (`playerctl`).
- **Session & Power:** Power profile management (`performance`, `balanced`, `power-saver`), lock screen, Do Not Disturb, Wi-Fi, and Bluetooth.
- **Interactive Web Dashboard:** Zero-dependency `http.server.ThreadingHTTPServer` dashboard with animated SVG dials (`gauge-ui.dev`), dual-view mode switcher, and live activity stream.
- **Deterministic Intent Router:** Instant sub-millisecond keyword/regex command interpreter with zero ML overhead.

---

## Quick Start

### 1. Launch Web GUI Dashboard
```bash
./run.sh --gui
# Access via browser at http://localhost:8080
```

### 2. Run Subsystem Self-Test Suite
```bash
./run.sh --test
```

### 3. Execute Single Command (CLI Mode)
```bash
./run.sh --text "Turn up the volume"
./run.sh --text "Change screen resolution to 1080p"
./run.sh --text "Set resolution to 2560x1600"
./run.sh --text "Check system memory and disk usage"
```

---

## Supported Commands

| Category | Actions | Examples |
|---|---|---|
| **Volume** | `volume_up`, `volume_down`, `mute_toggle` | "Turn up the volume", "Mute audio" |
| **Display Resolution** | `resolution_set`, `resolution_status`, `resolution_up`, `resolution_down` | "Change screen resolution to 1080p", "What is my resolution", "Decrease resolution" |
| **Brightness** | `brightness_up`, `brightness_down`, `night_light_toggle` | "Increase brightness", "Toggle night light" |
| **Media** | `play_pause`, `next_track`, `previous_track` | "Play music", "Next track" |
| **Power & Session** | `lock_screen`, `power_profile_performance`, `power_profile_balanced`, `power_profile_saver` | "Lock screen", "Set performance mode" |
| **Connectivity** | `wifi_toggle`, `bluetooth_toggle`, `dnd_toggle` | "Toggle WiFi", "Enable Bluetooth", "Do not disturb" |
| **System Info** | `current_time`, `battery_status`, `gpu_status`, `memory_disk_usage` | "What time is it", "Check GPU temp", "Check battery" |
| **App Launcher** | `chrome`, `terminal`, `obsidian`, `files` | "Launch Chrome", "Open terminal" |

---

## Architecture

```
[Web Dashboard / CLI] → [Deterministic Intent Router] → [System Controller]
                                                        │
                                                        ├──> wpctl (Audio)
                                                        ├──> brightnessctl / Mutter D-Bus (Display)
                                                        ├──> playerctl (Media)
                                                        ├──> powerprofilesctl (Power)
                                                        ├──> nmcli / bluetoothctl (Connectivity)
                                                        ├──> loginctl (Session)
                                                        └──> Desktop Apps (Launch)
```

---

## Project Structure

```
system_controller.py    # Core system actions & telemetry
decision_engine.py      # Deterministic intent router (Laya replacement)
agent.py                # CLI agent entry point
gui_server.py           # Web dashboard (ThreadingHTTPServer)
voice_agent_widget.html # Desktop widget (Hermes)
main.py                 # CLI commands & test suite
config.py               # App paths & environment
```

---

## Requirements

- Python 3.10+ with `psutil`, `numpy`
- GNOME Mutter (Wayland) or X11 for display control
- PipeWire + `wpctl` for audio
- `brightnessctl` (with video group/sudo) for brightness
- `playerctl` for MPRIS media
- `nvidia-smi` for GPU telemetry

Virtual environment is self-contained in `.venv/`.

---

## Development

```bash
# Run GUI server
./run.sh --gui --port 8080

# Run tests
./run.sh --test

# Direct command
./run.sh --text "Set brightness to 80%"
```