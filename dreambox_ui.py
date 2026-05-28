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
    {
        "title": "Wonderfalls S1",
        "glob":  "~/videos/S01E*.mp4",
        "cover": "~/videos/covers/wonderfalls.jpg",
    },
    {
        "title": "The Office S1",
        "glob":  "~/videos/office/THE_OFFICE_T*.mp4",
        "cover": "~/videos/covers/office.jpg",
    },
]

# ── VOLUME ───────────────────────────────────────────────────────────────────
def _read_vol():
    try:
        out = subprocess.check_output(
            ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
            stderr=subprocess.DEVNULL,
        ).decode()
        m = re.search(r'Volume:\s*([\d.]+)', out)
        if m:
            return round(float(m.group(1)) * 100)
    except Exception:
        pass
    return 80

_vol = [_read_vol()]

def _set_vol(v):
    _vol[0] = max(0, min(100, v))
    os.system(f"wpctl set-volume @DEFAULT_AUDIO_SINK@ {_vol[0]}%")
    try:
        _vol_lbl.config(text=f"{_vol[0]}%")
    except Exception:
        pass

# ── MPV IPC ──────────────────────────────────────────────────────────────────
_IPC = "/tmp/dreambox_mpv.sock"
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
    try:
        _play_lbl.config(text="▶" if _paused[0] else "⏸")
    except Exception:
        pass

def _next_ep():
    if _paused[0]:          # resume so next ep autoplays
        _paused[0] = False
        try:
            _play_lbl.config(text="⏸")
        except Exception:
            pass
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
_hide_id = [None]

# ── PLAYING FRAME ─────────────────────────────────────────────────────────────
playing_frame = tk.Frame(root, bg="black")

# ── CONTROL BAR (child of root — floats above mpv's sub-window) ───────────────
CTRL_H = 80   # height of the bottom bar in pixels

_ctrl = tk.Frame(root, bg="#1c1c1c")

# ── left group: play/pause  next ─────────────────────────────────────────────
_play_lbl = tk.Label(
    _ctrl, text="⏸",
    font=("Helvetica", 34),
    fg="white", bg="#1c1c1c",
    padx=20, pady=10,
)
_play_lbl.pack(side="left", padx=(10, 2))

_next_lbl = tk.Label(
    _ctrl, text="⏭",
    font=("Helvetica", 34),
    fg="white", bg="#1c1c1c",
    padx=16, pady=10,
)
_next_lbl.pack(side="left", padx=(2, 10))

# ── right group: vol−  vol%  vol+  ✕ ─────────────────────────────────────────
_exit_lbl = tk.Label(
    _ctrl, text=" ✕ ",
    font=("Helvetica", 28, "bold"),
    fg="white", bg="#992222",
    padx=14, pady=10,
)
_exit_lbl.pack(side="right", padx=(2, 10))

_vol_up_lbl = tk.Label(
    _ctrl, text=" + ",
    font=("Helvetica", 30, "bold"),
    fg="white", bg="#1c1c1c",
    padx=14, pady=10,
)
_vol_up_lbl.pack(side="right", padx=2)

_vol_lbl = tk.Label(
    _ctrl, text=f"{_vol[0]}%",
    font=("Helvetica", 22),
    fg="#bbbbbb", bg="#1c1c1c",
    width=5,
)
_vol_lbl.pack(side="right")

_vol_dn_lbl = tk.Label(
    _ctrl, text=" − ",
    font=("Helvetica", 30, "bold"),
    fg="white", bg="#1c1c1c",
    padx=14, pady=10,
)
_vol_dn_lbl.pack(side="right", padx=2)

# thin separator line above bar
_sep = tk.Frame(root, bg="#444444", height=1)


def _show_ctrl():
    _sep.place(x=0, y=SH - CTRL_H - 1, width=SW, height=1)
    _ctrl.place(x=0, y=SH - CTRL_H, width=SW, height=CTRL_H)
    _ctrl.lift()
    _sep.lift()
    _reset_hide()

def _hide_ctrl():
    _ctrl.place_forget()
    _sep.place_forget()
    _hide_id[0] = None

def _reset_hide():
    if _hide_id[0]:
        root.after_cancel(_hide_id[0])
    _hide_id[0] = root.after(5000, _hide_ctrl)

def _keep_ctrl_on_top():
    if _proc[0] is not None:
        if _ctrl.winfo_ismapped():
            _ctrl.lift()
            _sep.lift()
        root.after(300, _keep_ctrl_on_top)


# ── PLAYBACK ──────────────────────────────────────────────────────────────────
def play_show(glob_path):
    files = sorted(glob_module.glob(os.path.expanduser(glob_path)))
    if not files:
        return
    os.system("pkill -9 -f mpv 2>/dev/null; pkill -9 -f cvlc 2>/dev/null; pkill -9 -f vlc 2>/dev/null")
    os.path.exists(_IPC) and os.remove(_IPC)
    _paused[0] = False
    try:
        _play_lbl.config(text="⏸")
    except Exception:
        pass
    main_frame.pack_forget()
    playing_frame.pack(fill="both", expand=True)
    root.attributes("-fullscreen", True)
    root.update()
    leds_dim()

    xid = playing_frame.winfo_id()
    env = os.environ.copy()
    env.pop("WAYLAND_DISPLAY", None)
    env["DISPLAY"] = ":0"
    _proc[0] = subprocess.Popen(
        [
            "mpv",
            f"--wid={xid}",
            "--vo=x11",
            "--hwdec=auto",
            "--loop-playlist=inf",
            "--no-osd-bar",
            "--really-quiet",
            "--no-terminal",
            f"--input-ipc-server={_IPC}",
        ] + files,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=env,
    )
    root.after(300, _keep_ctrl_on_top)


def stop_show():
    if _proc[0]:
        try:
            _proc[0].kill()
            _proc[0].wait(timeout=2)
        except Exception:
            pass
        _proc[0] = None
    os.system("pkill -9 -f mpv 2>/dev/null; pkill -9 -f cvlc 2>/dev/null; pkill -9 -f vlc 2>/dev/null")
    _hide_ctrl()
    playing_frame.pack_forget()
    main_frame.pack(fill="both", expand=True)
    leds_full()
    root.after(150, _reload_covers)


# ── MAIN MENU ─────────────────────────────────────────────────────────────────
main_frame = tk.Frame(root, bg="black")
main_frame.pack(fill="both", expand=True)

_cover_photos = [None, None]

def _make_card(parent, show, idx):
    card = tk.Frame(parent, bg="black")
    cover_path = os.path.expanduser(show["cover"])

    img_lbl = tk.Label(card, bg="black")
    img_lbl.place(relx=0, rely=0, relwidth=1, relheight=1)

    tk.Label(
        card, text=show["title"],
        font=("Helvetica", 15, "bold"),
        fg="white", bg="black",
    ).place(relx=0.5, rely=0.96, anchor="s")

    def _load(w, h):
        try:
            img = Image.open(cover_path).resize((w, h), Image.LANCZOS)
            ph = ImageTk.PhotoImage(img)
            _cover_photos[idx] = ph
            img_lbl.config(image=ph)
        except Exception:
            card.config(bg="#1c1c1c")

    def _resize(e):
        if e.width > 1 and e.height > 1:
            _load(e.width, e.height)

    card.bind("<Configure>", _resize)
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


# ── TAP DISPATCH ──────────────────────────────────────────────────────────────
def _tap(event):
    sx = event.x_root - root.winfo_rootx()
    sy = event.y_root - root.winfo_rooty()

    # ── MENU ──
    if _proc[0] is None:
        idx = min(int(sx / SW * len(SHOWS)), len(SHOWS) - 1)
        play_show(SHOWS[idx]["glob"])
        return

    # ── PLAYING — bar hidden → show it ──
    if not _ctrl.winfo_ismapped():
        _show_ctrl()
        return

    # ── PLAYING — bar visible — any touch keeps it alive ──
    _reset_hide()

    if sy < SH - CTRL_H:
        return   # tapped above bar — just reset timer

    # tapped within the bar — route by x position
    if sx > SW * 0.88:           # ✕  exit  (rightmost ~12%)
        stop_show()
    elif sx > SW * 0.72:         # +  vol up
        _set_vol(_vol[0] + 10)
    elif sx > SW * 0.55:         # −  vol down
        _set_vol(_vol[0] - 10)
    elif sx > SW * 0.22:         # ⏭  next episode
        _next_ep()
    else:                        # ⏸  play/pause
        _toggle_pause()


root.bind_all("<Button-1>", _tap)


# ── CLEANUP ───────────────────────────────────────────────────────────────────
def _quit():
    stop_show()
    if GPIO_AVAILABLE:
        lgpio.tx_pwm(_chip, LED_PIN, 100, 0)
        lgpio.gpiochip_close(_chip)
    root.destroy()


root.protocol("WM_DELETE_WINDOW", _quit)
root.mainloop()
