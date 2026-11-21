# Збереження налаштувань користувача (тема, вибрана модель) у файл JSON.

import json
from pathlib import Path

from config.config import DEFAULT_MODEL, DEFAULT_REASONING


DEFAULTS = {
    "theme": "system",
    "model": DEFAULT_MODEL,
    "sidebar": True,
    "style": "Без стилю",
    "size": "Квадрат 1:1",
    "name": "",
    # Профіль (лише на цьому комп'ютері): прізвище, пошта, фото (шлях до файлу) і кілька слів про себе для Gaia
    "surname": "",
    "email": "",
    "avatar": "",
    "about": "",
    "quality_boost": True,
    "translate": True,
    "reasoning": DEFAULT_REASONING,
    "language": "uk",
}


class SettingsStore:
    def __init__(self, path):
        self.path = Path(path)
        self.values = dict(DEFAULTS)
        if self.path.exists():
            try:
                self.values.update(json.loads(self.path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass

    def get(self, key):
        return self.values.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self.values[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.values, ensure_ascii=False, indent=2), encoding="utf-8")
