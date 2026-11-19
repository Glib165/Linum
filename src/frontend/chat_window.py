# Окреме вікно з чатом ("Відкрити в новому вікні" в меню чату).
# Лише для перегляду: можна гортати, виділяти й копіювати текст, відкривати картинки,
# а в головному вікні тим часом працювати з іншим чатом.

import os
from pathlib import Path

import customtkinter as ctk

from src.frontend import theme
from src.frontend.widgets import SelectableText

WIDTH = 760
TEXT_WIDTH = 600


class ChatWindow(ctk.CTkToplevel):
    def __init__(self, app, chat):
        super().__init__(app)
        self.app = app
        self.images = []
        self.title(chat["title"])
        self.geometry(f"{WIDTH}x820")
        self.minsize(520, 400)
        self.configure(fg_color=theme.BG)
        # customtkinter ставить вікну свою іконку трохи згодом, тому нашу ставимо після неї
        self.after(250, self._set_icon)

        feed = ctk.CTkScrollableFrame(
            self, fg_color=theme.BG, scrollbar_button_color=theme.BG, scrollbar_button_hover_color=theme.BORDER,
        )
        feed.pack(fill="both", expand=True, padx=8, pady=8)
        for message in chat["messages"]:
            self._add(feed, message)
        self.after(100, self.lift)

    def _set_icon(self):
        try:
            self.iconbitmap(self.app.icon_path)
        except Exception:
            pass

    def _add(self, feed, message):
        kind = message.get("kind")
        font = self.app.font
        if kind == "user" or (kind is None and message.get("prompt") and not message.get("image")):
            row = ctk.CTkFrame(feed, fg_color="transparent")
            row.pack(fill="x", pady=(18, 6))
            attachment = message.get("attachment")
            if attachment and Path(attachment).exists():
                self._picture(row, attachment, 220).pack(anchor="e", padx=(80, 6), pady=(0, 6))
            text = message.get("text") or message.get("prompt") or ""
            if text:
                bubble = ctk.CTkFrame(row, fg_color=theme.SURFACE, corner_radius=16)
                bubble.pack(anchor="e", padx=(80, 6))
                SelectableText(bubble, text, font(14), max_width=460, bg=theme.SURFACE).pack(padx=16, pady=9)
        elif kind == "assistant":
            SelectableText(feed, message["text"], font(14), max_width=TEXT_WIDTH).pack(anchor="w", padx=6, pady=(4, 8))
        elif message.get("image"):
            if kind is None and message.get("prompt"):
                # Старий формат: запит і картинка в одному повідомленні
                self._add(feed, {"kind": "user", "text": message["prompt"]})
            card = ctk.CTkFrame(feed, fg_color=theme.SURFACE, corner_radius=18, border_width=1, border_color=theme.BORDER)
            card.pack(anchor="w", padx=2, pady=(0, 8))
            if Path(message["image"]).exists():
                self._picture(card, message["image"], 460).pack(padx=8, pady=(8, 4))
            if message.get("prompt_en"):
                SelectableText(
                    card, message["prompt_en"], font(12), max_width=450, text_color=theme.MUTED, bg=theme.SURFACE,
                ).pack(anchor="w", padx=14, pady=(2, 10))

    def _picture(self, parent, path, longest):
        # Картинка; клік відкриває її в програмі перегляду Windows
        image = self.app.card_image(Path(path), longest=longest)
        self.images.append(image)
        label = ctk.CTkLabel(parent, image=image, text="", cursor="hand2")
        label.bind("<Button-1>", lambda event: os.startfile(Path(path).resolve()))
        return label
