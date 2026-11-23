# Робить docs/linum-mask.js: дві маски з нулів і одиниць для частинок на сайті.
#   LINUM_MASK      іконка Linum (Крик): з неї складається перший екран
#   LINUM_STRUCTURE синя структура: у неї частинки перетікають, коли сторінку гортають униз
# Маски лежать у .js, а не в картинках, щоб сайт працював і просто з диска (file://).
#
# Запуск з папки Linum:
#   python scripts/make_site_mask.py

import base64
from pathlib import Path

from PIL import Image

TARGET = Path("docs/linum-mask.js")

# (назва в JS, картинка, ширина, висота, поріг яскравості)
MASKS = [
    ("LINUM_MASK", Path("assets/icons/exported/linum-icon-1-outline.jpg"), 320, 320, 110),
    ("LINUM_STRUCTURE", Path("docs/images/structure.png"), 480, 320, 140),
]


def mask(source, width, height, threshold):
    # Яскравість беремо як найсвітліший з кольорів: інакше сині лінії здаються темними
    image = Image.open(source).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    bits = bytearray((width * height + 7) // 8)
    pixels = image.tobytes()
    for index in range(width * height):
        if max(pixels[index * 3:index * 3 + 3]) > threshold:
            bits[index // 8] |= 1 << (index % 8)
    return bits


def main():
    lines = []
    for name, source, width, height, threshold in MASKS:
        bits = mask(source, width, height, threshold)
        data = base64.b64encode(bytes(bits)).decode("ascii")
        lines.append(f'window.{name} = {{ width: {width}, height: {height}, bits: "{data}" }};')
        white = sum(bin(byte).count("1") for byte in bits)
        print(f"{name}: {white} світлих пікселів з {width * height}")
    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
