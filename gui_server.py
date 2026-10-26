#!/usr/bin/env python3
import os
import sys
import json
import time
import shutil
import tempfile
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from collections import deque
import numpy as np

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Ensure PipeWire audio socket environment
if "XDG_RUNTIME_DIR" not in os.environ or not os.environ["XDG_RUNTIME_DIR"]:
    os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
if "LD_LIBRARY_PATH" not in os.environ or "/usr/local/lib/ollama/cuda_v12" not in os.environ.get("LD_LIBRARY_PATH", ""):
    os.environ["LD_LIBRARY_PATH"] = f"/usr/local/lib/ollama/cuda_v12:{os.environ.get('LD_LIBRARY_PATH', '')}"

from agent import LocalSystemAgent

# Global state for server
SERVER_PORT = 8080
agent_instance = None
history_log = deque(maxlen=60)
state_lock = threading.Lock()

def get_agent():
    global agent_instance
    if agent_instance is None:
        agent_instance = LocalSystemAgent(init_audio_listener=False)
    return agent_instance

def record_event(event_type: str, message: str, meta: dict = None):
    with state_lock:
        item = {
            "id": int(time.time() * 1000),
            "timestamp": time.strftime("%H:%M:%S"),
            "type": event_type,
            "message": message,
            "meta": meta or {}
        }
        history_log.appendleft(item)

SHADCN_HTML_PAGE = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>System Controller &bull; Linux Dashboard</title>
  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Lucide Icons -->
  <script src="https://unpkg.com/lucide@latest"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            border: 'hsl(var(--border))',
            input: 'hsl(var(--input))',
            ring: 'hsl(var(--ring))',
            background: 'hsl(var(--background))',
            foreground: 'hsl(var(--foreground))',
            primary: {
              DEFAULT: 'hsl(var(--primary))',
              foreground: 'hsl(var(--primary-foreground))',
            },
            secondary: {
              DEFAULT: 'hsl(var(--secondary))',
              foreground: 'hsl(var(--secondary-foreground))',
            },
            destructive: {
              DEFAULT: 'hsl(var(--destructive))',
              foreground: 'hsl(var(--destructive-foreground))',
            },
            muted: {
              DEFAULT: 'hsl(var(--muted))',
              foreground: 'hsl(var(--muted-foreground))',
            },
            accent: {
              DEFAULT: 'hsl(var(--accent))',
              foreground: 'hsl(var(--accent-foreground))',
            },
            popover: {
              DEFAULT: 'hsl(var(--popover))',
              foreground: 'hsl(var(--popover-foreground))',
            },
            card: {
              DEFAULT: 'hsl(var(--card))',
              foreground: 'hsl(var(--card-foreground))',
            },
          },
          borderRadius: {
            none: '0px',
            sm: '0px',
            DEFAULT: '0px',
            md: '0px',
            lg: '0px',
            xl: '0px',
            '2xl': '0px',
            '3xl': '0px',
            full: '0px',
          },
          fontFamily: {
            sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
            mono: ['JetBrains Mono', 'Menlo', 'monospace']
          }
        }
      }
    }
  </script>
  <style>
    :root {
      --background: 240 10% 3.9%;
      --foreground: 0 0% 98%;
      --card: 240 10% 4.9%;
      --card-foreground: 0 0% 98%;
      --popover: 240 10% 4.9%;
      --popover-foreground: 0 0% 98%;
      --primary: 0 0% 98%;
      --primary-foreground: 240 5.9% 10%;
      --secondary: 240 3.7% 15.9%;
      --secondary-foreground: 0 0% 98%;
      --muted: 240 3.7% 15.9%;
      --muted-foreground: 240 5% 64.9%;
      --accent: 240 3.7% 15.9%;
      --accent-foreground: 0 0% 98%;
      --destructive: 0 62.8% 30.6%;
      --destructive-foreground: 0 0% 98%;
      --border: 240 3.7% 15.9%;
      --input: 240 3.7% 15.9%;
      --ring: 240 4.9% 83.9%;
      --radius: 0rem;
    }

    *, *::before, *::after {
      border-radius: 0px !important;
    }

    input[type=range] {
      -webkit-appearance: none;
      background: hsl(var(--secondary));
      border-radius: 0px;
      height: 6px;
      outline: none;
    }
    input[type=range]::-webkit-slider-thumb {
      -webkit-appearance: none;
      appearance: none;
      width: 16px;
      height: 16px;
      border-radius: 0px;
      background: hsl(var(--primary));
      border: 2px solid hsl(var(--background));
      box-shadow: 0 0 0 1px hsl(var(--border));
      cursor: pointer;
      transition: transform 0.1s ease;
    }
    input[type=range]::-webkit-slider-thumb:hover {
      transform: scale(1.15);
    }

    @keyframes toast-in {
      from { transform: translateY(100%); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
    .animate-toast {
      animation: toast-in 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: hsl(var(--border)); border-radius: 0px; }
    ::-webkit-scrollbar-thumb:hover { background: hsl(var(--muted-foreground)); }
  </style>
</head>
<body class="bg-background text-foreground min-h-screen flex flex-col antialiased font-sans selection:bg-primary selection:text-primary-foreground pb-24">

  <!-- Header -->
  <header class="sticky top-0 z-50 w-full border-b border-border/60 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="flex h-8 w-8 items-center justify-center bg-primary text-primary-foreground">
          <i data-lucide="cpu" class="h-4 w-4"></i>
        </div>
        <div class="flex items-center gap-2">
          <span class="font-semibold text-sm tracking-tight">System Controller</span>
          <span class="inline-flex items-center border border-border bg-secondary px-2 py-0.5 text-[11px] font-medium text-secondary-foreground">shadcn/ui + gauge-ui</span>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <div class="hidden sm:inline-flex items-center gap-1.5 border border-border bg-secondary/50 px-2.5 py-1 text-xs font-mono text-muted-foreground">
          <span class="h-1.5 w-1.5 bg-emerald-500"></span>
          <span>System Online</span>
        </div>
        <div class="hidden md:inline-flex items-center gap-1.5 border border-border bg-secondary/50 px-2.5 py-1 text-xs font-mono text-muted-foreground" id="nav-gpu-badge">
          <i data-lucide="cpu" class="h-3 w-3"></i>
          <span>RTX 4070 (0%)</span>
        </div>

        <!-- Toggle View Mode: Icon only near GPU name -->
        <div class="inline-flex h-8 items-center border border-border bg-muted p-0.5 text-xs text-muted-foreground font-mono" title="Toggle View Mode (Gauges / Text)">
          <button onclick="setViewMode('graphical')" id="btn-mode-graphical" class="h-7 w-7 flex items-center justify-center bg-background text-foreground shadow-sm transition-colors" title="Gauges View">
            <i data-lucide="gauge" class="w-3.5 h-3.5"></i>
          </button>
          <button onclick="setViewMode('text')" id="btn-mode-text" class="h-7 w-7 flex items-center justify-center hover:text-foreground transition-colors" title="Text View">
            <i data-lucide="align-left" class="w-3.5 h-3.5"></i>
          </button>
        </div>

        <!-- Quick Dark / Light Mode Switcher -->
        <button onclick="triggerAction('theme_toggle')" id="nav-theme-toggle" class="h-8 w-8 flex items-center justify-center border border-border bg-muted hover:bg-accent text-foreground transition-colors" title="Toggle System Theme (Dark/Light)">
          <i data-lucide="sun-moon" class="w-3.5 h-3.5"></i>
        </button>

        <div class="inline-flex items-center gap-1.5 border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-400">
          <span class="h-1.5 w-1.5 bg-emerald-500 animate-pulse"></span>
          <span id="nav-uptime-status">Online</span>
        </div>
      </div>
    </div>
  </header>

  <!-- Main Container -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex-1 w-full flex flex-col gap-6">

    <!-- TAB 1: CONTROLS VIEW -->
    <div id="view-controls" class="space-y-6">

      <!-- Section: Interactive Hardware Controls with gauge-ui.dev Dials -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

        <!-- 1. Master Audio & Microphone Station -->
        <div class="border border-border bg-card text-card-foreground shadow-sm p-6 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between mb-2">
              <h4 class="text-sm font-semibold tracking-tight flex items-center gap-2">
                <i data-lucide="volume-2" class="w-4 h-4 text-muted-foreground"></i> Audio &amp; Mic
              </h4>
              <span id="volume-pct-label" class="inline-flex items-center border border-border bg-secondary px-2 py-0.5 text-xs font-mono font-medium">100%</span>
            </div>

            <!-- Dual Animated Gauges for Speaker & Mic -->
            <div id="audio-gauges-row" class="grid grid-cols-2 gap-2 my-2">
              <div class="flex flex-col items-center border border-border bg-background p-2">
                <div id="gauge-ctrl-vol" class="w-24 h-20"></div>
                <span class="text-[10px] font-mono text-muted-foreground">OUTPUT</span>
              </div>
              <div class="flex flex-col items-center border border-border bg-background p-2">
                <div id="gauge-ctrl-mic" class="w-24 h-20"></div>
                <span class="text-[10px] font-mono text-muted-foreground">MIC GAIN</span>
              </div>
            </div>

            <div class="space-y-1 mt-2">
              <div class="flex justify-between text-[11px] text-muted-foreground font-mono">
                <span>Volume</span>
                <span id="vol-sub-label">100%</span>
              </div>
              <input type="range" id="vol-slider" min="0" max="150" value="100" onchange="setVolumeLevel(this.value)" oninput="updateVolLabel(this.value)" class="w-full">
            </div>

            <div class="space-y-1 mt-2">
              <div class="flex justify-between text-[11px] text-muted-foreground font-mono">
                <span>Mic Input</span>
                <span id="mic-pct-label">100%</span>
              </div>
              <input type="range" id="mic-slider" min="0" max="150" value="100" onchange="setMicVolumeLevel(this.value)" oninput="updateMicLabel(this.value)" class="w-full">
            </div>
          </div>

          <div class="grid grid-cols-4 gap-1.5 mt-4">
            <button onclick="triggerAction('volume_down')" class="inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors">
              <i data-lucide="volume-1" class="w-4 h-4 mb-0.5"></i>
              <span class="text-[10px] font-mono">-10%</span>
            </button>
            <button onclick="triggerAction('volume_up')" class="inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors">
              <i data-lucide="volume-2" class="w-4 h-4 mb-0.5"></i>
              <span class="text-[10px] font-mono">+10%</span>
            </button>
            <button id="mute-btn" onclick="triggerAction('mute_toggle')" class="inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors">
              <i data-lucide="volume-x" class="w-4 h-4 mb-0.5"></i>
              <span class="text-[10px] font-mono">Mute</span>
            </button>
            <button id="mic-mute-btn" onclick="triggerAction('mic_mute_toggle')" class="inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors">
              <i data-lucide="mic-off" class="w-4 h-4 mb-0.5"></i>
              <span class="text-[10px] font-mono">Mic</span>
            </button>
          </div>
        </div>

        <!-- 2. Display Brightness & Eye Care -->
        <div class="border border-border bg-card text-card-foreground shadow-sm p-6 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between mb-2">
              <h4 class="text-sm font-semibold tracking-tight flex items-center gap-2">
                <i data-lucide="sun" class="w-4 h-4 text-muted-foreground"></i> Display &amp; Backlight
              </h4>
              <span id="brightness-pct-label" class="inline-flex items-center border border-border bg-secondary px-2 py-0.5 text-xs font-mono font-medium">40%</span>
            </div>

            <!-- Interactive Luminance Gauge -->
            <div id="bright-gauge-row" class="flex flex-col items-center border border-border bg-background p-2 my-2">
              <div id="gauge-ctrl-bright" class="w-32 h-24"></div>
              <span class="text-[10px] font-mono text-muted-foreground">PANEL LUMINANCE</span>
            </div>
            <p id="bright-desc-text" class="hidden text-xs text-muted-foreground my-2">Adjust panel backlight brightness and night light mode.</p>

            <div class="space-y-1.5 mt-2">
              <div class="flex justify-between text-xs text-muted-foreground font-mono">
                <span>Backlight Slider</span>
                <span id="brightness-sub-label">40%</span>
              </div>
              <input type="range" id="brightness-slider" min="1" max="100" value="40" onchange="setBrightnessLevel(this.value)" oninput="updateBrightnessLabel(this.value)" class="w-full">
            </div>
          </div>

          <div class="grid grid-cols-4 gap-1.5 mt-4">
            <button onclick="triggerAction('brightness_down')" title="Decrease Brightness" class="inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors">
              <i data-lucide="sun-dim" class="w-4 h-4 mb-0.5"></i>
              <span class="text-[10px] font-mono">-10%</span>
            </button>
            <button onclick="triggerAction('brightness_up')" title="Increase Brightness" class="inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors">
              <i data-lucide="sun-medium" class="w-4 h-4 mb-0.5"></i>
              <span class="text-[10px] font-mono">+10%</span>
            </button>
            <button id="night-light-btn" onclick="triggerAction('night_light_toggle')" title="Toggle Night Light" class="inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors">
              <i data-lucide="moon" class="w-4 h-4 mb-0.5"></i>
              <span class="text-[10px] font-mono">Night</span>
            </button>
            <button id="theme-mode-btn" onclick="triggerAction('theme_toggle')" title="Toggle System Theme (Dark/Light)" class="inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors">
              <i data-lucide="sun-moon" class="w-4 h-4 mb-0.5"></i>
              <span id="theme-btn-label" class="text-[10px] font-mono">Dark</span>
            </button>
          </div>
        </div>

        <!-- 3. Display Resolution & Orientation Station -->
        <div class="border border-border bg-card text-card-foreground shadow-sm p-6 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-sm font-semibold tracking-tight flex items-center gap-2">
                <i data-lucide="monitor" class="w-4 h-4 text-muted-foreground"></i> Resolution &amp; Orientation
              </h4>
              <span id="resolution-current-badge" class="inline-flex items-center border border-border bg-secondary px-2 py-0.5 text-xs font-mono font-medium truncate max-w-[150px]">2560x1600 @ 240Hz</span>
            </div>

            <!-- Resolution Selector & Quick Steps -->
            <div class="space-y-1.5 my-2">
              <div class="flex justify-between items-center text-xs text-muted-foreground font-mono">
                <span>Display Resolution</span>
                <span class="text-[11px] text-muted-foreground">Mutter D-Bus</span>
              </div>
              <div class="mt-1">
                <select id="resolution-select" onchange="applyResolution(this.value)" class="w-full bg-background border border-border px-2.5 py-1.5 text-xs font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-primary">
                  <option value="2560x1600">2560x1600 (QHD+ Native)</option>
                  <option value="2560x1440">2560x1440 (1440p 2K)</option>
                  <option value="1920x1200">1920x1200 (FHD+)</option>
                  <option value="1920x1080">1920x1080 (1080p FHD)</option>
                  <option value="1600x900">1600x900 (HD+)</option>
                  <option value="1280x720">1280x720 (720p HD)</option>
                </select>
              </div>
              <div class="grid grid-cols-2 gap-1.5 pt-1">
                <button onclick="triggerAction('resolution_down')" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-1 text-xs font-mono transition-colors">
                  <i data-lucide="zoom-out" class="w-3 h-3 mr-1"></i> Lower Res
                </button>
                <button onclick="triggerAction('resolution_up')" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-1 text-xs font-mono transition-colors">
                  <i data-lucide="zoom-in" class="w-3 h-3 mr-1"></i> Higher Res
                </button>
              </div>
            </div>

            <!-- Display Orientation Section -->
            <div class="space-y-1.5 mt-3 pt-3 border-t border-border">
              <div class="flex justify-between items-center text-xs text-muted-foreground font-mono">
                <span class="flex items-center gap-1.5"><i data-lucide="rotate-cw" class="w-3.5 h-3.5"></i> Orientation</span>
                <span id="orientation-current-badge" class="text-foreground font-bold uppercase">Standard (0°)</span>
              </div>
              <div class="grid grid-cols-4 gap-1.5 mt-2 font-mono text-xs">
                <button onclick="applyOrientation('normal')" id="orient-btn-normal" class="border border-border bg-background hover:bg-accent py-1.5 px-1 text-center transition-colors" title="Standard Landscape (0°)">0°</button>
                <button onclick="applyOrientation('right')" id="orient-btn-right" class="border border-border bg-background hover:bg-accent py-1.5 px-1 text-center transition-colors" title="Portrait (90° clockwise)">90°</button>
                <button onclick="applyOrientation('inverted')" id="orient-btn-inverted" class="border border-border bg-background hover:bg-accent py-1.5 px-1 text-center transition-colors" title="Inverted (180°)">180°</button>
                <button onclick="applyOrientation('left')" id="orient-btn-left" class="border border-border bg-background hover:bg-accent py-1.5 px-1 text-center transition-colors" title="Portrait Flipped (270°)">270°</button>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-2 mt-4">
            <button onclick="triggerAction('orientation_rotate')" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs font-medium gap-1.5 transition-colors">
              <i data-lucide="rotate-cw" class="w-3.5 h-3.5"></i>
              <span>Cycle Rotate</span>
            </button>
            <button onclick="applyOrientation('normal')" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs font-medium gap-1.5 transition-colors">
              <i data-lucide="monitor" class="w-3.5 h-3.5"></i>
              <span>Reset 0°</span>
            </button>
          </div>
        </div>

        <!-- 4. Power Profiles & Session Controls -->
        <div class="border border-border bg-card text-card-foreground shadow-sm p-6 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-sm font-semibold tracking-tight flex items-center gap-2">
                <i data-lucide="zap" class="w-4 h-4 text-muted-foreground"></i> Power &amp; Session
              </h4>
              <span id="power-profile-pill" class="inline-flex items-center border border-border bg-secondary px-2 py-0.5 text-xs font-mono font-medium uppercase">Balanced</span>
            </div>

            <div class="grid grid-cols-3 gap-1.5 my-2">
              <button onclick="setPowerProfile('performance')" id="p-perf" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-1 text-xs font-mono transition-colors">Perf</button>
              <button onclick="setPowerProfile('balanced')" id="p-bal" class="inline-flex items-center justify-center border border-primary bg-primary text-primary-foreground py-1 text-xs font-mono font-medium transition-colors">Balanced</button>
              <button onclick="setPowerProfile('power-saver')" id="p-save" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-1 text-xs font-mono transition-colors">Saver</button>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-2 mt-5">
            <button onclick="triggerAction('lock_screen')" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs font-medium gap-1.5 transition-colors">
              <i data-lucide="lock" class="w-3.5 h-3.5"></i>
              <span>Lock Screen</span>
            </button>
            <button id="dnd-btn" onclick="triggerAction('dnd_toggle')" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs font-medium gap-1.5 transition-colors">
              <i data-lucide="bell-off" class="w-3.5 h-3.5"></i>
              <span id="dnd-label">DND: ON</span>
            </button>
          </div>
        </div>

        <!-- 4. Media & Quick App Dock -->
        <div class="border border-border bg-card text-card-foreground shadow-sm p-6 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-sm font-semibold tracking-tight flex items-center gap-2">
                <i data-lucide="disc" class="w-4 h-4 text-muted-foreground"></i> Media &amp; Apps
              </h4>
              <span id="media-status-pill" class="inline-flex items-center border border-border bg-secondary px-2 py-0.5 text-xs font-mono font-medium">Idle</span>
            </div>

            <div class="grid grid-cols-3 gap-1.5 mb-4">
              <button onclick="triggerAction('previous_track')" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-1.5 text-xs transition-colors">
                <i data-lucide="skip-back" class="w-4 h-4"></i>
              </button>
              <button onclick="triggerAction('play_pause')" class="inline-flex items-center justify-center border border-primary bg-primary text-primary-foreground hover:bg-primary/90 py-1.5 text-xs transition-colors">
                <i data-lucide="play" class="w-4 h-4"></i>
              </button>
              <button onclick="triggerAction('next_track')" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-1.5 text-xs transition-colors">
                <i data-lucide="skip-forward" class="w-4 h-4"></i>
              </button>
            </div>
          </div>

          <div>
            <div class="text-[11px] text-muted-foreground font-mono mb-1.5">App Launch Dock</div>
            <div class="grid grid-cols-4 gap-1.5">
              <button onclick="triggerAction('launch_chrome')" title="Chrome" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground p-2 transition-colors">
                <i data-lucide="globe" class="w-4 h-4 text-blue-400"></i>
              </button>
              <button onclick="triggerAction('launch_terminal')" title="Terminal" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground p-2 transition-colors">
                <i data-lucide="terminal" class="w-4 h-4 text-emerald-400"></i>
              </button>
              <button onclick="triggerAction('launch_obsidian')" title="Obsidian" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground p-2 transition-colors">
                <i data-lucide="file-text" class="w-4 h-4 text-purple-400"></i>
              </button>
              <button onclick="triggerAction('launch_files')" title="Files" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground p-2 transition-colors">
                <i data-lucide="folder" class="w-4 h-4 text-amber-400"></i>
              </button>
            </div>
          </div>
        </div>

        <!-- 6. Keyboard Backlight & RGB Illumination -->
        <div id="card-kbd-backlight" class="relative border border-border bg-card text-card-foreground shadow-sm p-6 flex flex-col justify-between overflow-hidden">
          
          <!-- Unavailable / Setup Required Overlay (Visible when !supported) -->
          <div id="kbd-setup-overlay" onclick="openKbdSetupModal()" class="hidden absolute inset-0 bg-background/85 backdrop-blur-[2px] z-20 flex flex-col items-center justify-center p-6 text-center cursor-pointer transition-all hover:bg-background/90 group border border-amber-500/30">
            <div class="h-10 w-10 border border-amber-500/40 bg-amber-500/10 flex items-center justify-center text-amber-400 mb-2 group-hover:scale-105 transition-transform">
              <i data-lucide="shield-alert" class="w-5 h-5"></i>
            </div>
            <div class="text-xs font-semibold text-foreground tracking-tight">Driver Setup Required</div>
            <p class="text-[11px] text-muted-foreground mt-1 max-w-[220px]">
              Hardware ACPI lighting requires Secure Boot MOK authorization. Click to view instructions.
            </p>
            <div class="mt-3 inline-flex items-center gap-1.5 border border-amber-500/40 bg-amber-500/15 text-amber-300 px-2.5 py-1 text-[11px] font-mono group-hover:bg-amber-500/25 transition-colors">
              <i data-lucide="wrench" class="w-3.5 h-3.5"></i>
              <span>Enable Component</span>
            </div>
          </div>

          <div>
            <div class="flex items-center justify-between mb-2">
              <h4 class="text-sm font-semibold tracking-tight flex items-center gap-2">
                <i data-lucide="keyboard" class="w-4 h-4 text-muted-foreground"></i> Keyboard Backlight
              </h4>
              <span id="kbd-backlight-badge" onclick="openKbdSetupModal()" class="inline-flex items-center border border-border bg-secondary px-2 py-0.5 text-xs font-mono font-medium cursor-pointer">100% (Wave)</span>
            </div>

            <!-- Illumination Slider -->
            <div class="space-y-1.5 mt-2">
              <div class="flex justify-between text-xs text-muted-foreground font-mono">
                <span>Brightness</span>
                <span id="kbd-sub-label">100%</span>
              </div>
              <input type="range" id="kbd-brightness-slider" min="0" max="100" value="100" onchange="setKbdBacklightLevel(this.value)" oninput="updateKbdBacklightLabel(this.value)" class="w-full">
            </div>

            <!-- RGB Effect Modes -->
            <div class="space-y-1 mt-3">
              <div class="text-[11px] text-muted-foreground font-mono">Lighting Effects</div>
              <div class="grid grid-cols-5 gap-1 font-mono text-[10px]">
                <button onclick="setKbdMode('wave')" id="kbd-mode-wave" class="border border-primary bg-primary text-primary-foreground py-1 px-1 text-center font-bold transition-colors" title="Rainbow Wave">Wave</button>
                <button onclick="setKbdMode('breathe')" id="kbd-mode-breathe" class="border border-border bg-background hover:bg-accent py-1 px-1 text-center transition-colors" title="Breathing">Breathe</button>
                <button onclick="setKbdMode('neon')" id="kbd-mode-neon" class="border border-border bg-background hover:bg-accent py-1 px-1 text-center transition-colors" title="Neon Cycle">Neon</button>
                <button onclick="setKbdMode('zoom')" id="kbd-mode-zoom" class="border border-border bg-background hover:bg-accent py-1 px-1 text-center transition-colors" title="Zoom Bounce">Zoom</button>
                <button onclick="setKbdMode('static')" id="kbd-mode-static" class="border border-border bg-background hover:bg-accent py-1 px-1 text-center transition-colors" title="Static Color">Static</button>
              </div>
            </div>

            <!-- Static Color Palette Swatches -->
            <div class="space-y-1 mt-3">
              <div class="text-[11px] text-muted-foreground font-mono">Static Color Presets</div>
              <div class="flex items-center gap-1.5 pt-0.5">
                <button onclick="setKbdColor('#00ffff')" class="w-5 h-5 border border-border shadow-sm transition-transform hover:scale-110" style="background-color: #00ffff;" title="Cyan"></button>
                <button onclick="setKbdColor('#ff2a2a')" class="w-5 h-5 border border-border shadow-sm transition-transform hover:scale-110" style="background-color: #ff2a2a;" title="Red"></button>
                <button onclick="setKbdColor('#00ff66')" class="w-5 h-5 border border-border shadow-sm transition-transform hover:scale-110" style="background-color: #00ff66;" title="Green"></button>
                <button onclick="setKbdColor('#0088ff')" class="w-5 h-5 border border-border shadow-sm transition-transform hover:scale-110" style="background-color: #0088ff;" title="Blue"></button>
                <button onclick="setKbdColor('#a855f7')" class="w-5 h-5 border border-border shadow-sm transition-transform hover:scale-110" style="background-color: #a855f7;" title="Purple"></button>
                <button onclick="setKbdColor('#f59e0b')" class="w-5 h-5 border border-border shadow-sm transition-transform hover:scale-110" style="background-color: #f59e0b;" title="Amber"></button>
                <button onclick="setKbdColor('#ffffff')" class="w-5 h-5 border border-border shadow-sm transition-transform hover:scale-110" style="background-color: #ffffff;" title="White"></button>
              </div>
            </div>
          </div>

          <!-- Quick Action Buttons -->
          <div class="grid grid-cols-4 gap-1.5 mt-4">
            <button onclick="triggerAction('kbd_backlight_down')" title="Dim -20%" class="inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors">
              <i data-lucide="minus" class="w-4 h-4 mb-0.5"></i>
              <span class="text-[10px] font-mono">-20%</span>
            </button>
            <button onclick="triggerAction('kbd_backlight_up')" title="Brighten +20%" class="inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors">
              <i data-lucide="plus" class="w-4 h-4 mb-0.5"></i>
              <span class="text-[10px] font-mono">+20%</span>
            </button>
            <button id="kbd-power-btn" onclick="triggerAction('kbd_backlight_toggle')" title="Toggle On/Off" class="inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors">
              <i data-lucide="power" class="w-4 h-4 mb-0.5"></i>
              <span class="text-[10px] font-mono">Toggle</span>
            </button>
            <button onclick="setKbdMode('wave')" title="Reset to Rainbow Wave" class="inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors">
              <i data-lucide="sparkles" class="w-4 h-4 mb-0.5 text-amber-400"></i>
              <span class="text-[10px] font-mono">Wave</span>
            </button>
          </div>
        </div>

        <!-- 7. Touchpad & Input Peripherals -->
        <div id="card-touchpad" class="border border-border bg-card text-card-foreground shadow-sm p-6 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between mb-2">
              <h4 class="text-sm font-semibold tracking-tight flex items-center gap-2">
                <i data-lucide="mouse-pointer" class="w-4 h-4 text-muted-foreground"></i> Touchpad &amp; Pointer
              </h4>
              <span id="touchpad-status-badge" class="inline-flex items-center border border-border bg-secondary px-2 py-0.5 text-xs font-mono font-medium">Active</span>
            </div>

            <!-- Pointer Speed Slider -->
            <div class="space-y-1.5 mt-2">
              <div class="flex justify-between text-xs text-muted-foreground font-mono">
                <span>Pointer Speed</span>
                <span id="touchpad-speed-label">50%</span>
              </div>
              <input type="range" id="touchpad-speed-slider" min="0" max="100" value="50" onchange="setTouchpadSpeed(this.value)" oninput="updateTouchpadSpeedLabel(this.value)" class="w-full">
            </div>

            <!-- Feature Toggles -->
            <div class="space-y-2 mt-3 pt-3 border-t border-border">
              <div class="flex items-center justify-between">
                <span class="text-xs font-mono text-muted-foreground flex items-center gap-1.5">
                  <i data-lucide="hand" class="w-3.5 h-3.5"></i> Tap to Click
                </span>
                <button id="touchpad-tap-btn" onclick="triggerAction('touchpad_tap_toggle')" class="border border-border bg-background hover:bg-accent px-2.5 py-1 text-[11px] font-mono transition-colors">
                  ON
                </button>
              </div>

              <div class="flex items-center justify-between">
                <span class="text-xs font-mono text-muted-foreground flex items-center gap-1.5">
                  <i data-lucide="arrow-down-up" class="w-3.5 h-3.5"></i> Natural Scrolling
                </span>
                <button id="touchpad-scroll-btn" onclick="triggerAction('touchpad_natural_scroll_toggle')" class="border border-border bg-background hover:bg-accent px-2.5 py-1 text-[11px] font-mono transition-colors">
                  ON
                </button>
              </div>
            </div>
          </div>

          <!-- Quick Action Buttons -->
          <div class="grid grid-cols-4 gap-1.5 mt-4">
            <button onclick="triggerAction('touchpad_speed_down')" title="Speed -15%" class="inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors">
              <i data-lucide="minus" class="w-4 h-4 mb-0.5"></i>
              <span class="text-[10px] font-mono">-15%</span>
            </button>
            <button onclick="triggerAction('touchpad_speed_up')" title="Speed +15%" class="inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors">
              <i data-lucide="plus" class="w-4 h-4 mb-0.5"></i>
              <span class="text-[10px] font-mono">+15%</span>
            </button>
            <button id="touchpad-power-btn" onclick="triggerAction('touchpad_toggle')" title="Toggle Touchpad" class="inline-flex flex-col items-center justify-center border border-primary bg-primary text-primary-foreground py-2 text-xs transition-colors">
              <i data-lucide="power" class="w-4 h-4 mb-0.5"></i>
              <span class="text-[10px] font-mono">Toggle</span>
            </button>
            <button onclick="setTouchpadSpeed(50)" title="Reset Speed to 50%" class="inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors">
              <i data-lucide="rotate-ccw" class="w-4 h-4 mb-0.5"></i>
              <span class="text-[10px] font-mono">50%</span>
            </button>
          </div>
        </div>

        <!-- 8. Screen Studio & Capture -->
        <div id="card-screen-studio" class="border border-border bg-card text-card-foreground shadow-sm p-6 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-sm font-semibold tracking-tight flex items-center gap-2">
                <i data-lucide="camera" class="w-4 h-4 text-muted-foreground"></i> Screen Studio
              </h4>
              <span id="recording-status-badge" class="inline-flex items-center border border-border bg-secondary px-2 py-0.5 text-xs font-mono font-medium">Idle</span>
            </div>

            <p class="text-xs text-muted-foreground mb-3">Full-desktop display capture, ffmpeg recording, and remote sharing.</p>

            <div class="space-y-2">
              <div class="flex items-center justify-between border border-border bg-background p-2.5">
                <div class="flex items-center gap-2 text-xs">
                  <i data-lucide="video" class="w-4 h-4 text-emerald-400"></i>
                  <span>Desktop Recording</span>
                </div>
                <button id="recording-toggle-btn" onclick="triggerAction('screen_recording_toggle')" class="border border-border bg-background hover:bg-accent px-2.5 py-1 text-xs font-mono transition-colors">
                  Start Record
                </button>
              </div>

              <div class="flex items-center justify-between border border-border bg-background p-2.5">
                <div class="flex items-center gap-2 text-xs">
                  <i data-lucide="share-2" class="w-4 h-4 text-blue-400"></i>
                  <span>Remote Desktop (RDP)</span>
                </div>
                <button id="sharing-toggle-btn" onclick="triggerAction('screen_sharing_toggle')" class="border border-border bg-background hover:bg-accent px-2.5 py-1 text-xs font-mono transition-colors">
                  Disabled
                </button>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-2 mt-4">
            <button onclick="triggerAction('take_screenshot')" class="inline-flex items-center justify-center border border-primary bg-primary text-primary-foreground hover:bg-primary/90 py-2 text-xs font-medium gap-1.5 transition-colors">
              <i data-lucide="camera" class="w-3.5 h-3.5"></i>
              <span>Take Screenshot</span>
            </button>
            <button onclick="triggerAction('screen_recording_toggle')" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs font-medium gap-1.5 transition-colors">
              <i data-lucide="circle-dot" class="w-3.5 h-3.5 text-rose-500"></i>
              <span id="record-btn-text">Record Screen</span>
            </button>
          </div>
        </div>

        <!-- 9. Desktop Workspace & Clipboard -->
        <div id="card-workspace-clipboard" class="border border-border bg-card text-card-foreground shadow-sm p-6 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-sm font-semibold tracking-tight flex items-center gap-2">
                <i data-lucide="layout" class="w-4 h-4 text-muted-foreground"></i> Workspace &amp; Clipboard
              </h4>
              <span id="monitors-count-badge" class="inline-flex items-center border border-border bg-secondary px-2 py-0.5 text-xs font-mono font-medium">1 Display</span>
            </div>

            <div class="space-y-2.5">
              <!-- Idle Blanking Timeout -->
              <div>
                <div class="flex justify-between items-center text-xs text-muted-foreground font-mono mb-1">
                  <span>Screen Blanking Timeout</span>
                  <span id="blanking-label">Never</span>
                </div>
                <div class="grid grid-cols-4 gap-1 font-mono text-[11px]">
                  <button onclick="setBlanking(0)" class="border border-border bg-background hover:bg-accent py-1 text-center transition-colors">Never</button>
                  <button onclick="setBlanking(300)" class="border border-border bg-background hover:bg-accent py-1 text-center transition-colors">5 min</button>
                  <button onclick="setBlanking(600)" class="border border-border bg-background hover:bg-accent py-1 text-center transition-colors">10 min</button>
                  <button onclick="setBlanking(900)" class="border border-border bg-background hover:bg-accent py-1 text-center transition-colors">15 min</button>
                </div>
              </div>

              <!-- Clipboard Status & Action -->
              <div class="pt-2 border-t border-border">
                <div class="flex justify-between items-center text-xs text-muted-foreground font-mono mb-1">
                  <span>System Clipboard</span>
                  <button onclick="triggerAction('clipboard_clear')" class="text-rose-400 hover:underline">Clear</button>
                </div>
                <div class="flex gap-1.5">
                  <button onclick="triggerAction('clipboard_read')" class="flex-1 border border-border bg-background hover:bg-accent py-1 text-xs font-mono transition-colors">
                    Read Clipboard
                  </button>
                  <button onclick="copySampleText()" class="border border-border bg-background hover:bg-accent px-2 py-1 text-xs font-mono transition-colors" title="Copy Test String">
                    Copy Test
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-2 mt-4">
            <button onclick="triggerAction('wallpaper_status')" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs font-medium gap-1.5 transition-colors">
              <i data-lucide="image" class="w-3.5 h-3.5"></i>
              <span>Wallpaper Info</span>
            </button>
            <button onclick="triggerAction('monitors_status')" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs font-medium gap-1.5 transition-colors">
              <i data-lucide="monitor" class="w-3.5 h-3.5"></i>
              <span>Displays Info</span>
            </button>
          </div>
        </div>

      </div>

    </div>

    <!-- TAB 2: VITALS VIEW (Supports Graphical Dial View & Normal Text View) -->
    <div id="view-vitals" class="hidden space-y-6">

      <!-- Quick Stats Strip: Graphical View (gauge-ui.dev Animated SVG Gauges) -->
      <div id="strip-graphical-view" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <!-- 1. GPU TEMP GAUGE -->
        <div class="border border-border bg-card p-3 shadow-sm flex flex-col items-center">
          <div class="w-full flex items-center justify-between text-[11px] text-muted-foreground font-mono mb-1">
            <span>GPU TEMP</span>
            <i data-lucide="flame" class="w-3.5 h-3.5 text-amber-500"></i>
          </div>
          <div id="gauge-stat-gpu" class="w-28 h-24"></div>
          <div class="text-[10px] text-muted-foreground font-mono mt-1" id="stat-gpu-vram">VRAM: 3.8/8.2 GB</div>
        </div>

        <!-- 2. CPU LOAD GAUGE -->
        <div class="border border-border bg-card p-3 shadow-sm flex flex-col items-center">
          <div class="w-full flex items-center justify-between text-[11px] text-muted-foreground font-mono mb-1">
            <span>CPU LOAD</span>
            <i data-lucide="cpu" class="w-3.5 h-3.5 text-cyan-400"></i>
          </div>
          <div id="gauge-stat-cpu" class="w-28 h-24"></div>
          <div class="text-[10px] text-muted-foreground font-mono mt-1" id="stat-cpu-temp">Package: 58°C</div>
        </div>

        <!-- 3. RAM USAGE GAUGE -->
        <div class="border border-border bg-card p-3 shadow-sm flex flex-col items-center">
          <div class="w-full flex items-center justify-between text-[11px] text-muted-foreground font-mono mb-1">
            <span>RAM USAGE</span>
            <i data-lucide="layers" class="w-3.5 h-3.5 text-purple-400"></i>
          </div>
          <div id="gauge-stat-ram" class="w-28 h-24"></div>
          <div class="text-[10px] text-muted-foreground font-mono mt-1" id="stat-ram-gb">7.8 / 14.8 GB</div>
        </div>

        <!-- 4. NVMe STORAGE GAUGE -->
        <div class="border border-border bg-card p-3 shadow-sm flex flex-col items-center">
          <div class="w-full flex items-center justify-between text-[11px] text-muted-foreground font-mono mb-1">
            <span>NVMe ROOT</span>
            <i data-lucide="hard-drive" class="w-3.5 h-3.5 text-emerald-400"></i>
          </div>
          <div id="gauge-stat-disk" class="w-28 h-24"></div>
          <div class="text-[10px] text-muted-foreground font-mono mt-1" id="stat-disk-gb">68 / 479 GB</div>
        </div>

        <!-- 5. DISPLAY BRIGHTNESS GAUGE -->
        <div class="border border-border bg-card p-3 shadow-sm flex flex-col items-center">
          <div class="w-full flex items-center justify-between text-[11px] text-muted-foreground font-mono mb-1">
            <span>DISPLAY</span>
            <i data-lucide="sun" class="w-3.5 h-3.5 text-amber-400"></i>
          </div>
          <div id="gauge-stat-bright" class="w-28 h-24"></div>
          <div class="text-[10px] text-muted-foreground font-mono mt-1" id="stat-night-light">Night Light: ON</div>
        </div>

        <!-- 6. BATTERY / POWER GAUGE -->
        <div class="border border-border bg-card p-3 shadow-sm flex flex-col items-center">
          <div class="w-full flex items-center justify-between text-[11px] text-muted-foreground font-mono mb-1">
            <span>POWER</span>
            <i data-lucide="battery" class="w-3.5 h-3.5 text-emerald-400"></i>
          </div>
          <div id="gauge-stat-bat" class="w-28 h-24"></div>
          <div class="text-[10px] text-muted-foreground font-mono uppercase truncate mt-1" id="stat-power-profile">Balanced</div>
        </div>
      </div>

      <!-- Quick Stats Strip: Normal Text View (Like Before) -->
      <div id="strip-text-view" class="hidden grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <!-- 1. GPU Text Card -->
        <div class="border border-border bg-card p-3 shadow-sm">
          <div class="flex items-center justify-between text-xs text-muted-foreground font-mono">
            <span>GPU TEMP</span>
            <i data-lucide="flame" class="w-3.5 h-3.5 text-amber-500"></i>
          </div>
          <div class="text-xl font-bold text-foreground mt-1" id="text-gpu-temp">42°C</div>
          <div class="text-[11px] text-muted-foreground font-mono mt-0.5" id="text-gpu-vram">VRAM: 3.8/8.2 GB</div>
          <div class="h-1.5 w-full overflow-hidden bg-secondary mt-2">
            <div id="text-gpu-bar" class="h-full bg-primary" style="width: 47%"></div>
          </div>
        </div>

        <!-- 2. CPU Text Card -->
        <div class="border border-border bg-card p-3 shadow-sm">
          <div class="flex items-center justify-between text-xs text-muted-foreground font-mono">
            <span>CPU LOAD</span>
            <i data-lucide="cpu" class="w-3.5 h-3.5 text-cyan-400"></i>
          </div>
          <div class="text-xl font-bold text-foreground mt-1" id="text-cpu-load">12%</div>
          <div class="text-[11px] text-muted-foreground font-mono mt-0.5" id="text-cpu-temp">Package: 58°C</div>
          <div class="h-1.5 w-full overflow-hidden bg-secondary mt-2">
            <div id="text-cpu-bar" class="h-full bg-primary" style="width: 12%"></div>
          </div>
        </div>

        <!-- 3. RAM Text Card -->
        <div class="border border-border bg-card p-3 shadow-sm">
          <div class="flex items-center justify-between text-xs text-muted-foreground font-mono">
            <span>RAM USAGE</span>
            <i data-lucide="layers" class="w-3.5 h-3.5 text-purple-400"></i>
          </div>
          <div class="text-xl font-bold text-foreground mt-1" id="text-ram-pct">52%</div>
          <div class="text-[11px] text-muted-foreground font-mono mt-0.5" id="text-ram-gb">7.8 / 14.8 GB</div>
          <div class="h-1.5 w-full overflow-hidden bg-secondary mt-2">
            <div id="text-ram-bar" class="h-full bg-primary" style="width: 52%"></div>
          </div>
        </div>

        <!-- 4. Storage Text Card -->
        <div class="border border-border bg-card p-3 shadow-sm">
          <div class="flex items-center justify-between text-xs text-muted-foreground font-mono">
            <span>NVMe ROOT</span>
            <i data-lucide="hard-drive" class="w-3.5 h-3.5 text-emerald-400"></i>
          </div>
          <div class="text-xl font-bold text-foreground mt-1" id="text-disk-pct">14%</div>
          <div class="text-[11px] text-muted-foreground font-mono mt-0.5" id="text-disk-gb">68 / 479 GB</div>
          <div class="h-1.5 w-full overflow-hidden bg-secondary mt-2">
            <div id="text-disk-bar" class="h-full bg-primary" style="width: 14%"></div>
          </div>
        </div>

        <!-- 5. Brightness Text Card -->
        <div class="border border-border bg-card p-3 shadow-sm">
          <div class="flex items-center justify-between text-xs text-muted-foreground font-mono">
            <span>DISPLAY</span>
            <i data-lucide="sun" class="w-3.5 h-3.5 text-amber-400"></i>
          </div>
          <div class="text-xl font-bold text-foreground mt-1" id="text-bright-pct">40%</div>
          <div class="text-[11px] text-muted-foreground font-mono mt-0.5" id="text-night-light">Night Light: ON</div>
          <div class="h-1.5 w-full overflow-hidden bg-secondary mt-2">
            <div id="text-bright-bar" class="h-full bg-primary" style="width: 40%"></div>
          </div>
        </div>

        <!-- 6. Battery / Power Text Card -->
        <div class="border border-border bg-card p-3 shadow-sm">
          <div class="flex items-center justify-between text-xs text-muted-foreground font-mono">
            <span>POWER</span>
            <i data-lucide="battery" class="w-3.5 h-3.5 text-emerald-400"></i>
          </div>
          <div class="text-xl font-bold text-foreground mt-1" id="text-bat-pct">41%</div>
          <div class="text-[11px] text-muted-foreground font-mono uppercase truncate mt-0.5" id="text-power-profile">Balanced</div>
          <div class="h-1.5 w-full overflow-hidden bg-secondary mt-2">
            <div id="text-bat-bar" class="h-full bg-primary" style="width: 41%"></div>
          </div>
        </div>
      </div>
      
      <!-- Graphical Instrument Cluster View (gauge-ui.dev with Nested GaugeInset) -->
      <div id="vitals-graphical-view" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <!-- Detailed GPU Instrument Card -->
        <div class="border border-border bg-card text-card-foreground shadow-sm p-6 flex flex-col justify-between">
          <div class="flex items-center justify-between mb-2">
            <div>
              <h3 class="text-base font-semibold leading-none tracking-tight">NVIDIA RTX 4070</h3>
              <p class="text-xs text-muted-foreground mt-1">Thermal &amp; VRAM Nested Gauge</p>
            </div>
            <span class="inline-flex items-center border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-mono font-medium text-emerald-400">CUDA Active</span>
          </div>

          <!-- Large Composite Gauge + GaugeInset -->
          <div class="flex items-center justify-center my-2 bg-background border border-border p-4">
            <div id="gauge-vital-gpu" class="w-56 h-52"></div>
          </div>

          <div class="grid grid-cols-3 gap-2 pt-2">
            <div class="border border-border bg-background p-2.5">
              <div class="text-[10px] text-muted-foreground font-mono">CORE UTIL</div>
              <div class="text-sm font-bold text-foreground mt-0.5" id="detail-gpu-util">0%</div>
            </div>
            <div class="border border-border bg-background p-2.5">
              <div class="text-[10px] text-muted-foreground font-mono">VRAM USED</div>
              <div class="text-sm font-bold text-foreground mt-0.5" id="detail-gpu-vram">3867 MB</div>
            </div>
            <div class="border border-border bg-background p-2.5">
              <div class="text-[10px] text-muted-foreground font-mono">POWER DRAW</div>
              <div class="text-sm font-bold text-foreground mt-0.5" id="detail-gpu-power">13.3 W</div>
            </div>
          </div>
          <div class="hidden" id="detail-gpu-temp">45°C</div>
        </div>

        <!-- Detailed CPU & RAM Instrument Card -->
        <div class="border border-border bg-card text-card-foreground shadow-sm p-6 flex flex-col justify-between">
          <div class="flex items-center justify-between mb-2">
            <div>
              <h3 class="text-base font-semibold leading-none tracking-tight">Compute &amp; Memory</h3>
              <p class="text-xs text-muted-foreground mt-1">CPU Load &amp; Package Temp Inset</p>
            </div>
            <span class="inline-flex items-center border border-border bg-secondary px-2.5 py-0.5 text-xs font-mono font-medium">x86_64</span>
          </div>

          <!-- Large Composite Gauge + GaugeInset -->
          <div class="flex items-center justify-center my-2 bg-background border border-border p-4">
            <div id="gauge-vital-cpu" class="w-56 h-52"></div>
          </div>

          <div class="grid grid-cols-3 gap-2 pt-2">
            <div class="border border-border bg-background p-2.5">
              <div class="text-[10px] text-muted-foreground font-mono">CPU LOAD</div>
              <div class="text-sm font-bold text-foreground mt-0.5" id="detail-cpu-load">12%</div>
            </div>
            <div class="border border-border bg-background p-2.5">
              <div class="text-[10px] text-muted-foreground font-mono">RAM ALLOC</div>
              <div class="text-sm font-bold text-foreground mt-0.5" id="detail-ram-used">7.8 GB</div>
            </div>
            <div class="border border-border bg-background p-2.5">
              <div class="text-[10px] text-muted-foreground font-mono">GOVERNOR</div>
              <div class="text-sm font-bold text-foreground mt-0.5 uppercase truncate" id="detail-governor">Balanced</div>
            </div>
          </div>
          <div class="hidden" id="detail-cpu-temp">60°C</div>
        </div>

        <!-- Detailed Storage, Battery & Radios Instrument Card -->
        <div class="border border-border bg-card text-card-foreground shadow-sm p-6 flex flex-col justify-between">
          <div class="flex items-center justify-between mb-2">
            <div>
              <h3 class="text-base font-semibold leading-none tracking-tight">Storage &amp; Battery</h3>
              <p class="text-xs text-muted-foreground mt-1">NVMe Root &amp; Battery Charge Inset</p>
            </div>
            <span class="inline-flex items-center border border-border bg-secondary px-2.5 py-0.5 text-xs font-mono font-medium" id="detail-ip-badge">192.168.1.48</span>
          </div>

          <!-- Large Composite Gauge + GaugeInset -->
          <div class="flex items-center justify-center my-2 bg-background border border-border p-4">
            <div id="gauge-vital-disk" class="w-56 h-52"></div>
          </div>

          <div class="grid grid-cols-3 gap-2 pt-2 text-xs">
            <div class="border border-border bg-background p-2.5">
              <div class="text-[10px] text-muted-foreground font-mono">NVMe USED</div>
              <div class="text-sm font-bold text-foreground mt-0.5" id="detail-disk-used">68.1 GB</div>
            </div>
            <div class="border border-border bg-background p-2.5">
              <div class="text-[10px] text-muted-foreground font-mono">WI-FI SSID</div>
              <div class="text-xs font-bold text-foreground mt-0.5 truncate" id="detail-wifi-ssid">Wi-Fi</div>
            </div>
            <div class="border border-border bg-background p-2.5">
              <div class="text-[10px] text-muted-foreground font-mono">BLUETOOTH</div>
              <div class="text-xs font-bold text-emerald-400 mt-0.5" id="detail-bt-status">On</div>
            </div>
          </div>
          <div class="hidden" id="detail-uptime">Active</div>
        </div>
      </div>

      <!-- Normal Text & Progress Bar View (Like Before) -->
      <div id="vitals-text-view" class="hidden grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <!-- Detailed GPU Card (Text View) -->
        <div class="border border-border bg-card text-card-foreground shadow-sm p-6">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="text-base font-semibold leading-none tracking-tight">NVIDIA RTX 4070</h3>
              <p class="text-xs text-muted-foreground mt-1">Dedicated Graphics Processor</p>
            </div>
            <span class="inline-flex items-center border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-mono font-medium text-emerald-400">Active</span>
          </div>

          <div class="space-y-4">
            <div>
              <div class="flex justify-between text-xs text-muted-foreground font-mono mb-1">
                <span>GPU Core Utilization</span>
                <span id="text-detail-gpu-util">0%</span>
              </div>
              <div class="h-2 w-full overflow-hidden bg-secondary">
                <div id="text-bar-gpu-util" class="h-full bg-primary" style="width: 0%"></div>
              </div>
            </div>

            <div>
              <div class="flex justify-between text-xs text-muted-foreground font-mono mb-1">
                <span>VRAM Allocation (8.2 GB Total)</span>
                <span id="text-detail-gpu-vram">3867 MB</span>
              </div>
              <div class="h-2 w-full overflow-hidden bg-secondary">
                <div id="text-bar-gpu-vram" class="h-full bg-primary" style="width: 47%"></div>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3 pt-2">
              <div class="border border-border bg-background p-2.5">
                <div class="text-[10px] text-muted-foreground font-mono">TEMPERATURE</div>
                <div class="text-base font-bold text-foreground mt-0.5" id="text-detail-gpu-temp">45°C</div>
              </div>
              <div class="border border-border bg-background p-2.5">
                <div class="text-[10px] text-muted-foreground font-mono">POWER DRAW</div>
                <div class="text-base font-bold text-foreground mt-0.5" id="text-detail-gpu-power">13.3 W</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Detailed CPU & RAM Card (Text View) -->
        <div class="border border-border bg-card text-card-foreground shadow-sm p-6">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="text-base font-semibold leading-none tracking-tight">Compute &amp; Memory</h3>
              <p class="text-xs text-muted-foreground mt-1">Intel Multi-Core Processor</p>
            </div>
            <span class="inline-flex items-center border border-border bg-secondary px-2.5 py-0.5 text-xs font-mono font-medium">x86_64</span>
          </div>

          <div class="space-y-4">
            <div>
              <div class="flex justify-between text-xs text-muted-foreground font-mono mb-1">
                <span>CPU Overall Load</span>
                <span id="text-detail-cpu-load">12%</span>
              </div>
              <div class="h-2 w-full overflow-hidden bg-secondary">
                <div id="text-bar-cpu-load" class="h-full bg-primary" style="width: 12%"></div>
              </div>
            </div>

            <div>
              <div class="flex justify-between text-xs text-muted-foreground font-mono mb-1">
                <span>System RAM Usage (14.8 GB Total)</span>
                <span id="text-detail-ram-used">7.8 GB</span>
              </div>
              <div class="h-2 w-full overflow-hidden bg-secondary">
                <div id="text-bar-ram-used" class="h-full bg-primary" style="width: 52%"></div>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3 pt-2">
              <div class="border border-border bg-background p-2.5">
                <div class="text-[10px] text-muted-foreground font-mono">PACKAGE TEMP</div>
                <div class="text-base font-bold text-foreground mt-0.5" id="text-detail-cpu-temp">60°C</div>
              </div>
              <div class="border border-border bg-background p-2.5">
                <div class="text-[10px] text-muted-foreground font-mono">GOVERNOR</div>
                <div class="text-base font-bold text-foreground mt-0.5 uppercase" id="text-detail-governor">Balanced</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Detailed Storage & Radios Card (Text View) -->
        <div class="border border-border bg-card text-card-foreground shadow-sm p-6">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="text-base font-semibold leading-none tracking-tight">Storage &amp; Radios</h3>
              <p class="text-xs text-muted-foreground mt-1">NVMe Disk, Wi-Fi &amp; Bluetooth</p>
            </div>
            <span class="inline-flex items-center border border-border bg-secondary px-2.5 py-0.5 text-xs font-mono font-medium" id="text-detail-ip-badge">192.168.1.48</span>
          </div>

          <div class="space-y-4">
            <div>
              <div class="flex justify-between text-xs text-muted-foreground font-mono mb-1">
                <span>Root NVMe Disk (479 GB Total)</span>
                <span id="text-detail-disk-used">68.1 GB</span>
              </div>
              <div class="h-2 w-full overflow-hidden bg-secondary">
                <div id="text-bar-disk-used" class="h-full bg-primary" style="width: 14%"></div>
              </div>
            </div>

            <div class="space-y-2 pt-1 text-xs">
              <div class="flex items-center justify-between border border-border bg-background p-2.5">
                <span class="flex items-center gap-2"><i data-lucide="wifi" class="w-3.5 h-3.5 text-muted-foreground"></i> Wi-Fi Network</span>
                <span class="font-mono font-semibold" id="text-detail-wifi-ssid">Excitel_Kaizzwifi</span>
              </div>
              <div class="flex items-center justify-between border border-border bg-background p-2.5">
                <span class="flex items-center gap-2"><i data-lucide="bluetooth" class="w-3.5 h-3.5 text-muted-foreground"></i> Bluetooth Radio</span>
                <span class="font-mono font-semibold text-emerald-400" id="text-detail-bt-status">Powered On</span>
              </div>
              <div class="flex items-center justify-between border border-border bg-background p-2.5">
                <span class="flex items-center gap-2"><i data-lucide="clock" class="w-3.5 h-3.5 text-muted-foreground"></i> System Uptime</span>
                <span class="font-mono font-semibold" id="text-detail-uptime">Active Session</span>
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- TAB 2: ACTIVITY LOGS VIEW -->
    <div id="view-logs" class="hidden space-y-6">
      <div class="border border-border bg-card text-card-foreground shadow-sm p-6">
        <div class="flex items-center justify-between mb-4 border-b border-border pb-3">
          <div>
            <h3 class="text-base font-semibold leading-none tracking-tight">Realtime Activity Stream</h3>
            <p class="text-xs text-muted-foreground mt-1">Live audit log of system commands, telemetry updates, and hardware executions.</p>
          </div>
          <button onclick="clearHistory()" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground px-3 py-1.5 text-xs font-medium transition-colors">
            Clear Logs
          </button>
        </div>

        <div id="activity-feed" class="space-y-2 overflow-y-auto max-h-[500px] pr-1">
          <div class="text-center py-12 text-muted-foreground font-mono text-xs">Waiting for events...</div>
        </div>
      </div>
    </div>

  </main>

  <!-- Bottom Center Floating Tab Dock -->
  <div class="fixed bottom-5 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
    <div class="inline-flex h-11 items-center justify-center bg-muted/90 p-1 text-muted-foreground backdrop-blur supports-[backdrop-filter]:bg-muted/75 shadow-2xl border border-border pointer-events-auto">
      <button onclick="switchTab('controls')" id="tab-controls" class="inline-flex items-center justify-center whitespace-nowrap px-4 py-1.5 text-xs font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 bg-background text-foreground shadow-sm">
        <i data-lucide="sliders" class="w-4 h-4 mr-2"></i> Controls
      </button>
      <button onclick="switchTab('vitals')" id="tab-vitals" class="inline-flex items-center justify-center whitespace-nowrap px-4 py-1.5 text-xs font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 hover:text-foreground">
        <i data-lucide="activity" class="w-4 h-4 mr-2"></i> Vitals
      </button>
      <button onclick="switchTab('logs')" id="tab-logs" class="inline-flex items-center justify-center whitespace-nowrap px-4 py-1.5 text-xs font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 hover:text-foreground">
        <i data-lucide="terminal" class="w-4 h-4 mr-2"></i> Activity Logs
      </button>
    </div>
  </div>

  <!-- shadcn Toast Container -->
  <div id="toast-container" class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none"></div>

  <!-- Modal: Keyboard Backlight Hardware Setup / MOK Enrollment Dialog -->
  <div id="kbd-setup-modal" class="hidden fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
    <div id="kbd-setup-modal-card" class="relative w-full max-w-lg border border-border bg-card text-card-foreground shadow-2xl p-6 sm:p-7 space-y-5 animate-in fade-in zoom-in-95 duration-150">
      
      <!-- Modal Header -->
      <div class="flex items-start justify-between border-b border-border pb-4">
        <div class="flex items-center gap-3">
          <div class="h-9 w-9 border border-amber-500/40 bg-amber-500/10 flex items-center justify-center text-amber-400 shrink-0">
            <i data-lucide="shield-alert" class="w-5 h-5"></i>
          </div>
          <div>
            <h3 class="text-sm font-semibold tracking-tight text-foreground">Enable Keyboard Backlight Hardware</h3>
            <p class="text-xs text-muted-foreground mt-0.5">Acer Predator PHN16-72 &bull; ACPI WMI Driver Setup</p>
          </div>
        </div>
        <button onclick="closeKbdSetupModal()" class="text-muted-foreground hover:text-foreground p-1 transition-colors">
          <i data-lucide="x" class="w-4 h-4"></i>
        </button>
      </div>

      <!-- Explanation -->
      <div class="text-xs text-muted-foreground space-y-2 leading-relaxed">
        <p>
          On your <strong class="text-foreground font-mono">Acer Predator PHN16-72</strong>, keyboard lighting is driven directly by the Embedded Controller (EC) via ACPI WMI (<code class="bg-muted px-1 py-0.5 font-mono text-[11px] text-foreground">\_SB.PC00.WMID.WMBH</code>).
        </p>
        <p>
          Because <strong class="text-foreground">Secure Boot</strong> is active, Linux blocks the built <code class="bg-muted px-1 py-0.5 font-mono text-[11px] text-foreground">acpi_call</code> driver until its signing key is authorized in your UEFI bootloader.
        </p>
      </div>

      <!-- Step-by-Step Instructions -->
      <div class="space-y-3">
        <div class="text-xs font-semibold uppercase tracking-wider font-mono text-muted-foreground">Follow these steps:</div>
        
        <!-- Step 1 -->
        <div class="border border-border bg-background p-3.5 space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-xs font-semibold text-foreground flex items-center gap-2">
              <span class="flex h-5 w-5 items-center justify-center border border-primary bg-primary text-primary-foreground text-[10px] font-mono">1</span>
              Enroll the MOK Key in Terminal
            </span>
            <button onclick="copyMokCommand()" id="copy-mok-btn" class="inline-flex items-center gap-1 border border-border bg-secondary hover:bg-accent px-2 py-0.5 text-[11px] font-mono transition-colors">
              <i data-lucide="copy" class="w-3 h-3"></i>
              <span id="copy-btn-text">Copy</span>
            </button>
          </div>
          <div class="bg-muted p-2 font-mono text-[11px] text-foreground select-all break-all border border-border/50">
            sudo mokutil --import /var/lib/shim-signed/mok/MOK.der
          </div>
          <p class="text-[11px] text-muted-foreground">
            Run this command and enter a temporary password (for example <code class="text-foreground font-mono font-bold">1234</code>).
          </p>
        </div>

        <!-- Step 2 -->
        <div class="border border-border bg-background p-3.5 space-y-1.5">
          <span class="text-xs font-semibold text-foreground flex items-center gap-2">
            <span class="flex h-5 w-5 items-center justify-center border border-primary bg-primary text-primary-foreground text-[10px] font-mono">2</span>
            Confirm on Next Reboot (10 seconds)
          </span>
          <p class="text-[11px] text-muted-foreground leading-relaxed">
            Reboot your laptop. When the blue <strong class="text-foreground">"Perform MOK management"</strong> screen appears:
          </p>
          <div class="bg-muted/60 p-2 font-mono text-[11px] text-foreground border border-border/50 space-y-1">
            <div>&bull; Select <strong class="text-primary">Enroll MOK</strong> &rarr; <strong class="text-primary">Continue</strong></div>
            <div>&bull; Select <strong class="text-primary">Yes</strong> to confirm</div>
            <div>&bull; Enter your password (<span class="text-muted-foreground">e.g. 1234</span>) &rarr; Select <strong class="text-primary">Reboot</strong></div>
          </div>
        </div>

        <!-- Alternative Note -->
        <div class="border border-border/60 bg-muted/30 p-3 text-[11px] text-muted-foreground space-y-1">
          <div class="text-foreground font-semibold flex items-center gap-1.5">
            <i data-lucide="info" class="w-3.5 h-3.5 text-blue-400"></i>
            <span>Alternative &amp; Temporary Control:</span>
          </div>
          <div>&bull; <strong class="text-foreground">Alternative:</strong> Disable Secure Boot in your UEFI BIOS (<kbd class="px-1 border border-border bg-background">F2</kbd> on startup).</div>
          <div>&bull; <strong class="text-foreground">Temporary:</strong> Use hardware keys <kbd class="px-1 border border-border bg-background">Fn + F4</kbd> / <kbd class="px-1 border border-border bg-background">Fn + F5</kbd> directly on your physical keyboard.</div>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="flex items-center justify-between border-t border-border pt-4">
        <button onclick="checkAndRefreshStatus()" id="modal-refresh-btn" class="inline-flex items-center gap-1.5 border border-border bg-secondary hover:bg-accent text-foreground px-3 py-1.5 text-xs font-mono transition-colors">
          <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i>
          <span>Check Status</span>
        </button>
        <button onclick="closeKbdSetupModal()" class="inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground px-4 py-1.5 text-xs font-medium transition-colors">
          Dismiss
        </button>
      </div>

    </div>
  </div>

  <!-- Client Script & gauge-ui.dev Engine -->
  <script>
    /* =========================================================================
     * flicker-dot Dot-Grid Mechanical Loading Spinner Engine (npm: flicker-dot)
     * ========================================================================= */
    const FlickerDot = (function() {
      const RADAR = [
        [false,true,true,true,true,true,false,false,false,true,true,true,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false],
        [false,false,false,false,true,true,true,false,false,false,false,true,true,true,false,false,false,false,true,true,true,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false],
        [false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,false,false,true,true,false,false,false,true,true,true,true,false,false,false,false,false,true,true,false,false,false,false,false,false,true,false,false,false,false,false,false,false],
        [false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,false,false,false,false,true,true,true,false,false,false,false,true,true,true,false,false,false,false,true,true,true],
        [false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,true,true,true,false,false,false,true,true,true,true,true,false],
        [false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,true,true,true,false,false,false,false,true,true,true,false,false,false,false,true,true,true,false,false,false,false],
        [false,false,false,false,false,false,false,true,false,false,false,false,false,false,true,true,false,false,false,false,false,true,true,true,true,false,false,false,true,true,false,false,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false],
        [true,true,true,false,false,false,false,true,true,true,false,false,false,false,true,true,true,false,false,false,false,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false]
      ];

      function render(opts = {}) {
        const grids = opts.grids || RADAR;
        const size = opts.size || 20;
        const variant = opts.variant || '7x7';
        const onColor = opts.onColor || 'hsl(var(--primary))';
        const offColor = opts.offColor || 'rgba(255, 255, 255, 0.12)';
        const speed = opts.speed || 1.2;

        const small = variant === '5x5';
        const FRAME_INTERVAL = 150;
        const DOT_R = 2;
        const PITCH = 6;
        const OFFSET = 3;
        const COLS = small ? 5 : 7;
        const VIEWBOX = small ? 30 : 42;
        const SAFE_AREA_INDICES = [];
        for (let r = 1; r <= 5; r++) {
          for (let c = 1; c <= 5; c++) SAFE_AREA_INDICES.push(r * 7 + c);
        }
        const frames = small ? grids.map(f => SAFE_AREA_INDICES.map(i => f[i])) : grids;
        const n = frames.length;
        const totalDots = frames[0].length;
        const dur = (n * FRAME_INTERVAL / 1000 / (speed > 0 ? speed : 1)).toFixed(3) + 's';
        const uid = 'fk' + Math.random().toString(36).substring(2, 8);

        const dotPatterns = Array.from({ length: totalDots }, (_, i) => frames.map(f => f[i]));
        const uniquePatterns = new Map();
        for (const pattern of dotPatterns) {
          const key = pattern.map(v => v ? '1' : '0').join('');
          if (pattern.some(v => v) && !pattern.every(v => v) && !uniquePatterns.has(key)) {
            uniquePatterns.set(key, pattern);
          }
        }

        function buildStops(pattern, n) {
          const stops = ['0% { opacity: ' + (pattern[0] ? 1 : 0) + '; }'];
          for (let i = 1; i < n; i++) {
            const pct = (i * 100 / n).toFixed(2);
            if (pattern[i] !== pattern[i - 1]) {
              stops.push((pct - 0.01).toFixed(2) + '% { opacity: ' + (pattern[i - 1] ? 1 : 0) + '; }');
              stops.push(pct + '% { opacity: ' + (pattern[i] ? 1 : 0) + '; }');
            }
          }
          stops.push('100% { opacity: ' + (pattern[n - 1] ? 1 : 0) + '; }');
          return stops.join(' ');
        }

        let keyframeCss = '';
        for (const [key, pattern] of uniquePatterns.entries()) {
          keyframeCss += '@keyframes ' + uid + '_' + key + ' { ' + buildStops(pattern, n) + ' } ';
        }

        const css = '[data-fk="' + uid + '"] circle { fill: var(--off); } [data-fk="' + uid + '"] circle.on { fill: var(--on); } @media (prefers-reduced-motion: reduce) { [data-fk="' + uid + '"] circle { animation: none !important; } } ' + keyframeCss;

        let baseCircles = '';
        let animCircles = '';
        for (let i = 0; i < totalDots; i++) {
          const cx = (i % COLS) * PITCH + OFFSET;
          const cy = Math.floor(i / COLS) * PITCH + OFFSET;
          const pattern = dotPatterns[i];
          const key = pattern.map(v => v ? '1' : '0').join('');
          const neverOn = pattern.every(v => !v);
          const alwaysOn = pattern.every(v => v);
          baseCircles += '<circle cx="' + cx + '" cy="' + cy + '" r="' + DOT_R + '" />';
          if (alwaysOn) {
            animCircles += '<circle class="on" cx="' + cx + '" cy="' + cy + '" r="' + DOT_R + '" />';
          } else if (!neverOn) {
            animCircles += '<circle class="on" cx="' + cx + '" cy="' + cy + '" r="' + DOT_R + '" opacity="' + (pattern[0] ? 1 : 0) + '" style="animation: ' + uid + '_' + key + ' var(--dur) linear infinite;" />';
          }
        }

        return '<svg data-fk="' + uid + '" width="' + size + '" height="' + size + '" viewBox="0 0 ' + VIEWBOX + ' ' + VIEWBOX + '" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg" role="status" aria-label="Loading" style="--on: ' + onColor + '; --off: ' + offColor + '; --dur: ' + dur + '; display: inline-block; vertical-align: middle; flex-shrink: 0;"><style>' + css + '</style>' + baseCircles + animCircles + '</svg>';
      }

      return { render, RADAR };
    })();

    /* =========================================================================
     * gauge-ui.dev Composable SVG Gauge Engine (from https://gauge-ui.dev/r/gauge.json)
     * Exact Math, Spring Physics (stepSpring, SUBSTEP=1/240), and Primitives:
     * GaugeTrack, GaugeArc, GaugeTickFill, GaugeTicks, GaugeTickLabels,
     * GaugeNeedle, GaugeHub, GaugeDot, GaugeZones, GaugeInset, GaugeValue, GaugeText
     * ========================================================================= */
    const GaugeMath = {
      clamp: (v, min, max) => Math.min(max, Math.max(min, v)),
      degToRad: (d) => (d * Math.PI) / 180,
      round: (n) => Math.round(n * 1000) / 1000,
      fmt: (n) => Number(n.toFixed(3)).toString(),
      polar(radius, angle) {
        const theta = this.degToRad(angle + 90);
        return {
          x: this.round(radius * Math.cos(theta)),
          y: this.round(radius * Math.sin(theta))
        };
      },
      valueToAngle(value, min, max, startAngle, endAngle) {
        const span = max - min;
        const t = span === 0 ? 0 : (this.clamp(value, min, max) - min) / span;
        return startAngle + t * (endAngle - startAngle);
      },
      arcPath(radius, from, to) {
        const sweep = Math.min(to - from, 360);
        if (sweep <= 0 || radius <= 0) return "";
        const pieces = Math.max(1, Math.ceil(sweep / 180));
        const step = sweep / pieces;
        const start = this.polar(radius, from);
        const parts = [`M ${this.fmt(start.x)} ${this.fmt(start.y)}`];
        for (let i = 1; i <= pieces; i++) {
          const p = this.polar(radius, from + step * i);
          parts.push(`A ${this.fmt(radius)} ${this.fmt(radius)} 0 0 1 ${this.fmt(p.x)} ${this.fmt(p.y)}`);
        }
        return parts.join(" ");
      },
      stepValues(min, max, intervals) {
        const n = Math.max(1, Math.round(intervals));
        return Array.from({ length: n + 1 }, (_, i) => min + ((max - min) * i) / n);
      },
      springPhysics(visualDuration = 0.55, bounce = 0.12) {
        const root = (2 * Math.PI) / (visualDuration * 1.2);
        const stiffness = root * root;
        const ratio = Math.min(1, Math.max(0.05, 1 - bounce));
        return { stiffness, damping: 2 * ratio * Math.sqrt(stiffness), mass: 1 };
      },
      stepSpring(state, target, physics, dt, precision) {
        const SUBSTEP = 1 / 240;
        let { value, velocity } = state;
        let remaining = Math.min(dt, 0.064);
        while (remaining > 0) {
          const h = Math.min(SUBSTEP, remaining);
          const force = -physics.stiffness * (value - target) - physics.damping * velocity;
          velocity += (force / physics.mass) * h;
          value += velocity * h;
          remaining -= h;
        }
        const done = Math.abs(value - target) < precision && Math.abs(velocity) < precision * 10;
        return done
          ? { state: { value: target, velocity: 0 }, done: true }
          : { state: { value, velocity }, done: false };
      }
    };

    class GaugeInstance {
      constructor(containerId, config) {
        this.container = document.getElementById(containerId);
        this.config = Object.assign({
          min: 0,
          max: 100,
          startAngle: 40,
          endAngle: 320,
          radius: 200,
          padding: 36,
          unit: "%",
          label: "",
          variant: "arc", // 'arc' | 'tick-fill' | 'needle' | 'zones-needle' | 'composite'
          color: "#fafafa",
          zones: null,
          inset: null
        }, config);

        this.target = 0;
        this.spring = { value: 0, velocity: 0 };
        this.insetTarget = 0;
        this.insetSpring = { value: 0, velocity: 0 };
        this.physics = GaugeMath.springPhysics(0.55, 0.14);
        this.animFrame = null;
        this.lastTime = performance.now();
        this.renderFrame();
      }

      setValue(nextVal, nextInsetVal = null) {
        this.target = GaugeMath.clamp(Number(nextVal) || 0, this.config.min, this.config.max);
        if (nextInsetVal !== null && this.config.inset) {
          this.insetTarget = GaugeMath.clamp(Number(nextInsetVal) || 0, this.config.inset.min || 0, this.config.inset.max || 100);
        }
        if (!this.animFrame) {
          this.lastTime = performance.now();
          const tick = (now) => {
            const dt = Math.max(0.001, (now - this.lastTime) / 1000);
            this.lastTime = now;
            const span = Math.abs(this.config.max - this.config.min) || 100;
            const res = GaugeMath.stepSpring(this.spring, this.target, this.physics, dt, span * 1e-4);
            this.spring = res.state;

            let insetDone = true;
            if (this.config.inset) {
              const iSpan = Math.abs((this.config.inset.max || 100) - (this.config.inset.min || 0)) || 100;
              const iRes = GaugeMath.stepSpring(this.insetSpring, this.insetTarget, this.physics, dt, iSpan * 1e-4);
              this.insetSpring = iRes.state;
              insetDone = iRes.done;
            }

            this.renderFrame();
            if (!res.done || !insetDone) {
              this.animFrame = requestAnimationFrame(tick);
            } else {
              this.animFrame = null;
            }
          };
          this.animFrame = requestAnimationFrame(tick);
        }
      }

      drawPrimitives(g, val, isInset = false) {
        const { min, max, startAngle, endAngle, radius, color, unit, label, variant, zones } = g;
        const angleOf = (v) => GaugeMath.valueToAngle(v, min, max, startAngle, endAngle);
        const curAngle = angleOf(val);
        let svg = "";

        // 1. GaugeZones (if configured)
        if (zones && zones.length > 0) {
          let prev = min;
          zones.forEach((z) => {
            const zEnd = Math.min(max, z.to);
            const a0 = angleOf(prev) + 1;
            const a1 = angleOf(zEnd) - 1;
            if (a1 > a0) {
              svg += `<path d="${GaugeMath.arcPath(radius + 20, a0, a1)}" fill="none" stroke="${z.color}" stroke-width="8" stroke-linecap="butt" stroke-opacity="0.85" />`;
            }
            prev = zEnd;
          });
        }

        // 2. Variant rendering
        if (variant === "tick-fill") {
          const count = isInset ? 20 : 32;
          const ticks = GaugeMath.stepValues(min, max, count);
          ticks.forEach((tv) => {
            const isLit = tv <= val + 0.001;
            const len = isLit ? 26 : 18;
            const half = len / 2;
            const ang = angleOf(tv);
            const p1 = GaugeMath.polar(radius - half, ang);
            const p2 = GaugeMath.polar(radius + half, ang);
            const strokeCol = isLit ? (typeof color === 'function' ? color(tv) : color) : "currentColor";
            const op = isLit ? 1 : 0.16;
            svg += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="${strokeCol}" stroke-opacity="${op}" stroke-width="${isInset ? 5 : 4.5}" stroke-linecap="butt" />`;
          });
        } else {
          // GaugeTrack + GaugeArc
          const trackW = isInset ? 20 : 22;
          svg += `<path d="${GaugeMath.arcPath(radius, startAngle, endAngle)}" fill="none" stroke="currentColor" stroke-opacity="0.14" stroke-width="${trackW}" stroke-linecap="butt" />`;
          if (curAngle > startAngle + 0.1) {
            const activeCol = typeof color === "function" ? color(val) : color;
            svg += `<path d="${GaugeMath.arcPath(radius, startAngle, curAngle)}" fill="none" stroke="${activeCol}" stroke-width="${trackW}" stroke-linecap="butt" />`;
          }

          // GaugeTicks
          const tickCount = isInset ? 6 : 10;
          const ticks = GaugeMath.stepValues(min, max, tickCount);
          ticks.forEach((tv) => {
            const ang = angleOf(tv);
            const p1 = GaugeMath.polar(radius - 22, ang);
            const p2 = GaugeMath.polar(radius - 12, ang);
            svg += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="currentColor" stroke-opacity="0.35" stroke-width="2.5" />`;
          });
        }

        // 3. GaugeTickLabels (on composite large gauges)
        if (g.showLabels && !isInset) {
          const lbls = GaugeMath.stepValues(min, max, 5);
          lbls.forEach((lv) => {
            const p = GaugeMath.polar(radius - 46, angleOf(lv));
            svg += `<text x="${p.x}" y="${p.y}" fill="currentColor" fill-opacity="0.55" font-size="18" text-anchor="middle" dominant-baseline="central" class="font-mono tabular-nums">${Math.round(lv)}</text>`;
          });
        }

        // 4. GaugeNeedle or GaugeDot
        if (variant === "needle" || variant === "composite") {
          // Needle with center gap so GaugeValue sits cleanly in the middle
          const gap = isInset ? 55 : 74;
          const reach = radius * 0.84;
          if (reach > gap) {
            const pInner = GaugeMath.polar(gap, curAngle);
            const pTip = GaugeMath.polar(reach, curAngle);
            svg += `<line x1="${pInner.x}" y1="${pInner.y}" x2="${pTip.x}" y2="${pTip.y}" stroke="#fafafa" stroke-width="${isInset ? 6 : 5}" stroke-linecap="butt" />`;
          }
          const dotPos = GaugeMath.polar(radius, curAngle);
          svg += `<circle cx="${dotPos.x}" cy="${dotPos.y}" r="${isInset ? 9 : 8}" fill="#fafafa" />`;
        } else if (variant === "dot") {
          const dotPos = GaugeMath.polar(radius, curAngle);
          svg += `<circle cx="${dotPos.x}" cy="${dotPos.y}" r="14" fill="hsl(var(--background))" />`;
          svg += `<circle cx="${dotPos.x}" cy="${dotPos.y}" r="9" fill="${color}" />`;
        }

        // 5. GaugeValue & GaugeText
        const valY = g.inset ? -18 : 0;
        const valFontSize = isInset ? 68 : (g.inset ? 66 : 74);
        svg += `<text x="0" y="${valY}" fill="currentColor" font-size="${valFontSize}" font-weight="700" text-anchor="middle" dominant-baseline="central" class="font-mono tabular-nums">${Math.round(val)}${unit}</text>`;

        if (label) {
          const lblY = isInset ? 65 : (g.inset ? 28 : 68);
          svg += `<text x="0" y="${lblY}" fill="currentColor" fill-opacity="0.55" font-size="${isInset ? 28 : 24}" font-weight="600" text-anchor="middle" dominant-baseline="central" class="font-mono">${label}</text>`;
        }

        return svg;
      }

      renderFrame() {
        if (!this.container) return;
        const half = this.config.radius + this.config.padding;
        let inner = this.drawPrimitives(this.config, this.spring.value, false);

        // Nested <GaugeInset>
        if (this.config.inset) {
          const ins = Object.assign({
            min: 0,
            max: 100,
            startAngle: 40,
            endAngle: 320,
            radius: 200,
            x: 0,
            y: 112,
            scale: 0.36,
            unit: "%",
            label: "INSET",
            variant: "arc",
            color: "#38bdf8"
          }, this.config.inset);
          inner += `<g transform="translate(${ins.x} ${ins.y}) scale(${ins.scale})">${this.drawPrimitives(ins, this.insetSpring.value, true)}</g>`;
        }

        this.container.innerHTML = `<svg viewBox="${-half} ${-half} ${2 * half} ${2 * half}" preserveAspectRatio="xMidYMid meet" class="w-full h-full overflow-visible text-foreground">${inner}</svg>`;
      }
    }

    const gauges = {};

    function initGauges() {
      // 6 Top Strip Gauges
      gauges.statGpu = new GaugeInstance("gauge-stat-gpu", {
        min: 0, max: 100, unit: "°C", label: "RTX 4070", variant: "needle",
        color: "#f59e0b",
        zones: [{ to: 60, color: "#10b981" }, { to: 80, color: "#f59e0b" }, { to: 100, color: "#ef4444" }]
      });
      gauges.statCpu = new GaugeInstance("gauge-stat-cpu", {
        min: 0, max: 100, unit: "%", label: "CORE", variant: "tick-fill", color: "#22d3ee"
      });
      gauges.statRam = new GaugeInstance("gauge-stat-ram", {
        min: 0, max: 100, unit: "%", label: "MEMORY", variant: "dot", color: "#a855f7"
      });
      gauges.statDisk = new GaugeInstance("gauge-stat-disk", {
        min: 0, max: 100, unit: "%", label: "NVMe", variant: "arc", color: "#10b981"
      });
      gauges.statBright = new GaugeInstance("gauge-stat-bright", {
        min: 0, max: 100, unit: "%", label: "PANEL", variant: "tick-fill", color: "#fbbf24"
      });
      gauges.statBat = new GaugeInstance("gauge-stat-bat", {
        min: 0, max: 100, unit: "%", label: "CHARGE", variant: "arc", color: "#10b981",
        zones: [{ to: 20, color: "#ef4444" }, { to: 50, color: "#f59e0b" }, { to: 100, color: "#10b981" }]
      });

      // Controls View Interactive Gauges
      gauges.ctrlVol = new GaugeInstance("gauge-ctrl-vol", {
        min: 0, max: 150, unit: "%", label: "VOL", variant: "needle", color: "#fafafa"
      });
      gauges.ctrlMic = new GaugeInstance("gauge-ctrl-mic", {
        min: 0, max: 150, unit: "%", label: "MIC", variant: "tick-fill", color: "#22d3ee"
      });
      gauges.ctrlBright = new GaugeInstance("gauge-ctrl-bright", {
        min: 1, max: 100, unit: "%", label: "LUX", variant: "tick-fill", color: "#fbbf24"
      });

      // Vitals View Composite Gauges with Nested <GaugeInset>
      gauges.vitalGpu = new GaugeInstance("gauge-vital-gpu", {
        min: 0, max: 100, unit: "°C", label: "GPU TEMP", variant: "composite", showLabels: true, color: "#f59e0b",
        zones: [{ to: 60, color: "#10b981" }, { to: 80, color: "#f59e0b" }, { to: 100, color: "#ef4444" }],
        inset: { min: 0, max: 100, unit: "%", label: "VRAM", variant: "tick-fill", color: "#a855f7" }
      });
      gauges.vitalCpu = new GaugeInstance("gauge-vital-cpu", {
        min: 0, max: 100, unit: "%", label: "CPU LOAD", variant: "tick-fill", showLabels: true, color: "#22d3ee",
        inset: { min: 0, max: 100, unit: "°C", label: "PKG TEMP", variant: "arc", color: "#f59e0b" }
      });
      gauges.vitalDisk = new GaugeInstance("gauge-vital-disk", {
        min: 0, max: 100, unit: "%", label: "NVMe USED", variant: "composite", showLabels: true, color: "#10b981",
        inset: { min: 0, max: 100, unit: "%", label: "BATTERY", variant: "arc", color: "#10b981" }
      });
    }

    let isWakeEnabled = false;
    let isRecording = false;
    let useTTS = true;
    let currentViewMode = 'graphical';

    function setViewMode(mode) {
      currentViewMode = mode;
      const isGraph = mode === 'graphical';
      const btnG = document.getElementById('btn-mode-graphical');
      const btnT = document.getElementById('btn-mode-text');
      const stripG = document.getElementById('strip-graphical-view');
      const stripT = document.getElementById('strip-text-view');
      const vitG = document.getElementById('vitals-graphical-view');
      const vitT = document.getElementById('vitals-text-view');
      const audioG = document.getElementById('audio-gauges-row');
      const brightG = document.getElementById('bright-gauge-row');
      const brightDesc = document.getElementById('bright-desc-text');

      if (isGraph) {
        if (btnG) btnG.className = "h-7 w-7 flex items-center justify-center bg-background text-foreground shadow-sm transition-colors";
        if (btnT) btnT.className = "h-7 w-7 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors";
        if (stripG) stripG.classList.remove('hidden');
        if (stripT) stripT.classList.add('hidden');
        if (vitG) vitG.classList.remove('hidden');
        if (vitT) vitT.classList.add('hidden');
        if (audioG) audioG.classList.remove('hidden');
        if (brightG) brightG.classList.remove('hidden');
        if (brightDesc) brightDesc.classList.add('hidden');
        showToast("View Mode", "Switched to Animated Gauges view.");
      } else {
        if (btnT) btnT.className = "h-7 w-7 flex items-center justify-center bg-background text-foreground shadow-sm transition-colors";
        if (btnG) btnG.className = "h-7 w-7 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors";
        if (stripG) stripG.classList.add('hidden');
        if (stripT) stripT.classList.remove('hidden');
        if (vitG) vitG.classList.add('hidden');
        if (vitT) vitT.classList.remove('hidden');
        if (audioG) audioG.classList.add('hidden');
        if (brightG) brightG.classList.add('hidden');
        if (brightDesc) brightDesc.classList.remove('hidden');
        showToast("View Mode", "Switched to Normal Text & Bar view.");
      }
      lucide.createIcons();
    }

    document.addEventListener("DOMContentLoaded", () => {
      lucide.createIcons();
      initGauges();
      fetchStatus();
      setInterval(fetchStatus, 3000);
    });

    function switchTab(tabId) {
      const tabs = ['controls', 'vitals', 'logs'];
      tabs.forEach(t => {
        const view = document.getElementById(`view-${t}`);
        const btn = document.getElementById(`tab-${t}`);
        if (view && btn) {
          if (t === tabId) {
            view.classList.remove('hidden');
            btn.className = "inline-flex items-center justify-center whitespace-nowrap px-4 py-1.5 text-xs font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 bg-background text-foreground shadow-sm";
          } else {
            view.classList.add('hidden');
            btn.className = "inline-flex items-center justify-center whitespace-nowrap px-4 py-1.5 text-xs font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 hover:text-foreground";
          }
        }
      });
      lucide.createIcons();
    }

    function showToast(title, description, isError = false, action = null) {
      const container = document.getElementById("toast-container");
      const toast = document.createElement("div");
      toast.className = `pointer-events-auto flex w-80 items-start justify-between space-x-2 border ${isError ? 'border-destructive bg-destructive/10 text-destructive-foreground' : 'border-border bg-card text-card-foreground'} p-3.5 shadow-lg animate-toast`;
      let actionHtml = "";
      if (action && action.path) {
        actionHtml = `
          <button onclick="openFolder('${action.path}')" class="ml-3 inline-flex items-center border border-border bg-background hover:bg-accent px-2 py-1 text-[11px] font-mono transition-colors">
            <i data-lucide="folder-open" class="w-3.5 h-3.5 mr-1"></i> Open Folder
          </button>
        `;
      }
      toast.innerHTML = `
        <div class="flex-1">
          <div class="text-xs font-semibold leading-none">${title}</div>
          <div class="text-[11px] text-muted-foreground mt-1">${description}</div>
        </div>
        ${actionHtml}
      `;
      container.appendChild(toast);
      if (action && action.path) {
        lucide.createIcons();
      }
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.2s ease';
        setTimeout(() => toast.remove(), 250);
      }, 5000);
    }

    function openFolder(path) {
      fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "open_folder", path: path })
      });
    }

    function showActionToast(description, isError = false) {
      showToast("System Action", description, isError);
    }

    async function fetchStatus() {
      try {
        const res = await fetch("/api/status");
        if (!res.ok) return;
        const data = await res.json();

        if (data.telemetry) {
          const t = data.telemetry;
          document.getElementById("nav-uptime-status").innerText = t.uptime ? `Up ${t.uptime}` : "Online";

          // GPU
          if (t.gpu && t.gpu.available) {
            document.getElementById("nav-gpu-badge").innerHTML = `<i data-lucide="cpu" class="h-3 w-3"></i><span>RTX 4070 (${t.gpu.utilization_pct}%)</span>`;
            document.getElementById("stat-gpu-vram").innerText = `VRAM: ${(t.gpu.vram_used_mb/1024).toFixed(1)}/8.2 GB`;
            document.getElementById("detail-gpu-util").innerText = `${t.gpu.utilization_pct}%`;
            document.getElementById("detail-gpu-vram").innerText = `${t.gpu.vram_used_mb} MB`;
            document.getElementById("detail-gpu-temp").innerText = `${t.gpu.temp_c}°C`;
            document.getElementById("detail-gpu-power").innerText = `${t.gpu.power_w} W`;

            // Text View Sync
            const elTxtGpuTemp = document.getElementById("text-gpu-temp");
            if (elTxtGpuTemp) elTxtGpuTemp.innerText = `${t.gpu.temp_c}°C`;
            const elTxtGpuVram = document.getElementById("text-gpu-vram");
            if (elTxtGpuVram) elTxtGpuVram.innerText = `VRAM: ${(t.gpu.vram_used_mb/1024).toFixed(1)}/8.2 GB`;
            const elTxtGpuBar = document.getElementById("text-gpu-bar");
            const vramPct = (t.gpu.vram_used_mb / t.gpu.vram_total_mb) * 100;
            if (elTxtGpuBar) elTxtGpuBar.style.width = `${vramPct}%`;

            const elDetGpuUtil = document.getElementById("text-detail-gpu-util");
            if (elDetGpuUtil) elDetGpuUtil.innerText = `${t.gpu.utilization_pct}%`;
            const elDetGpuBar = document.getElementById("text-bar-gpu-util");
            if (elDetGpuBar) elDetGpuBar.style.width = `${t.gpu.utilization_pct}%`;
            const elDetGpuVram = document.getElementById("text-detail-gpu-vram");
            if (elDetGpuVram) elDetGpuVram.innerText = `${t.gpu.vram_used_mb} MB`;
            const elDetVramBar = document.getElementById("text-bar-gpu-vram");
            if (elDetVramBar) elDetVramBar.style.width = `${vramPct}%`;
            const elDetGpuTemp = document.getElementById("text-detail-gpu-temp");
            if (elDetGpuTemp) elDetGpuTemp.innerText = `${t.gpu.temp_c}°C`;
            const elDetGpuPwr = document.getElementById("text-detail-gpu-power");
            if (elDetGpuPwr) elDetGpuPwr.innerText = `${t.gpu.power_w} W`;

            if (gauges.statGpu) gauges.statGpu.setValue(t.gpu.temp_c);
            if (gauges.vitalGpu) gauges.vitalGpu.setValue(t.gpu.temp_c, vramPct);
          }

          // CPU
          if (t.cpu_temp_c) {
            document.getElementById("stat-cpu-temp").innerText = `Package: ${t.cpu_temp_c}°C`;
            document.getElementById("detail-cpu-temp").innerText = `${t.cpu_temp_c}°C`;
            const elTxtCpuTemp = document.getElementById("text-cpu-temp");
            if (elTxtCpuTemp) elTxtCpuTemp.innerText = `Package: ${t.cpu_temp_c}°C`;
            const elDetCpuTemp = document.getElementById("text-detail-cpu-temp");
            if (elDetCpuTemp) elDetCpuTemp.innerText = `${t.cpu_temp_c}°C`;
          }
          document.getElementById("detail-cpu-load").innerText = `${t.cpu_percent}%`;
          const elTxtCpuLoad = document.getElementById("text-cpu-load");
          if (elTxtCpuLoad) elTxtCpuLoad.innerText = `${t.cpu_percent}%`;
          const elTxtCpuBar = document.getElementById("text-cpu-bar");
          if (elTxtCpuBar) elTxtCpuBar.style.width = `${t.cpu_percent}%`;
          const elDetCpuLoad = document.getElementById("text-detail-cpu-load");
          if (elDetCpuLoad) elDetCpuLoad.innerText = `${t.cpu_percent}%`;
          const elDetCpuBar = document.getElementById("text-bar-cpu-load");
          if (elDetCpuBar) elDetCpuBar.style.width = `${t.cpu_percent}%`;

          if (gauges.statCpu) gauges.statCpu.setValue(t.cpu_percent);
          if (gauges.vitalCpu) gauges.vitalCpu.setValue(t.cpu_percent, t.cpu_temp_c || 50);

          // RAM
          document.getElementById("stat-ram-gb").innerText = `${t.ram_used_gb} / ${t.ram_total_gb} GB`;
          document.getElementById("detail-ram-used").innerText = `${t.ram_used_gb} GB`;
          const elTxtRamPct = document.getElementById("text-ram-pct");
          if (elTxtRamPct) elTxtRamPct.innerText = `${t.ram_percent}%`;
          const elTxtRamGb = document.getElementById("text-ram-gb");
          if (elTxtRamGb) elTxtRamGb.innerText = `${t.ram_used_gb} / ${t.ram_total_gb} GB`;
          const elTxtRamBar = document.getElementById("text-ram-bar");
          if (elTxtRamBar) elTxtRamBar.style.width = `${t.ram_percent}%`;
          const elDetRamUsed = document.getElementById("text-detail-ram-used");
          if (elDetRamUsed) elDetRamUsed.innerText = `${t.ram_used_gb} GB`;
          const elDetRamBar = document.getElementById("text-bar-ram-used");
          if (elDetRamBar) elDetRamBar.style.width = `${t.ram_percent}%`;

          if (gauges.statRam) gauges.statRam.setValue(t.ram_percent);

          // Storage & Battery
          document.getElementById("stat-disk-gb").innerText = `${t.disk_used_gb} / ${t.disk_total_gb} GB`;
          document.getElementById("detail-disk-used").innerText = `${t.disk_used_gb} GB`;
          const elTxtDiskPct = document.getElementById("text-disk-pct");
          if (elTxtDiskPct) elTxtDiskPct.innerText = `${t.disk_percent}%`;
          const elTxtDiskGb = document.getElementById("text-disk-gb");
          if (elTxtDiskGb) elTxtDiskGb.innerText = `${t.disk_used_gb} / ${t.disk_total_gb} GB`;
          const elTxtDiskBar = document.getElementById("text-disk-bar");
          if (elTxtDiskBar) elTxtDiskBar.style.width = `${t.disk_percent}%`;
          const elDetDiskUsed = document.getElementById("text-detail-disk-used");
          if (elDetDiskUsed) elDetDiskUsed.innerText = `${t.disk_used_gb} GB`;
          const elDetDiskBar = document.getElementById("text-bar-disk-used");
          if (elDetDiskBar) elDetDiskBar.style.width = `${t.disk_percent}%`;

          const batPct = t.battery ? t.battery.percent : 100;
          const elTxtBatPct = document.getElementById("text-bat-pct");
          if (elTxtBatPct) elTxtBatPct.innerText = `${batPct}%`;
          const elTxtBatBar = document.getElementById("text-bat-bar");
          if (elTxtBatBar) elTxtBatBar.style.width = `${batPct}%`;

          if (gauges.statDisk) gauges.statDisk.setValue(t.disk_percent);
          if (gauges.statBat) gauges.statBat.setValue(batPct);
          if (gauges.vitalDisk) gauges.vitalDisk.setValue(t.disk_percent, batPct);

          // Brightness
          if (t.brightness) {
            document.getElementById("brightness-pct-label").innerText = `${t.brightness.brightness}%`;
            document.getElementById("brightness-sub-label").innerText = `${t.brightness.brightness}%`;
            document.getElementById("brightness-slider").value = t.brightness.brightness;
            const elTxtBrightPct = document.getElementById("text-bright-pct");
            if (elTxtBrightPct) elTxtBrightPct.innerText = `${t.brightness.brightness}%`;
            const elTxtBrightBar = document.getElementById("text-bright-bar");
            if (elTxtBrightBar) elTxtBrightBar.style.width = `${t.brightness.brightness}%`;

            if (gauges.statBright) gauges.statBright.setValue(t.brightness.brightness);
            if (gauges.ctrlBright) gauges.ctrlBright.setValue(t.brightness.brightness);
          }

          // Display Resolution
          if (t.display) {
            const curRes = t.display.current_resolution || "";
            const curHz = t.display.current_refresh ? ` @ ${Math.round(t.display.current_refresh)}Hz` : "";
            const resBadge = document.getElementById("resolution-current-badge");
            if (resBadge) resBadge.innerText = `${curRes}${curHz}`;

            const resSelect = document.getElementById("resolution-select");
            if (resSelect && t.display.resolutions && t.display.resolutions.length > 0) {
              if (resSelect.dataset.populated !== "true") {
                resSelect.innerHTML = "";
                t.display.resolutions.forEach(r => {
                  const opt = document.createElement("option");
                  opt.value = r;
                  opt.textContent = `${r}${r === curRes ? ' (Active)' : ''}`;
                  resSelect.appendChild(opt);
                });
                resSelect.dataset.populated = "true";
              }
              if (document.activeElement !== resSelect) {
                resSelect.value = curRes;
              }
            }

            // Display Orientation
            const curOrient = t.display.orientation || "normal";
            const orientBadge = document.getElementById("orientation-current-badge");
            if (orientBadge) orientBadge.innerText = curOrient;
            ["normal", "right", "inverted", "left"].forEach(o => {
              const b = document.getElementById(`orient-btn-${o}`);
              if (b) {
                if (curOrient.startsWith(o)) {
                  b.className = "border border-primary bg-primary text-primary-foreground py-1 px-1 text-center font-bold transition-colors";
                } else {
                  b.className = "border border-border bg-background hover:bg-accent py-1 px-1 text-center transition-colors";
                }
              }
            });
          }

          // Night Light
          document.getElementById("stat-night-light").innerText = t.night_light ? "Night Light: ON" : "Night Light: OFF";
          const elTxtNight = document.getElementById("text-night-light");
          if (elTxtNight) elTxtNight.innerText = t.night_light ? "Night Light: ON" : "Night Light: OFF";

          const nlBtn = document.getElementById("night-light-btn");
          if (t.night_light) {
            nlBtn.className = "inline-flex flex-col items-center justify-center border border-amber-500/40 bg-amber-500/10 text-amber-300 py-2 text-xs transition-colors";
          } else {
            nlBtn.className = "inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors";
          }

          // System Theme (Dark / Light Mode)
          const isDark = t.color_scheme === "dark";
          const themeBtn = document.getElementById("theme-mode-btn");
          const themeLbl = document.getElementById("theme-btn-label");
          const navThemeBtn = document.getElementById("nav-theme-toggle");
          if (themeLbl) themeLbl.innerText = isDark ? "Dark" : "Light";
          if (themeBtn) {
            if (isDark) {
              themeBtn.className = "inline-flex flex-col items-center justify-center border border-purple-500/40 bg-purple-500/10 text-purple-300 py-2 text-xs transition-colors";
            } else {
              themeBtn.className = "inline-flex flex-col items-center justify-center border border-amber-500/40 bg-amber-500/10 text-amber-300 py-2 text-xs transition-colors";
            }
          }
          if (navThemeBtn) {
            navThemeBtn.title = `Current Theme: ${isDark ? 'Dark' : 'Light'} (Click to toggle)`;
          }

          // Keyboard Backlight Telemetry Sync
          if (t.keyboard_backlight) {
            const kb = t.keyboard_backlight;
            const overlay = document.getElementById("kbd-setup-overlay");
            const kbBadge = document.getElementById("kbd-backlight-badge");

            if (!kb.supported) {
              if (overlay) overlay.classList.remove("hidden");
              if (kbBadge) {
                kbBadge.innerText = "Setup Required";
                kbBadge.className = "inline-flex items-center border border-amber-500/40 bg-amber-500/10 text-amber-400 px-2 py-0.5 text-xs font-mono font-medium cursor-pointer";
                kbBadge.title = "Click to view instructions to enable hardware control";
                kbBadge.onclick = openKbdSetupModal;
              }
            } else {
              if (overlay) overlay.classList.add("hidden");
              if (kbBadge) {
                kbBadge.innerText = (kb.enabled && kb.brightness > 0) ? `${kb.brightness}% (${kb.mode || 'Active'})` : "Off";
                kbBadge.className = "inline-flex items-center border border-border bg-secondary px-2 py-0.5 text-xs font-mono font-medium";
                kbBadge.title = "";
                kbBadge.onclick = null;
              }
              const kbSub = document.getElementById("kbd-sub-label");
              if (kbSub) kbSub.innerText = `${kb.brightness}%`;
              const kbSlider = document.getElementById("kbd-brightness-slider");
              if (kbSlider && document.activeElement !== kbSlider) {
                kbSlider.value = kb.brightness;
              }
              const kbPowerBtn = document.getElementById("kbd-power-btn");
              if (kbPowerBtn) {
                if (kb.enabled && kb.brightness > 0) {
                  kbPowerBtn.className = "inline-flex flex-col items-center justify-center border border-primary bg-primary text-primary-foreground py-2 text-xs transition-colors";
                } else {
                  kbPowerBtn.className = "inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors";
                }
              }
              ["wave", "breathe", "neon", "zoom", "static"].forEach(m => {
                const mb = document.getElementById(`kbd-mode-${m}`);
                if (mb) {
                  if (kb.mode === m) {
                    mb.className = "border border-primary bg-primary text-primary-foreground py-1 px-1 text-center font-bold text-[10px] font-mono transition-colors";
                  } else {
                    mb.className = "border border-border bg-background hover:bg-accent py-1 px-1 text-center text-[10px] font-mono transition-colors";
                  }
                }
              });
            }
          }

          // Touchpad & Pointer Telemetry Sync
          if (t.touchpad) {
            const tp = t.touchpad;
            const badge = document.getElementById("touchpad-status-badge");
            if (badge) {
              badge.innerText = tp.enabled ? "Active" : "Disabled";
              badge.className = tp.enabled
                ? "inline-flex items-center border border-emerald-500/40 bg-emerald-500/10 text-emerald-400 px-2 py-0.5 text-xs font-mono font-medium"
                : "inline-flex items-center border border-amber-500/40 bg-amber-500/10 text-amber-400 px-2 py-0.5 text-xs font-mono font-medium";
            }
            const speedSlider = document.getElementById("touchpad-speed-slider");
            if (speedSlider && document.activeElement !== speedSlider) {
              speedSlider.value = tp.speed_percent;
            }
            const speedLabel = document.getElementById("touchpad-speed-label");
            if (speedLabel) speedLabel.innerText = `${tp.speed_percent}%`;

            const tapBtn = document.getElementById("touchpad-tap-btn");
            if (tapBtn) {
              tapBtn.innerText = tp.tap_to_click ? "ON" : "OFF";
              tapBtn.className = tp.tap_to_click
                ? "border border-primary bg-primary text-primary-foreground px-2.5 py-1 text-[11px] font-mono font-bold transition-colors"
                : "border border-border bg-background hover:bg-accent text-foreground px-2.5 py-1 text-[11px] font-mono transition-colors";
            }

            const scrollBtn = document.getElementById("touchpad-scroll-btn");
            if (scrollBtn) {
              scrollBtn.innerText = tp.natural_scroll ? "ON" : "OFF";
              scrollBtn.className = tp.natural_scroll
                ? "border border-primary bg-primary text-primary-foreground px-2.5 py-1 text-[11px] font-mono font-bold transition-colors"
                : "border border-border bg-background hover:bg-accent text-foreground px-2.5 py-1 text-[11px] font-mono transition-colors";
            }

            const powerBtn = document.getElementById("touchpad-power-btn");
            if (powerBtn) {
              powerBtn.className = tp.enabled
                ? "inline-flex flex-col items-center justify-center border border-primary bg-primary text-primary-foreground py-2 text-xs transition-colors"
                : "inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors";
            }
          }

          // Screen Studio Sync (Recording & Sharing)
          if (t.screen_recording) {
            const rBadge = document.getElementById("recording-status-badge");
            const rBtn = document.getElementById("recording-toggle-btn");
            const rText = document.getElementById("record-btn-text");
            if (t.screen_recording.active) {
              if (rBadge) {
                rBadge.innerText = `REC ${t.screen_recording.elapsed_seconds}s`;
                rBadge.className = "inline-flex items-center border border-rose-500/40 bg-rose-500/10 text-rose-400 px-2 py-0.5 text-xs font-mono font-medium animate-pulse";
              }
              if (rBtn) { rBtn.innerText = "Stop Record"; rBtn.className = "border border-rose-500 bg-rose-500 text-white px-2.5 py-1 text-xs font-mono"; }
              if (rText) rText.innerText = "Stop Recording";
            } else {
              if (rBadge) {
                rBadge.innerText = "Idle";
                rBadge.className = "inline-flex items-center border border-border bg-secondary px-2 py-0.5 text-xs font-mono font-medium";
              }
              if (rBtn) { rBtn.innerText = "Start Record"; rBtn.className = "border border-border bg-background hover:bg-accent px-2.5 py-1 text-xs font-mono transition-colors"; }
              if (rText) rText.innerText = "Record Screen";
            }
          }

          if (t.screen_sharing) {
            const sBtn = document.getElementById("sharing-toggle-btn");
            if (sBtn) {
              sBtn.innerText = t.screen_sharing.active ? "ENABLED" : "DISABLED";
              sBtn.className = t.screen_sharing.active
                ? "border border-primary bg-primary text-primary-foreground px-2.5 py-1 text-xs font-mono font-bold transition-colors"
                : "border border-border bg-background hover:bg-accent px-2.5 py-1 text-xs font-mono transition-colors";
            }
          }

          // Monitors & Blanking Sync
          if (t.monitors) {
            const mBadge = document.getElementById("monitors-count-badge");
            if (mBadge) mBadge.innerText = `${t.monitors.count} Display${t.monitors.count > 1 ? 's' : ''}`;
          }

          if (t.blanking) {
            const bLbl = document.getElementById("blanking-label");
            if (bLbl) bLbl.innerText = t.blanking.label;
          }

          // Power Profile
          if (t.power_profile) {
            document.getElementById("stat-power-profile").innerText = t.power_profile;
            document.getElementById("power-profile-pill").innerText = t.power_profile;
            document.getElementById("detail-governor").innerText = t.power_profile;
            const elTxtPwr = document.getElementById("text-power-profile");
            if (elTxtPwr) elTxtPwr.innerText = t.power_profile;
            const elDetGov = document.getElementById("text-detail-governor");
            if (elDetGov) elDetGov.innerText = t.power_profile;

            updatePowerProfileButtons(t.power_profile);
          }

          // Mic
          if (t.mic) {
            document.getElementById("mic-pct-label").innerText = `${t.mic.volume}%`;
            document.getElementById("mic-slider").value = t.mic.volume;
            if (gauges.ctrlMic) gauges.ctrlMic.setValue(t.mic.volume);
            const micBtn = document.getElementById("mic-mute-btn");
            if (t.mic.muted) {
              micBtn.className = "inline-flex flex-col items-center justify-center border border-destructive bg-destructive/10 text-destructive-foreground py-2 text-xs transition-colors";
            } else {
              micBtn.className = "inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors";
            }
          }

          // DND
          const dndLbl = document.getElementById("dnd-label");
          const dndBtn = document.getElementById("dnd-btn");
          if (t.dnd) {
            dndLbl.innerText = "DND: ON";
            dndBtn.className = "inline-flex items-center justify-center border border-primary bg-primary text-primary-foreground py-2 text-xs font-medium gap-1.5 transition-colors";
          } else {
            dndLbl.innerText = "DND: OFF";
            dndBtn.className = "inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs font-medium gap-1.5 transition-colors";
          }

          // Network & Uptime
          if (t.ip) document.getElementById("detail-ip-badge").innerText = t.ip;
          if (t.wifi) document.getElementById("detail-wifi-ssid").innerText = t.wifi.ssid || "Wi-Fi";
          if (t.bluetooth) document.getElementById("detail-bt-status").innerText = t.bluetooth.enabled ? "On" : "Off";
          if (t.uptime) document.getElementById("detail-uptime").innerText = `Session Uptime: ${t.uptime}`;
        }

        // Volume
        if (data.volume) {
          document.getElementById("volume-pct-label").innerText = data.volume.volume + "%";
          document.getElementById("vol-sub-label").innerText = data.volume.volume + "%";
          document.getElementById("vol-slider").value = data.volume.volume;
          if (gauges.ctrlVol) gauges.ctrlVol.setValue(data.volume.volume);
          const muteBtn = document.getElementById("mute-btn");
          if (data.volume.muted) {
            muteBtn.className = "inline-flex flex-col items-center justify-center border border-destructive bg-destructive/10 text-destructive-foreground py-2 text-xs transition-colors";
          } else {
            muteBtn.className = "inline-flex flex-col items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-2 text-xs transition-colors";
          }
        }

        // Wake State
        isWakeEnabled = !!data.wake_listening;
        updateWakeUI(isWakeEnabled);

        // Activity Feed
        if (data.recent_events) renderEvents(data.recent_events);

        lucide.createIcons();
      } catch (err) {
        console.warn("Status error:", err);
      }
    }

    function updatePowerProfileButtons(prof) {
      ["p-perf", "p-bal", "p-save"].forEach(id => {
        document.getElementById(id).className = "inline-flex items-center justify-center border border-border bg-background hover:bg-accent text-foreground py-1 text-xs font-mono transition-colors";
      });
      if (prof === "performance") {
        document.getElementById("p-perf").className = "inline-flex items-center justify-center border border-primary bg-primary text-primary-foreground py-1 text-xs font-mono font-medium transition-colors";
      } else if (prof === "balanced") {
        document.getElementById("p-bal").className = "inline-flex items-center justify-center border border-primary bg-primary text-primary-foreground py-1 text-xs font-mono font-medium transition-colors";
      } else {
        document.getElementById("p-save").className = "inline-flex items-center justify-center border border-primary bg-primary text-primary-foreground py-1 text-xs font-mono font-medium transition-colors";
      }
    }

    async function submitTextCommand(e) {
      if (e) e.preventDefault();
      const input = document.getElementById("command-input");
      if (!input) return;
      const cmd = input.value.trim();
      if (!cmd) return;
      input.value = "";
      await executeCommand(cmd);
    }

    function runPreset(cmd) {
      executeCommand(cmd);
    }

    async function executeCommand(cmd) {
      const decRaw = document.getElementById("decision-raw");
      if (decRaw) decRaw.innerText = `"${cmd}"`;
      const spinnerEl = document.getElementById("agent-flicker-spinner");
      if (spinnerEl) spinnerEl.innerHTML = FlickerDot.render({ size: 18, variant: "5x5" });
      const stateLbl = document.getElementById("agent-state-label");
      if (stateLbl) stateLbl.innerText = "Routing with Laya Decision Engine...";
      const badge = document.getElementById("decision-latency-badge");
      if (badge) badge.innerHTML = FlickerDot.render({ size: 16, variant: "5x5" }) + ` <span class="text-xs font-mono text-muted-foreground ml-1.5">Routing...</span>`;

      try {
        const res = await fetch("/api/command", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ command: cmd, tts: useTTS })
        });
        const data = await res.json();
        handleCommandResult(data);
      } catch (err) {
        showToast("Command Execution Error", err.toString(), true);
      } finally {
        if (spinnerEl) spinnerEl.innerHTML = "";
        if (stateLbl) stateLbl.innerText = "Ready for voice commands";
      }
    }

    function handleCommandResult(data) {
      if (!data) return;
      if (data.decision) {
        const decAct = document.getElementById("decision-action");
        if (decAct) decAct.innerText = data.decision.action || "-";
        const decTgt = document.getElementById("decision-target");
        if (decTgt) decTgt.innerText = data.decision.target || "-";
      }
      if (data.latency_ms) {
        const badge = document.getElementById("decision-latency-badge");
        if (badge) badge.innerHTML = `Latency: <span class="text-emerald-400 font-semibold ml-1">${data.latency_ms}ms</span>`;
      }
      const decTime = document.getElementById("decision-time");
      if (decTime) decTime.innerText = new Date().toLocaleTimeString();
      const decStat = document.getElementById("decision-status");
      if (decStat) decStat.innerText = data.success ? "Success" : "Failed";

      const fb = document.getElementById("feedback-bubble");
      const fbTxt = document.getElementById("feedback-text");
      if (data.feedback) {
        if (fbTxt) fbTxt.innerText = data.feedback;
        if (fb) fb.classList.remove("hidden");
        // Pass file_path to toast for "Open Folder" action
        if (data.file_path) {
          showToast("Command Executed", data.feedback, false, { path: data.file_path });
        } else {
          showToast("Command Executed", data.feedback);
        }
      }
      fetchStatus();
    }

    async function triggerAction(act) {
      const res = await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: act })
      });
      const data = await res.json();
      handleCommandResult(data);
    }

    function updateVolLabel(val) {
      document.getElementById("volume-pct-label").innerText = val + "%";
      document.getElementById("vol-sub-label").innerText = val + "%";
      if (gauges.ctrlVol) gauges.ctrlVol.setValue(val);
    }

    async function setVolumeLevel(val) {
      await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "set_volume", volume_level: parseInt(val) })
      });
      fetchStatus();
    }

    function updateMicLabel(val) {
      document.getElementById("mic-pct-label").innerText = val + "%";
      if (gauges.ctrlMic) gauges.ctrlMic.setValue(val);
    }

    async function setMicVolumeLevel(val) {
      await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "set_mic_volume", mic_level: parseInt(val) })
      });
      fetchStatus();
    }

    function updateBrightnessLabel(val) {
      document.getElementById("brightness-pct-label").innerText = val + "%";
      document.getElementById("brightness-sub-label").innerText = val + "%";
      if (gauges.statBright) gauges.statBright.setValue(val);
      if (gauges.ctrlBright) gauges.ctrlBright.setValue(val);
    }

    async function setBrightnessLevel(val) {
      await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "set_brightness", brightness_level: parseInt(val) })
      });
      fetchStatus();
    }

    function updateKbdBacklightLabel(val) {
      const el = document.getElementById("kbd-sub-label");
      if (el) el.innerText = val + "%";
      const b = document.getElementById("kbd-backlight-badge");
      if (b) b.innerText = val + "%";
    }

    function updateTouchpadSpeedLabel(val) {
      const lbl = document.getElementById("touchpad-speed-label");
      if (lbl) lbl.innerText = val + "%";
    }

    async function setTouchpadSpeed(val) {
      updateTouchpadSpeedLabel(val);
      try {
        const res = await fetch("/api/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "set_touchpad_speed", speed_percent: parseInt(val) })
        });
        const data = await res.json();
        if (data.feedback) showActionToast(data.feedback);
        fetchStatus();
      } catch (e) {
        console.error("setTouchpadSpeed error:", e);
      }
    }

    async function setBlanking(secs) {
      try {
        const res = await fetch("/api/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "set_screen_blanking", seconds: parseInt(secs) })
        });
        const data = await res.json();
        if (data.feedback) showActionToast(data.feedback);
        fetchStatus();
      } catch (e) {
        console.error("setBlanking error:", e);
      }
    }

    async function copySampleText() {
      try {
        const res = await fetch("/api/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "clipboard_copy", text: "Hello from Voice Agent System Controller!" })
        });
        const data = await res.json();
        if (data.feedback) showActionToast(data.feedback);
      } catch (e) {
        console.error("copySampleText error:", e);
      }
    }

    async function setKbdBacklightLevel(val) {
      try {
        await fetch("/api/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "set_kbd_backlight", brightness_level: parseInt(val) })
        });
        fetchStatus();
      } catch (e) {
        console.error("setKbdBacklightLevel error:", e);
      }
    }

    async function setKbdColor(hex) {
      try {
        const res = await fetch("/api/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "set_kbd_color", color: hex })
        });
        const data = await res.json();
        if (data.feedback) showActionToast(data.feedback);
        fetchStatus();
      } catch (e) {
        console.error("setKbdColor error:", e);
      }
    }

    async function setKbdMode(mode) {
      try {
        const res = await fetch("/api/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "set_kbd_mode", mode: mode })
        });
        const data = await res.json();
        if (data.feedback) showActionToast(data.feedback);
        fetchStatus();
      } catch (e) {
        console.error("setKbdMode error:", e);
      }
    }

    function openKbdSetupModal() {
      const m = document.getElementById("kbd-setup-modal");
      if (m) {
        m.classList.remove("hidden");
        lucide.createIcons();
      }
    }

    function closeKbdSetupModal() {
      const m = document.getElementById("kbd-setup-modal");
      if (m) m.classList.add("hidden");
    }

    async function copyMokCommand() {
      const cmd = "sudo mokutil --import /var/lib/shim-signed/mok/MOK.der";
      try {
        await navigator.clipboard.writeText(cmd);
        const btn = document.getElementById("copy-btn-text");
        if (btn) btn.innerText = "Copied!";
        showToast("Clipboard", "Command copied to clipboard");
        setTimeout(() => {
          if (btn) btn.innerText = "Copy";
        }, 2000);
      } catch (err) {
        showToast("Copy command:", cmd);
      }
    }

    async function checkAndRefreshStatus() {
      const btn = document.getElementById("modal-refresh-btn");
      if (btn) btn.innerHTML = '<i data-lucide="loader" class="w-3.5 h-3.5 animate-spin"></i><span>Checking...</span>';
      try {
        const res = await fetch("/api/status");
        const data = await res.json();
        if (data.telemetry && data.telemetry.keyboard_backlight) {
          const kb = data.telemetry.keyboard_backlight;
          if (kb.supported) {
            closeKbdSetupModal();
            showToast("Hardware Enabled", "Keyboard backlight hardware is active and ready!", false);
          } else {
            showToast("Setup Incomplete", "Secure Boot MOK is not enrolled yet. Please run the command and reboot once.", true);
          }
        }
      } catch (e) {
        console.error("checkAndRefreshStatus error:", e);
      } finally {
        setTimeout(() => {
          if (btn) btn.innerHTML = '<i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i><span>Check Status</span>';
          lucide.createIcons();
          fetchStatus();
        }, 500);
      }
    }

    window.addEventListener("click", (e) => {
      const modal = document.getElementById("kbd-setup-modal");
      if (modal && e.target === modal) {
        closeKbdSetupModal();
      }
    });

    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeKbdSetupModal();
    });

    async function applyResolution(val) {
      if (!val) return;
      try {
        const res = await fetch("/api/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "set_resolution", resolution: val })
        });
        const data = await res.json();
        if (data.feedback) {
          showActionToast(`Resolution: ${data.feedback}`);
        }
        setTimeout(fetchStatus, 500);
      } catch (e) {
        console.error("Resolution apply error:", e);
      }
    }

    async function applyOrientation(val) {
      if (!val) return;
      try {
        const res = await fetch("/api/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "set_orientation", orientation: val })
        });
        const data = await res.json();
        if (data.feedback) {
          showToast("Display Orientation", data.feedback);
        }
        setTimeout(fetchStatus, 500);
      } catch (e) {
        console.error("Orientation apply error:", e);
      }
    }

    async function setPowerProfile(prof) {
      await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "set_power_profile", profile: prof })
      });
      fetchStatus();
    }

    function renderEvents(events) {
      const container = document.getElementById("activity-feed");
      if (!events || events.length === 0) return;

      let html = "";
      events.forEach(item => {
        html += `
          <div class="flex items-start justify-between border border-border bg-card p-3 shadow-sm text-xs">
            <div class="flex items-start gap-2.5 min-w-0">
              <span class="inline-flex h-6 w-6 items-center justify-center border border-border bg-secondary shrink-0 mt-0.5">
                <i data-lucide="${item.type === 'voice_command' ? 'mic' : item.type === 'executed' ? 'check' : 'activity'}" class="w-3.5 h-3.5 text-foreground"></i>
              </span>
              <div class="min-w-0">
                <div class="font-medium text-foreground truncate">${item.message}</div>
                ${item.meta && item.meta.decision ? `
                  <div class="flex items-center gap-2 mt-0.5 text-[10px] font-mono text-muted-foreground">
                    <span>${item.meta.decision.action} &bull; ${item.meta.decision.target}</span>
                    ${item.meta.latency_ms ? `<span class="text-emerald-400 font-semibold">${item.meta.latency_ms}ms</span>` : ''}
                  </div>
                ` : ''}
              </div>
            </div>
            <span class="text-[10px] font-mono text-muted-foreground ml-3 shrink-0">${item.timestamp}</span>
          </div>
        `;
      });
      container.innerHTML = html;
      lucide.createIcons();
    }

    function clearHistory() {
      fetch("/api/history/clear", { method: "POST" });
      document.getElementById("activity-feed").innerHTML = '<div class="text-center py-12 text-muted-foreground font-mono text-xs">Logs cleared.</div>';
      showToast("Activity Logs", "Logs cleared successfully.");
    }
  </script>
</body>
</html>
"""

class VoiceAgentHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_str, status=200):
        body = html_str.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._send_html(SHADCN_HTML_PAGE)
            return

        elif path == "/api/status":
            agent = get_agent()
            vol = agent.system.get_volume_info()
            telemetry = agent.system.get_system_telemetry()
            media = agent.system.get_media_info()

            with state_lock:
                events = list(history_log)[:20]

            self._send_json({
                "status": "online",
                "volume": vol,
                "telemetry": telemetry,
                "media": media,
                "recent_events": events
            })
            return

        elif path == "/api/history":
            with state_lock:
                events = list(history_log)
            self._send_json({"events": events})
            return

        else:
            self.send_error(404, "Endpoint Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body_data = self.rfile.read(length) if length > 0 else b"{}"

        try:
            payload = json.loads(body_data.decode("utf-8")) if body_data else {}
        except Exception:
            payload = {}

        agent = get_agent()

        if path == "/api/command":
            cmd = payload.get("command", "")
            use_tts = payload.get("tts", True)
            if not cmd:
                self._send_json({"success": False, "feedback": "Empty command"}, 400)
                return

            start_t = time.time()
            decision = agent.decision_engine.decide(cmd)
            success, feedback = agent.system.execute_decision(decision)
            latency = (time.time() - start_t) * 1000

            record_event("command", cmd, {
                "decision": decision,
                "latency_ms": round(latency, 1),
                "success": success
            })
            record_event("executed", feedback, {
                "latency_ms": round(latency, 1),
                "success": success
            })

            self._send_json({
                "success": success,
                "feedback": feedback,
                "decision": decision,
                "latency_ms": round(latency, 1)
            })
            return

        elif path == "/api/action":
            act = payload.get("action", "")
            vol_lvl = payload.get("volume_level")
            mic_lvl = payload.get("mic_level")
            bright_lvl = payload.get("brightness_level")
            profile = payload.get("profile")
            resolution_val = payload.get("resolution")
            orientation_val = payload.get("orientation")
            color_val = payload.get("color")
            mode_val = payload.get("mode")

            start_t = time.time()
            if act == "set_volume" and vol_lvl is not None:
                success, feedback = agent.system.set_volume_percent(vol_lvl)
                decision = {"action": "volume_control", "target": f"set_{vol_lvl}%"}
            elif act == "set_mic_volume" and mic_lvl is not None:
                success, feedback = agent.system.set_mic_volume_percent(mic_lvl)
                decision = {"action": "mic_control", "target": f"set_{mic_lvl}%"}
            elif act == "set_brightness" and bright_lvl is not None:
                success, feedback = agent.system.set_brightness_percent(bright_lvl)
                decision = {"action": "display_control", "target": f"set_{bright_lvl}%"}
            elif act == "set_kbd_backlight" and bright_lvl is not None:
                success, feedback = agent.system.set_keyboard_backlight_percent(bright_lvl)
                decision = {"action": "keyboard_backlight_control", "target": f"kbd_backlight_set_{bright_lvl}%"}
            elif act == "set_kbd_color" and color_val:
                success, feedback = agent.system.set_keyboard_backlight_color(color_val)
                decision = {"action": "keyboard_backlight_control", "target": "kbd_backlight_color", "color": color_val}
            elif act == "set_kbd_mode" and mode_val:
                success, feedback = agent.system.set_keyboard_backlight_mode(mode_val)
                decision = {"action": "keyboard_backlight_control", "target": "kbd_backlight_mode", "mode": mode_val}
            elif act == "kbd_backlight_toggle":
                success, feedback = agent.system.set_keyboard_backlight_toggle()
                decision = {"action": "keyboard_backlight_control", "target": "kbd_backlight_toggle"}
            elif act == "kbd_backlight_up":
                success, feedback = agent.system.step_keyboard_backlight("up", 20)
                decision = {"action": "keyboard_backlight_control", "target": "kbd_backlight_up"}
            elif act == "kbd_backlight_down":
                success, feedback = agent.system.step_keyboard_backlight("down", 20)
                decision = {"action": "keyboard_backlight_control", "target": "kbd_backlight_down"}
            elif act == "kbd_backlight_on":
                success, feedback = agent.system.set_keyboard_backlight_percent(100)
                decision = {"action": "keyboard_backlight_control", "target": "kbd_backlight_on"}
            elif act == "kbd_backlight_off":
                success, feedback = agent.system.set_keyboard_backlight_percent(0)
                decision = {"action": "keyboard_backlight_control", "target": "kbd_backlight_off"}
            elif act == "set_orientation" and orientation_val:
                success, feedback = agent.system.set_display_orientation(orientation_val)
                decision = {"action": "orientation_control", "target": f"orientation_{orientation_val}"}
            elif act.startswith("orientation_"):
                orient_target = act.replace("orientation_", "")
                decision = {"action": "orientation_control", "target": act}
                success, feedback = agent.system.set_display_orientation(orient_target)
            elif act == "set_resolution" and resolution_val:
                success, feedback = agent.system.set_display_resolution(resolution_val)
                decision = {"action": "resolution_control", "target": f"resolution_{resolution_val}"}
            elif act == "resolution_down":
                success, feedback = agent.system.step_display_resolution(direction="down")
                decision = {"action": "resolution_control", "target": "resolution_down"}
            elif act == "resolution_up":
                success, feedback = agent.system.step_display_resolution(direction="up")
                decision = {"action": "resolution_control", "target": "resolution_up"}
            elif act.startswith("resolution_"):
                res_target = act.replace("resolution_", "")
                decision = {"action": "resolution_control", "target": act}
                if res_target in ("up", "down"):
                    success, feedback = agent.system.step_display_resolution(direction=res_target)
                else:
                    success, feedback = agent.system.set_display_resolution(res_target)
            elif act == "set_power_profile" and profile:
                success, feedback = agent.system.set_power_profile(profile)
                decision = {"action": "session_control", "target": f"power_profile_{profile}"}
            elif act == "volume_up":
                decision = {"action": "volume_control", "target": "volume_up"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "volume_down":
                decision = {"action": "volume_control", "target": "volume_down"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "mute_toggle":
                decision = {"action": "volume_control", "target": "mute_toggle"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "mic_mute_toggle":
                decision = {"action": "mic_control", "target": "mic_mute_toggle"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "brightness_up":
                decision = {"action": "display_control", "target": "brightness_up"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "brightness_down":
                decision = {"action": "display_control", "target": "brightness_down"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "night_light_toggle":
                decision = {"action": "display_control", "target": "night_light_toggle"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "theme_toggle":
                decision = {"action": "display_control", "target": "theme_toggle"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "dark_mode":
                decision = {"action": "display_control", "target": "dark_mode"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "light_mode":
                decision = {"action": "display_control", "target": "light_mode"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "wifi_toggle":
                decision = {"action": "connectivity_control", "target": "wifi_toggle"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "bluetooth_toggle":
                decision = {"action": "connectivity_control", "target": "bluetooth_toggle"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "dnd_toggle":
                decision = {"action": "connectivity_control", "target": "dnd_toggle"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "lock_screen":
                decision = {"action": "session_control", "target": "lock_screen"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "touchpad_toggle":
                decision = {"action": "touchpad_control", "target": "touchpad_toggle"}
                success, feedback = agent.system.set_touchpad_toggle()
            elif act == "touchpad_on":
                decision = {"action": "touchpad_control", "target": "touchpad_on"}
                success, feedback = agent.system.set_touchpad_enabled(True)
            elif act == "touchpad_off":
                decision = {"action": "touchpad_control", "target": "touchpad_off"}
                success, feedback = agent.system.set_touchpad_enabled(False)
            elif act == "touchpad_tap_toggle":
                decision = {"action": "touchpad_control", "target": "touchpad_tap_toggle"}
                success, feedback = agent.system.set_touchpad_tap_to_click_toggle()
            elif act == "touchpad_natural_scroll_toggle":
                decision = {"action": "touchpad_control", "target": "touchpad_natural_scroll_toggle"}
                success, feedback = agent.system.set_touchpad_natural_scroll_toggle()
            elif act == "set_touchpad_speed":
                speed_pct = payload.get("speed_percent", 50)
                decision = {"action": "touchpad_control", "target": f"touchpad_speed_set_{speed_pct}"}
                success, feedback = agent.system.set_touchpad_speed_percent(speed_pct)
            elif act == "touchpad_speed_up":
                decision = {"action": "touchpad_control", "target": "touchpad_speed_up"}
                success, feedback = agent.system.step_touchpad_speed("up", 15)
            elif act == "touchpad_speed_down":
                decision = {"action": "touchpad_control", "target": "touchpad_speed_down"}
                success, feedback = agent.system.step_touchpad_speed("down", 15)
            elif act == "take_screenshot":
                decision = {"action": "screenshot_control", "target": "take_screenshot"}
                success, feedback, file_path = agent.system.take_screenshot()
            elif act == "screen_recording_toggle":
                stat = agent.system.get_screen_recording_status()
                if stat["active"]:
                    decision = {"action": "screen_recording_control", "target": "screen_recording_stop"}
                    success, feedback, file_path = agent.system.stop_screen_recording()
                else:
                    decision = {"action": "screen_recording_control", "target": "screen_recording_start"}
                    success, feedback, file_path = agent.system.start_screen_recording()
            elif act == "screen_sharing_toggle":
                info = agent.system.get_screen_sharing_info()
                decision = {"action": "screen_sharing_control", "target": "screen_sharing_toggle"}
                success, feedback = agent.system.set_screen_sharing(not info["active"])
            elif act == "set_screen_blanking":
                secs = payload.get("seconds", 0)
                decision = {"action": "blanking_control", "target": f"blanking_set_{secs}"}
                success, feedback = agent.system.set_screen_blanking(secs)
            elif act == "set_wallpaper":
                path = payload.get("path", "")
                decision = {"action": "wallpaper_control", "target": "wallpaper_set"}
                success, feedback = agent.system.set_wallpaper(path)
            elif act == "wallpaper_status":
                decision = {"action": "wallpaper_control", "target": "wallpaper_status"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "monitors_status":
                decision = {"action": "monitors_control", "target": "monitors_status"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "clipboard_clear":
                decision = {"action": "clipboard_control", "target": "clipboard_clear"}
                success, feedback = agent.system.clear_clipboard()
            elif act == "clipboard_read":
                decision = {"action": "clipboard_control", "target": "clipboard_read"}
                success, feedback = agent.system.get_clipboard_text()
            elif act == "clipboard_copy":
                txt = payload.get("text", "")
                decision = {"action": "clipboard_control", "target": "clipboard_copy"}
                success, feedback = agent.system.set_clipboard_text(txt)
            elif act == "set_mouse_speed":
                speed_pct = payload.get("speed_percent", 50)
                decision = {"action": "mouse_control", "target": f"mouse_speed_set_{speed_pct}"}
                val = (speed_pct / 50.0) - 1.0
                success, feedback = agent.system.set_mouse_speed(val)
            elif act == "mouse_natural_scroll_toggle":
                info = agent.system.get_mouse_info()
                decision = {"action": "mouse_control", "target": "mouse_natural_scroll_toggle"}
                success, feedback = agent.system.set_mouse_natural_scroll(not info["natural_scroll"])
            elif act == "play_pause":
                decision = {"action": "media_control", "target": "play_pause"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "next_track":
                decision = {"action": "media_control", "target": "next_track"}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "previous_track":
                decision = {"action": "media_control", "target": "previous_track"}
                success, feedback = agent.system.execute_decision(decision)
            elif act.startswith("launch_"):
                app_name = act.replace("launch_", "")
                decision = {"action": "app_launcher", "target": app_name}
                success, feedback = agent.system.execute_decision(decision)
            elif act == "open_folder":
                path = payload.get("path", "")
                if path and os.path.exists(os.path.dirname(path)):
                    success = True
                    feedback = f"Opened folder: {os.path.dirname(path)}"
                    subprocess.Popen(["xdg-open", os.path.dirname(path)], env=self.env)
                else:
                    success = False
                    feedback = "Invalid folder path"
                decision = {"action": "open_folder", "target": path}
            else:
                success, feedback = False, f"Unknown action: {act}"
                decision = {"action": "unknown", "target": act}

            latency = (time.time() - start_t) * 1000
            record_event("action", feedback, {
                "decision": decision,
                "latency_ms": round(latency, 1),
                "success": success
            })

            response_data = {
                "success": success,
                "feedback": feedback,
                "decision": decision,
                "latency_ms": round(latency, 1)
            }
            if 'file_path' in locals() and file_path:
                response_data["file_path"] = file_path
            self._send_json(response_data)
            return

        elif path == "/api/history/clear":
            with state_lock:
                history_log.clear()
            self._send_json({"success": True})
            return

        else:
            self.send_error(404, "Endpoint Not Found")

def run_server(port=SERVER_PORT):
    server = ThreadingHTTPServer(("0.0.0.0", port), VoiceAgentHandler)
    print(f"============================================================")
    print(f"  Linux System Controller & Dashboard Online")
    print(f"  URL: http://localhost:{port} (or http://127.0.0.1:{port})")
    print(f"============================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else SERVER_PORT
    run_server(port)
