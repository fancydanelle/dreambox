import os
import re
import glob as glob_module
import subprocess
import threading
import time
import tkinter as tk
from PIL import Image, ImageTk
import evdev
from evdev import ecodes

# --- GPIO / LED SETUP ---
LED_PIN         = 18
BRIGHTNESS_FULL = 100
BRIGHTNESS_DIM  = 15

try:
    import lgpio
    _chip = lgpio.gpiochip_open(0)
    lgpio.gpio_claim_output(_chip, LED_PIN, 0)
    lgpio.tx_pwm(_chip, LED_PIN, 100, BRIGHTNESS_FULL)
    GPIO_AVAILABLE = True
except Exception:
    GPIO_AVAILABLE = False

def leds_full():
    if GPIO_AVAILABLE:
        lgpio.tx_pwm(_chip, LED_PIN, 100, BRIGHTNESS_FULL)

def leds_dim():
    if GPIO_AVAILABLE:
        lgpio.tx_pwm(_chip, LED_PIN, 100, BRIGHTNESS_DIM)


time.sleep(2)


# --- PRIMARY MONITOR GEOMETRY ---
def get_primary_display():
    try:
        out = subprocess.check_output(["xrandr", "--current"],
                                      stderr=subprocess.DEVNULL).decode()
        for line in out.splitlines():
            if " connected primary" in line:
                m = re.search(r'(\d+)x(\d+)\+(\d+)\+(\d+)', line)
                if m:
                    return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    except Exception:
        pass
    return 1920, 1080, 0, 0

DISP_W, DISP_H, DISP_X, DISP_Y = get_primary_display()

TOUCH_DEV  = "/dev/input/event5"
TOUCH_XMAX = 799
TOUCH_YMAX = 479


# --- VOLUME ---
def _read_system_volume():
    try:
        out = subprocess.check_output(["amixer", "sget", "Master"],
                                      stderr=subprocess.DEVNULL).decode()
        m = re.search(r'\[(\d+)%\]', out)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return 80

vol_state = {
    "level":    _read_system_volume(),
    "panel":    None,   # tk.Frame child of play window
    "label":    None,
    "after_id": None,
}

def _apply_volume():
    v = vol_state["level"]
    os.system(f"amixer -q sset Master {v}% 2>/dev/null || "
              f"pactl set-sink-volume @DEFAULT_SINK@ {v}% 2>/dev/null")
    if vol_state["label"]:
        try:
            vol_state["label"].config(text=f"{v}%")
        except Exception:
            pass

def vol_up():
    vol_state["level"] = min(100, vol_state["level"] + 10)
    _apply_volume()
    _reset_vol_timer()

def vol_down():
    vol_state["level"] = max(0, vol_state["level"] - 10)
    _apply_volume()
    _reset_vol_timer()

def _reset_vol_timer():
    if vol_state["after_id"]:
        root.after_cancel(vol_state["after_id"])
    vol_state["after_id"] = root.after(3000, hide_vol_panel)

def show_vol_panel():
    if vol_state["panel"]:
        _reset_vol_timer()
        return
    pw = play_window[0]
    if not pw:
        return
    try:
        ph = 240
        panel = tk.Frame(pw, bg="#222222")
        panel.place(x=0, y=(DISP_H - ph) // 2, width=DISP_W, height=ph)
        panel.lift()

        f_btn = ("Helvetica", 72, "bold")
        f_vol = ("Helvetica", 60, "bold")

        tk.Label(panel, text="-", font=f_btn, fg="white",   bg="#222222").place(relx=0.15, rely=0.5, anchor="center")
        lbl = tk.Label(panel, text=f"{vol_state['level']}%", font=f_vol, fg="#eeeeee", bg="#222222")
        lbl.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(panel, text="+", font=f_btn, fg="white",   bg="#222222").place(relx=0.85, rely=0.5, anchor="center")

        panel.update()
        vol_state["panel"] = panel
        vol_state["label"] = lbl
        _reset_vol_timer()
    except Exception as e:
        with open("/tmp/tap_debug.log", "a") as f:
            f.write(f"show_vol_panel error: {e}\n")

def hide_vol_panel():
    if vol_state["panel"]:
        try:
            vol_state["panel"].destroy()
        except Exception:
            pass
        vol_state["panel"] = None
        vol_state["label"] = None
    vol_state["after_id"] = None


# --- SHOWS ---
SHOWS = [
    {"title": "Wonderfalls S1", "glob":  "~/videos/S01E*.mp4",
     "cover": "~/videos/covers/wonderfalls.jpg"},
    {"title": "The Office S1",  "glob":  "~/videos/office/THE_OFFICE_T*.mp4",
     "cover": "~/videos/covers/office.jpg"},
]


root = tk.Tk()
root.attributes("-fullscreen", True)
root.config(cursor="none", bg="black")

vlc_playing = [False]
play_window = [None]


# --- EVDEV TOUCH MONITOR ---
def touch_monitor():
    try:
        dev = evdev.InputDevice(TOUCH_DEV)
        tx, ty = 0, 0
        for event in dev.read_loop():
            if not vlc_playing[0]:
                continue
            if event.type == ecodes.EV_ABS:
                if event.code in (ecodes.ABS_X, ecodes.ABS_MT_POSITION_X):
                    tx = event.value
                elif event.code in (ecodes.ABS_Y, ecodes.ABS_MT_POSITION_Y):
                    ty = event.value
            elif (event.type == ecodes.EV_KEY
                  and event.code == ecodes.BTN_TOUCH
                  and event.value == 1):
                sx = (tx / TOUCH_XMAX) * DISP_W
                sy = (ty / TOUCH_YMAX) * DISP_H
                if sx < DISP_W * 0.20 and sy < DISP_H * 0.20:
                    root.after(0, stop_show)
                elif vol_state["panel"]:
                    if sx < DISP_W * 0.33:
                        root.after(0, vol_down)
                    elif sx > DISP_W * 0.67:
                        root.after(0, vol_up)
                    else:
                        root.after(0, _reset_vol_timer)
                elif DISP_W * 0.25 < sx < DISP_W * 0.75 and DISP_H * 0.25 < sy < DISP_H * 0.75:
                    root.after(0, show_vol_panel)
    except Exception as e:
        with open("/tmp/tap_debug.log", "a") as f:
            f.write(f"evdev error: {e}\n")

threading.Thread(target=touch_monitor, daemon=True).start()


# --- PLAYBACK ---
def play_show(glob_path):
    os.system("pkill -f vlc; pkill -f cvlc")
    files = sorted(glob_module.glob(os.path.expanduser(glob_path)))
    if not files:
        return

    # Fullscreen play window — VLC embeds inside it
    pw = tk.Toplevel(root)
    pw.attributes("-fullscreen", True)
    pw.config(bg="black", cursor="none")
    for _ in range(5):
        pw.update()

    # Video container — sized explicitly from known display dimensions
    video_frame = tk.Frame(pw, bg="black")
    video_frame.place(x=DISP_X, y=DISP_Y, width=DISP_W, height=DISP_H)
    for _ in range(3):
        pw.update()

    xid = video_frame.winfo_id()
    play_window[0] = pw
    leds_dim()
    vlc_playing[0] = True

    vlc_env = os.environ.copy()
    vlc_env.pop("WAYLAND_DISPLAY", None)
    vlc_env["DISPLAY"] = ":0"
    subprocess.Popen(
        ["cvlc", "--no-osd", "--no-video-title-show", "--quiet", "--loop",
         f"--drawable-xid={xid}"] + files,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=vlc_env,
    )


def stop_show():
    vlc_playing[0] = False
    os.system("pkill -f vlc; pkill -f cvlc")
    hide_vol_panel()
    if play_window[0]:
        play_window[0].destroy()
        play_window[0] = None
    leds_full()
    root.deiconify()
    root.lift()
    root.focus_force()


# --- MENU CARDS ---
def make_show_card(parent, show):
    card = tk.Frame(parent, bg="black")
    cover_path = os.path.expanduser(show["cover"])
    bg_label = tk.Label(card, bg="black")
    bg_label.place(relx=0, rely=0, relwidth=1, relheight=1)
    bg_label.bind("<Button-1>", lambda e, g=show["glob"]: play_show(g))

    def on_resize(event):
        w, h = event.width, event.height
        if w > 1 and h > 1:
            try:
                img = Image.open(cover_path).resize((w, h), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                bg_label.config(image=photo)
                bg_label.photo = photo
            except Exception:
                card.config(bg="#1c1c1c")

    card.bind("<Configure>", on_resize)
    return card


main_frame = tk.Frame(root, bg="black")
main_frame.pack(fill="both", expand=True)

for show in SHOWS:
    card = make_show_card(main_frame, show)
    card.pack(side="left", fill="both", expand=True)


# --- CLEANUP ---
def on_close():
    stop_show()
    if GPIO_AVAILABLE:
        lgpio.tx_pwm(_chip, LED_PIN, 100, 0)
        lgpio.gpiochip_close(_chip)
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()
