"""Makes the placeholder wallpaper: Migood dark gradient + soft green glow +
the wordmark. Replace assets/wallpaper.png with real art any time.

    python3 build/make-wallpaper.py   (needs Pillow: pip install pillow)
"""
import os
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")
W, H = 1920, 1080

# Vertical gradient #1d2a36 -> #0a0d12 (the Migood app's dark colours).
top, bottom = (0x1D, 0x2A, 0x36), (0x0A, 0x0D, 0x12)
img = Image.new("RGB", (W, H))
px = ImageDraw.Draw(img)
for y in range(H):
    t = y / (H - 1)
    px.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))

# Two blurred Migood-green (#2ecc71) glows.
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
g = ImageDraw.Draw(glow)
g.ellipse([W * 0.55, -H * 0.3, W * 1.25, H * 0.6], fill=(0x2E, 0xCC, 0x71, 70))
g.ellipse([-W * 0.25, H * 0.55, W * 0.35, H * 1.35], fill=(0x2E, 0xCC, 0x71, 45))
img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(160)))

# Wordmark in the middle, a bit above centre (the shelf covers the bottom).
logo = Image.open(os.path.join(ASSETS, "migood-logo.png")).convert("RGBA")
scale = (W * 0.28) / logo.width
logo = logo.resize((round(logo.width * scale), round(logo.height * scale)), Image.LANCZOS)
img.alpha_composite(logo, ((W - logo.width) // 2, (H - logo.height) // 2 - 60))

img.convert("RGB").save(os.path.join(ASSETS, "wallpaper.png"), optimize=True)
print("wrote assets/wallpaper.png")
