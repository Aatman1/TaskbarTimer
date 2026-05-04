# TaskbarTimer
<p align="center">
  <img src="TaskTimer_logo.svg" alt="Description" width="400">
</p>

A sleek, feature-rich desktop timer and alarm application for Windows, built with Python and Tkinter. TaskbarTimer lives in your system tray and provides a dark-themed floating window with four integrated time-management tools.



![Platform](https://img.shields.io/badge/platform-Windows-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)
![Build](https://img.shields.io/badge/build-passing-brightgreen)
![Status](https://img.shields.io/badge/status-stable-success)

---

## ✨ Features

### 🕐 Timer
- Set countdowns using flexible input formats: `5:00`, `1h30m`, `90s`, etc.
- Quick-start presets: **5m**, **15m**, **30m**, **1h**
- Animated circular progress ring with smooth interpolation
- Pause, Resume, Restart, and Reset controls
- Audible alarm (multi-tone beep sequence) when the countdown expires

### ⏱ Stopwatch
- Precision display down to tenths of a second (`MM:SS.f`)
- Start, Pause, Resume, and Reset
- Lap recording with a scrollable lap history list

### 🔔 Alarm
- Schedule alarms by time of day (fires once per minute match)
- Toggle individual alarms on/off with a single click
- Delete alarms instantly
- **Snooze** (9-minute delay) or **Dismiss** when ringing
- Alarms persist between sessions (saved to `~/.timer_alarm_v3.json`)
- Continuous audible alert when an alarm fires

### 🌍 World Clock
- Live, auto-updating clocks for 17 cities across all major time zones:  
  Honolulu, Los Angeles, Denver, Chicago, New York, São Paulo, London, Paris, Cairo, Moscow, Dubai, Mumbai, Bangkok, Beijing, Tokyo, Sydney, Auckland
- Scrollable list; updates every second

---

## 🖥 System Tray Integration

When `Pillow` and `pystray` are installed, TaskbarTimer runs as a **system tray icon**:

- **Dynamic icon** — shows a progress arc and remaining time while the timer runs; turns red on expiry
- **Tooltip** — displays the current countdown (`⏱ 04:32`) or a completion message
- **Right-click menu**:
  - Show Timer window
  - Quick Start (5m / 15m / 30m / 1h)
  - Toggle "Run at Startup" (writes to the Windows registry)
  - Quit

---

## 🎨 UI & Design

- **Dark theme** — deep navy/charcoal palette (`#10111a` background)
- **Frameless window** — custom title bar with drag-to-move support
- **Windows 11 styling** — rounded corners and immersive dark mode applied via DWM API (`DwmSetWindowAttribute`)
- **Smooth fade-in** on launch
- **Custom rounded buttons** drawn on `tk.Canvas` with hover states
- **12h / 24h toggle** — switch time formats globally across Alarm and World Clock tabs

---

## 📋 Requirements

### Python
- Python **3.8** or newer

### Required (core UI)
```
tkinter      # Included with standard Python on Windows
```

### Optional (system tray icon)
```
Pillow
pystray
```

> Without `Pillow` and `pystray`, the app runs normally but without a system tray icon.

---

## 🚀 Installation & Running

### 1. Clone or download
```bash
git clone https://github.com/your-username/taskbar-timer.git
cd taskbar-timer
```

### 2. Install optional dependencies
```bash
pip install Pillow pystray
```

### 3. Run
```bash
python timer_app.py
```

---

## 📦 Building a Standalone Executable (optional)

Use [PyInstaller](https://pyinstaller.org/) to produce a single `.exe` with no Python installation required:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name TaskbarTimer timer_app.py
```

The compiled executable will appear in the `dist/` folder. The "Run at Startup" tray menu item automatically detects and uses the `.exe` path when running as a PyInstaller bundle.

---

## ⚙️ Configuration

Alarm data is saved automatically to:

```
C:\Users\<YourName>\.timer_alarm_v3.json
```

The file is a plain JSON array. Example:
```json
[
  {"time": "07:00", "label": "Good morning", "on": true},
  {"time": "12:30", "label": "Lunch", "on": false}
]
```

- Times are always stored in **24-hour format** internally, regardless of display preference.
- The file is created with a default "Good morning" alarm if it does not exist.

---

## ⌨️ Time Input Formats (Timer tab)

The timer entry field accepts several natural formats:

| Input | Interpreted as |
|-------|---------------|
| `5:00` | 5 minutes |
| `1:30:00` | 1 hour 30 minutes |
| `90` | 90 minutes |
| `1h30m` | 1 hour 30 minutes |
| `45s` | 45 seconds |
| `2h` | 2 hours |

---

## 🏗 Project Structure

```
timer_app.py          # Single-file application
~/.timer_alarm_v3.json  # Auto-generated alarm config (per user)
```

### Key classes and functions

| Name | Role |
|------|------|
| `App` | Main `tk.Tk` window; owns all panels and the event loop |
| `TimerState` | Shared global state (remaining time, running flag, expired flag) |
| `RoundedButton` | Custom canvas-drawn button with hover effects |
| `make_tray_icon()` | Generates the dynamic PIL image for the system tray |
| `run_tray()` | Runs the `pystray` icon in a daemon thread |
| `beep_alarm()` | Plays a multi-tone beep sequence via `winsound` in a daemon thread |
| `parse_time()` | Parses flexible time strings into total seconds |
| `load_alarms()` / `save_alarms()` | JSON persistence for alarm data |
| `apply_win11_style()` | Applies DWM dark mode and rounded corners via `ctypes` |

---

## 🪟 Platform Notes

TaskbarTimer is **Windows-only** due to its use of:

- `winreg` — Windows Registry (startup toggle)
- `winsound` — Windows audio beep
- `ctypes.windll.dwmapi` — Windows 11 DWM visual styling

Running on macOS or Linux will raise import errors for these modules.

---

## 📄 License

This project is provided as-is. Feel free to modify and distribute it for personal use.
