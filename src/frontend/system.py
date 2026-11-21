# Дії, які на Windows і Mac робляться по-різному: відкрити файл, показати його в папці,
# скопіювати картинку в буфер обміну.
#
# Яка зараз система, каже sys.platform:
#   "win32"  - Windows
#   "darwin" - Mac (macOS)

import os
import subprocess
import sys
from pathlib import Path

WINDOWS = sys.platform == "win32"
MAC = sys.platform == "darwin"


def open_path(path):
    """Відкриває файл чи папку програмою за замовчуванням (картинку - переглядачем, папку - провідником)."""
    path = Path(path).resolve()
    if MAC:
        subprocess.Popen(["open", str(path)])
    else:
        os.startfile(path)


def show_in_folder(path):
    """Відкриває папку з файлом і виділяє в ній сам файл."""
    path = Path(path).resolve()
    if MAC:
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(f'explorer /select,"{path}"')


def copy_image_mac(path):
    # На Mac через вбудовану програму osascript: "поклади в буфер цей файл як картинку PNG"
    from PIL import Image

    png = Path("outputs/tmp/clipboard.png").resolve()
    png.parent.mkdir(parents=True, exist_ok=True)
    Image.open(path).convert("RGB").save(png)
    script = f'set the clipboard to (read (POSIX file "{png}") as «class PNGf»)'
    subprocess.run(["osascript", "-e", script], check=True)
