# Збереження чатів у файл JSON.
# Чат це назва і список повідомлень. Види повідомлень (поле "kind"):
#   "user"       текст користувача
#   "assistant"  текстова відповідь Linum
#   "image"      створене або змінене зображення
#   без "kind"   старий формат: запит користувача і зображення разом

import json
import uuid
from datetime import datetime
from pathlib import Path

NEW_CHAT_TITLE = "Новий чат"


def _now():
    return datetime.now().isoformat(timespec="seconds")


class ChatStore:
    def __init__(self, path):
        self.path = Path(path)
        self.chats = []
        self.load()

    def load(self):
        if not self.path.exists():
            return
        try:
            self.chats = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self.chats = []

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Спершу пишемо в тимчасовий файл, а потім підміняємо.
        # Так чати не зіпсуються, якщо програма закриється посеред запису.
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(self.chats, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def sorted_chats(self):
        return sorted(self.chats, key=lambda chat: chat["updated"], reverse=True)

    def get(self, chat_id):
        for chat in self.chats:
            if chat["id"] == chat_id:
                return chat
        return None

    def create_chat(self):
        now = _now()
        chat = {
            "id": uuid.uuid4().hex,
            "title": NEW_CHAT_TITLE,
            "created": now,
            "updated": now,
            "messages": [],
        }
        self.chats.append(chat)
        self.save()
        return chat

    def add_message(self, chat_id, message):
        chat = self.get(chat_id)
        if chat is None:
            return
        chat["messages"].append(message)
        title = message.get("text") or message.get("prompt") or ("Фото" if message.get("attachment") else "")
        if chat["title"] == NEW_CHAT_TITLE and title:
            chat["title"] = " ".join(title.split())[:60]
        chat["updated"] = _now()
        self.save()

    def delete_chat(self, chat_id):
        self.chats = [chat for chat in self.chats if chat["id"] != chat_id]
        self.save()
