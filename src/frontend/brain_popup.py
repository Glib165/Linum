# Віконце "рівень міркувань і модель", яке відкривається з кнопки в полі вводу.
#
#   ┌──────────────────────────────┐
#   │           Високий          ↺ │   назва рівня і кнопка "як було"
#   │       Gaia · збалансована ›  │   художня модель (клік відкриває список)
#   │  ━━━━━━━━━━━━●───────·────── │   повзунок: Низький ... Ультра
#   │  Gaia 3.7 · думає · ...      │   що робить цей рівень
#   └──────────────────────────────┘

import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageDraw

from config.config import DEFAULT_REASONING, MODELS, REASONING
from src.frontend import theme
from src.frontend.widgets import themed

WIDTH = 300
SLIDER_WIDTH = 264
SLIDER_HEIGHT = 34
# Повзунок малюємо в кілька разів більшим і зменшуємо: так кола гладкі, без "сходинок"
SCALE = 4


def describe(settings):
    # Що робить рівень, словами: береться прямо з налаштувань REASONING у config.py
    model = "Мала модель" if "e4b" in settings["model"] or "e2b" in settings["model"] else "Gaia 3.7"
    think = "думає" if settings["think"] else "без роздумів"
    check = "перевіряє картинку" if settings["check"] else "без перевірки"
    return f"{model}  ·  {think}  ·  {check}"


def slider_image(position, count, mode):
    # Малюнок повзунка: доріжка, заповнена синім до бігунка, крапки на позиціях і білий бігунок
    index = 0 if mode == "light" else 1
    width, height = SLIDER_WIDTH * SCALE, SLIDER_HEIGHT * SCALE
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    knob = height // 2 - 2 * SCALE
    track_top, track_bottom = height // 2 - 11 * SCALE, height // 2 + 11 * SCALE
    left, right = knob + 2 * SCALE, width - knob - 2 * SCALE
    stops = [left + (right - left) * i / (count - 1) for i in range(count)]
    x = stops[position]

    draw.rounded_rectangle((0, track_top, width - 1, track_bottom), radius=11 * SCALE, fill=theme.LEVEL_TRACK[index])
    draw.rounded_rectangle((0, track_top, x, track_bottom), radius=11 * SCALE, fill=theme.LEVEL_FILL[index])
    for i, stop in enumerate(stops):
        if i == position:
            continue
        dot = (255, 255, 255, 150) if i < position else ((150, 150, 150, 255) if index == 0 else (110, 110, 110, 255))
        draw.ellipse((stop - 2 * SCALE, height // 2 - 2 * SCALE, stop + 2 * SCALE, height // 2 + 2 * SCALE), fill=dot)
    # Легка тінь під бігунком, потім сам бігунок
    draw.ellipse((x - knob, height // 2 - knob + SCALE, x + knob, height // 2 + knob + SCALE), fill=(0, 0, 0, 60))
    draw.ellipse((x - knob, height // 2 - knob, x + knob, height // 2 + knob), fill=(255, 255, 255, 255))
    return image.resize((SLIDER_WIDTH, SLIDER_HEIGHT), Image.LANCZOS)


class BrainPopup(ctk.CTkToplevel):
    def __init__(self, app, anchor):
        super().__init__(app)
        self.app = app
        self.levels = list(REASONING.keys())
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        # Заокруглені кути: фон вікна робимо "прозорим кольором" Windows. Цей колір майже такий,
        # як фон програми, тому згладжені краї кутів не дають темної чи світлої облямівки.
        red, green, blue = (int(themed(theme.BG)[i:i + 2], 16) for i in (1, 3, 5))
        key = f"#{red:02x}{green:02x}{blue ^ 1:02x}"
        self.configure(fg_color=key)
        self.attributes("-transparentcolor", key)

        body = ctk.CTkFrame(
            self, fg_color=theme.SURFACE, bg_color=key, corner_radius=14, border_width=1, border_color=theme.BORDER,
        )
        body.pack(fill="both", expand=True)

        head = ctk.CTkFrame(body, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 0))
        head.grid_columnconfigure((0, 2), minsize=30)
        head.grid_columnconfigure(1, weight=1)
        self.title_label = ctk.CTkLabel(head, text="", font=app.font(16, "bold"), text_color=theme.LEVEL)
        self.title_label.grid(row=0, column=1)
        ctk.CTkButton(
            head, text="", image=app.small_icons["refresh"], width=28, height=28, corner_radius=8,
            fg_color="transparent", hover_color=theme.SURFACE_HOVER, command=self.reset,
        ).grid(row=0, column=2, sticky="e")

        self.model_button = ctk.CTkButton(
            body, text="", height=22, width=0, corner_radius=6, font=app.font(12),
            fg_color="transparent", hover_color=theme.SURFACE_HOVER, text_color=theme.MUTED,
            command=self.choose_model,
        )
        self.model_button.pack(pady=(0, 10))

        self.slider = ctk.CTkLabel(body, text="", cursor="hand2")
        self.slider.pack(padx=18)
        self.slider.bind("<Button-1>", self.drag)
        self.slider.bind("<B1-Motion>", self.drag)

        self.description = ctk.CTkLabel(
            body, text="", font=app.font(11), text_color=theme.MUTED, wraplength=WIDTH - 30,
        )
        self.description.pack(padx=12, pady=(8, 12))

        self.refresh()
        self.bind("<Escape>", lambda event: self.close())
        # Клік будь-де в головному вікні або переміщення вікна закриває віконце
        self.anchor = anchor
        # Де було вікно програми, коли віконце відкрилося: якщо вікно зрушать, віконце закриється
        self.app_geometry = self._geometry_of_app()
        self.click_binding = app.bind("<Button-1>", self._outside_click, add="+")
        self.move_binding = app.bind("<Configure>", self._app_moved, add="+")
        self.menu_open = False
        self._place_above(anchor)

    def _place_above(self, anchor):
        # Над кнопкою, вирівняно по її правому краю
        self.update_idletasks()
        scaling = ctk.ScalingTracker.get_window_scaling(self)
        width = int(WIDTH * scaling)
        height = self.winfo_reqheight()
        x = anchor.winfo_rootx() + anchor.winfo_width() - width
        # Над усім полем вводу (кнопка лежить у рядку інструментів, а той - у рамці поля)
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
        self.title_label.configure(text=name)
        model = self.app.selected_model or "Модель"
        tier = self.app.model_tiers.get(model, "")
        self.model_button.configure(text=f"{model}  ·  {tier}  ›" if tier else f"{model}  ›")
        self.slider_image = ctk.CTkImage(
            light_image=slider_image(index, len(self.levels), "light"),
            dark_image=slider_image(index, len(self.levels), "dark"),
            size=(SLIDER_WIDTH, SLIDER_HEIGHT),
        )
        self.slider.configure(image=self.slider_image)
        self.description.configure(text=describe(REASONING[name]))

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

    def choose_model(self):
        # Список художніх моделей; ті, файлу яких немає, неактивні
        menu = tk.Menu(
            self, tearoff=0, bd=0, relief="flat", font=(theme.FONT_FAMILY, 10),
            bg=themed(theme.SURFACE), fg=themed(theme.TEXT),
            activebackground=themed(theme.SURFACE_HOVER), activeforeground=themed(theme.TEXT),
            disabledforeground=themed(theme.MUTED),
        )
        for name in MODELS:
            tier = self.app.model_tiers.get(name, "")
            available = self.app.model_available(name)
            label = f"{name}  ·  {tier}" if available else f"{name}  ·  файлу ще немає"
            menu.add_command(
                label=label, state="normal" if available else "disabled",
                command=lambda n=name: (self.app.select_model(n), self.refresh()),
            )
        self.menu_open = True
        try:
            menu.tk_popup(self.model_button.winfo_rootx(), self.model_button.winfo_rooty() + self.model_button.winfo_height())
        finally:
            menu.grab_release()
            self.menu_open = False

    def _outside_click(self, event):
        # Клік по самій кнопці віконця обробляє кнопка (вона й закриває), тут його пропускаємо
        if self.menu_open or str(event.widget).startswith(str(self.anchor)):
            return
        self.close()

    def _geometry_of_app(self):
        app = self.app
        return app.winfo_rootx(), app.winfo_rooty(), app.winfo_width(), app.winfo_height()

    def _app_moved(self, event):
        # Windows інколи надсилає "вікно змінилося" без справжньої зміни, тому порівнюємо
        if event.widget is self.app and self._geometry_of_app() != self.app_geometry:
            self.close()

    def close(self):
        if not self.winfo_exists():
            return
        self.app.unbind("<Button-1>", self.click_binding)
        self.app.unbind("<Configure>", self.move_binding)
        self.app.brain_popup = None
        self.destroy()
