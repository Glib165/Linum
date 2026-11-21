# Кольори і шрифт інтерфейсу Linum.
# Кожен колір задано парою: (світла тема, темна тема).
# customtkinter сам бере потрібний колір, коли тема змінюється.

BG = ("#FAF9F7", "#1A1A1A")
SIDEBAR = ("#F3F2EF", "#151515")
SURFACE = ("#FFFFFF", "#262626")
SURFACE_HOVER = ("#F0EEEA", "#2F2F2F")
SELECTED = ("#EAE8E3", "#303030")
BORDER = ("#E4E1DC", "#363636")

TEXT = ("#1A1A1A", "#ECECEC")
MUTED = ("#7A7875", "#8F8F8F")

ACCENT = ("#1A1A1A", "#ECECEC")
ACCENT_HOVER = ("#333333", "#D0D0D0")
ACCENT_TEXT = ("#FFFFFF", "#1A1A1A")

DANGER = ("#B42318", "#F97066")

# Виділений мишкою текст
SELECTION = ("#C9DDF7", "#3B4F6B")

# Віконце рівня міркувань: синя назва рівня і заповнена частина повзунка
LEVEL = ("#2672A8", "#5AA9DA")
LEVEL_FILL = ("#2F80B9", "#2D78A8")
LEVEL_TRACK = ("#E3E0DB", "#333333")

# Перегляд фото на весь екран завжди темний, щоб картинка була в центрі уваги
VIEWER_BG = ("#111111", "#0E0E0E")
VIEWER_TEXT = ("#EDEDED", "#EDEDED")
VIEWER_MUTED = ("#9A9A9A", "#9A9A9A")
VIEWER_HOVER = ("#2A2A2A", "#2A2A2A")

# Шрифт інтерфейсу: Segoe UI на Windows, системний Helvetica Neue на Mac
FONT_FAMILY = "Helvetica Neue" if __import__("sys").platform == "darwin" else "Segoe UI"
