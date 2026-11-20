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
    "gallery": {"uk": "Галерея", "en": ""},
    "images_folder": {"uk": "Папка із зображеннями", "en": "Folder with images", "ru": "Папка с изображениями"},
    "search_placeholder": {"uk": "Шукати в чатах", "en": "Search in chats", "ru": "Искать в чатах"},
    "pinned": {"uk": "Закріплені", "en": "Pinned", "ru": "Закреплённые"},
    "projects": {"uk": "Проєкти", "en": "Projects", "ru": "Проекты"},
    "recent": {"uk": "Нещодавні", "en": "Recent", "ru": "Недавние"},

    # Поле вводу
    "prompt_placeholder": {"uk": "Напишіть повідомлення або попросіть намалювати", "en": ""},
    "send_hint": {"uk": "Enter надсилає, Shift+Enter переносить рядок", "en": ""},

    # Кнопки під картинкою
    "more_variant": {"uk": "Ще варіант", "en": ""},
    "copy_prompt": {"uk": "Копіювати запит", "en": ""},
    "open": {"uk": "Відкрити", "en": ""},
    "in_folder": {"uk": "У папці", "en": ""},

    # Привітання на головному екрані
    "good_morning": {"uk": "Доброго ранку", "en": ""},
    "good_afternoon": {"uk": "Добрий день", "en": ""},
    "good_evening": {"uk": "Добрий вечір", "en": ""},
    "good_night": {"uk": "Доброї ночі", "en": ""},

    # Налаштування мови
    "language": {"uk": "Мова інтерфейсу", "en": ""},
    "language_hint": {"uk": "Мова кнопок і написів. Gaia завжди відповідає мовою, якою ви пишете", "en": ""},
    "restart_title": {"uk": "Зміна мови", "en": ""},
    "restart_question": {"uk": "Мова зміниться після перезапуску Linum. Перезапустити зараз?", "en": ""},
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
