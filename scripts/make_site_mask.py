# Робить docs/linum-mask.js: іконку Linum у вигляді маски з нулів і одиниць.
# Сайт розкладає частинки по білих лініях цієї маски, і з них складається Крик.
# Маска лежить у .js, а не в картинці, щоб сайт працював і просто з диска (file://).
#
# Запуск з папки Linum:
#   python scripts/make_site_mask.py

import base64
from pathlib import Path

from PIL import Image

SOURCE = Path("assets/icons/exported/linum-icon-1-outline.jpg")
TARGET = Path("docs/linum-mask.js")
SIZE = 320


def main():
    image = Image.open(SOURCE).convert("L").resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    bits = bytearray(SIZE * SIZE // 8)
    for index, value in enumerate(image.tobytes()):
        if value > 110:
            bits[index // 8] |= 1 << (index % 8)
    data = base64.b64encode(bytes(bits)).decode("ascii")
    TARGET.write_text(f'window.LINUM_MASK = {{ size: {SIZE}, bits: "{data}" }};\n', encoding="utf-8")
    white = sum(bin(byte).count("1") for byte in bits)
    print(f"{TARGET}: {white} білих пікселів з {SIZE * SIZE}")


if __name__ == "__main__":
    main()
