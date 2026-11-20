# Віконце "рівень міркувань і модель", яке відкривається з кнопки в полі вводу.
#
#   ┌──────────────────────────────┐
#   │           Високий          ↺ │   назва рівня (синя, а Ультра фіолетова) і кнопка "як було"
#   │      Gaia · збалансована ›   │   художня модель: клік відкриває список моделей
#   │  ━━━━━━━━━━━━●───────·────── │   повзунок: Низький ... Ультра
#   └──────────────────────────────┘

import random

import customtkinter as ctk
import numpy as np
from PIL import Image, ImageDraw

from config.config import DEFAULT_MODEL, DEFAULT_REASONING, MODELS, REASONING
from src.frontend import theme
from src.frontend.icons import make_icon
from src.frontend.i18n import label, t
from src.frontend.widgets import themed

WIDTH = 300
MENU_WIDTH = 260
SLIDER_WIDTH = 264
SLIDER_HEIGHT = 30
# Повзунок малюємо в кілька разів більшим і зменшуємо: так кола гладкі, без "сходинок"
SCALE = 4

# Ультра має особливий вигляд: фіолетова назва і перелив від синього до фіолетового з іскорками
ULTRA = list(REASONING.keys())[-1]
ULTRA_TITLE = ("#7A4FD6", "#B794F6")
ULTRA_GRADIENT = ((61, 95, 217), (123, 92, 224), (184, 128, 236))
ULTRA_NOTE = "ultra_note"


def rounded_window(window):
    # Вікно без рамки Windows із заокругленими кутами. Фон вікна стає "прозорим кольором";
    # цей колір майже такий, як фон програми, тож згладжені краї кутів не дають облямівки.
    red, green, blue = (int(themed(theme.BG)[i:i + 2], 16) for i in (1, 3, 5))
    key = f"#{red:02x}{green:02x}{blue ^ 1:02x}"
    window.withdraw()
    window.overrideredirect(True)
    window.attributes("-topmost", True)
    window.configure(fg_color=key)
    window.attributes("-transparentcolor", key)
    body = ctk.CTkFrame(
        window, fg_color=theme.SURFACE, bg_color=key, corner_radius=14, border_width=1, border_color=theme.BORDER,
    )
    body.pack(fill="both", expand=True)
    return body


def slider_image(position, count, mode, ultra):
    # Малюнок повзунка: доріжка-пігулка, заповнена частина до бігунка, крапки на позиціях і білий бігунок
    index = 0 if mode == "light" else 1
    width, height = SLIDER_WIDTH * SCALE, SLIDER_HEIGHT * SCALE
    middle = height // 2
    radius = middle - SCALE
    knob = radius - 2 * SCALE
    left, right = radius, width - radius
    stops = [left + (right - left) * i / (count - 1) for i in range(count)]
    x = stops[position]

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, middle - radius, width - 1, middle + radius), radius=radius, fill=theme.LEVEL_TRACK[index])

    # Заповнена частина: для Ультра перелив кольорів з іскорками, для решти синя
    fill_mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(fill_mask).rounded_rectangle((0, middle - radius, x + radius, middle + radius), radius=radius, fill=255)
    if ultra:
        anchors = np.linspace(0, 1, len(ULTRA_GRADIENT))
        share = np.linspace(0, 1, width)
        row = np.stack([np.interp(share, anchors, [color[c] for color in ULTRA_GRADIENT]) for c in range(3)], axis=-1)
        fill = Image.fromarray(np.repeat(row[None], height, axis=0).astype("uint8")).convert("RGBA")
        # Іскорки малюємо на окремому прозорому шарі і накладаємо зверху, щоб вони світилися на переливі
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        sparkles = ImageDraw.Draw(layer)
        chance = random.Random(7)
        for _ in range(55):
            sx, sy = chance.uniform(radius, x), chance.uniform(middle - radius * 0.7, middle + radius * 0.7)
            size = chance.uniform(0.6, 1.8) * SCALE
            sparkles.ellipse((sx - size, sy - size, sx + size, sy + size), fill=(255, 255, 255, chance.randint(70, 220)))
        fill = Image.alpha_composite(fill, layer)
    else:
        fill = Image.new("RGBA", (width, height), theme.LEVEL_FILL[index])
    image.paste(fill, (0, 0), fill_mask)

    # Крапки, тінь і бігунок на окремому шарі: напівпрозоре накладається на доріжку, а не "пробиває" її
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    top = ImageDraw.Draw(layer)
    for i, stop in enumerate(stops):
        if i == position:
            continue
        dot = (255, 255, 255, 150) if i < position else ((160, 160, 160, 255) if index == 0 else (105, 105, 105, 255))
        top.ellipse((stop - 2 * SCALE, middle - 2 * SCALE, stop + 2 * SCALE, middle + 2 * SCALE), fill=dot)
    # Легка тінь під бігунком, потім сам бігунок
    top.ellipse((x - knob, middle - knob + SCALE, x + knob, middle + knob + SCALE), fill=(0, 0, 0, 60))
    top.ellipse((x - knob, middle - knob, x + knob, middle + knob), fill=(255, 255, 255, 255))
    image = Image.alpha_composite(image, layer)
    return image.resize((SLIDER_WIDTH, SLIDER_HEIGHT), Image.LANCZOS)


class BrainPopup(ctk.CTkToplevel):
    def __init__(self, app, anchor):
        super().__init__(app)
        self.app = app
        self.anchor = anchor
        self.levels = list(REASONING.keys())
        self.model_menu = None
        body = rounded_window(self)

        head = ctk.CTkFrame(body, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 0))
        head.grid_columnconfigure((0, 2), minsize=30)
        head.grid_columnconfigure(1, weight=1)
        self.title_label = ctk.CTkLabel(head, text="", font=app.font(16, "bold"))
        self.title_label.grid(row=0, column=1)
        ctk.CTkButton(
            head, text="", image=app.small_icons["refresh"], width=28, height=28, corner_radius=8,
            fg_color="transparent", hover_color=theme.SURFACE_HOVER, command=self.reset,
        ).grid(row=0, column=2, sticky="e")

        self.subtitle = ctk.CTkButton(
            body, text="", height=22, width=0, corner_radius=6, font=app.font(12),
            fg_color="transparent", hover_color=theme.SURFACE_HOVER, text_color=theme.MUTED,
            command=self.toggle_model_menu,
        )
        self.subtitle.pack(pady=(0, 10))

        self.slider = ctk.CTkLabel(body, text="", cursor="hand2")
        self.slider.pack(padx=18, pady=(0, 16))
        self.slider.bind("<Button-1>", self.drag)
        self.slider.bind("<B1-Motion>", self.drag)

        self.refresh()
        self.bind("<Escape>", lambda event: self.close())
        # Клік будь-де в головному вікні або переміщення вікна закриває віконце
        self.click_binding = app.bind("<Button-1>", self._outside_click, add="+")
        self.move_binding = app.bind("<Configure>", self._app_moved, add="+")
        self._place_above(anchor)
        # Де було вікно програми, коли віконце відкрилося: якщо вікно зрушать, віконце закриється
        self.app_geometry = self._geometry_of_app()

    def _place_above(self, anchor):
        # Над усім полем вводу (кнопка лежить у рядку інструментів, а той - у рамці поля),
        # вирівняно по правому краю кнопки
        self.update_idletasks()
        scaling = ctk.ScalingTracker.get_window_scaling(self)
        width = int(WIDTH * scaling)
        height = self.winfo_reqheight()
        x = anchor.winfo_rootx() + anchor.winfo_width() - width
        y = anchor.master.master.winfo_rooty() - height - int(8 * scaling)
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
        self.deiconify()
        self.lift()
        self.focus_force()

    def level_index(self):
        current = self.app.settings.get("reasoning")
        return self.levels.index(current) if current in self.levels else self.levels.index(DEFAULT_REASONING)

    def refresh(self):
        index = self.level_index()
        name = self.levels[index]
        ultra = name == ULTRA
        self.title_label.configure(text=label(name), text_color=ULTRA_TITLE if ultra else theme.LEVEL)
        key = self.app.selected_model or DEFAULT_MODEL
        model = self.app.model_title(key)
        if ultra:
            self.subtitle.configure(text=f"{t(ULTRA_NOTE)}  ·  {model}  ›")
        else:
            tier = self.app.model_tiers.get(key, "")
            self.subtitle.configure(text=f"{model}  ·  {tier}  ›" if tier else f"{model}  ›")
        self.slider_image = ctk.CTkImage(
            light_image=slider_image(index, len(self.levels), "light", ultra),
            dark_image=slider_image(index, len(self.levels), "dark", ultra),
            size=(SLIDER_WIDTH, SLIDER_HEIGHT),
        )
        self.slider.configure(image=self.slider_image)

    def drag(self, event):
        # Найближча до курсора позиція повзунка
        share = min(1.0, max(0.0, event.x / max(1, self.slider.winfo_width())))
        index = round(share * (len(self.levels) - 1))
        if index != self.level_index():
            self.app.set_reasoning(self.levels[index])
            self.refresh()

    def reset(self):
        self.app.set_reasoning(DEFAULT_REASONING)
        self.refresh()

    def toggle_model_menu(self):
        if self.model_menu is not None:
            self.model_menu.close()
        else:
            self.model_menu = ModelMenu(self)

    def model_chosen(self, name):
        self.app.select_model(name)
        self.refresh()

    def _geometry_of_app(self):
        app = self.app
        return app.winfo_rootx(), app.winfo_rooty(), app.winfo_width(), app.winfo_height()

    def _outside_click(self, event):
        # Клік по самій кнопці віконця обробляє кнопка (вона й закриває), тут його пропускаємо
        if str(event.widget).startswith(str(self.anchor)):
            return
        self.close()

    def _app_moved(self, event):
        # Windows інколи надсилає "вікно змінилося" без справжньої зміни, тому порівнюємо
        if event.widget is self.app and self._geometry_of_app() != self.app_geometry:
            self.close()

    def close(self):
        if not self.winfo_exists():
            return
        if self.model_menu is not None:
            self.model_menu.close()
        self.app.unbind("<Button-1>", self.click_binding)
        self.app.unbind("<Configure>", self.move_binding)
        self.app.brain_popup = None
        self.destroy()


class ModelMenu(ctk.CTkToplevel):
    # Список художніх моделей над віконцем рівня:
    #   Оберіть модель
    #   За замовчуванням            (другий рядок: рекомендована модель)
    #   Fornax                      (другий рядок: швидка)
    #   Gaia                     ✓
    #   Cygnus
    def __init__(self, popup):
        super().__init__(popup)
        self.popup = popup
        app = popup.app
        body = rounded_window(self)
        self.check_icon = make_icon("check", 14, theme.TEXT)

        ctk.CTkLabel(body, text=t("choose_model"), font=app.font(12), text_color=theme.MUTED, anchor="w").pack(
            fill="x", padx=16, pady=(10, 2)
        )
        current = app.selected_model or DEFAULT_MODEL
        tier = app.model_tiers.get(DEFAULT_MODEL, "")
        self._item(body, t("default"), t("recommended").format(model=app.model_title(DEFAULT_MODEL), tier=tier), DEFAULT_MODEL, False)
        for name in MODELS:
            available = app.model_available(name)
            note = app.model_tiers.get(name, "") if available else t("no_model_file")
            self._item(body, app.model_title(name), note, name, name == current, enabled=available)
        ctk.CTkFrame(body, height=6, fg_color="transparent").pack()

        self.bind("<Escape>", lambda event: self.close())
        self.update_idletasks()
        scaling = ctk.ScalingTracker.get_window_scaling(self)
        width = int(MENU_WIDTH * scaling)
        height = self.winfo_reqheight()
        x = popup.winfo_rootx()
        y = popup.winfo_rooty() - height - int(6 * scaling)
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
        self.deiconify()
        self.lift()

    def _item(self, parent, title, note, model, checked, enabled=True):
        # Пункт меню: назва, сірий підпис другим рядком і галочка, якщо модель вибрана
        app = self.popup.app
        row = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=8)
        row.pack(fill="x", padx=6, pady=1)
        row.grid_columnconfigure(0, weight=1)
        title_label = ctk.CTkLabel(
            row, text=title, font=app.font(13), anchor="w", height=20,
            text_color=theme.TEXT if enabled else theme.MUTED,
        )
        title_label.grid(row=0, column=0, sticky="w", padx=(10, 0), pady=(6, 0))
        note_label = ctk.CTkLabel(row, text=note, font=app.font(11), anchor="w", height=16, text_color=theme.MUTED)
        note_label.grid(row=1, column=0, sticky="w", padx=(10, 0), pady=(0, 6))
        widgets = [row, title_label, note_label]
        if checked:
            mark = ctk.CTkLabel(row, text="", image=self.check_icon)
            mark.grid(row=0, column=1, rowspan=2, padx=(0, 10))
            widgets.append(mark)
        if not enabled:
            return

        def enter(event):
            row.configure(fg_color=theme.SURFACE_HOVER)

        def leave(event):
            # Курсор міг перейти з рамки на підпис усередині неї: перевіряємо, де він насправді
            x, y = self.winfo_pointerxy()
            if not str(self.winfo_containing(x, y) or "").startswith(str(row)):
                row.configure(fg_color="transparent")

        def choose(event):
            self.close()
            self.popup.model_chosen(model)

        for widget in widgets:
            widget.bind("<Enter>", enter, add="+")
            widget.bind("<Leave>", leave, add="+")
            widget.bind("<Button-1>", choose, add="+")
            widget.configure(cursor="hand2")

    def close(self):
        if self.winfo_exists():
            self.destroy()
        self.popup.model_menu = None
