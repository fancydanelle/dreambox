#!/usr/bin/env python3
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
font_time  = ImageFont.truetype(TTF, 22)

_dummy = ImageDraw.Draw(Image.new("1", (device.width, device.height)))
_b1    = _dummy.textbbox((0, 0), "DREAMBOX", font=font_title)
_b3    = _dummy.textbbox((0, 0), "00:00 PM", font=font_time)
Y_TOP = _b1[3] + 4
Y_BOT = device.height - _b3[3] - 4
W     = device.width

NUM_FIREFLIES = 18


class Firefly:
    def __init__(self):
        self.x  = random.uniform(0, W)
        self.y  = random.uniform(Y_TOP, Y_BOT)
        self.vx = random.uniform(-0.3, 0.3)
        self.vy = random.uniform(-0.2, 0.2)
        self.lit   = False
        self.timer = random.randint(0, 40)
        self._new_phase()

    def _new_phase(self):
        if self.lit:
            self.lit   = False
            self.timer = random.randint(15, 50)   # dark: 1.5–5 s at 10 fps
        else:
            self.lit   = True
            self.timer = random.randint(6, 18)    # glowing: 0.6–1.8 s

    def update(self, draw):
        # Gentle organic drift
        self.vx += random.uniform(-0.04, 0.04)
        self.vy += random.uniform(-0.03, 0.03)
        self.vx  = max(-0.35, min(0.35, self.vx))
        self.vy  = max(-0.22, min(0.22, self.vy))
        self.x  += self.vx
        self.y  += self.vy

        # Soft bounce off strip edges
        if self.x < 1:
            self.vx = abs(self.vx)
        elif self.x > W - 2:
            self.vx = -abs(self.vx)
        if self.y < Y_TOP:
            self.vy = abs(self.vy)
        elif self.y > Y_BOT:
            self.vy = -abs(self.vy)

        self.timer -= 1
        if self.timer <= 0:
            self._new_phase()

        if self.lit:
            px, py = int(self.x), int(self.y)
            # Centre pixel + soft cross halo for glow effect
            draw.point((px, py), fill=255)
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = px + dx, py + dy
                if 0 <= nx < W and Y_TOP <= ny <= Y_BOT:
                    draw.point((nx, ny), fill=255)


fireflies = [Firefly() for _ in range(NUM_FIREFLIES)]

while True:
    now = datetime.now().strftime("%I:%M %p")

    image = Image.new("1", (device.width, device.height))
    draw  = ImageDraw.Draw(image)

    draw.text((0, 0),         "DREAMBOX", font=font_title, fill=255)
    draw.text((0, Y_BOT + 4), now,        font=font_time,  fill=255)

    for f in fireflies:
        f.update(draw)

    device.display(image)
    time.sleep(0.1)
