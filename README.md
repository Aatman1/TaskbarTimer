⏱ TaskbarTimer



A modern, minimal countdown timer with system tray controls and a floating always-on-top UI — designed for focus and productivity.

📖 Overview

TaskbarTimer is a lightweight desktop timer built for Windows users who want quick, distraction-free time tracking without opening bulky apps.

It combines:

A floating, frameless timer window
A live-updating system tray icon
Quick controls accessible anywhere

Perfect for:

🍅 Pomodoro sessions
📚 Studying
💻 Deep work
🏋️ Workouts
⏳ Time blocking
✨ Features
🎯 Core Functionality
⏱ Countdown timer with second-level precision
🔄 Circular progress ring visualization
🧠 Smart state handling (pause, resume, reset, restart)
🖥️ UI/UX
Frameless, always-on-top floating window
Clean dark-themed interface
Draggable anywhere on screen
Minimal and distraction-free
⚡ Speed & Input
Quick presets: 5m / 10m / 25m / 1h
Flexible input parsing:
5:00
25m
1h30m
90 (minutes)
📌 System Tray Integration
Live countdown displayed in tray tooltip
Dynamic tray icon with progress visualization
Right-click menu:
Show Timer
Quick Start (5 / 10 / 25 min)
Pause / Resume
Reset
Quit
🔔 Notifications
Audible alarm when timer completes
Visual “DONE” state
🖼️ Screenshots (Optional)

Add screenshots here for better presentation

/assets/screenshot1.png
/assets/screenshot2.png
📦 Installation
⚡ Option 1 — Download Executable (Recommended)
Go to the Releases section
Download the latest .zip
Extract the files
Run:
TaskbarTimer.exe

✅ No Python required
✅ Ready to use instantly

🔧 Option 2 — Run from Source
1. Clone the repository
git clone https://github.com/Aatman1/TaskbarTimer.git
cd taskbartimer
2. Install dependencies
pip install pillow pystray
3. Run the application
python timer_app.py
🚀 Usage Guide
▶ Starting a Timer
Enter a time (e.g., 25m, 5:00)
Press ▶ Start
⏸ Controls
Pause → ⏸
Resume → ▶
Reset → ↺
🖱 System Tray
Click tray icon → open timer
Right-click → quick actions
🧠 Input Format Reference
Input	Meaning
5:00	5 minutes
25m	25 minutes
1h	1 hour
1h30m	1.5 hours
90	90 minutes
45s	45 seconds
🏗️ Project Structure
taskbartimer/
│
├── timer_app.py        # Main application
├── assets/             # Icons / screenshots (optional)
├── README.md
└── requirements.txt
🛠️ Tech Stack
Python 3
Tkinter → UI
Pillow (PIL) → Tray icon rendering
pystray → System tray integration
winsound → Alarm notifications (Windows)
⚙️ Building an Executable

To create a standalone .exe:

1. Install PyInstaller
pip install pyinstaller
2. Build
pyinstaller --onefile --noconsole timer_app.py
3. Output
/dist/TaskbarTimer.exe
🧩 Customization

You can easily tweak:

🎨 Colors (top of timer_app.py)
⏱ Preset durations
🔊 Alarm sound behavior
🖼 Tray icon design
📌 Roadmap
 Multiple timers
 Custom themes (light/dark toggle)
 Desktop notifications
 Keyboard shortcuts
 Timer history / analytics
 Config file support
🐛 Known Issues
Windows-only (uses winsound)
Some systems may not support custom fonts in tray icon
Multi-monitor positioning may vary
🤝 Contributing

Contributions are welcome!

Fork the repo
Create a branch (feature/new-feature)
Commit changes
Open a Pull Request
📄 License

This project is licensed under the MIT License.

⭐ Support

If you find this useful:

👉 Star the repo
👉 Share it with others
👉 Suggest features or improvements

🙌 Acknowledgments
Python community
Open-source UI inspiration
Productivity enthusiasts worldwide