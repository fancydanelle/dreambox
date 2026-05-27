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
font_time  = ImageFont.truetype(TTF, 22)

_dummy = ImageDraw.Draw(Image.new("1", (device.width, device.height)))
_b1    = _dummy.textbbox((0, 0), "DREAMBOX", font=font_title)
_b3    = _dummy.textbbox((0, 0), "00:00 PM", font=font_time)
Y_TOP  = _b1[3] + 2
Y_BOT  = device.height - _b3[3] - 2
W      = device.width
CX     = W / 2
CY     = (Y_TOP + Y_BOT) / 2
# Scale Y so stars use the full strip height
Y_SCALE = (Y_BOT - Y_TOP) / W

NUM_STARS = 70
ACCEL     = 1.12


class Star:
    def __init__(self, scatter=0):
        self.spawn()
        for _ in range(scatter):
            self._step()

    def spawn(self):
        angle   = random.uniform(0, 2 * math.pi)
        speed   = random.uniform(0.3, 1.2)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.x  = CX
        self.y  = CY

    def _step(self):
        self.x  += self.vx
        self.y  += self.vy * Y_SCALE
        self.vx *= ACCEL
        self.vy *= ACCEL

    def update(self, draw):
        px, py = self.x, self.y
        self._step()
        if not (0 <= self.x < W and Y_TOP <= self.y <= Y_BOT):
            self.spawn()
            return
        draw.line([(int(px), int(py)), (int(self.x), int(self.y))], fill=255)


stars = [Star(scatter=random.randint(0, 15)) for _ in range(NUM_STARS)]

while True:
    now = datetime.now().strftime("%I:%M %p")

    image = Image.new("1", (device.width, device.height))
    draw  = ImageDraw.Draw(image)

    draw.text((0, 0),         "DREAMBOX", font=font_title, fill=255)
    draw.text((0, Y_BOT + 1), now,        font=font_time,  fill=255)

    for s in stars:
        s.update(draw)

    device.display(image)
    time.sleep(0.1)
