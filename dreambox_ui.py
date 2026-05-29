import os
import re
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

# ── MPV IPC ──────────────────────────────────────────────────────────────────
_IPC = "/tmp/dreambox_mpv.sock"

def _mpv_cmd(*args):
    try:
        s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(_IPC)
        import json
        s.sendall(json.dumps({"command": list(args)}).encode() + b"\n")
        s.close()
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
_proc      = [None]
_exit_hide = [None]

# ── EXIT BUTTON — only shown when user taps during playback ──────────────────
EW, EH = 240, 90
EX, EY = (SW - EW) // 2, (SH - EH) // 2

_exit_frame = tk.Frame(root, bg="#992222",
                       highlightbackground="#cc4444", highlightthickness=2)
tk.Button(_exit_frame, text="✕   EXIT", font=("Helvetica", 24, "bold"),
          fg="white", bg="#992222", activebackground="#cc3333",
          activeforeground="white", relief="flat", bd=0,
          command=lambda: stop_show()).pack(expand=True, fill="both")


def _show_exit():
    if _exit_hide[0]:
        root.after_cancel(_exit_hide[0])
    _exit_frame.place(x=EX, y=EY, width=EW, height=EH)
    _exit_frame.lift()
    _exit_hide[0] = root.after(4000, _hide_exit)

def _hide_exit():
    _exit_frame.place_forget()
    _exit_hide[0] = None


def _keep_on_top():
    if _proc[0] is not None:
        if _exit_frame.winfo_ismapped():
            _exit_frame.lift()
        root.after(200, _keep_on_top)


# ── TAP HANDLER ───────────────────────────────────────────────────────────────
_last_tap = [0]

def _on_tap(event):
    now = time.time()
    if now - _last_tap[0] < 0.3:
        return
    _last_tap[0] = now

    if _proc[0] is None:
        # menu — pick show by which half was tapped
        sx = event.x_root - root.winfo_rootx()
        idx = 0 if sx < SW // 2 else 1
        play_show(idx)
        return

    # playing — show exit button (or reset its timer)
    _show_exit()


root.bind_all("<Button-1>", _on_tap)


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
        ["mpv", f"--wid={xid}", "--vo=x11", "--hwdec=auto",
         "--loop-playlist=inf", "--osd-level=0", "--really-quiet",
         "--no-terminal", f"--input-ipc-server={_IPC}"] + files,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    )
    root.after(200, _keep_on_top)


def stop_show():
    _hide_exit()
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
