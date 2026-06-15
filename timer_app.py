import sys
import winreg
import tkinter as tk
import threading
import time
import math
import re
import json
import ctypes
import ctypes.wintypes
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for Python versions < 3.9
    ZoneInfo = None
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    import pystray
    TRAY_OK = True
except ImportError:
    TRAY_OK = False

# ────────────────────────────────────────────────────────────────────────────
# Tray icon generator
# ────────────────────────────────────────────────────────────────────────────

def _load_font(size):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try: return ImageFont.truetype(name, size)
        except Exception: pass
    return ImageFont.load_default()

# Forward declaration for make_tray_icon to use the global state object
state = None


# -- Win11 DWM helpers --
DWMWA_USE_IMMERSIVE_DARK_MODE   = 70
DWMWA_WINDOW_CORNER_PREFERENCE  = 33
DWMWCP_ROUND                    = 2

def apply_win11_style(hwnd: int):
    try:
        dwm = ctypes.windll.dwmapi
        val = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                                  ctypes.byref(val), ctypes.sizeof(val))
        corner = ctypes.c_int(DWMWCP_ROUND)
        dwm.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                                  ctypes.byref(corner), ctypes.sizeof(corner))
    except Exception:
        pass

def make_tray_icon(remaining: int, running: bool, expired: bool, logo: Image.Image = None) -> Image.Image:
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
    if state.total > 0 and not expired: # Use state.total instead of state.total_seconds
        frac   = max(0.0, remaining / state.total)
        extent = int(360 * frac)
        # track
        d.arc([7, 7, S-7, S-7], 0, 360, fill=(40, 42, 60, 180), width=5)
        if extent > 0:
            d.arc([7, 7, S-7, S-7], -90, -90 + extent, fill=ring, width=5)

    # label
    if expired: label = "✓"
    elif running:
        m = remaining // 60; s = remaining % 60
        label = f"{m}:{s:02}" if m < 60 else f"{m//60}h"
    else: 
        if logo:
            img.paste(logo, (14, 14), logo if logo.mode == 'RGBA' else None)
            return img
        label = "⏱"

    fnt  = _load_font(14 if len(label) <= 3 else 11)
    bbox = d.textbbox((0, 0), label, font=fnt)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((S - tw) // 2, (S - th) // 2), label, font=fnt, fill=(232, 234, 246, 255))
    return img

# -- Palette --
C = {
    "bg"       : "#10111a",
    "surface"  : "#181922",
    "surface2" : "#1f2030",
    "border"   : "#2c2d3e",
    "accent"   : "#7eb8f7",
    "accent_d" : "#4a90d9",
    "alarm"    : "#f87171",
    "alarm_d"  : "#c0392b",
    "success"  : "#6ee7b7",
    "warn"     : "#f0c060",
    "text"     : "#e8eaf6",
    "muted"    : "#565870",
    "muted2"   : "#3a3c52",
    "white"    : "#ffffff",
}

WORLD_ZONES = [
    ("Honolulu", "Pacific/Honolulu"), ("Anchorage", "America/Anchorage"), ("Vancouver", "America/Vancouver"),
    ("Los Angeles", "America/Los_Angeles"), ("Phoenix", "America/Phoenix"), ("Denver", "America/Denver"),
    ("Chicago", "America/Chicago"), ("Mexico City", "America/Mexico_City"), ("New York", "America/New_York"),
    ("Toronto", "America/Toronto"), ("Caracas", "America/Caracas"), ("Santiago", "America/Santiago"),
    ("São Paulo", "America/Sao_Paulo"), ("Buenos Aires", "America/Argentina/Buenos_Aires"), ("London", "Europe/London"),
    ("Paris", "Europe/Paris"), ("Berlin", "Europe/Berlin"), ("Lagos", "Africa/Lagos"), ("Cairo", "Africa/Cairo"),
    ("Johannesburg", "Africa/Johannesburg"), ("Jerusalem", "Asia/Jerusalem"), ("Moscow", "Europe/Moscow"),
    ("Istanbul", "Europe/Istanbul"), ("Nairobi", "Africa/Nairobi"), ("Dubai", "Asia/Dubai"), ("Karachi", "Asia/Karachi"),
    ("Mumbai", "Asia/Kolkata"), ("Dhaka", "Asia/Dhaka"), ("Bangkok", "Asia/Bangkok"), ("Jakarta", "Asia/Jakarta"),
    ("Beijing", "Asia/Shanghai"), ("Singapore", "Asia/Singapore"), ("Perth", "Australia/Perth"), ("Tokyo", "Asia/Tokyo"),
    ("Seoul", "Asia/Seoul"), ("Adelaide", "Australia/Adelaide"), ("Sydney", "Australia/Sydney"),
    ("Auckland", "Pacific/Auckland"), ("Fiji", "Pacific/Fiji")
]

CONFIG_PATH = Path.home() / ".timer_alarm_v3.json"

# -- Custom Rounded Button --
class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, callback, width=100, height=40, radius=20, color=C["accent_d"], hover_color=C["accent"], fg=C["white"], hover_fg=None, font=("Segoe UI", 10, "bold")):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, cursor="hand2")
        self.callback = callback
        self.color = color
        self.hover_color = hover_color
        self.fg = fg
        self.hover_fg = hover_fg if hover_fg else fg
        self._hovering = False
        self.radius = radius
        self.text = text
        self.font = font

        # Ensure the canvas is updated to get correct width/height for drawing
        self.update_idletasks() # This might be called too early, before widget is fully mapped.
        self.bind("<Button-1>", lambda e: self.callback())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.draw(self.color)

    def draw(self, fill):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w == 1 or h == 1: # If not yet mapped, use requested size
            w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        r = self.radius
        self.create_oval(0, 0, r*2, r*2, fill=fill, outline="")
        self.create_oval(w-r*2, 0, w, r*2, fill=fill, outline="")
        self.create_oval(0, h-r*2, r*2, h, fill=fill, outline="")
        self.create_oval(w-r*2, h-r*2, w, h, fill=fill, outline="")
        self.create_rectangle(r, 0, w-r, h, fill=fill, outline="")
        self.create_rectangle(0, r, w, h-r, fill=fill, outline="")
        text_col = self.hover_fg if self._hovering else self.fg
        self.create_text(w/2, h/2, text=self.text, fill=text_col, font=self.font)

    def _on_enter(self, e):
        self._hovering = True
        self.draw(self.hover_color)

    def _on_leave(self, e):
        self._hovering = False
        self.draw(self.color)
    
    def config_text(self, new_text, new_color=None):
        self.text = new_text
        if new_color: self.color = new_color
        self.draw(self.color) # Redraw with new text/color

# -- Shared state & Helpers --
class TimerState:
    def __init__(self):
        self.total = 0
        self.remaining = 0.0
        self.running = False
        self.expired = False
        self.label = ""
        self.frac = 1.0

state = TimerState() # Global state object

def sort_alarms(alarms):
    return sorted(alarms, key=lambda x: [int(p) for p in x["time"].split(":")])

def load_alarms():
    try:
        if CONFIG_PATH.exists(): 
            return sort_alarms(json.loads(CONFIG_PATH.read_text()))
    except: pass # Graceful fallback if config is corrupted or missing
    return sort_alarms([{"time": "07:00", "label": "Good morning", "on": True}])

def save_alarms(alarms):
    try: CONFIG_PATH.write_text(json.dumps(alarms))
    except: pass

def lerp_color(c1, c2, t):
    r1,g1,b1 = int(c1[1:3],16),int(c1[3:5],16),int(c1[5:7],16)
    r2,g2,b2 = int(c2[1:3],16),int(c2[3:5],16),int(c2[5:7],16)
    return f"#{int(r1+(r2-r1)*t):02x}{int(g1+(g2-g1)*t):02x}{int(b1+(b2-b1)*t):02x}"

def fmt_sec(s):
    s = max(0, int(s))
    h, r = divmod(s, 3600); m, s = divmod(r, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"

def fmt_ms(ms):
    t = ms / 1000; m = int(t//60); s = int(t%60); f = int((t%1)*10)
    return f"{m:02}:{s:02}.{f}"

def parse_time(raw: str) -> int:
    s = raw.lower().strip()
    try:
        if ":" in s:
            parts = s.split(":")
            if len(parts) == 2: return int(parts[0])*60 + int(parts[1])
            if len(parts) == 3: return int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
        total = 0
        for val, unit in re.findall(r"(\d+)\s*([hms]?)", s):
            v = int(val)
            if unit == "h": total += v*3600
            elif unit == "m": total += v*60
            elif unit == "s": total += v
            else: total += v*60
        return total
    except: return 0

_alarm_stop_event = threading.Event()

def beep_alarm(continuous=False):
    def _b():
        _alarm_stop_event.clear()
        try:
            import winsound
            while True:
                for freq, dur in [(660,160),(880,160),(1100,280),(880,160),(660,240)]:
                    if _alarm_stop_event.is_set(): return
                    winsound.Beep(freq, dur); time.sleep(0.04)
                if not continuous: break
                time.sleep(1)
        except: pass
    threading.Thread(target=_b, daemon=True).start()

# -- Main App --
class App(tk.Tk):
    W, H = 400, 480 # Increased height to accommodate new elements

    def __init__(self):
        super().__init__()
        self.overrideredirect(True)
        self.attributes("-topmost", True, "-alpha", 0.0)
        self.configure(bg=C["bg"])
        
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{self.W}x{self.H}+{sw-self.W-20}+{sh-self.H-56}")

        self._drag_x = self._drag_y = 0
        self._last_tick = time.monotonic()
        self._sw_running = False
        self._sw_elapsed = 0.0
        self._sw_laps = []
        self.alarms = load_alarms() # Load alarms from config
        self._alarm_last = ""
        self._ringing = False
        self._snooze_time = None
        self._use_12hr_format = False # Default to 24-hour format

        # Logo handling
        self.logo_img = None
        self.tk_logo = None
        logo_path = Path(__file__).parent / "TaskTimer_logo.svg"
        if logo_path.exists():
            try:
                # Note: Pillow requires extra plugins for SVG support. 
                # This logic loads the logo if available.
                full_logo = Image.open(logo_path)
                self.logo_img = full_logo.resize((36, 36), Image.Resampling.LANCZOS)
                logo_sm = full_logo.resize((18, 18), Image.Resampling.LANCZOS)
                self.tk_logo = ImageTk.PhotoImage(logo_sm)
                self.iconphoto(False, self.tk_logo)
            except Exception: pass

        self._build_ui()
        self._apply_win11()
        self._fade_in()
        self._main_loop()
        self._alarm_loop()
        self._start_tray_icon() # Start the system tray icon

    def _apply_win11(self):
        self.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
        apply_win11_style(hwnd)

    def _fade_in(self):
        a = self.attributes("-alpha")
        if a < 0.96:
            self.attributes("-alpha", min(0.96, a+0.08))
            self.after(14, self._fade_in)

    def toggle_visibility(self):
        if self.state() == "normal":
            self.withdraw()
        else:
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)

    def destroy(self):
        self._stop_tray_icon() # Ensure tray icon is stopped
        super().destroy()

    def _build_ui(self):
        outer = tk.Frame(self, bg=C["border"], padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        self._inner = tk.Frame(outer, bg=C["bg"])
        self._inner.pack(fill="both", expand=True)

        # Title bar
        bar = tk.Frame(self._inner, bg=C["surface"], height=34)
        bar.pack(fill="x"); bar.pack_propagate(False)
        
        if self.tk_logo:
            tk.Label(bar, image=self.tk_logo, bg=C["surface"]).pack(side="left", padx=(10, 0))
            
        tk.Label(bar, text=" TaskbarTimer", bg=C["surface"], fg=C["muted"], font=("Segoe UI",9)).pack(side="left")
        
        for sym, fn, hcol in [("×", self.destroy, "#c42b1c"), ("−", self.withdraw, C["surface2"])]:
            b = tk.Label(bar, text=sym, bg=C["surface"], fg=C["muted"], font=("Segoe UI",13), width=3, cursor="hand2", anchor="center")
            b.pack(side="right")
            b.bind("<Button-1>", lambda e, f=fn: f())

        # Time format toggle button
        self._format_btn = tk.Label(bar, text="12h" if self._use_12hr_format else "24h", 
                                    bg=C["surface"], fg=C["muted"], font=("Segoe UI", 9, "bold"), width=4, cursor="hand2")
        self._format_btn.pack(side="right")
        self._format_btn.bind("<Button-1>", lambda e: self._toggle_time_format())

        bar.bind("<ButtonPress-1>", self._drag_start)
        bar.bind("<B1-Motion>", self._drag_move)

        # Tabs
        self._tab_frame = tk.Frame(self._inner, bg=C["surface"], height=45) # Increased height
        self._tab_frame.pack(fill="x")
        self._tab_btns = {}
        for name in ("Timer","Stopwatch","Alarm","World"):
            b = tk.Label(self._tab_frame, text=name.upper(), bg=C["surface"], fg=C["muted"], font=("Segoe UI",11,"bold"), cursor="hand2") # Increased font size
            b.pack(side="left", expand=True, fill="both")
            b.bind("<Button-1>", lambda e, n=name.lower(): self._switch_tab(n))
            self._tab_btns[name.lower()] = b

        # Panels
        self._build_timer_panel()
        self._build_stopwatch_panel()
        self._build_alarm_panel()
        self._build_world_panel()
        self._switch_tab("timer")

    def _drag_start(self, e): self._drag_x=e.x_root-self.winfo_x(); self._drag_y=e.y_root-self.winfo_y()
    def _drag_move(self, e): self.geometry(f"+{e.x_root-self._drag_x}+{e.y_root-self._drag_y}")

    def _toggle_time_format(self):
        t_str = self._a_time_var.get().strip()
        self._use_12hr_format = not self._use_12hr_format
        
        try:
            if self._use_12hr_format:
                # 24h -> 12h
                dt = datetime.strptime(t_str, "%H:%M")
                self._a_time_var.set(dt.strftime("%I:%M"))
                self._ampm_btn.config_text(dt.strftime("%p"))
                self._ampm_btn.pack(side="left", padx=2, after=self._a_time_entry)
            else:
                # 12h -> 24h
                full_t = f"{t_str} {self._ampm_btn.text}"
                dt = datetime.strptime(full_t, "%I:%M %p")
                self._a_time_var.set(dt.strftime("%H:%M"))
                self._ampm_btn.pack_forget()
        except Exception:
            now = datetime.now()
            self._a_time_var.set(now.strftime("%I:%M" if self._use_12hr_format else "%H:%M"))
            if self._use_12hr_format:
                self._ampm_btn.config_text(now.strftime("%p"))
                self._ampm_btn.pack(side="left", padx=2, after=self._a_time_entry)
            else: self._ampm_btn.pack_forget()

        self._format_btn.config(text="12h" if self._use_12hr_format else "24h")
        self._alarm_render()
        self._tick_world() # Immediate refresh for world clocks
        
    def _toggle_ampm(self):
        new_val = "PM" if self._ampm_btn.text == "AM" else "AM"
        self._ampm_btn.config_text(new_val)

    def _switch_tab(self, name):
        panels = {"timer": self._timer_panel, "stopwatch": self._sw_panel, "alarm": self._alarm_panel, "world": self._world_panel}
        for k, p in panels.items(): 
            if k == name: p.pack(fill="both", expand=True)
            else: p.pack_forget()
        for k, b in self._tab_btns.items():
            # Update button appearance based on active tab
            if k == name:
                b.config(bg=C["surface2"], fg=C["accent"])
            else:
                b.config(fg=C["accent"] if k==name else C["muted"], bg=C["surface2"] if k==name else C["surface"])

    # -- TIMER PANEL (Consolidated) --
    def _build_timer_panel(self):
        p = self._timer_panel = tk.Frame(self._inner, bg=C["bg"])
        self.ring_canvas = tk.Canvas(p, width=400, height=160, bg=C["bg"], highlightthickness=0)
        self.ring_canvas.pack()

        # Rounded Presets
        cf = tk.Frame(p, bg=C["bg"]); cf.pack(pady=10)
        for label, secs in [("5m",300),("15m",900),("30m",1800),("1h",3600)]:
            btn = RoundedButton(cf, label, lambda s=secs, l=label: self._preset(s, l), width=60, height=30, radius=15, color=C["surface2"], fg=C["muted"])
            btn.pack(side="left", padx=4)

        # Entry
        self._entry_var = tk.StringVar(value="5:00")
        eb = tk.Frame(p, bg=C["surface2"], padx=10, pady=5)
        eb.pack(pady=10)
        tk.Entry(eb, textvariable=self._entry_var, bg=C["surface2"], fg=C["text"], relief="flat", font=("Segoe UI",14), width=8, justify="center", insertbackground=C["accent"]).pack()

        # Primary Rounded Button
        self.main_btn = RoundedButton(p, "START TIMER", self._start_from_entry, width=240, height=50, radius=25)
        self.main_btn.pack(pady=10)

        # Secondary Controls
        ctrl_f = tk.Frame(p, bg=C["bg"])
        ctrl_f.pack()
        self.restart_btn = tk.Label(ctrl_f, text="RESTART", bg=C["bg"], fg=C["muted2"], font=("Segoe UI",8,"bold"), cursor="hand2")
        self.restart_btn.pack(side="left", padx=10)
        self.restart_btn.bind("<Button-1>", lambda e: self._restart())

        self.reset_btn = tk.Label(ctrl_f, text="RESET", bg=C["bg"], fg=C["muted2"], font=("Segoe UI",8,"bold"), cursor="hand2")
        self.reset_btn.pack(side="left", padx=10)
        self.reset_btn.bind("<Button-1>", lambda e: self._reset_timer())

    def _preset(self, secs, label):
        if self._ringing: self._dismiss_ringing()
        state.total = secs; state.remaining = float(secs); state.running = True; state.expired = False
        state.label = label; self._last_tick = time.monotonic()
        self._update_ui_state()

    def _start_from_entry(self):
        if self._ringing:
            self._dismiss_ringing()
            return
        if state.running:
            state.running = False
        elif state.expired:
            self._restart()
        elif state.total > 0 and 0 < state.remaining < state.total:
            state.running = True
            self._last_tick = time.monotonic()
        else:
            secs = parse_time(self._entry_var.get())
            if secs > 0:
                state.total = secs; state.remaining = float(secs); state.running = True; state.expired = False
                self._last_tick = time.monotonic()
            else: # Invalid input
                self._entry_var.set("Invalid!")
                self.after(1000, lambda: self._entry_var.set("5:00")) # Reset after 1 sec
        self._update_ui_state()

    def _restart(self):
        if state.total > 0: # Only restart if a timer was previously set
            state.remaining = float(state.total); state.running = True; state.expired = False
            self._last_tick = time.monotonic(); self._update_ui_state()

    def _reset_timer(self):
        state.running = False
        state.expired = False
        state.remaining = float(state.total)
        self._update_ui_state()

    def _dismiss_ringing(self):
        """Stop the sound and clear ringing/expired states."""
        self._ringing = False
        self._snooze_time = None
        state.expired = False
        _alarm_stop_event.set()
        self._update_ui_state()
        self._alarm_render()

    def _snooze_ringing(self):
        """Silence the alarm and schedule it to fire again in 9 minutes."""
        self._ringing = False
        self._snooze_time = datetime.now() + timedelta(minutes=9)
        _alarm_stop_event.set()
        self._update_ui_state()
        self._alarm_render()

    def _update_ui_state(self):
        if state.expired or self._ringing:
            text = "DISMISS ALARM" if self._ringing else "DISMISS"
            self.main_btn.config_text(text, C["alarm_d"])
            self.restart_btn.config(fg=C["text"])
            self.reset_btn.config(fg=C["text"])
        elif state.running: # Timer is running
            self.main_btn.config_text("PAUSE", C["surface2"])
            self.restart_btn.config(fg=C["text"])
            self.reset_btn.config(fg=C["text"])
        else:
            if state.total > 0 and 0 < state.remaining < state.total:
                self.main_btn.config_text("RESUME", C["accent_d"])
            else:
                self.main_btn.config_text("START TIMER", C["accent_d"])
            self.restart_btn.config(fg=C["text"] if state.total > 0 else C["muted2"])
            self.reset_btn.config(fg=C["text"] if state.total > 0 else C["muted2"])

    def _main_loop(self):
        now = time.monotonic()
        if state.running and not state.expired:
            elapsed = now - self._last_tick
            if elapsed >= 1.0:
                self._last_tick += 1.0
                state.remaining = max(0.0, state.remaining - 1)
            if state.remaining <= 0:
                state.remaining = 0; state.expired = True; state.running = False
                beep_alarm(); self._update_ui_state()
        self._draw_ring()
        self.after(16, self._main_loop)

    def _draw_ring(self):
        c = self.ring_canvas; c.delete("all")
        cx, cy, R = 200, 85, 60
        target = max(0.0, state.remaining / state.total) if state.total > 0 else 0
        state.frac += (target - state.frac) * 0.1 # Smooth animation
        
        c.create_oval(cx-R, cy-R, cx+R, cy+R, outline=C["muted2"], width=8)
        if state.frac > 0:
            col = C["alarm"] if state.expired else C["accent"]
            extent = -359.9 if state.expired else -(state.frac * 359.9)
            c.create_arc(cx-R, cy-R, cx+R, cy+R, start=90, extent=extent, style="arc", outline=col, width=8)
        
        txt = "RINGING!" if self._ringing else ("DONE" if state.expired else (fmt_sec(state.remaining) if state.total > 0 else "--:--"))
        c.create_text(cx, cy, text=txt, fill=C["text"], font=("Consolas", 24, "bold"))

    # -- STOPWATCH PANEL (Simplified) --
    def _build_stopwatch_panel(self):
        p = self._sw_panel = tk.Frame(self._inner, bg=C["bg"])
        self._sw_disp = tk.Label(p, text="00:00.0", bg=C["bg"], fg=C["accent"], font=("Consolas", 42, "bold"))
        self._sw_disp.pack(pady=20)

        # Control Buttons
        btn_f = tk.Frame(p, bg=C["bg"])
        btn_f.pack(pady=5)

        self.sw_btn = RoundedButton(btn_f, "START", self._sw_toggle, width=120, height=44, radius=22)
        self.sw_btn.pack(side="left", padx=5)

        self.sw_lap_btn = RoundedButton(btn_f, "LAP", self._sw_lap, width=120, height=44, radius=22, color=C["surface2"], fg=C["muted"])
        self.sw_lap_btn.pack(side="left", padx=5)

        self.sw_reset = tk.Label(p, text="RESET", bg=C["bg"], fg=C["muted2"], font=("Segoe UI",8,"bold"), cursor="hand2")
        self.sw_reset.pack()
        self.sw_reset.bind("<Button-1>", lambda e: self._sw_clear())

        # Lap List
        container = tk.Frame(p, bg=C["bg"])
        container.pack(fill="both", expand=True, padx=20, pady=10)

        self._sw_canvas = tk.Canvas(container, bg=C["bg"], highlightthickness=0)
        self._sw_scrollbar = tk.Scrollbar(container, orient="vertical", command=self._sw_canvas.yview)
        self._sw_lap_list = tk.Frame(self._sw_canvas, bg=C["bg"])

        self._sw_canvas.create_window((0, 0), window=self._sw_lap_list, anchor="nw", width=340)
        self._sw_canvas.configure(yscrollcommand=self._sw_scrollbar.set)
        self._sw_canvas.pack(side="left", fill="both", expand=True)
        self._sw_scrollbar.pack(side="right", fill="y")
        self._sw_lap_list.bind("<Configure>", lambda e: self._sw_canvas.configure(scrollregion=self._sw_canvas.bbox("all")))
        self._sw_canvas.bind("<MouseWheel>", self._on_sw_scroll)
        self._sw_lap_list.bind("<MouseWheel>", self._on_sw_scroll)

    def _sw_toggle(self):
        self._sw_running = not self._sw_running
        if self._sw_running:
            self._sw_start = time.time() - self._sw_elapsed
            self.sw_btn.config_text("PAUSE", C["surface2"])
            self.sw_lap_btn.config_text("LAP", C["accent_d"])
            self._sw_tick()
        else:
            self.sw_btn.config_text("RESUME", C["accent_d"])
            self.sw_lap_btn.config_text("LAP", C["surface2"])

    def _sw_lap(self):
        if self._sw_running:
            self._sw_laps.append(self._sw_elapsed)
            self._render_laps()

    def _render_laps(self):
        # Preserve scroll position
        y_scroll = self._sw_canvas.yview()[0]

        for w in self._sw_lap_list.winfo_children(): w.destroy()
        for i, lap_time in enumerate(reversed(self._sw_laps)):
            idx = len(self._sw_laps) - i
            f = tk.Frame(self._sw_lap_list, bg=C["surface"], pady=6)
            f.pack(fill="x", pady=1)
            l1 = tk.Label(f, text=f"Lap {idx}", bg=C["surface"], fg=C["muted"], font=("Segoe UI", 9))
            l1.pack(side="left", padx=15)
            l2 = tk.Label(f, text=fmt_ms(lap_time*1000), bg=C["surface"], fg=C["text"], font=("Consolas", 11))
            l2.pack(side="right", padx=15)

            # Ensure children widgets also propagate scroll events
            for widget in (f, l1, l2):
                widget.bind("<MouseWheel>", self._on_sw_scroll)

        # Restore scroll position
        self._sw_lap_list.update_idletasks()
        self._sw_canvas.yview_moveto(y_scroll)

    def _sw_tick(self):
        if not self._sw_running: return
        self._sw_elapsed = time.time() - self._sw_start
        self._sw_disp.config(text=fmt_ms(self._sw_elapsed*1000))
        self.after(80, self._sw_tick)

    def _sw_clear(self):
        self._sw_running = False; self._sw_elapsed = 0.0; self._sw_laps = []
        self._sw_disp.config(text="00:00.0")
        self.sw_btn.config_text("START", C["accent_d"])
        self.sw_lap_btn.config_text("LAP", C["surface2"])
        self._render_laps()

    def _on_sw_scroll(self, event):
        """Handle mouse wheel scrolling for the stopwatch lap canvas."""
        self._sw_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # -- ALARM PANEL --
    def _build_alarm_panel(self):
        p = self._alarm_panel = tk.Frame(self._inner, bg=C["bg"])
        
        # Header / Add Alarm Row
        add_f = tk.Frame(p, bg=C["surface"], pady=15)
        add_f.pack(fill="x", side="top")
        
        inputs = tk.Frame(add_f, bg=C["surface"])
        inputs.pack(padx=16, fill="x")

        init_fmt = "%I:%M" if self._use_12hr_format else "%H:%M"
        self._a_time_var = tk.StringVar(value=datetime.now().strftime(init_fmt))
        self._a_time_entry = tk.Entry(inputs, textvariable=self._a_time_var, width=6, bg=C["surface2"], fg=C["text"], 
                 font=("Consolas",14, "bold"), relief="flat", insertbackground=C["accent"], justify="center")
        self._a_time_entry.pack(side="left", padx=5)
        self._ampm_btn = RoundedButton(inputs, datetime.now().strftime("%p"), self._toggle_ampm, width=45, height=34, radius=10, color=C["surface2"], fg=C["accent"], hover_fg=C["white"])
        if self._use_12hr_format: self._ampm_btn.pack(side="left", padx=2)
        
        self._a_label_var = tk.StringVar(value="New Alarm")
        tk.Entry(inputs, textvariable=self._a_label_var, bg=C["surface2"], fg=C["text"], 
                 font=("Segoe UI",10), relief="flat", insertbackground=C["accent"]).pack(side="left", padx=5, expand=True, fill="x")
        
        RoundedButton(inputs, "ADD", self._alarm_add, width=60, height=34, radius=17).pack(side="right", padx=5)

        # Scrollable container for alarms
        container = tk.Frame(p, bg=C["bg"])
        container.pack(fill="both", expand=True, padx=16, pady=10)
        
        self._alarm_canvas = tk.Canvas(container, bg=C["bg"], highlightthickness=0)
        self._alarm_scrollbar = tk.Scrollbar(container, orient="vertical", command=self._alarm_canvas.yview)
        self._alarm_list_frame = tk.Frame(self._alarm_canvas, bg=C["bg"])
        
        self._alarm_canvas.create_window((0, 0), window=self._alarm_list_frame, anchor="nw", width=350)
        self._alarm_canvas.configure(yscrollcommand=self._alarm_scrollbar.set)
        
        self._alarm_canvas.pack(side="left", fill="both", expand=True)
        self._alarm_scrollbar.pack(side="right", fill="y")
        
        self._alarm_list_frame.bind("<Configure>", lambda e: self._alarm_canvas.configure(scrollregion=self._alarm_canvas.bbox("all")))
        self._alarm_canvas.bind("<MouseWheel>", self._on_alarm_scroll)
        self._alarm_list_frame.bind("<MouseWheel>", self._on_alarm_scroll)
        
        self._alarm_render()

    def _alarm_add(self):
        t = self._a_time_var.get().strip()
        lbl = self._a_label_var.get().strip() or "Alarm"
        
        try:
            # Parse based on current UI format then normalize to 24h internal storage
            if self._use_12hr_format:
                dt = datetime.strptime(f"{t} {self._ampm_btn.text}", "%I:%M %p")
            else:
                dt = datetime.strptime(t, "%H:%M")
            t_24 = dt.strftime("%H:%M")
        except ValueError:
            self._a_time_var.set("Err!")
            reset_fmt = "%I:%M" if self._use_12hr_format else "%H:%M"
            self.after(1000, lambda: self._a_time_var.set(datetime.now().strftime(reset_fmt)))
            return
            
        self.alarms = sort_alarms(self.alarms + [{"time": t_24, "label": lbl, "on": True}])
        save_alarms(self.alarms); self._alarm_render()
        self._a_label_var.set("New Alarm")

    def _alarm_toggle(self, idx):
        self.alarms[idx]["on"] = not self.alarms[idx]["on"]
        save_alarms(self.alarms); self._alarm_render()

    def _alarm_delete(self, idx):
        del self.alarms[idx]
        save_alarms(self.alarms); self._alarm_render()

    def _on_alarm_scroll(self, event):
        """Handle mouse wheel scrolling for the alarm list canvas."""
        self._alarm_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _alarm_render(self):
        for w in self._alarm_list_frame.winfo_children(): w.destroy()
        
        if not self.alarms:
            lbl = tk.Label(self._alarm_list_frame, text="No alarms set", bg=C["bg"], fg=C["muted2"], font=("Segoe UI", 10))
            lbl.pack(pady=40)
            lbl.bind("<MouseWheel>", self._on_alarm_scroll)
            return
            
        if self._ringing:
            f = tk.Frame(self._alarm_list_frame, bg=C["alarm_d"], pady=12)
            f.pack(fill="x", pady=(0, 10))
            l1 = tk.Label(f, text="ALARM!", bg=C["alarm_d"], fg=C["white"], font=("Segoe UI", 11, "bold"))
            l1.pack(side="left", padx=15)
            b1 = RoundedButton(f, "DISMISS", self._dismiss_ringing, width=80, height=30, radius=15, color=C["white"], fg=C["alarm_d"])
            b1.pack(side="right", padx=5)
            b2 = RoundedButton(f, "SNOOZE", self._snooze_ringing, width=80, height=30, radius=15, color=C["alarm"], fg=C["white"])
            b2.pack(side="right", padx=5)
            for w in (f, l1, b1, b2): w.bind("<MouseWheel>", self._on_alarm_scroll)

        for i, a in enumerate(self.alarms):
            is_on = a.get("on", False)
            row_bg = C["surface2"] if is_on else C["surface"]
            f = tk.Frame(self._alarm_list_frame, bg=row_bg, pady=12)
            f.pack(fill="x", pady=1)
            
            # Status indicator
            color = C["success"] if a["on"] else C["muted"]
            dot = tk.Label(f, text="●", bg=row_bg, fg=color, font=("Segoe UI", 14), cursor="hand2")
            dot.pack(side="left", padx=12)
            dot.bind("<Button-1>", lambda e, idx=i: self._alarm_toggle(idx))
            
            # Time and Label
            txt_f = tk.Frame(f, bg=row_bg)
            txt_f.pack(side="left", fill="both", expand=True)
            
            display_time_str = a["time"]
            if self._use_12hr_format:
                try:
                    dt_obj = datetime.strptime(display_time_str, "%H:%M")
                    display_time_str = dt_obj.strftime("%I:%M %p")
                except ValueError: pass # Keep original if parsing fails
            time_lbl = tk.Label(txt_f, text=display_time_str, bg=row_bg, fg=C["text"] if is_on else C["muted"], font=("Consolas", 18, "bold"), anchor="w")
            time_lbl.pack(fill="x")
            sub_lbl = tk.Label(txt_f, text=a["label"].upper(), bg=row_bg, fg=C["muted"], font=("Segoe UI", 8, "bold"), anchor="w")
            sub_lbl.pack(fill="x")
            
            # Delete button
            del_btn = tk.Label(f, text="×", bg=row_bg, fg=C["muted"], font=("Segoe UI", 18), cursor="hand2", width=2)
            del_btn.pack(side="right", padx=10)
            del_btn.bind("<Button-1>", lambda e, idx=i: self._alarm_delete(idx))
            
            for w in (f, dot, txt_f, time_lbl, sub_lbl, del_btn):
                w.bind("<MouseWheel>", self._on_alarm_scroll)

    # -- WORLD PANEL --
    def _build_world_panel(self):
        p = self._world_panel = tk.Frame(self._inner, bg=C["bg"])

        # Scrollable container for world clocks
        container = tk.Frame(p, bg=C["bg"])
        container.pack(fill="both", expand=True, padx=16, pady=10)
        
        self._world_canvas = tk.Canvas(container, bg=C["bg"], highlightthickness=0)
        self._world_scrollbar = tk.Scrollbar(container, orient="vertical", command=self._world_canvas.yview)
        self._world_list_frame = tk.Frame(self._world_canvas, bg=C["bg"])
        
        self._world_canvas.create_window((0, 0), window=self._world_list_frame, anchor="nw", width=350)
        self._world_canvas.configure(yscrollcommand=self._world_scrollbar.set)
        
        self._world_canvas.pack(side="left", fill="both", expand=True)
        self._world_scrollbar.pack(side="right", fill="y")
        
        self._world_list_frame.bind("<Configure>", lambda e: self._world_canvas.configure(scrollregion=self._world_canvas.bbox("all")))
        self._world_canvas.bind("<MouseWheel>", self._on_world_scroll)
        self._world_list_frame.bind("<MouseWheel>", self._on_world_scroll)

        self._world_labels = {}
        for city, tz_name in WORLD_ZONES:
            row = tk.Frame(self._world_list_frame, bg=C["bg"], pady=8)
            row.pack(fill="x", padx=10)
            
            name_lbl = tk.Label(row, text=city, bg=C["bg"], fg=C["muted"], font=("Segoe UI", 10, "bold"))
            name_lbl.pack(side="left")
            
            lbl = tk.Label(row, text="--:--", bg=C["bg"], fg=C["text"], font=("Consolas", 14))
            lbl.pack(side="right")
            self._world_labels[city] = lbl
            
            # Enable mouse wheel scrolling when hovering over rows or labels
            for widget in (row, name_lbl, lbl):
                widget.bind("<MouseWheel>", self._on_world_scroll)
                
        self._tick_world()

    def _on_world_scroll(self, event):
        """Handle mouse wheel scrolling for the world clock canvas."""
        self._world_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _tick_world(self):
        now_utc = datetime.now(timezone.utc)
        for city, tz_name in WORLD_ZONES:
            if ZoneInfo:
                try:
                    local_time = now_utc.astimezone(ZoneInfo(tz_name))
                    time_str = local_time.strftime("%I:%M %p" if self._use_12hr_format else "%H:%M")
                except Exception:
                    time_str = "Error"
            else:
                time_str = now_utc.strftime("%H:%M") + " UTC"
            self._world_labels[city].config(text=time_str)
            
        self.after(1000, self._tick_world)

    def _alarm_loop(self):
        now = datetime.now()
        curr_hm = now.strftime("%H:%M")
        
        triggered = False
        # Check scheduled alarms
        for a in self.alarms:
            if a.get("on") and a["time"] == curr_hm:
                # Ensure we only fire once per specific minute
                if a.get("last_fired") != curr_hm:
                    a["last_fired"] = curr_hm
                    triggered = True
                    break
        
        # Check snooze timer
        if self._snooze_time and now >= self._snooze_time:
            self._snooze_time = None
            triggered = True

        if triggered and not self._ringing:
            self._ringing = True
            beep_alarm(continuous=True)
            self.deiconify(); self.lift(); self.attributes("-topmost", True)
            self._update_ui_state(); self._alarm_render()
        
        self.after(1000, self._alarm_loop)

    # -- SYSTEM TRAY INTEGRATION --
    def _start_tray_icon(self):
        if not TRAY_OK: return
        self._tray_icon = None # Will be set by run_tray
        threading.Thread(target=run_tray, args=(self,), daemon=True).start()

    def _stop_tray_icon(self):
        if self._tray_icon:
            self._tray_icon.stop()

    def _toggle_run_on_startup(self):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "TaskbarTimer"
        
        if getattr(sys, 'frozen', False): # Running as a PyInstaller bundle
            app_path = sys.executable
        else: # Running as a script, use python.exe to run this script
            app_path = f'"{sys.executable}" "{Path(__file__).resolve()}"'

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            try:
                winreg.QueryValueEx(key, app_name)
                # If it exists, remove it
                winreg.DeleteValue(key, app_name)
                print(f"Removed '{app_name}' from startup.")
            except FileNotFoundError:
                # If it doesn't exist, add it
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, app_path)
                print(f"Added '{app_name}' to startup.")
            finally:
                winreg.CloseKey(key)
        except Exception as e:
            print(f"Error modifying startup registry: {e}")
        
        # Recreate the tray icon to update the menu item's checked state
        if self._tray_icon:
            self._tray_icon.stop()
            self._start_tray_icon()

    def _is_run_on_startup_enabled(self):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "TaskbarTimer"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, app_name)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

# ────────────────────────────────────────────────────────────────────────────
# System tray
# ────────────────────────────────────────────────────────────────────────────

def run_tray(app: App):
    icon_img = make_tray_icon(0, False, False, app.logo_img)

    def ui(fn): return lambda icon, item: app.after(0, fn)
    def quick_start(secs, label):
        def _do():
            app._preset(secs, label) # Use app._preset for quick start
            app.deiconify(); app.lift(); app.attributes("-topmost", True)
        return lambda icon, item: app.after(0, _do)

    menu = pystray.Menu(
        pystray.MenuItem("Show/Hide Timer", ui(app.toggle_visibility), default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quick Start", pystray.Menu(
            pystray.MenuItem("5 minutes", quick_start(300,  "5m")),
            pystray.MenuItem("15 minutes", quick_start(900,  "15m")),
            pystray.MenuItem("30 minutes", quick_start(1800, "30m")),
            pystray.MenuItem("1 hour", quick_start(3600, "1h")),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Run at Startup", ui(app._toggle_run_on_startup), checked=lambda item: app._is_run_on_startup_enabled()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", lambda icon, item: (icon.stop(), app.after(0, app.destroy))),
    )
    app._tray_icon = pystray.Icon("TaskbarTimer", icon_img, "TaskbarTimer", menu)

    def _refresh():
        while app.winfo_exists(): # Keep refreshing as long as the app window exists
            time.sleep(1)
            try:
                app._tray_icon.icon  = make_tray_icon(int(state.remaining), state.running, state.expired, app.logo_img)
                if state.running:
                    r = int(state.remaining)
                    h = r // 3600; m = (r%3600)//60; s = r%60
                    app._tray_icon.title = f"⏱ {h}:{m:02}:{s:02}" if h else f"⏱ {m:02}:{s:02}"
                elif state.expired:
                    app._tray_icon.title = "✓ Timer finished!"
                else:
                    app._tray_icon.title = "TaskbarTimer"
            except Exception:
                pass

    threading.Thread(target=_refresh, daemon=True).start()
    app._tray_icon.run()

if __name__ == "__main__":
    app = App()
    app.mainloop()