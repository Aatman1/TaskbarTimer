"""
TaskbarTimer — Countdown Timer with System Tray + Floating Window
Runs on Windows. Shows timer in tray tooltip and floating always-on-top window.
"""

import tkinter as tk
from tkinter import font as tkfont
import threading
import time
import sys
import os
import math
import winsound  # Windows only — plays alarm beep
from PIL import Image, ImageDraw, ImageFont
import pystray

# ── Color palette ────────────────────────────────────────────────────────────
BG         = "#0f0f10"
SURFACE    = "#1a1a1d"
BORDER     = "#2a2a30"
ACCENT     = "#4fc3f7"   # icy blue
ACCENT2    = "#ff6b6b"   # alarm red
TEXT       = "#f0f0f0"
MUTED      = "#6b6b7a"
PROGRESS   = "#4fc3f7"

# ── App state ─────────────────────────────────────────────────────────────────
class TimerState:
    def __init__(self):
        self.total_seconds  = 0
        self.remaining      = 0
        self.running        = False
        self.expired        = False
        self.alarm_fired    = False
        self.label          = "Timer"

state = TimerState()

# ── Tray icon helpers ─────────────────────────────────────────────────────────

def make_tray_icon(remaining: int, running: bool, expired: bool) -> Image.Image:
    """Draw a small 64×64 icon showing remaining minutes or a ring."""
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d    = ImageDraw.Draw(img)

    # Background circle
    bg_col = "#ff4444" if expired else ("#1a1a1d" if not running else "#0d2233")
    d.ellipse([2, 2, size-2, size-2], fill=bg_col, outline="#4fc3f7", width=2)

    # Progress arc (only when running / set)
    if state.total_seconds > 0 and not expired:
        frac  = remaining / state.total_seconds
        angle = int(360 * frac)
        d.arc([6, 6, size-6, size-6], start=-90, end=-90 + angle,
              fill="#4fc3f7", width=4)

    # Text label — minutes remaining
    mins = remaining // 60
    secs = remaining % 60
    label = f"{mins}m" if mins >= 60 else (f"{mins:02}:{secs:02}" if mins > 0 else f"{secs}s")
    if expired:
        label = "✓"

    # Try to load a font, fall back to default
    try:
        fnt = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        fnt = ImageFont.load_default()

    bbox = d.textbbox((0, 0), label, font=fnt)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2
    ty = (size - th) // 2
    d.text((tx, ty), label, font=fnt, fill="#f0f0f0")

    return img


# ── Floating window ───────────────────────────────────────────────────────────

class FloatingTimer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TaskbarTimer")
        self.root.overrideredirect(True)          # frameless
        self.root.attributes("-topmost", True)    # always on top
        self.root.attributes("-alpha", 0.95)
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        # Position: bottom-right, just above taskbar
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = 300, 220
        self.root.geometry(f"{w}x{h}+{sw - w - 16}+{sh - h - 56}")

        self._drag_x = 0
        self._drag_y = 0
        self._build_ui()
        self._update_loop()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = self.root
        root.columnconfigure(0, weight=1)

        # ── Title bar ────────────────────────────────────────────────────────
        title_bar = tk.Frame(root, bg=SURFACE, height=32)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)

        title_lbl = tk.Label(title_bar, text="⏱  TaskbarTimer",
                             bg=SURFACE, fg=MUTED,
                             font=("Segoe UI", 9, "bold"))
        title_lbl.pack(side="left", padx=12)

        close_btn = tk.Label(title_bar, text="×", bg=SURFACE, fg=MUTED,
                             font=("Segoe UI", 14), cursor="hand2")
        close_btn.pack(side="right", padx=8)
        close_btn.bind("<Button-1>", lambda e: self._hide())

        min_btn = tk.Label(title_bar, text="–", bg=SURFACE, fg=MUTED,
                           font=("Segoe UI", 14), cursor="hand2")
        min_btn.pack(side="right", padx=4)
        min_btn.bind("<Button-1>", lambda e: self._minimize())

        # Drag support
        for w in (title_bar, title_lbl):
            w.bind("<ButtonPress-1>",   self._drag_start)
            w.bind("<B1-Motion>",       self._drag_move)

        # ── Divider ──────────────────────────────────────────────────────────
        tk.Frame(root, bg=BORDER, height=1).pack(fill="x")

        # ── Canvas (arc progress ring) ────────────────────────────────────────
        self.canvas = tk.Canvas(root, width=300, height=120,
                                bg=BG, highlightthickness=0)
        self.canvas.pack()
        self._draw_ring()

        # ── Input row ────────────────────────────────────────────────────────
        inp_frame = tk.Frame(root, bg=BG)
        inp_frame.pack(fill="x", padx=16, pady=(0, 10))

        # Preset buttons
        for label, secs in [("5m", 300), ("10m", 600), ("25m", 1500), ("1h", 3600)]:
            btn = tk.Label(inp_frame, text=label, bg=SURFACE, fg=MUTED,
                           font=("Segoe UI", 8, "bold"),
                           padx=8, pady=3, cursor="hand2", relief="flat")
            btn.pack(side="left", padx=2)
            btn.bind("<Button-1>", lambda e, s=secs: self._preset(s))
            btn.bind("<Enter>",    lambda e, b=btn: b.config(fg=ACCENT))
            btn.bind("<Leave>",    lambda e, b=btn: b.config(fg=MUTED))

        # Custom input
        self.entry_var = tk.StringVar()
        entry = tk.Entry(inp_frame, textvariable=self.entry_var,
                         bg=SURFACE, fg=TEXT, insertbackground=ACCENT,
                         relief="flat", font=("Segoe UI", 9),
                         width=8)
        entry.pack(side="left", padx=(8, 2), ipady=3)
        entry.insert(0, "5:00")
        entry.bind("<Return>", lambda e: self._start_from_entry())

        go_btn = tk.Label(inp_frame, text="▶", bg=ACCENT, fg=BG,
                          font=("Segoe UI", 9, "bold"),
                          padx=8, pady=3, cursor="hand2")
        go_btn.pack(side="left", padx=2)
        go_btn.bind("<Button-1>", lambda e: self._start_from_entry())

        # ── Control buttons ───────────────────────────────────────────────────
        ctrl = tk.Frame(root, bg=BG)
        ctrl.pack(fill="x", padx=16, pady=(0, 12))

        self.pause_btn = tk.Label(ctrl, text="⏸ Pause",
                                  bg=SURFACE, fg=TEXT,
                                  font=("Segoe UI", 9),
                                  padx=10, pady=4, cursor="hand2")
        self.pause_btn.pack(side="left", padx=2)
        self.pause_btn.bind("<Button-1>", lambda e: self._toggle_pause())

        reset_btn = tk.Label(ctrl, text="↺ Reset",
                             bg=SURFACE, fg=MUTED,
                             font=("Segoe UI", 9),
                             padx=10, pady=4, cursor="hand2")
        reset_btn.pack(side="left", padx=2)
        reset_btn.bind("<Button-1>", lambda e: self._reset())

    # ── Drawing ────────────────────────────────────────────────────────────────

    def _draw_ring(self):
        c = self.canvas
        c.delete("all")
        cx, cy, r = 150, 60, 44

        # Background ring
        c.create_arc(cx-r, cy-r, cx+r, cy+r,
                     start=90, extent=360,
                     style="arc", outline=SURFACE, width=8)

        frac = 0.0
        if state.total_seconds > 0:
            frac = max(0.0, state.remaining / state.total_seconds)

        # Progress arc
        extent = int(360 * frac)
        color = ACCENT2 if state.expired else ACCENT
        if extent > 0:
            c.create_arc(cx-r, cy-r, cx+r, cy+r,
                         start=90, extent=-extent,
                         style="arc", outline=color, width=8)

        # Time text
        remaining = state.remaining
        h   = remaining // 3600
        m   = (remaining % 3600) // 60
        s   = remaining % 60
        if h > 0:
            time_str = f"{h}:{m:02}:{s:02}"
        else:
            time_str = f"{m:02}:{s:02}"

        if state.expired:
            time_str = "DONE"
            color = ACCENT2
        elif not state.running and state.total_seconds == 0:
            time_str = "--:--"
            color = MUTED
        else:
            color = TEXT

        c.create_text(cx, cy, text=time_str,
                      fill=color,
                      font=("Segoe UI", 22, "bold"))

        # Label below
        lbl = state.label if state.running or state.expired else "Set a timer"
        c.create_text(cx, cy + 32, text=lbl,
                      fill=MUTED, font=("Segoe UI", 8))

    # ── Timer logic ───────────────────────────────────────────────────────────

    def _preset(self, seconds: int):
        self._set_timer(seconds)
        self._start()

    def _start_from_entry(self):
        raw = self.entry_var.get().strip()
        secs = self._parse_time(raw)
        if secs and secs > 0:
            self._set_timer(secs)
            state.label = raw
            self._start()

    def _parse_time(self, s: str) -> int:
        """Parse  5:00 / 5m30s / 90 / 1h / 25 etc."""
        s = s.lower().strip()
        try:
            if ":" in s:
                parts = s.split(":")
                if len(parts) == 2:
                    return int(parts[0]) * 60 + int(parts[1])
                if len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            total = 0
            import re
            for val, unit in re.findall(r"(\d+)\s*([hms]?)", s):
                val = int(val)
                if unit == "h":   total += val * 3600
                elif unit == "m": total += val * 60
                elif unit == "s": total += val
                else:             total += val * 60   # bare number = minutes
            return total
        except Exception:
            return 0

    def _set_timer(self, seconds: int):
        state.total_seconds = seconds
        state.remaining     = seconds
        state.running       = False
        state.expired       = False
        state.alarm_fired   = False
        self._update_pause_btn()

    def _start(self):
        state.running     = True
        state.expired     = False
        state.alarm_fired = False
        self._update_pause_btn()

    def _toggle_pause(self):
        if state.expired:
            self._reset()
            return
        state.running = not state.running
        self._update_pause_btn()

    def _reset(self):
        state.remaining   = state.total_seconds
        state.running     = False
        state.expired     = False
        state.alarm_fired = False
        self._update_pause_btn()

    def _update_pause_btn(self):
        if state.expired:
            self.pause_btn.config(text="↺ Restart")
        elif state.running:
            self.pause_btn.config(text="⏸ Pause")
        else:
            self.pause_btn.config(text="▶ Resume")

    # ── Update loop ───────────────────────────────────────────────────────────

    def _update_loop(self):
        if state.running and state.remaining > 0:
            state.remaining -= 1
        elif state.running and state.remaining == 0 and not state.expired:
            state.expired     = True
            state.running     = False
            state.alarm_fired = True
            self._fire_alarm()

        self._draw_ring()
        self.root.title("TaskbarTimer" + (f" — {self._fmt_remaining()}" if state.running else ""))
        self.root.after(1000, self._update_loop)

    def _fmt_remaining(self) -> str:
        r = state.remaining
        h = r // 3600
        m = (r % 3600) // 60
        s = r % 60
        if h:
            return f"{h}:{m:02}:{s:02}"
        return f"{m:02}:{s:02}"

    def _fire_alarm(self):
        def _beep():
            for _ in range(3):
                try:
                    winsound.Beep(880, 300)
                    time.sleep(0.15)
                    winsound.Beep(1100, 400)
                    time.sleep(0.2)
                except Exception:
                    pass
        threading.Thread(target=_beep, daemon=True).start()

    # ── Drag ─────────────────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def _drag_move(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    # ── Visibility ────────────────────────────────────────────────────────────

    def _hide(self):
        self.root.withdraw()

    def _minimize(self):
        self.root.iconify()

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)

    def run(self):
        self.root.mainloop()


# ── System tray ───────────────────────────────────────────────────────────────

def run_tray(floating: FloatingTimer):
    icon_img = make_tray_icon(0, False, False)

    def on_show(icon, item):
        floating.root.after(0, floating.show)

    def on_quit(icon, item):
        icon.stop()
        floating.root.after(0, floating.root.destroy)

    def on_start_5(icon, item):
        def _do():
            floating._set_timer(300)
            floating._start()
            floating.show()
        floating.root.after(0, _do)

    def on_start_10(icon, item):
        def _do():
            floating._set_timer(600)
            floating._start()
            floating.show()
        floating.root.after(0, _do)

    def on_start_25(icon, item):
        def _do():
            floating._set_timer(1500)
            floating._start()
            floating.show()
        floating.root.after(0, _do)

    def on_pause(icon, item):
        floating.root.after(0, floating._toggle_pause)

    def on_reset(icon, item):
        floating.root.after(0, floating._reset)

    menu = pystray.Menu(
        pystray.MenuItem("Show Timer",    on_show,    default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quick Start",   pystray.Menu(
            pystray.MenuItem("5 minutes",  on_start_5),
            pystray.MenuItem("10 minutes", on_start_10),
            pystray.MenuItem("25 minutes (Pomodoro)", on_start_25),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Pause / Resume", on_pause),
        pystray.MenuItem("Reset",          on_reset),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit",           on_quit),
    )

    icon = pystray.Icon("TaskbarTimer", icon_img, "TaskbarTimer", menu)

    def tray_update():
        """Refresh tray icon + tooltip every second."""
        while True:
            time.sleep(1)
            try:
                new_img = make_tray_icon(state.remaining, state.running, state.expired)
                if state.running:
                    h = state.remaining // 3600
                    m = (state.remaining % 3600) // 60
                    s = state.remaining % 60
                    tooltip = f"⏱ {h}:{m:02}:{s:02}" if h else f"⏱ {m:02}:{s:02}"
                elif state.expired:
                    tooltip = "✓ Timer finished!"
                else:
                    tooltip = "TaskbarTimer — Click to open"
                icon.icon  = new_img
                icon.title = tooltip
            except Exception:
                pass

    threading.Thread(target=tray_update, daemon=True).start()
    icon.run()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = FloatingTimer()

    # Run tray in background thread
    tray_thread = threading.Thread(target=run_tray, args=(app,), daemon=True)
    tray_thread.start()

    app.run()