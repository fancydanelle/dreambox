import os
import re
import json
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

def _mpv_get(prop):
    try:
        s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        s.settimeout(0.4)
        s.connect(_IPC)
        s.sendall(json.dumps({"command": ["get_property", prop]}).encode() + b"\n")
        data = b""
        while True:
            chunk = s.recv(512)
            if not chunk:
                break
            data += chunk
            if b"\n" in chunk:
                break
        s.close()
        resp = json.loads(data.split(b"\n")[0])
        if resp.get("error") == "success":
            return resp.get("data")
    except Exception:
        pass
    return None

def _fmt_time(secs):
    secs = int(secs or 0)
    return f"{secs // 60}:{secs % 60:02d}"

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
_proc    = [None]
_prog_id = [None]

# ── OVERLAY — always a child of root so it stacks above playing_frame ────────
# Sits at bottom strip so it doesn't cover most of the video
OW, OH = 800, 120
OX, OY = 0, SH - OH   # bottom strip

BG  = "#1a1a1a"
BTN = "#2a2a2a"
RED = "#992222"

_overlay = tk.Frame(root, bg=BG, highlightbackground="#555555",
                    highlightthickness=2)

# ── row 1: title + exit ───────────────────────────────────────────────────────
_row1 = tk.Frame(_overlay, bg=BG)
_row1.pack(fill="x", padx=10, pady=(6, 2))

_title_lbl = tk.Label(_row1, text="", font=("Helvetica", 13, "bold"),
                       fg="white", bg=BG, anchor="w")
_title_lbl.pack(side="left", fill="x", expand=True)

_exit_btn = tk.Button(_row1, text="  ✕  ", font=("Helvetica", 13, "bold"),
                      fg="white", bg=RED, activebackground="#cc3333",
                      activeforeground="white", relief="flat", bd=0,
                      command=lambda: stop_show())
_exit_btn.pack(side="right")

tk.Frame(_overlay, bg="#444444", height=1).pack(fill="x")

# ── row 2: play/pause | next | vol- | vol% | vol+ ────────────────────────────
_row2 = tk.Frame(_overlay, bg=BG)
_row2.pack(fill="both", expand=True, padx=10, pady=4)

_play_btn = tk.Button(_row2, text="  ⏸  ", font=("Helvetica", 28),
                      fg="white", bg=BTN, activebackground="#444444",
                      activeforeground="white", relief="flat", bd=0,
                      padx=14, pady=4,
                      command=_toggle_pause)
_play_btn.pack(side="left", padx=(0, 6))

_next_btn = tk.Button(_row2, text="  ⏭  ", font=("Helvetica", 28),
                      fg="white", bg=BTN, activebackground="#444444",
                      activeforeground="white", relief="flat", bd=0,
                      padx=14, pady=4,
                      command=_next_ep)
_next_btn.pack(side="left", padx=(0, 20))

# spacer
tk.Label(_row2, bg=BG).pack(side="left", expand=True)

# volume
_vol_dn = tk.Button(_row2, text="  −  ", font=("Helvetica", 24, "bold"),
                    fg="white", bg=BTN, activebackground="#444444",
                    activeforeground="white", relief="flat", bd=0,
                    padx=10, pady=4,
                    command=lambda: _set_vol(-10))
_vol_dn.pack(side="left", padx=(0, 4))

_vol_lbl = tk.Label(_row2, text=f"{_vol[0]}%",
                    font=("Helvetica", 16), fg="#aaaaaa", bg=BG, width=5)
_vol_lbl.pack(side="left")

_vol_up = tk.Button(_row2, text="  +  ", font=("Helvetica", 24, "bold"),
                    fg="white", bg=BTN, activebackground="#444444",
                    activeforeground="white", relief="flat", bd=0,
                    padx=10, pady=4,
                    command=lambda: _set_vol(10))
_vol_up.pack(side="left", padx=(4, 0))

# time label
_time_lbl = tk.Label(_row2, text="", font=("Helvetica", 12),
                     fg="#888888", bg=BG)
_time_lbl.pack(side="right", padx=(10, 0))


# ── OVERLAY SHOW/HIDE ─────────────────────────────────────────────────────────
def _show_overlay():
    _overlay.place(x=OX, y=OY, width=OW, height=OH)
    _overlay.lift()
    _start_progress()

def _hide_overlay():
    _overlay.place_forget()
    if _prog_id[0]:
        root.after_cancel(_prog_id[0])
        _prog_id[0] = None

def _start_progress():
    if _prog_id[0]:
        root.after_cancel(_prog_id[0])
    _tick_progress()

def _tick_progress():
    if _proc[0] is None or not _overlay.winfo_ismapped():
        return
    pos = _mpv_get("time-pos")
    dur = _mpv_get("duration")
    if pos is not None and dur:
        _time_lbl.config(text=f"{_fmt_time(pos)} / {_fmt_time(dur)}")
    _prog_id[0] = root.after(1000, _tick_progress)


def _keep_on_top():
    if _proc[0] is not None:
        if _overlay.winfo_ismapped():
            _overlay.lift()
        root.after(200, _keep_on_top)


# ── TAP: show overlay when screen tapped during playback ─────────────────────
_last_tap = [0]

def _on_tap(event):
    now = time.time()
    if now - _last_tap[0] < 0.3:   # debounce double-fire
        return
    _last_tap[0] = now

    if _proc[0] is None:
        # menu — pick show by which half was tapped
        sx = event.x_root - root.winfo_rootx()
        idx = 0 if sx < SW // 2 else 1
        play_show(idx)
        return

    # playing — show overlay if hidden, keep it up if already visible
    if not _overlay.winfo_ismapped():
        _show_overlay()


root.bind_all("<Button-1>", _on_tap)


# ── PLAYBACK ──────────────────────────────────────────────────────────────────
def play_show(idx):
    show = SHOWS[idx]
    files = sorted(glob_module.glob(os.path.expanduser(show["glob"])))
    if not files:
        return
    os.system("pkill -9 -f mpv 2>/dev/null; true")
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
    _show_overlay()   # show controls immediately on play

    xid = playing_frame.winfo_id()
    env = os.environ.copy()
    env.pop("WAYLAND_DISPLAY", None)
    env["DISPLAY"] = ":0"
    _proc[0] = subprocess.Popen(
        ["mpv", f"--wid={xid}", "--vo=x11", "--hwdec=auto",
         "--loop-playlist=inf", "--no-osd-bar", "--really-quiet",
         "--no-terminal", f"--input-ipc-server={_IPC}"] + files,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    )
    root.after(200, _keep_on_top)


def stop_show():
    _hide_overlay()
    if _proc[0]:
        try:
            _proc[0].kill()
            _proc[0].wait(timeout=2)
        except Exception:
            pass
        _proc[0] = None
    os.system("pkill -9 -f mpv 2>/dev/null; true")
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
