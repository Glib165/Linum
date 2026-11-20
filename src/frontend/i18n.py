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
    # Решта інтерфейсу
    "no_model_files": {"uk": "Не знайдено жодного файлу моделі. Покладіть його в models/checkpoints", "en": "No model file found. Put one into models/checkpoints", "ru": "Не найдено ни одного файла модели. Положите его в models/checkpoints"},
    "profile": {"uk": "Профіль", "en": "Profile", "ru": "Профиль"},
    "choose_photo": {"uk": "Оберіть фото", "en": "Choose a photo", "ru": "Выберите фото"},
    "images": {"uk": "Зображення", "en": "Images", "ru": "Изображения"},
    "all_files": {"uk": "Усі файли", "en": "All files", "ru": "Все файлы"},
    "open_photo_failed": {"uk": "Не вдалося відкрити фото: {error}", "en": "Could not open the photo: {error}", "ru": "Не удалось открыть фото: {error}"},
    "your_photo": {"uk": "Ваше фото", "en": "Your photo", "ru": "Ваше фото"},
    "archive": {"uk": "Архів", "en": "Archive", "ru": "Архив"},
    "nothing_found": {"uk": "Нічого не знайдено", "en": "Nothing found", "ru": "Ничего не найдено"},
    "empty_here": {"uk": "Тут порожньо", "en": "Nothing here yet", "ru": "Здесь пусто"},
    "chats_will_appear": {"uk": "Тут з'являться ваші чати", "en": "Your chats will appear here", "ru": "Здесь появятся ваши чаты"},
    "open_new_window": {"uk": "Відкрити в новому вікні", "en": "Open in new window", "ru": "Открыть в новом окне"},
    "mark_read": {"uk": "Позначити прочитаним", "en": "Mark as read", "ru": "Отметить прочитанным"},
    "mark_unread": {"uk": "Позначити непрочитаним", "en": "Mark as unread", "ru": "Отметить непрочитанным"},
    "acc_unread": {"uk": "Н", "en": "U", "ru": "Н"},
    "pin": {"uk": "Закріпити", "en": "Pin", "ru": "Закрепить"},
    "unpin": {"uk": "Відкріпити", "en": "Unpin", "ru": "Открепить"},
    "acc_pin": {"uk": "З", "en": "P", "ru": "З"},
    "rename": {"uk": "Перейменувати", "en": "Rename", "ru": "Переименовать"},
    "acc_rename": {"uk": "П", "en": "R", "ru": "П"},
    "add_to_project": {"uk": "Додати до проєкту", "en": "Add to project", "ru": "Добавить в проект"},
    "new_project_dots": {"uk": "Новий проєкт...", "en": "New project...", "ru": "Новый проект..."},
    "remove_from_project": {"uk": "Прибрати з проєкту", "en": "Remove from project", "ru": "Убрать из проекта"},
    "move_to_section": {"uk": "Перемістити до розділу", "en": "Move to section", "ru": "Переместить в раздел"},
    "new_section_dots": {"uk": "Новий розділ...", "en": "New section...", "ru": "Новый раздел..."},
    "remove_from_section": {"uk": "Прибрати з розділу", "en": "Remove from section", "ru": "Убрать из раздела"},
    "archive_action": {"uk": "Архівувати", "en": "Archive", "ru": "Архивировать"},
    "unarchive": {"uk": "Повернути з архіву", "en": "Restore from archive", "ru": "Вернуть из архива"},
    "acc_archive": {"uk": "А", "en": "A", "ru": "А"},
    "delete": {"uk": "Видалити", "en": "Delete", "ru": "Удалить"},
    "acc_delete": {"uk": "В", "en": "D", "ru": "У"},
    "new_project": {"uk": "Новий проєкт", "en": "New project", "ru": "Новый проект"},
    "new_section": {"uk": "Новий розділ", "en": "New section", "ru": "Новый раздел"},
    "project_name": {"uk": "Назва проєкту:", "en": "Project name:", "ru": "Название проекта:"},
    "section_name": {"uk": "Назва розділу:", "en": "Section name:", "ru": "Название раздела:"},
    "delete_chat": {"uk": "Видалити чат", "en": "Delete chat", "ru": "Удалить чат"},
    "delete_chat_question": {"uk": "Видалити чат «{title}»?\nЗображення залишаться в папці outputs.", "en": "Delete the chat “{title}”?\nThe images will stay in the outputs folder.", "ru": "Удалить чат «{title}»?\nИзображения останутся в папке outputs."},
    "recent_images": {"uk": "Останні зображення", "en": "Recent images", "ru": "Последние изображения"},
    "all": {"uk": "Усі", "en": "All", "ru": "Все"},
    "images_will_appear": {"uk": "Тут з'являться створені зображення", "en": "Your images will appear here", "ru": "Здесь появятся созданные изображения"},
    "translation_line": {"uk": "Переклад {source}: {text}", "en": "Translated {source}: {text}", "ru": "Перевод {source}: {text}"},
    "from_ukrainian": {"uk": "з української", "en": "from Ukrainian", "ru": "с украинского"},
    "from_russian": {"uk": "з російської", "en": "from Russian", "ru": "с русского"},
    "thinking": {"uk": "Думаю...", "en": "Thinking...", "ru": "Думаю..."},
    "waking_up": {"uk": "Прокидаюся... {seconds} с (перша відповідь довша)", "en": "Waking up... {seconds} s (the first reply takes longer)", "ru": "Просыпаюсь... {seconds} с (первый ответ дольше)"},
    "image_missing": {"uk": "Файл зображення не знайдено", "en": "Image file not found", "ru": "Файл изображения не найден"},
    "review_recolored": {"uk": "Перевірка: {problem} Кольори виправлено перефарбуванням.",
                         "en": "Check: {problem} Colors fixed by recoloring.",
                         "ru": "Проверка: {problem} Цвета исправлены перекрашиванием."},
    "review_kept_first": {"uk": "Перевірка: {problem} Перемальований варіант вийшов гіршим, тож лишено перший.",
                          "en": "Check: {problem} The redrawn version was worse, so the first one was kept.",
                          "ru": "Проверка: {problem} Перерисованный вариант оказался хуже, поэтому оставлен первый."},
    "comparing": {"uk": "Порівнюю два варіанти", "en": "Comparing two versions", "ru": "Сравниваю два варианта"},
    "upscaled": {"uk": "Збільшено ×{scale}", "en": "Upscaled ×{scale}", "ru": "Увеличено ×{scale}"},
    "upscaling": {"uk": "Збільшую фото ×{scale}", "en": "Upscaling ×{scale}", "ru": "Увеличиваю фото ×{scale}"},
    "upscale_too_big": {"uk": "Фото вже велике: збільшене вийшло б завеликим", "en": "The image is already large: upscaling would make it too big",
                        "ru": "Фото уже большое: увеличенное получилось бы слишком большим"},
    "looking_for_place": {"uk": "Шукаю місце: {place}", "en": "Looking for the place: {place}", "ru": "Ищу место: {place}"},
    "adding": {"uk": "Додаю", "en": "Adding", "ru": "Добавляю"},
    "added_to": {"uk": "Додано: {place}", "en": "Added: {place}", "ru": "Добавлено: {place}"},
    "review_redrawn": {"uk": "Перевірка: {problem} Перемальовано.", "en": "Check: {problem} Redrawn.", "ru": "Проверка: {problem} Перерисовано."},
    "checked": {"uk": "Перевірено", "en": "Checked", "ru": "Проверено"},
    "recolored": {"uk": "Перефарбовано", "en": "Recolored", "ru": "Перекрашено"},
    "recolored_target": {"uk": "Перефарбовано: {target}", "en": "Recolored: {target}", "ru": "Перекрашено: {target}"},
    "removed_target": {"uk": "Прибрано: {target}", "en": "Removed: {target}", "ru": "Убрано: {target}"},
    "changed_target": {"uk": "Змінено: {target}", "en": "Changed: {target}", "ru": "Изменено: {target}"},
    "target_not_found": {"uk": "Не знайдено «{target}», змінено все фото", "en": "“{target}” not found, the whole photo was changed", "ru": "Не найдено «{target}», изменено всё фото"},
    "photo_edit": {"uk": "Зміна фото", "en": "Photo edit", "ru": "Изменение фото"},
    "steps_count": {"uk": "{steps} кроків", "en": "{steps} steps", "ru": "{steps} шагов"},
    "seconds_short": {"uk": "{seconds} с", "en": "{seconds} s", "ru": "{seconds} с"},
    "preparing": {"uk": "Готую запит", "en": "Preparing the request", "ru": "Готовлю запрос"},
    "prompt_copied": {"uk": "Запит скопійовано", "en": "Prompt copied", "ru": "Запрос скопирован"},
    "model_missing": {"uk": "Модель {name} ще не додана. Покладіть файл сюди: {path}", "en": "The {name} model is not added yet. Put its file here: {path}", "ru": "Модель {name} ещё не добавлена. Положите файл сюда: {path}"},
    "loading_model": {"uk": "Завантажую модель {name}...", "en": "Loading the {name} model...", "ru": "Загружаю модель {name}..."},
    "model_load_failed": {"uk": "Не вдалося завантажити модель {name}: {error}", "en": "Could not load the {name} model: {error}", "ru": "Не удалось загрузить модель {name}: {error}"},
    "thanks_lesson": {"uk": "Дякую! Linum зробить з цього урок.", "en": "Thank you! Linum will learn from this.", "ru": "Спасибо! Linum извлечёт из этого урок."},
    "rating_removed": {"uk": "Оцінку знято", "en": "Rating removed", "ru": "Оценка снята"},
    "lesson_learned": {"uk": "Linum запам'ятав: {text}", "en": "Linum learned: {text}", "ru": "Linum запомнил: {text}"},
    "stopping": {"uk": "Зупиняю після поточного кроку...", "en": "Stopping after the current step...", "ru": "Останавливаю после текущего шага..."},
    "training_not_ready": {"uk": "Зачекайте: художник або мозок ще не готові, чи Linum зараз зайнятий.", "en": "Please wait: the artist or the brain is not ready yet, or Linum is busy.", "ru": "Подождите: художник или мозг ещё не готовы, или Linum сейчас занят."},
    "stop": {"uk": "Зупинити", "en": "Stop", "ru": "Остановить"},
    "start": {"uk": "Почати", "en": "Start", "ru": "Начать"},
    "round_error": {"uk": "Помилка в раунді: {error}", "en": "Error in the round: {error}", "ru": "Ошибка в раунде: {error}"},
    "round_lesson": {"uk": "Раунд {round}. Новий урок: {text}", "en": "Round {round}. New lesson: {text}", "ru": "Раунд {round}. Новый урок: {text}"},
    "round_ok": {"uk": "Раунд {round}. Критик не знайшов помилок у завданні: {request}", "en": "Round {round}. The Critic found no mistakes in the task: {request}", "ru": "Раунд {round}. Критик не нашёл ошибок в задании: {request}"},
    "round_nothing": {"uk": "Раунд {round} без нового уроку.", "en": "Round {round} without a new lesson.", "ru": "Раунд {round} без нового урока."},
    "training_done": {"uk": "Тренування завершено: раундів {rounds}, нових уроків {learned}.", "en": "Training finished: {rounds} rounds, {learned} new lessons.", "ru": "Тренировка завершена: раундов {rounds}, новых уроков {learned}."},
    "write_first": {"uk": "Спершу напишіть повідомлення", "en": "Write a message first", "ru": "Сначала напишите сообщение"},
    "photo_needs_gaia": {"uk": "Щоб працювати з фото, потрібна Gaia. Запустіть Ollama.", "en": "Gaia is needed to work with photos. Start Ollama.", "ru": "Чтобы работать с фото, нужна Gaia. Запустите Ollama."},
    "brain_unavailable": {"uk": "Мозок Linum недоступний (запустіть Ollama). Поки що лише малюю за описом.", "en": "Linum's brain is unavailable (start Ollama). For now I only draw from the description.", "ru": "Мозг Linum недоступен (запустите Ollama). Пока только рисую по описанию."},
    "linum_thinking": {"uk": "Linum думає...", "en": "Linum is thinking...", "ru": "Linum думает..."},
    "linum_reasoning": {"uk": "Linum міркує, це може зайняти хвилину-дві...", "en": "Linum is reasoning, this may take a minute or two...", "ru": "Linum размышляет, это может занять минуту-две..."},
    "reason_memory": {"uk": "не вистачило пам'яті, щоб завантажитися", "en": "not enough memory to load", "ru": "не хватило памяти, чтобы загрузиться"},
    "reason_ollama": {"uk": "Ollama не запущена", "en": "Ollama is not running", "ru": "Ollama не запущена"},
    "gaia_failed": {"uk": "Gaia не змогла відповісти: {reason}.", "en": "Gaia could not reply: {reason}.", "ru": "Gaia не смогла ответить: {reason}."},
    "retry": {"uk": "Повторити", "en": "Retry", "ru": "Повторить"},
    "artist_loading": {"uk": "Художня модель ще завантажується. Повторіть прохання за хвилину.", "en": "The art model is still loading. Please repeat your request in a minute.", "ru": "Художественная модель ещё загружается. Повторите просьбу через минуту."},
    "creating_with_model": {"uk": "Створюю зображення моделлю {model}...", "en": "Creating an image with {model}...", "ru": "Создаю изображение моделью {model}..."},
    "searching_for": {"uk": "Шукаю: {target}", "en": "Looking for: {target}", "ru": "Ищу: {target}"},
    "removing": {"uk": "Прибираю", "en": "Removing", "ru": "Убираю"},
    "editing_image": {"uk": "Змінюю зображення", "en": "Editing the image", "ru": "Изменяю изображение"},
    "creating_image": {"uk": "Створюю зображення", "en": "Creating the image", "ru": "Создаю изображение"},
    "recoloring": {"uk": "Перефарбовую", "en": "Recoloring", "ru": "Перекрашиваю"},
    "checking_result": {"uk": "Перевіряю результат", "en": "Checking the result", "ru": "Проверяю результат"},
    "redrawing": {"uk": "Перемальовую", "en": "Redrawing", "ru": "Перерисовываю"},
    "translation_short": {"uk": "Переклад: {text}", "en": "Translation: {text}", "ru": "Перевод: {text}"},
    "step_of": {"uk": "Крок {step} з {total}", "en": "Step {step} of {total}", "ru": "Шаг {step} из {total}"},
    "done_in": {"uk": "Готово за {seconds} с", "en": "Done in {seconds} s", "ru": "Готово за {seconds} с"},
    "create_failed": {"uk": "Не вдалося створити зображення: {error}", "en": "Could not create the image: {error}", "ru": "Не удалось создать изображение: {error}"},
    "settings": {"uk": "Налаштування", "en": "Settings", "ru": "Настройки"},
    "light_theme": {"uk": "Світла тема", "en": "Light theme", "ru": "Светлая тема"},
    "dark_theme": {"uk": "Темна тема", "en": "Dark theme", "ru": "Тёмная тема"},
    "about": {"uk": "Про Linum", "en": "About Linum", "ru": "О Linum"},
    "close": {"uk": "Закрити", "en": "Close", "ru": "Закрыть"},
    "copy": {"uk": "Копіювати", "en": "Copy", "ru": "Копировать"},
    "go_to_chat": {"uk": "Перейти до чату", "en": "Go to chat", "ru": "Перейти в чат"},
    "copied": {"uk": "Скопійовано", "en": "Copied", "ru": "Скопировано"},
    "failed": {"uk": "Не вдалося", "en": "Failed", "ru": "Не удалось"},
    "wait_image": {"uk": "Зачекайте, поки створиться зображення", "en": "Please wait until the image is created", "ru": "Подождите, пока создастся изображение"},
    "general": {"uk": "Загальні", "en": "General", "ru": "Общие"},
    "appearance": {"uk": "Вигляд", "en": "Appearance", "ru": "Внешний вид"},
    "generation": {"uk": "Генерація", "en": "Generation", "ru": "Генерация"},
    "experience": {"uk": "Досвід", "en": "Experience", "ru": "Опыт"},
    "storage": {"uk": "Сховище", "en": "Storage", "ru": "Хранилище"},
    "your_name": {"uk": "Ваше ім'я", "en": "Your name", "ru": "Ваше имя"},
    "your_name_hint": {"uk": "Так Linum звертатиметься до вас на головному екрані", "en": "This is how Linum will greet you on the home screen", "ru": "Так Linum будет обращаться к вам на главном экране"},
    "name_placeholder": {"uk": "Ім'я", "en": "Name", "ru": "Имя"},
    "translate_prompts": {"uk": "Перекладати запити", "en": "Translate prompts", "ru": "Переводить запросы"},
    "translate_hint": {"uk": "Українські й російські запити перекладаються англійською, бо модель розуміє лише її", "en": "Ukrainian and Russian prompts are translated into English, because the model only understands English", "ru": "Украинские и русские запросы переводятся на английский, потому что модель понимает только его"},
    "theme": {"uk": "Тема", "en": "Theme", "ru": "Тема"},
    "theme_hint": {"uk": "Системна тема підлаштовується під налаштування Windows", "en": "The system theme follows your Windows settings", "ru": "Системная тема подстраивается под настройки Windows"},
    "theme_light": {"uk": "Світла", "en": "Light", "ru": "Светлая"},
    "theme_dark": {"uk": "Темна", "en": "Dark", "ru": "Тёмная"},
    "theme_system": {"uk": "Системна", "en": "System", "ru": "Системная"},
    "sidebar": {"uk": "Бокова панель", "en": "Sidebar", "ru": "Боковая панель"},
    "sidebar_hint": {"uk": "Показувати список чатів зліва", "en": "Show the list of chats on the left", "ru": "Показывать список чатов слева"},
    "reasoning_level": {"uk": "Рівень міркувань", "en": "Reasoning level", "ru": "Уровень рассуждений"},
    "reasoning_hint": {"uk": "Низький найшвидший. Високий і Ультра думають перед відповіддю. Середній і Ультра перевіряють готову картинку", "en": "Low is the fastest. High and Ultra think before replying. Medium and Ultra check the finished image", "ru": "Низкий самый быстрый. Высокий и Ультра думают перед ответом. Средний и Ультра проверяют готовую картинку"},
    "model": {"uk": "Модель", "en": "Model", "ru": "Модель"},
    "model_hint": {"uk": "Fornax швидка, Gaia збалансована, Cygnus найкраща", "en": "Fornax is fast, Gaia is balanced, Cygnus is the best", "ru": "Fornax быстрая, Gaia сбалансированная, Cygnus лучшая"},
    "default_style": {"uk": "Стиль за замовчуванням", "en": "Default style", "ru": "Стиль по умолчанию"},
    "default_style_hint": {"uk": "Стиль, з яким відкривається новий чат", "en": "The style a new chat starts with", "ru": "Стиль, с которым открывается новый чат"},
    "default_size": {"uk": "Формат за замовчуванням", "en": "Default format", "ru": "Формат по умолчанию"},
    "default_size_hint": {"uk": "Портрет і альбом створюються довше за квадрат", "en": "Portrait and landscape take longer than square", "ru": "Портрет и альбом создаются дольше квадрата"},
    "quality_boost": {"uk": "Покращення якості", "en": "Quality boost", "ru": "Улучшение качества"},
    "quality_boost_hint": {"uk": "Просить модель уникати розмитості, зайвих пальців і деформацій", "en": "Asks the model to avoid blur, extra fingers and deformations", "ru": "Просит модель избегать размытия, лишних пальцев и деформаций"},
    "generation_steps": {"uk": "Кроки генерації", "en": "Generation steps", "ru": "Шаги генерации"},
    "steps_hint": {"uk": "{steps}. Змінюються у файлі config/config.py", "en": "{steps}. They are set in config/config.py", "ru": "{steps}. Меняются в файле config/config.py"},
    "experience_intro": {"uk": "Уроки, які Linum зробив зі своїх помилок і ваших оцінок. Gaia читає їх перед кожною картинкою. Якщо урок хибний, видаліть його.", "en": "Lessons Linum learned from its mistakes and your ratings. Gaia reads them before every image. If a lesson is wrong, delete it.", "ru": "Уроки, которые Linum извлёк из своих ошибок и ваших оценок. Gaia читает их перед каждой картинкой. Если урок ошибочный, удалите его."},
    "training": {"uk": "Тренування", "en": "Training", "ru": "Тренировка"},
    "training_hint": {"uk": "Агенти самі придумують завдання, малюють, перевіряють себе і записують уроки. Один раунд займає 2-5 хвилин. Поки йде тренування, малювати в чаті не можна.", "en": "Agents invent tasks, draw, check themselves and write down lessons. One round takes 2-5 minutes. You cannot draw in the chat during training.", "ru": "Агенты сами придумывают задания, рисуют, проверяют себя и записывают уроки. Один раунд занимает 2-5 минут. Пока идёт тренировка, рисовать в чате нельзя."},
    "no_lessons": {"uk": "Уроків поки немає. Оцініть кілька картинок кнопками під ними.", "en": "No lessons yet. Rate a few images with the buttons under them.", "ru": "Уроков пока нет. Оцените несколько картинок кнопками под ними."},
    "agent_trainer": {"uk": "Агент-Тренер", "en": "Trainer agent", "ru": "Агент-Тренер"},
    "agent_critic": {"uk": "Агент-Критик", "en": "Critic agent", "ru": "Агент-Критик"},
    "your_rating": {"uk": "Ваша оцінка", "en": "Your rating", "ru": "Ваша оценка"},
    "developer": {"uk": "Розробник", "en": "Developer", "ru": "Разработчик"},
    "images_stats": {"uk": "{count} шт., {megabytes} МБ", "en": "{count} images, {megabytes} MB", "ru": "{count} шт., {megabytes} МБ"},
    "open_folder": {"uk": "Відкрити папку", "en": "Open folder", "ru": "Открыть папку"},
    "models": {"uk": "Моделі", "en": "Models", "ru": "Модели"},
    "models_location": {"uk": "Файли моделей лежать у {path}", "en": "Model files are in {path}", "ru": "Файлы моделей лежат в {path}"},
    "chats": {"uk": "Чати", "en": "Chats", "ru": "Чаты"},
    "chats_stats": {"uk": "{count} шт. Видалення чатів не видаляє самих зображень", "en": "{count} chats. Deleting chats does not delete the images", "ru": "{count} шт. Удаление чатов не удаляет сами изображения"},
    "delete_all_chats": {"uk": "Видалити всі чати", "en": "Delete all chats", "ru": "Удалить все чаты"},
    "delete_all_question": {"uk": "Видалити всі чати?\nЗображення залишаться в папці outputs.", "en": "Delete all chats?\nThe images will stay in the outputs folder.", "ru": "Удалить все чаты?\nИзображения останутся в папке outputs."},
    "version": {"uk": "Версія {version}", "en": "Version {version}", "ru": "Версия {version}"},
    "after_model_load": {"uk": "Визначиться після завантаження моделі", "en": "Known after the model loads", "ru": "Определится после загрузки модели"},
    "gpu": {"uk": "Відеокарта", "en": "Graphics card", "ru": "Видеокарта"},
    "work_mode": {"uk": "Режим роботи", "en": "Mode", "ru": "Режим работы"},
    "work_mode_hint": {"uk": "Повна точність (fp32), частини моделі чекають своєї черги в оперативній пам'яті", "en": "Full precision (fp32), parts of the model wait their turn in RAM", "ru": "Полная точность (fp32), части модели ждут своей очереди в оперативной памяти"},
    "translation": {"uk": "Переклад", "en": "Translation", "ru": "Перевод"},
    "translation_hint": {"uk": "Helsinki-NLP opus-mt для української і російської, працює на процесорі", "en": "Helsinki-NLP opus-mt for Ukrainian and Russian, runs on the CPU", "ru": "Helsinki-NLP opus-mt для украинского и русского, работает на процессоре"},
    "ultra_note": {"uk": "думає найдовше, 3-6 хв на картинку", "en": "thinks the longest, 3-6 min per image", "ru": "думает дольше всех, 3-6 мин на картинку"},
    "choose_model": {"uk": "Оберіть модель", "en": "Choose a model", "ru": "Выберите модель"},
    "recommended": {"uk": "Рекомендована: {model}, {tier}", "en": "Recommended: {model}, {tier}", "ru": "Рекомендуемая: {model}, {tier}"},
    "default": {"uk": "За замовчуванням", "en": "Default", "ru": "По умолчанию"},
    "no_model_file": {"uk": "файлу моделі ще немає", "en": "model file is missing", "ru": "файла модели ещё нет"},
    "tier_fast": {"uk": "швидка", "en": "fast", "ru": "быстрая"},
    "tier_balanced": {"uk": "збалансована", "en": "balanced", "ru": "сбалансированная"},
    "tier_best": {"uk": "найкраща", "en": "best", "ru": "лучшая"},
    "cut": {"uk": "Вирізати", "en": "Cut", "ru": "Вырезать"},
    "paste": {"uk": "Вставити", "en": "Paste", "ru": "Вставить"},
    "copy_message": {"uk": "Копіювати все повідомлення", "en": "Copy the whole message", "ru": "Копировать всё сообщение"},
    "select_all": {"uk": "Виділити все", "en": "Select all", "ru": "Выделить всё"},
    "trainer_inventing": {"uk": "Тренер придумує завдання на тему «{topic}»...", "en": "The Trainer is inventing a task on “{topic}”...", "ru": "Тренер придумывает задание на тему «{topic}»..."},
    "trainer_task": {"uk": "Завдання: {request}\nАвтор пише опис...", "en": "Task: {request}\nThe Author is writing the description...", "ru": "Задание: {request}\nАвтор пишет описание..."},
    "artist_drawing": {"uk": "Художник малює...", "en": "The Artist is drawing...", "ru": "Художник рисует..."},
    "critic_checking": {"uk": "Критик перевіряє...", "en": "The Critic is checking...", "ru": "Критик проверяет..."},
    "critic_found": {"uk": "Критик знайшов проблему: {problem}\nПробуємо виправлений опис...", "en": "The Critic found a problem: {problem}\nTrying a corrected description...", "ru": "Критик нашёл проблему: {problem}\nПробуем исправленное описание..."},
    "critic_rechecking": {"uk": "Критик перевіряє виправлення...", "en": "The Critic is checking the fix...", "ru": "Критик проверяет исправление..."},
    "teacher_writing": {"uk": "Вчитель записує урок...", "en": "The Teacher is writing a lesson...", "ru": "Учитель записывает урок..."},
}


# Значення, які Linum зберігає в чатах і налаштуваннях (назви стилів, форматів, рівнів).
# Усередині вони лишаються українськими, щоб старі чати їх упізнавали, а на екрані перекладаються.
VALUES = {
    "Без стилю": {"en": "No style", "ru": "Без стиля"},
    "Фото": {"en": "Photo", "ru": "Фото"},
    "Кіно": {"en": "Cinema", "ru": "Кино"},
    "Аніме": {"en": "Anime", "ru": "Аниме"},
    "Олійний живопис": {"en": "Oil painting", "ru": "Масляная живопись"},
    "Акварель": {"en": "Watercolor", "ru": "Акварель"},
    "3D": {"en": "3D", "ru": "3D"},
    "Піксель-арт": {"en": "Pixel art", "ru": "Пиксель-арт"},
    "Ескіз": {"en": "Sketch", "ru": "Эскиз"},
    "Квадрат 1:1": {"en": "Square 1:1", "ru": "Квадрат 1:1"},
    "Портрет 2:3": {"en": "Portrait 2:3", "ru": "Портрет 2:3"},
    "Альбом 3:2": {"en": "Landscape 3:2", "ru": "Альбом 3:2"},
    "Низький": {"en": "Low", "ru": "Низкий"},
    "Середній": {"en": "Medium", "ru": "Средний"},
    "Високий": {"en": "High", "ru": "Высокий"},
    "Ультра": {"en": "Ultra", "ru": "Ультра"},
}

# Привітання на головному екрані: для кожної пори дня кілька варіантів, Linum бере один навмання.
# {name} - ім'я користувача. Якщо ім'я не вказане, разом з ним зникає і кома перед ним.
# "any" - привітання, які підходять для будь-якої пори дня.
GREETINGS = {
    "morning": {
        "uk": ["Доброго ранку, {name}", "Гарного ранку, {name}", "З добрим ранком, {name}", "Бадьорого ранку, {name}"],
        "en": ["Good morning, {name}", "Morning, {name}", "Rise and shine, {name}", "Have a bright morning, {name}"],
        "ru": ["Доброе утро, {name}", "С добрым утром, {name}", "Хорошего утра, {name}", "Бодрого утра, {name}"],
    },
    "afternoon": {
        "uk": ["Добрий день, {name}", "Гарного дня, {name}", "Вітаю, {name}", "Привіт, {name}"],
        "en": ["Good afternoon, {name}", "Hello, {name}", "Hi there, {name}", "Have a great day, {name}"],
        "ru": ["Добрый день, {name}", "Хорошего дня, {name}", "Приветствую, {name}", "Привет, {name}"],
    },
    "evening": {
        "uk": ["Добрий вечір, {name}", "Гарного вечора, {name}", "Затишного вечора, {name}", "Вечір добрий, {name}"],
        "en": ["Good evening, {name}", "Have a cozy evening, {name}", "Evening, {name}", "Nice to see you tonight, {name}"],
        "ru": ["Добрый вечер, {name}", "Хорошего вечера, {name}", "Уютного вечера, {name}", "Вечер добрый, {name}"],
    },
    "night": {
        "uk": ["Доброї ночі, {name}", "Не спиться, {name}?", "Нічне натхнення, {name}?", "Тиха ніч для творчості, {name}"],
        "en": ["Good night, {name}", "Can't sleep, {name}?", "Late-night inspiration, {name}?", "A quiet night to create, {name}"],
        "ru": ["Доброй ночи, {name}", "Не спится, {name}?", "Ночное вдохновение, {name}?", "Тихая ночь для творчества, {name}"],
    },
    "any": {
        "uk": ["З поверненням, {name}", "Радий вас бачити, {name}", "Що створимо сьогодні, {name}?", "Готовий малювати, {name}"],
        "en": ["Welcome back, {name}", "Good to see you, {name}", "What shall we create today, {name}?", "Ready to draw, {name}"],
        "ru": ["С возвращением, {name}", "Рад вас видеть, {name}", "Что создадим сегодня, {name}?", "Готов рисовать, {name}"],
    },
}

# Мова, якою зараз показується інтерфейс (встановлюється при запуску з налаштувань)
current = DEFAULT_LANGUAGE


def set_language(code):
    global current
    current = code if code in LANGUAGES else DEFAULT_LANGUAGE


def greeting(period, name, chance):
    """Одне привітання для пори дня ("morning", "afternoon", "evening", "night").

    chance: генератор випадкових чисел. Linum створює його один раз при запуску, тож поки
    програма відкрита, привітання не скаче, а при наступному запуску буде інше.
    """
    options = []
    for part in (period, "any"):
        texts = GREETINGS[part]
        options += texts.get(current) or texts[DEFAULT_LANGUAGE]
    text = chance.choice(options)
    if name:
        return text.replace("{name}", name)
    # Без імені: "Доброго ранку, {name}" стає "Доброго ранку", а "Не спиться, {name}?" стає "Не спиться?"
    return text.replace(", {name}", "").replace("{name}", "").strip()


def t(key):
    """Текст напису вибраною мовою. Якщо перекладу немає, український; якщо немає й ключа, сам ключ."""
    texts = TEXTS.get(key)
    if texts is None:
        return key
    return texts.get(current) or texts[DEFAULT_LANGUAGE]


def label(value):
    """Як показати на екрані збережене значення (наприклад, стиль "Кіно" англійською стає "Cinema")."""
    texts = VALUES.get(value)
    if texts is None:
        return value
    return texts.get(current) or value


def unlabel(shown, options):
    """Зворотне до label: з напису на екрані повертає збережене значення з options."""
    for value in options:
        if label(value) == shown:
            return value
    return shown
