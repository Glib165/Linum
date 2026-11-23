# Головне вікно програми Linum

import ctypes
import gc
import os
import random
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
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
    UPLOAD_MAX_SIZE,
    SIZES,
    STYLES,
    REASONING,
    DEFAULT_REASONING,
    DEVELOPER,
)
from src.backend.services.chat_store import ChatStore
from src.backend.services.settings_store import SettingsStore
from src.frontend import theme
from src.frontend.icons import make_icon
from src.frontend.i18n import LANGUAGES, greeting, label, set_language, t, unlabel
from src.frontend.system import MAC, copy_image_mac, open_path, show_in_folder
from src.frontend.widgets import (
    PromptBox,
    SelectableText,
    fade_in,
    install_clipboard_keys,
    refresh_theme,
    themed,
)

THEMES = {"light": "theme_light", "dark": "theme_dark", "system": "theme_system"}
MODEL_TIERS = {"Fornax": "tier_fast", "Gaia": "tier_balanced", "Cygnus": "tier_best"}
LANGUAGE_NAMES = {"uk": "from_ukrainian", "ru": "from_russian"}

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


# Число, від якого залежить, яке привітання випаде. Обирається один раз при запуску:
# поки Linum відкритий, привітання те саме, а наступного запуску буде інше.
GREETING_SEED = random.randint(0, 2**31 - 1)


def greeting_text(name):
    hour = datetime.now().hour
    if 5 <= hour < 12:
        period = "morning"
    elif 12 <= hour < 18:
        period = "afternoon"
    elif 18 <= hour < 23:
        period = "evening"
    else:
        period = "night"
    return greeting(period, name, random.Random(GREETING_SEED))


def copy_image_to_clipboard(path):
    """Кладе картинку в буфер обміну, щоб її можна було вставити в чат чи редактор."""
    if MAC:
        return copy_image_mac(path)
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
    elif torch is not None and torch.backends.mps.is_available():
        torch.mps.empty_cache()


class Cancelled(Exception):
    # Користувач натиснув "Стоп": малювання обривається на найближчому кроці
    pass


def torch_out_of_memory():
    # Клас помилки "не вистачило відеопам'яті" з PyTorch
    import torch

    return torch.cuda.OutOfMemoryError


def open_folder(path):
    folder = Path(path)
    folder.mkdir(parents=True, exist_ok=True)
    open_path(folder)


class LinumApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings = SettingsStore(SETTINGS_FILE)
        # Мова інтерфейсу: усі написи t(...) далі показуються нею
        set_language(self.settings.get("language"))
        # Раніше ім'я і прізвище писалися в одне поле. Тепер для прізвища є своє.
        full = self.settings.get("name").strip()
        if " " in full and not self.settings.get("surname"):
            first, rest = full.split(" ", 1)
            self.settings.set("name", first)
            self.settings.set("surname", rest.strip())
        self.chats = ChatStore(CHATS_FILE)
        ctk.set_appearance_mode(self.settings.get("theme"))

        self.pipe = None
        self.loaded_model = None
        self.selected_model = None
        self.artist_idle_timer = None
        self.artist_running = False
        self.ai_lock = threading.Lock()
        self.model_tiers = {name: t(key) for name, key in MODEL_TIERS.items()}
        # busy: модель вантажиться або створює картинку, тому кнопку "створити" вимкнено.
        # generating: саме створюється картинка, тоді не можна і переходити між екранами.
        self.busy = False
        self.generating = False
        self.view = None
        self.current_chat_id = None
        self.chat_buttons = []
        # Що показує список чатів: None (усі), ("project", назва) або ("archive",)
        self.list_mode = None
        # Черга уроків: картинки, з яких Gaia ще має зробити урок (оцінені або з помилкою від Критика)
        self.lesson_queue = []
        self.learning = False
        # Кнопка "Стоп": номер поточної справи (відповідь чи малювання) і прохання її зупинити.
        # Результат справи, яку вже зупинили, приходить пізніше з іншим номером і просто ігнорується.
        self.job_id = 0
        self.cancel_requested = False
        # Тренування агентів (сторінка "Досвід")
        self.training = False
        self.training_stop = False
        self.training_status = ""
        self.training_label = None
        self.training_button = None
        self.training_recent = []
        self.image_refs = []
        self.thumb_cache = {}
        self.card_cache = {}
        self.feed_body = None
        self.fonts = {}
        self.pending = None
        # None до першої перевірки Ollama. Якщо моделі немає, Linum малює за запитом.
        self.brain_ready = None
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
            "refresh", "copy", "open", "folder", "palette", "frame", "model", "bulb", "expand",
        )}
        self.dots_icon = make_icon("dots", 16, theme.TEXT)
        # Оцінка картинки: сірі іконки, а вибрана оцінка яскравіша
        self.rating_icons = {
            (name, active): make_icon(name, 15, theme.TEXT if active else theme.MUTED)
            for name in ("thumb_up", "thumb_down") for active in (False, True)
        }
        self.menu_icons = {name: make_icon(name, 16, theme.TEXT) for name in (
            "settings", "palette", "folder", "model", "person",
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
            self.update_brain_button()
            self.set_status(t("no_model_files"))
        else:
            self.select_model(first_model)
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
        # Через кілька секунд після запуску тихо питаємо GitHub, чи немає нової версії
        self.restart_requested = False
        self.after(5_000, self._check_update)

    # ---------- Оновлення ----------

    def _check_update(self):
        from src import updater

        if not updater.can_update():
            return

        def work():
            release = updater.latest_release()
            if release is not None and updater.is_newer(release["version"], APP_VERSION):
                self.after(0, self._offer_update, release)

        threading.Thread(target=work, daemon=True).start()

    def _offer_update(self, release):
        from tkinter import messagebox

        if self.busy:
            # Linum зараз малює чи думає: запропонуємо трохи пізніше, щоб не заважати
            self.after(10_000, self._offer_update, release)
            return
        if not messagebox.askyesno(APP_NAME, t("update_available").format(version=release["version"]), parent=self):
            return
        self._set_busy(True)
        self.set_status(t("update_download"))

        def work():
            from src import updater

            try:
                updater.install(release, lambda stage: self.after(0, self.set_status, t(f"update_{stage}")))
            except Exception as error:
                self.after(0, self._on_update_failed, error)
                return
            self.after(0, self._on_updated, release)

        threading.Thread(target=work, daemon=True).start()

    def _on_update_failed(self, error):
        self._set_busy(False)
        self.set_status(t("update_failed").format(error=shorten(str(error), 140)))

    def _on_updated(self, release):
        from tkinter import messagebox

        messagebox.showinfo(APP_NAME, t("update_done").format(version=release["version"]), parent=self)
        # main.py побачить цю позначку і запустить Linum знову, вже нову версію
        self.restart_requested = True
        self.destroy()

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
        self.icon_path = str(ico_path.resolve())
        if MAC:
            # На Mac іконки .ico немає: показуємо звичайну картинку
            from PIL import ImageTk

            self.mac_icon = ImageTk.PhotoImage(Image.open(ICON_PATH).convert("RGB").resize((256, 256)))
            self.iconphoto(True, self.mac_icon)
        else:
            self.iconbitmap(self.icon_path)
        # Ім'я "Linum" замість "Python" у меню панелі завдань і при закріпленні
        from src.frontend.taskbar import describe_window

        self.after(300, lambda: describe_window(self, APP_NAME, self.icon_path))

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
        self.status_label.configure(text=text or t("send_hint"))

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
            ("new", t("new_chat"), "plus", self.new_chat),
            ("search", t("search"), "search", self.toggle_search),
            ("gallery", t("gallery"), "gallery", self.show_gallery),
            ("folder", t("images_folder"), "folder", lambda: open_folder(OUTPUTS_DIR)),
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
            placeholder_text=t("search_placeholder"),
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

        # Заголовок над списком: "Закріплені", якщо є закріплені чати, інакше "Нещодавні"
        self.list_title = ctk.CTkLabel(
            self.sidebar, text=t("recent"), font=self.font(12), text_color=theme.MUTED, anchor="w"
        )
        self.list_title.grid(row=3, column=0, sticky="ew", padx=18, pady=(18, 4))

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
        self.avatar = None
        self.profile_name = ctk.CTkLabel(profile, text="", font=self.font(14), text_color=theme.TEXT, anchor="w")
        self.profile_name.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        for widget in (profile, self.profile_name):
            self._bind_profile(widget)
        self._update_profile()

    def full_name(self):
        return f"{self.settings.get('name').strip()} {self.settings.get('surname').strip()}".strip()

    def avatar_image(self, size):
        # Фото профілю кружечком, або None, якщо фото немає
        path = self.settings.get("avatar")
        if not path or not Path(path).exists():
            return None
        image = Image.open(path).convert("RGB")
        side = min(image.size)
        image = image.crop(((image.width - side) // 2, (image.height - side) // 2,
                            (image.width + side) // 2, (image.height + side) // 2)).resize((size * 3, size * 3), Image.LANCZOS)
        mask = Image.new("L", image.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, image.width - 1, image.height - 1), fill=255)
        image.putalpha(mask)
        return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))

    def _bind_profile(self, widget):
        # Клік по профілю відкриває меню, наведення підсвічує весь рядок
        widget.bind("<Button-1>", self.toggle_account_menu)
        widget.bind("<Enter>", lambda event: self.profile.configure(fg_color=theme.SURFACE_HOVER))
        widget.bind("<Leave>", lambda event: self.profile.configure(fg_color="transparent"))

    def _update_profile(self):
        name = self.full_name()
        # Кружечок щоразу створюємо заново: customtkinter не вміє прибрати з напису картинку,
        # і після "Прибрати фото" старе фото лишалося б поверх літери
        if self.avatar is not None:
            self.avatar.destroy()
        photo = self.avatar_image(30)
        self.avatar_photo = photo
        self.avatar = ctk.CTkLabel(
            self.profile, text="" if photo else (name[:1] or "L").upper(), image=photo, width=30, height=30,
            corner_radius=15, fg_color="transparent" if photo else theme.ACCENT, text_color=theme.ACCENT_TEXT,
            font=self.font(13, "bold"),
        )
        self.avatar.grid(row=0, column=0, padx=(6, 0), pady=6)
        self._bind_profile(self.avatar)
        self.profile_name.configure(text=name or t("profile"))

    def profile_text(self):
        # Що Gaia знає з профілю: ім'я та "про себе" (пошту не передаємо, вона їй не потрібна)
        parts = []
        if self.full_name():
            parts.append(t("profile_for_gaia_name").format(name=self.full_name()))
        if self.settings.get("about").strip():
            parts.append(t("profile_for_gaia_about").format(about=self.settings.get("about").strip()))
        return " ".join(parts)

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
            placeholder=t("prompt_placeholder"),
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
            tools, values=self.style_values(), command=self.style_chosen, **self.menu_style()
        )
        self.style_menu.set(label(self.settings.get("style") if self.settings.get("style") in self.styles() else "Без стилю"))
        self.style_menu.pack(side="left")

        ctk.CTkLabel(tools, image=self.small_icons["frame"], text="").pack(side="left", padx=(10, 0))
        self.size_menu = ctk.CTkOptionMenu(
            tools, values=[label(name) for name in SIZES],
            command=lambda shown: self.settings.set("size", unlabel(shown, SIZES)), **self.menu_style()
        )
        self.size_menu.set(label(self.settings.get("size") if self.settings.get("size") in SIZES else "Квадрат 1:1"))
        self.size_menu.pack(side="left")

        self.image_count_menu = ctk.CTkOptionMenu(
            tools,
            values=["1", "2", "4"],
            **self.menu_style(),
        )
        self.image_count_menu.set("1")
        self.image_count_menu.pack(side="left", padx=(8, 0))

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
            command=self.on_send_button,
        )
        self.send_button.pack(side="right")
        # Модель і рівень міркувань: одна кнопка, яка відкриває віконце з повзунком
        self.brain_popup = None
        self.brain_button = ctk.CTkButton(
            tools, text="", image=self.small_icons["model"], compound="left", width=0, height=30,
            corner_radius=8, font=self.font(13), fg_color="transparent", hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT, text_color_disabled=theme.MUTED, command=self.toggle_brain_popup,
        )
        self.brain_button.pack(side="right", padx=(0, 10))
        self.update_brain_button()

        self.status_label = ctk.CTkLabel(
            self.composer_block, text=t("send_hint"), font=self.font(12), text_color=theme.MUTED, anchor="w"
        )
        self.status_label.grid(row=1, column=0, sticky="w", padx=(14, 0), pady=(6, 0))

    # ---------- Фото від користувача ----------

    def pick_attachment(self):
        # Діалог вибору фото з комп'ютера
        from tkinter import filedialog

        path = filedialog.askopenfilename(
            parent=self,
            title=t("choose_photo"),
            filetypes=[(t("images"), "*.png *.jpg *.jpeg *.webp *.bmp *.gif"), (t("all_files"), "*.*")],
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
            self.set_status(t("open_photo_failed").format(error=shorten(str(error), 100)))
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
        image.thumbnail((UPLOAD_MAX_SIZE, UPLOAD_MAX_SIZE), Image.LANCZOS)

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
        return {"image": path, "prompt": text or t("your_photo"), "model": t("your_photo")}

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
        # Усі заголовки тепер малюються всередині списку
        self.list_title.grid_remove()
        query = self.search_entry.get().strip().lower() if self.search_entry.winfo_ismapped() else ""
        chats = [chat for chat in self.chats.sorted_chats() if chat["messages"]]
        active = [chat for chat in chats if not chat.get("archived")]
        mode = self.list_mode
        other_rows = 0

        if query:
            # Пошук: простий список усіх чатів, крім архіву
            for chat in active:
                if query in chat["title"].lower() or any(
                    query in (message.get("prompt") or message.get("text") or "").lower()
                    or query in message.get("prompt_en", "").lower()
                    for message in chat["messages"]
                ):
                    self._chat_row(chat)
        elif mode and mode[0] == "archive":
            self._list_back(t("archive"))
            for chat in chats:
                if chat.get("archived"):
                    self._chat_row(chat)
        elif mode and mode[0] == "project":
            self._list_back(mode[1])
            for chat in active:
                if chat.get("project") == mode[1]:
                    self._chat_row(chat)
        else:
            pinned = [chat for chat in active if chat.get("pinned")]
            # Чати проєктів видно всередині проєкту, а не в загальному списку
            free = [chat for chat in active if not chat.get("pinned") and not chat.get("project")]
            if pinned:
                self._chat_section(t("pinned"))
                for chat in pinned:
                    self._chat_row(chat)
            projects = sorted({chat["project"] for chat in active if chat.get("project")}, key=str.lower)
            if projects:
                self._chat_section(t("projects"))
                for name in projects:
                    self._project_row(name, sum(1 for chat in active if chat.get("project") == name))
                    other_rows += 1
            for section in sorted({chat["section"] for chat in free if chat.get("section")}, key=str.lower):
                self._chat_section(section)
                for chat in free:
                    if chat.get("section") == section:
                        self._chat_row(chat)
            rest = [chat for chat in free if not chat.get("section")]
            if rest:
                self._chat_section(t("recent"))
                for chat in rest:
                    self._chat_row(chat)
            archived = len(chats) - len(active)
            if archived:
                ctk.CTkButton(
                    self.chat_list, text=f"{t('archive')} ({archived})", anchor="w", height=30, corner_radius=8,
                    font=self.font(12), fg_color="transparent", hover_color=theme.SURFACE_HOVER,
                    text_color=theme.MUTED, command=lambda: self.show_chat_list(("archive",)),
                ).pack(fill="x", pady=(10, 0))
                other_rows += 1

        if not self.chat_buttons and not other_rows:
            if query:
                text = t("nothing_found")
            elif mode:
                text = t("empty_here")
            else:
                text = t("chats_will_appear")
            ctk.CTkLabel(self.chat_list, text=text, font=self.font(12), text_color=theme.MUTED).pack(
                anchor="w", padx=10, pady=6
            )

    def show_chat_list(self, mode):
        # Перемикає список: усі чати (None), один проєкт або архів
        self.list_mode = mode
        self.render_chat_list()

    def _list_back(self, title):
        # Рядок "‹ Назва" угорі списку проєкту чи архіву: повертає до всіх чатів
        ctk.CTkButton(
            self.chat_list, text=f"‹   {title}", anchor="w", height=34, corner_radius=8,
            font=self.font(13, "bold"), fg_color="transparent", hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT, command=lambda: self.show_chat_list(None),
        ).pack(fill="x", pady=(0, 6))

    def _project_row(self, name, count):
        ctk.CTkButton(
            self.chat_list, text=f"{shorten(name, 22)}   {count}", image=self.small_icons["folder"], compound="left",
            anchor="w", height=34, corner_radius=8, font=self.font(13), fg_color="transparent",
            hover_color=theme.SURFACE_HOVER, text_color=theme.TEXT,
            command=lambda: self.show_chat_list(("project", name)),
        ).pack(fill="x", pady=1)

    def _chat_row(self, chat):
        selected = chat["id"] == self.current_chat_id and self.view == "chat"
        unread = bool(chat.get("unread"))
        button = ctk.CTkButton(
            self.chat_list,
            # Непрочитаний чат: крапка перед назвою і жирний шрифт
            text=("•  " if unread else "") + shorten(chat["title"], 24 if unread else 26),
            anchor="w",
            height=34,
            corner_radius=8,
            font=self.font(13, "bold") if unread else self.font(13),
            fg_color=theme.SELECTED if selected else "transparent",
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT,
            command=lambda chat_id=chat["id"]: self.open_chat(chat_id),
        )
        button.pack(fill="x", pady=1)
        button.bind("<Button-3>", lambda event, chat_id=chat["id"]: self._chat_menu(event, chat_id))
        button.chat_id = chat["id"]
        self._add_chat_dots(button)
        self.chat_buttons.append(button)

    def highlight_chat(self):
        # Лише перемикає підсвічування в списку чатів, без повної перебудови списку
        for button in self.chat_buttons:
            self._update_chat_dots(button)

    def _chat_section(self, title):
        ctk.CTkLabel(
            self.chat_list, text=title, font=self.font(12), text_color=theme.MUTED, anchor="w"
        ).pack(fill="x", padx=10, pady=(8, 2))

    def _add_chat_dots(self, button):
        # Кнопка "три крапки" поверх правого краю чату. Видно при наведенні і у відкритого чату.
        dots = ctk.CTkButton(
            self.chat_list,
            text="",
            image=self.dots_icon,
            width=26,
            height=26,
            corner_radius=6,
            fg_color=theme.SURFACE_HOVER,
            hover_color=theme.BORDER,
            text_color=theme.TEXT,
            command=lambda: self._chat_menu(None, button.chat_id, dots),
        )
        button.dots = dots
        button.hovered = False

        def entered(event):
            button.hovered = True
            self._update_chat_dots(button)

        def left(event):
            # Курсор міг просто перейти з чату на крапки: перевіряємо трохи згодом, де він насправді
            def check():
                if not button.winfo_exists():
                    return
                x, y = self.winfo_pointerxy()
                under = str(self.winfo_containing(x, y) or "")
                button.hovered = under.startswith((str(button), str(dots)))
                self._update_chat_dots(button)

            self.after(30, check)

        for widget in (button, dots):
            widget.bind("<Enter>", entered, add="+")
            widget.bind("<Leave>", left, add="+")
        self._update_chat_dots(button)

    def _update_chat_dots(self, button):
        dots = getattr(button, "dots", None)
        if dots is None or not dots.winfo_exists():
            return
        selected = button.chat_id == self.current_chat_id and self.view == "chat"
        # Рядок лишається підсвіченим, навіть коли курсор перейшов з нього на крапки.
        # Фон крапок такий самий, як у рядка під ними, щоб вони не виглядали латкою.
        if button.hovered:
            color = theme.SURFACE_HOVER
        else:
            color = theme.SELECTED if selected else "transparent"
        if button.cget("fg_color") != color:
            button.configure(fg_color=color)
        if button.hovered or selected:
            dots.configure(fg_color=color)
            dots.place(in_=button, relx=1.0, x=-4, rely=0.5, anchor="e")
            dots.lift()
        else:
            dots.place_forget()

    def _chat_menu(self, event, chat_id, anchor=None):
        # Меню чату: з трьох крапок (anchor) або з правої кнопки миші (event)
        if self.generating:
            return
        chat = self.chats.get(chat_id)
        if chat is None:
            return
        style = dict(
            tearoff=0, bd=0, relief="flat", font=(theme.FONT_FAMILY, 10),
            bg=themed(theme.SURFACE), fg=themed(theme.TEXT),
            activebackground=themed(theme.SURFACE_HOVER), activeforeground=themed(theme.TEXT),
            selectcolor=themed(theme.TEXT),
        )
        menu = tk.Menu(self, **style)

        def item(label, command, key=None, **extra):
            # key: літера справа в меню. Коли меню відкрите, натискання цієї літери вибирає пункт.
            options = {"label": label, "command": command, **extra}
            if key:
                options["accelerator"] = key
                if key.lower() in label.lower():
                    options["underline"] = label.lower().index(key.lower())
            menu.add_command(**options)

        def later(func, *args):
            # Дію запускаємо, коли меню вже закрилось
            return lambda: self.after(1, func, *args)

        archived = bool(chat.get("archived"))
        item(t("open_new_window"), later(self.open_chat_window, chat_id))
        if chat.get("unread"):
            item(t("mark_read"), later(self.set_chat_flag, chat_id, "unread", False), t("acc_unread"))
        else:
            item(t("mark_unread"), later(self.set_chat_flag, chat_id, "unread", True), t("acc_unread"))
        menu.add_separator()
        if chat.get("pinned"):
            item(t("unpin"), later(self.set_chat_flag, chat_id, "pinned", False), t("acc_pin"))
        else:
            item(t("pin"), later(self.set_chat_flag, chat_id, "pinned", True), t("acc_pin"))
        item(t("rename"), later(self.rename_chat, chat_id), t("acc_rename"))
        for key, label, new_label, remove_label in (
            ("project", t("add_to_project"), t("new_project_dots"), t("remove_from_project")),
            ("section", t("move_to_section"), t("new_section_dots"), t("remove_from_section")),
        ):
            submenu = tk.Menu(menu, **style)
            current = chat.get(key, "")
            for name in self.chats.names(key):
                # Позначка біля проєкту чи розділу, де чат уже лежить
                mark = tk.BooleanVar(value=name == current)
                submenu.add_checkbutton(label=name, variable=mark, command=later(self.set_chat_flag, chat_id, key, name))
                submenu.marks = getattr(submenu, "marks", []) + [mark]
            if self.chats.names(key):
                submenu.add_separator()
            submenu.add_command(label=new_label, command=later(self.new_chat_group, chat_id, key))
            if current:
                submenu.add_command(label=remove_label, command=later(self.set_chat_flag, chat_id, key, ""))
            menu.add_cascade(label=label, menu=submenu)
        menu.add_separator()
        if archived:
            item(t("unarchive"), later(self.set_chat_flag, chat_id, "archived", False), t("acc_archive"))
        else:
            item(t("archive_action"), later(self.set_chat_flag, chat_id, "archived", True), t("acc_archive"))
        item(t("delete"), later(self.delete_chat, chat_id), t("acc_delete"),
             foreground=themed(theme.DANGER), activeforeground=themed(theme.DANGER))
        if anchor is not None and anchor.winfo_ismapped():
            # Під трьома крапками
            x, y = anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height() + 2
        elif event is not None:
            x, y = event.x_root, event.y_root
        else:
            x, y = self.winfo_pointerxy()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def pin_chat(self, chat_id, pinned):
        self.set_chat_flag(chat_id, "pinned", pinned)

    def set_chat_flag(self, chat_id, key, value):
        # Закріпити, позначити непрочитаним, архівувати, додати до проєкту чи розділу
        self.chats.set_field(chat_id, key, value)
        self.render_chat_list()

    def new_chat_group(self, chat_id, key):
        # Новий проєкт або розділ: питаємо назву і одразу кладемо туди чат
        dialog = ctk.CTkInputDialog(
            title=t("new_project") if key == "project" else t("new_section"),
            text=t("project_name") if key == "project" else t("section_name"),
            fg_color=theme.BG, button_fg_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
            button_text_color=theme.ACCENT_TEXT, entry_fg_color=theme.SURFACE, entry_border_color=theme.BORDER,
            entry_text_color=theme.TEXT, text_color=theme.TEXT,
        )
        name = " ".join((dialog.get_input() or "").split())[:40]
        if name:
            self.set_chat_flag(chat_id, key, name)

    def open_chat_window(self, chat_id):
        from src.frontend.chat_window import ChatWindow

        chat = self.chats.get(chat_id)
        if chat is not None:
            ChatWindow(self, chat)

    def rename_chat(self, chat_id):
        # Назва чату на місці стає полем вводу: Enter зберігає, Esc скасовує
        button = next((b for b in self.chat_buttons if b.chat_id == chat_id), None)
        chat = self.chats.get(chat_id)
        if button is None or chat is None:
            return
        button.dots.place_forget()
        entry = ctk.CTkEntry(
            self.chat_list, height=34, corner_radius=8, border_width=1, border_color=theme.ACCENT,
            fg_color=theme.SURFACE, text_color=theme.TEXT, font=self.font(13),
        )
        entry.insert(0, chat["title"])
        entry.place(in_=button, relx=0, rely=0, relwidth=1, relheight=1)
        entry.focus_set()
        entry.select_range(0, "end")
        done = False

        def finish(save):
            nonlocal done
            if done:
                return
            done = True
            if save:
                self.chats.rename(chat_id, entry.get())
                if chat_id == self.current_chat_id and self.view == "chat":
                    self.header_title.configure(text=shorten(self.chats.get(chat_id)["title"], 70))
            entry.destroy()
            self.render_chat_list()

        entry.bind("<Return>", lambda event: finish(True))
        entry.bind("<Escape>", lambda event: finish(False))
        entry.bind("<FocusOut>", lambda event: finish(True))

    def open_chat(self, chat_id):
        if self.generating:
            return
        previous = self.chats.get(self.current_chat_id)
        # Порожній чат, з якого пішли, нікому не потрібен, тому прибираємо його
        if previous and previous["id"] != chat_id and not previous["messages"]:
            self.chats.delete_chat(previous["id"])
        self.current_chat_id = chat_id
        known = any(button.chat_id == chat_id for button in self.chat_buttons)
        chat = self.chats.get(chat_id)
        was_unread = bool(chat and chat.get("unread"))
        if was_unread:
            # Відкрили чат, отже прочитали: прибираємо крапку і жирний шрифт
            self.chats.set_field(chat_id, "unread", False)
        self.render_chat()
        if known and previous and previous["messages"] and not was_unread:
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
            t("delete_chat"),
            t("delete_chat_question").format(title=chat["title"]),
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
        ctk.CTkLabel(head, text=t("recent_images"), font=self.font(13), text_color=theme.MUTED).pack(side="left", padx=(4, 0))
        ctk.CTkButton(
            head,
            text=t("all"),
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
        self.header_title.configure(text=f"{t('gallery')}  ·  {len(items)}")
        self.delete_button.grid_remove()
        self.render_chat_list()

        for widget in self.gallery.winfo_children():
            widget.destroy()
        if not items:
            ctk.CTkLabel(
                self.gallery, text=t("images_will_appear"), font=self.font(14), text_color=theme.MUTED
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
                t("translation_line").format(
                    source=t(LANGUAGE_NAMES[message["language"]]) if message.get("language") in LANGUAGE_NAMES else "",
                    text=message["prompt_en"],
                ),
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
        label = ctk.CTkLabel(row, text=t("thinking"), font=self.font(14), text_color=theme.MUTED)
        label.pack(side="left", pady=(1, 0))
        self.thinking = {"row": row, "label": label, "started": time.time()}
        self._tick_thinking()

    def _tick_thinking(self):
        # Перша відповідь чекає, поки модель завантажиться в пам'ять, тож пояснюємо затримку
        if self.thinking is None:
            return
        seconds = int(time.time() - self.thinking["started"])
        if seconds >= 12:
            self.thinking["label"].configure(text=t("waking_up").format(seconds=seconds))
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
                card, text=t("image_missing"), width=IMAGE_SIZE, height=120,
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
                card, t({"recolor": "review_recolored"}.get(message.get("fix"), "review_kept_first"
                        if message.get("kept_first") else "review_redrawn")).format(problem=message["review"]),
                self.font(12),
                max_width=IMAGE_SIZE - 10, text_color=theme.MUTED, bg=theme.SURFACE,
            ).pack(anchor="w", padx=14, pady=(2, 2))

        details = [self.model_title(message["model"])]
        if message.get("upscaled"):
            details.append(t("upscaled").format(scale=message["upscaled"]))
        if message.get("checked") and not message.get("review"):
            details.append(t("checked"))
        if message.get("add"):
            details.append(t("added_to").format(place=message.get("place") or "") if message.get("target_found") else t("photo_edit"))
        elif message.get("recolored"):
            details.append(t("recolored_target").format(target=message["target"]) if message.get("target") else t("recolored"))
        elif message.get("target") and message.get("target_found"):
            details.append(t("removed_target" if message.get("remove") else "changed_target").format(target=message["target"]))
        elif message.get("target"):
            details.append(t("target_not_found").format(target=message["target"]))
        elif message.get("source"):
            details.append(t("photo_edit"))
        if message.get("style") and message["style"] != "Без стилю":
            details.append(label(message["style"]))
        if message["steps"]:
            details.append(t("steps_count").format(steps=message["steps"]))
        details += [t("seconds_short").format(seconds=message.get("seconds", 0)), datetime.fromisoformat(message["created"]).strftime("%H:%M")]
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(fill="x", padx=(14, 8), pady=(2, 0))
        ctk.CTkLabel(
            info, text="  ·  ".join(details), font=self.font(12), text_color=theme.MUTED, anchor="w"
        ).pack(side="left", fill="x", expand=True)
        if path.exists():
            # Збільшити в 2 рази: у чат додається збільшена копія
            ctk.CTkButton(
                info, text="×2", image=self.small_icons["expand"], compound="left", width=0, height=26,
                corner_radius=8, font=self.font(12), fg_color="transparent", hover_color=theme.SURFACE_HOVER,
                text_color=theme.TEXT, command=lambda m=message: self.upscale_image(m),
            ).pack(side="left", padx=(0, 4))
        if DEVELOPER and message.get("kind") == "image" and path.exists():
            # Оцінка: з неї Linum робить урок і вчиться (лише в режимі розробника)
            buttons = {}
            for name, rated in (("thumb_up", 1), ("thumb_down", -1)):
                buttons[name] = ctk.CTkButton(
                    info, text="", image=self.rating_icons[(name, message.get("rating") == rated)],
                    width=28, height=26, corner_radius=8, fg_color="transparent", hover_color=theme.SURFACE_HOVER,
                )
            for name, button in buttons.items():
                button.configure(command=lambda liked=name == "thumb_up": self.rate_image(message, liked, buttons))
                button.pack(side="left")

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=8, pady=(2, 8))
        self.small_button(actions, t("more_variant"), self.small_icons["refresh"], lambda m=message: self.variation(m)).pack(side="left")
        self.small_button(actions, t("copy_prompt"), self.small_icons["copy"], lambda m=message: self.copy_prompt(m)).pack(side="left")
        if path.exists():
            self.small_button(actions, t("open"), self.small_icons["open"], lambda p=path: open_path(p)).pack(side="left")
            self.small_button(actions, t("in_folder"), self.small_icons["folder"], lambda p=path: self.show_in_folder(p)).pack(side="left")
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
        title = ctk.CTkLabel(inner, text=t("preparing"), font=self.font(15), text_color=theme.TEXT)
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
        show_in_folder(path)

    def copy_prompt(self, message):
        self.clipboard_clear()
        self.clipboard_append(message["prompt"])
        self.set_status(t("prompt_copied"))

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
            vary=True,
            add=bool(message.get("add")),
            place=message.get("place", ""),
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
            return
        if not self.model_available(name):
            self.set_status(t("model_missing").format(name=self.model_title(name), path=MODELS[name]["path"]))
            return
        self.selected_model = name
        self.update_brain_button()
        self.settings.set("model", name)
        if self.pipe is not None and name != self.loaded_model:
            self._release_artist()

    def _cache_artist(self, name, pipe):
        self.pipe = pipe
        self.loaded_model = name

    def _release_artist(self):
        if self.artist_idle_timer is not None:
            self.after_cancel(self.artist_idle_timer)
            self.artist_idle_timer = None
        if self.pipe is None:
            return

        from src.ai.generator import clear_edit_pipeline

        self.pipe = None
        self.loaded_model = None
        clear_edit_pipeline()
        gc.collect()
        free_gpu_memory()

    def _expire_artist(self):
        self.artist_idle_timer = None
        if self.artist_running:
            return
        if self.busy or self.learning:
            self.artist_idle_timer = self.after(1_000, self._expire_artist)
            return
        self._release_artist()

    def _run_ai(self, work):
        def run():
            with self.ai_lock:
                work()

        threading.Thread(target=run, daemon=True).start()

    # ---------- Генерація ----------

    def _set_busy(self, busy, generating=False):
        self.busy = busy
        self.generating = busy and generating
        if busy:
            self.job_id += 1
            self.cancel_requested = False
        state = "disabled" if busy else "normal"
        if busy:
            # Поки Linum думає чи малює, кнопка надсилання стає кнопкою "Стоп"
            self.send_button.configure(text="■", state="normal")
        else:
            self.send_button.configure(text="↑", state="normal")
        for widget in (self.brain_button, self.style_menu, self.size_menu, self.image_count_menu):
            widget.configure(state=state)
        if busy and self.brain_popup is not None:
            self.brain_popup.close()
        # Переходити між екранами не можна лише під час створення картинки
        navigation = "disabled" if self.generating else "normal"
        for widget in (self.nav_buttons["new"], self.nav_buttons["gallery"], self.delete_button, *self.chat_buttons):
            widget.configure(state=navigation)
        if not busy:
            if self.artist_running:
                self.artist_running = False
                if self.artist_idle_timer is not None:
                    self.after_cancel(self.artist_idle_timer)
                self.artist_idle_timer = self.after(300_000, self._expire_artist) if self.pipe else None
            # Коли Linum вільний, Вчитель обробляє чергу уроків
            self.after(300, self._run_lessons)

    # ---------- Свої стилі ----------

    def custom_styles(self):
        # Стилі, які створив користувач: {назва: {"prompt": англійською для художника, "description": як написав}}
        return dict(self.settings.get("custom_styles") or {})

    def styles(self):
        # Усі стилі для меню і малювання: вбудовані з config.py і свої
        return {**STYLES, **{name: style["prompt"] for name, style in self.custom_styles().items()}}

    def style_values(self):
        # Пункти меню стилю: назви на екрані (вбудовані перекладені) і наприкінці "+ Свій стиль..."
        return [label(name) for name in self.styles()] + [t("add_style_item")]

    def style_chosen(self, shown):
        if shown == t("add_style_item"):
            # Це не стиль, а кнопка: повертаємо в меню попередній стиль і відкриваємо віконце
            current = self.settings.get("style")
            self.style_menu.set(label(current if current in self.styles() else "Без стилю"))
            self.open_style_dialog()
            return
        self.settings.set("style", unlabel(shown, self.styles()))

    def open_style_dialog(self, refresh_settings=False):
        from src.frontend.style_dialog import StyleDialog

        def saved(name, prompt, description):
            styles = self.custom_styles()
            styles[name] = {"prompt": prompt, "description": description}
            self.settings.set("custom_styles", styles)
            # Новий стиль одразу вибраний
            self.settings.set("style", name)
            self.refresh_style_menu()
            self.set_status(t("style_saved").format(name=name))
            if refresh_settings and self.view == "settings":
                self.open_settings("generation")

        StyleDialog(self, saved)

    def delete_style(self, name):
        styles = self.custom_styles()
        styles.pop(name, None)
        self.settings.set("custom_styles", styles)
        if self.settings.get("style") == name:
            self.settings.set("style", "Без стилю")
        self.refresh_style_menu()
        self.open_settings("generation")

    def refresh_style_menu(self):
        current = self.settings.get("style")
        self.style_menu.configure(values=self.style_values())
        self.style_menu.set(label(current if current in self.styles() else "Без стилю"))

    # ---------- Пам'ять про користувача ----------

    def remember(self, text):
        # Записує факт про вас, якщо такого (чи дуже схожого) ще немає в пам'яті
        from src.ai import lessons, memory

        try:
            if any(lessons.similarity(text, fact["text"]) >= 0.6 for fact in memory.load()):
                return
            memory.add(text)
        except Exception:
            return
        self.set_status(t("remembered").format(text=shorten(text, 140)))

    # ---------- Збільшення фото ----------

    def upscale_image(self, message, scale=2):
        # Збільшує картинку в scale разів і додає в чат збільшену копію
        if self.busy:
            return
        path = Path(message["image"])
        with Image.open(path) as picture:
            width, height = picture.size
        if max(width, height) * scale > 6144:
            self.set_status(t("upscale_too_big"))
            return
        chat_id = self.current_chat_id
        started = time.time()
        self._set_busy(True, generating=True)
        self._add_pending_card(width * scale, height * scale)
        self.pending["title"].configure(text=t("upscaling").format(scale=scale))
        self._scroll_to_bottom()
        job = self.job_id

        def work():
            try:
                from src.ai.generator import save_image
                from src.ai.upscaler import upscale

                if self.brain_ready:
                    from src.ai import brain

                    brain.unload()
                with Image.open(path) as picture:
                    picture = picture.convert("RGB")
                    try:
                        bigger = upscale(picture, scale)
                    except torch_out_of_memory():
                        # Відеопам'ять могла зайняти Gaia: звільняємо її і пробуємо ще раз
                        from src.ai import brain

                        brain.unload()
                        free_gpu_memory()
                        bigger = upscale(picture, scale)
                if self.cancel_requested:
                    raise Cancelled()
                new_path = save_image(bigger)
            except Cancelled:
                self.after(0, self._deliver, job, self._on_stopped)
                return
            except Exception as error:
                self.after(0, self._deliver, job, self._on_generate_failed, error)
                return
            copy = {key: value for key, value in message.items()
                    if key not in ("rating", "review", "checked", "first_image", "second_image", "kept_first")}
            copy.update({
                "image": str(new_path),
                "upscaled": scale * message.get("upscaled", 1),
                "upscaled_from": str(path),
                "steps": 0,
                "seconds": round(time.time() - started),
                "created": datetime.now().isoformat(timespec="seconds"),
            })
            self.after(0, self._deliver, job, self._on_generated, chat_id, copy)

        self._run_ai(work)

    # ---------- Самонавчання ----------

    def rate_image(self, message, liked, buttons):
        # Оцінка картинки. Повторне натискання на ту саму оцінку знімає її.
        value = 1 if liked else -1
        if message.get("rating") == value:
            message.pop("rating")
        else:
            message["rating"] = value
            self.queue_lesson(message, liked)
        self.chats.save()
        for (name, button), rated in zip(buttons.items(), (1, -1)):
            button.configure(image=self.rating_icons[(name, message.get("rating") == rated)])
        self.set_status(t("thanks_lesson") if message.get("rating") else t("rating_removed"))

    def queue_lesson(self, message, liked):
        # liked: True/False - оцінка користувача; None - помилку знайшов Критик під час перевірки.
        # Навчати Linum може лише розробник: у звичайних користувачів уроки не записуються.
        if not DEVELOPER:
            return
        if not Path(message.get("image", "")).exists():
            return
        self.lesson_queue.append((message, liked))
        self._run_lessons()

    def _run_lessons(self):
        # Уроки робимо по одному і лише коли Linum нічого не малює: інакше Gaia і художник
        # не вмістяться у відеопам'ять разом
        if self.learning or self.busy or not self.brain_ready or not self.lesson_queue:
            return
        message, liked = self.lesson_queue.pop(0)
        self.learning = True
        settings = self.reasoning()

        def work():
            lesson = None
            try:
                from src.ai import brain, lessons

                free_gpu_memory()
                text = brain.learn(message, liked, settings)
                if text and not lessons.is_known(text):
                    lesson = lessons.add(text, "review" if liked is None else "rating")
            except Exception:
                lesson = None
            self.after(0, self._on_lesson, lesson)

        self._run_ai(work)

    def _on_lesson(self, lesson):
        self.learning = False
        if lesson is not None and not self.busy:
            self.set_status(t("lesson_learned").format(text=shorten(lesson["text"], 140)))
        self._run_lessons()

    def toggle_training(self):
        if not DEVELOPER:
            return
        if self.training:
            # Зупиняємо між кроками: поточний крок агентів доробиться
            self.training_stop = True
            self._set_training_status(t("stopping"))
            return
        if self.busy or self.selected_model is None or not self.brain_ready:
            self._set_training_status(t("training_not_ready"))
            return
        self.training = True
        self.training_stop = False
        self.artist_running = True
        self._set_busy(True)
        if self.training_button is not None and self.training_button.winfo_exists():
            self.training_button.configure(text=t("stop"))
        pipe, model, settings = self.pipe, self.selected_model, self.reasoning()

        def log(text):
            self.after(0, self._set_training_status, text)

        def work():
            nonlocal pipe
            try:
                from src.ai import brain, trainer
                from src.ai.generator import load_model

                if pipe is None and not self.training_stop:
                    brain.unload()
                    pipe = load_model(model)
                    self.after(0, self._cache_artist, model, pipe)
            except Exception as error:
                self.after(0, self._on_training_done, 0, 0, error)
                return

            rounds = learned = 0
            while not self.training_stop:
                try:
                    result = trainer.run_round(
                        pipe, model, settings, self.training_recent, log,
                        stop=lambda: self.training_stop,
                    )
                except trainer.Stopped:
                    break
                except Exception as error:
                    log(t("round_error").format(error=shorten(str(error), 160)))
                    break
                rounds += 1
                trainer.record_round(result)
                self.after(0, self._refresh_experience)
                if result.get("lesson"):
                    learned += 1
                    log(t("round_lesson").format(round=rounds, text=result["lesson"]["text"]))
                elif result.get("request") and not result.get("problem"):
                    log(t("round_ok").format(round=rounds, request=result["request"]))
                else:
                    log(t("round_nothing").format(round=rounds))
            self.after(0, self._on_training_done, rounds, learned)

        self._run_ai(work)

    def _refresh_experience(self):
        # Сторінка "Досвід" показує свіжі уроки і раунди одразу, без перезаходу
        if self.view == "settings" and getattr(self, "settings_section", None) == "experience":
            self.open_settings("experience")

    def _set_training_status(self, text):
        self.training_status = text
        self.set_status(shorten(" ".join(text.split()), 150))
        if self.training_label is not None and self.training_label.winfo_exists():
            self.training_label.configure(text=text)

    def _on_training_done(self, rounds, learned, error=None):
        self.training = False
        self._set_busy(False)
        if error is None:
            self._set_training_status(t("training_done").format(rounds=rounds, learned=learned))
        else:
            self._set_training_status(t("round_error").format(error=shorten(str(error), 160)))
        if self.view == "settings":
            # Оновлюємо сторінку, щоб з'явились нові уроки
            self.open_settings("experience")

    def on_send_button(self):
        # Одна кнопка на дві дії: коли Linum вільний, надсилає, коли зайнятий, зупиняє
        if self.busy:
            self.stop_current()
        else:
            self.on_generate()

    def stop_current(self):
        if self.training:
            self.toggle_training()
            return
        if not self.busy:
            return
        if self.pending is None:
            # Gaia ще думає: зупиняємо одразу, а її запізнілу відповідь відкинемо
            self.job_id += 1
            self._on_stopped()
        else:
            # Художник малює: він зупиниться на найближчому кроці
            self.cancel_requested = True
            self.set_status(t("stopping"))

    def _deliver(self, job, handler, *args):
        # Передає результат фонової справи, лише якщо її не зупинили
        if job == self.job_id:
            handler(*args)

    def _on_stopped(self):
        self._remove_thinking()
        if self.pending is not None:
            self.pending["row"].destroy()
            self.pending = None
        self._set_busy(False)
        self.set_status(t("stopped"))
        self.prompt_entry.focus_set()

    def on_generate(self, event=None):
        if self.busy:
            return
        prompt = self.prompt_entry.get().strip()
        if not prompt and self.attachment is None:
            self.set_status(t("write_first"))
            return
        if self.brain_ready is None:
            self._check_brain(prompt)
        else:
            self._submit_prompt(prompt)

    def _submit_prompt(self, prompt):
        if self.attachment is not None and not self.brain_ready:
            self.set_status(t("photo_needs_gaia"))
            return
        started = self.send_message(prompt) if self.brain_ready else self.start_generation(prompt)
        if started:
            self.prompt_entry.clear()
            self.clear_attachment()

    # ---------- Мозок ----------

    def set_reasoning(self, value):
        # Зміна рівня з поля вводу або з налаштувань: запам'ятовуємо і показуємо однаково в обох місцях
        self.settings.set("reasoning", value)
        self.update_brain_button()
        self.brain_ready = None

    def model_title(self, name):
        # Назва моделі з номером для екрана: "Gaia" стає "Gaia 3.7"
        version = MODELS.get(name, {}).get("version")
        return f"{name} {version}" if version else name

    def update_brain_button(self):
        # Текст кнопки в полі вводу: художня модель і рівень міркувань
        level = self.settings.get("reasoning")
        level = level if level in REASONING else DEFAULT_REASONING
        self.brain_button.configure(text=f"{self.model_title(self.selected_model or DEFAULT_MODEL)}  ·  {label(level)}")

    def toggle_brain_popup(self):
        from src.frontend.brain_popup import BrainPopup

        if self.brain_popup is not None:
            self.brain_popup.close()
        elif not self.busy:
            self.brain_popup = BrainPopup(self, self.brain_button)

    def reasoning(self):
        # Налаштування вибраного рівня міркувань: {"model", "think", "check"}
        from src.ai import brain

        return brain.level(self.settings.get("reasoning"))

    def _check_brain(self, prompt):
        model = self.reasoning()["model"]
        self._set_busy(True, generating=True)
        self.set_status(t("linum_thinking"))
        job = self.job_id

        def work():
            if job != self.job_id:
                return
            try:
                from src.ai import brain

                ready = brain.is_available(model)
            except Exception:
                ready = False
            self.after(0, self._deliver, job, self._on_brain_checked, model, ready, prompt)

        self._run_ai(work)

    def _on_brain_checked(self, model, ready, prompt):
        self._set_busy(False)
        if model != self.reasoning()["model"]:
            self._check_brain(prompt)
            return
        self.brain_ready = ready
        if not ready and self.selected_model is None:
            self.set_status(t("brain_unavailable"))
            return
        self._submit_prompt(prompt)

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
        job = self.job_id
        # Мозок відповідає від імені обраної моделі (Cygnus 2.0, Fornax 1.0...)
        model_name = self.model_title(self.selected_model or DEFAULT_MODEL)
        profile = self.profile_text()
        self.set_status(t("linum_reasoning") if settings["think"] else t("linum_thinking"))
        history_messages = list(chat["messages"])

        def work():
            if job != self.job_id:
                return
            try:
                from src.ai import brain

                # Художник міг лишити зайняту відеопам'ять. Віддаємо її, щоб Gaia завантажилась.
                free_gpu_memory()
                decision = brain.decide(brain.history_from_chat(history_messages), settings, model_name, profile)
            except Exception as error:
                self.after(0, self._deliver, job, self._on_brain_failed, chat_id, text, error)
                return
            self.after(0, self._deliver, job, self._on_decided, chat_id, text, decision)

        self._run_ai(work)

    def _on_brain_failed(self, chat_id, text, error):
        # Помилку показуємо прямо в чаті, з кнопкою, щоб спитати ще раз
        self._remove_thinking()
        self._set_busy(False)
        self.set_status()
        message = str(error)
        if "out of memory" in message.lower() or "terminated" in message.lower():
            reason = t("reason_memory")
        elif "connect" in message.lower() or "refused" in message.lower():
            reason = t("reason_ollama")
        else:
            reason = shorten(message, 120)
        row = self._assistant_row()
        ctk.CTkLabel(
            row, text=t("gaia_failed").format(reason=reason), font=self.font(14), text_color=theme.DANGER,
        ).pack(side="left")

        def retry():
            if self.busy:
                return
            row.destroy()
            self._ask_brain(chat_id, text)

        self.small_button(row, t("retry"), self.small_icons["refresh"], retry).pack(side="left", padx=(10, 0))
        self._scroll_to_bottom()

    def _on_decided(self, chat_id, text, decision):
        self._remove_thinking()
        if decision["reply"]:
            self.chats.add_message(chat_id, {"kind": "assistant", "text": decision["reply"], "created": self.now()})
            fade_in([self._add_assistant_text(decision["reply"])])()
            self._scroll_to_bottom()
        self._set_busy(False)
        self.set_status()
        if decision.get("remember"):
            self.remember(decision["remember"])

        if decision["action"] == "chat":
            self.prompt_entry.focus_set()
            return

        source = None
        if decision["action"] == "edit":
            source = self.last_image(chat_id)
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
            add=decision["add"] if source else False,
            place=decision["place"] if source else "",
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
                         targets=None, where="", remove=False, colors=None, box=None, vary=False, add=False, place=""):
        # source: шлях до фото, яке треба змінити. Без нього малюється нове зображення.
        # targets: англійські назви предмета, який треба знайти на фото і змінити лише його.
        # remove: прибрати цей предмет (місце заливається фоном і домальовується).
        # colors: лише перефарбувати предмет, без художника: [{"from": "#...", "to": "#..."}].
        # box: рамка предмета (x1, y1, x2, y2), якщо вже відома (наприклад, для "Ще варіант").
        if self.busy:
            return False
        if self.selected_model is None:
            self.set_status(t("no_model_files"))
            return False
        chat = self.chats.get(self.current_chat_id)
        if chat is None:
            chat = self.chats.create_chat()
            self.current_chat_id = chat["id"]

        style = style or unlabel(self.style_menu.get(), self.styles())
        size = size or unlabel(self.size_menu.get(), SIZES)
        width, height = SIZES.get(size, SIZES["Квадрат 1:1"])
        image_count = 1
        if source is None and not vary:
            image_count = int(self.image_count_menu.get())
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

        model = self.selected_model
        steps = MODELS[model]["steps"]
        chat_id = chat["id"]
        pipe = self.pipe
        started = time.time()
        settings = self.reasoning()
        style_text = self.styles().get(style, "")
        self.artist_running = True
        self._set_busy(True, generating=True)
        # Номер цієї справи беремо ПІСЛЯ _set_busy: він там збільшується
        job = self.job_id
        self.set_status(t("creating_with_model").format(model=self.model_title(model)))

        def on_step(step, total):
            if self.cancel_requested:
                raise Cancelled()
            self.after(0, self._update_progress, step, total)

        def check_cancel():
            # Між етапами (пошук, малювання, перевірка) теж дивимося, чи не натиснули "Стоп"
            if self.cancel_requested:
                raise Cancelled()

        def work():
            nonlocal english, language, steps, box, seed, colors, pipe
            review = None
            first_image = None
            # Як Критик виправив помилку: "recolor" або "redraw"; і другий варіант, якщо лишили перший
            fixed_by = None
            second_image = None
            first_prompt = None
            try:
                from src.ai.generator import edit_image, generate_image, load_model, save_image
                from src.ai.translator import to_english

                if unload_brain:
                    from src.ai import brain

                    if source is not None and targets and box is None:
                        # Поки Gaia ще в пам'яті, просимо її показати рамкою, де предмет
                        self.after(0, self._set_pending_title, t("searching_for").format(target=targets[0]))
                        box = brain.locate(source, targets[0], where, model=settings["model"])
                    elif source is not None and add and box is None:
                        # Додати предмет: Gaia показує рамкою місце, де він має з'явитися
                        self.after(0, self._set_pending_title, t("looking_for_place").format(place=place or "..."))
                        box = brain.locate(source, f"area {place} where a new object can be placed", where,
                                           model=settings["model"])
                    # Мозок і художник разом не вміщаються в пам'ять, тому мозок на час малювання вивантажуємо
                    brain.unload()
                elif self.brain_ready:
                    from src.ai import brain

                    brain.unload()
                check_cancel()
                if english is None:
                    if translate:
                        english, language = to_english(prompt)
                    else:
                        english, language = prompt, "en"
                self.after(0, self._on_translated, english, language)
                full_prompt = english
                if style_text:
                    full_prompt = f"{english}, {style_text}"
                negative = NEGATIVE_PROMPT if quality_boost else None
                mask = None
                found = None
                edit_strength = strength
                if source is not None and targets:
                    # Шукаємо предмет на фото, щоб перемалювати лише його
                    self.after(0, self._set_pending_title, t("searching_for").format(target=targets[0]))
                    from src.ai.segmenter import find_mask

                    mask, found = find_mask(source, targets, where=where, remove=remove, box=box)
                    if mask is not None and remove:
                        # Запобіжник: "прибрати" не може стерти третину фото. Найімовірніше,
                        # шукач сплутав предмет з головним об'єктом, тож краще нічого не прибирати.
                        area = sum(1 for value in mask.getdata() if value) / (mask.width * mask.height)
                        if area > 0.33:
                            mask, found = None, None
                    if mask is not None:
                        self.after(0, self._set_pending_title, t("removing") if remove else t("editing_image"))
                        if remove:
                            # Прибираємо: художник не повинен намалювати цей предмет знову
                            negative = ", ".join(targets) + ", " + (negative or "")
                            edit_strength = 0.6
                        else:
                            # Зміна одного предмета потребує сильнішого перемальовування
                            edit_strength = max(strength or 0.55, 0.7)
                if source is not None and add and box is not None:
                    # Додаємо предмет: художник малює лише в рамці, яку показала Gaia.
                    # Маска овальна і з м'яким краєм, щоб новий предмет не виглядав вклеєним прямокутником.
                    from PIL import ImageFilter

                    with Image.open(source) as original:
                        mask = Image.new("L", original.size, 0)
                    ImageDraw.Draw(mask).ellipse(box, fill=255)
                    mask = mask.filter(ImageFilter.GaussianBlur(4)).point(lambda value: 255 if value > 100 else 0)
                    self.after(0, self._set_pending_title, t("adding"))
                    # Новий предмет потребує майже повного перемальовування місця
                    edit_strength = 0.9
                def draw(text, seed):
                    nonlocal pipe
                    # Малює нове зображення або змінює фото. Повертає (шлях, кроки).
                    check_cancel()
                    if pipe is None:
                        self.after(0, self._set_pending_title, t("loading_model").format(name=self.model_title(model)))
                        pipe = load_model(model)
                        self.after(0, self._deliver, job, self._cache_artist, model, pipe)
                        self.after(0, self._on_translated, english, language)
                        check_cancel()
                    if source is None:
                        return generate_image(pipe, text, model, on_step, negative, width, height, seed), steps
                    return edit_image(
                        pipe, source, text, mask=mask, strength=edit_strength, model_name=model,
                        on_step=on_step, negative_prompt=negative, seed=seed, fill=remove and mask is not None,
                    )

                recolored = bool(colors) and source is not None and (mask is not None or not targets)
                if recolored:
                    # Лише колір: міняємо його точно по пікселях, художник не потрібен
                    from src.ai.recolor import recolor, vary_color

                    if vary:
                        # "Ще варіант": кожен новий колір трохи інший відтінок (залежить від seed)
                        colors = [{**change, "to": vary_color(change["to"], seed + index)}
                                  for index, change in enumerate(colors)]
                    self.after(0, self._set_pending_title, t("recoloring"))
                    with Image.open(source) as original:
                        whole = Image.new("L", original.size, 255)
                        path = save_image(recolor(original, mask if mask is not None else whole, colors, exact=vary))
                    steps = 0
                else:
                    path, steps = draw(full_prompt, seed)

                check_cancel()
                if settings["check"] and unload_brain and not recolored:
                    # Критик дивиться на готову картинку. Якщо вийшло не те, виправляє один раз:
                    # помилку лише в кольорах перефарбовує, а решту перемальовує і потім
                    # порівнює два варіанти, щоб показати кращий. Художника спершу прибираємо з відеопам'яті.
                    from src.ai import brain

                    free_gpu_memory()
                    self.after(0, self._set_pending_title, t("checking_result"))
                    verdict = brain.review(path, prompt, english, settings)
                    check_cancel()
                    if verdict is not None and not verdict["ok"]:
                        review = verdict["problem"]
                        first_image = path
                        first_prompt = english
                        if verdict["fix"] == "recolor":
                            # Кольори: точно і за секунди, сама картинка лишається та сама
                            from src.ai.recolor import recolor
                            from src.ai.segmenter import find_mask

                            self.after(0, self._set_pending_title, t("recoloring"))
                            fix_box = brain.locate(path, verdict["targets"][0], "", model=settings["model"])
                            brain.unload()
                            fix_mask, _ = find_mask(path, verdict["targets"], box=fix_box)
                            if fix_mask is not None:
                                with Image.open(path) as picture:
                                    recolored_path = save_image(recolor(picture, fix_mask, verdict["colors"]))
                                # Перефарбування теж може зіпсувати картинку (якщо Критик помилився
                                # і предмет не той): лишаємо його, лише якщо Критик визнав його кращим
                                self.after(0, self._set_pending_title, t("comparing"))
                                if brain.compare(first_image, recolored_path, prompt, settings) == 2:
                                    path = recolored_path
                                    fixed_by = "recolor"
                        if fixed_by is None:
                            brain.unload()
                            self.after(0, self._set_pending_title, t("redrawing"))
                            english = verdict["prompt"] or english
                            full_prompt = f"{english}, {style_text}" if style_text else english
                            seed = random.randint(0, 2**31 - 1)
                            path, steps = draw(full_prompt, seed)
                            fixed_by = "redraw"
                            # Перемальоване не завжди краще: Критик порівнює обидва варіанти
                            free_gpu_memory()
                            self.after(0, self._set_pending_title, t("comparing"))
                            if brain.compare(first_image, path, prompt, settings) == 1:
                                second_image = path
                                path, english = first_image, first_prompt
            except Cancelled:
                self.after(0, self._deliver, job, self._on_stopped)
                return
            except Exception as error:
                self.after(0, self._deliver, job, self._on_generate_failed, error)
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
                    message["first_prompt"] = first_prompt
                    message["fix"] = fixed_by
                    if second_image is not None:
                        # Перемальований варіант вийшов гіршим, тож показуємо перший
                        message["kept_first"] = True
                        message["second_image"] = str(second_image)
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
                if add:
                    message["add"] = True
                    message["place"] = place
                    message["target_found"] = box is not None
                    if box is not None:
                        message["box"] = [round(value) for value in box]
            variants = []
            variant_error = None
            if image_count > 1:
                variant_prompt = f"{english}, {style_text}" if style_text else english
                used_seeds = {message["seed"]}
                try:
                    if settings["check"] and unload_brain and not recolored:
                        # Критик щойно завантажив Gaia у відеопам'ять. Прибираємо її,
                        # інакше художнику не вистачить місця на наступні варіанти.
                        from src.ai import brain

                        brain.unload()
                        free_gpu_memory()
                    for number in range(2, image_count + 1):
                        check_cancel()
                        self.after(0, self._set_pending_title,
                                   f"{t('creating_image')} {number}/{image_count}")
                        variant_seed = random.randint(0, 2**31 - 1)
                        while variant_seed in used_seeds:
                            variant_seed = random.randint(0, 2**31 - 1)
                        used_seeds.add(variant_seed)

                        variant_started = time.time()
                        variant_path, variant_steps = draw(variant_prompt, variant_seed)
                        check_cancel()
                        variants.append({
                            "kind": "image",
                            "prompt": prompt,
                            "prompt_en": english,
                            "language": language,
                            "style": style,
                            "size": size,
                            "seed": variant_seed,
                            "image": str(variant_path),
                            "model": model,
                            "steps": variant_steps,
                            "seconds": round(time.time() - variant_started),
                            "created": self.now(),
                        })
                except Cancelled:
                    self.after(0, self._deliver, job, self._on_stopped)
                    return
                except Exception as error:
                    # Перша картинка вже готова: показуємо її і ті варіанти, що встигли, а не губимо все
                    traceback.print_exc()
                    variant_error = error

                message["seconds"] = round(time.time() - started)

            self.after(0, self._deliver, job, self._on_generated, chat_id, message, variants, variant_error)

        self._run_ai(work)
        return True

    def _on_translated(self, english, language):
        if self.pending is None:
            return
        self.pending["title"].configure(text=t("editing_image") if self.pending.get("edit") else t("creating_image"))
        if language != "en":
            self.pending["steps"].configure(text=shorten(t("translation_short").format(text=english), 54))

    def _set_pending_title(self, text):
        if self.pending is not None:
            self.pending["title"].configure(text=text)

    def _update_progress(self, step, total):
        if self.pending is None:
            return
        self.pending["bar"].set(step / total)
        self.pending["steps"].configure(text=t("step_of").format(step=step, total=total))

    def _on_generated(self, chat_id, message, variants=(), variant_error=None):
        self.chats.add_message(chat_id, message)
        for variant in variants:
            self.chats.add_message(chat_id, variant)
        self._set_busy(False)
        self.render_chat(fade="last")
        self.render_chat_list()
        if variant_error is not None:
            self.set_status(t("create_failed").format(error=shorten(str(variant_error), 140)))
        else:
            self.set_status(t("done_in").format(seconds=message["seconds"]))
        self.prompt_entry.focus_set()
        if message.get("review"):
            # Критик знайшов помилку: Вчитель зробить з неї урок, щоб Автор її більше не повторював
            self.queue_lesson(message, None)

    def _on_generate_failed(self, error):
        self._set_busy(False)
        self.render_chat(fade=None)
        self.render_chat_list()
        self.set_status(t("create_failed").format(error=shorten(str(error), 140)))

    # ---------- Меню акаунта ----------

    def later(self, func):
        # Кнопки всередині меню і перегляду знищуються разом з ними,
        # тому дію запускаємо на мить пізніше, коли кнопка вже відпрацювала
        return lambda: self.after(1, func)

    def toggle_account_menu(self, event=None):
        if self.account_menu is not None:
            self.close_account_menu()
            return
        name = self.settings.get("name").strip() or t("profile")
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
            (t("profile"), "person", lambda: self.open_settings("profile")),
            (t("settings"), "settings", lambda: self.open_settings("general")),
            (t("light_theme") if is_dark else t("dark_theme"), "palette", self.quick_toggle_theme),
            (t("images_folder"), "folder", lambda: open_folder(OUTPUTS_DIR)),
            (t("about"), "model", lambda: self.open_settings("about")),
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

        viewer_button(t("close"), self.later(self.close_viewer))
        viewer_button(t("in_folder"), lambda: self.show_in_folder(path))
        copy_button = viewer_button(t("copy"), lambda: self.copy_image(path, copy_button))
        self.viewer_copy = lambda: self.copy_image(path, copy_button)
        viewer_button(t("open"), lambda: open_path(path))
        if chat_id is not None:
            viewer_button(t("go_to_chat"), self.later(lambda: (self.close_viewer(), self.open_chat(chat_id))))

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

        details = [self.model_title(message["model"])]
        if message.get("style") and message["style"] != "Без стилю":
            details.append(label(message["style"]))
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
            text = t("copied")
        except Exception:
            text = t("failed")
        if button is not None:
            button.configure(text=text)
            self.after(1500, lambda: button.winfo_exists() and button.configure(text=t("copy")))

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
            self.set_status(t("wait_image"))
            return
        self.settings_section = section
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
            container, text=t("settings"), font=self.font(30, family="Georgia"), text_color=theme.TEXT, anchor="w"
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
            ("profile", t("profile")),
            ("general", t("general")),
            ("appearance", t("appearance")),
            ("generation", t("generation")),
            *((("experience", t("experience")),) if DEVELOPER else ()),
            ("memory", t("memory")),
            ("storage", t("storage")),
            ("about", t("about")),
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
        ctk.CTkLabel(
            text, text=title, font=self.font(14), text_color=theme.TEXT, anchor="w", justify="left", wraplength=440,
        ).pack(anchor="w")
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

    def _settings_profile(self, content):
        # Профіль: ім'я, прізвище, фото, пошта і кілька слів про себе. Лише на цьому комп'ютері.
        self._settings_title(content, t("profile"))
        ctk.CTkLabel(
            content, text=t("profile_hint"), font=self.font(12), text_color=theme.MUTED, anchor="w",
            justify="left", wraplength=560,
        ).pack(fill="x", pady=(0, 18))

        # Фото: велике кругле і дві кнопки
        head = ctk.CTkFrame(content, fg_color="transparent")
        head.pack(fill="x", pady=(0, 18))
        photo = self.avatar_image(72)
        name = self.full_name()
        big = ctk.CTkLabel(
            head, text="" if photo else (name[:1] or "L").upper(), image=photo, width=72, height=72, corner_radius=36,
            fg_color="transparent" if photo else theme.ACCENT, text_color=theme.ACCENT_TEXT, font=self.font(28, "bold"),
        )
        big.pack(side="left")
        self.profile_photo = photo
        buttons = ctk.CTkFrame(head, fg_color="transparent")
        buttons.pack(side="left", padx=(16, 0))
        for text, command in ((t("change_photo"), self.choose_avatar), (t("remove_photo"), self.remove_avatar)):
            if command == self.remove_avatar and not photo:
                continue
            ctk.CTkButton(
                buttons, text=text, width=0, height=30, corner_radius=8, font=self.font(13), fg_color="transparent",
                hover_color=theme.SURFACE_HOVER, text_color=theme.TEXT, border_width=1, border_color=theme.BORDER,
                command=command,
            ).pack(anchor="w", pady=2)

        self._profile_entry(content, t("first_name"), t("first_name_hint"), "name", t("name_placeholder"))
        self._profile_entry(content, t("surname"), t("surname_hint"), "surname", t("surname"))
        self._profile_entry(content, t("email"), t("email_hint"), "email", "name@example.com")

        # Про себе: кілька рядків, які читає Gaia
        ctk.CTkLabel(content, text=t("about_me"), font=self.font(14), text_color=theme.TEXT, anchor="w").pack(fill="x")
        ctk.CTkLabel(
            content, text=t("about_me_hint"), font=self.font(12), text_color=theme.MUTED, anchor="w",
            justify="left", wraplength=560,
        ).pack(fill="x")
        about = ctk.CTkTextbox(
            content, height=90, corner_radius=8, border_width=1, border_color=theme.BORDER, fg_color=theme.SURFACE,
            text_color=theme.TEXT, font=self.font(13), wrap="word",
        )
        about.insert("1.0", self.settings.get("about"))
        about.pack(fill="x", pady=(6, 14))
        about.bind("<KeyRelease>", lambda event: self.settings.set("about", about.get("1.0", "end").strip()[:500]))

    def _profile_entry(self, content, title, hint, key, placeholder):
        # Рядок профілю з полем вводу: зберігається одразу, поки ви пишете
        row = self._setting_row(content, title, hint)
        entry = ctk.CTkEntry(
            row, width=240, height=34, corner_radius=8, border_width=1, border_color=theme.BORDER,
            fg_color=theme.SURFACE, text_color=theme.TEXT, placeholder_text=placeholder,
            placeholder_text_color=theme.MUTED, font=self.font(13),
        )
        if self.settings.get(key):
            entry.insert(0, self.settings.get(key))
        entry.grid(row=0, column=1, sticky="e")

        def changed(event):
            self.settings.set(key, entry.get().strip()[:80])
            self._update_profile()
            if key == "name" and self.view == "home":
                self.greeting_label.configure(text=greeting_text(self.settings.get("name").strip()))

        entry.bind("<KeyRelease>", changed)

    def choose_avatar(self):
        from tkinter import filedialog

        path = filedialog.askopenfilename(
            parent=self, title=t("change_photo"),
            filetypes=[(t("images"), "*.png *.jpg *.jpeg *.webp *.bmp"), (t("all_files"), "*.*")],
        )
        if not path:
            return
        try:
            image = Image.open(path).convert("RGB")
        except Exception as error:
            self.set_status(t("open_photo_failed").format(error=shorten(str(error), 100)))
            return
        # Копію фото кладемо в data/avatar.png: оригінал можна потім видалити чи перемістити
        side = min(image.size)
        image = image.crop(((image.width - side) // 2, (image.height - side) // 2,
                            (image.width + side) // 2, (image.height + side) // 2)).resize((256, 256), Image.LANCZOS)
        target = Path("data/avatar.png")
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target)
        self.settings.set("avatar", str(target))
        self._update_profile()
        self.open_settings("profile")

    def remove_avatar(self):
        self.settings.set("avatar", "")
        self._update_profile()
        self.open_settings("profile")

    def _settings_general(self, content):
        self._settings_title(content, t("general"))


        row = self._setting_row(
            content,
            t("translate_prompts"),
            t("translate_hint"),
        )
        self._switch(row, "translate")

        row = self._setting_row(content, t("language"), t("language_hint"))
        selector = ctk.CTkSegmentedButton(
            row, values=list(LANGUAGES.values()), command=self.change_language, **self.segmented_style()
        )
        selector.set(LANGUAGES.get(self.settings.get("language"), LANGUAGES["uk"]))
        selector.grid(row=0, column=1, sticky="e")

    def change_language(self, name):
        # Мова інтерфейсу міняється після перезапуску: усі написи створюються під час запуску
        code = next(code for code, label in LANGUAGES.items() if label == name)
        if code == self.settings.get("language"):
            return
        self.settings.set("language", code)
        set_language(code)
        if messagebox.askyesno(t("restart_title"), t("restart_question"), parent=self):
            subprocess.Popen([sys.executable, *sys.argv])
            self.destroy()

    def _settings_appearance(self, content):
        self._settings_title(content, t("appearance"))

        row = self._setting_row(content, t("theme"), t("theme_hint"))
        names = {mode: t(key) for mode, key in THEMES.items()}
        selector = ctk.CTkSegmentedButton(
            row, values=list(names.values()),
            command=lambda shown: self.set_theme(next(mode for mode, name in names.items() if name == shown)),
            **self.segmented_style(),
        )
        selector.set(names.get(self.settings.get("theme"), names["system"]))
        selector.grid(row=0, column=1, sticky="e")

        def sidebar_changed(value):
            self.sidebar_visible = value
            self._apply_sidebar()

        row = self._setting_row(content, t("sidebar"), t("sidebar_hint"))
        self._switch(row, "sidebar", sidebar_changed)

    def _settings_generation(self, content):
        self._settings_title(content, t("generation"))

        row = self._setting_row(
            content,
            t("reasoning_level"),
            t("reasoning_hint"),
        )
        selector = ctk.CTkSegmentedButton(
            row, values=[label(name) for name in REASONING],
            command=lambda shown: self.set_reasoning(unlabel(shown, REASONING)), **self.segmented_style()
        )
        selector.set(label(self.settings.get("reasoning")))
        selector.grid(row=0, column=1, sticky="e")

        row = self._setting_row(content, t("model"), t("model_hint"))
        model_menu = None

        titles = {self.model_title(name): name for name in MODELS}

        def model_changed(shown):
            self.select_model(titles[shown])
            model_menu.set(self.model_title(self.selected_model or titles[shown]))

        model_menu = self._option(row, list(titles), self.model_title(self.selected_model or DEFAULT_MODEL), model_changed)

        def style_changed(shown):
            self.settings.set("style", unlabel(shown, self.styles()))
            self.style_menu.set(shown)

        row = self._setting_row(content, t("default_style"), t("default_style_hint"))
        self._option(row, [label(name) for name in self.styles()], self.style_menu.get(), style_changed)

        # Свої стилі: кнопка "Додати стиль" і список з кнопкою "Видалити" біля кожного
        row = self._setting_row(content, t("custom_styles"), t("custom_styles_hint"))
        self._outline_button(row, t("add_style"), lambda: self.open_style_dialog(refresh_settings=True))
        for name, style in self.custom_styles().items():
            row = self._setting_row(content, name, style.get("description") or style["prompt"])
            self._outline_button(row, t("delete"), lambda n=name: self.delete_style(n), danger=True)

        def size_changed(shown):
            self.settings.set("size", unlabel(shown, SIZES))
            self.size_menu.set(shown)

        row = self._setting_row(content, t("default_size"), t("default_size_hint"))
        self._option(row, [label(name) for name in SIZES], self.size_menu.get(), size_changed)

        row = self._setting_row(
            content,
            t("quality_boost"),
            t("quality_boost_hint"),
        )
        self._switch(row, "quality_boost")

        steps = ", ".join(f"{name} {info['steps']}" for name, info in MODELS.items())
        self._setting_row(content, t("generation_steps"), t("steps_hint").format(steps=steps))

    def _settings_experience(self, content):
        # Зошит уроків: чого Linum навчився з власних помилок і ваших оцінок
        from src.ai import lessons

        self._settings_title(content, t("experience"))
        ctk.CTkLabel(
            content,
            text=t("experience_intro"),
            font=self.font(12), text_color=theme.MUTED, anchor="w", justify="left", wraplength=560,
        ).pack(fill="x", pady=(0, 18))

        # Тренування: агенти самі придумують завдання, малюють, перевіряють і записують уроки
        row = self._setting_row(
            content, t("training"), t("training_hint"),
        )
        self.training_button = self._outline_button(
            row, t("stop") if self.training else t("start"), self.toggle_training,
        )
        self.training_label = ctk.CTkLabel(
            content, text=self.training_status, font=self.font(12), text_color=theme.TEXT,
            anchor="w", justify="left", wraplength=560,
        )
        self.training_label.pack(fill="x", pady=(0, 18))
        self._training_rounds(content)

        items = lessons.load()
        if not items:
            ctk.CTkLabel(
                content, text=t("no_lessons"),
                font=self.font(13), text_color=theme.MUTED, anchor="w",
            ).pack(fill="x")
            return

        def forget(lesson_id):
            lessons.remove(lesson_id)
            self.open_settings("experience")

        sources = {
            "training": t("agent_trainer"), "review": t("agent_critic"), "rating": t("your_rating"), "developer": t("developer"),
        }
        for lesson in reversed(items):
            when = datetime.fromisoformat(lesson["created"]).strftime("%d.%m %H:%M")
            row = self._setting_row(content, lesson["text"], f"{sources.get(lesson['source'], '')}  ·  {when}")
            self._outline_button(row, t("delete"), lambda i=lesson["id"]: forget(i), danger=True)

    def _training_rounds(self, content):
        # Останні раунди тренування: картинка, завдання і чим закінчилося
        from src.ai import trainer

        rounds = trainer.load_rounds()[-8:]
        if not rounds:
            return
        ctk.CTkLabel(
            content, text=t("training_rounds").format(count=len(trainer.load_rounds())), font=self.font(14, "bold"),
            text_color=theme.TEXT, anchor="w",
        ).pack(fill="x", pady=(0, 8))
        for item in reversed(rounds):
            row = ctk.CTkFrame(content, fg_color=theme.SURFACE, corner_radius=12)
            row.pack(fill="x", pady=(0, 6))
            row.grid_columnconfigure(1, weight=1)
            picture = item.get("image") or item.get("first_image")
            if picture and Path(picture).exists():
                thumb = ctk.CTkLabel(row, image=self.thumbnail(picture, 56), text="", cursor="hand2")
                thumb.grid(row=0, column=0, rowspan=2, padx=8, pady=8)
                thumb.bind("<Button-1>", lambda event, p=picture: open_path(p))
            ctk.CTkLabel(
                row, text=item["request"], font=self.font(13), text_color=theme.TEXT, anchor="w",
                justify="left", wraplength=470,
            ).grid(row=0, column=1, sticky="w", padx=(4, 10), pady=(8, 0))
            if item.get("lesson"):
                outcome = t("round_outcome_lesson").format(problem=item["problem"], lesson=item["lesson"])
            elif item.get("problem"):
                outcome = t("round_outcome_fixed" if item.get("fixed") else "round_outcome_problem").format(problem=item["problem"])
            else:
                outcome = t("round_outcome_ok")
            ctk.CTkLabel(
                row, text=outcome, font=self.font(12), text_color=theme.MUTED, anchor="w", justify="left", wraplength=470,
            ).grid(row=1, column=1, sticky="w", padx=(4, 10), pady=(0, 8))
        ctk.CTkFrame(content, height=10, fg_color="transparent").pack()

    def _settings_memory(self, content):
        # Що Gaia пам'ятає про вас між чатами
        from src.ai import memory

        self._settings_title(content, t("memory"))
        ctk.CTkLabel(
            content, text=t("memory_intro"), font=self.font(12), text_color=theme.MUTED,
            anchor="w", justify="left", wraplength=560,
        ).pack(fill="x", pady=(0, 18))
        facts = memory.load()
        if not facts:
            ctk.CTkLabel(content, text=t("memory_empty"), font=self.font(13), text_color=theme.MUTED, anchor="w").pack(fill="x")
            return

        def forget(fact_id):
            memory.remove(fact_id)
            self.open_settings("memory")

        for fact in reversed(facts):
            when = datetime.fromisoformat(fact["created"]).strftime("%d.%m %H:%M")
            row = self._setting_row(content, fact["text"], when)
            self._outline_button(row, t("delete"), lambda i=fact["id"]: forget(i), danger=True)

    def _settings_storage(self, content):
        self._settings_title(content, t("storage"))

        images = self.all_images()
        megabytes = sum(Path(message["image"]).stat().st_size for _, message in images) / (1024 * 1024)
        chats = [chat for chat in self.chats.chats if chat["messages"]]

        row = self._setting_row(content, t("images"), t("images_stats").format(count=len(images), megabytes=f"{megabytes:.1f}"))
        self._outline_button(row, t("open_folder"), lambda: open_folder(OUTPUTS_DIR))

        models_folder = Path(MODELS[DEFAULT_MODEL]["path"]).parent
        row = self._setting_row(content, t("models"), t("models_location").format(path=models_folder.as_posix()))
        self._outline_button(row, t("open_folder"), lambda: open_folder(models_folder))

        row = self._setting_row(content, t("chats"), t("chats_stats").format(count=len(chats)))
        self._outline_button(row, t("delete_all_chats"), self.later(self.clear_all_chats), danger=True)

    def _settings_about(self, content):
        head = ctk.CTkFrame(content, fg_color="transparent")
        head.pack(fill="x", pady=(0, 22))
        names = ctk.CTkFrame(head, fg_color="transparent")
        names.pack(side="left")
        ctk.CTkLabel(names, text=APP_NAME, font=self.font(20, "bold"), text_color=theme.TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(
            names, text=t("version").format(version=APP_VERSION), font=self.font(13), text_color=theme.MUTED, anchor="w"
        ).pack(anchor="w")

        gpu = t("after_model_load")
        torch = sys.modules.get("torch")
        if torch is not None and torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)
        elif torch is not None and torch.backends.mps.is_available():
            gpu = "Apple Silicon (MPS)"

        self._setting_row(content, t("model"), f"{self.model_title(self.selected_model or DEFAULT_MODEL)}: Stable Diffusion 1.5")
        self._setting_row(content, t("gpu"), gpu)
        self._setting_row(
            content, t("work_mode"), t("work_mode_hint")
        )
        self._setting_row(content, t("translation"), t("translation_hint"))

    def clear_all_chats(self):
        confirmed = messagebox.askyesno(
            t("delete_all_chats"),
            t("delete_all_question"),
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
