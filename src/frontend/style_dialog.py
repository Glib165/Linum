# Віконце "Новий стиль": назва і опис стилю.
# Опис можна писати будь-якою мовою: художник розуміє лише англійську, тому Linum
# перекладає його сам (тим самим перекладачем, що й запити, на процесорі).

import re
import threading

import customtkinter as ctk

from src.frontend import theme
from src.frontend.i18n import t

CYRILLIC = re.compile("[А-Яа-яІіЇїЄєҐґЁё]")


class StyleDialog(ctk.CTkToplevel):
    def __init__(self, app, on_saved):
        super().__init__(app)
        self.app = app
        self.on_saved = on_saved
        self.title(t("new_style"))
        self.geometry("460x360")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG)
        self.transient(app)
        self.after(250, self._set_icon)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=22, pady=18)

        ctk.CTkLabel(body, text=t("style_name"), font=app.font(13), text_color=theme.TEXT, anchor="w").pack(fill="x")
        self.name_entry = ctk.CTkEntry(
            body, height=34, corner_radius=8, border_width=1, border_color=theme.BORDER, fg_color=theme.SURFACE,
            text_color=theme.TEXT, font=app.font(13), placeholder_text=t("style_name_example"),
            placeholder_text_color=theme.MUTED,
        )
        self.name_entry.pack(fill="x", pady=(4, 14))

        ctk.CTkLabel(body, text=t("style_description"), font=app.font(13), text_color=theme.TEXT, anchor="w").pack(fill="x")
        ctk.CTkLabel(
            body, text=t("style_description_hint"), font=app.font(11), text_color=theme.MUTED, anchor="w",
            justify="left", wraplength=410,
        ).pack(fill="x")
        self.description = ctk.CTkTextbox(
            body, height=90, corner_radius=8, border_width=1, border_color=theme.BORDER, fg_color=theme.SURFACE,
            text_color=theme.TEXT, font=app.font(13), wrap="word",
        )
        self.description.pack(fill="x", pady=(4, 10))

        self.status = ctk.CTkLabel(body, text="", font=app.font(12), text_color=theme.MUTED, anchor="w")
        self.status.pack(fill="x")

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x", side="bottom")
        self.save_button = ctk.CTkButton(
            buttons, text=t("save"), height=34, corner_radius=8, font=app.font(13), fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER, text_color=theme.ACCENT_TEXT, command=self.save,
        )
        self.save_button.pack(side="right")
        ctk.CTkButton(
            buttons, text=t("cancel"), height=34, corner_radius=8, font=app.font(13), fg_color="transparent",
            hover_color=theme.SURFACE_HOVER, text_color=theme.TEXT, border_width=1, border_color=theme.BORDER,
            command=self.destroy,
        ).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda event: self.destroy())
        self.after(150, self._focus)

    def _set_icon(self):
        try:
            self.iconbitmap(self.app.icon_path)
        except Exception:
            pass

    def _focus(self):
        self.lift()
        self.name_entry.focus_set()

    def save(self):
        name = " ".join(self.name_entry.get().split())[:30]
        description = " ".join(self.description.get("1.0", "end").split())[:300]
        if not name or not description:
            self.status.configure(text=t("style_fill_both"), text_color=theme.DANGER)
            return
        if name in self.app.styles() and name not in self.app.custom_styles():
            # Вбудований стиль з такою назвою вже є (а свій можна перезаписати)
            self.status.configure(text=t("style_exists"), text_color=theme.DANGER)
            return
        if not CYRILLIC.search(description):
            self._done(name, description, description)
            return
        # Опис не англійською: перекладаємо у фоні, щоб вікно не завмерло
        self.save_button.configure(state="disabled")
        self.status.configure(text=t("translating_style"), text_color=theme.MUTED)

        def work():
            try:
                from src.ai.translator import to_english

                english = to_english(description)[0]
            except Exception:
                english = description
            self.after(0, self._done, name, english, description)

        threading.Thread(target=work, daemon=True).start()

    def _done(self, name, english, description):
        if not self.winfo_exists():
            return
        self.on_saved(name, english, description)
        self.destroy()
