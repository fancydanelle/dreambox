#!/usr/bin/env python3
import math
import random
import time
from datetime import datetime

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw, ImageFont

serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)

TTF = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def fit_font(text, max_width, start=40):
    size = start
    while size > 4:
        f = ImageFont.truetype(TTF, size)
        if f.getlength(text) <= max_width:
            return f
        size -= 1
    return ImageFont.truetype(TTF, 4)

font_title = fit_font("DREAMBOX", device.width)
font_time  = font_title

_dummy = ImageDraw.Draw(Image.new("1", (device.width, device.height)))
_b1    = _dummy.textbbox((0, 0), "DREAMBOX", font=font_title)
_b3    = _dummy.textbbox((0, 0), "00:00 PM", font=font_time)

W      = device.width
H      = device.height
Y_TOP  = _b1[3] + 4
TIME_Y = H - _b3[3] - 1
Y_BOT  = max(Y_TOP + 4, TIME_Y - 8)

CX      = W // 2
CY      = (Y_TOP + Y_BOT) // 2
Y_SCALE = (Y_BOT - Y_TOP) / W    # squish vertically to fill the strip
ACCEL   = 1.08                   # speed multiplier per frame
NUM_STARS = 40

# SSD1306 pages (8 pixel rows each)
_ROW_BYTES = (W + 7) // 8
_ANIM_P0   = Y_TOP // 8
_ANIM_P1   = Y_BOT // 8
_TIME_P0   = TIME_Y // 8
_TIME_P1   = (H - 1) // 8


def _write_pages(image, p0, p1):
    """Write only SSD1306 pages p0..p1; all other pages are untouched."""
    raw  = image.tobytes()
    data = []
    for p in range(p0, p1 + 1):
        for col in range(W):
            byte = 0
            for bit in range(8):
                row = p * 8 + bit
                if row < H:
                    b = raw[row * _ROW_BYTES + col // 8]
                    if b & (0x80 >> (col % 8)):
                        byte |= (1 << bit)
            data.append(byte)
    serial.command(
        0x20, 0x00,
        0x21, 0, W - 1,
        0x22, p0, p1,
    )
    serial.data(data)


class Star:
    def __init__(self, fresh=False):
        self.reset(fresh)

    def reset(self, fresh=False):
        self.angle = random.uniform(0, 2 * math.pi)
        self.speed = random.uniform(0.3, 0.8)
        # Spread initial distances so stars don't all burst at once on startup
        self.dist  = random.uniform(0, W // 2) if fresh else random.uniform(0, 2)

    def update(self, draw):
        self.dist  += self.speed
        self.speed *= ACCEL

        px = int(CX + math.cos(self.angle) * self.dist)
        py = int(CY + math.sin(self.angle) * self.dist * Y_SCALE)

        if 0 <= px < W and Y_TOP <= py <= Y_BOT:
            draw.point((px, py), fill=255)
        else:
            self.reset()


stars = [Star(fresh=True) for _ in range(NUM_STARS)]

# ── Initial full-screen draw ───────────────────────────────────────────────────
_now0 = datetime.now().strftime("%I:%M %p")
_img0 = Image.new("1", (W, H))
_d0   = ImageDraw.Draw(_img0)
_d0.text((0, 0), "DREAMBOX", font=font_title, fill=255)
_d0.text(((W - int(font_time.getlength(_now0))) // 2, TIME_Y), _now0, font=font_time, fill=255)
device.display(_img0)

_prev_now  = _now0
_prev_anim = None

# ── Main loop ─────────────────────────────────────────────────────────────────
while True:
    now   = datetime.now().strftime("%I:%M %p")
    image = Image.new("1", (W, H))
    draw  = ImageDraw.Draw(image)

    draw.text((0, 0), "DREAMBOX", font=font_title, fill=255)
    draw.text(((W - int(font_time.getlength(now))) // 2, TIME_Y), now, font=font_time, fill=255)

    for s in stars:
        s.update(draw)

    raw = image.tobytes()

    if now != _prev_now:
        _write_pages(image, _TIME_P0, _TIME_P1)
        _prev_now = now

    anim_slice = raw[_ANIM_P0 * 8 * _ROW_BYTES : (_ANIM_P1 + 1) * 8 * _ROW_BYTES]
    if anim_slice != _prev_anim:
        _write_pages(image, _ANIM_P0, _ANIM_P1)
        _prev_anim = anim_slice

    time.sleep(0.1)
