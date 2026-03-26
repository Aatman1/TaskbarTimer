# ⏱ TaskbarTimer

A lightweight countdown timer that lives in your **Windows system tray** with an always-on-top floating window.

---

## Features

- ✨ **Enhanced UI** — Glowing progress ring with pulse animation, hover effects, focus glows
- 📊 **Live Progress** — % complete above timer, larger bold fonts
- ⚙️ **Settings** — Toggle sound mute (⚙ button)
- ⌨️ **Keyboard Shortcuts** — Space (pause/resume), R (reset), Esc (hide)
- 🕐 **Countdown timer** — set any duration (5m, 1h30m, 90, 1:30:00, etc.)
- 🔔 **Alarm sound** — plays a beep when timer expires (with pulse glow)
- 📌 **Always-on-top** floating window — never buried under other apps
- 🖱 **System tray icon** — shows live countdown, right-click for quick presets
- ⚡ **Quick presets** — 5m, 10m, 25m (Pomodoro), 1h buttons
- 🎯 **Draggable** — move the window anywhere on screen
- 💡 **Minimal** — close the window, timer keeps running in tray

---

## Option A — Run from Python (no install needed)

**Requirements:** Python 3.8+, Windows

```
pip install pystray pillow
python timer_app.py
```

---

## Option B — Build a standalone .exe

Double-click `build.bat` — it will install PyInstaller and package everything into:

```
dist\TaskbarTimer.exe
```

No Python needed to run the `.exe`. Share it, pin it to startup, done.

**To auto-start with Windows:**
1. Press `Win + R` → type `shell:startup` → Enter
2. Copy `TaskbarTimer.exe` into that folder

---

## How to use

| Action | How |
|--------|-----|
| Set timer | Type `5:00`, `25`, `1h30m`, `90s` in the box → press Enter or ▶ |
| Quick start | Click a preset button (5m, 10m, 25m, 1h) |
| Pause/Resume | Click ⏸ Pause button or tray → Pause/Resume |
| Reset | Click ↺ Reset |
| Tray shortcuts | Right-click tray icon for quick 5/10/25m starts |
| Hide window | Click × — timer keeps running in tray |
| Show again | Double-click tray icon |

---

## Time input formats

All of these work in the input box:

- `5` → 5 minutes
- `5:00` → 5 minutes
- `1:30:00` → 1 hour 30 minutes
- `25m` → 25 minutes
- `1h30m` → 1 hour 30 minutes
- `90s` → 90 seconds
- `1h` → 1 hour
