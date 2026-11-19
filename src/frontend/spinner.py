# Анімація "думаю": кружок із точок навколо центральної точки.
# Кільце повільно обертається, ним біжить хвиля світла, а точка в центрі пульсує.
# Кадри малюються один раз через PIL, а вікно потім просто показує їх по колу.

import math

from PIL import Image, ImageDraw

DOTS = 10          # скільки точок у кільці
FRAMES = 60        # кадрів в одному колі анімації
TILT = math.radians(28)  # нахил кільця, щоб воно виглядало об'ємним


def make_frames(size, color):
    """color: (r, g, b) колір точок. Тло прозоре."""
    scale = 4
    big = size * scale
    center = big / 2
    radius = big * 0.34
    dot = big * 0.055
    frames = []

    for frame in range(FRAMES):
        t = frame / FRAMES
        image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        dots = []

        for i in range(DOTS):
            # За одне коло анімації кільце повертається на одну точку, тож перехід непомітний
            angle = 2 * math.pi * (i + t) / DOTS
            # Трохи нерівний радіус робить кільце "живим"
            r = radius * (1 + 0.07 * math.sin(3 * angle + 1.3))
            x = r * math.cos(angle)
            y = r * math.sin(angle) * math.cos(TILT)
            depth = math.sin(angle) * math.sin(TILT)  # від -1 (далеко) до 1 (близько)

            # Хвиля світла пробігає все кільце за одне коло анімації
            wave = (1 + math.cos(2 * math.pi * (i / DOTS - t))) / 2
            brightness = 0.18 + 0.82 * wave ** 3
            brightness *= 0.75 + 0.25 * (depth + 1) / 2
            dot_size = dot * (0.8 + 0.35 * wave) * (0.85 + 0.15 * (depth + 1) / 2)
            dots.append((depth, x, y, dot_size, brightness))

        # Центральна точка пульсує двічі за коло
        pulse = (1 + math.cos(4 * math.pi * t)) / 2
        dots.append((0, 0, 0, dot * (0.9 + 0.4 * pulse), 0.45 + 0.55 * pulse))

        for _, x, y, dot_size, brightness in sorted(dots):
            alpha = int(255 * brightness)
            draw.ellipse(
                (center + x - dot_size, center + y - dot_size, center + x + dot_size, center + y + dot_size),
                fill=(*color, alpha),
            )
        frames.append(image.resize((size, size), Image.LANCZOS))
    return frames
