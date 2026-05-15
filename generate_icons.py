"""One-off script: generate PNG icons for special Kodi folder categories."""
from PIL import Image, ImageDraw
import os

RESOURCES = os.path.join(os.path.dirname(__file__), 'resources')
SIZE = 256
BG = (26, 26, 26, 255)
CLEAR = (0, 0, 0, 0)


def base(color=None):
    img = Image.new('RGBA', (SIZE, SIZE), CLEAR)
    d = ImageDraw.Draw(img)
    d.ellipse([8, 8, SIZE - 8, SIZE - 8], fill=BG)
    return img, d


def save(img, name):
    path = os.path.join(RESOURCES, name)
    img.save(path)
    print(f'  {path}')


# --- continue_watching: blue ring + right-arrow ---
img, d = base()
cx = cy = SIZE // 2
d.ellipse([cx-82, cy-82, cx+82, cy+82], outline=(66, 165, 245, 255), width=18)
# right-pointing play triangle
tri = [(cx+15, cy-28), (cx+15, cy+28), (cx+52, cy)]
d.polygon(tri, fill=(66, 165, 245, 255))
save(img, 'continue_watching.png')

# --- my_list: green bookmark ---
img, d = base()
GREEN = (76, 175, 80, 255)
bx1, bx2 = cx - 38, cx + 38
by1 = cy - 58
by2 = cy + 58
d.rectangle([bx1, by1, bx2, cy + 10], fill=GREEN)
d.polygon([(bx1, cy + 10), (cx, cy + 58), (bx2, cy + 10)], fill=GREEN)
# horizontal lines (list look)
WHITE = (255, 255, 255, 200)
for i, y in enumerate(range(cy - 38, cy, 16)):
    d.rectangle([bx1 + 10, y, bx2 - 10, y + 7], fill=WHITE)
save(img, 'my_list.png')

# --- top10: gold trophy ---
img, d = base()
GOLD = (255, 193, 7, 255)
# Cup body
d.ellipse([cx-40, cy-58, cx+40, cy+10], fill=GOLD)
# Stem
d.rectangle([cx-10, cy+10, cx+10, cy+38], fill=GOLD)
# Base
d.rectangle([cx-32, cy+38, cx+32, cy+52], fill=GOLD)
# Handles (arcs)
d.arc([cx-62, cy-44, cx-30, cy+4], start=120, end=240, fill=GOLD, width=10)
d.arc([cx+30, cy-44, cx+62, cy+4], start=-60, end=60, fill=GOLD, width=10)
save(img, 'top10.png')

# --- live: red broadcast icon ---
img, d = base()
RED = (244, 67, 54, 255)
WHITE = (255, 255, 255, 255)
# Concentric arcs (signal waves)
for r, w in [(70, 8), (50, 8), (30, 8)]:
    d.arc([cx - r, cy - r, cx + r, cy + r], start=210, end=330, fill=RED, width=w)
# Center dot
d.ellipse([cx-14, cy-14, cx+14, cy+14], fill=RED)
# LIVE text approximation: three vertical bars
for i, bx in enumerate([cx-20, cx-4, cx+12]):
    h = [28, 20, 28][i]
    d.rectangle([bx, cy + 22, bx + 8, cy + 22 + h], fill=WHITE)
save(img, 'live.png')

# --- episodic: purple TV/playlist ---
img, d = base()
PURPLE = (156, 39, 176, 255)
WHITE = (255, 255, 255, 200)
# TV outline
tv_x1, tv_y1, tv_x2, tv_y2 = cx-62, cy-50, cx+62, cy+30
d.rectangle([tv_x1, tv_y1, tv_x2, tv_y2], outline=PURPLE, width=8)
# Play triangle on screen
tri = [(cx-18, cy-28), (cx-18, cy+12), (cx+26, cy-8)]
d.polygon(tri, fill=PURPLE)
# Stand
d.rectangle([cx-22, cy+30, cx+22, cy+48], fill=PURPLE)
d.rectangle([cx-36, cy+48, cx+36, cy+58], fill=PURPLE)
save(img, 'episodic.png')

# --- screen: teal monitor ---
img, d = base()
TEAL = (0, 150, 136, 255)
# Monitor frame
d.rectangle([cx-70, cy-55, cx+70, cy+30], fill=TEAL)
# Screen inner
d.rectangle([cx-58, cy-43, cx+58, cy+18], fill=BG)
# Stand + base
d.rectangle([cx-12, cy+30, cx+12, cy+48], fill=TEAL)
d.rectangle([cx-34, cy+48, cx+34, cy+60], fill=TEAL)
# Accent dots bottom-right of screen
for i in range(3):
    bx = cx + 38 - i * 14
    d.ellipse([bx-4, cy+8, bx+4, cy+16], fill=TEAL)
save(img, 'screen.png')

print('Done.')
