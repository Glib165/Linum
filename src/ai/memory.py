# Пам'ять Gaia про користувача: що вона знає про вас між різними чатами
# ("просить звертатися на «ти»", "любить темні, похмурі тони").
# Gaia записує сюди факти сама, коли ви розповідаєте про себе, і читає їх у кожному новому чаті.
# Факти лежать у data/memory.json, їх видно і можна видалити в Налаштування -> Пам'ять.

import json
import uuid
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path("data/memory.json")


def load():
    # Усі факти списком. Якщо файлу ще немає, фактів немає.
    if not MEMORY_FILE.exists():
        return []
    try:
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save(facts):
    # Спершу в тимчасовий файл, потім підміна: так пам'ять не зіпсується, якщо зникне світло
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = MEMORY_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(MEMORY_FILE)


def add(text):
    """Записує новий факт і повертає його."""
    facts = load()
    fact = {
        "id": uuid.uuid4().hex,
        "text": text,
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    facts.append(fact)
    save(facts)
    return fact


def remove(fact_id):
    """Видаляє факт за його "id"."""
    facts = load()
    facts = [fact for fact in facts if fact["id"] != fact_id]
    save(facts)


def as_prompt():
    """Факти одним текстом для Gaia, або "" якщо вона ще нічого не знає."""
    facts = load()
    if not facts:
        return ""
    lines = [f"- {fact['text']}" for fact in facts]
    return ("Що ти пам'ятаєш про користувача з попередніх розмов:\n" + "\n".join(lines) + "\n"
            "Його смаки (улюблені кольори, настрій, стилі) обов'язково втілюй у кожному описі для художника "
            "(\"prompt\"), якщо в цьому проханні він не попросив інакше. Не згадуй пам'ять у відповіді без потреби.")
