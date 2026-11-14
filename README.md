Zenith OS
Precision at your screen’s edge. Intelligent. Weightless. Pitch Black.

Platform
Python
Framework
AI Engine
Audio

Zenith OS is a hyper-minimalist, high-performance AI desktop companion and dynamic island interface designed for Windows 10 and 11, created by Vansh Soni.

Quickstart • Features • Robot Eyes • AI Routing • Architecture • Author

🌟 Overview

Zenith OS transforms the upper edge of your Windows display into a fluid, responsive OLED dynamic island (#000000). It seamlessly integrates:

Autonomous Expressive Robot Eyes: A 60 FPS vector companion with 16 distinct procedural moods, cursor gaze tracking, and real-time audio reactivity.
Dual-Core AI Engine: Ultra-low-latency cloud reasoning via Groq LLaMA 3.3 70B paired with a 0.0ms deterministic fast-path router for instant hardware control.
Android 16 Waveform Seek Bar: A 48-segment fluid audio visualizer with ambient radial album art glow and Windows SMTC media integration.
Smart Workspaces Engine: One-click snapshotting and restoration of multi-window desktop layouts.
Productivity & Telemetry: Pomodoro focus timer, low-latency clipboard vault, anti-snapback volume and brightness sliders, and live CPU, RAM, and Battery telemetry.
🚀 Quickstart

Run Zenith OS directly from source:

Prerequisites
Windows 10 or 11 (64-bit)
Python 3.10+ installed
Setup & Run
bash
# 1. Clone repository
git clone https://github.com/sonivansh1/DynamicIslandOS.git
cd DynamicIslandOS
# 2. Install dependencies
pip install -r requirements.txt
# 3. Launch Zenith OS
python main.py

Tip: You can also double-click Launch_Island.bat for one-click startup with automated dependency verification.

🤖 Autonomous Expressive Robot Eyes

Zenith OS features a living vector robot companion rendered procedurally at 60 FPS. It maintains virtually 0.00% CPU overhead via an event-driven physics engine that idles when untouched.

Supported Mood Matrix (16 Procedural Expressions)
Mood State	Visual Expression	Trigger Condition
Neutral Idle	Dual rounded rectangular eyes with soft cyan bloom (#00F0FF)	Default standing-by state; glances naturally
Happy Arch	Upward smiling crescent arches (^ ^)	Positive AI feedback, task completion
Love Hearts	Neon pink pulsing hearts (#FF5096) with cubic bezier curves	Compliments, favorites
Star Sparkle	8-point rotating golden stars (#FFD700)	Milestones reached, focus sessions
Wink	Playful horizontal wink	Friendly interactions
Command Mic	3 vertical equalizer lines driven by microphone input	Active user speech detection (Ctrl + Space)
AI Responding	Rhythmic undulating harmonic sine waves	Groq LLaMA text-to-speech playback
Curious Squint	Subtle eye narrowing with upward tilt	Incoming system alerts
Dizzy / Confused	Asymmetrical eye heights with quizzical tilt	Unrecognized prompt
Focused Scanner	Ultra-sleek horizontal laser slits with sweeping beam	Active Pomodoro focus session
Shocked Surprise	Wide vertically dilated ovals	Battery alert, sudden volume spike
Dead Offline	Red crossed X  X dead eyes (#FF2233)	Lost internet connectivity
🧠 Dual-Core AI Engine

Zenith OS pairs the reasoning depth of Groq LLaMA 3.3 70B with a deterministic local fast-path engine that executes system commands with zero network latency.

Instant Hardware Commands (0.0ms Latency)
"volume up" / "volume down" — CoreAudio endpoint adjustments
"mute" / "unmute" — Master audio toggle
"brightness up" / "brightness down" — WMI monitor luminance control
"lock the pc" — Immediate session lock (User32.LockWorkStation)
"set timer for 25 minutes" — Focus countdown timer
"what are my current system stats" — Instant CPU, RAM, and Battery telemetry
🎵 Android 16 Waveform Media Player
48 Organic Waveform Bars: Dynamically calculated vertical bars replacing traditional static seek thumbs.
Live Seeking: Click or drag directly across the waveform to jump to any track position.
Ambient Radial Art Glow: Automatically samples album art to cast a subtle radial glow behind the island.
Audio Output Selector: Seamlessly switch between headphones, internal speakers, and external monitors.
⚡ Smart Workspaces Orchestration

Capture and restore multi-window desktop workflows with a single click:

Window Enumeration: Queries the Desktop Window Manager (DWM) for all active, non-minimized windows.
App Resolution: Maps running process IDs to executable paths or Store Application User Model IDs (AUMID).
Layout Restoration: Launches any closed apps and snaps windows back to their multi-monitor coordinates.
📊 Productivity & System Hub
Pomodoro Focus Timer: Dual native modes (Focus: 25m, Break: 5m) with quick adjustment steppers.
Clipboard Vault: Stores up to 10 recent clipboard entries for immediate one-click restoration.
Hardware Sliders: Capsule sliders for Volume and Brightness equipped with anti-snapback drag locking.
Live Telemetry: Continuous real-time readings for CPU load, RAM allocation, and battery status.
⌨️ Global Shortcuts
Shortcut	Action
Ctrl + Space	Trigger Zenith AI (Voice input & text prompt)
Click Top Notch	Expand / Collapse the OLED dashboard
Hover Top Notch	Reveal quick media and timer controls
Escape	Instantly collapse expanded dashboard
🛠️ Source Code Structure
text
DynamicIslandOS/
├── main.py                 # Core dynamic island overlay & window manager
├── island_eyes.py          # Procedural 60 FPS vector robot eyes & moods
├── dashboard_widget.py     # OLED multi-tab dashboard (Music, Timer, System, Workspaces, Clipboard)
├── ai_worker.py            # Groq LLaMA 3.3 router, Whisper STT & fast-path engine
├── media_worker.py         # Windows SMTC media transport & waveform visualizer
├── system_tools.py         # Hardware telemetry, audio, and brightness controllers
├── workspace_engine.py     # Win32/DWM window snapshot & restoration engine
├── settings_dialog.py      # Island appearance & preferences configuration
├── config.py               # JSON configuration manager
├── requirements.txt        # Python package dependencies
├── Launch_Island.bat       # One-click startup script
└── icon.ico                # Application icon
👤 Author & Contact

Zenith OS is designed and developed by Vansh Soni.

GitHub: github.com/sonivansh1
LinkedIn: linkedin.com/in/vanshsoni1
Location: Bhopal, India
Copyright © 2026 Vansh Soni. All rights reserved.
