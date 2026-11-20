# Переклад інтерфейсу Linum.
#
# Кожен напис має назву-ключ і текст для кожної мови. У коді замість самого тексту пишемо
# t("ключ"), і програма показує його вибраною мовою. Якщо перекладу на цю мову ще немає
# (порожній рядок), показується український текст, тож нічого не ламається.
#
# Щоб додати мову: дописати її в LANGUAGES і додати переклад у кожен напис нижче.

LANGUAGES = {
    "uk": "Українська",
    "en": "English",
    "ru": "Русский",
}
DEFAULT_LANGUAGE = "uk"

TEXTS = {
    # Бічна панель
    "new_chat": {"uk": "Новий чат", "en": "New chat", "ru": "Новый чат"},
    "search": {"uk": "Пошук", "en": "Search", "ru": "Поиск"},
    "gallery": {"uk": "Галерея", "en": "Gallery", "ru": "Галерея"},
    "images_folder": {"uk": "Папка із зображеннями", "en": "Folder with images", "ru": "Папка с изображениями"},
    "search_placeholder": {"uk": "Шукати в чатах", "en": "Search in chats", "ru": "Искать в чатах"},
    "pinned": {"uk": "Закріплені", "en": "Pinned", "ru": "Закреплённые"},
    "projects": {"uk": "Проєкти", "en": "Projects", "ru": "Проекты"},
    "recent": {"uk": "Нещодавні", "en": "Recent", "ru": "Недавние"},

    # Поле вводу
    "prompt_placeholder": {"uk": "Напишіть повідомлення або попросіть намалювати", "en": "Write a message or ask me to draw something", "ru": "Напишите сообщение или попросите нарисовать"},
    "send_hint": {"uk": "Enter надсилає, Shift+Enter переносить рядок", "en": "Enter sends, Shift+Enter adds a new line", "ru": "Enter отправляет, Shift+Enter переносит строку"},

    # Кнопки під картинкою
    "more_variant": {"uk": "Ще варіант", "en": "Another variant", "ru": "Ещё вариант"},
    "copy_prompt": {"uk": "Копіювати запит", "en": "Copy prompt", "ru": "Копировать запрос"},
    "open": {"uk": "Відкрити", "en": "Open", "ru": "Открыть"},
    "in_folder": {"uk": "У папці", "en": "Show in folder", "ru": "В папке"},

    # Привітання на головному екрані
    "good_morning": {"uk": "Доброго ранку", "en": "Good morning", "ru": "Доброе утро"},
    "good_afternoon": {"uk": "Добрий день", "en": "Good afternoon", "ru": "Добрый день"},
    "good_evening": {"uk": "Добрий вечір", "en": "Good evening", "ru": "Добрый вечер"},
    "good_night": {"uk": "Доброї ночі", "en": "Good night", "ru": "Доброй ночи"},

    # Налаштування мови
    "language": {"uk": "Мова інтерфейсу", "en": "Interface language", "ru": "Язык интерфейса"},
    "language_hint": {"uk": "Мова кнопок і написів. Gaia завжди відповідає мовою, якою ви пишете", "en": "Language of buttons and labels. Gaia always replies in the language you write in", "ru": "Язык кнопок и надписей. Gaia всегда отвечает на языке, на котором вы пишете"},
    "restart_title": {"uk": "Зміна мови", "en": "Language change", "ru": "Смена языка"},
    "restart_question": {"uk": "Мова зміниться після перезапуску Linum. Перезапустити зараз?", "en": "The language will change after Linum restarts. Restart now?", "ru": "Язык изменится после перезапуска Linum. Перезапустить сейчас?"},
}

# Мова, якою зараз показується інтерфейс (встановлюється при запуску з налаштувань)
current = DEFAULT_LANGUAGE


def set_language(code):
    global current
    current = code if code in LANGUAGES else DEFAULT_LANGUAGE


def t(key):
    """Текст напису вибраною мовою. Якщо перекладу немає, український; якщо немає й ключа, сам ключ."""
    texts = TEXTS.get(key)
    if texts is None:
        return key
    return texts.get(current) or texts[DEFAULT_LANGUAGE]
