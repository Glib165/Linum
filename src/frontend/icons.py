# Прості лінійні іконки, намальовані кодом.
# Кожна малюється білим на великому полотні, а потім фарбується
# у колір світлої і темної теми та зменшується, щоб лінії були гладкими.

import customtkinter as ctk
from PIL import Image, ImageDraw

CANVAS = 96
STROKE = 7


def _plus(d):
    d.line((48, 16, 48, 80), fill=255, width=STROKE)
    d.line((16, 48, 80, 48), fill=255, width=STROKE)


def _search(d):
    d.ellipse((14, 14, 62, 62), outline=255, width=STROKE)
    d.line((55, 55, 82, 82), fill=255, width=STROKE)


def _gallery(d):
    for x, y in ((12, 12), (52, 12), (12, 52), (52, 52)):
        d.rounded_rectangle((x, y, x + 32, y + 32), radius=7, outline=255, width=STROKE)


def _folder(d):
    d.rounded_rectangle((10, 30, 86, 80), radius=8, outline=255, width=STROKE)
    d.line((14, 32, 14, 18, 38, 18, 46, 30), fill=255, width=STROKE, joint="curve")


def _sidebar(d):
    d.rounded_rectangle((8, 16, 88, 80), radius=10, outline=255, width=STROKE)
    d.line((36, 16, 36, 80), fill=255, width=STROKE)


def _settings(d):
    # Три повзунки, як у мікшері
    for y, x in ((24, 62), (48, 32), (72, 56)):
        d.line((12, y, 84, y), fill=255, width=STROKE)
        d.ellipse((x - 10, y - 10, x + 10, y + 10), fill=0, outline=255, width=STROKE)


def _trash(d):
    d.line((14, 26, 82, 26), fill=255, width=STROKE)
    d.line((36, 26, 36, 14, 60, 14, 60, 26), fill=255, width=STROKE, joint="curve")
    d.rounded_rectangle((24, 30, 72, 84), radius=8, outline=255, width=STROKE)


def _refresh(d):
    d.arc((16, 16, 80, 80), start=-50, end=250, fill=255, width=STROKE)
    d.polygon([(58, 6), (82, 20), (58, 34)], fill=255)


def _open(d):
    d.line((54, 18, 34, 18, 18, 34, 18, 78, 62, 78, 78, 62, 78, 42), fill=255, width=STROKE, joint="curve")
    d.line((44, 52, 82, 14), fill=255, width=STROKE)
    d.line((60, 14, 82, 14, 82, 36), fill=255, width=STROKE, joint="curve")


def _copy(d):
    d.rounded_rectangle((32, 32, 84, 84), radius=9, outline=255, width=STROKE)
    d.line((22, 66, 12, 66, 12, 12, 66, 12, 66, 22), fill=255, width=STROKE, joint="curve")


def _palette(d):
    d.ellipse((10, 12, 86, 84), outline=255, width=STROKE)
    for x, y in ((32, 34), (52, 26), (68, 44)):
        d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=255)
    d.ellipse((28, 54, 46, 72), outline=255, width=6)


def _frame(d):
    d.rounded_rectangle((10, 16, 86, 80), radius=9, outline=255, width=STROKE)
    d.line((18, 70, 40, 46, 54, 60, 64, 50, 80, 68), fill=255, width=STROKE, joint="curve")
    d.ellipse((58, 26, 70, 38), fill=255)


def _model(d):
    # Кубик: модель ШІ
    d.polygon([(48, 10), (84, 30), (84, 68), (48, 88), (12, 68), (12, 30)], outline=255, width=STROKE)
    d.line((12, 30, 48, 50, 84, 30), fill=255, width=STROKE, joint="curve")
    d.line((48, 50, 48, 88), fill=255, width=STROKE)


def _bulb(d):
    # Лампочка: рівень міркувань
    d.arc((22, 8, 74, 60), start=135, end=405, fill=255, width=STROKE)
    d.line((31, 52, 36, 66, 60, 66, 65, 52), fill=255, width=STROKE, joint="curve")
    d.line((38, 77, 58, 77), fill=255, width=STROKE)
    d.line((42, 88, 54, 88), fill=255, width=STROKE)


def _close(d):
    d.line((22, 22, 74, 74), fill=255, width=STROKE + 2)
    d.line((74, 22, 22, 74), fill=255, width=STROKE + 2)


DRAWERS = {
    "close": _close,
    "plus": _plus,
    "search": _search,
    "gallery": _gallery,
    "folder": _folder,
    "sidebar": _sidebar,
    "settings": _settings,
    "trash": _trash,
    "refresh": _refresh,
    "open": _open,
    "copy": _copy,
    "palette": _palette,
    "frame": _frame,
    "model": _model,
    "bulb": _bulb,
}


def make_icon(name, size, colors):
    # colors це пара (колір для світлої теми, колір для темної)
    mask = Image.new("L", (CANVAS, CANVAS), 0)
    DRAWERS[name](ImageDraw.Draw(mask))

    def painted(color):
        image = Image.new("RGBA", mask.size, color)
        image.putalpha(mask)
        return image

    return ctk.CTkImage(light_image=painted(colors[0]), dark_image=painted(colors[1]), size=(size, size))
