# Власні віджети Linum:
#   SelectableText  текст повідомлення, який можна виділити мишкою і скопіювати
#   PromptBox       багаторядкове поле вводу (Enter надсилає, Shift+Enter новий рядок)
#   text_menu       меню правої кнопки миші: Копіювати, Вставити, Виділити все
#   fade_in         плавна поява нового вмісту
#   install_clipboard_keys  Ctrl+C / Ctrl+V / Ctrl+X / Ctrl+A на будь-якій розкладці

import tkinter as tk
import tkinter.font as tkfont
import weakref

import customtkinter as ctk

from src.frontend import theme
from src.frontend.i18n import t


def themed(color):
    # Колір з пари (світла, темна) для теми, яка увімкнена зараз
    if isinstance(color, (tuple, list)):
        return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
    return color


def wrapped_lines(text, font, width):
    # Скільки рядків займе текст при ширині width, якщо переносити цілими словами.
    # Рахуємо самі, щоб знати висоту ще до того, як віджет з'явиться на екрані.
    total = 0
    for paragraph in text.split("\n"):
        line = ""
        lines = 1
        for word in paragraph.split(" "):
            candidate = f"{line} {word}" if line else word
            if font.measure(candidate) <= width or not line:
                line = candidate
            else:
                lines += 1
                line = word
        total += lines
    return total


# ---------- Меню правої кнопки ----------


def text_menu(widget, event, editable):
    """Меню для тексту. widget це tk.Text (усередині CTkTextbox)."""
    has_selection = bool(widget.tag_ranges("sel"))
    menu = tk.Menu(
        widget,
        tearoff=0,
        bg=themed(theme.SURFACE),
        fg=themed(theme.TEXT),
        activebackground=themed(theme.SURFACE_HOVER),
        activeforeground=themed(theme.TEXT),
        disabledforeground=themed(theme.MUTED),
        bd=0,
        relief="flat",
        font=(theme.FONT_FAMILY, 10),
    )

    def state(enabled):
        return "normal" if enabled else "disabled"

    def select_all():
        widget.focus_set()
        widget.tag_add("sel", "1.0", "end-1c")

    def copy_all():
        widget.clipboard_clear()
        widget.clipboard_append(widget.get("1.0", "end-1c"))

    if editable:
        menu.add_command(label=t("cut"), accelerator="Ctrl+X", state=state(has_selection),
                         command=lambda: widget.event_generate("<<Cut>>"))
    menu.add_command(label=t("copy"), accelerator="Ctrl+C", state=state(has_selection),
                     command=lambda: widget.event_generate("<<Copy>>"))
    if editable:
        menu.add_command(label=t("paste"), accelerator="Ctrl+V",
                         command=lambda: widget.event_generate("<<Paste>>"))
    else:
        menu.add_command(label=t("copy_message"), command=copy_all)
    menu.add_separator()
    menu.add_command(label=t("select_all"), accelerator="Ctrl+A", command=select_all)
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def install_clipboard_keys(root):
    # На українській чи російській розкладці Ctrl+C надсилає кириличну літеру,
    # і стандартні комбінації tkinter не спрацьовують. Тому ловимо фізичну клавішу.
    actions = {67: "<<Copy>>", 86: "<<Paste>>", 88: "<<Cut>>", 65: "select_all", 90: "<<Undo>>"}

    def on_key(event):
        action = actions.get(event.keycode)
        widget = event.widget
        if action is None or not isinstance(widget, (tk.Text, tk.Entry)):
            return None
        # На латинській розкладці tkinter сам обробляє все, крім Ctrl+A:
        # у текстовому полі він за замовчуванням переносить курсор на початок рядка
        if event.keysym.isascii() and len(event.keysym) == 1 and action != "select_all":
            return None
        if action == "select_all":
            if isinstance(widget, tk.Text):
                widget.tag_add("sel", "1.0", "end-1c")
            else:
                widget.select_range(0, "end")
        else:
            widget.event_generate(action)
        return "break"

    root.bind_all("<Control-KeyPress>", on_key, add="+")


def setup_selection(textbox):
    # Колір виділення, і щоб виділення не зникало, коли фокус переходить деінде
    selection = themed(theme.SELECTION)
    textbox.configure(selectbackground=selection, inactiveselectbackground=selection,
                      selectforeground=themed(theme.TEXT))


# ---------- Текст повідомлення ----------


def display_lines(text_widget):
    # Скільки рядків займає текст на екрані з урахуванням переносів.
    # Залежно від версії Python відповідь буває числом, кортежем або None.
    try:
        result = text_widget.count("1.0", "end-1c", "displaylines")
    except tk.TclError:
        return None
    if isinstance(result, tuple):
        result = result[0]
    return (result or 0) + 1


class SelectableText(tk.Frame):
    """Текст лише для читання, але його можна виділити мишкою і скопіювати.

    Ширина підлаштовується під текст (не більше max_width), висота під кількість рядків.
    Зроблено на звичайному tk.Text: він легкий, тож чат із сотнею повідомлень відкривається швидко.
    """

    # Усі тексти на екрані, щоб перефарбувати їх при зміні теми
    instances = weakref.WeakSet()

    def __init__(self, master, text, font, max_width, text_color=theme.TEXT, bg=theme.BG):
        scaling = ctk.ScalingTracker.get_widget_scaling(master)
        # Шрифт у справжніх пікселях екрана (customtkinter масштабує свої віджети сам, а tk.Text ні)
        self.real_font = tkfont.Font(
            family=font.cget("family"), size=-abs(round(abs(font.cget("size")) * scaling)), weight=font.cget("weight")
        )
        self.text = text
        self.text_color = text_color
        self.bg_color = bg
        self.line_height = self.real_font.metrics("linespace")
        natural = max(self.real_font.measure(line) for line in text.split("\n")) + 4
        self.pixel_width = max(20, min(round(max_width * scaling), natural))
        lines = wrapped_lines(text, self.real_font, self.pixel_width - 2)
        super().__init__(master, width=self.pixel_width, height=self.line_height * lines + 2, bd=0,
                         highlightthickness=0, bg=themed(bg))
        self.pack_propagate(False)

        self.textbox = tk.Text(
            self, font=self.real_font, wrap="word", bd=0, highlightthickness=0, padx=0, pady=1,
            cursor="xterm", exportselection=True, takefocus=0,
        )
        self.textbox.insert("1.0", text)
        self.textbox.configure(state="disabled")
        self.textbox.pack(fill="both", expand=True)
        self.apply_colors()
        SelectableText.instances.add(self)

        self.textbox.bind("<Button-1>", lambda event: self.textbox.focus_set())
        self.textbox.bind("<Button-3>", lambda event: text_menu(self.textbox, event, editable=False))
        # Коліщатко миші має гортати чат, а не цей маленький текст
        self.textbox.bind("<MouseWheel>", self._forward_wheel)
        self.textbox.bind("<Configure>", lambda event: self.after_idle(self._fit_height))

    def apply_colors(self, text_color=None):
        bg = themed(self.bg_color)
        self.configure(bg=bg)
        self.textbox.configure(bg=bg, fg=text_color or themed(self.text_color))
        setup_selection(self.textbox)

    def _forward_wheel(self, event):
        # Передаємо прокрутку рамці навколо, а вона вже гортає всю стрічку чату
        self.master.event_generate("<MouseWheel>", delta=event.delta, x=event.x, y=event.y)
        return "break"

    def _fit_height(self):
        # Перевірка після появи на екрані: якщо рядків вийшло більше, ніж ми порахували
        if not self.winfo_exists():
            return
        lines = display_lines(self.textbox)
        if lines is None:
            return
        height = self.line_height * lines + 2
        if abs(height - int(self.cget("height"))) > 2:
            self.configure(height=height)


def refresh_theme():
    # Після зміни теми перефарбовуємо тексти, бо tk.Text не вміє цього сам
    for item in list(SelectableText.instances):
        try:
            item.apply_colors()
        except tk.TclError:
            pass


# ---------- Поле вводу ----------


class PromptBox(ctk.CTkTextbox):
    """Багаторядкове поле вводу.

    Enter надсилає повідомлення, Shift+Enter переносить рядок.
    Поле підростає разом із текстом до MAX_LINES рядків, далі текст прокручується.
    """

    MAX_LINES = 8
    PLACEHOLDER_X = 12
    PLACEHOLDER_Y = 6

    def __init__(self, master, placeholder, font, width, on_submit):
        self.line_height = font.metrics("linespace")
        super().__init__(
            master,
            width=width,
            height=self.line_height + 12,
            font=font,
            border_width=0,
            fg_color=theme.SURFACE,
            text_color=theme.TEXT,
            wrap="word",
            activate_scrollbars=False,
        )
        self.on_submit = on_submit
        self.placeholder_visible = True
        self.visible_lines = 1
        self._textbox.configure(undo=True)
        # Відступи навколо тексту теж клікабельні, а не лише сам рядок
        self._canvas.bind("<Button-1>", self.focus_end)
        setup_selection(self._textbox)
        # У текстового поля немає підказки-заглушки, тому кладемо поверх нього сірий напис
        self.placeholder = ctk.CTkLabel(self, text=placeholder, font=font, text_color=theme.MUTED, height=1)
        self.placeholder.place(x=self.PLACEHOLDER_X, y=self.PLACEHOLDER_Y)
        # Над підказкою курсор миші такий самий, як над текстом, і клік по ній відкриває поле для друку
        self.placeholder.configure(cursor="xterm")
        self.placeholder.bind("<Button-1>", self.focus_end)
        self.bind("<Return>", self._on_return)
        self.bind("<KeyRelease>", lambda event: self._refresh())
        self.bind("<<Paste>>", lambda event: self.after(1, self._refresh))
        self.bind("<<SelectAll>>", self._select_all)
        self.bind("<<Cut>>", lambda event: self.after(1, self._refresh))
        self.bind("<Button-3>", lambda event: text_menu(self._textbox, event, editable=True))

    def _on_return(self, event):
        if event.state & 0x0001:  # затиснутий Shift: звичайний перенос рядка
            self.after(1, self._refresh)
            return None
        self.on_submit()
        return "break"  # не вставляти перенос рядка

    def _select_all(self, event=None):
        # Порожнє поле нема чого виділяти
        if self.get():
            self._textbox.tag_add("sel", "1.0", "end-1c")
        return "break"

    def focus_end(self, event=None):
        # Клік будь-де по рамці поля ставить курсор у кінець тексту
        self._textbox.focus_set()
        self._textbox.mark_set("insert", "end-1c")
        self._textbox.see("insert")
        return "break"

    def _refresh(self):
        # Викликається після кожної клавіші. Змінюємо вигляд лише тоді, коли справді треба:
        # кожна зміна висоти змушує customtkinter перемальовувати всю рамку з кнопками,
        # і якщо робити це на кожну літеру, інтерфейс смикається.
        text = self.get()
        show_placeholder = not text
        if show_placeholder != self.placeholder_visible:
            self.placeholder_visible = show_placeholder
            if show_placeholder:
                self.placeholder.place(x=self.PLACEHOLDER_X, y=self.PLACEHOLDER_Y)
            else:
                self.placeholder.place_forget()

        # Скільки рядків займає текст на екрані (довгі рядки переносяться)
        lines = display_lines(self._textbox) or text.count("\n") + 1
        lines = max(1, min(self.MAX_LINES, lines))
        if lines != self.visible_lines:
            self.visible_lines = lines
            self.configure(height=self.line_height * lines + 12)
        if lines == self.MAX_LINES:
            self._textbox.see("insert")

    def get(self, *args):
        # Без аргументів повертає весь текст, як у звичайного однорядкового поля
        if args:
            return super().get(*args)
        return super().get("1.0", "end-1c")

    def clear(self):
        self.delete("1.0", "end")
        self._refresh()

    def set_text(self, text):
        self.delete("1.0", "end")
        self.insert("1.0", text)
        self._refresh()


# ---------- Плавна поява ----------


def _mix(start, end, t):
    a = [int(start[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(end[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _is_hex(color):
    return isinstance(color, str) and color.startswith("#") and len(color) == 7


def fade_in(widgets, duration=180, steps=9):
    """Плавно проявляє текст у віджетах: колір літер переходить від кольору тла до справжнього.

    Перефарбовуємо лише текст, бо це дешево і анімація не гальмує.
    Повертає функцію: її викликають одразу (перший кадр, текст ще невидимий), далі анімація йде сама.
    """
    texts = []   # SelectableText
    labels = []  # написи і кнопки customtkinter: (віджет, колір тла під ним)

    def background_of(widget):
        # Колір рамки, на якій лежить віджет (картка, бульбашка чи тло вікна)
        parent = widget.master
        while parent is not None:
            try:
                color = parent.cget("fg_color")
            except (ValueError, tk.TclError, AttributeError):
                color = None
            if color not in (None, "transparent"):
                return color
            parent = parent.master
        return theme.BG

    def collect(widget):
        if isinstance(widget, SelectableText):
            texts.append(widget)
            return
        if isinstance(widget, (ctk.CTkLabel, ctk.CTkButton)) and widget.cget("text"):
            labels.append((widget, widget.cget("text_color"), background_of(widget)))
        for child in widget.winfo_children():
            collect(child)

    for widget in widgets:
        collect(widget)

    def frame(index):
        t = min(1.0, index / steps)
        eased = 1 - (1 - t) ** 3  # швидко на початку, м'яко в кінці
        done = index >= steps
        for item in texts:
            if item.winfo_exists():
                end = themed(item.text_color)
                item.apply_colors(None if done else _mix(themed(item.bg_color), end, eased))
        for widget, color, background in labels:
            if not widget.winfo_exists():
                continue
            if done:
                widget.configure(text_color=color)  # знову пара кольорів для обох тем
            elif _is_hex(themed(color)) and _is_hex(themed(background)):
                widget.configure(text_color=_mix(themed(background), themed(color), eased))
        if not done and widgets and widgets[0].winfo_exists():
            widgets[0].after(duration // steps, frame, index + 1)

    return lambda: frame(0)
