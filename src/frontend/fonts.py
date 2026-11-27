# Шрифт чату Linum: Linum Serif (змінена Lora, ліцензія SIL OFL 1.1, див. assets/fonts/OFL.txt).
# Ним пишуться повідомлення в чаті і поле вводу. Кнопки й меню лишаються шрифтом інтерфейсу.
#
# Шрифт не встановлюється в систему: на Windows Linum підключає його лише для себе
# (AddFontResourceEx з позначкою FR_PRIVATE), і після закриття програми він зникає.

import sys
from pathlib import Path

FAMILY = "Linum Serif"
FILES = ["LinumSerif-Regular.ttf", "LinumSerif-Bold.ttf"]
FOLDER = Path(__file__).resolve().parents[2] / "assets" / "fonts"

# Якщо свій шрифт підключити не вдалося, беремо серифний шрифт, який є в системі
FALLBACK = "Georgia"


def load_chat_font():
    """Підключає Linum Serif і повертає назву родини шрифту для чату."""
    if sys.platform != "win32":
        # На Mac підключення шрифту лише для програми ще не зроблено: поки системний серифний
        return FALLBACK
    try:
        import ctypes

        private = 0x10  # FR_PRIVATE: шрифт бачить тільки Linum
        loaded = 0
        for name in FILES:
            path = FOLDER / name
            if path.exists():
                loaded += ctypes.windll.gdi32.AddFontResourceExW(str(path), private, 0)
        return FAMILY if loaded else FALLBACK
    except (OSError, AttributeError):
        return FALLBACK
