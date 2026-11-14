# 🧪 Dynamic Island Desktop Companion — Comprehensive Manual Testing Guide

This document provides a complete, step-by-step verification checklist and testing manual for the **Dynamic Island Desktop Companion** application.

---

## 🚀 Quick Start & Launching

### Launch Application
Open PowerShell or Command Prompt in the repository folder:
```powershell
cd C:\Users\vansh\.gemini\antigravity\scratch\DynamicIslandOS
.\Launch_Island.bat
# or directly with Python:
& "C:\Users\vansh\AppData\Local\Python\pythoncore-3.14-64\python.exe" main.py
```

### Run Automated Test Suite
To verify all subsystems and AI parsing pipelines automatically:
```powershell
& "C:\Users\vansh\AppData\Local\Python\pythoncore-3.14-64\python.exe" manual_test_suite.py --auto
```
To launch the interactive CLI verification menu:
```powershell
& "C:\Users\vansh\AppData\Local\Python\pythoncore-3.14-64\python.exe" manual_test_suite.py --interactive
```

---

## 📋 Comprehensive Feature Checklist

### 1. Compact Idle Island & Minimalist Audio Wave
* **Visual Appearance**:
  - The island sits at the top-center of your primary display in pitch-black OLED (`#000000`) glass with subtle borders.
  - When music is stopped or paused, the pill is sleek and compact.
* **Minimalist Audio Wave**:
  - Play any song on Spotify, YouTube (Chrome/Edge), or Windows Media Player.
  - Look at the right side of the compact pill: a gentle, organic multi-harmonic wave flows rhythmically.
  - Verify it is calm and unobtrusive, replacing loud attention-drawing visualizers.
  - Pause playback: the wave smoothly collapses into a minimalist static bar or hides.

---

### 2. Timer Hover Controls & Quick Actions
* **Start a Timer**:
  - Click on the island to open the dashboard, select **Timer**, and press **▶ (Start)**.
  - Move your mouse away so the island collapses back to the compact pill.
* **Hover State Verification**:
  - Hover your mouse cursor over the compact pill while the timer is running.
  - The island smoothly expands to reveal:
    - **Time remaining** (e.g. `Timer 24:58`).
    - **Minimalist Pause/Resume button (`⏸` / `▶`)**: Click to pause countdown; the icon switches to `▶`. Click again to resume.
    - **Minimalist Stop button (`⏹`)**: Click to cancel timer and return to idle.
    - **Next Panel button (`›`)**: Click to rotate smoothly into the Quick Actions / Controls panel without opening the full dashboard.

---

### 3. Focus / Break Mode Toggle (Collapse Fix Verification)
* **Open Timer Tab**:
  - Click the island or press `Ctrl + Space` to expand into the Full Dashboard.
  - Click on the **Timer** tab in the navigation bar.
* **Mode Switching**:
  - Click on **Break (5 min)**:
    - ✅ **Expected**: The timer displays `05:00` and the mode indicator highlights "Break".
    - ✅ **Fix Verified**: The island stays open in `FULL_DASHBOARD` and does **not** collapse to compact pill.
  - Click back to **Focus (25 min)**:
    - ✅ **Expected**: The timer displays `25:00` and remains comfortably open in the dashboard view.
  - Adjust durations using the `+` and `-` stepper buttons.
  - Click the reset button (`↺`) to restore countdown time.

---

### 4. Android 16 Expressive Waveform Seek Bar & Ambient Glow
* **Media Player Tab**:
  - Open the dashboard and click the **Music** tab.
* **Dominant Color Ambient Glow**:
  - The background behind the album art dynamically radiates a subtle radial gradient matching the artwork's dominant palette.
  - Controls, progress track, and labels inherit the harmonic color scheme.
* **Android 16 Waveform Seek Bar**:
  - 48 vertically varying waveform bars replace standard circular slider thumbs.
  - **Played Section**: Lit with vibrant glowing bars.
  - **Unplayed Section**: Muted deep-grey organic waveform.
  - **Fluid Animation**: Bars oscillate with micro-motion while playing, and freeze when paused.
  - **Seeking**: Click or drag anywhere along the waveform to instantly scrub playback in YouTube/Spotify.
* **Wall-Clock Accurate Resumption**:
  - Note the playback position (e.g., `01:10`).
  - Collapse the island to compact pill and wait for 20-30 seconds.
  - Re-expand the island: verify the timestamp and waveform immediately reflect the true elapsed time (e.g., `01:40`) rather than jumping from the stale `01:10` mark.
* **Audio Device Selector**:
  - Look at the top right of the media player: click the audio output dropdown to change output devices directly.

---

### 5. System Telemetry & Ultra-Smooth Sliders
* **System Tab**:
  - Click **System** in the bottom navigation bar.
  - Observe real-time system metrics: **CPU**, **Memory**, **Network**, **Storage**, **Battery**, and **Uptime**.
* **Vertical Capsule Sliders (Volume & Brightness)**:
  - Two rounded vertical pill capsules represent Display Brightness and System Volume.
  - **Interaction**:
    - Click and drag up/down inside the capsule.
    - Or scroll the mouse wheel directly over each capsule.
  - **Verification**:
    - Verify the sliders glide smoothly with zero stutter.
    - Notice that after releasing the slider, there is **zero snap-back**: the background telemetry polling thread respects a 1.2-second user interaction lockout window.
* **Optimize Memory**:
  - Click the **"🚀 Optimize memory"** button at the bottom: verify working set cleanup executes and frees RAM.

---

### 6. Workspaces Management
* **Workspaces Tab**:
  - Click **Workspaces** in the navigation bar.
* **Clean Single-Entry Creation**:
  - Verify that only the clean **"New Workspace"** button is present (redundant duplicate capture buttons removed).
  - Click **"New Workspace"**: enter a name (e.g., `Coding`) and select the apps to bundle.
* **Launch Workspace**:
  - Click **"Launch"** on any workspace card: all mapped applications launch into position simultaneously.

---

### 7. Clipboard History (10 Items Cap)
* **Clipboard Tab**:
  - Click **Clipboard** in the bottom navigation bar.
* **Clean OLED Header**:
  - Displays a clean header with "Clear All" action (no clutter or redundant counters).
* **10 Items Cap**:
  - Copy several different texts across your browser or text editor.
  - Verify that the history keeps at most the last 10 copied entries.
  - Click on any clipboard card to copy it back to your active Windows clipboard.
  - Click the trash can (`🗑`) icon to remove an individual entry.

---

## 🎙️ AI Voice & Text Command Test Matrix

You can trigger the AI Companion by clicking the **Microphone** icon or by pressing the global hotkey **`Ctrl + Space`**.

### Category 1: Hardware & Display Controls (Fast-Path Zero Latency)
| Command | Expected Behavior |
| :--- | :--- |
| `"volume up"` | Increases system master volume by 10% |
| `"volume down"` | Decreases system master volume by 10% |
| `"set volume to 60 percent"` | Sets volume to exact 60% level |
| `"brightness up"` | Increases screen brightness by 10% |
| `"set brightness to 80"` | Sets monitor brightness to 80% |
| `"turn on night light"` | Activates Windows blue-light reduction |
| `"lock the pc"` | Instantly locks the Windows user session |
| `"minimize all windows"` | Clears screen to show desktop |

### Category 2: Productivity & Workspaces
| Command | Expected Behavior |
| :--- | :--- |
| `"start notepad"` | Launches Windows Notepad instantly |
| `"launch Development workspace"` | Launches saved Development workspace apps |
| `"capture current workspace as Research"` | Captures open active windows into a new workspace |
| `"set timer for 25 minutes"` | Starts a 25-minute Pomodoro focus countdown |

### Category 3: System Diagnostics & Telemetry
| Command | Expected Behavior |
| :--- | :--- |
| `"battery"` | Speaks/displays battery percentage and charging state |
| `"what are my current system stats and ram usage"` | Reports active CPU%, RAM usage, GPU, and system uptime |

### Category 4: File & Storage Operations
| Command | Expected Behavior |
| :--- | :--- |
| `"find file notes.txt"` | Searches user directories and opens file location |
| `"create folder ProjectX on Desktop"` | Generates a new directory on the user's Desktop |
| `"what is the size of Downloads"` | Calculates total bytes consumed by the Downloads folder |

### Category 5: Companion Memory & Identity
| Command | Expected Behavior |
| :--- | :--- |
| `"who created you"` | Confirms companion personality and creator grounding |
| `"remember my favorite color is obsidian black"` | Persists custom note to `~/.zenith_memory.txt` |
| `"what is my favorite color"` | Recalls stored information from memory file |

---

## 🎨 Visual Wave & AI Animation Verification
1. **Listening Animation**:
   - When speaking to the mic, the 3-line reactive wave smoothly tracks audio levels.
2. **Responding Animation**:
   - While the AI is generating and speaking its response, a rhythmic breathing wave animates continuously.
   - The animation does **not** cut abruptly to idle until the entire response is completed.
3. **Emo Eyes Suppression**:
   - If "Emo Eyes" are disabled in Settings, the eyes remain 100% hidden and do not flash after speech finishes.
