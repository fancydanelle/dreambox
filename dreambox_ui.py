import os
import re
import glob as glob_module
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

# Controls bar — shown on tap, auto-hides after 4 s
_ctrl = tk.Frame(playing_frame, bg="#111111", height=90)

# Stop button (left)
_stop_lbl = tk.Label(
    _ctrl, text="  ✕  STOP  ",
    font=("Helvetica", 24, "bold"),
    fg="white", bg="#cc2222",
    padx=10, pady=14,
)
_stop_lbl.pack(side="left", padx=14, pady=10)

# Volume controls (right side: − VOL% +)
_vol_up = tk.Label(
    _ctrl, text="  +  ",
    font=("Helvetica", 30, "bold"),
    fg="white", bg="#2a6a2a",
    padx=12, pady=14,
)
_vol_lbl = tk.Label(
    _ctrl, text=f"{_vol[0]}%",
    font=("Helvetica", 22),
    fg="white", bg="#111111",
    width=5,
)
_vol_dn = tk.Label(
    _ctrl, text="  −  ",
    font=("Helvetica", 30, "bold"),
    fg="white", bg="#6a2a2a",
    padx=12, pady=14,
)
_vol_up.pack(side="right", padx=(0, 14), pady=10)
_vol_lbl.pack(side="right", pady=10)
_vol_dn.pack(side="right", pady=10)


def _show_ctrl():
    _ctrl.place(x=0, y=0, relwidth=1)
    _ctrl.lift()
    _reset_hide()

def _hide_ctrl():
    _ctrl.place_forget()
    _hide_id[0] = None

def _reset_hide():
    if _hide_id[0]:
        root.after_cancel(_hide_id[0])
    _hide_id[0] = root.after(4000, _hide_ctrl)

def _keep_ctrl_on_top():
    """Every 400 ms: re-assert fullscreen (hides taskbar) and re-lift controls."""
    if _proc[0] is not None:
        root.attributes("-fullscreen", True)
        if _ctrl.winfo_ismapped():
            _ctrl.lift()
        root.after(400, _keep_ctrl_on_top)


# ── PLAYBACK ──────────────────────────────────────────────────────────────────
def play_show(glob_path):
    files = sorted(glob_module.glob(os.path.expanduser(glob_path)))
    if not files:
        return
    os.system("pkill -9 -f mpv 2>/dev/null; pkill -9 -f cvlc 2>/dev/null; pkill -9 -f vlc 2>/dev/null")
    main_frame.pack_forget()
    playing_frame.pack(fill="both", expand=True)
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
            "--loop-playlist=inf",
            "--no-osd-bar",
            "--really-quiet",
            "--no-terminal",
        ] + files,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=env,
    )
    root.after(400, _keep_ctrl_on_top)


def stop_show():
    if _proc[0]:
        try:
            _proc[0].kill()          # SIGKILL — guarantees audio stops
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


_cover_photos = [None, None]   # module-level refs so GC never drops them

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
            _cover_photos[idx] = ph          # keep reference
            img_lbl.config(image=ph)
        except Exception:
            card.config(bg="#1c1c1c")

    def _resize(e):
        if e.width > 1 and e.height > 1:
            _load(e.width, e.height)

    card.bind("<Configure>", _resize)
    card._load = _load                       # expose for forced reload
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
    Wr = root.winfo_width()

    # ── MENU MODE ──
    if _proc[0] is None:
        idx = min(int(sx / Wr * len(SHOWS)), len(SHOWS) - 1)
        play_show(SHOWS[idx]["glob"])
        return

    # ── PLAYING MODE — controls hidden → show them ──
    if not _ctrl.winfo_ismapped():
        _show_ctrl()
        return

    # ── PLAYING MODE — controls visible → route tap ──
    if sy > 90:
        # Tapped below controls bar → just reset hide timer
        _reset_hide()
        return

    if sx < Wr * 0.38:
        stop_show()
    elif sx > Wr * 0.82:
        _set_vol(_vol[0] + 10)
        _reset_hide()
    elif sx > Wr * 0.62:
        _set_vol(_vol[0] - 10)
        _reset_hide()
    else:
        _reset_hide()


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
