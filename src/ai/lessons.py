# Зошит уроків Gaia: що вона дізналась з досвіду (з оцінок користувача і власних перевірок).
# Gaia читає ці уроки перед тим, як писати опис для художника, і не повторює старих помилок.
# Уроки лежать у data/lessons.json, їх можна прочитати й видалити.

import json
import uuid
from datetime import datetime
from pathlib import Path

LESSONS_FILE = Path("data/lessons.json")

# Скільки найсвіжіших уроків показувати Gaia (більше займає її пам'ять і сповільнює відповідь)
PROMPT_LIMIT = 30


def load():
    # Усі уроки списком. Якщо файлу ще немає, уроків немає.
    if not LESSONS_FILE.exists():
        return []
    try:
        return json.loads(LESSONS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save(lessons):
    # Спершу в тимчасовий файл, потім підміна: так зошит не зіпсується, якщо зникне світло
    LESSONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = LESSONS_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(lessons, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(LESSONS_FILE)


def add(text, source):
    """Додає урок і повертає його.

    text: сам урок, одне речення.
    source: звідки урок: "rating" (оцінка користувача) або "review" (перевірка Gaia).
    """
    lessons = load()
    lesson = {
        "id": uuid.uuid4().hex,
        "text": text,
        "source": source,
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    lessons.append(lesson)
    save(lessons)
    return lesson


def remove(lesson_id):
    """Видаляє урок за його "id"."""
    lessons = load()
    lessons = [lesson for lesson in lessons if lesson["id"] != lesson_id]
    save(lessons)


def words(text):
    # Слова уроку без розділових знаків і коротких службових слів
    cleaned = "".join(char.lower() if char.isalnum() else " " for char in text)
    return {word for word in cleaned.split() if len(word) > 2}


def similarity(first, second):
    # Яка частка слів спільна (від 0 до 1)
    first, second = words(first), words(second)
    return len(first & second) / len(first | second) if first and second else 0.0


def head(text):
    # Уроки зазвичай мають вигляд "проблема: порада". Перша частина - сама проблема.
    for mark in (":", ";", " - "):
        if mark in text:
            return text.split(mark, 1)[0]
    return ""


def is_known(text):
    """Чи є вже в зошиті такий самий урок: схожий цілком або про ту саму проблему."""
    for lesson in load():
        if similarity(text, lesson["text"]) >= 0.45:
            return True
        if len(words(head(text))) >= 4 and similarity(head(text), head(lesson["text"])) >= 0.7:
            return True
    return False


def as_prompt():
    """Свіжі уроки одним текстом для Gaia, або "" якщо уроків ще немає."""
    lessons = load()[-PROMPT_LIMIT:]
    if not lessons:
        return ""
    lines = [f"- {lesson['text']}" for lesson in lessons]
    return "Уроки з досвіду (обов'язково враховуй їх, коли пишеш prompt):\n" + "\n".join(lines)
