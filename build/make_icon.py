"""生成应用图标 build/icon.ico（打包 exe 前运行一次）"""
import os

from PIL import Image, ImageDraw

SIZE = 256
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 深色圆角底
d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=52, fill=(12, 13, 15, 255))
d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=52, outline=(46, 64, 70, 255), width=6)

# 四格：左上强调色、其余灰
accent = (46, 230, 176, 255)
grey = (90, 104, 110, 255)
d.rounded_rectangle([44, 64, 118, 138], radius=10, fill=accent)
d.rounded_rectangle([134, 64, 208, 138], radius=10, fill=grey)
d.rounded_rectangle([44, 154, 118, 186], radius=8, fill=grey)
d.rounded_rectangle([134, 154, 208, 186], radius=8, fill=grey)

out = os.path.join(OUT_DIR, 'icon.ico')
img.save(out, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print('saved', out)
