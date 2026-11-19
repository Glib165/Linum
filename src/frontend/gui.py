# Головне вікно програми Linum

import ctypes
import os
import random
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image, ImageDraw

from config.config import (
    APP_NAME,
    APP_VERSION,
    CHATS_FILE,
    DEFAULT_MODEL,
    ICO_PATH,
    ICON_PATH,
    MODELS,
    NEGATIVE_PROMPT,
    OUTPUTS_DIR,
    SETTINGS_FILE,
    UPLOADS_DIR,
    SIZES,
    STYLES,
    REASONING,
    DEFAULT_REASONING,
)
from src.backend.services.chat_store import ChatStore
from src.backend.services.settings_store import SettingsStore
from src.frontend import theme
from src.frontend.icons import make_icon
from src.frontend.widgets import (
    PromptBox,
    SelectableText,
    fade_in,
    install_clipboard_keys,
    refresh_theme,
    themed,
)

THEMES = {"Світла": "light", "Темна": "dark", "Системна": "system"}
MODEL_TIERS = {"Fornax": "швидка", "Gaia": "збалансована", "Cygnus": "найкраща"}
LANGUAGE_NAMES = {"uk": "з української", "ru": "з російської"}
LANGUAGE_HINT = "Enter надсилає, Shift+Enter переносить рядок"

# Анімація "думаю" (кільце з точок): розмір кадрів і колір точок у світлій і темній темі
SPINNER_FRAME_SIZE = 144
SPINNER_COLORS = {"light": (26, 26, 26), "dark": (240, 240, 240)}

IMAGE_SIZE = 448
THUMB_SIZE = 172
CONTENT_MAX_WIDTH = 760


def shorten(text, length):
    # Для заголовків і підписів: переноси рядків стають пробілами
    text = " ".join(text.split())
    if len(text) <= length:
        return text
    return text[: length - 1].rstrip() + "…"


def rounded(image, radius):
    # Робить заокруглені кути у картинки, як у карток інтерфейсу
    image = image.convert("RGBA")
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width, image.height), radius=radius, fill=255)
    image.putalpha(mask)
    return image


def fit(width, height, longest):
    # Розмір для показу: найдовша сторона дорівнює longest, пропорції зберігаються
    scale = longest / max(width, height)
    return round(width * scale), round(height * scale)


def load_icon_mask(path):
    # Іконка це білі лінії на чорному тлі. Яскравість кожної точки стає її непрозорістю,
    # тож чорне тло зникає, а лінії можна перефарбувати під будь-яку тему.
    gray = Image.open(path).convert("L")
    box = gray.point(lambda value: 255 if value > 60 else 0).getbbox()
    if box:
        gray = gray.crop(box)
    side = int(max(gray.size) * 1.08)
    square = Image.new("L", (side, side), 0)
    square.paste(gray, ((side - gray.width) // 2, (side - gray.height) // 2))
    return square


def greeting_text(name):
    hour = datetime.now().hour
    if 5 <= hour < 12:
        text = "Доброго ранку"
    elif 12 <= hour < 18:
        text = "Добрий день"
    elif 18 <= hour < 23:
        text = "Добрий вечір"
    else:
        text = "Доброї ночі"
    return f"{text}, {name}" if name else text


def copy_image_to_clipboard(path):
    """Кладе картинку в буфер обміну Windows, щоб її можна було вставити в чат чи редактор."""
    import io

    from ctypes import wintypes

    buffer = io.BytesIO()
    Image.open(path).convert("RGB").save(buffer, "BMP")
    data = buffer.getvalue()[14:]  # без заголовка файлу залишається формат DIB

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]

    handle = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
    pointer = kernel32.GlobalLock(handle)
    ctypes.memmove(pointer, data, len(data))
    kernel32.GlobalUnlock(handle)

    if not user32.OpenClipboard(None):
        raise RuntimeError("clipboard busy")
    try:
        user32.EmptyClipboard()
        user32.SetClipboardData(8, handle)  # CF_DIB
    finally:
        user32.CloseClipboard()


def free_gpu_memory():
    # PyTorch тримає звільнену відеопам'ять "про запас" для себе.
    # Віддаємо її системі, щоб мовна модель Gaia могла завантажитися на відеокарту.
    torch = sys.modules.get("torch")
    if torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()


def open_folder(path):
    folder = Path(path)
    folder.mkdir(parents=True, exist_ok=True)
    os.startfile(folder.resolve())


class LinumApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings = SettingsStore(SETTINGS_FILE)
        self.chats = ChatStore(CHATS_FILE)
        ctk.set_appearance_mode(self.settings.get("theme"))

        self.pipe = None
        self.loaded_model = None
        self.selected_model = None
        # busy: модель вантажиться або створює картинку, тому кнопку "створити" вимкнено.
        # generating: саме створюється картинка, тоді не можна і переходити між екранами.
        self.busy = False
        self.generating = False
        self.view = None
        self.current_chat_id = None
        self.chat_buttons = []
        self.image_refs = []
        self.thumb_cache = {}
        self.card_cache = {}
        self.feed_body = None
        self.fonts = {}
        self.pending = None
        # Мозок (мовна модель в Ollama). Якщо його немає, Linum просто малює за запитом, як раніше.
        self.brain_ready = False
        self.thinking = None
        # Кадри анімації "думаю" (малюються у фоні) і готові картинки для різних розмірів
        self.spinner_frames = None
        self.spinner_images = {}
        self.account_menu = None
        self.viewer = None
        self.settings_page = None
        self.content_width = CONTENT_MAX_WIDTH
        self.sidebar_visible = bool(self.settings.get("sidebar"))

        self.title(APP_NAME)
        self.geometry("1440x900")
        self.minsize(960, 660)
        self.configure(fg_color=theme.BG)

        self.icon_mask = load_icon_mask(ICON_PATH)
        self._set_window_icon()
        self.icons = {name: make_icon(name, 18, theme.TEXT) for name in (
            "plus", "search", "gallery", "folder", "sidebar", "settings", "trash",
        )}
        self.small_icons = {name: make_icon(name, 15, theme.MUTED) for name in (
            "refresh", "copy", "open", "folder", "palette", "frame", "model", "bulb",
        )}
        self.menu_icons = {name: make_icon(name, 16, theme.TEXT) for name in (
            "settings", "palette", "folder", "model",
        )}
        self.attach_icon = make_icon("plus", 16, theme.TEXT)
        self.close_icon = make_icon("close", 10, theme.TEXT)
        # Фото, яке користувач додав до наступного повідомлення (шлях у data/uploads)
        self.attachment = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()
        self._apply_sidebar()

        # Порожні чати з минулих запусків не потрібні
        for chat in list(self.chats.chats):
            if not chat["messages"]:
                self.chats.delete_chat(chat["id"])
        self.new_chat()

        first_model = self._initial_model()
        if first_model is None:
            self.model_menu.set(DEFAULT_MODEL)
            self.send_button.configure(state="disabled")
            self.set_status("Не знайдено жодного файлу моделі. Покладіть його в models/checkpoints")
        else:
            self.select_model(first_model)
        self._check_brain()
        self._prepare_spinner()

        self.bind("<Control-n>", lambda event: self.new_chat())
        self.bind("<Escape>", self._on_escape)
        self.bind("<Control-c>", self._on_copy_key)
        # Ctrl+C, Ctrl+V та інші працюють і на українській розкладці
        install_clipboard_keys(self)
        # Клік будь-де закриває меню акаунта, якщо клікнули не по ньому
        self.bind_all("<Button-1>", self._on_global_click, add="+")
        self.after(10, lambda: self.state("zoomed"))
        self.prompt_entry.focus_set()

    # ---------- Допоміжне ----------

    def font(self, size, weight="normal", family=None):
        key = (size, weight, family)
        if key not in self.fonts:
            self.fonts[key] = ctk.CTkFont(family=family or theme.FONT_FAMILY, size=size, weight=weight)
        return self.fonts[key]

    def icon_button(self, parent, icon, command, size=32):
        return ctk.CTkButton(
            parent,
            text="",
            image=icon,
            width=size,
            height=size,
            corner_radius=8,
            fg_color="transparent",
            hover_color=theme.SURFACE_HOVER,
            command=command,
        )

    def small_button(self, parent, text, icon, command):
        # Маленька кнопка з іконкою під картинкою
        return ctk.CTkButton(
            parent,
            text=text,
            image=icon,
            compound="left",
            width=0,
            height=28,
            corner_radius=8,
            font=self.font(12),
            fg_color="transparent",
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT,
            command=command,
        )

    def menu_style(self):
        return {
            "width": 0,
            "height": 30,
            "corner_radius": 8,
            "font": self.font(13),
            "dropdown_font": self.font(13),
            "fg_color": theme.SURFACE,
            "button_color": theme.SURFACE,
            "button_hover_color": theme.SURFACE_HOVER,
            "text_color": theme.TEXT,
            "text_color_disabled": theme.MUTED,
            "dropdown_fg_color": theme.SURFACE,
            "dropdown_hover_color": theme.SURFACE_HOVER,
            "dropdown_text_color": theme.TEXT,
            "dynamic_resizing": True,
        }

    def segmented_style(self):
        return {
            "font": self.font(13),
            "height": 34,
            "corner_radius": 10,
            "fg_color": theme.SURFACE,
            "selected_color": theme.SELECTED,
            "selected_hover_color": theme.SELECTED,
            "unselected_color": theme.SURFACE,
            "unselected_hover_color": theme.SURFACE_HOVER,
            "text_color": theme.TEXT,
            "text_color_disabled": theme.MUTED,
        }

    def _set_window_icon(self):
        # Своя іконка в панелі задач Windows, а не значок Python
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Linum.App")
        except (AttributeError, OSError):
            pass
        ico_path = Path(ICO_PATH)
        if not ico_path.exists():
            ico_path.parent.mkdir(parents=True, exist_ok=True)
            self._build_ico(ico_path)
        self.iconbitmap(str(ico_path.resolve()))

    def tinted_logo(self, color, size):
        # Оригінальна іконка Linum, перефарбована в потрібний колір, на прозорому тлі
        # Лінії в оригіналі тонкі, при зменшенні вони блякнуть. Тому чим менша іконка,
        # тим сильніше потовщуємо лінії перед зменшенням.
        from PIL import ImageFilter

        shrink = self.icon_mask.width / size
        thicken = int(shrink * 0.8) // 2 * 2 + 1  # непарне число, як потрібно фільтру
        mask = self.icon_mask
        if thicken >= 3:
            mask = mask.filter(ImageFilter.MaxFilter(thicken))
        mask = mask.resize((size, size), Image.LANCZOS).point(lambda value: min(255, int(value * 1.4)))
        logo = Image.new("RGBA", (size, size), color)
        logo.putalpha(mask)
        return logo

    def _build_ico(self, ico_path):
        # Значок програми: оригінальна іконка без змін, лише зменшена
        icon = Image.merge("RGB", (self.icon_mask, self.icon_mask, self.icon_mask))
        icon.save(ico_path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    def thumbnail(self, path, size):
        # Зменшені копії картинок запам'ятовуємо, щоб не читати файл щоразу
        key = (str(path), size)
        if key not in self.thumb_cache:
            image = Image.open(path).convert("RGB")
            side = min(image.size)
            left = (image.width - side) // 2
            top = (image.height - side) // 2
            square = image.crop((left, top, left + side, top + side)).resize((size * 2, size * 2), Image.LANCZOS)
            self.thumb_cache[key] = rounded(square, 24)
        picture = self.thumb_cache[key]
        return ctk.CTkImage(light_image=picture, dark_image=picture, size=(size, size))

    def card_image(self, path, longest=IMAGE_SIZE):
        # Картинка для картки в чаті. Зменшуємо і заокруглюємо один раз,
        # тож повторне відкриття чату не читає великі файли знову.
        key = (str(path), longest)
        if key not in self.card_cache:
            with Image.open(path) as source:
                size = fit(source.width, source.height, longest)
                scaling = ctk.ScalingTracker.get_widget_scaling(self)
                sharp = source.convert("RGB").resize(
                    (int(size[0] * scaling * 2), int(size[1] * scaling * 2)), Image.LANCZOS
                )
            picture = rounded(sharp, int(28 * scaling))
            self.card_cache[key] = ctk.CTkImage(light_image=picture, dark_image=picture, size=size)
        return self.card_cache[key]

    def set_status(self, text=None):
        self.status_label.configure(text=text or LANGUAGE_HINT)

    def _scroll_to_bottom(self, instant=False):
        canvas = self.feed._parent_canvas

        def scroll():
            # Розмір вмісту оновлюємо одразу, а не чекаємо, поки стрічка сама це помітить
            self.feed.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.yview_moveto(1.0)

        if instant:
            scroll()
        self.after(60, scroll)

    # ---------- Бокова панель ----------

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=264, corner_radius=0, fg_color=theme.SIDEBAR)
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(4, weight=1)

        top = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        self.icon_button(top, self.icons["sidebar"], self.toggle_sidebar).pack(side="left")

        nav = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav.grid(row=1, column=0, sticky="ew", padx=8)
        self.nav_buttons = {}
        for key, text, icon, command in (
            ("new", "Новий чат", "plus", self.new_chat),
            ("search", "Пошук", "search", self.toggle_search),
            ("gallery", "Галерея", "gallery", self.show_gallery),
            ("folder", "Папка із зображеннями", "folder", lambda: open_folder(OUTPUTS_DIR)),
        ):
            button = ctk.CTkButton(
                nav,
                text=text,
                image=self.icons[icon],
                compound="left",
                anchor="w",
                height=36,
                corner_radius=8,
                font=self.font(14),
                fg_color="transparent",
                hover_color=theme.SURFACE_HOVER,
                text_color=theme.TEXT,
                command=command,
            )
            button.pack(fill="x", pady=1)
            self.nav_buttons[key] = button

        self.search_entry = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="Шукати в чатах",
            height=34,
            corner_radius=8,
            border_width=1,
            border_color=theme.BORDER,
            fg_color=theme.SURFACE,
            text_color=theme.TEXT,
            placeholder_text_color=theme.MUTED,
            font=self.font(13),
        )
        self.search_entry.bind("<KeyRelease>", lambda event: self.render_chat_list())
        self.search_entry.bind("<Escape>", lambda event: self.toggle_search())

        ctk.CTkLabel(
            self.sidebar, text="Нещодавні", font=self.font(12), text_color=theme.MUTED, anchor="w"
        ).grid(row=3, column=0, sticky="ew", padx=18, pady=(18, 4))

        self.chat_list = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color="transparent",
            scrollbar_button_color=theme.SIDEBAR,
            scrollbar_button_hover_color=theme.BORDER,
        )
        self.chat_list.grid(row=4, column=0, sticky="nsew", padx=(4, 2))

        # Профіль унизу, як у Claude: кружечок з першою літерою імені.
        # Натискання відкриває маленьке меню акаунта.
        profile = ctk.CTkFrame(self.sidebar, fg_color="transparent", corner_radius=10, cursor="hand2")
        profile.grid(row=5, column=0, sticky="ew", padx=8, pady=8)
        profile.grid_columnconfigure(1, weight=1)
        self.profile = profile
        self.avatar = ctk.CTkLabel(
            profile,
            text="",
            width=30,
            height=30,
            corner_radius=15,
            fg_color=theme.ACCENT,
            text_color=theme.ACCENT_TEXT,
            font=self.font(13, "bold"),
        )
        self.avatar.grid(row=0, column=0, padx=(6, 0), pady=6)
        self.profile_name = ctk.CTkLabel(profile, text="", font=self.font(14), text_color=theme.TEXT, anchor="w")
        self.profile_name.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        chevron = ctk.CTkLabel(profile, text="⌃", font=self.font(13), text_color=theme.MUTED)
        chevron.grid(row=0, column=2, padx=(0, 10))
        for widget in (profile, self.avatar, self.profile_name, chevron):
            widget.bind("<Button-1>", self.toggle_account_menu)
            widget.bind("<Enter>", lambda event: profile.configure(fg_color=theme.SURFACE_HOVER))
            widget.bind("<Leave>", lambda event: profile.configure(fg_color="transparent"))
        self._update_profile()

    def _update_profile(self):
        name = self.settings.get("name").strip()
        self.avatar.configure(text=(name[:1] or "L").upper())
        self.profile_name.configure(text=name or "Профіль")

    def toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible
        self.settings.set("sidebar", self.sidebar_visible)
        self._apply_sidebar()

    def _apply_sidebar(self):
        if self.sidebar_visible:
            self.sidebar.grid(row=0, column=0, sticky="nsw")
            self.header_toggle.grid_remove()
        else:
            self.sidebar.grid_remove()
            self.header_toggle.grid()

    def toggle_search(self):
        if self.search_entry.winfo_ismapped():
            self.search_entry.delete(0, "end")
            self.search_entry.grid_remove()
            self.render_chat_list()
        else:
            self.search_entry.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 0))
            self.search_entry.focus_set()

    # ---------- Головна частина ----------

    def _build_main(self):
        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color=theme.BG)
        self.main.grid(row=0, column=1, sticky="nsew")
        # Колонки 0 і 2 це порожні поля з боків, а 1 це центральна колонка з контентом
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_columnconfigure(2, weight=1)
        self.main.bind("<Configure>", self._on_main_resize)

        # Верх: лише кнопка показу панелі (коли її сховано), назва чату і кошик
        header = ctk.CTkFrame(self.main, fg_color="transparent", height=44)
        header.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=(8, 0))
        header.grid_columnconfigure(1, weight=1)
        self.header_toggle = self.icon_button(header, self.icons["sidebar"], self.toggle_sidebar)
        self.header_toggle.grid(row=0, column=0)
        self.header_title = ctk.CTkLabel(header, text="", font=self.font(13), text_color=theme.MUTED, height=32)
        self.header_title.grid(row=0, column=1)
        self.delete_button = self.icon_button(header, self.icons["trash"], self.delete_chat)
        self.delete_button.grid(row=0, column=2)

        # Головний екран: привітання над полем і останні зображення під ним
        self.greeting = ctk.CTkFrame(self.main, fg_color="transparent")
        greeting_row = ctk.CTkFrame(self.greeting, fg_color="transparent")
        greeting_row.pack(pady=(0, 24))
        # Іконка Linum ліворуч від привітання, у кольорі тексту поточної теми
        logo_size = 64
        self.logo_image = ctk.CTkImage(
            light_image=self.tinted_logo(theme.TEXT[0], logo_size * 2),
            dark_image=self.tinted_logo(theme.TEXT[1], logo_size * 2),
            size=(logo_size, logo_size),
        )
        ctk.CTkLabel(greeting_row, image=self.logo_image, text="").pack(side="left", padx=(0, 14))
        self.greeting_label = ctk.CTkLabel(
            greeting_row, text="", font=self.font(34, family="Georgia"), text_color=theme.TEXT
        )
        self.greeting_label.pack(side="left")

        self.recents = ctk.CTkFrame(self.main, fg_color="transparent")

        # Стрічка повідомлень і галерея
        self.feed = ctk.CTkScrollableFrame(
            self.main,
            width=CONTENT_MAX_WIDTH,
            fg_color="transparent",
            scrollbar_button_color=theme.BG,
            scrollbar_button_hover_color=theme.BORDER,
        )
        self.gallery = ctk.CTkScrollableFrame(
            self.main,
            width=CONTENT_MAX_WIDTH,
            fg_color="transparent",
            scrollbar_button_color=theme.BG,
            scrollbar_button_hover_color=theme.BORDER,
        )

        self._build_composer()

    def _build_composer(self):
        self.composer_block = ctk.CTkFrame(self.main, fg_color="transparent")
        self.composer_block.grid_columnconfigure(0, weight=1)

        composer = ctk.CTkFrame(
            self.composer_block, fg_color=theme.SURFACE, corner_radius=20, border_width=1, border_color=theme.BORDER
        )
        composer.grid(row=0, column=0, sticky="ew")
        composer.grid_columnconfigure(0, weight=1)

        self.prompt_entry = PromptBox(
            composer,
            placeholder="Напишіть повідомлення або попросіть намалювати",
            font=self.font(15),
            width=CONTENT_MAX_WIDTH - 40,
            on_submit=self.on_generate,
        )
        self.prompt_entry.grid(row=1, column=0, sticky="ew", padx=(12, 12), pady=(12, 0))
        # Ctrl+V з картинкою в буфері обміну додає її як фото
        self.prompt_entry.bind("<<Paste>>", self._paste_image, add="+")

        # Мініатюра доданого фото над текстом (з'являється, лише коли фото є)
        self.attachment_bar = ctk.CTkFrame(composer, fg_color="transparent")
        self.attachment_bar.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 0))
        self.attachment_bar.grid_remove()

        # Панель інструментів усередині поля: стиль і формат зліва, модель і кнопка справа
        tools = ctk.CTkFrame(composer, fg_color="transparent")
        tools.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 10))

        # Клік по будь-якому порожньому місцю рамки (не по кнопках) ставить курсор у поле, як у Claude
        composer.bind("<Button-1>", self.prompt_entry.focus_end)
        tools.bind("<Button-1>", self.prompt_entry.focus_end)

        self.attach_button = ctk.CTkButton(
            tools,
            text="",
            image=self.attach_icon,
            width=30,
            height=30,
            corner_radius=15,
            fg_color="transparent",
            hover_color=theme.SURFACE_HOVER,
            command=self.pick_attachment,
        )
        self.attach_button.pack(side="left", padx=(0, 4))

        ctk.CTkLabel(tools, image=self.small_icons["palette"], text="").pack(side="left", padx=(6, 0))
        self.style_menu = ctk.CTkOptionMenu(
            tools, values=list(STYLES.keys()), command=lambda value: self.settings.set("style", value), **self.menu_style()
        )
        self.style_menu.set(self.settings.get("style") if self.settings.get("style") in STYLES else "Без стилю")
        self.style_menu.pack(side="left")

        ctk.CTkLabel(tools, image=self.small_icons["frame"], text="").pack(side="left", padx=(10, 0))
        self.size_menu = ctk.CTkOptionMenu(
            tools, values=list(SIZES.keys()), command=lambda value: self.settings.set("size", value), **self.menu_style()
        )
        self.size_menu.set(self.settings.get("size") if self.settings.get("size") in SIZES else "Квадрат 1:1")
        self.size_menu.pack(side="left")

        # Рівень міркувань Gaia: можна міняти перед кожним повідомленням
        ctk.CTkLabel(tools, image=self.small_icons["bulb"], text="").pack(side="left", padx=(10, 0))
        self.reasoning_menu = ctk.CTkOptionMenu(
            tools, values=list(REASONING.keys()), command=self.set_reasoning, **self.menu_style()
        )
        self.reasoning_menu.set(self.settings.get("reasoning") if self.settings.get("reasoning") in REASONING else DEFAULT_REASONING)
        self.reasoning_menu.pack(side="left")

        self.send_button = ctk.CTkButton(
            tools,
            text="↑",
            width=36,
            height=36,
            corner_radius=18,
            font=self.font(18, "bold"),
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            text_color=theme.ACCENT_TEXT,
            text_color_disabled=theme.MUTED,
            command=self.on_generate,
        )
        self.send_button.pack(side="right")
        self.model_tier_label = ctk.CTkLabel(tools, text="", font=self.font(12), text_color=theme.MUTED)
        self.model_tier_label.pack(side="right", padx=(0, 12))
        self.model_menu = ctk.CTkOptionMenu(
            tools, values=list(MODELS.keys()), command=self.select_model, **self.menu_style()
        )
        self.model_menu.pack(side="right")
        ctk.CTkLabel(tools, image=self.small_icons["model"], text="").pack(side="right")

        self.status_label = ctk.CTkLabel(
            self.composer_block, text=LANGUAGE_HINT, font=self.font(12), text_color=theme.MUTED, anchor="w"
        )
        self.status_label.grid(row=1, column=0, sticky="w", padx=(14, 0), pady=(6, 0))

    # ---------- Фото від користувача ----------

    def pick_attachment(self):
        # Діалог вибору фото з комп'ютера
        from tkinter import filedialog

        path = filedialog.askopenfilename(
            parent=self,
            title="Оберіть фото",
            filetypes=[("Зображення", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"), ("Усі файли", "*.*")],
        )
        if path:
            self.attach_image(path)

    def _paste_image(self, event=None):
        # Якщо в буфері обміну картинка (скріншот, скопійоване фото) або файл-картинка,
        # додаємо її як фото. Інакше нічого не робимо, і вставиться звичайний текст.
        from PIL import ImageGrab

        try:
            content = ImageGrab.grabclipboard()
        except Exception:
            return None
        if isinstance(content, Image.Image):
            self.attach_image(content)
            return "break"
        if isinstance(content, list):
            for item in content:
                if Path(item).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
                    self.attach_image(item)
                    return "break"
        return None

    def attach_image(self, source):
        # source: шлях до файлу або вже відкрита картинка PIL.
        # Робимо копію в data/uploads, щоб фото в чаті не зникло, якщо оригінал перемістять.
        try:
            image = source if isinstance(source, Image.Image) else Image.open(source)
            image.load()
        except Exception as error:
            self.set_status(f"Не вдалося відкрити фото: {shorten(str(error), 100)}")
            return
        if image.mode in ("RGBA", "LA", "P"):
            # Прозорі місця робимо білими, а не чорними
            image = image.convert("RGBA")
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=image.getchannel("A"))
            image = background
        else:
            image = image.convert("RGB")
        # Дуже великі фото зменшуємо: моделі все одно працюють з ~768 пікселів
        image.thumbnail((1536, 1536), Image.LANCZOS)

        folder = Path(UPLOADS_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".png")
        image.save(path)
        self.attachment = str(path)
        self._render_attachment()
        self.prompt_entry.focus_end()

    def clear_attachment(self):
        self.attachment = None
        self._render_attachment()

    def _render_attachment(self):
        for widget in self.attachment_bar.winfo_children():
            widget.destroy()
        if self.attachment is None:
            self.attachment_bar.grid_remove()
            return
        holder = ctk.CTkFrame(self.attachment_bar, fg_color="transparent", width=64, height=64)
        holder.pack(side="left")
        holder.pack_propagate(False)
        picture = ctk.CTkLabel(holder, image=self.thumbnail(self.attachment, 60), text="", cursor="hand2")
        picture.place(x=0, y=4)
        picture.bind("<Button-1>", lambda event: self.open_viewer(self.attachment_message(self.attachment, "")))
        ctk.CTkButton(
            holder,
            text="",
            image=self.close_icon,
            width=20,
            height=20,
            corner_radius=10,
            fg_color=theme.SURFACE_HOVER,
            hover_color=theme.BORDER,
            border_width=1,
            border_color=theme.BORDER,
            command=self.clear_attachment,
        ).place(x=44, y=0)
        self.attachment_bar.grid()

    @staticmethod
    def attachment_message(path, text):
        # Дані у форматі повідомлення з картинкою, щоб показати фото користувача в перегляді
        return {"image": path, "prompt": text or "Ваше фото", "model": "Ваше фото"}

    def _on_main_resize(self, event):
        # Центральна колонка не ширша за CONTENT_MAX_WIDTH, як у сучасних чатів
        scaling = ctk.ScalingTracker.get_widget_scaling(self)
        available = int(self.main.winfo_width() / scaling) - 64
        width = max(460, min(CONTENT_MAX_WIDTH, available))
        if width != self.content_width:
            self.content_width = width
            self.feed.configure(width=width)
            self.gallery.configure(width=width)
            self.prompt_entry.configure(width=width - 40)

    def _set_view(self, view):
        # Перемикає головну частину між екранами: home (привітання), chat і gallery
        self.view = view
        self.close_account_menu()
        self.close_viewer()
        for widget in (self.greeting, self.recents, self.feed, self.gallery, self.composer_block):
            widget.grid_remove()
        if self.settings_page is not None:
            self.settings_page.destroy()
            self.settings_page = None

        if view == "home":
            self.main.grid_rowconfigure(1, weight=1)
            self.main.grid_rowconfigure(3, weight=1)
            self.greeting.grid(row=1, column=1, sticky="s")
            self.composer_block.grid(row=2, column=1, sticky="ew")
            self.recents.grid(row=3, column=1, sticky="new", pady=(34, 0))
        elif view == "chat":
            self.main.grid_rowconfigure(1, weight=1)
            self.main.grid_rowconfigure(3, weight=0)
            self.feed.grid(row=1, column=1, sticky="ns", pady=(4, 0))
            self.composer_block.grid(row=2, column=1, sticky="ew", pady=(10, 0))
            self.main.grid_rowconfigure(3, minsize=18)
        elif view in ("gallery", "settings"):
            self.main.grid_rowconfigure(1, weight=1)
            self.main.grid_rowconfigure(3, weight=0)
            if view == "gallery":
                self.gallery.grid(row=1, column=1, sticky="ns", pady=(4, 0))

    # ---------- Чати ----------

    def render_chat_list(self):
        for widget in self.chat_list.winfo_children():
            widget.destroy()
        self.chat_buttons = []
        query = self.search_entry.get().strip().lower() if self.search_entry.winfo_ismapped() else ""

        for chat in self.chats.sorted_chats():
            if not chat["messages"]:
                continue
            if query and query not in chat["title"].lower() and not any(
                query in (message.get("prompt") or message.get("text") or "").lower()
                or query in message.get("prompt_en", "").lower()
                for message in chat["messages"]
            ):
                continue
            selected = chat["id"] == self.current_chat_id and self.view == "chat"
            button = ctk.CTkButton(
                self.chat_list,
                text=shorten(chat["title"], 30),
                anchor="w",
                height=34,
                corner_radius=8,
                font=self.font(13),
                fg_color=theme.SELECTED if selected else "transparent",
                hover_color=theme.SURFACE_HOVER,
                text_color=theme.TEXT,
                command=lambda chat_id=chat["id"]: self.open_chat(chat_id),
            )
            button.pack(fill="x", pady=1)
            button.bind("<Button-3>", lambda event, chat_id=chat["id"]: self._chat_menu(event, chat_id))
            button.chat_id = chat["id"]
            self.chat_buttons.append(button)

        if not self.chat_buttons:
            ctk.CTkLabel(
                self.chat_list,
                text="Нічого не знайдено" if query else "Тут з'являться ваші чати",
                font=self.font(12),
                text_color=theme.MUTED,
            ).pack(anchor="w", padx=10, pady=6)

    def highlight_chat(self):
        # Лише перемикає підсвічування в списку чатів, без повної перебудови списку
        for button in self.chat_buttons:
            selected = button.chat_id == self.current_chat_id and self.view == "chat"
            color = theme.SELECTED if selected else "transparent"
            if button.cget("fg_color") != color:
                button.configure(fg_color=color)

    def _chat_menu(self, event, chat_id):
        # Меню правої кнопки миші на чаті
        if self.generating:
            return
        menu = tk.Menu(
            self, tearoff=0, bd=0, relief="flat", font=(theme.FONT_FAMILY, 10),
            bg=themed(theme.SURFACE), fg=themed(theme.TEXT),
            activebackground=themed(theme.SURFACE_HOVER), activeforeground=themed(theme.TEXT),
        )
        menu.add_command(label="Відкрити", command=lambda: self.open_chat(chat_id))
        menu.add_separator()
        menu.add_command(label="Видалити чат", command=lambda: self.delete_chat(chat_id))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def open_chat(self, chat_id):
        if self.generating:
            return
        previous = self.chats.get(self.current_chat_id)
        # Порожній чат, з якого пішли, нікому не потрібен, тому прибираємо його
        if previous and previous["id"] != chat_id and not previous["messages"]:
            self.chats.delete_chat(previous["id"])
        self.current_chat_id = chat_id
        known = any(button.chat_id == chat_id for button in self.chat_buttons)
        self.render_chat()
        if known and previous and previous["messages"]:
            self.highlight_chat()
        else:
            self.render_chat_list()

    def new_chat(self):
        if self.generating:
            return
        current = self.chats.get(self.current_chat_id)
        if current and not current["messages"]:
            self.render_chat()
            self.render_chat_list()
        else:
            chat = self.chats.create_chat()
            self.open_chat(chat["id"])
        self.prompt_entry.focus_set()

    def delete_chat(self, chat_id=None):
        if self.generating:
            return
        chat = self.chats.get(chat_id or self.current_chat_id)
        if chat is None or not chat["messages"]:
            return
        confirmed = messagebox.askyesno(
            "Видалити чат",
            f"Видалити чат «{chat['title']}»?\nЗображення залишаться в папці outputs.",
            parent=self,
        )
        if not confirmed:
            return
        self.chats.delete_chat(chat["id"])
        if chat["id"] == self.current_chat_id:
            self.current_chat_id = None
            self.new_chat()
        else:
            self.render_chat_list()

    def render_chat(self, fade="all"):
        # fade: "all" плавно проявляє видимі повідомлення (при відкритті чату),
        #       "last" лише останнє (коли додалася нова картинка), None без анімації
        self.image_refs = []
        self.pending = None

        chat = self.chats.get(self.current_chat_id)
        if chat is None or not chat["messages"]:
            self._render_home()
            return

        # Новий вміст збираємо в окремій рамці, поки вона ще не на екрані
        old = self.feed_body
        self.feed_body = self._new_feed_body()
        rows = []
        for message in chat["messages"]:
            kind = message.get("kind")
            if kind == "user":
                rows.append(self._add_prompt_bubble({"prompt": message["text"], "attachment": message.get("attachment")}))
            elif kind == "assistant":
                rows.append(self._add_assistant_text(message["text"]))
            elif kind == "image":
                rows.append(self._add_image_card(message))
            else:
                # Старий формат: запит і картинка разом
                rows.append(self._add_prompt_bubble(message))
                rows.append(self._add_image_card(message))
        body = self.feed_body
        self.feed_body = old

        self._set_view("chat")
        self.header_title.configure(text=shorten(chat["title"], 70))
        self.delete_button.grid()
        # Проявляємо лише останні повідомлення: саме їх видно після прокрутки донизу
        fade_rows = {"all": rows[-10:], "last": rows[-1:]}.get(fade, [])
        self._show_feed_body(body, fade_rows)

    # ---------- Головний екран і галерея ----------

    def all_images(self):
        # Усі створені зображення з усіх чатів, від нових до старих
        items = []
        for chat in self.chats.chats:
            for message in chat["messages"]:
                if message.get("image") and Path(message["image"]).exists():
                    items.append((chat["id"], message))
        items.sort(key=lambda item: item[1]["created"], reverse=True)
        return items

    def _render_home(self):
        self._set_view("home")
        self.header_title.configure(text="")
        self.delete_button.grid_remove()
        self.greeting_label.configure(text=greeting_text(self.settings.get("name").strip()))

        for widget in self.recents.winfo_children():
            widget.destroy()
        items = self.all_images()[:4]
        if not items:
            return

        head = ctk.CTkFrame(self.recents, fg_color="transparent")
        head.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(head, text="Останні зображення", font=self.font(13), text_color=theme.MUTED).pack(side="left", padx=(4, 0))
        ctk.CTkButton(
            head,
            text="Усі",
            width=0,
            height=26,
            corner_radius=8,
            font=self.font(13),
            fg_color="transparent",
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.MUTED,
            command=self.show_gallery,
        ).pack(side="right")

        row = ctk.CTkFrame(self.recents, fg_color="transparent")
        row.pack(fill="x")
        for chat_id, message in items:
            card = self._thumb_card(row, message, lambda cid=chat_id: self.open_chat(cid))
            card.pack(side="left", padx=(0, 12))

    def _thumb_card(self, parent, message, on_click):
        card = ctk.CTkFrame(parent, fg_color=theme.SURFACE, corner_radius=14, border_width=1, border_color=theme.BORDER)
        picture = ctk.CTkLabel(card, image=self.thumbnail(message["image"], THUMB_SIZE - 16), text="")
        picture.pack(padx=8, pady=(8, 6))
        caption = ctk.CTkFrame(card, fg_color="transparent")
        caption.pack(fill="x", padx=10, pady=(0, 8))
        title = ctk.CTkLabel(caption, text=shorten(message["prompt"], 18), font=self.font(12), text_color=theme.TEXT)
        title.pack(side="left")
        date = ctk.CTkLabel(
            caption,
            text=datetime.fromisoformat(message["created"]).strftime("%d.%m"),
            font=self.font(11),
            text_color=theme.MUTED,
        )
        date.pack(side="right")
        for widget in (card, picture, title, date):
            widget.bind("<Button-1>", lambda event: on_click())
            widget.configure(cursor="hand2")
        return card

    def show_gallery(self):
        if self.generating:
            return
        previous = self.chats.get(self.current_chat_id)
        if previous and not previous["messages"]:
            self.chats.delete_chat(previous["id"])
            self.current_chat_id = None
        self._set_view("gallery")
        items = self.all_images()
        self.header_title.configure(text=f"Галерея  ·  {len(items)}")
        self.delete_button.grid_remove()
        self.render_chat_list()

        for widget in self.gallery.winfo_children():
            widget.destroy()
        if not items:
            ctk.CTkLabel(
                self.gallery, text="Тут з'являться створені зображення", font=self.font(14), text_color=theme.MUTED
            ).pack(pady=120)
            return

        columns = 4
        grid = ctk.CTkFrame(self.gallery, fg_color="transparent")
        grid.pack(pady=(8, 20))
        for index, (chat_id, message) in enumerate(items):
            card = self._thumb_card(grid, message, lambda m=message, cid=chat_id: self.open_viewer(m, cid))
            card.grid(row=index // columns, column=index % columns, padx=6, pady=6)

    # ---------- Повідомлення ----------

    # Усі повідомлення лежать у self.feed_body усередині прокручуваної стрічки.
    # При відкритті чату новий вміст збирається невидимим і з'являється одразу цілим,
    # тому немає миготіння, коли віджети створюються по одному.

    def _new_feed_body(self):
        return ctk.CTkFrame(self.feed, fg_color="transparent")

    def _reset_feed(self):
        if self.feed_body is not None:
            self.feed_body.destroy()
        self.feed_body = self._new_feed_body()
        self.feed_body.pack(fill="x")

    def _show_feed_body(self, body, fade_rows):
        # Підміняє старий вміст новим і плавно проявляє останні повідомлення
        old = self.feed_body
        self.feed_body = body
        start = fade_in(fade_rows) if fade_rows else None
        if start:
            start()  # перший кадр: нові повідомлення ще кольору тла
        if old is not None and old is not body:
            # Старий вміст ховаємо одразу, а знищуємо трохи пізніше, щоб не гальмувати показ нового
            old.pack_forget()
            self.after(30, old.destroy)
        if not body.winfo_ismapped():
            body.pack(fill="x")
        self._scroll_to_bottom(instant=True)

    def _add_prompt_bubble(self, message):
        row = ctk.CTkFrame(self.feed_body, fg_color="transparent")
        row.pack(fill="x", pady=(22, 8))
        attachment = message.get("attachment")
        if attachment and Path(attachment).exists():
            # Фото користувача праворуч над бульбашкою, як у месенджерах
            image = self.card_image(attachment, longest=240)
            self.image_refs.append(image)
            picture = ctk.CTkLabel(row, image=image, text="", cursor="hand2")
            picture.pack(side="top", anchor="e", padx=(80, 8), pady=(0, 6 if message["prompt"] else 0))
            picture.bind(
                "<Button-1>",
                lambda event, p=attachment, t=message["prompt"]: self.open_viewer(self.attachment_message(p, t)),
            )
        if not message["prompt"]:
            return row
        bubble = ctk.CTkFrame(row, fg_color=theme.SURFACE, corner_radius=16)
        bubble.pack(side="right", padx=(80, 8))
        has_translation = message.get("prompt_en") and message.get("language", "en") != "en"
        SelectableText(
            bubble, message["prompt"], self.font(14), max_width=500, bg=theme.SURFACE,
        ).pack(anchor="w", padx=16, pady=(9, 0 if has_translation else 9))
        if has_translation:
            SelectableText(
                bubble,
                f"Переклад {LANGUAGE_NAMES.get(message['language'], '')}: {message['prompt_en']}",
                self.font(12),
                max_width=500,
                text_color=theme.MUTED,
                bg=theme.SURFACE,
            ).pack(anchor="w", padx=16, pady=(0, 9))
        return row

    def _card_row(self):
        row = ctk.CTkFrame(self.feed_body, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        card = ctk.CTkFrame(row, fg_color=theme.SURFACE, corner_radius=18, border_width=1, border_color=theme.BORDER)
        card.pack(side="left", padx=(2, 0))
        return row, card

    def _assistant_row(self):
        # Рядок відповіді Linum: просто текст ліворуч, без бульбашки
        row = ctk.CTkFrame(self.feed_body, fg_color="transparent")
        row.pack(fill="x", pady=(14, 6), padx=(6, 0))
        return row

    # ---------- Анімація "думаю" ----------

    def _prepare_spinner(self):
        # Кадри анімації малюються у фоні при запуску, це займає менше секунди
        def work():
            from src.frontend.spinner import make_frames

            frames = {
                "light": make_frames(SPINNER_FRAME_SIZE, SPINNER_COLORS["light"]),
                "dark": make_frames(SPINNER_FRAME_SIZE, SPINNER_COLORS["dark"]),
            }
            self.after(0, lambda: setattr(self, "spinner_frames", frames))

        threading.Thread(target=work, daemon=True).start()

    def spinner_images_for(self, size):
        if self.spinner_frames is None:
            return None
        if size not in self.spinner_images:
            self.spinner_images[size] = [
                ctk.CTkImage(light_image=light, dark_image=dark, size=(size, size))
                for light, dark in zip(self.spinner_frames["light"], self.spinner_frames["dark"])
            ]
        return self.spinner_images[size]

    def spinner_label(self, parent, size):
        # Мітка з анімацією. Якщо кадри ще малюються, місце вже зайняте,
        # а анімація з'явиться, щойно вони будуть готові.
        label = ctk.CTkLabel(parent, text="", width=size, height=size)

        def next_frame(index):
            if not label.winfo_exists():
                return
            images = self.spinner_images_for(size)
            if images is not None:
                label.configure(image=images[index % len(images)])
                index += 1
            label.after(45, next_frame, index)

        next_frame(0)
        return label

    def _add_assistant_text(self, text):
        row = self._assistant_row()
        SelectableText(row, text, self.font(14), max_width=self.content_width - 60).pack(anchor="w", pady=(1, 0))
        return row

    def _add_thinking(self):
        row = self._assistant_row()
        self.spinner_label(row, 30).pack(side="left", padx=(0, 10))
        label = ctk.CTkLabel(row, text="Думаю...", font=self.font(14), text_color=theme.MUTED)
        label.pack(side="left", pady=(1, 0))
        self.thinking = {"row": row, "label": label, "started": time.time()}
        self._tick_thinking()

    def _tick_thinking(self):
        # Перша відповідь чекає, поки модель завантажиться в пам'ять, тож пояснюємо затримку
        if self.thinking is None:
            return
        seconds = int(time.time() - self.thinking["started"])
        if seconds >= 12:
            self.thinking["label"].configure(text=f"Прокидаюся... {seconds} с (перша відповідь довша)")
        self.after(1000, self._tick_thinking)

    def _remove_thinking(self):
        if self.thinking is not None:
            self.thinking["row"].destroy()
            self.thinking = None

    def _add_image_card(self, message):
        row, card = self._card_row()

        path = Path(message["image"])
        if path.exists():
            image = self.card_image(path)
            self.image_refs.append(image)
            picture_label = ctk.CTkLabel(card, image=image, text="", cursor="hand2")
            picture_label.pack(padx=8, pady=(8, 4))
            # Натискання на картинку відкриває її на весь екран
            picture_label.bind("<Button-1>", lambda event, m=message: self.open_viewer(m))
        else:
            ctk.CTkLabel(
                card, text="Файл зображення не знайдено", width=IMAGE_SIZE, height=120,
                font=self.font(13), text_color=theme.MUTED,
            ).pack(padx=8, pady=8)

        if message.get("kind") == "image" and message.get("prompt_en"):
            # Опис, який мозок написав для художника
            SelectableText(
                card, message["prompt_en"], self.font(12), max_width=IMAGE_SIZE - 10,
                text_color=theme.MUTED, bg=theme.SURFACE,
            ).pack(anchor="w", padx=14, pady=(2, 2))

        if message.get("review"):
            # Gaia перевірила перший варіант, знайшла проблему і перемалювала
            SelectableText(
                card, f"Перевірка: {message['review']} Перемальовано.", self.font(12),
                max_width=IMAGE_SIZE - 10, text_color=theme.MUTED, bg=theme.SURFACE,
            ).pack(anchor="w", padx=14, pady=(2, 2))

        details = [message["model"]]
        if message.get("checked") and not message.get("review"):
            details.append("Перевірено")
        if message.get("recolored"):
            details.append(f"Перефарбовано: {message['target']}" if message.get("target") else "Перефарбовано")
        elif message.get("target") and message.get("target_found"):
            details.append(f"{'Прибрано' if message.get('remove') else 'Змінено'}: {message['target']}")
        elif message.get("target"):
            details.append(f"Не знайдено «{message['target']}», змінено все фото")
        elif message.get("source"):
            details.append("Зміна фото")
        if message.get("style") and message["style"] != "Без стилю":
            details.append(message["style"])
        if message["steps"]:
            details.append(f"{message['steps']} кроків")
        details += [f"{message.get('seconds', 0)} с", datetime.fromisoformat(message["created"]).strftime("%H:%M")]
        ctk.CTkLabel(
            card, text="  ·  ".join(details), font=self.font(12), text_color=theme.MUTED, anchor="w"
        ).pack(fill="x", padx=14, pady=(2, 0))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=8, pady=(2, 8))
        self.small_button(actions, "Ще варіант", self.small_icons["refresh"], lambda m=message: self.variation(m)).pack(side="left")
        self.small_button(actions, "Копіювати запит", self.small_icons["copy"], lambda m=message: self.copy_prompt(m)).pack(side="left")
        if path.exists():
            self.small_button(actions, "Відкрити", self.small_icons["open"], lambda p=path: os.startfile(p.resolve())).pack(side="left")
            self.small_button(actions, "У папці", self.small_icons["folder"], lambda p=path: self.show_in_folder(p)).pack(side="left")
        return row

    def _add_pending_card(self, width, height):
        row, card = self._card_row()
        box_width, box_height = fit(width, height, IMAGE_SIZE)
        box = ctk.CTkFrame(card, width=box_width, height=box_height, corner_radius=14, fg_color=theme.SURFACE_HOVER)
        box.pack(padx=8, pady=8)
        box.pack_propagate(False)

        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        self.spinner_label(inner, 64).pack(pady=(0, 14))
        title = ctk.CTkLabel(inner, text="Готую запит", font=self.font(15), text_color=theme.TEXT)
        title.pack()
        bar = ctk.CTkProgressBar(
            inner, width=min(240, box_width - 60), height=3, corner_radius=2,
            progress_color=theme.ACCENT, fg_color=theme.BORDER,
        )
        bar.set(0)
        bar.pack(pady=(16, 10))
        steps_label = ctk.CTkLabel(inner, text="", font=self.font(12), text_color=theme.MUTED)
        steps_label.pack()
        self.pending = {"row": row, "title": title, "bar": bar, "steps": steps_label}

    def show_in_folder(self, path):
        subprocess.Popen(f'explorer /select,"{path.resolve()}"')

    def copy_prompt(self, message):
        self.clipboard_clear()
        self.clipboard_append(message["prompt"])
        self.set_status("Запит скопійовано")

    def variation(self, message):
        # Той самий запит, стиль і формат, але новий seed, тобто нова картинка
        source = message.get("source")
        self.start_generation(
            message["prompt"],
            english=message.get("prompt_en") or message["prompt"],
            language=message.get("language", "en"),
            style=message.get("style", "Без стилю"),
            size=message.get("size", "Квадрат 1:1"),
            show_bubble=message.get("kind") != "image",
            kind=message.get("kind"),
            source=source if source and Path(source).exists() else None,
            strength=message.get("strength"),
            targets=message.get("targets") or ([message["target"]] if message.get("target") else None),
            where=message.get("where", ""),
            remove=bool(message.get("remove")),
            colors=message.get("colors"),
            box=tuple(message["box"]) if message.get("box") else None,
        )

    # ---------- Моделі ----------

    def model_available(self, name):
        path = MODELS[name]["path"]
        return bool(path) and Path(path).exists()

    def _initial_model(self):
        for name in (self.settings.get("model"), DEFAULT_MODEL, *MODELS):
            if name in MODELS and self.model_available(name):
                return name
        return None

    def select_model(self, name):
        if self.busy:
            self.model_menu.set(self.selected_model or name)
            return
        if not self.model_available(name):
            self.model_menu.set(self.selected_model or name)
            self.set_status(f"Модель {name} ще не додана. Покладіть файл сюди: {MODELS[name]['path']}")
            return
        self.selected_model = name
        self.model_menu.set(name)
        self.model_tier_label.configure(text=MODEL_TIERS.get(name, ""))
        self.settings.set("model", name)
        if name != self.loaded_model:
            self._load_model_async(name)

    def _load_model_async(self, name):
        old_pipe = self.pipe
        self.pipe = None
        self.loaded_model = None
        self._set_busy(True)
        self.set_status(f"Завантажую модель {name}...")

        def work():
            nonlocal old_pipe
            try:
                # Важкі бібліотеки підключаємо тут, у фоні, щоб вікно з'являлося одразу
                import gc

                import torch

                from src.ai.generator import load_model

                old_pipe = None
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                pipe = load_model(name)
            except Exception as error:
                self.after(0, self._on_model_failed, name, error)
                return
            self.after(0, self._on_model_loaded, name, pipe)

        threading.Thread(target=work, daemon=True).start()

    def _on_model_loaded(self, name, pipe):
        self.pipe = pipe
        self.loaded_model = name
        self._set_busy(False)
        self.set_status()
        self._preload_translator()

    def _on_model_failed(self, name, error):
        self._set_busy(False)
        self.set_status(f"Не вдалося завантажити модель {name}: {shorten(str(error), 140)}")

    def _preload_translator(self):
        # Український перекладач готуємо заздалегідь, щоб перший запит не чекав
        def work():
            try:
                from src.ai.translator import load_translator

                load_translator("uk")
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()

    # ---------- Генерація ----------

    def _set_busy(self, busy, generating=False):
        self.busy = busy
        self.generating = busy and generating
        state = "disabled" if busy else "normal"
        self.send_button.configure(state="normal" if not busy and self.pipe is not None else "disabled")
        for widget in (self.model_menu, self.style_menu, self.size_menu, self.reasoning_menu):
            widget.configure(state=state)
        # Переходити між екранами не можна лише під час створення картинки
        navigation = "disabled" if self.generating else "normal"
        for widget in (self.nav_buttons["new"], self.nav_buttons["gallery"], self.delete_button, *self.chat_buttons):
            widget.configure(state=navigation)

    def on_generate(self, event=None):
        prompt = self.prompt_entry.get().strip()
        if not prompt and self.attachment is None:
            self.set_status("Спершу напишіть повідомлення")
            return
        if self.attachment is not None and not self.brain_ready:
            self.set_status("Щоб працювати з фото, потрібна Gaia. Запустіть Ollama.")
            return
        started = self.send_message(prompt) if self.brain_ready else self.start_generation(prompt)
        if started:
            self.prompt_entry.clear()
            self.clear_attachment()

    # ---------- Мозок ----------

    def set_reasoning(self, value):
        # Зміна рівня з поля вводу або з налаштувань: запам'ятовуємо і показуємо однаково в обох місцях
        self.settings.set("reasoning", value)
        self.reasoning_menu.set(value)
        # У нового рівня може бути інша модель: перевіряємо, чи вона є, і завантажуємо її
        self._check_brain()

    def reasoning(self):
        # Налаштування вибраного рівня міркувань: {"model", "think", "check"}
        from src.ai import brain

        return brain.level(self.settings.get("reasoning"))

    def _check_brain(self):
        # Перевіряємо у фоні, чи запущена Ollama з моделлю вибраного рівня, і одразу завантажуємо її
        model = self.reasoning()["model"]

        def work():
            try:
                from src.ai import brain

                ready = brain.is_available(model)
            except Exception:
                ready = False
            self.after(0, self._on_brain_checked, ready)
            if ready:
                try:
                    brain.warm_up(model)
                except Exception:
                    pass

        threading.Thread(target=work, daemon=True).start()

    def _on_brain_checked(self, ready):
        self.brain_ready = ready
        if not ready and not self.busy:
            self.set_status("Мозок Linum недоступний (запустіть Ollama). Поки що лише малюю за описом.")

    def send_message(self, text):
        # Повідомлення йде до мозку, а він вирішує: відповісти, намалювати чи змінити фото
        if self.busy:
            return False
        chat = self.chats.get(self.current_chat_id)
        if chat is None:
            chat = self.chats.create_chat()
            self.current_chat_id = chat["id"]
        chat_id = chat["id"]

        message = {"kind": "user", "text": text, "created": self.now()}
        if self.attachment is not None:
            message["attachment"] = self.attachment
        self.chats.add_message(chat_id, message)
        if self.view != "chat":
            self._set_view("chat")
            self._reset_feed()
        self.header_title.configure(text=shorten(chat["title"], 70))
        self.delete_button.grid()
        self.render_chat_list()
        bubble = self._add_prompt_bubble({"prompt": text, "attachment": message.get("attachment")})
        fade_in([bubble])()
        self._ask_brain(chat_id, text)
        return True

    def _ask_brain(self, chat_id, text):
        # Надсилає розмову мозку. Окремо від send_message, щоб кнопка "Повторити" могла
        # спитати ще раз, не додаючи повідомлення користувача вдруге.
        chat = self.chats.get(chat_id)
        self._add_thinking()
        self._scroll_to_bottom()
        self._set_busy(True, generating=True)
        settings = self.reasoning()
        self.set_status("Linum міркує, це може зайняти хвилину-дві..." if settings["think"] else "Linum думає...")
        history_messages = list(chat["messages"])

        def work():
            try:
                from src.ai import brain

                # Художник міг лишити зайняту відеопам'ять. Віддаємо її, щоб Gaia завантажилась.
                free_gpu_memory()
                decision = brain.decide(brain.history_from_chat(history_messages), settings)
            except Exception as error:
                self.after(0, self._on_brain_failed, chat_id, text, error)
                return
            self.after(0, self._on_decided, chat_id, text, decision)

        threading.Thread(target=work, daemon=True).start()

    def _on_brain_failed(self, chat_id, text, error):
        # Помилку показуємо прямо в чаті, з кнопкою, щоб спитати ще раз
        self._remove_thinking()
        self._set_busy(False)
        self.set_status()
        message = str(error)
        if "out of memory" in message.lower() or "terminated" in message.lower():
            reason = "не вистачило пам'яті, щоб завантажитися"
        elif "connect" in message.lower() or "refused" in message.lower():
            reason = "Ollama не запущена"
        else:
            reason = shorten(message, 120)
        row = self._assistant_row()
        ctk.CTkLabel(
            row, text=f"Gaia не змогла відповісти: {reason}.", font=self.font(14), text_color=theme.DANGER,
        ).pack(side="left")

        def retry():
            if self.busy:
                return
            row.destroy()
            self._ask_brain(chat_id, text)

        self.small_button(row, "Повторити", self.small_icons["refresh"], retry).pack(side="left", padx=(10, 0))
        self._scroll_to_bottom()

    def _on_decided(self, chat_id, text, decision):
        self._remove_thinking()
        if decision["reply"]:
            self.chats.add_message(chat_id, {"kind": "assistant", "text": decision["reply"], "created": self.now()})
            fade_in([self._add_assistant_text(decision["reply"])])()
            self._scroll_to_bottom()
        self._set_busy(False)
        self.set_status()

        if decision["action"] == "chat":
            self.prompt_entry.focus_set()
            return

        source = None
        if decision["action"] == "edit":
            source = self.last_image(chat_id)
        if self.pipe is None:
            self.set_status("Художня модель ще завантажується. Повторіть прохання за хвилину.")
            return
        self.start_generation(
            text,
            english=decision["prompt"],
            language="en",
            show_bubble=False,
            kind="image",
            source=source,
            strength=decision["strength"] if source else None,
            unload_brain=True,
            targets=decision["targets"] if source else None,
            where=decision["where"] if source else "",
            remove=decision["remove"] if source else False,
            colors=decision["colors"] if source else None,
        )

    def last_image(self, chat_id):
        chat = self.chats.get(chat_id)
        # Останнє фото в чаті: створене Linum або додане користувачем
        for message in reversed(chat["messages"] if chat else []):
            for key in ("image", "attachment"):
                if message.get(key) and Path(message[key]).exists():
                    return message[key]
        return None

    @staticmethod
    def now():
        return datetime.now().isoformat(timespec="seconds")

    # ---------- Створення і зміна зображень ----------

    def start_generation(self, prompt, english=None, language=None, style=None, size=None,
                         show_bubble=True, kind=None, source=None, strength=None, unload_brain=False,
                         targets=None, where="", remove=False, colors=None, box=None):
        # source: шлях до фото, яке треба змінити. Без нього малюється нове зображення.
        # targets: англійські назви предмета, який треба знайти на фото і змінити лише його.
        # remove: прибрати цей предмет (місце заливається фоном і домальовується).
        # colors: лише перефарбувати предмет, без художника: [{"from": "#...", "to": "#..."}].
        # box: рамка предмета (x1, y1, x2, y2), якщо вже відома (наприклад, для "Ще варіант").
        if self.busy or self.pipe is None:
            return False
        chat = self.chats.get(self.current_chat_id)
        if chat is None:
            chat = self.chats.create_chat()
            self.current_chat_id = chat["id"]

        style = style or self.style_menu.get()
        size = size or self.size_menu.get()
        width, height = SIZES.get(size, SIZES["Квадрат 1:1"])
        if source is not None:
            with Image.open(source) as original:
                width, height = original.size
            strength = strength or 0.55
        seed = random.randint(0, 2**31 - 1)
        translate = bool(self.settings.get("translate"))
        quality_boost = bool(self.settings.get("quality_boost"))

        if self.view != "chat":
            self._set_view("chat")
            self.header_title.configure(text=shorten(prompt, 70))
            self._reset_feed()
        if show_bubble:
            self._add_prompt_bubble({"prompt": prompt})
        self._add_pending_card(width, height)
        self.pending["edit"] = source is not None
        self._scroll_to_bottom()

        model = self.loaded_model
        steps = MODELS[model]["steps"]
        chat_id = chat["id"]
        pipe = self.pipe
        started = time.time()
        settings = self.reasoning()
        self._set_busy(True, generating=True)
        self.set_status(f"Створюю зображення моделлю {model}...")

        def on_step(step, total):
            self.after(0, self._update_progress, step, total)

        def work():
            nonlocal english, language, steps, box, seed
            review = None
            first_image = None
            try:
                from src.ai.generator import edit_image, generate_image, save_image
                from src.ai.translator import to_english

                if unload_brain:
                    from src.ai import brain

                    if source is not None and targets and box is None:
                        # Поки Gaia ще в пам'яті, просимо її показати рамкою, де предмет
                        self.after(0, self._set_pending_title, f"Шукаю: {targets[0]}")
                        box = brain.locate(source, targets[0], where, model=settings["model"])
                    # Мозок і художник разом не вміщаються в пам'ять, тому мозок на час малювання вивантажуємо
                    brain.unload()
                if english is None:
                    if translate:
                        english, language = to_english(prompt)
                    else:
                        english, language = prompt, "en"
                self.after(0, self._on_translated, english, language)
                full_prompt = english
                if STYLES.get(style):
                    full_prompt = f"{english}, {STYLES[style]}"
                negative = NEGATIVE_PROMPT if quality_boost else None
                mask = None
                found = None
                edit_strength = strength
                if source is not None and targets:
                    # Шукаємо предмет на фото, щоб перемалювати лише його
                    self.after(0, self._set_pending_title, f"Шукаю: {targets[0]}")
                    from src.ai.segmenter import find_mask

                    mask, found = find_mask(source, targets, where=where, remove=remove, box=box)
                    if mask is not None and remove:
                        # Запобіжник: "прибрати" не може стерти третину фото. Найімовірніше,
                        # шукач сплутав предмет з головним об'єктом, тож краще нічого не прибирати.
                        area = sum(1 for value in mask.getdata() if value) / (mask.width * mask.height)
                        if area > 0.33:
                            mask, found = None, None
                    if mask is not None:
                        self.after(0, self._set_pending_title, "Прибираю" if remove else "Змінюю зображення")
                        if remove:
                            # Прибираємо: художник не повинен намалювати цей предмет знову
                            negative = ", ".join(targets) + ", " + (negative or "")
                            edit_strength = 0.6
                        else:
                            # Зміна одного предмета потребує сильнішого перемальовування
                            edit_strength = max(strength or 0.55, 0.7)
                def draw(text, seed):
                    # Малює нове зображення або змінює фото. Повертає (шлях, кроки).
                    if source is None:
                        return generate_image(pipe, text, model, on_step, negative, width, height, seed), steps
                    return edit_image(
                        pipe, source, text, mask=mask, strength=edit_strength, model_name=model,
                        on_step=on_step, negative_prompt=negative, seed=seed, fill=remove and mask is not None,
                    )

                recolored = bool(colors) and source is not None and (mask is not None or not targets)
                if recolored:
                    # Лише колір: міняємо його точно по пікселях, художник не потрібен
                    from src.ai.recolor import recolor

                    self.after(0, self._set_pending_title, "Перефарбовую")
                    with Image.open(source) as original:
                        whole = Image.new("L", original.size, 255)
                        path = save_image(recolor(original, mask if mask is not None else whole, colors))
                    steps = 0
                else:
                    path, steps = draw(full_prompt, seed)

                if settings["check"] and unload_brain and not recolored:
                    # Gaia дивиться на готову картинку. Якщо вийшло не те, перемальовує один раз
                    # за її виправленим описом. Художника спершу прибираємо з відеопам'яті.
                    from src.ai import brain

                    free_gpu_memory()
                    self.after(0, self._set_pending_title, "Перевіряю результат")
                    verdict = brain.review(path, prompt, english, settings)
                    if verdict is not None and not verdict["ok"]:
                        review = verdict["problem"]
                        first_image = path
                        brain.unload()
                        self.after(0, self._set_pending_title, "Перемальовую")
                        english = verdict["prompt"]
                        full_prompt = f"{english}, {STYLES[style]}" if STYLES.get(style) else english
                        seed = random.randint(0, 2**31 - 1)
                        path, steps = draw(full_prompt, seed)
            except Exception as error:
                self.after(0, self._on_generate_failed, error)
                return
            message = {
                "prompt": prompt,
                "prompt_en": english,
                "language": language,
                "style": style,
                "size": size,
                "seed": seed,
                "image": str(path),
                "model": model,
                "steps": steps,
                "seconds": round(time.time() - started),
                "created": datetime.now().isoformat(timespec="seconds"),
            }
            if kind:
                message["kind"] = kind
            if settings["check"] and unload_brain and not recolored:
                message["checked"] = True
                if review is not None:
                    # Що Gaia не сподобалось у першому варіанті, і сам перший варіант
                    message["review"] = review
                    message["first_image"] = str(first_image)
            if source is not None:
                message["source"] = str(source)
                message["strength"] = strength
                if targets:
                    message["targets"] = targets
                    message["where"] = where
                    message["target"] = found or targets[0]
                    message["remove"] = remove
                    message["target_found"] = mask is not None
                    if box is not None:
                        message["box"] = [round(value) for value in box]
                if colors:
                    message["colors"] = colors
                    message["recolored"] = recolored
            self.after(0, self._on_generated, chat_id, message)

        threading.Thread(target=work, daemon=True).start()
        return True

    def _on_translated(self, english, language):
        if self.pending is None:
            return
        self.pending["title"].configure(text="Змінюю зображення" if self.pending.get("edit") else "Створюю зображення")
        if language != "en":
            self.pending["steps"].configure(text=shorten(f"Переклад: {english}", 54))

    def _set_pending_title(self, text):
        if self.pending is not None:
            self.pending["title"].configure(text=text)

    def _update_progress(self, step, total):
        if self.pending is None:
            return
        self.pending["bar"].set(step / total)
        self.pending["steps"].configure(text=f"Крок {step} з {total}")

    def _on_generated(self, chat_id, message):
        self.chats.add_message(chat_id, message)
        self._set_busy(False)
        self.render_chat(fade="last")
        self.render_chat_list()
        self.set_status(f"Готово за {message['seconds']} с")
        self.prompt_entry.focus_set()

    def _on_generate_failed(self, error):
        self._set_busy(False)
        self.render_chat(fade=None)
        self.render_chat_list()
        self.set_status(f"Не вдалося створити зображення: {shorten(str(error), 140)}")

    # ---------- Меню акаунта ----------

    def later(self, func):
        # Кнопки всередині меню і перегляду знищуються разом з ними,
        # тому дію запускаємо на мить пізніше, коли кнопка вже відпрацювала
        return lambda: self.after(1, func)

    def toggle_account_menu(self, event=None):
        if self.account_menu is not None:
            self.close_account_menu()
            return
        name = self.settings.get("name").strip() or "Профіль"
        menu = ctk.CTkFrame(
            self, width=250, fg_color=theme.SURFACE, corner_radius=12, border_width=1, border_color=theme.BORDER
        )

        head = ctk.CTkFrame(menu, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkLabel(head, text=name, font=self.font(14, "bold"), text_color=theme.TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(
            head, text=f"{APP_NAME} {APP_VERSION}", font=self.font(12), text_color=theme.MUTED, anchor="w"
        ).pack(anchor="w")
        ctk.CTkFrame(menu, height=1, corner_radius=0, fg_color=theme.BORDER).pack(fill="x", padx=1)

        is_dark = ctk.get_appearance_mode() == "Dark"
        items = (
            ("Налаштування", "settings", lambda: self.open_settings("general")),
            ("Світла тема" if is_dark else "Темна тема", "palette", self.quick_toggle_theme),
            ("Папка із зображеннями", "folder", lambda: open_folder(OUTPUTS_DIR)),
            ("Про Linum", "model", lambda: self.open_settings("about")),
        )
        box = ctk.CTkFrame(menu, fg_color="transparent")
        box.pack(fill="x", padx=6, pady=6)
        for text, icon, command in items:
            ctk.CTkButton(
                box,
                text=text,
                image=self.menu_icons[icon],
                compound="left",
                anchor="w",
                width=236,
                height=34,
                corner_radius=8,
                font=self.font(13),
                fg_color="transparent",
                hover_color=theme.SURFACE_HOVER,
                text_color=theme.TEXT,
                command=self.later(lambda c=command: (self.close_account_menu(), c())),
            ).pack(fill="x")

        menu.place(in_=self, x=10, rely=1.0, y=-60, anchor="sw")
        menu.lift()
        self.account_menu = menu

    def close_account_menu(self):
        if self.account_menu is not None:
            self.account_menu.destroy()
            self.account_menu = None

    def _on_global_click(self, event):
        if self.account_menu is None:
            return
        widget = str(event.widget)
        if widget.startswith(str(self.account_menu)) or widget.startswith(str(self.profile)):
            return
        self.close_account_menu()

    def _on_escape(self, event=None):
        if self.viewer is not None:
            self.close_viewer()
        elif self.account_menu is not None:
            self.close_account_menu()

    def quick_toggle_theme(self):
        self.set_theme("light" if ctk.get_appearance_mode() == "Dark" else "dark")

    def set_theme(self, mode):
        ctk.set_appearance_mode(mode)
        self.settings.set("theme", mode)
        refresh_theme()

    def set_name(self, name):
        self.settings.set("name", name.strip())
        self._update_profile()
        if self.view == "home":
            self.greeting_label.configure(text=greeting_text(name.strip()))

    # ---------- Перегляд фото на весь екран ----------

    def open_viewer(self, message, chat_id=None):
        path = Path(message["image"])
        if not path.exists():
            return
        self.close_viewer()
        self.close_account_menu()

        overlay = ctk.CTkFrame(self, corner_radius=0, fg_color=theme.VIEWER_BG)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()
        self.viewer = overlay

        top = ctk.CTkFrame(overlay, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(14, 0))
        ctk.CTkLabel(
            top, text=shorten(message["prompt"], 90), font=self.font(14), text_color=theme.VIEWER_TEXT, anchor="w"
        ).pack(side="left", padx=(6, 0))

        def viewer_button(text, command):
            button = ctk.CTkButton(
                top,
                text=text,
                width=0,
                height=32,
                corner_radius=8,
                font=self.font(13),
                fg_color="transparent",
                hover_color=theme.VIEWER_HOVER,
                text_color=theme.VIEWER_TEXT,
                command=command,
            )
            button.pack(side="right", padx=(6, 0))
            return button

        viewer_button("Закрити", self.later(self.close_viewer))
        viewer_button("У папці", lambda: self.show_in_folder(path))
        copy_button = viewer_button("Копіювати", lambda: self.copy_image(path, copy_button))
        self.viewer_copy = lambda: self.copy_image(path, copy_button)
        viewer_button("Відкрити", lambda: os.startfile(path.resolve()))
        if chat_id is not None:
            viewer_button("Перейти до чату", self.later(lambda: (self.close_viewer(), self.open_chat(chat_id))))

        # Картинка займає весь вільний простір вікна, зберігаючи пропорції
        scaling = ctk.ScalingTracker.get_widget_scaling(self)
        available_width = self.winfo_width() / scaling - 120
        available_height = self.winfo_height() / scaling - 150
        source = Image.open(path).convert("RGB")
        factor = min(available_width / source.width, available_height / source.height)
        size = (max(1, int(source.width * factor)), max(1, int(source.height * factor)))
        sharp = source.resize((int(size[0] * scaling), int(size[1] * scaling)), Image.LANCZOS)
        picture = rounded(sharp, int(12 * scaling))
        self.viewer_image = ctk.CTkImage(light_image=picture, dark_image=picture, size=size)
        ctk.CTkLabel(overlay, image=self.viewer_image, text="").pack(expand=True)

        details = [message["model"]]
        if message.get("style") and message["style"] != "Без стилю":
            details.append(message["style"])
        details.append(f"{source.width}×{source.height}")
        if message.get("seed") is not None:
            details.append(f"seed {message['seed']}")
        ctk.CTkLabel(
            overlay, text="  ·  ".join(details), font=self.font(12), text_color=theme.VIEWER_MUTED
        ).pack(pady=(0, 16))

        # Клік по темному тлі навколо картинки закриває перегляд
        overlay.bind("<Button-1>", lambda event: self.close_viewer())

    def copy_image(self, path, button=None):
        try:
            copy_image_to_clipboard(path)
            text = "Скопійовано"
        except Exception:
            text = "Не вдалося"
        if button is not None:
            button.configure(text=text)
            self.after(1500, lambda: button.winfo_exists() and button.configure(text="Копіювати"))

    def _on_copy_key(self, event):
        # Ctrl+C копіює фото лише коли відкритий перегляд
        if self.viewer is not None:
            self.viewer_copy()

    def close_viewer(self):
        if self.viewer is not None:
            self.viewer.destroy()
            self.viewer = None
            self.viewer_image = None

    # ---------- Сторінка налаштувань ----------

    def open_settings(self, section="general"):
        if self.generating:
            self.set_status("Зачекайте, поки створиться зображення")
            return
        previous = self.chats.get(self.current_chat_id)
        if previous and not previous["messages"]:
            self.chats.delete_chat(previous["id"])
            self.current_chat_id = None
        self._set_view("settings")
        self.header_title.configure(text="")
        self.delete_button.grid_remove()
        self.render_chat_list()

        page = ctk.CTkFrame(self.main, fg_color="transparent")
        page.grid(row=1, column=0, columnspan=3, rowspan=3, sticky="nsew")
        self.settings_page = page

        container = ctk.CTkFrame(page, fg_color="transparent")
        container.pack(fill="y", expand=True, pady=(16, 20))
        ctk.CTkLabel(
            container, text="Налаштування", font=self.font(30, family="Georgia"), text_color=theme.TEXT, anchor="w"
        ).pack(anchor="w", pady=(0, 24))

        body = ctk.CTkFrame(container, fg_color="transparent")
        body.pack(fill="both", expand=True)
        nav = ctk.CTkFrame(body, fg_color="transparent")
        nav.pack(side="left", fill="y", anchor="n")
        content = ctk.CTkScrollableFrame(
            body,
            width=600,
            fg_color="transparent",
            scrollbar_button_color=theme.BG,
            scrollbar_button_hover_color=theme.BORDER,
        )
        content.pack(side="left", fill="y", padx=(32, 0))

        for key, title in (
            ("general", "Загальні"),
            ("appearance", "Вигляд"),
            ("generation", "Генерація"),
            ("storage", "Сховище"),
            ("about", "Про Linum"),
        ):
            ctk.CTkButton(
                nav,
                text=title,
                anchor="w",
                width=180,
                height=34,
                corner_radius=8,
                font=self.font(14),
                fg_color=theme.SELECTED if key == section else "transparent",
                hover_color=theme.SURFACE_HOVER,
                text_color=theme.TEXT,
                command=self.later(lambda k=key: self.open_settings(k)),
            ).pack(fill="x", pady=1)

        getattr(self, f"_settings_{section}")(content)

    def _settings_title(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=self.font(18, "bold"), text_color=theme.TEXT, anchor="w").pack(
            fill="x", pady=(0, 18)
        )

    def _setting_row(self, parent, title, description=None):
        # Рядок налаштування: назва й пояснення зліва, елемент керування справа
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 14))
        row.grid_columnconfigure(0, weight=1)
        text = ctk.CTkFrame(row, fg_color="transparent")
        text.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(text, text=title, font=self.font(14), text_color=theme.TEXT, anchor="w").pack(anchor="w")
        if description:
            ctk.CTkLabel(
                text, text=description, font=self.font(12), text_color=theme.MUTED,
                anchor="w", justify="left", wraplength=380,
            ).pack(anchor="w")
        ctk.CTkFrame(parent, height=1, corner_radius=0, fg_color=theme.BORDER).pack(fill="x", pady=(0, 14))
        return row

    def _switch(self, parent, key, on_change=None):
        variable = tk.BooleanVar(value=bool(self.settings.get(key)))

        def changed():
            self.settings.set(key, variable.get())
            if on_change is not None:
                on_change(variable.get())

        switch = ctk.CTkSwitch(
            parent,
            text="",
            variable=variable,
            command=changed,
            width=46,
            switch_width=40,
            switch_height=22,
            progress_color=("#1A1A1A", "#ECECEC"),
            fg_color=("#D6D3CE", "#4A4A4A"),
            button_color=("#FFFFFF", "#1A1A1A"),
            button_hover_color=("#FFFFFF", "#1A1A1A"),
        )
        switch.grid(row=0, column=1, sticky="e")
        return switch

    def _outline_button(self, parent, text, command, danger=False):
        button = ctk.CTkButton(
            parent,
            text=text,
            width=0,
            height=32,
            corner_radius=8,
            font=self.font(13),
            fg_color="transparent",
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.DANGER if danger else theme.TEXT,
            border_width=1,
            border_color=theme.BORDER,
            command=command,
        )
        button.grid(row=0, column=1, sticky="e")
        return button

    def _option(self, parent, values, current, command):
        menu = ctk.CTkOptionMenu(parent, values=values, command=command, **self.menu_style())
        menu.set(current)
        menu.grid(row=0, column=1, sticky="e")
        return menu

    def _settings_general(self, content):
        self._settings_title(content, "Загальні")

        row = self._setting_row(content, "Ваше ім'я", "Так Linum звертатиметься до вас на головному екрані")
        name_entry = ctk.CTkEntry(
            row,
            width=220,
            height=34,
            corner_radius=8,
            border_width=1,
            border_color=theme.BORDER,
            fg_color=theme.SURFACE,
            text_color=theme.TEXT,
            placeholder_text="Ім'я",
            placeholder_text_color=theme.MUTED,
            font=self.font(13),
        )
        if self.settings.get("name"):
            name_entry.insert(0, self.settings.get("name"))
        name_entry.grid(row=0, column=1, sticky="e")
        name_entry.bind("<KeyRelease>", lambda event: self.set_name(name_entry.get()))

        row = self._setting_row(
            content,
            "Перекладати запити",
            "Українські й російські запити перекладаються англійською, бо модель розуміє лише її",
        )
        self._switch(row, "translate")

    def _settings_appearance(self, content):
        self._settings_title(content, "Вигляд")

        row = self._setting_row(content, "Тема", "Системна тема підлаштовується під налаштування Windows")
        names = {mode: label for label, mode in THEMES.items()}
        selector = ctk.CTkSegmentedButton(
            row, values=list(THEMES.keys()), command=lambda label: self.set_theme(THEMES[label]), **self.segmented_style()
        )
        selector.set(names.get(self.settings.get("theme"), "Системна"))
        selector.grid(row=0, column=1, sticky="e")

        def sidebar_changed(value):
            self.sidebar_visible = value
            self._apply_sidebar()

        row = self._setting_row(content, "Бокова панель", "Показувати список чатів зліва")
        self._switch(row, "sidebar", sidebar_changed)

    def _settings_generation(self, content):
        self._settings_title(content, "Генерація")

        row = self._setting_row(
            content,
            "Рівень міркувань",
            "Низький найшвидший. Високий і Ультра думають перед відповіддю. "
            "Середній і Ультра перевіряють готову картинку",
        )
        selector = ctk.CTkSegmentedButton(
            row, values=list(REASONING.keys()), command=self.set_reasoning, **self.segmented_style()
        )
        selector.set(self.settings.get("reasoning"))
        selector.grid(row=0, column=1, sticky="e")

        row = self._setting_row(content, "Модель", "Fornax швидка, Gaia збалансована, Cygnus найкраща")
        model_menu = None

        def model_changed(value):
            self.select_model(value)
            model_menu.set(self.selected_model or value)

        model_menu = self._option(row, list(MODELS.keys()), self.selected_model or DEFAULT_MODEL, model_changed)

        def style_changed(value):
            self.settings.set("style", value)
            self.style_menu.set(value)

        row = self._setting_row(content, "Стиль за замовчуванням", "Стиль, з яким відкривається новий чат")
        self._option(row, list(STYLES.keys()), self.style_menu.get(), style_changed)

        def size_changed(value):
            self.settings.set("size", value)
            self.size_menu.set(value)

        row = self._setting_row(content, "Формат за замовчуванням", "Портрет і альбом створюються довше за квадрат")
        self._option(row, list(SIZES.keys()), self.size_menu.get(), size_changed)

        row = self._setting_row(
            content,
            "Покращення якості",
            "Просить модель уникати розмитості, зайвих пальців і деформацій",
        )
        self._switch(row, "quality_boost")

        steps = ", ".join(f"{name} {info['steps']}" for name, info in MODELS.items())
        self._setting_row(content, "Кроки генерації", f"{steps}. Змінюються у файлі config/config.py")

    def _settings_storage(self, content):
        self._settings_title(content, "Сховище")

        images = self.all_images()
        megabytes = sum(Path(message["image"]).stat().st_size for _, message in images) / (1024 * 1024)
        chats = [chat for chat in self.chats.chats if chat["messages"]]

        row = self._setting_row(content, "Зображення", f"{len(images)} шт., {megabytes:.1f} МБ")
        self._outline_button(row, "Відкрити папку", lambda: open_folder(OUTPUTS_DIR))

        models_folder = Path(MODELS[DEFAULT_MODEL]["path"]).parent
        row = self._setting_row(content, "Моделі", f"Файли моделей лежать у {models_folder.as_posix()}")
        self._outline_button(row, "Відкрити папку", lambda: open_folder(models_folder))

        row = self._setting_row(content, "Чати", f"{len(chats)} шт. Видалення чатів не видаляє самих зображень")
        self._outline_button(row, "Видалити всі чати", self.later(self.clear_all_chats), danger=True)

    def _settings_about(self, content):
        head = ctk.CTkFrame(content, fg_color="transparent")
        head.pack(fill="x", pady=(0, 22))
        names = ctk.CTkFrame(head, fg_color="transparent")
        names.pack(side="left")
        ctk.CTkLabel(names, text=APP_NAME, font=self.font(20, "bold"), text_color=theme.TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(
            names, text=f"Версія {APP_VERSION}", font=self.font(13), text_color=theme.MUTED, anchor="w"
        ).pack(anchor="w")

        gpu = "Визначиться після завантаження моделі"
        torch = sys.modules.get("torch")
        if torch is not None and torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)

        self._setting_row(content, "Модель", f"{self.loaded_model or DEFAULT_MODEL}: Stable Diffusion 1.5")
        self._setting_row(content, "Відеокарта", gpu)
        self._setting_row(
            content, "Режим роботи", "Повна точність (fp32), частини моделі чекають своєї черги в оперативній пам'яті"
        )
        self._setting_row(content, "Переклад", "Helsinki-NLP opus-mt для української і російської, працює на процесорі")

    def clear_all_chats(self):
        confirmed = messagebox.askyesno(
            "Видалити всі чати",
            "Видалити всі чати?\nЗображення залишаться в папці outputs.",
            parent=self,
        )
        if not confirmed:
            return
        self.chats.chats = []
        self.chats.save()
        self.current_chat_id = None
        self.render_chat_list()
        self.open_settings("storage")


if __name__ == "__main__":
    LinumApp().mainloop()
