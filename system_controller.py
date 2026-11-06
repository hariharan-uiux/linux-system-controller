import os
import sys
import re
import glob
import fcntl
import subprocess
import datetime
import time
import shutil
import psutil
from typing import Dict, Any, Tuple
import config

if "/usr/lib/python3/dist-packages" not in sys.path:
    sys.path.append("/usr/lib/python3/dist-packages")

# Keyboard Backlight & RGB Hardware Constants
HIDIOCSFEATURE_11 = 0xC00B4806

KBD_EFFECT_MODES = {
    "static": 0x02,
    "breathe": 0x04,
    "breathing": 0x04,
    "neon": 0x05,
    "wave": 0x07,
    "rainbow": 0x07,
    "zoom": 0x09,
    "meteor": 0x0A,
    "twinkle": 0x0B,
}

KBD_COLOR_MAP = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "white": (255, 255, 255),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "purple": (138, 43, 226),
    "yellow": (255, 255, 0),
    "orange": (255, 128, 0),
    "amber": (255, 191, 0),
    "pink": (255, 105, 180),
    "ice blue": (150, 220, 255),
    "warm white": (255, 240, 200),
}

class SystemController:
    def __init__(self):
        self.env = os.environ.copy()
        uid = os.getuid()
        if "XDG_RUNTIME_DIR" not in self.env or not self.env["XDG_RUNTIME_DIR"]:
            self.env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
        if "DBUS_SESSION_BUS_ADDRESS" not in self.env or not self.env["DBUS_SESSION_BUS_ADDRESS"]:
            self.env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"
        if "DISPLAY" not in self.env:
            self.env["DISPLAY"] = ":0"
        
        self.kbd_backend = None
        self.kbd_device = None
        self.kbd_supported = False
        self.kbd_state = {
            "brightness": 100,
            "enabled": True,
            "mode": "wave",
            "color": "#00ffff",
            "speed": 5
        }
        self.recording_proc = None
        self.recording_file = None
        self.recording_start_t = 0
        self.screencast_active = False
        self.screencast_proxy = None
        self._init_keyboard_backlight()

    def execute_decision(self, decision: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Execute the action determined by Laya.
        Returns: (success_bool, speech_feedback_text)
        """
        action = decision.get("action")
        target = decision.get("target")
        raw = decision.get("raw", "")

        # Volume Controls
        if action == "volume_control":
            return self._handle_volume(target)

        # Keyboard Backlight & RGB Controls
        elif action == "keyboard_backlight_control" or (target and target.startswith("kbd_backlight_")):
            if target == "kbd_backlight_status":
                info = self.get_keyboard_backlight_info()
                if not info["supported"]:
                    return False, "Keyboard backlight hardware is not detected on this system."
                if not info["enabled"] or info["brightness"] == 0:
                    return True, "Keyboard backlight is currently turned off."
                return True, f"Keyboard backlight is on at {info['brightness']} percent brightness in {info['mode']} mode."
            elif target == "kbd_backlight_on":
                last_bri = self.kbd_state.get("brightness", 100)
                if last_bri <= 0:
                    last_bri = 100
                return self.set_keyboard_backlight_percent(last_bri)
            elif target == "kbd_backlight_off":
                return self.set_keyboard_backlight_percent(0)
            elif target == "kbd_backlight_toggle":
                return self.set_keyboard_backlight_toggle()
            elif target == "kbd_backlight_up":
                return self.step_keyboard_backlight("up", 20)
            elif target == "kbd_backlight_down":
                return self.step_keyboard_backlight("down", 20)
            elif target and target.startswith("kbd_backlight_set_"):
                try:
                    pct = int(target.replace("kbd_backlight_set_", "").replace("%", ""))
                    return self.set_keyboard_backlight_percent(pct)
                except ValueError:
                    pass
            elif target == "kbd_backlight_set":
                m = re.search(r"(\d+)\s*%?", raw)
                if m:
                    return self.set_keyboard_backlight_percent(int(m.group(1)))
                return self.set_keyboard_backlight_percent(80)
            elif target == "kbd_backlight_color":
                col = decision.get("color") or raw
                return self.set_keyboard_backlight_color(col)
            elif target == "kbd_backlight_mode":
                mod = decision.get("mode") or raw
                return self.set_keyboard_backlight_mode(mod)
            return False, "Unknown keyboard backlight command."

        # Display & Resolution & Orientation Controls
        elif action in ("display_control", "resolution_control", "orientation_control") or target in ("resolution_set", "resolution_status", "resolution_up", "resolution_down", "orientation_status", "orientation_landscape", "orientation_portrait", "orientation_inverted", "orientation_left", "orientation_rotate", "orientation_set") or (target and (target.startswith("resolution_") or target.startswith("orientation_"))):
            if target == "brightness_up":
                res = subprocess.run(["sudo", "brightnessctl", "set", "10%+"], capture_output=True, text=True)
                return res.returncode == 0, "Brightness increased by 10 percent."
            elif target == "brightness_down":
                res = subprocess.run(["sudo", "brightnessctl", "set", "10%-"], capture_output=True, text=True)
                return res.returncode == 0, "Brightness decreased by 10 percent."
            elif target == "night_light_toggle":
                curr = self.get_night_light()
                return self.set_night_light(not curr)
            elif target == "dark_mode":
                return self.set_color_scheme("dark")
            elif target == "light_mode":
                return self.set_color_scheme("light")
            elif target in ("theme_toggle", "color_scheme_toggle"):
                return self.toggle_color_scheme()
            elif target == "theme_status":
                curr = self.get_color_scheme()
                return True, f"The system theme is currently in {curr} mode."
            elif target == "resolution_status":
                info = self.get_display_info()
                res_str = info.get("current_resolution", "unknown")
                hz = info.get("current_refresh", 60)
                return True, f"The display resolution is currently {res_str} at {int(round(hz))} Hertz."
            elif target == "resolution_up":
                return self.step_display_resolution(direction="up")
            elif target == "resolution_down":
                return self.step_display_resolution(direction="down")
            elif target == "orientation_status":
                info = self.get_display_info()
                orient = info.get("orientation", "normal")
                return True, f"The display orientation is currently {orient}."
            elif target == "orientation_landscape":
                return self.set_display_orientation("normal")
            elif target == "orientation_portrait":
                return self.set_display_orientation("right")
            elif target == "orientation_inverted":
                return self.set_display_orientation("inverted")
            elif target == "orientation_left":
                return self.set_display_orientation("left")
            elif target == "orientation_rotate":
                info = self.get_display_info()
                curr_t = info.get("transform", 0)
                return self.set_display_orientation(str((curr_t + 1) % 4))
            elif target == "orientation_set" or (target and target.startswith("orientation_")) or action == "orientation_control":
                orient_param = target.replace("orientation_", "") if (target and target.startswith("orientation_") and target != "orientation_set") else raw
                return self.set_display_orientation(orient_param)
            elif target == "resolution_set" or (target and target.startswith("resolution_")) or action == "resolution_control":
                # Check if user asked to query current resolution
                low_raw = raw.lower()
                if any(q in low_raw for q in ["what is", "current", "tell me", "check"]) and "resolution" in low_raw:
                    info = self.get_display_info()
                    res_str = info.get("current_resolution", "unknown")
                    hz = info.get("current_refresh", 60)
                    return True, f"The display resolution is currently {res_str} at {int(round(hz))} Hertz."

                if any(w in low_raw for w in ["decrease", "lower", "down", "reduce", "smaller"]):
                    return self.step_display_resolution(direction="down")
                elif any(w in low_raw for w in ["increase", "higher", "up", "raise", "larger"]):
                    return self.step_display_resolution(direction="up")

                res_param = ""
                if target and target.startswith("resolution_") and target not in ("resolution_set", "resolution_status", "resolution_up", "resolution_down"):
                    res_param = target.replace("resolution_", "")
                else:
                    res_param = raw
                return self.set_display_resolution(res_param)
            return False, "Unknown display command."

        # Mic Controls
        elif action == "mic_control":
            if target == "mic_mute_toggle":
                return self.set_mic_mute_toggle()
            elif target == "mic_volume_up":
                res = subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SOURCE@", "10%+"], env=self.env, capture_output=True, text=True)
                return res.returncode == 0, "Microphone volume increased."
            elif target == "mic_volume_down":
                res = subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SOURCE@", "10%-"], env=self.env, capture_output=True, text=True)
                return res.returncode == 0, "Microphone volume decreased."
            return False, "Unknown microphone command."

        # Connectivity Controls
        elif action == "connectivity_control":
            if target == "wifi_toggle":
                curr = self.get_wifi_info()["enabled"]
                return self.set_wifi(not curr)
            elif target == "bluetooth_toggle":
                curr = self.get_bluetooth_info()["enabled"]
                return self.set_bluetooth(not curr)
            elif target == "dnd_toggle":
                curr = self.get_dnd()
                return self.set_dnd(not curr)
            return False, "Unknown connectivity command."

        # Touchpad Controls
        elif action == "touchpad_control" or (target and target.startswith("touchpad_")):
            if target == "touchpad_status":
                info = self.get_touchpad_info()
                state_str = "enabled" if info["enabled"] else "disabled"
                return True, f"Touchpad is currently {state_str} at {info['speed_percent']} percent speed. Tap-to-click is {'on' if info['tap_to_click'] else 'off'}."
            elif target == "touchpad_on":
                return self.set_touchpad_enabled(True)
            elif target == "touchpad_off":
                return self.set_touchpad_enabled(False)
            elif target == "touchpad_toggle":
                return self.set_touchpad_toggle()
            elif target in ("touchpad_tap_toggle", "touchpad_tap_to_click_toggle"):
                return self.set_touchpad_tap_to_click_toggle()
            elif target in ("touchpad_natural_scroll_toggle", "touchpad_scroll_toggle"):
                return self.set_touchpad_natural_scroll_toggle()
            elif target and target.startswith("touchpad_speed_set_"):
                try:
                    pct = int(target.replace("touchpad_speed_set_", "").replace("%", ""))
                    return self.set_touchpad_speed_percent(pct)
                except ValueError:
                    pass
            elif target == "touchpad_speed_up":
                return self.step_touchpad_speed("up", 15)
            elif target == "touchpad_speed_down":
                return self.step_touchpad_speed("down", 15)
            elif target == "touchpad_speed":
                m = re.search(r"(\d+)\s*%?", raw)
                if m:
                    return self.set_touchpad_speed_percent(int(m.group(1)))
                return self.set_touchpad_speed_percent(50)
            return False, "Unknown touchpad command."

        # Session & Power Controls
        elif action == "session_control":
            if target == "lock_screen":
                return self.lock_screen()
            elif target == "power_profile_performance":
                return self.set_power_profile("performance")
            elif target == "power_profile_balanced":
                return self.set_power_profile("balanced")
            elif target == "power_profile_saver":
                return self.set_power_profile("power-saver")
            return False, "Unknown session command."

        # Monitors & Multi-Display
        elif action == "monitors_control" or target in ("monitors_status", "monitors_query"):
            info = self.get_monitors_info()
            if info["multi_monitor"]:
                conns = ", ".join([m["connector"] for m in info["monitors"]])
                return True, f"Multi-monitor active with {info['count']} displays ({conns}). Primary is {info['primary']}."
            return True, f"Single display active on {info['primary']}."

        # Wallpaper Controls
        elif action == "wallpaper_control" or (target and target.startswith("wallpaper_")):
            if target == "wallpaper_status":
                info = self.get_wallpaper_info()
                return True, f"Current desktop wallpaper is set to {info['filename']}."
            elif target.startswith("wallpaper_set_"):
                val = target.replace("wallpaper_set_", "")
                return self.set_wallpaper(val)
            elif target == "wallpaper_set":
                path = decision.get("path") or raw
                return self.set_wallpaper(path)
            return False, "Unknown wallpaper command."

        # Screensaver & Idle Blanking Controls
        elif action == "blanking_control" or (target and target.startswith("blanking_")):
            if target == "blanking_status":
                info = self.get_screen_blanking_info()
                return True, f"Screen blanking idle delay is set to {info['label']}."
            elif target.startswith("blanking_set_"):
                try:
                    secs = int(target.replace("blanking_set_", ""))
                    return self.set_screen_blanking(secs)
                except ValueError:
                    return self.set_screen_blanking(0)
            elif target == "blanking_never":
                return self.set_screen_blanking(0)
            elif target == "blanking_5min":
                return self.set_screen_blanking(300)
            elif target == "blanking_10min":
                return self.set_screen_blanking(600)
            elif target == "blanking_15min":
                return self.set_screen_blanking(900)
            return False, "Unknown screen blanking command."

        # Mouse & Pointer Controls
        elif action == "mouse_control" or (target and target.startswith("mouse_")):
            if target == "mouse_status":
                info = self.get_mouse_info()
                return True, f"Mouse speed is {info['speed_percent']} percent. Natural scroll is {'on' if info['natural_scroll'] else 'off'}."
            elif target == "mouse_natural_scroll_toggle":
                info = self.get_mouse_info()
                return self.set_mouse_natural_scroll(not info["natural_scroll"])
            elif target and target.startswith("mouse_speed_set_"):
                try:
                    pct = int(target.replace("mouse_speed_set_", ""))
                    val = (pct / 50.0) - 1.0
                    return self.set_mouse_speed(val)
                except ValueError:
                    pass
            return False, "Unknown mouse command."

        # Keyboard Controls
        elif action == "keyboard_control" or (target and target.startswith("keyboard_")):
            if target == "keyboard_status":
                info = self.get_keyboard_info()
                return True, f"Keyboard layout sources: {info['sources']} (repeat interval: {info['repeat_interval_ms']}ms)."
            elif target == "keyboard_fast_repeat":
                return self.set_keyboard_repeat_rate(20, 250)
            elif target == "keyboard_default_repeat":
                return self.set_keyboard_repeat_rate(30, 500)
            return False, "Unknown keyboard command."

        # Clipboard Controls
        elif action == "clipboard_control" or (target and target.startswith("clipboard_")):
            if target in ("clipboard_read", "clipboard_status", "clipboard_get"):
                return self.get_clipboard_text()
            elif target == "clipboard_clear":
                return self.clear_clipboard()
            elif target == "clipboard_copy":
                text = decision.get("text", "")
                return self.set_clipboard_text(text)
            return False, "Unknown clipboard command."

        # Screenshot Controls
        elif action == "screenshot_control" or target in ("take_screenshot", "screenshot_capture"):
            success, msg, _ = self.take_screenshot()
            return success, msg

        # Screen Recording Controls
        elif action == "screen_recording_control" or (target and target.startswith("screen_recording_")):
            if target in ("screen_recording_start", "start_recording"):
                success, msg, _ = self.start_screen_recording()
                return success, msg
            elif target in ("screen_recording_stop", "stop_recording"):
                res = self.stop_screen_recording()
                return res[0], res[1]
            elif target in ("screen_recording_status", "recording_status"):
                stat = self.get_screen_recording_status()
                if stat["active"]:
                    return True, f"Screen recording is active ({stat['elapsed_seconds']}s elapsed, file: {stat['file']})."
                return True, "No screen recording is currently active."
            return False, "Unknown screen recording command."

        # Screen Sharing Controls
        elif action == "screen_sharing_control" or (target and target.startswith("screen_sharing_")):
            if target in ("screen_sharing_status", "sharing_status"):
                info = self.get_screen_sharing_info()
                state = "enabled" if info["active"] else "disabled"
                return True, f"Screen sharing (RDP) is currently {state}."
            elif target == "screen_sharing_toggle":
                info = self.get_screen_sharing_info()
                return self.set_screen_sharing(not info["active"])
            elif target == "screen_sharing_on":
                return self.set_screen_sharing(True)
            elif target == "screen_sharing_off":
                return self.set_screen_sharing(False)
            return False, "Unknown screen sharing command."

        # Media Controls
        elif action == "media_control":
            return self._handle_media(target)

        # App Launching
        elif action == "app_launcher":
            return self._handle_app(target)

        # System Information
        elif action == "system_info":
            if target == "gpu_status":
                gpu = self.get_gpu_vitals()
                if gpu["available"]:
                    return True, f"NVIDIA RTX 4070 is at {gpu['temp_c']} degrees Celsius, utilizing {gpu['utilization_pct']} percent, with {gpu['vram_used_mb']} megabytes of VRAM in use."
                return True, "No dedicated NVIDIA GPU telemetry available."
            return self._handle_system_info(target)

        # Custom Shell Execution
        elif action == "shell_command":
            return self._handle_shell(raw)

        # Fallback / General
        else:
            return True, f"I heard: {raw}. No direct system command matched."

    def _handle_volume(self, target: str) -> Tuple[bool, str]:
        if target == "volume_up":
            cmd = ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "10%+"]
            msg = "Volume increased."
        elif target == "volume_down":
            cmd = ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "10%-"]
            msg = "Volume decreased."
        elif target == "mute_toggle":
            cmd = ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]
            msg = "Audio mute toggled."
        else:
            return False, "Unknown volume command."

        res = subprocess.run(cmd, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return res.returncode == 0, msg

    def _handle_media(self, target: str) -> Tuple[bool, str]:
        if not shutil.which("playerctl"):
            return False, "playerctl is not available."

        if target == "play_pause":
            cmd = ["playerctl", "play-pause"]
            msg = "Media playback toggled."
        elif target == "next_track":
            cmd = ["playerctl", "next"]
            msg = "Skipping to next track."
        elif target == "previous_track":
            cmd = ["playerctl", "previous"]
            msg = "Skipping to previous track."
        else:
            return False, "Unknown media action."

        res = subprocess.run(cmd, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return res.returncode == 0, msg

    def _handle_app(self, target: str) -> Tuple[bool, str]:
        path = config.APP_PATHS.get(target)
        if not path or not os.path.exists(path):
            # Try finding binary in PATH
            found = shutil.which(target)
            if not found:
                return False, f"Could not find application {target} on system."
            path = found

        name = target.capitalize()
        # Launch detached from current process
        subprocess.Popen(
            [path],
            env=self.env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return True, f"Launching {name}."

    def _handle_system_info(self, target: str) -> Tuple[bool, str]:
        if target == "current_time":
            now = datetime.datetime.now().strftime("%I:%M %p")
            return True, f"The current time is {now}."

        elif target == "battery_status":
            battery = psutil.sensors_battery()
            if battery:
                percent = int(battery.percent)
                charging = "charging" if battery.power_plugged else "on battery"
                return True, f"Battery is at {percent} percent, {charging}."
            else:
                return True, "No battery detected; system is on AC power."

        elif target == "memory_disk_usage":
            mem = psutil.virtual_memory()
            disk = shutil.disk_usage("/")
            mem_pct = int(mem.percent)
            disk_pct = int((disk.used / disk.total) * 100)
            return True, f"Memory usage is at {mem_pct} percent, and disk is at {disk_pct} percent."

        else:
            return True, "System status is healthy and operational."

    def _handle_shell(self, raw_command: str) -> Tuple[bool, str]:
        # Extract meaningful shell task or run safe command
        print(f"[SystemController] Executing command context: {raw_command}")
        return True, f"Processing system request: {raw_command}"

    def get_volume_info(self) -> Dict[str, Any]:
        try:
            res = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], env=self.env, capture_output=True, text=True)
            if res.returncode == 0:
                output = res.stdout.strip()
                parts = output.split()
                vol = 0.0
                muted = "[MUTED]" in output
                if len(parts) >= 2:
                    try:
                        vol = float(parts[1])
                    except ValueError:
                        pass
                return {"volume": int(round(vol * 100)), "muted": muted}
        except Exception:
            pass
        return {"volume": 50, "muted": False}

    def set_volume_percent(self, percent: int) -> Tuple[bool, str]:
        val = max(0, min(150, int(percent)))
        vol_float = val / 100.0
        res = subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{vol_float:.2f}"], env=self.env, capture_output=True, text=True)
        return res.returncode == 0, f"Volume set to {val}%."

    def get_media_info(self) -> Dict[str, Any]:
        if not shutil.which("playerctl"):
            return {"active": False, "status": "No playerctl", "title": "", "artist": ""}
        try:
            status_res = subprocess.run(["playerctl", "status"], env=self.env, capture_output=True, text=True)
            if status_res.returncode == 0:
                status = status_res.stdout.strip()
                title_res = subprocess.run(["playerctl", "metadata", "title"], env=self.env, capture_output=True, text=True)
                title = title_res.stdout.strip() if title_res.returncode == 0 else ""
                artist_res = subprocess.run(["playerctl", "metadata", "artist"], env=self.env, capture_output=True, text=True)
                artist = artist_res.stdout.strip() if artist_res.returncode == 0 else ""
                return {"active": True, "status": status, "title": title, "artist": artist}
        except Exception:
            pass
        return {"active": False, "status": "Stopped", "title": "", "artist": ""}

    def get_system_telemetry(self) -> Dict[str, Any]:
        mem = psutil.virtual_memory()
        disk = shutil.disk_usage("/")
        battery = psutil.sensors_battery()
        bat_info = None
        if battery:
            bat_info = {
                "percent": int(battery.percent),
                "power_plugged": battery.power_plugged
            }

        # CPU Temp
        cpu_temp = None
        try:
            temps = psutil.sensors_temperatures()
            if "coretemp" in temps and temps["coretemp"]:
                cpu_temp = int(temps["coretemp"][0].current)
            elif "acpitz_0" in temps and temps["acpitz_0"]:
                cpu_temp = int(temps["acpitz_0"][0].current)
        except Exception:
            pass

        # Uptime
        uptime_str = ""
        try:
            boot_t = psutil.boot_time()
            uptime_secs = int(time.time() - boot_t)
            hours, remainder = divmod(uptime_secs, 3600)
            minutes, _ = divmod(remainder, 60)
            uptime_str = f"{hours}h {minutes}m"
        except Exception:
            uptime_str = "N/A"

        # IP address
        ip_addr = "127.0.0.1"
        try:
            res = subprocess.run(["hostname", "-I"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                ip_addr = res.stdout.strip().split()[0]
        except Exception:
            pass

        return {
            "time": datetime.datetime.now().strftime("%I:%M %p"),
            "uptime": uptime_str,
            "ip": ip_addr,
            "ram_percent": int(mem.percent),
            "ram_used_gb": round(mem.used / (1024**3), 1),
            "ram_total_gb": round(mem.total / (1024**3), 1),
            "disk_percent": int((disk.used / disk.total) * 100),
            "disk_used_gb": round(disk.used / (1024**3), 1),
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "cpu_percent": int(psutil.cpu_percent(interval=0.05)),
            "cpu_temp_c": cpu_temp,
            "battery": bat_info,
            "gpu": self.get_gpu_vitals(),
            "brightness": self.get_brightness_info(),
            "keyboard_backlight": self.get_keyboard_backlight_info(),
            "display": self.get_display_info(),
            "mic": self.get_mic_info(),
            "power_profile": self.get_power_profile(),
            "night_light": self.get_night_light(),
            "color_scheme": self.get_color_scheme(),
            "dnd": self.get_dnd(),
            "wifi": self.get_wifi_info(),
            "bluetooth": self.get_bluetooth_info(),
            "touchpad": self.get_touchpad_info(),
            "monitors": self.get_monitors_info(),
            "wallpaper": self.get_wallpaper_info(),
            "blanking": self.get_screen_blanking_info(),
            "mouse": self.get_mouse_info(),
            "keyboard": self.get_keyboard_info(),
            "screen_recording": self.get_screen_recording_status(),
            "screen_sharing": self.get_screen_sharing_info()
        }

    def get_display_info(self) -> Dict[str, Any]:
        """
        Query current display resolution, refresh rate, scaling, and available modes.
        Uses GNOME Mutter DisplayConfig over D-Bus when available, with fallback to xrandr.
        """
        # 1. Try GNOME Mutter D-Bus (native under Wayland & X11)
        try:
            import gi
            from gi.repository import Gio
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            proxy = Gio.DBusProxy.new_sync(
                bus,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.gnome.Mutter.DisplayConfig",
                "/org/gnome/Mutter/DisplayConfig",
                "org.gnome.Mutter.DisplayConfig",
                None
            )
            state = proxy.GetCurrentState()
            serial, monitors, logical_monitors, properties = state
            if monitors:
                connector_info, modes, props = monitors[0]
                connector = connector_info[0]

                current_w, current_h = 0, 0
                current_refresh = 60.0
                unique_resolutions = []
                seen_res = set()

                for m in modes:
                    m_id, w, h, refresh, pref_scale, supported_scales, mode_props = m
                    res_str = f"{w}x{h}"
                    if res_str not in seen_res:
                        seen_res.add(res_str)
                        unique_resolutions.append(res_str)
                    if mode_props.get("is-current"):
                        current_w, current_h = w, h
                        current_refresh = round(float(refresh), 1)

                scale = 1.0
                transform = 0
                if logical_monitors:
                    scale = round(float(logical_monitors[0][2]), 2)
                    if len(logical_monitors[0]) > 3:
                        try:
                            transform = int(logical_monitors[0][3])
                        except (ValueError, TypeError):
                            transform = 0

                transform_names = {0: "normal", 1: "right", 2: "inverted", 3: "left"}
                orientation_str = transform_names.get(transform, "normal")

                return {
                    "connector": connector,
                    "current_resolution": f"{current_w}x{current_h}",
                    "current_refresh": current_refresh,
                    "scale": scale,
                    "orientation": orientation_str,
                    "transform": transform,
                    "resolutions": unique_resolutions[:10]
                }
        except Exception:
            pass

        # 2. Fallback to xrandr
        try:
            res = subprocess.run(["xrandr", "--current"], env=self.env, capture_output=True, text=True)
            if res.returncode == 0:
                lines = res.stdout.splitlines()
                connector = "default"
                current_w, current_h = 1920, 1080
                current_refresh = 60.0
                unique_resolutions = []
                seen_res = set()
                transform = 0

                for line in lines:
                    if " connected " in line:
                        connector = line.split()[0]
                        if " left " in line:
                            transform = 3
                        elif " right " in line:
                            transform = 1
                        elif " inverted " in line:
                            transform = 2
                        else:
                            transform = 0
                    # Parse mode line: e.g. "   3840x2400    239.94*+"
                    m_res = re.match(r"^\s+(\d+)x(\d+)\s+([\d\.\*\+]+)", line)
                    if m_res:
                        w, h = int(m_res.group(1)), int(m_res.group(2))
                        res_str = f"{w}x{h}"
                        if res_str not in seen_res:
                            seen_res.add(res_str)
                            unique_resolutions.append(res_str)
                        if "*" in m_res.group(3):
                            current_w, current_h = w, h
                            m_hz = re.search(r"([\d\.]+)\*", m_res.group(3))
                            if m_hz:
                                current_refresh = round(float(m_hz.group(1)), 1)

                transform_names = {0: "normal", 1: "right", 2: "inverted", 3: "left"}
                orientation_str = transform_names.get(transform, "normal")

                return {
                    "connector": connector,
                    "current_resolution": f"{current_w}x{current_h}",
                    "current_refresh": current_refresh,
                    "scale": 1.0,
                    "orientation": orientation_str,
                    "transform": transform,
                    "resolutions": unique_resolutions[:10]
                }
        except Exception:
            pass

        return {
            "connector": "Unknown",
            "current_resolution": "2560x1600",
            "current_refresh": 240.0,
            "scale": 1.0,
            "orientation": "normal",
            "transform": 0,
            "resolutions": ["2560x1600", "2560x1440", "1920x1200", "1920x1080", "1280x720"]
        }

    def set_display_resolution(self, resolution_input: str) -> Tuple[bool, str]:
        """
        Set the display resolution dynamically via GNOME Mutter D-Bus or xrandr.
        Accepts formats: '1080p', '1920x1080', '1920 by 1080', '2560x1600', 'max', 'native', etc.
        """
        if not resolution_input:
            return False, "No resolution specified."

        low = resolution_input.lower().strip()

        alias_map = {
            "1080p": (1920, 1080),
            "fhd": (1920, 1080),
            "720p": (1280, 720),
            "hd": (1280, 720),
            "1440p": (2560, 1440),
            "2k": (2560, 1440),
            "qhd": (2560, 1440),
            "qhd+": (2560, 1600),
            "1200p": (1920, 1200),
            "fhd+": (1920, 1200),
            "4k": (3840, 2160),
            "uhd": (3840, 2160),
        }

        target_w, target_h = None, None

        if low in alias_map:
            target_w, target_h = alias_map[low]
        elif "1080" in low:
            target_w, target_h = (1920, 1080)
        elif "720" in low:
            target_w, target_h = (1280, 720)
        elif "1200" in low:
            target_w, target_h = (1920, 1200)
        elif "1600" in low:
            target_w, target_h = (2560, 1600)
        elif "1440" in low:
            target_w, target_h = (2560, 1440)
        elif any(k in low for k in ("native", "max", "highest", "default")):
            info = self.get_display_info()
            if info.get("resolutions"):
                highest = info["resolutions"][0]
                m_h = re.match(r"(\d+)x(\d+)", highest)
                if m_h:
                    target_w, target_h = int(m_h.group(1)), int(m_h.group(2))
        else:
            m_dim = re.search(r"(\d{3,4})\s*(?:x|by|\*)\s*(\d{3,4})", low)
            if m_dim:
                target_w, target_h = int(m_dim.group(1)), int(m_dim.group(2))

        if not target_w or not target_h:
            return False, f"Could not recognize resolution from '{resolution_input}'."

        # 1. Attempt GNOME Mutter DisplayConfig D-Bus application
        try:
            import gi
            from gi.repository import Gio
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            proxy = Gio.DBusProxy.new_sync(
                bus,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.gnome.Mutter.DisplayConfig",
                "/org/gnome/Mutter/DisplayConfig",
                "org.gnome.Mutter.DisplayConfig",
                None
            )
            state = proxy.GetCurrentState()
            serial, monitors, logical_monitors, properties = state
            if monitors:
                connector_info, modes, props = monitors[0]
                connector = connector_info[0]

                # Find mode matching target dimensions
                matching_modes = [m for m in modes if m[1] == target_w and m[2] == target_h]
                if matching_modes:
                    # Prefer highest refresh rate
                    best_mode = sorted(matching_modes, key=lambda m: m[3], reverse=True)[0]
                    mode_id, w, h, refresh, pref_scale, supported_scales, mode_props = best_mode

                    current_scale = logical_monitors[0][2] if logical_monitors else 1.0
                    chosen_scale = current_scale if current_scale in supported_scales else pref_scale

                    # Method 1 = TEMPORARY (activates mode change immediately)
                    proxy.ApplyMonitorsConfig(
                        "(uua(iiduba(ssa{sv}))a{sv})",
                        serial,
                        1,
                        [(0, 0, chosen_scale, 0, True, [(connector, mode_id, {})])],
                        {}
                    )
                    return True, f"Display resolution set to {target_w} by {target_h} at {int(round(refresh))} Hertz."
        except Exception as e:
            print(f"[SystemController] Mutter ApplyMonitorsConfig notice: {e}")

        # 2. Fallback to xrandr
        try:
            info = self.get_display_info()
            connector = info.get("connector", "eDP-1")
            res = subprocess.run(["xrandr", "--output", connector, "--mode", f"{target_w}x{target_h}"], env=self.env, capture_output=True, text=True)
            if res.returncode == 0:
                return True, f"Display resolution set to {target_w} by {target_h}."
            return False, f"Resolution {target_w}x{target_h} could not be applied: {res.stderr.strip() or 'Unknown error'}"
        except Exception as e:
            return False, f"Failed to set display resolution: {e}"

    def step_display_resolution(self, direction: str = "down") -> Tuple[bool, str]:
        """
        Step resolution up or down among available system presets.
        """
        info = self.get_display_info()
        available = info.get("resolutions", [])
        curr = info.get("current_resolution", "")
        if not available or not curr:
            return False, "Could not determine available display resolutions."

        try:
            curr_idx = available.index(curr)
        except ValueError:
            curr_idx = 0

        if direction == "down":
            new_idx = min(len(available) - 1, curr_idx + 1)
            if new_idx == curr_idx:
                return True, f"Display is already at the lowest configured preset ({curr})."
        else:
            new_idx = max(0, curr_idx - 1)
            if new_idx == curr_idx:
                return True, f"Display is already at the maximum resolution ({curr})."

        target_res = available[new_idx]
        return self.set_display_resolution(target_res)

    def set_display_orientation(self, orientation_input: str) -> Tuple[bool, str]:
        """
        Set display orientation dynamically via GNOME Mutter D-Bus or xrandr.
        Accepts: 'normal', 'landscape', 'portrait', 'right', 'inverted', 'left', 'upside down', '0', '90', '180', '270', etc.
        """
        if not orientation_input:
            return False, "No orientation specified."

        low = str(orientation_input).lower().strip()
        transform_target = None
        human_name = ""

        if any(w in low for w in ["normal", "landscape", "standard", "default", "horizontal"]) or low in ("0", "0°", "0 deg", "0 degrees"):
            transform_target = 0
            human_name = "normal landscape (0 degrees)"
        elif any(w in low for w in ["right", "portrait", "vertical", "clockwise"]) or low in ("90", "90°", "90 deg", "90 degrees"):
            transform_target = 1
            human_name = "portrait (90 degrees)"
        elif any(w in low for w in ["inverted", "upside down", "upsidedown", "flipped"]) or low in ("180", "180°", "180 deg", "180 degrees"):
            transform_target = 2
            human_name = "inverted (180 degrees)"
        elif any(w in low for w in ["left", "counter-clockwise", "anticlockwise"]) or low in ("270", "270°", "270 deg", "270 degrees"):
            transform_target = 3
            human_name = "portrait flipped (270 degrees)"
        elif any(w in low for w in ["rotate", "next", "cycle"]):
            info = self.get_display_info()
            curr = info.get("transform", 0)
            transform_target = (curr + 1) % 4
            names = {
                0: "normal landscape (0 degrees)",
                1: "portrait (90 degrees)",
                2: "inverted (180 degrees)",
                3: "portrait flipped (270 degrees)"
            }
            human_name = names.get(transform_target, "normal landscape (0 degrees)")
        else:
            return False, f"Unrecognized orientation: '{orientation_input}'."

        # 1. Attempt GNOME Mutter DisplayConfig D-Bus application
        try:
            import gi
            from gi.repository import Gio
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            proxy = Gio.DBusProxy.new_sync(
                bus,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.gnome.Mutter.DisplayConfig",
                "/org/gnome/Mutter/DisplayConfig",
                "org.gnome.Mutter.DisplayConfig",
                None
            )
            state = proxy.GetCurrentState()
            serial, monitors, logical_monitors, properties = state
            if monitors:
                connector_info, modes, props = monitors[0]
                connector = connector_info[0]

                current_mode_id = None
                for m in modes:
                    if m[6].get("is-current"):
                        current_mode_id = m[0]
                        break
                if not current_mode_id and modes:
                    current_mode_id = modes[0][0]

                current_scale = logical_monitors[0][2] if logical_monitors else 1.0

                proxy.ApplyMonitorsConfig(
                    "(uua(iiduba(ssa{sv}))a{sv})",
                    serial,
                    1,
                    [(0, 0, current_scale, transform_target, True, [(connector, current_mode_id, {})])],
                    {}
                )
                return True, f"Display orientation set to {human_name}."
        except Exception as e:
            print(f"[SystemController] Mutter ApplyMonitorsConfig orientation notice: {e}")

        # 2. Fallback to xrandr
        try:
            rot_map = {0: "normal", 1: "right", 2: "inverted", 3: "left"}
            rot_str = rot_map.get(transform_target, "normal")
            info = self.get_display_info()
            connector = info.get("connector", "eDP-1")
            res = subprocess.run(["xrandr", "--output", connector, "--rotate", rot_str], env=self.env, capture_output=True, text=True)
            if res.returncode == 0:
                return True, f"Display orientation set to {human_name}."
            return False, f"Orientation could not be applied: {res.stderr.strip() or 'Unknown error'}"
        except Exception as e:
            return False, f"Failed to set display orientation: {e}"

    def get_brightness_info(self) -> Dict[str, Any]:
        try:
            res = subprocess.run(["brightnessctl", "-m"], capture_output=True, text=True)
            if res.returncode == 0:
                parts = res.stdout.strip().split(",")
                if len(parts) >= 4:
                    pct = int(parts[3].replace("%", ""))
                    return {"brightness": pct}
        except Exception:
            pass
        return {"brightness": 50}

    def set_brightness_percent(self, percent: int) -> Tuple[bool, str]:
        val = max(1, min(100, int(percent)))
        res = subprocess.run(["sudo", "brightnessctl", "set", f"{val}%"], capture_output=True, text=True)
        return res.returncode == 0, f"Brightness set to {val}%."

    def _init_keyboard_backlight(self):
        """Discover keyboard backlight hardware backend."""
        self.kbd_backend = None
        self.kbd_device = None
        self.kbd_supported = False
        self.kbd_note = ""
        self.kbd_state = {
            "brightness": 100,
            "enabled": True,
            "mode": "wave",
            "color": "#00ffff",
            "speed": 5
        }

        # 1. Check if acpi_call is active (/proc/acpi/call) - works directly with \_SB.PC00.WMID.WMBH on Acer Predator
        if os.path.exists("/proc/acpi/call"):
            self.kbd_backend = "acpi_call"
            self.kbd_supported = True
            return

        # 2. Check if facer driver character device is loaded (/dev/acer-gkbbl-0)
        if os.path.exists("/dev/acer-gkbbl-0"):
            self.kbd_backend = "facer"
            self.kbd_device = "/dev/acer-gkbbl-0"
            self.kbd_supported = True
            return

        # 3. Check predatorctl CLI
        if shutil.which("predatorctl"):
            self.kbd_backend = "predatorctl"
            self.kbd_supported = True
            return

        # 4. Check standard Linux sysfs LED devices
        for pattern in ["/sys/class/leds/*kbd_backlight*", "/sys/class/leds/*::kbd_backlight*"]:
            matches = glob.glob(pattern)
            if matches:
                self.kbd_backend = "sysfs"
                self.kbd_device = matches[0]
                self.kbd_supported = True
                return

        # 5. Check brightnessctl for keyboard devices
        try:
            res = subprocess.run(["brightnessctl", "--device=*kbd_backlight*", "info"], capture_output=True, text=True)
            if res.returncode == 0:
                self.kbd_backend = "brightnessctl"
                self.kbd_device = "*kbd_backlight*"
                self.kbd_supported = True
                return
        except Exception:
            pass

        # 6. Check if this machine is an Acer Predator (e.g. PHN16-72)
        try:
            with open("/sys/devices/virtual/dmi/id/product_name", "r") as f:
                prod = f.read().strip()
                if "Predator" in prod or "Nitro" in prod or "PHN16" in prod:
                    self.kbd_backend = "acpi_wmi"
                    self.kbd_supported = False
                    self.kbd_note = (
                        "Acer Predator PHN16-72 keyboard lighting uses ACPI WMI (_SB.PC00.WMID.WMBH). "
                        "Because Secure Boot is enabled, the acpi_call kernel module requires MOK key enrollment to load. "
                        "Use physical Fn+F4/Fn+F5 keys or enroll MOK to enable software control."
                    )
                    return
        except Exception:
            pass

    def _write_kbd_hardware(self, mode: str = None, bri: int = None, color_rgb: Tuple[int, int, int] = None, speed: int = 5) -> bool:
        """Send hardware control to the detected keyboard backlight backend."""
        if not self.kbd_supported:
            return False

        if mode is None:
            mode = self.kbd_state.get("mode", "wave")
        if bri is None:
            bri = self.kbd_state.get("brightness", 100) if self.kbd_state.get("enabled", True) else 0
        if color_rgb is None:
            hex_c = self.kbd_state.get("color", "#00ffff").lstrip("#")
            try:
                color_rgb = tuple(int(hex_c[i:i+2], 16) for i in (0, 2, 4))
            except Exception:
                color_rgb = (0, 255, 255)

        # Backend 1: acpi_call (\_SB.PC00.WMID.WMBH command 0x14)
        if self.kbd_backend == "acpi_call":
            try:
                ACPI_MODES = {
                    "static": 0, "breathe": 1, "breathing": 1, "neon": 2,
                    "wave": 3, "rainbow": 3, "shifting": 4, "zoom": 5,
                    "meteor": 6, "twinkle": 7
                }
                m_code = ACPI_MODES.get(mode.lower(), 3)
                r, g, b = color_rgb if color_rgb else (0, 255, 255)
                payload = [
                    m_code if bri > 0 else 0,
                    max(1, min(9, int(speed))),
                    int(bri),
                    0,
                    1,
                    int(r), int(g), int(b),
                    3,
                    1,
                    0, 0, 0, 0, 0, 0
                ]
                hex_str = "".join(f"{b:02x}" for b in payload)
                call_cmd = f"\\_SB.PC00.WMID.WMBH 0 0x14 b{hex_str}"
                with open("/proc/acpi/call", "w") as f:
                    f.write(call_cmd)
                with open("/proc/acpi/call", "r") as f:
                    res = f.read().strip()
                return not res.startswith("Error")
            except Exception as e:
                print(f"[SystemController] acpi_call write failed: {e}")
                return False

        # Backend 2: facer (/dev/acer-gkbbl-0)
        elif self.kbd_backend == "facer" and self.kbd_device:
            try:
                ACPI_MODES = {
                    "static": 0, "breathe": 1, "breathing": 1, "neon": 2,
                    "wave": 3, "rainbow": 3, "shifting": 4, "zoom": 5,
                    "meteor": 6, "twinkle": 7
                }
                payload = [0] * 16
                payload[0] = ACPI_MODES.get(mode.lower(), 3)
                payload[1] = max(1, min(9, int(speed)))
                payload[2] = int(bri)
                payload[3] = 8 if payload[0] == 3 else 0
                payload[4] = 1
                payload[5], payload[6], payload[7] = color_rgb
                payload[9] = 1
                with open(self.kbd_device, "wb") as f:
                    f.write(bytes(payload))
                return True
            except Exception as e:
                print(f"[SystemController] facer write failed: {e}")
                return False

        # Backend 3: Standard Linux sysfs
        elif self.kbd_backend == "sysfs" and self.kbd_device:
            try:
                bri_file = os.path.join(self.kbd_device, "brightness")
                max_file = os.path.join(self.kbd_device, "max_brightness")
                max_val = 255
                if os.path.exists(max_file):
                    with open(max_file, "r") as f:
                        max_val = int(f.read().strip())
                target_val = int(round((bri / 100.0) * max_val))
                with open(bri_file, "w") as f:
                    f.write(str(target_val))
                return True
            except PermissionError:
                cmd = f"echo {target_val} | sudo tee {bri_file}"
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                return res.returncode == 0
            except Exception as e:
                print(f"[SystemController] sysfs write failed: {e}")
                return False

        # Backend 4: brightnessctl
        elif self.kbd_backend == "brightnessctl":
            try:
                res = subprocess.run(["sudo", "brightnessctl", "--device=*kbd_backlight*", "set", f"{bri}%"], capture_output=True, text=True)
                return res.returncode == 0
            except Exception as e:
                print(f"[SystemController] brightnessctl failed: {e}")
                return False

        # Backend 5: predatorctl CLI
        elif self.kbd_backend == "predatorctl":
            try:
                if bri <= 0:
                    res = subprocess.run(["predatorctl", "kb", "off"], capture_output=True, text=True)
                elif mode == "wave":
                    res = subprocess.run(["predatorctl", "kb", "wave", "--speed", str(speed)], capture_output=True, text=True)
                else:
                    hex_str = f"#{color_rgb[0]:02x}{color_rgb[1]:02x}{color_rgb[2]:02x}"
                    res = subprocess.run(["predatorctl", "kb", "static", hex_str, hex_str, hex_str, hex_str], capture_output=True, text=True)
                return res.returncode == 0
            except Exception as e:
                print(f"[SystemController] predatorctl failed: {e}")
                return False

        return False

    def get_keyboard_backlight_info(self) -> Dict[str, Any]:
        """Return live telemetry status for keyboard illumination."""
        if not self.kbd_supported:
            self._init_keyboard_backlight()

        return {
            "brightness": self.kbd_state.get("brightness", 100) if self.kbd_state.get("enabled", True) else 0,
            "max_brightness": 100,
            "enabled": self.kbd_state.get("enabled", True),
            "mode": self.kbd_state.get("mode", "wave"),
            "color": self.kbd_state.get("color", "#00ffff"),
            "speed": self.kbd_state.get("speed", 5),
            "supported": self.kbd_supported,
            "backend": self.kbd_backend or "none",
            "device": self.kbd_device or "none",
            "note": self.kbd_note
        }

    def set_keyboard_backlight_percent(self, percent: int) -> Tuple[bool, str]:
        """Set keyboard backlight brightness to a specific percentage (0-100)."""
        if not self.kbd_supported:
            msg = self.kbd_note if self.kbd_note else "Keyboard backlight hardware is not accessible on this system."
            return False, msg
        
        val = max(0, min(100, int(percent)))
        self.kbd_state["brightness"] = val
        self.kbd_state["enabled"] = val > 0
        success = self._write_kbd_hardware(bri=val)
        if val == 0:
            return success, "Keyboard backlight turned off."
        return success, f"Keyboard backlight brightness set to {val} percent."

    def step_keyboard_backlight(self, direction: str = "up", step: int = 20) -> Tuple[bool, str]:
        """Increment or decrement keyboard backlight brightness."""
        if not self.kbd_supported:
            msg = self.kbd_note if self.kbd_note else "Keyboard backlight hardware is not accessible on this system."
            return False, msg

        current = self.kbd_state.get("brightness", 100) if self.kbd_state.get("enabled", True) else 0
        if direction == "up":
            target_val = min(100, current + step if current > 0 else step)
        else:
            target_val = max(0, current - step)
        
        return self.set_keyboard_backlight_percent(target_val)

    def set_keyboard_backlight_toggle(self) -> Tuple[bool, str]:
        """Toggle keyboard backlight between on and off."""
        if not self.kbd_supported:
            msg = self.kbd_note if self.kbd_note else "Keyboard backlight hardware is not accessible on this system."
            return False, msg

        currently_on = self.kbd_state.get("enabled", True) and (self.kbd_state.get("brightness", 100) > 0)
        if currently_on:
            return self.set_keyboard_backlight_percent(0)
        else:
            last = self.kbd_state.get("brightness", 100)
            if last <= 0:
                last = 100
            return self.set_keyboard_backlight_percent(last)

    def set_keyboard_backlight_color(self, color_name_or_hex: str) -> Tuple[bool, str]:
        """Set static keyboard backlight color from name or hex code."""
        if not self.kbd_supported:
            msg = self.kbd_note if self.kbd_note else "Keyboard backlight hardware is not accessible on this system."
            return False, msg

        clean = color_name_or_hex.strip().lower()
        # Check named colors
        rgb = None
        for name, values in KBD_COLOR_MAP.items():
            if name in clean:
                rgb = values
                clean = name
                break

        # Check hex code
        if rgb is None:
            hex_match = re.search(r"#?([0-9a-f]{6})", clean)
            if hex_match:
                h = hex_match.group(1)
                rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
                clean = f"#{h}"
            else:
                rgb = (0, 255, 255)
                clean = "cyan"

        hex_repr = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        self.kbd_state["color"] = hex_repr
        self.kbd_state["mode"] = "static"
        self.kbd_state["enabled"] = True
        if self.kbd_state.get("brightness", 0) == 0:
            self.kbd_state["brightness"] = 100

        success = self._write_kbd_hardware(mode="static", bri=self.kbd_state["brightness"], color_rgb=rgb)
        return success, f"Keyboard backlight color set to {clean}."

    def set_keyboard_backlight_mode(self, mode: str) -> Tuple[bool, str]:
        """Set keyboard backlight animation effect mode (wave, static, breathe, neon, zoom, etc.)."""
        if not self.kbd_supported:
            msg = self.kbd_note if self.kbd_note else "Keyboard backlight hardware is not accessible on this system."
            return False, msg

        clean_mode = mode.strip().lower()
        matched_mode = "wave"
        for m in KBD_EFFECT_MODES.keys():
            if m in clean_mode:
                matched_mode = m
                break

        if "rainbow" in clean_mode:
            matched_mode = "wave"
        elif "breathing" in clean_mode:
            matched_mode = "breathe"

        self.kbd_state["mode"] = matched_mode
        self.kbd_state["enabled"] = True
        if self.kbd_state.get("brightness", 0) == 0:
            self.kbd_state["brightness"] = 100

        success = self._write_kbd_hardware(mode=matched_mode, bri=self.kbd_state["brightness"])
        return success, f"Keyboard backlight effect set to {matched_mode} mode."

    def get_mic_info(self) -> Dict[str, Any]:
        try:
            res = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"], env=self.env, capture_output=True, text=True)
            if res.returncode == 0:
                output = res.stdout.strip()
                parts = output.split()
                vol = 0.0
                muted = "[MUTED]" in output
                if len(parts) >= 2:
                    try:
                        vol = float(parts[1])
                    except ValueError:
                        pass
                return {"volume": int(round(vol * 100)), "muted": muted}
        except Exception:
            pass
        return {"volume": 100, "muted": False}

    def set_mic_mute_toggle(self) -> Tuple[bool, str]:
        res = subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"], env=self.env, capture_output=True, text=True)
        info = self.get_mic_info()
        state = "muted" if info["muted"] else "unmuted"
        return res.returncode == 0, f"Microphone {state}."

    def set_mic_volume_percent(self, percent: int) -> Tuple[bool, str]:
        val = max(0, min(150, int(percent)))
        vol_float = val / 100.0
        res = subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SOURCE@", f"{vol_float:.2f}"], env=self.env, capture_output=True, text=True)
        return res.returncode == 0, f"Microphone input set to {val}%."

    def get_gpu_vitals(self) -> Dict[str, Any]:
        try:
            res = subprocess.run([
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits"
            ], capture_output=True, text=True)
            if res.returncode == 0:
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                if len(parts) >= 5:
                    return {
                        "available": True,
                        "name": "NVIDIA GeForce RTX 4070",
                        "utilization_pct": int(parts[0]),
                        "vram_used_mb": int(parts[1]),
                        "vram_total_mb": int(parts[2]),
                        "temp_c": int(parts[3]),
                        "power_w": float(parts[4])
                    }
        except Exception:
            pass
        return {"available": False, "name": "N/A", "utilization_pct": 0, "vram_used_mb": 0, "vram_total_mb": 0, "temp_c": 0, "power_w": 0.0}

    def get_power_profile(self) -> str:
        try:
            res = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True)
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return "balanced"

    def set_power_profile(self, profile: str) -> Tuple[bool, str]:
        if profile not in ("performance", "balanced", "power-saver"):
            return False, f"Invalid power profile: {profile}"
        res = subprocess.run(["powerprofilesctl", "set", profile], capture_output=True, text=True)
        return res.returncode == 0, f"Power profile set to {profile}."

    def get_night_light(self) -> bool:
        try:
            res = subprocess.run(["gsettings", "get", "org.gnome.settings-daemon.plugins.color", "night-light-enabled"], env=self.env, capture_output=True, text=True)
            return "true" in res.stdout.lower()
        except Exception:
            return False

    def set_night_light(self, enable: bool) -> Tuple[bool, str]:
        val = "true" if enable else "false"
        res = subprocess.run(["gsettings", "set", "org.gnome.settings-daemon.plugins.color", "night-light-enabled", val], env=self.env, capture_output=True, text=True)
        return res.returncode == 0, f"Night Light {'enabled' if enable else 'disabled'}."

    def get_color_scheme(self) -> str:
        try:
            res = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"], env=self.env, capture_output=True, text=True)
            if "prefer-dark" in res.stdout.lower() or "dark" in res.stdout.lower():
                return "dark"
        except Exception:
            pass
        return "light"

    def set_color_scheme(self, mode: str) -> Tuple[bool, str]:
        target = mode.lower().strip()
        if target in ("dark", "prefer-dark", "night"):
            c_scheme = "prefer-dark"
            gtk_theme = "Yaru-dark"
            msg = "System dark mode enabled."
        else:
            c_scheme = "default"
            gtk_theme = "Yaru"
            msg = "System light mode enabled."

        r1 = subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", c_scheme], env=self.env, capture_output=True, text=True)
        r2 = subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", gtk_theme], env=self.env, capture_output=True, text=True)
        return (r1.returncode == 0 and r2.returncode == 0), msg

    def toggle_color_scheme(self) -> Tuple[bool, str]:
        curr = self.get_color_scheme()
        target = "light" if curr == "dark" else "dark"
        return self.set_color_scheme(target)

    def get_dnd(self) -> bool:
        try:
            res = subprocess.run(["gsettings", "get", "org.gnome.desktop.notifications", "show-banners"], env=self.env, capture_output=True, text=True)
            return "false" in res.stdout.lower()
        except Exception:
            return False

    def set_dnd(self, enable: bool) -> Tuple[bool, str]:
        val = "false" if enable else "true"
        res = subprocess.run(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", val], env=self.env, capture_output=True, text=True)
        return res.returncode == 0, f"Do Not Disturb {'activated' if enable else 'deactivated'}."

    def get_wifi_info(self) -> Dict[str, Any]:
        try:
            res = subprocess.run(["nmcli", "radio", "wifi"], capture_output=True, text=True)
            enabled = "enabled" in res.stdout.lower()
            ssid_res = subprocess.run(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"], capture_output=True, text=True)
            ssid = "Disconnected"
            for line in ssid_res.stdout.splitlines():
                if line.startswith("yes:"):
                    ssid = line.split(":", 1)[1]
                    break
            return {"enabled": enabled, "ssid": ssid}
        except Exception:
            return {"enabled": True, "ssid": "Unknown"}

    def set_wifi(self, enable: bool) -> Tuple[bool, str]:
        state = "on" if enable else "off"
        res = subprocess.run(["nmcli", "radio", "wifi", state], capture_output=True, text=True)
        return res.returncode == 0, f"Wi-Fi switched {state}."

    def get_bluetooth_info(self) -> Dict[str, Any]:
        try:
            res = subprocess.run(["bluetoothctl", "show"], capture_output=True, text=True)
            enabled = "Powered: yes" in res.stdout
            return {"enabled": enabled}
        except Exception:
            return {"enabled": True}

    def set_bluetooth(self, enable: bool) -> Tuple[bool, str]:
        state = "on" if enable else "off"
        res = subprocess.run(["bluetoothctl", "power", state], capture_output=True, text=True)
        return res.returncode == 0, f"Bluetooth switched {state}."

    def get_touchpad_info(self) -> Dict[str, Any]:
        """
        Query GNOME touchpad configuration via gsettings.
        """
        try:
            r_events = subprocess.run(["gsettings", "get", "org.gnome.desktop.peripherals.touchpad", "send-events"], env=self.env, capture_output=True, text=True)
            send_events = r_events.stdout.strip().strip("'\"") if r_events.returncode == 0 else "enabled"
            enabled = send_events == "enabled"

            r_tap = subprocess.run(["gsettings", "get", "org.gnome.desktop.peripherals.touchpad", "tap-to-click"], env=self.env, capture_output=True, text=True)
            tap_to_click = "true" in r_tap.stdout.lower() if r_tap.returncode == 0 else True

            r_nat = subprocess.run(["gsettings", "get", "org.gnome.desktop.peripherals.touchpad", "natural-scroll"], env=self.env, capture_output=True, text=True)
            natural_scroll = "true" in r_nat.stdout.lower() if r_nat.returncode == 0 else True

            r_spd = subprocess.run(["gsettings", "get", "org.gnome.desktop.peripherals.touchpad", "speed"], env=self.env, capture_output=True, text=True)
            speed = 0.0
            if r_spd.returncode == 0:
                try:
                    speed = float(r_spd.stdout.strip())
                except ValueError:
                    speed = 0.0
            
            speed_percent = int(round(((speed + 1.0) / 2.0) * 100))
            speed_percent = max(0, min(100, speed_percent))

            return {
                "supported": True,
                "enabled": enabled,
                "send_events": send_events,
                "tap_to_click": tap_to_click,
                "natural_scroll": natural_scroll,
                "speed": round(speed, 2),
                "speed_percent": speed_percent
            }
        except Exception as e:
            return {
                "supported": False,
                "enabled": True,
                "send_events": "enabled",
                "tap_to_click": True,
                "natural_scroll": True,
                "speed": 0.0,
                "speed_percent": 50,
                "error": str(e)
            }

    def set_touchpad_enabled(self, enable: bool) -> Tuple[bool, str]:
        val = "enabled" if enable else "disabled"
        res = subprocess.run(["gsettings", "set", "org.gnome.desktop.peripherals.touchpad", "send-events", val], env=self.env, capture_output=True, text=True)
        if res.returncode == 0:
            return True, f"Touchpad {'enabled' if enable else 'disabled'}."
        return False, f"Failed to set touchpad state: {res.stderr.strip()}"

    def set_touchpad_toggle(self) -> Tuple[bool, str]:
        info = self.get_touchpad_info()
        return self.set_touchpad_enabled(not info["enabled"])

    def set_touchpad_tap_to_click(self, enable: bool) -> Tuple[bool, str]:
        val = "true" if enable else "false"
        res = subprocess.run(["gsettings", "set", "org.gnome.desktop.peripherals.touchpad", "tap-to-click", val], env=self.env, capture_output=True, text=True)
        if res.returncode == 0:
            return True, f"Tap to click {'enabled' if enable else 'disabled'}."
        return False, f"Failed to set tap to click: {res.stderr.strip()}"

    def set_touchpad_tap_to_click_toggle(self) -> Tuple[bool, str]:
        info = self.get_touchpad_info()
        return self.set_touchpad_tap_to_click(not info["tap_to_click"])

    def set_touchpad_natural_scroll(self, enable: bool) -> Tuple[bool, str]:
        val = "true" if enable else "false"
        res = subprocess.run(["gsettings", "set", "org.gnome.desktop.peripherals.touchpad", "natural-scroll", val], env=self.env, capture_output=True, text=True)
        if res.returncode == 0:
            return True, f"Natural scrolling {'enabled' if enable else 'disabled'}."
        return False, f"Failed to set natural scrolling: {res.stderr.strip()}"

    def set_touchpad_natural_scroll_toggle(self) -> Tuple[bool, str]:
        info = self.get_touchpad_info()
        return self.set_touchpad_natural_scroll(not info["natural_scroll"])

    def set_touchpad_speed(self, speed_val: float) -> Tuple[bool, str]:
        clamped = max(-1.0, min(1.0, float(speed_val)))
        r1 = subprocess.run(["gsettings", "set", "org.gnome.desktop.peripherals.touchpad", "speed", str(round(clamped, 2))], env=self.env, capture_output=True, text=True)
        r2 = subprocess.run(["gsettings", "set", "org.gnome.desktop.peripherals.mouse", "speed", str(round(clamped, 2))], env=self.env, capture_output=True, text=True)
        pct = int(round(((clamped + 1.0) / 2.0) * 100))
        if r1.returncode == 0 or r2.returncode == 0:
            return True, f"Pointer speed set to {pct} percent."
        return False, f"Failed to set pointer speed: {r1.stderr.strip()}"

    def set_touchpad_speed_percent(self, pct: int) -> Tuple[bool, str]:
        clamped_pct = max(0, min(100, int(pct)))
        speed_val = (clamped_pct / 50.0) - 1.0
        return self.set_touchpad_speed(speed_val)

    def step_touchpad_speed(self, direction: str = "up", step_pct: int = 15) -> Tuple[bool, str]:
        info = self.get_touchpad_info()
        current_pct = info["speed_percent"]
        target = current_pct + step_pct if direction == "up" else current_pct - step_pct
        return self.set_touchpad_speed_percent(target)

    def lock_screen(self) -> Tuple[bool, str]:
        res = subprocess.run(["loginctl", "lock-session"], env=self.env, capture_output=True, text=True)
        return res.returncode == 0, "Desktop screen locked."

    # ----------------------------------------------------
    # Additional System Controls: Displays, Wallpaper, Blanking,
    # Mouse, Keyboard, Clipboard, Screenshot, Recording, Sharing
    # ----------------------------------------------------
    def get_monitors_info(self) -> Dict[str, Any]:
        """
        Inspect connected displays and multi-monitor setup via Mutter D-Bus.
        """
        try:
            res = subprocess.run([
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Mutter.DisplayConfig",
                "--object-path", "/org/gnome/Mutter/DisplayConfig",
                "--method", "org.gnome.Mutter.DisplayConfig.GetCurrentState"
            ], env=self.env, capture_output=True, text=True)
            monitors = []
            if res.returncode == 0 and res.stdout:
                matches = re.findall(r"\(\('([a-zA-Z0-9\-_]+)',\s*'([^']*)'", res.stdout)
                for conn, vendor in matches:
                    monitors.append({"connector": conn, "vendor": vendor, "primary": len(monitors) == 0})
            if not monitors:
                monitors = [{"connector": "eDP-1", "vendor": "Built-in Panel", "primary": True}]
            return {
                "count": len(monitors),
                "multi_monitor": len(monitors) > 1,
                "primary": monitors[0]["connector"] if monitors else "eDP-1",
                "monitors": monitors
            }
        except Exception as e:
            return {
                "count": 1,
                "multi_monitor": False,
                "primary": "eDP-1",
                "monitors": [{"connector": "eDP-1", "vendor": "Primary Panel", "primary": True}],
                "error": str(e)
            }

    def get_wallpaper_info(self) -> Dict[str, Any]:
        try:
            res = subprocess.run(["gsettings", "get", "org.gnome.desktop.background", "picture-uri"], env=self.env, capture_output=True, text=True)
            uri = res.stdout.strip().strip("'\"") if res.returncode == 0 else ""
            return {"uri": uri, "filename": os.path.basename(uri) if uri else "default"}
        except Exception:
            return {"uri": "", "filename": "default"}

    def set_wallpaper(self, uri_or_path: str) -> Tuple[bool, str]:
        if not uri_or_path:
            return False, "No wallpaper path provided."
        uri = uri_or_path
        if not uri.startswith("file://") and os.path.exists(uri_or_path):
            uri = f"file://{os.path.abspath(uri_or_path)}"
        r1 = subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri], env=self.env, capture_output=True, text=True)
        r2 = subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri], env=self.env, capture_output=True, text=True)
        if r1.returncode == 0 or r2.returncode == 0:
            return True, f"Desktop wallpaper updated to {os.path.basename(uri)}."
        return False, f"Failed to set wallpaper: {r1.stderr.strip()}"

    def get_screen_blanking_info(self) -> Dict[str, Any]:
        try:
            res = subprocess.run(["gsettings", "get", "org.gnome.desktop.session", "idle-delay"], env=self.env, capture_output=True, text=True)
            secs = 0
            if res.returncode == 0:
                m = re.search(r"\d+", res.stdout)
                if m:
                    secs = int(m.group(0))
            label = "Never" if secs == 0 else f"{int(secs / 60)} minutes"
            return {"idle_delay_seconds": secs, "label": label}
        except Exception:
            return {"idle_delay_seconds": 0, "label": "Never"}

    def set_screen_blanking(self, seconds: int) -> Tuple[bool, str]:
        secs = max(0, int(seconds))
        res = subprocess.run(["gsettings", "set", "org.gnome.desktop.session", "idle-delay", f"uint32 {secs}"], env=self.env, capture_output=True, text=True)
        label = "Never" if secs == 0 else f"{int(secs / 60)} minutes"
        if res.returncode == 0:
            return True, f"Screen blanking idle delay set to {label}."
        return False, f"Failed to set idle blanking: {res.stderr.strip()}"

    def get_mouse_info(self) -> Dict[str, Any]:
        try:
            r_spd = subprocess.run(["gsettings", "get", "org.gnome.desktop.peripherals.mouse", "speed"], env=self.env, capture_output=True, text=True)
            speed = float(r_spd.stdout.strip()) if r_spd.returncode == 0 else 0.0
            r_nat = subprocess.run(["gsettings", "get", "org.gnome.desktop.peripherals.mouse", "natural-scroll"], env=self.env, capture_output=True, text=True)
            natural_scroll = "true" in r_nat.stdout.lower() if r_nat.returncode == 0 else False
            r_acc = subprocess.run(["gsettings", "get", "org.gnome.desktop.peripherals.mouse", "accel-profile"], env=self.env, capture_output=True, text=True)
            accel_profile = r_acc.stdout.strip().strip("'\"") if r_acc.returncode == 0 else "default"
            pct = int(round(((speed + 1.0) / 2.0) * 100))
            return {
                "speed": round(speed, 2),
                "speed_percent": max(0, min(100, pct)),
                "natural_scroll": natural_scroll,
                "accel_profile": accel_profile
            }
        except Exception:
            return {"speed": 0.0, "speed_percent": 50, "natural_scroll": False, "accel_profile": "default"}

    def set_mouse_speed(self, speed_val: float) -> Tuple[bool, str]:
        clamped = max(-1.0, min(1.0, float(speed_val)))
        res = subprocess.run(["gsettings", "set", "org.gnome.desktop.peripherals.mouse", "speed", str(round(clamped, 2))], env=self.env, capture_output=True, text=True)
        pct = int(round(((clamped + 1.0) / 2.0) * 100))
        if res.returncode == 0:
            return True, f"Mouse speed set to {pct} percent."
        return False, f"Failed to set mouse speed: {res.stderr.strip()}"

    def set_mouse_natural_scroll(self, enable: bool) -> Tuple[bool, str]:
        val = "true" if enable else "false"
        res = subprocess.run(["gsettings", "set", "org.gnome.desktop.peripherals.mouse", "natural-scroll", val], env=self.env, capture_output=True, text=True)
        if res.returncode == 0:
            return True, f"Mouse natural scrolling {'enabled' if enable else 'disabled'}."
        return False, f"Failed to set mouse natural scroll: {res.stderr.strip()}"

    def get_keyboard_info(self) -> Dict[str, Any]:
        try:
            r_src = subprocess.run(["gsettings", "get", "org.gnome.desktop.input-sources", "sources"], env=self.env, capture_output=True, text=True)
            sources = r_src.stdout.strip() if r_src.returncode == 0 else "[('xkb', 'us')]"
            r_rep = subprocess.run(["gsettings", "get", "org.gnome.desktop.peripherals.keyboard", "repeat-interval"], env=self.env, capture_output=True, text=True)
            m_rep = re.search(r"\d+", r_rep.stdout)
            interval = int(m_rep.group(0)) if m_rep else 30
            r_del = subprocess.run(["gsettings", "get", "org.gnome.desktop.peripherals.keyboard", "delay"], env=self.env, capture_output=True, text=True)
            m_del = re.search(r"\d+", r_del.stdout)
            delay = int(m_del.group(0)) if m_del else 500
            return {"sources": sources, "repeat_interval_ms": interval, "repeat_delay_ms": delay}
        except Exception:
            return {"sources": "[('xkb', 'us')]", "repeat_interval_ms": 30, "repeat_delay_ms": 500}

    def set_keyboard_repeat_rate(self, interval: int = 30, delay: int = 500) -> Tuple[bool, str]:
        r1 = subprocess.run(["gsettings", "set", "org.gnome.desktop.peripherals.keyboard", "repeat-interval", f"uint32 {int(interval)}"], env=self.env, capture_output=True, text=True)
        r2 = subprocess.run(["gsettings", "set", "org.gnome.desktop.peripherals.keyboard", "delay", f"uint32 {int(delay)}"], env=self.env, capture_output=True, text=True)
        if r1.returncode == 0 or r2.returncode == 0:
            return True, f"Keyboard repeat rate set (interval: {interval}ms, delay: {delay}ms)."
        return False, "Failed to set keyboard repeat rate."

    def get_clipboard_text(self) -> Tuple[bool, str]:
        # 1. Wayland wl-paste
        try:
            res = subprocess.run(["wl-paste"], env=self.env, capture_output=True, text=True)
            if res.returncode == 0:
                txt = res.stdout.strip()
                preview = (txt[:80] + "...") if len(txt) > 80 else txt
                return True, f"Clipboard: \"{preview}\""
        except (FileNotFoundError, Exception):
            pass

        # 2. X11 xclip
        try:
            res = subprocess.run(["xclip", "-o", "-selection", "clipboard"], env=self.env, capture_output=True, text=True)
            if res.returncode == 0:
                txt = res.stdout.strip()
                preview = (txt[:80] + "...") if len(txt) > 80 else txt
                return True, f"Clipboard: \"{preview}\""
        except (FileNotFoundError, Exception):
            pass

        # 3. X11 xsel
        try:
            res = subprocess.run(["xsel", "-b", "-o"], env=self.env, capture_output=True, text=True)
            if res.returncode == 0:
                txt = res.stdout.strip()
                preview = (txt[:80] + "...") if len(txt) > 80 else txt
                return True, f"Clipboard: \"{preview}\""
        except (FileNotFoundError, Exception):
            pass

        return False, "Clipboard is empty or inaccessible."

    def set_clipboard_text(self, text: str) -> Tuple[bool, str]:
        # 1. Wayland wl-copy
        try:
            proc = subprocess.Popen(["wl-copy"], env=self.env, stdin=subprocess.PIPE, text=True)
            proc.communicate(input=text)
            if proc.returncode == 0:
                return True, f"Copied to clipboard: \"{text[:40]}\""
        except (FileNotFoundError, Exception):
            pass

        # 2. X11 xclip
        try:
            proc = subprocess.Popen(["xclip", "-selection", "clipboard"], env=self.env, stdin=subprocess.PIPE, text=True)
            proc.communicate(input=text)
            if proc.returncode == 0:
                return True, f"Copied to clipboard: \"{text[:40]}\""
        except (FileNotFoundError, Exception):
            pass

        # 3. X11 xsel
        try:
            proc = subprocess.Popen(["xsel", "-b", "-i"], env=self.env, stdin=subprocess.PIPE, text=True)
            proc.communicate(input=text)
            if proc.returncode == 0:
                return True, f"Copied to clipboard: \"{text[:40]}\""
        except (FileNotFoundError, Exception):
            pass

        return False, "Failed to set clipboard."

    def clear_clipboard(self) -> Tuple[bool, str]:
        # 1. Wayland wl-copy
        try:
            res = subprocess.run(["wl-copy", "-c"], env=self.env, capture_output=True)
            if res.returncode == 0:
                return True, "Clipboard cleared."
        except (FileNotFoundError, Exception):
            pass

        # 2. X11 xclip
        try:
            proc = subprocess.Popen(["xclip", "-selection", "clipboard"], env=self.env, stdin=subprocess.PIPE, text=True)
            proc.communicate(input="")
            if proc.returncode == 0:
                return True, "Clipboard cleared."
        except (FileNotFoundError, Exception):
            pass

        # 3. X11 xsel
        try:
            res = subprocess.run(["xsel", "-b", "-c"], env=self.env, capture_output=True)
            if res.returncode == 0:
                return True, "Clipboard cleared."
        except (FileNotFoundError, Exception):
            pass

        return False, "Failed to clear clipboard."

    def take_screenshot(self, filename: str = None) -> Tuple[bool, str, str]:
        """
        Take a screenshot using XDG Desktop Portal, grim, scrot, xwd, or ffmpeg fallback.
        Returns: (success, message, file_path)
        """
        try:
            shots_dir = os.path.expanduser("~/Pictures/Screenshots")
            os.makedirs(shots_dir, exist_ok=True)
            fname = filename or f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            dest = os.path.join(shots_dir, fname)
            
            # 1. Use XDG Desktop Portal Screenshot API (works on Wayland with portal daemon)
            try:
                res = subprocess.run([
                    "gdbus", "call", "--session",
                    "--dest", "org.freedesktop.portal.Desktop",
                    "--object-path", "/org/freedesktop/portal/desktop",
                    "--method", "org.freedesktop.portal.Screenshot.Screenshot",
                    "", '{"interactive": <false>}'
                ], env=self.env, capture_output=True, text=True)
                
                if res.returncode == 0:
                    time.sleep(0.5)
                    newest = None
                    newest_time = 0
                    for f in os.listdir(shots_dir):
                        if f.startswith("screenshot_") or f.startswith("Screenshot"):
                            full = os.path.join(shots_dir, f)
                            mtime = os.path.getmtime(full)
                            if mtime > newest_time:
                                newest_time = mtime
                                newest = full
                    
                    if newest:
                        return True, f"Screenshot saved to {newest}", newest
                    return True, f"Screenshot captured to {shots_dir}", shots_dir
            except (FileNotFoundError, Exception):
                pass

            # 2. Try grim on Wayland
            if os.environ.get("WAYLAND_DISPLAY") or self.env.get("WAYLAND_DISPLAY"):
                try:
                    res_grim = subprocess.run(["grim", dest], env=self.env, capture_output=True, text=True)
                    if res_grim.returncode == 0 and os.path.exists(dest):
                        return True, f"Screenshot saved to {dest} ({round(os.path.getsize(dest)/1024, 1)} KB).", dest
                except (FileNotFoundError, Exception):
                    pass

            # 3. Try scrot (common X11 screenshot tool)
            try:
                res_scrot = subprocess.run(["scrot", dest], env=self.env, capture_output=True, text=True)
                if res_scrot.returncode == 0 and os.path.exists(dest):
                    return True, f"Screenshot saved to {dest} ({round(os.path.getsize(dest)/1024, 1)} KB).", dest
            except (FileNotFoundError, Exception):
                pass

            # 4. Try xwd + ffmpeg
            try:
                display_env = self.env.get("DISPLAY") or os.environ.get("DISPLAY", ":0")
                xwd_file = dest.rsplit(".", 1)[0] + ".xwd"
                res_xwd = subprocess.run(["xwd", "-root", "-display", display_env, "-out", xwd_file], env=self.env, capture_output=True)
                if res_xwd.returncode == 0 and os.path.exists(xwd_file):
                    subprocess.run(["ffmpeg", "-i", xwd_file, dest, "-y"], env=self.env, capture_output=True)
                    try:
                        os.remove(xwd_file)
                    except OSError:
                        pass
                    if os.path.exists(dest):
                        return True, f"Screenshot saved to {dest} ({round(os.path.getsize(dest)/1024, 1)} KB).", dest
            except (FileNotFoundError, Exception):
                pass

            # 5. Fallback to ffmpeg x11grab with dynamic display and resolution
            display_str = self.env.get("DISPLAY") or os.environ.get("DISPLAY", ":0")
            display_info = self.get_display_info()
            video_size = display_info.get("current_resolution", "1920x1080")
            if not re.match(r"^\d+x\d+$", video_size) or video_size == "0x0":
                video_size = "1920x1080"

            cmd = ["ffmpeg", "-f", "x11grab", "-video_size", video_size, "-i", display_str, "-vframes", "1", "-update", "1", dest, "-y"]
            fallback_res = subprocess.run(cmd, env=self.env, capture_output=True, text=True)
            if fallback_res.returncode == 0 and os.path.exists(dest):
                return True, f"Screenshot saved to {dest} ({round(os.path.getsize(dest)/1024, 1)} KB).", dest
            return False, f"Screenshot failed on display {display_str}", ""
        except Exception as e:
            return False, f"Screenshot error: {str(e)}", ""

    def start_screen_recording(self, filename: str = None) -> Tuple[bool, str, str]:
        """
        Start screen recording using GNOME Shell's native screencast API (works on Wayland).
        Returns: (success, message, file_path)
        """
        is_active = self.screencast_active or (self.recording_proc is not None and self.recording_proc.poll() is None)
        if is_active:
            return False, f"Screen recording is already active (file: {os.path.basename(self.recording_file or '')}).", ""
        
        try:
            recs_dir = os.path.expanduser("~/Videos/Recordings")
            os.makedirs(recs_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 1. Native GNOME Shell Screencast via D-Bus (Wayland / Mutter native)
            try:
                import gi
                from gi.repository import Gio
                bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                proxy = Gio.DBusProxy.new_sync(
                    bus,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "org.gnome.Shell.Screencast",
                    "/org/gnome/Shell/Screencast",
                    "org.gnome.Shell.Screencast",
                    None
                )
                template = os.path.join(recs_dir, f"recording_{timestamp}_%d")
                res = proxy.Screencast("(sa{sv})", template, {})
                if res and res[0]:
                    self.screencast_active = True
                    self.screencast_proxy = proxy
                    self.recording_file = res[1]
                    self.recording_start_t = time.time()
                    self.recording_proc = None
                    return True, f"Screen recording started (Wayland native): {os.path.basename(self.recording_file)}.", self.recording_file
            except Exception as e_dbus:
                print(f"[SystemController] GNOME Screencast D-Bus exception: {e_dbus}")
            
            # 2. Fallback to ffmpeg x11grab (X11 only)
            fname = filename or f"recording_{timestamp}.mp4"
            dest = os.path.join(recs_dir, fname)
            cmd = [
                "ffmpeg", "-f", "x11grab", "-video_size", "1920x1080", "-i", ":0",
                "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                dest, "-y"
            ]
            self.recording_proc = subprocess.Popen(cmd, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.recording_file = dest
            self.recording_start_t = time.time()
            self.screencast_active = False
            self.screencast_proxy = None
            return True, f"Screen recording started (X11 fallback): {os.path.basename(dest)}.", dest
        except Exception as e:
            return False, f"Failed to start screen recording: {str(e)}", ""

    def stop_screen_recording(self) -> Tuple[bool, str, str]:
        """
        Stop active screen recording and return (success, message, file_path).
        """
        is_active = self.screencast_active or (self.recording_proc is not None and self.recording_proc.poll() is None)
        if not is_active:
            return False, "No screen recording is currently active.", ""
        try:
            saved_file = self.recording_file or ""
            dur = int(time.time() - self.recording_start_t) if self.recording_start_t else 0

            # 1. Stop GNOME Shell Screencast if active
            if self.screencast_active and self.screencast_proxy:
                try:
                    self.screencast_proxy.StopScreencast()
                except Exception as e_stop:
                    print(f"[SystemController] StopScreencast D-Bus error: {e_stop}")
                self.screencast_active = False
                self.screencast_proxy = None

            # 2. Stop ffmpeg process if active
            if self.recording_proc and self.recording_proc.poll() is None:
                self.recording_proc.send_signal(signal.SIGINT)
                try:
                    self.recording_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.recording_proc.kill()
                self.recording_proc = None

            fname = os.path.basename(saved_file) if saved_file else "recording"
            self.recording_file = None
            self.recording_start_t = 0
            return True, f"Screen recording stopped ({fname}, {dur}s duration).", saved_file
        except Exception as e:
            self.screencast_active = False
            self.screencast_proxy = None
            if self.recording_proc:
                self.recording_proc.kill()
                self.recording_proc = None
            return False, f"Error stopping recording: {str(e)}", ""

    def get_screen_recording_status(self) -> Dict[str, Any]:
        active = self.screencast_active or (self.recording_proc is not None and self.recording_proc.poll() is None)
        elapsed = int(time.time() - self.recording_start_t) if active else 0
        return {
            "active": active,
            "file": os.path.basename(self.recording_file) if self.recording_file else "",
            "elapsed_seconds": elapsed
        }

    def get_screen_sharing_info(self) -> Dict[str, Any]:
        try:
            r_rdp = subprocess.run(["gsettings", "get", "org.gnome.desktop.remote-desktop.rdp", "enable"], env=self.env, capture_output=True, text=True)
            rdp_enabled = "true" in r_rdp.stdout.lower() if r_rdp.returncode == 0 else False
            r_vnc = subprocess.run(["gsettings", "get", "org.gnome.desktop.remote-desktop.vnc", "enable"], env=self.env, capture_output=True, text=True)
            vnc_enabled = "true" in r_vnc.stdout.lower() if r_vnc.returncode == 0 else False
            return {"rdp_enabled": rdp_enabled, "vnc_enabled": vnc_enabled, "active": rdp_enabled or vnc_enabled}
        except Exception:
            return {"rdp_enabled": False, "vnc_enabled": False, "active": False}

    def set_screen_sharing(self, enable: bool) -> Tuple[bool, str]:
        val = "true" if enable else "false"
        res = subprocess.run(["gsettings", "set", "org.gnome.desktop.remote-desktop.rdp", "enable", val], env=self.env, capture_output=True, text=True)
        if res.returncode == 0:
            return True, f"Screen sharing (RDP) {'enabled' if enable else 'disabled'}."
        return False, f"Failed to configure screen sharing: {res.stderr.strip()}"

    def parse_command(self, text: str) -> Dict[str, Any]:
        """
        Deterministic regex/keyword parser mapping natural language text to system actions.
        Zero dependency on Laya, models, or external services.
        """
        if not text or not text.strip():
            return {"action": "general_query", "target": "general", "raw": ""}

        raw = text.strip()
        low = raw.lower()

        # 1. Display Resolution & Orientation
        if any(w in low for w in ["orientation", "rotate", "rotation", "portrait", "landscape"]):
            if any(q in low for q in ["what", "check", "current", "tell me", "status"]):
                return {"action": "orientation_control", "target": "orientation_status", "raw": raw}
            elif any(w in low for w in ["portrait", "vertical", "90"]):
                return {"action": "orientation_control", "target": "orientation_portrait", "raw": raw}
            elif any(w in low for w in ["landscape", "normal", "standard", "horizontal", "default"]):
                return {"action": "orientation_control", "target": "orientation_landscape", "raw": raw}
            elif any(w in low for w in ["inverted", "upside down", "upsidedown", "flipped", "180"]):
                return {"action": "orientation_control", "target": "orientation_inverted", "raw": raw}
            elif any(w in low for w in ["left", "counter-clockwise", "anticlockwise", "270"]):
                return {"action": "orientation_control", "target": "orientation_left", "raw": raw}
            elif any(w in low for w in ["rotate", "next", "cycle", "turn"]):
                return {"action": "orientation_control", "target": "orientation_rotate", "raw": raw}
            else:
                return {"action": "orientation_control", "target": "orientation_set", "raw": raw}

        if "resolution" in low:
            if any(q in low for q in ["what", "check", "current", "tell me", "status"]):
                return {"action": "resolution_control", "target": "resolution_status", "raw": raw}
            elif any(w in low for w in ["decrease", "lower", "down", "reduce", "smaller"]):
                return {"action": "resolution_control", "target": "resolution_down", "raw": raw}
            elif any(w in low for w in ["increase", "higher", "up", "raise", "larger"]):
                return {"action": "resolution_control", "target": "resolution_up", "raw": raw}
            else:
                return {"action": "resolution_control", "target": "resolution_set", "raw": raw}

        # 2. Volume & Microphone
        if "mute" in low and ("mic" in low or "microphone" in low or "input" in low):
            return {"action": "mic_control", "target": "mic_mute_toggle", "raw": raw}
        if "mute" in low:
            return {"action": "volume_control", "target": "mute_toggle", "raw": raw}

        if any(w in low for w in ["volume", "sound", "audio"]):
            if any(w in low for w in ["up", "increase", "raise", "louder", "boost", "+"]):
                return {"action": "volume_control", "target": "volume_up", "raw": raw}
            elif any(w in low for w in ["down", "decrease", "lower", "quieter", "dim", "-"]):
                return {"action": "volume_control", "target": "volume_down", "raw": raw}

        # 3. Brightness, Night Light & System Theme (Dark/Light Mode)
        if any(w in low for w in ["dark mode", "dark theme", "light mode", "light theme", "color scheme", "system theme", "desktop theme"]):
            if any(q in low for q in ["what", "check", "current", "tell me", "status"]):
                return {"action": "display_control", "target": "theme_status", "raw": raw}
            elif any(w in low for w in ["dark", "night"]):
                return {"action": "display_control", "target": "dark_mode", "raw": raw}
            elif any(w in low for w in ["light", "day", "bright"]):
                return {"action": "display_control", "target": "light_mode", "raw": raw}
            else:
                return {"action": "display_control", "target": "theme_toggle", "raw": raw}

        if any(w in low for w in ["toggle theme", "switch theme", "toggle dark", "toggle light"]):
            return {"action": "display_control", "target": "theme_toggle", "raw": raw}

        # Keyboard Backlight & RGB Controls
        if ("keyboard" in low or "kbd" in low) and any(w in low for w in ["backlight", "light", "lights", "rgb", "brightness", "glow", "color", "colour", "wave", "breathe", "breathing", "neon", "zoom", "mode", "effect", "on", "off", "dim", "bright", "red", "green", "blue", "cyan", "magenta", "purple", "white", "amber", "yellow"]):
            # Status query
            if any(q in low for q in ["what", "check", "current", "tell me", "status", "how is"]):
                return {"action": "keyboard_backlight_control", "target": "kbd_backlight_status", "raw": raw}
            # Toggle
            elif any(w in low for w in ["toggle", "switch"]):
                return {"action": "keyboard_backlight_control", "target": "kbd_backlight_toggle", "raw": raw}
            # Turn Off
            elif any(w in low for w in ["turn off", "shut off", "power off", "disable", "off", "dark"]):
                return {"action": "keyboard_backlight_control", "target": "kbd_backlight_off", "raw": raw}
            # Step Up
            elif any(w in low for w in ["increase", "raise", "higher", "brighter", "boost", "more", "+"]) or ("up" in low.split()):
                return {"action": "keyboard_backlight_control", "target": "kbd_backlight_up", "raw": raw}
            # Step Down
            elif any(w in low for w in ["decrease", "lower", "dim", "less", "-"]) or ("down" in low.split()):
                return {"action": "keyboard_backlight_control", "target": "kbd_backlight_down", "raw": raw}

            # Percentage match: e.g. "set keyboard brightness to 70%" or "keyboard light 50%"
            pct_match = re.search(r"(\d+)\s*%", low) or re.search(r"(?:to|at|set)\s+(\d{1,3})", low)
            if pct_match:
                pct_val = int(pct_match.group(1))
                return {"action": "keyboard_backlight_control", "target": f"kbd_backlight_set_{pct_val}", "raw": raw}

            # Effect / Mode match
            for mname in ["wave", "rainbow", "breathe", "breathing", "neon", "zoom", "meteor", "twinkle", "static"]:
                if mname in low:
                    return {"action": "keyboard_backlight_control", "target": "kbd_backlight_mode", "mode": mname, "raw": raw}

            # Color match
            for cname in ["red", "green", "blue", "cyan", "magenta", "purple", "yellow", "orange", "amber", "pink", "white", "ice blue", "warm white"]:
                if cname in low:
                    return {"action": "keyboard_backlight_control", "target": "kbd_backlight_color", "color": cname, "raw": raw}

            # Turn On
            if any(w in low for w in ["turn on", "enable", "on", "start"]):
                return {"action": "keyboard_backlight_control", "target": "kbd_backlight_on", "raw": raw}

            return {"action": "keyboard_backlight_control", "target": "kbd_backlight_status", "raw": raw}

        if "night light" in low:
            return {"action": "display_control", "target": "night_light_toggle", "raw": raw}
        if "brightness" in low or "backlight" in low:
            if any(w in low for w in ["up", "increase", "raise", "higher", "more", "+"]):
                return {"action": "display_control", "target": "brightness_up", "raw": raw}
            elif any(w in low for w in ["down", "decrease", "lower", "dim", "less", "-"]):
                return {"action": "display_control", "target": "brightness_down", "raw": raw}

        # 4. Power & Session
        if "lock" in low:
            return {"action": "session_control", "target": "lock_screen", "raw": raw}
        if "performance" in low:
            return {"action": "session_control", "target": "power_profile_performance", "raw": raw}
        if any(w in low.split() for w in ["saver", "save", "eco", "powersave", "power-saver"]):
            return {"action": "session_control", "target": "power_profile_saver", "raw": raw}
        if "balanced" in low:
            return {"action": "session_control", "target": "power_profile_balanced", "raw": raw}

        # 5. Media Playback
        if any(w in low for w in ["play", "pause", "resume", "stop music"]):
            return {"action": "media_control", "target": "play_pause", "raw": raw}
        if "next" in low and ("song" in low or "track" in low or "music" in low):
            return {"action": "media_control", "target": "next_track", "raw": raw}
        if ("prev" in low or "previous" in low) and ("song" in low or "track" in low or "music" in low):
            return {"action": "media_control", "target": "previous_track", "raw": raw}

        # 6. Connectivity
        if "wifi" in low or "wi-fi" in low:
            return {"action": "connectivity_control", "target": "wifi_toggle", "raw": raw}
        if "bluetooth" in low:
            return {"action": "connectivity_control", "target": "bluetooth_toggle", "raw": raw}
        if "dnd" in low or "do not disturb" in low:
            return {"action": "connectivity_control", "target": "dnd_toggle", "raw": raw}

        # 7. Touchpad & Peripherals
        if "touchpad" in low or "trackpad" in low:
            if any(q in low for q in ["what", "check", "current", "tell me", "status", "how is"]):
                return {"action": "touchpad_control", "target": "touchpad_status", "raw": raw}
            elif any(w in low for w in ["turn off", "disable", "shut off", "deactivate", "off"]):
                return {"action": "touchpad_control", "target": "touchpad_off", "raw": raw}
            elif any(w in low for w in ["turn on", "enable", "activate", "on"]):
                return {"action": "touchpad_control", "target": "touchpad_on", "raw": raw}
            elif any(w in low for w in ["toggle", "switch"]):
                return {"action": "touchpad_control", "target": "touchpad_toggle", "raw": raw}
            elif "tap" in low:
                return {"action": "touchpad_control", "target": "touchpad_tap_to_click_toggle", "raw": raw}
            elif "scroll" in low:
                return {"action": "touchpad_control", "target": "touchpad_natural_scroll_toggle", "raw": raw}
            elif any(w in low for w in ["speed", "sensitivity", "pointer", "cursor"]):
                pct_m = re.search(r"(\d+)\s*%", low) or re.search(r"(?:to|at|set)\s+(\d{1,3})", low)
                if pct_m:
                    return {"action": "touchpad_control", "target": f"touchpad_speed_set_{pct_m.group(1)}", "raw": raw}
                if any(w in low for w in ["up", "increase", "faster", "higher"]):
                    return {"action": "touchpad_control", "target": "touchpad_speed_up", "raw": raw}
                if any(w in low for w in ["down", "decrease", "slower", "lower"]):
                    return {"action": "touchpad_control", "target": "touchpad_speed_down", "raw": raw}
                return {"action": "touchpad_control", "target": "touchpad_speed", "raw": raw}
            return {"action": "touchpad_control", "target": "touchpad_toggle", "raw": raw}

        if "tap to click" in low or "tap-to-click" in low:
            return {"action": "touchpad_control", "target": "touchpad_tap_to_click_toggle", "raw": raw}

        if "natural scroll" in low or "natural-scroll" in low or "reverse scroll" in low:
            return {"action": "touchpad_control", "target": "touchpad_natural_scroll_toggle", "raw": raw}

        # 8. Displays & Multiple Monitors
        if any(w in low for w in ["monitors", "multiple monitors", "dual screen", "display setup", "external screen", "connected displays"]):
            return {"action": "monitors_control", "target": "monitors_status", "raw": raw}

        # 9. Wallpaper & Desktop Background
        if "wallpaper" in low or "desktop background" in low or "background image" in low:
            if any(q in low for q in ["what", "check", "current", "tell me", "status"]):
                return {"action": "wallpaper_control", "target": "wallpaper_status", "raw": raw}
            return {"action": "wallpaper_control", "target": "wallpaper_status", "raw": raw}

        # 10. Screensaver & Screen Blanking
        if any(w in low for w in ["screensaver", "blanking", "screen timeout", "idle delay", "sleep timer"]):
            if any(q in low for q in ["what", "check", "current", "tell me", "status"]):
                return {"action": "blanking_control", "target": "blanking_status", "raw": raw}
            elif "never" in low or "disable" in low or "off" in low:
                return {"action": "blanking_control", "target": "blanking_never", "raw": raw}
            elif "5" in low:
                return {"action": "blanking_control", "target": "blanking_5min", "raw": raw}
            elif "10" in low:
                return {"action": "blanking_control", "target": "blanking_10min", "raw": raw}
            elif "15" in low:
                return {"action": "blanking_control", "target": "blanking_15min", "raw": raw}
            return {"action": "blanking_control", "target": "blanking_status", "raw": raw}

        # 11. Mouse & Pointer
        if "mouse" in low and any(w in low for w in ["speed", "sensitivity", "cursor", "pointer"]):
            pct_m = re.search(r"(\d+)\s*%", low) or re.search(r"(?:to|at|set)\s+(\d{1,3})", low)
            if pct_m:
                return {"action": "mouse_control", "target": f"mouse_speed_set_{pct_m.group(1)}", "raw": raw}
            return {"action": "mouse_control", "target": "mouse_status", "raw": raw}
        if "mouse" in low and ("scroll" in low or "natural" in low):
            return {"action": "mouse_control", "target": "mouse_natural_scroll_toggle", "raw": raw}

        # 12. Keyboard Settings
        if "keyboard" in low and any(w in low for w in ["layout", "source", "repeat", "delay", "language"]):
            return {"action": "keyboard_control", "target": "keyboard_status", "raw": raw}

        # 13. Clipboard
        if "clipboard" in low:
            if any(w in low for w in ["clear", "empty", "erase", "wipe"]):
                return {"action": "clipboard_control", "target": "clipboard_clear", "raw": raw}
            elif any(w in low for w in ["copy", "write", "set"]):
                m = re.search(r"(?:copy|write|set)\s+(.*)", raw, re.IGNORECASE)
                txt = m.group(1).strip() if m else raw
                return {"action": "clipboard_control", "target": "clipboard_copy", "text": txt, "raw": raw}
            return {"action": "clipboard_control", "target": "clipboard_read", "raw": raw}

        # 14. Screenshots
        if any(w in low for w in ["screenshot", "screen capture", "capture screen", "snapshot", "print screen", "screengrab"]):
            return {"action": "screenshot_control", "target": "take_screenshot", "raw": raw}

        # 15. Screen Recording
        if any(w in low for w in ["screen record", "record screen", "screen recording", "record video", "record desktop", "start recording", "stop recording", "recording status"]) or (("record" in low.split() or "recording" in low.split()) and not any(k in low for k in ["keyboard", "kbd", "clipboard"])):
            if any(w in low for w in ["stop", "end", "finish", "halt", "quit", "terminate"]):
                return {"action": "screen_recording_control", "target": "screen_recording_stop", "raw": raw}
            elif any(w in low for w in ["status", "check", "how is", "is recording"]):
                return {"action": "screen_recording_control", "target": "screen_recording_status", "raw": raw}
            return {"action": "screen_recording_control", "target": "screen_recording_start", "raw": raw}

        # 16. Screen Sharing & Remote Desktop
        if any(w in low for w in ["screen share", "screen sharing", "remote desktop", "rdp", "vnc"]):
            if any(w in low for w in ["what", "check", "current", "status"]):
                return {"action": "screen_sharing_control", "target": "screen_sharing_status", "raw": raw}
            elif any(w in low for w in ["start", "enable", "turn on", "on"]):
                return {"action": "screen_sharing_control", "target": "screen_sharing_on", "raw": raw}
            elif any(w in low for w in ["stop", "disable", "turn off", "off"]):
                return {"action": "screen_sharing_control", "target": "screen_sharing_off", "raw": raw}
            return {"action": "screen_sharing_control", "target": "screen_sharing_toggle", "raw": raw}

        # 7. System Info & Telemetry
        if any(w in low for w in ["time", "clock", "date"]):
            return {"action": "system_info", "target": "current_time", "raw": raw}
        if "battery" in low or "charge" in low:
            return {"action": "system_info", "target": "battery_status", "raw": raw}
        if any(w in low for w in ["gpu", "nvidia", "rtx", "graphics"]):
            return {"action": "system_info", "target": "gpu_status", "raw": raw}
        if any(w in low for w in ["ram", "memory", "disk", "storage", "cpu", "temp"]):
            return {"action": "system_info", "target": "memory_disk_usage", "raw": raw}

        # 8. Application Launching
        if "chrome" in low or "browser" in low:
            return {"action": "app_launcher", "target": "chrome", "raw": raw}
        if "terminal" in low or "bash" in low or "console" in low:
            return {"action": "app_launcher", "target": "terminal", "raw": raw}
        if "obsidian" in low:
            return {"action": "app_launcher", "target": "obsidian", "raw": raw}
        if "files" in low or "nautilus" in low:
            return {"action": "app_launcher", "target": "files", "raw": raw}

        return {"action": "general_query", "target": "general", "raw": raw}

if __name__ == "__main__":
    ctrl = SystemController()
    success, msg = ctrl.execute_decision({"action": "system_info", "target": "current_time"})
    print("Test System Info:", success, msg)
    success, msg = ctrl.execute_decision({"action": "volume_control", "target": "volume_up"})
    print("Test Volume Up:", success, msg)
