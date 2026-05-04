"""
TaskbarTimer v2 — Windows 11 Fluent Design
• Rounded corners via DWM API (native Win11)
• Acrylic-style frosted glass backdrop
• Smooth animated progress ring (60fps canvas)
• Scroll-wheel time adjustment
• Keyboard shortcuts
• Toast-style alarm notification
• Snap to taskbar edge on launch
"""

import tkinter as tk
import threading
import time
import math
import re
import ctypes
import ctypes.wintypes
import sys
import os
from PIL import Image, ImageDraw, ImageFont
import pystray

# ────────────────────────────────────────────────────────────────────────────
# Windows 11 DWM rounded corners + dark mode
# ────────────────────────────────────────────────────────────────────────────

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND                   = 2   # rounded corners
DWMWA_BORDER_COLOR             = 34
DWMWA_CAPTION_COLOR             = 35
DWMWA_TEXT_COLOR               = 36

def apply_win11_style(hwnd: int):
    """Apply rounded corners + dark title bar via DWM (Windows 11 only)."""
    try:
        dwm = ctypes.windll.dwmapi
        # Dark mode
        val = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                                  ctypes.byref(val), ctypes.sizeof(val))
        # Rounded corners
        corner = ctypes.c_int(DWMWCP_ROUND)
        dwm.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                                  ctypes.byref(corner), ctypes.sizeof(corner))
    except Exception:
        pass   # graceful fallback on older Windows

def set_click_through(hwnd: int, enable: bool):
    """Toggle click-through (transparent to mouse) on the alarm flash."""
    try:
        GWL_EXSTYLE    = -20
        WS_EX_LAYERED  = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if enable:
            style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    except Exception:
        pass

# ────────────────────────────────────────────────────────────────────────────
# Palette — deep dark glass, ice-blue accent, warm alarm
# ────────────────────────────────────────────────────────────────────────────

C = {
    "bg"       : "#10111a",      # deep navy-black
    "surface"  : "#181922",      # card surface
    "surface2" : "#1f2030",      # elevated surface
    "border"   : "#2c2d3e",      # subtle border
    "accent"   : "#7eb8f7",      # soft ice blue
    "accent_d" : "#4a90d9",      # darker accent for ring track
    "alarm"    : "#f87171",      # warm coral alarm
    "alarm_d"  : "#c0392b",      # deep alarm
    "success"  : "#6ee7b7",      # mint green done
    "text"     : "#e8eaf6",      # off-white
    "muted"    : "#565870",      # muted text
    "muted2"   : "#3a3c52",      # dimmer muted
    "white"    : "#ffffff",
}

FONT_MONO  = ("Consolas",   28, "bold")
FONT_SMALL = ("Segoe UI",    9)
FONT_MED   = ("Segoe UI",   10, "bold")
FONT_TINY  = ("Segoe UI",    8)

# ────────────────────────────────────────────────────────────────────────────
# Shared state
# ────────────────────────────────────────────────────────────────────────────

class TimerState:
    def __init__(self):
        self.total_seconds = 0
        self.remaining     = 0
        self.running       = False
        self.expired       = False
        self.label         = ""
        # animation
        self.display_frac  = 1.0   # smooth 0.0→1.0 ring fill
        self.pulse         = 0.0   # 0.0→1.0 alarm pulse phase

state = TimerState()

# ────────────────────────────────────────────────────────────────────────────
# Tray icon generator
# ────────────────────────────────────────────────────────────────────────────

def _load_font(size):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()

def make_tray_icon(remaining: int, running: bool, expired: bool) -> Image.Image:
    S   = 64
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    if expired:
        bg, ring = (220, 60, 60, 230), (255, 140, 140, 255)
    elif running:
        bg, ring = (16, 17, 26, 230), (126, 184, 247, 255)
    else:
        bg, ring = (24, 25, 34, 200), (86, 88, 112, 200)

    d.ellipse([2, 2, S-2, S-2], fill=bg)

    # progress arc
    if state.total_seconds > 0 and not expired:
        frac   = max(0.0, remaining / state.total_seconds)
        extent = int(360 * frac)
        # track
        d.arc([7, 7, S-7, S-7], 0, 360, fill=(40, 42, 60, 180), width=5)
        if extent > 0:
            d.arc([7, 7, S-7, S-7], -90, -90 + extent, fill=ring, width=5)

    # label
    if expired:
        label = "✓"
    elif running:
        m = remaining // 60
        s = remaining % 60
        label = f"{m}:{s:02}" if m < 60 else f"{m//60}h"
    else:
        label = "⏱"

    fnt  = _load_font(14 if len(label) <= 3 else 11)
    bbox = d.textbbox((0, 0), label, font=fnt)
    tw   = bbox[2] - bbox[0]
    th   = bbox[3] - bbox[1]
    d.text(((S - tw) // 2, (S - th) // 2), label,
           font=fnt, fill=(232, 234, 246, 255))
    return img

# ────────────────────────────────────────────────────────────────────────────
# Main floating window
# ────────────────────────────────────────────────────────────────────────────

class FloatingTimer:
    W, H = 380, 290

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TaskbarTimer")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.97)
        self.root.configure(bg=C["bg"])
        self.root.resizable(False, False)

        # Position: bottom-right just above taskbar
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = sw - self.W - 20
        y  = sh - self.H - 52    # 52 ≈ taskbar height
        self.root.geometry(f"{self.W}x{self.H}+{x}+{y}")

        self._drag_x = self._drag_y = 0
        self._hover_preset = None
        self._fade_alpha   = 0.0
        self._fading_in    = True
        self._last_tick    = time.monotonic()

        self._build_ui()

        # Apply Win11 rounded corners after window is realized
        self.root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        if hwnd == 0:
            hwnd = self.root.winfo_id()
        apply_win11_style(hwnd)
        self._hwnd = hwnd

        # Fade in
        self.root.attributes("-alpha", 0.0)
        self._fade_in()

        self._update_loop()

    # ── Fade ──────────────────────────────────────────────────────────────────

    def _fade_in(self):
        a = self.root.attributes("-alpha")
        if a < 0.97:
            self.root.attributes("-alpha", min(0.97, a + 0.07))
            self.root.after(16, self._fade_in)

    def _fade_out(self, callback):
        a = self.root.attributes("-alpha")
        if a > 0.01:
            self.root.attributes("-alpha", max(0.0, a - 0.08))
            self.root.after(16, lambda: self._fade_out(callback))
        else:
            callback()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = self.root

        # ── Outer border frame (simulates rounded glass border) ───────────────
        outer = tk.Frame(root, bg=C["border"], padx=1, pady=1)
        outer.pack(fill="both", expand=True, padx=0, pady=0)

        inner = tk.Frame(outer, bg=C["bg"])
        inner.pack(fill="both", expand=True)

        # ── Title bar ─────────────────────────────────────────────────────────
        title_bar = tk.Frame(inner, bg=C["surface"], height=36)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)

        # App icon dot
        dot = tk.Canvas(title_bar, width=8, height=8,
                        bg=C["surface"], highlightthickness=0)
        dot.pack(side="left", padx=(14, 4), pady=14)
        dot.create_oval(0, 0, 8, 8, fill=C["accent"], outline="")

        tk.Label(title_bar, text="TaskbarTimer",
                 bg=C["surface"], fg=C["muted"],
                 font=("Segoe UI", 9)).pack(side="left")

        # Window buttons
        for sym, cmd, hover_col in [
            ("×", self._close,    "#c42b1c")
        ]:
            b = tk.Label(title_bar, text=sym, bg=C["surface"], fg=C["muted"],
                         font=("Segoe UI", 13), width=3, cursor="hand2")
            b.pack(side="right", padx=1)
            b.bind("<Button-1>", lambda e, fn=cmd: fn())
            b.bind("<Enter>",    lambda e, w=b, c=hover_col: (
                w.config(bg=c, fg=C["white"])))
            b.bind("<Leave>",    lambda e, w=b: (
                w.config(bg=C["surface"], fg=C["muted"])))

        # Drag
        for w in (title_bar,):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>",     self._drag_move)

        # ── Separator ─────────────────────────────────────────────────────────
        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x")

        # ── Ring canvas ───────────────────────────────────────────────────────
        self.canvas = tk.Canvas(inner, width=380, height=134,
                                bg=C["bg"], highlightthickness=0)
        self.canvas.pack()
        # Scroll wheel on canvas to add/subtract time
        self.canvas.bind("<MouseWheel>", self._on_scroll)

        # ── Preset chips ──────────────────────────────────────────────────────
        chips_frame = tk.Frame(inner, bg=C["bg"])
        chips_frame.pack(fill="x", padx=16, pady=(0, 8))

        self._chip_widgets = []
        presets = [("5m", 300), ("10m", 600), ("15m", 900),
                   ("20m", 1200),("30m", 1800), ("45m", 2700), ("1h", 3600)]
        for label, secs in presets:
            chip = tk.Label(chips_frame, text=label,
                            bg=C["surface2"], fg=C["muted"],
                            font=("Segoe UI", 8, "bold"),
                            padx=9, pady=4, cursor="hand2")
            chip.pack(side="left", padx=2)
            chip.bind("<Button-1>", lambda e, s=secs, l=label: self._preset(s, l))
            chip.bind("<Enter>",    lambda e, w=chip: self._chip_hover(w, True))
            chip.bind("<Leave>",    lambda e, w=chip: self._chip_hover(w, False))
            self._chip_widgets.append(chip)

        # ── Input row ─────────────────────────────────────────────────────────
        inp = tk.Frame(inner, bg=C["bg"])
        inp.pack(fill="x", padx=16, pady=(0, 10))

        # Styled entry container
        entry_bg = tk.Frame(inp, bg=C["surface2"],
                            highlightbackground=C["border"],
                            highlightthickness=1)
        entry_bg.pack(side="left", fill="y")

        self.entry_var = tk.StringVar(value="5:00")
        self.entry = tk.Entry(entry_bg, textvariable=self.entry_var,
                              bg=C["surface2"], fg=C["text"],
                              insertbackground=C["accent"],
                              relief="flat", font=("Segoe UI", 10),
                              width=9, justify="center")
        self.entry.pack(padx=6, pady=5)
        self.entry.bind("<Return>",    lambda e: self._start_from_entry())
        self.entry.bind("<FocusIn>",   lambda e: self._entry_focus(True))
        self.entry.bind("<FocusOut>",  lambda e: self._entry_focus(False))
        self.entry.bind("<MouseWheel>", self._on_entry_scroll)

        # Hint label for accepted formats
        tk.Label(inp, text="5:00 · 25m · 1h30m · 90",
                 bg=C["bg"], fg=C["muted2"],
                 font=("Segoe UI", 7)).pack(side="left", padx=(8, 0))

        # ── Start button ──────────────────────────────────────────────────────
        self.start_btn = tk.Label(inner, text="▶  Start",
                                  bg=C["accent_d"], fg=C["white"],
                                  font=("Segoe UI", 12, "bold"),
                                  pady=12, cursor="hand2")
        self.start_btn.pack(fill="x", padx=16, pady=(0, 6))
        self.start_btn.bind("<Button-1>", lambda e: self._start_from_entry())
        self.start_btn.bind("<Enter>",    lambda e: self.start_btn.config(bg=C["accent"]))
        self.start_btn.bind("<Leave>",    lambda e: self.start_btn.config(bg=C["accent_d"]))

        # ── Control row ───────────────────────────────────────────────────────
        ctrl = tk.Frame(inner, bg=C["bg"])
        ctrl.pack(fill="x", padx=16, pady=(0, 14))

        self.pause_btn = tk.Label(ctrl, text="⏸  Pause",
                                  bg=C["surface2"], fg=C["text"],
                                  font=("Segoe UI", 10, "bold"),
                                  padx=16, pady=18, cursor="hand2")
        self.pause_btn.pack(side="left", padx=(0, 4))
        self.pause_btn.bind("<Button-1>", lambda e: self._toggle_pause())
        self.pause_btn.bind("<Enter>",    lambda e: self.pause_btn.config(fg=C["accent"]))
        self.pause_btn.bind("<Leave>",    lambda e: self.pause_btn.config(
            fg=C["muted2"] if state.expired else C["text"]))

        self.restart_btn = tk.Label(ctrl, text="↺  Restart",
                             bg=C["surface2"], fg=C["muted"],
                             font=("Segoe UI", 10, "bold"),
                             padx=16, pady=18, cursor="hand2")
        self.restart_btn.pack(side="left", padx=4)
        self.restart_btn.bind("<Button-1>", lambda e: self._restart())
        self.restart_btn.bind("<Enter>",    lambda e: self.restart_btn.config(fg=C["accent"]))
        self.restart_btn.bind("<Leave>",    lambda e: self.restart_btn.config(
            fg=C["accent"] if state.expired else C["muted"]))

        # Keyboard shortcuts hint
        kb = tk.Label(ctrl, text="Space=pause  R=restart  ↑↓=±1m",
                      bg=C["bg"], fg=C["muted2"], font=("Segoe UI", 7))
        kb.pack(side="right")

        def _space(e):
            if root.focus_get() is self.entry:
                return   # let spacebar type in the entry
            self._toggle_pause()

        def _r_key(e):
            if root.focus_get() is self.entry:
                return
            self._restart()

        # Global key bindings
        root.bind("<space>",  _space)
        root.bind("<r>",      _r_key)
        root.bind("<R>",      _r_key)
        root.bind("<Up>",     lambda e: self._adjust_time(60))
        root.bind("<Down>",   lambda e: self._adjust_time(-60))
        root.bind("<Escape>", lambda e: self._close())

    # ── Chip hover ────────────────────────────────────────────────────────────

    def _chip_hover(self, widget, on: bool):
        widget.config(
            bg=C["accent_d"] if on else C["surface2"],
            fg=C["white"]    if on else C["muted"],
        )

    def _entry_focus(self, on: bool):
        col = C["accent"] if on else C["border"]
        self.entry.master.config(highlightbackground=col)

    # ── Ring drawing (called every ~16ms for 60fps) ───────────────────────────

    def _draw_ring(self):
        c      = self.canvas
        c.delete("all")
        W, H   = 380, 134
        cx, cy = W // 2, H // 2 + 2
        R_out  = 50   # outer radius of ring
        R_in   = R_out - 11   # ring thickness = 11px
        tick   = time.monotonic()

        # ── Smooth fraction animation ─────────────────────────────────────────
        target = 0.0
        if state.total_seconds > 0 and not state.expired:
            target = max(0.0, state.remaining / state.total_seconds)
        elif state.expired:
            target = 0.0
        # Lerp display_frac toward target
        state.display_frac += (target - state.display_frac) * 0.12
        if abs(state.display_frac - target) < 0.001:
            state.display_frac = target

        frac = state.display_frac

        # ── Glow shadow behind ring ───────────────────────────────────────────
        if state.running and not state.expired:
            glow_col = C["accent_d"]
            for g in range(3, 0, -1):
                rg = R_out + g * 3
                c.create_oval(cx-rg, cy-rg, cx+rg, cy+rg,
                              outline=glow_col, width=1,
                              stipple="gray25" if g == 3 else "gray50")

        # ── Track ring (background) ───────────────────────────────────────────
        c.create_arc(cx-R_out, cy-R_out, cx+R_out, cy+R_out,
                     start=0, extent=359.9,
                     style="arc", outline=C["muted2"], width=11)

        # ── Progress arc ─────────────────────────────────────────────────────
        if state.expired:
            # Pulsing alarm ring
            pulse = (math.sin(tick * 4) + 1) / 2
            alarm_col = self._lerp_color(C["alarm_d"], C["alarm"], pulse)
            c.create_arc(cx-R_out, cy-R_out, cx+R_out, cy+R_out,
                         start=90, extent=-359.9,
                         style="arc", outline=alarm_col, width=11)
        elif frac > 0.001:
            extent = frac * 359.9
            # Color shifts warm as time runs low
            if frac > 0.4:
                ring_col = C["accent"]
            elif frac > 0.15:
                ring_col = "#f0c060"   # amber warning
            else:
                ring_col = C["alarm"]  # red urgent
            c.create_arc(cx-R_out, cy-R_out, cx+R_out, cy+R_out,
                         start=90, extent=-extent,
                         style="arc", outline=ring_col, width=11)

        # ── Center time text ──────────────────────────────────────────────────
        if state.expired:
            pulse = (math.sin(tick * 3) + 1) / 2
            txt_col = self._lerp_color(C["alarm_d"], C["alarm"], pulse)
            time_str = "DONE"
            sub_str  = "Timer finished!"
        elif state.total_seconds == 0:
            txt_col  = C["muted"]
            time_str = "--:--"
            sub_str  = "scroll ↑↓ to set time"
        else:
            txt_col  = C["text"]
            r        = state.remaining
            h_       = r // 3600
            m_       = (r % 3600) // 60
            s_       = r % 60
            time_str = f"{h_}:{m_:02}:{s_:02}" if h_ else f"{m_:02}:{s_:02}"
            sub_str  = state.label if state.label else ("Running" if state.running else "Paused")

        c.create_text(cx, cy - 6, text=time_str,
                      fill=txt_col, font=FONT_MONO, anchor="center")
        c.create_text(cx, cy + 22, text=sub_str,
                      fill=C["muted"], font=FONT_TINY, anchor="center")

        # ── Scroll hint (only when no timer set) ──────────────────────────────
        if state.total_seconds == 0 and not state.running:
            c.create_text(cx, cy - 38, text="⏱",
                          fill=C["muted2"], font=("Segoe UI", 18), anchor="center")

    @staticmethod
    def _lerp_color(c1: str, c2: str, t: float) -> str:
        """Linear interpolate between two hex colors."""
        r1, g1, b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
        r2, g2, b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
        r = int(r1 + (r2-r1)*t)
        g = int(g1 + (g2-g1)*t)
        b = int(b1 + (b2-b1)*t)
        return f"#{r:02x}{g:02x}{b:02x}"

    # ── Timer logic ───────────────────────────────────────────────────────────

    def _parse_time(self, s: str) -> int:
        s = s.lower().strip()
        try:
            if ":" in s:
                parts = s.split(":")
                if len(parts) == 2:
                    return int(parts[0]) * 60 + int(parts[1])
                if len(parts) == 3:
                    return int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
            total = 0
            for val, unit in re.findall(r"(\d+)\s*([hms]?)", s):
                v = int(val)
                if   unit == "h": total += v * 3600
                elif unit == "m": total += v * 60
                elif unit == "s": total += v
                else:             total += v * 60
            return total
        except Exception:
            return 0

    def _set_timer(self, seconds: int, label: str = ""):
        state.total_seconds   = seconds
        state.remaining       = seconds
        state.running         = False
        state.expired         = False
        state.label           = label
        state.display_frac    = 1.0
        self._last_tick       = time.monotonic()
        self._update_ui_state()

    def _start(self):
        state.running  = True
        state.expired  = False
        self._last_tick = time.monotonic()
        self._update_ui_state()

    def _preset(self, seconds: int, label: str):
        self._set_timer(seconds, label)
        self._start()

    def _start_from_entry(self):
        raw  = self.entry_var.get().strip()
        secs = self._parse_time(raw)
        if secs > 0:
            self._set_timer(secs, raw)
            self._start()
        else:
            # Flash entry red briefly
            self.entry.config(fg=C["alarm"])
            self.root.after(600, lambda: self.entry.config(fg=C["text"]))

    def _toggle_pause(self):
        if state.total_seconds == 0:
            return
        if state.expired:
            self._restart()
            return
        state.running = not state.running
        if state.running:
            # Reset tick anchor so paused time isn't counted
            self._last_tick = time.monotonic()
        self._update_ui_state()

    def _reset(self):
        state.remaining    = state.total_seconds
        state.running      = False
        state.expired      = False
        state.display_frac = 1.0
        state.label        = ""
        self._last_tick    = time.monotonic()
        self._update_ui_state()

    def _restart(self):
        """Reset back to full duration and immediately start running."""
        state.remaining    = state.total_seconds
        state.running      = True
        state.expired      = False
        state.display_frac = 1.0
        self._last_tick    = time.monotonic()
        self._update_ui_state()


    def _adjust_time(self, delta: int):
        """Add/subtract seconds. Works both before and during countdown."""
        if state.expired:
            return
        if state.total_seconds == 0:
            # Create a new timer from scroll
            new_total = max(60, delta)
            state.total_seconds = new_total
            state.remaining     = new_total
            state.display_frac  = 1.0
        else:
            new_rem   = max(0, min(state.total_seconds + delta,
                                   state.remaining + delta))
            # Also adjust total so ring doesn't look broken
            if not state.running:
                state.total_seconds = max(60, state.total_seconds + delta)
                state.remaining     = state.total_seconds
            else:
                state.remaining = max(0, state.remaining + delta)
        # Update entry box to reflect new time
        r = state.remaining
        h = r // 3600
        m = (r % 3600) // 60
        s = r % 60
        self.entry_var.set(f"{h}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}")

    def _on_scroll(self, event):
        delta = 60 if event.delta > 0 else -60
        self._adjust_time(delta)

    def _on_entry_scroll(self, event):
        delta = 60 if event.delta > 0 else -60
        self._adjust_time(delta)

    def _update_ui_state(self):
        if state.expired:
            self.pause_btn.config(text="⏸  Pause",   fg=C["muted2"])
            self.restart_btn.config(text="↺  Restart", fg=C["accent"])
            self.start_btn.config(text="↺  New Timer", bg=C["alarm_d"])
            self.start_btn.unbind("<Button-1>")
            self.start_btn.bind("<Button-1>", lambda e: self._restart())
        elif state.running:
            self.pause_btn.config(text="⏸  Pause",  fg=C["text"])
            self.restart_btn.config(text="↺  Restart", fg=C["muted"])
            self.start_btn.config(text="⏸  Pause", bg=C["accent_d"])
            self.start_btn.unbind("<Button-1>")
            self.start_btn.bind("<Button-1>", lambda e: self._toggle_pause())
        else:
            is_paused = state.total_seconds > 0 and state.remaining < state.total_seconds
            lbl = "▶  Resume" if state.total_seconds > 0 else "▶  Start"
            self.pause_btn.config(text=lbl,           fg=C["text"])
            self.restart_btn.config(text="↺  Restart", fg=C["muted"])
            if is_paused:
                self.start_btn.config(text="▶  Resume", bg=C["accent_d"])
                self.start_btn.unbind("<Button-1>")
                self.start_btn.bind("<Button-1>", lambda e: self._start())
            else:
                self.start_btn.config(text="▶  Start",  bg=C["accent_d"])
                self.start_btn.unbind("<Button-1>")
                self.start_btn.bind("<Button-1>", lambda e: self._start_from_entry())

    # ── Alarm flash overlay ───────────────────────────────────────────────────

    def _fire_alarm(self):
        # Beep in background
        def _beep():
            try:
                import winsound
                for freq, dur in [(660,200),(880,200),(1100,350),
                                  (880,200),(660,300)]:
                    winsound.Beep(freq, dur)
                    time.sleep(0.05)
            except Exception:
                pass
        threading.Thread(target=_beep, daemon=True).start()

        # Brief window flash (red tint alpha pulse)
        self._alarm_flash(5)

    def _alarm_flash(self, n: int):
        if n <= 0:
            self.root.attributes("-alpha", 0.97)
            return
        a = 0.97 if n % 2 == 0 else 0.6
        self.root.attributes("-alpha", a)
        self.root.after(180, lambda: self._alarm_flash(n - 1))

    # ── Main update loop (16ms ≈ 60fps for smooth ring) ───────────────────────

    def _update_loop(self):
        now = time.monotonic()

        # Accurate 1-second tick using wall clock, not frame counting
        if state.running and not state.expired:
            elapsed = now - self._last_tick
            if elapsed >= 1.0:
                ticks = int(elapsed)
                self._last_tick += ticks
                if state.remaining > ticks:
                    state.remaining -= ticks
                else:
                    state.remaining = 0

            if state.remaining == 0:
                state.expired  = True
                state.running  = False
                self._last_tick = now
                self._update_ui_state()
                self._fire_alarm()

        self._draw_ring()
        self.root.after(16, self._update_loop)   # ~60fps

    # ── Window controls ───────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def _drag_move(self, event):
        self.root.geometry(f"+{event.x_root - self._drag_x}"
                           f"+{event.y_root - self._drag_y}")

    def _close(self):
        self._fade_out(self.root.withdraw)

    def _minimize(self):
        self._fade_out(self.root.withdraw)

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self._fade_in()

    def run(self):
        self.root.mainloop()


# ────────────────────────────────────────────────────────────────────────────
# System tray
# ────────────────────────────────────────────────────────────────────────────

def run_tray(app: FloatingTimer):
    icon_img = make_tray_icon(0, False, False)

    def ui(fn):
        """Schedule fn on the Tk thread."""
        return lambda icon, item: app.root.after(0, fn)

    def quick_start(secs, label):
        def _do():
            app._set_timer(secs, label)
            app._start()
            app.show()
        return lambda icon, item: app.root.after(0, _do)

    menu = pystray.Menu(
        pystray.MenuItem("Show Timer",    ui(app.show), default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quick Start", pystray.Menu(
            pystray.MenuItem("5 minutes",            quick_start(300,  "5m")),
            pystray.MenuItem("10 minutes",           quick_start(600,  "10m")),
            pystray.MenuItem("15 minutes",           quick_start(900,  "15m")),
            pystray.MenuItem("20 minutes",           quick_start(1200, "20m")),
            pystray.MenuItem("30 minutes",           quick_start(1800, "30m")),
            pystray.MenuItem("45 minutes",           quick_start(2700, "45m")),
            pystray.MenuItem("1 hour",               quick_start(3600, "1h")),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Pause / Resume", ui(app._toggle_pause)),
        pystray.MenuItem("Restart",        ui(app._restart)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", lambda icon, item: (
            icon.stop(), app.root.after(0, app.root.destroy))),
    )

    icon = pystray.Icon("TaskbarTimer", icon_img, "TaskbarTimer", menu)

    def _refresh():
        while True:
            time.sleep(1)
            try:
                icon.icon  = make_tray_icon(state.remaining,
                                            state.running, state.expired)
                if state.running:
                    r = state.remaining
                    h = r // 3600; m = (r%3600)//60; s = r%60
                    icon.title = f"⏱ {h}:{m:02}:{s:02}" if h else f"⏱ {m:02}:{s:02}"
                elif state.expired:
                    icon.title = "✓ Timer finished!"
                else:
                    icon.title = "TaskbarTimer"
            except Exception:
                pass

    threading.Thread(target=_refresh, daemon=True).start()
    icon.run()


# ────────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = FloatingTimer()
    threading.Thread(target=run_tray, args=(app,), daemon=True).start()
    app.run()