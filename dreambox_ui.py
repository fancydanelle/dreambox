import os
import re
import json
import struct
import threading
import glob as glob_module
import socket as _socket
import subprocess
import time
import tkinter as tk
from PIL import Image, ImageTk

# ── LED ──────────────────────────────────────────────────────────────────────
LED_PIN = 18
try:
    import lgpio
    _chip = lgpio.gpiochip_open(0)
    lgpio.gpio_claim_output(_chip, LED_PIN, 0)
    lgpio.tx_pwm(_chip, LED_PIN, 100, 100)
    GPIO_AVAILABLE = True
except Exception:
    GPIO_AVAILABLE = False

def leds_full():
    if GPIO_AVAILABLE:
        lgpio.tx_pwm(_chip, LED_PIN, 100, 100)

def leds_dim():
    if GPIO_AVAILABLE:
        lgpio.tx_pwm(_chip, LED_PIN, 100, 15)

time.sleep(2)

# Ensure the OLED starfield is running
subprocess.Popen(
    ["bash", "-c",
     "pgrep -f oled_auto || nohup python3 /home/fancydanelle/oled_auto.py > /tmp/oled.log 2>&1 &"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)

# ── SHOWS ────────────────────────────────────────────────────────────────────
SHOWS = [
    {"title": "Wonderfalls",  "glob": "~/videos/S01E*.mp4",
     "cover": "~/videos/covers/wonderfalls.jpg"},
    {"title": "The Office",   "glob": "~/videos/office/THE_OFFICE_T*.mp4",
     "cover": "~/videos/covers/office.jpg"},
]

# ── VOLUME ───────────────────────────────────────────────────────────────────
def _read_vol():
    try:
        out = subprocess.check_output(
            ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
            stderr=subprocess.DEVNULL).decode()
        m = re.search(r'Volume:\s*([\d.]+)', out)
        if m:
            return round(float(m.group(1)) * 100)
    except Exception:
        pass
    return 80

_vol = [_read_vol()]

def _set_vol(delta):
    _vol[0] = max(0, min(100, _vol[0] + delta))
    os.system(f"wpctl set-volume @DEFAULT_AUDIO_SINK@ {_vol[0]}%")
    _vol_lbl.config(text=f"{_vol[0]}%")

# ── MPV IPC ──────────────────────────────────────────────────────────────────
_IPC    = "/tmp/dreambox_mpv.sock"
_paused = [False]

def _mpv_cmd(*args):
    try:
        s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(_IPC)
        s.sendall(json.dumps({"command": list(args)}).encode() + b"\n")
        s.close()
    except Exception:
        pass

def _toggle_pause():
    _paused[0] = not _paused[0]
    _mpv_cmd("cycle", "pause")
    _play_btn.config(text="  ▶  " if _paused[0] else "  ⏸  ")

def _next_ep():
    _paused[0] = False
    _play_btn.config(text="  ⏸  ")
    _mpv_cmd("playlist-next", "force")

# ── ROOT WINDOW ───────────────────────────────────────────────────────────────
SW, SH = 800, 480

root = tk.Tk()
root.geometry(f"{SW}x{SH}+0+0")
root.attributes("-fullscreen", True)
root.config(cursor="none", bg="black")
root.update()
root.lift()
root.focus_force()

# ── STATE ─────────────────────────────────────────────────────────────────────
_proc      = [None]
_ctrl_hide = [None]

BG  = "#1a1a1a"
BTN = "#2a2a2a"
RED = "#992222"

# ── CONTROL PANEL — shown once at episode start, auto-hides after 5s ─────────
OW, OH = 800, 120
OX, OY = 0, SH - OH   # bottom strip

_ctrl = tk.Frame(root, bg=BG, highlightbackground="#555555", highlightthickness=2)

_row1 = tk.Frame(_ctrl, bg=BG)
_row1.pack(fill="x", padx=10, pady=(6, 2))
_title_lbl = tk.Label(_row1, text="", font=("Helvetica", 13, "bold"),
                       fg="white", bg=BG, anchor="w")
_title_lbl.pack(side="left", fill="x", expand=True)
tk.Button(_row1, text="  ✕  ", font=("Helvetica", 13, "bold"),
          fg="white", bg=RED, activebackground="#cc3333",
          activeforeground="white", relief="flat", bd=0,
          command=lambda: stop_show()).pack(side="right")
tk.Frame(_ctrl, bg="#444444", height=1).pack(fill="x")

_row2 = tk.Frame(_ctrl, bg=BG)
_row2.pack(fill="both", expand=True, padx=10, pady=4)

_play_btn = tk.Button(_row2, text="  ⏸  ", font=("Helvetica", 28),
                      fg="white", bg=BTN, activebackground="#444444",
                      activeforeground="white", relief="flat", bd=0,
                      padx=14, pady=4, command=_toggle_pause)
_play_btn.pack(side="left", padx=(0, 6))

_next_btn = tk.Button(_row2, text="  ⏭  ", font=("Helvetica", 28),
                      fg="white", bg=BTN, activebackground="#444444",
                      activeforeground="white", relief="flat", bd=0,
                      padx=14, pady=4, command=_next_ep)
_next_btn.pack(side="left", padx=(0, 20))

tk.Label(_row2, bg=BG).pack(side="left", expand=True)

_vol_dn = tk.Button(_row2, text="  −  ", font=("Helvetica", 24, "bold"),
                    fg="white", bg=BTN, activebackground="#444444",
                    activeforeground="white", relief="flat", bd=0,
                    padx=10, pady=4, command=lambda: _set_vol(-10))
_vol_dn.pack(side="left", padx=(0, 4))

_vol_lbl = tk.Label(_row2, text=f"{_vol[0]}%",
                    font=("Helvetica", 16), fg="#aaaaaa", bg=BG, width=5)
_vol_lbl.pack(side="left")

_vol_up = tk.Button(_row2, text="  +  ", font=("Helvetica", 24, "bold"),
                    fg="white", bg=BTN, activebackground="#444444",
                    activeforeground="white", relief="flat", bd=0,
                    padx=10, pady=4, command=lambda: _set_vol(10))
_vol_up.pack(side="left", padx=(4, 0))


def _ctrl_show():
    if _ctrl_hide[0]:
        root.after_cancel(_ctrl_hide[0])
    _ctrl.place(x=OX, y=OY, width=OW, height=OH)
    _ctrl.lift()
    _ctrl_hide[0] = root.after(5000, _ctrl_hide_now)

def _ctrl_hide_now():
    _ctrl_hide[0] = None
    _ctrl.place_forget()


def _hide_exit():
    _ctrl_hide_now()

def _keep_on_top():
    if _proc[0] is not None:
        if _ctrl.winfo_ismapped():
            _ctrl.lift()
        root.after(200, _keep_on_top)


# ── TOUCH WATCHER — reads raw events, bypasses X11/mpv entirely ──────────────
# On 64-bit Pi: struct input_event = { long long, long long, ushort, ushort, int }
_EV_FMT  = 'qqHHi'
_EV_SIZE = struct.calcsize(_EV_FMT)   # 24 bytes
_EV_KEY  = 0x01
_BTN_TOUCH = 0x14a

def _touch_watcher():
    dev = '/dev/input/event5'   # ft5x06 DSI touchscreen
    while True:
        try:
            with open(dev, 'rb') as f:
                while True:
                    data = f.read(_EV_SIZE)
                    if len(data) < _EV_SIZE:
                        break
                    _, _, ev_type, ev_code, ev_value = struct.unpack(_EV_FMT, data)
                    if ev_type == _EV_KEY and ev_code == _BTN_TOUCH and ev_value == 1:
                        if _proc[0] is not None:
                            root.after(0, _ctrl_show)
        except Exception:
            time.sleep(1)   # retry on error

threading.Thread(target=_touch_watcher, daemon=True).start()


# ── MENU TAP — still use bind_all for the main menu (no mpv running) ─────────
_last_tap = [0]

def _on_menu_tap(event):
    if _proc[0] is not None:
        return   # playback handled by touch watcher
    now = time.time()
    if now - _last_tap[0] < 0.3:
        return
    _last_tap[0] = now
    sx = event.x_root - root.winfo_rootx()
    idx = 0 if sx < SW // 2 else 1
    play_show(idx)

root.bind_all("<Button-1>", _on_menu_tap)


# ── PLAYBACK ──────────────────────────────────────────────────────────────────
def play_show(idx):
    show = SHOWS[idx]
    files = sorted(glob_module.glob(os.path.expanduser(show["glob"])))
    if not files:
        return
    os.system("pkill -9 -f mpv 2>/dev/null; true")
    os.system("pkill -f wf-panel-pi 2>/dev/null; pkill -f 'lwrespawn.*wf-panel' 2>/dev/null; true")
    if os.path.exists(_IPC):
        os.remove(_IPC)
    _paused[0] = False
    _play_btn.config(text="  ⏸  ")
    _title_lbl.config(text=show["title"])
    main_frame.pack_forget()
    playing_frame.pack(fill="both", expand=True)
    root.attributes("-fullscreen", True)
    root.update()
    leds_dim()
    _ctrl_show()   # show controls once at episode start

    xid = playing_frame.winfo_id()
    env = os.environ.copy()
    env.pop("WAYLAND_DISPLAY", None)
    env["DISPLAY"] = ":0"
    _proc[0] = subprocess.Popen(
        ["mpv", f"--wid={xid}", "--vo=x11", "--hwdec=auto",
         "--loop-playlist=inf", "--osd-level=0", "--really-quiet",
         "--no-terminal", f"--input-ipc-server={_IPC}"] + files,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    )
    root.after(200, _keep_on_top)


def stop_show():
    _ctrl_hide_now()
    if _proc[0]:
        try:
            _proc[0].kill()
            _proc[0].wait(timeout=2)
        except Exception:
            pass
        _proc[0] = None
    os.system("pkill -9 -f mpv 2>/dev/null; true")
    subprocess.Popen(["/bin/sh", "/usr/bin/lwrespawn", "/usr/bin/wf-panel-pi"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    playing_frame.pack_forget()
    main_frame.pack(fill="both", expand=True)
    leds_full()
    root.after(150, _reload_covers)


# ── FRAMES ────────────────────────────────────────────────────────────────────
playing_frame = tk.Frame(root, bg="black")
main_frame    = tk.Frame(root, bg="black")
main_frame.pack(fill="both", expand=True)

_cover_photos = [None, None]

def _make_card(parent, show, idx):
    card = tk.Frame(parent, bg="black")
    cover_path = os.path.expanduser(show["cover"])
    img_lbl = tk.Label(card, bg="black")
    img_lbl.place(relx=0, rely=0, relwidth=1, relheight=1)
    tk.Label(card, text=show["title"], font=("Helvetica", 15, "bold"),
             fg="white", bg="black").place(relx=0.5, rely=0.96, anchor="s")

    def _load(w, h):
        try:
            img = Image.open(cover_path).resize((w, h), Image.LANCZOS)
            ph = ImageTk.PhotoImage(img)
            _cover_photos[idx] = ph
            img_lbl.config(image=ph)
        except Exception:
            card.config(bg="#1c1c1c")

    card.bind("<Configure>", lambda e: _load(e.width, e.height)
              if e.width > 1 and e.height > 1 else None)
    card._load = _load
    return card

_cards = []
for _i, _s in enumerate(SHOWS):
    _c = _make_card(main_frame, _s, _i)
    _c.pack(side="left", fill="both", expand=True)
    _cards.append(_c)

def _reload_covers():
    root.update()
    for c in _cards:
        w, h = c.winfo_width(), c.winfo_height()
        if w > 1 and h > 1:
            c._load(w, h)

root.after(300, _reload_covers)


# ── CLEANUP ───────────────────────────────────────────────────────────────────
def _quit():
    stop_show()
    if GPIO_AVAILABLE:
        lgpio.tx_pwm(_chip, LED_PIN, 100, 0)
        lgpio.gpiochip_close(_chip)
    root.destroy()

root.protocol("WM_DELETE_WINDOW", _quit)
root.mainloop()
