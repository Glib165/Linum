# Мозок Linum: мовна модель, яка розмовляє з користувачем
# і вирішує, що робити: просто відповісти, намалювати нове фото чи змінити останнє.
#
# Особистість (хто вона така) записана в models/llm/Gaia.Modelfile.
#
# Перевірка в консолі, з папки E:\Linum:
#   python -m src.ai.brain

import json
import re
import time
from pathlib import Path

import httpx
import ollama

from config.config import LLM_MODEL

MODELFILE = Path("models/llm/Gaia.Modelfile")

# Скільки модель лишається в пам'яті після відповіді
KEEP_ALIVE = "30m"

# Скільки останніх повідомлень чату показувати моделі
HISTORY_LIMIT = 20

# Правила, за якими мозок вирішує, що робити. Модель відповідає у форматі JSON,
# щоб програма точно розуміла її рішення.
RULES = """
Ти працюєш усередині програми Linum і можеш сама запускати художню модель.
Кожну відповідь давай як JSON з полями:
- "action": одне з "chat", "image", "edit".
- "reply": коротка відповідь користувачу його мовою.
- "prompt": для "image" і "edit" детальний опис зображення АНГЛІЙСЬКОЮ для художньої моделі Stable Diffusion:
  головний предмет, деталі, оточення, освітлення, ракурс; 20-60 слів через кому. Для "chat" порожній рядок.
- "strength": тільки для "edit": від 0.3 (трохи підправити) до 0.75 (сильно змінити). Для інших 0.

Як обирати action:
- "image": користувач просить намалювати, створити, згенерувати, показати нове зображення.
- "edit": користувач просить змінити ОСТАННЄ зображення з цього чату: колір, прибрати чи додати щось,
  інший стиль, пору року, час доби. У "prompt" опиши ВСЕ зображення таким, яким воно має стати,
  а не лише зміну. Саму зміну пиши на початку "prompt" і чітко (наприклад "red robot, ...").
  Якщо щось треба прибрати, просто не згадуй цього в "prompt".
- "chat": усе інше: розмова, питання, поради, пояснення.

Користувач може надіслати своє фото, і ти його бачиш.
- Якщо питає про фото (що на ньому, оціни, порадь) або просто надіслав його без прохання: "chat", опиши, що бачиш.
- Якщо просить змінити своє фото: "edit". Його фото тоді вважається останнім зображенням чату.
  У "prompt" опиши, що реально є на фото (люди, предмети, фон, світло), уже з потрібною зміною.
  Для невеликих змін (колір, освітлення, погода) strength 0.35-0.5, для сильних (інший стиль, пора року) 0.55-0.75.

Для "image" і "edit" у "reply" одним реченням скажи, що робиш. Не переписуй туди "prompt".
Ніколи не використовуй емодзі.
У "reply" можна переносити рядки (\\n), наприклад для списків або коли користувач сам пише кількома рядками.
"""

# Емодзі та інші піктограми, які програма прибирає з відповідей
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")


def clean(text):
    # Прибирає емодзі і зайві пробіли, але залишає переноси рядків
    lines = [re.sub(r"[ \t]{2,}", " ", line).strip() for line in EMOJI.sub("", text).split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()

DECISION_FORMAT = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["chat", "image", "edit"]},
        "reply": {"type": "string"},
        "prompt": {"type": "string"},
        "strength": {"type": "number"},
    },
    "required": ["action", "reply", "prompt", "strength"],
}


def identity():
    # Беремо особистість із Modelfile, щоб вона була записана лише в одному місці
    if MODELFILE.exists():
        found = re.search(r'SYSTEM """(.*?)"""', MODELFILE.read_text(encoding="utf-8"), re.S)
        if found:
            return found.group(1).strip()
    return "Ти Gaia, штучний інтелект програми Linum."


def is_available():
    # Чи запущена Ollama і чи є в ній наша модель
    try:
        names = [model.model for model in ollama.list().models]
    except Exception:
        return False
    return any(name == LLM_MODEL or name.split(":")[0] == LLM_MODEL for name in names)


def warm_up():
    # Завантажує модель у пам'ять заздалегідь, щоб перша відповідь не чекала
    ollama.generate(model=LLM_MODEL, prompt="", keep_alive=KEEP_ALIVE)


def unload():
    # Звільняє пам'ять для художньої моделі
    try:
        ollama.generate(model=LLM_MODEL, prompt="", keep_alive=0)
    except Exception:
        pass


def chat(history):
    # Проста розмова без рішень. history це список {"role": ..., "content": ...}.
    # Модель сама нічого не пам'ятає, тому щоразу отримує розмову з початку.
    response = ollama.chat(model=LLM_MODEL, messages=history, think=False, keep_alive=KEEP_ALIVE)
    return response["message"]["content"]


def chat_with_retry(attempts=3, **request):
    # Якщо модель не завантажилась (наприклад, бракувало відеопам'яті), Ollama звільняє
    # пам'ять і наступна спроба зазвичай вдається. Тому пробуємо кілька разів з паузою.
    for attempt in range(attempts):
        try:
            return ollama.chat(**request)
        except (ollama.ResponseError, ConnectionError, OSError, httpx.HTTPError):
            if attempt == attempts - 1:
                raise
            time.sleep(3 * (attempt + 1))


def history_from_chat(messages):
    # Перетворює повідомлення чату Linum на розмову, зрозумілу моделі.
    # Саму картинку модель отримує лише з останнього фото користувача: кожне фото вона
    # розглядає кілька секунд, тож старі фото лише згадуємо словами.
    last_attachment = None
    for message in messages:
        if message.get("kind") == "user" and message.get("attachment") and Path(message["attachment"]).exists():
            last_attachment = message["attachment"]

    history = []
    for message in messages:
        kind = message.get("kind")
        if kind == "user":
            entry = {"role": "user", "content": message["text"] or "(фото без тексту)"}
            attachment = message.get("attachment")
            if attachment and attachment == last_attachment:
                entry["images"] = [Path(attachment).read_bytes()]
                entry["content"] = "[Користувач надіслав фото, воно додане до цього повідомлення]\n" + entry["content"]
            elif attachment:
                entry["content"] = "[Користувач раніше надсилав фото]\n" + entry["content"]
            history.append(entry)
        elif kind == "assistant":
            history.append({"role": "assistant", "content": message["text"]})
        elif message.get("image"):
            if kind is None:
                # Старі повідомлення: запит і картинка разом
                history.append({"role": "user", "content": message["prompt"]})
            note = f"[У чаті з'явилося зображення. Опис для художника: {message.get('prompt_en', '')}]"
            history.append({"role": "assistant", "content": note})
    return history[-HISTORY_LIMIT:]


def decide(history):
    """Повертає рішення: {"action", "reply", "prompt", "strength"}."""
    messages = [{"role": "system", "content": identity() + "\n" + RULES}] + history
    response = chat_with_retry(
        model=LLM_MODEL,
        messages=messages,
        format=DECISION_FORMAT,
        think=False,
        keep_alive=KEEP_ALIVE,
        options={"temperature": 0.6},
    )
    try:
        decision = json.loads(response["message"]["content"])
    except json.JSONDecodeError:
        return {"action": "chat", "reply": clean(response["message"]["content"]), "prompt": "", "strength": 0}

    action = decision.get("action")
    if action not in ("chat", "image", "edit"):
        action = "chat"
    prompt = str(decision.get("prompt") or "").strip()
    if action != "chat" and not prompt:
        action = "chat"
    try:
        strength = float(decision.get("strength") or 0.55)
    except (TypeError, ValueError):
        strength = 0.55
    return {
        "action": action,
        "reply": clean(str(decision.get("reply") or "")),
        "prompt": prompt,
        "strength": min(0.8, max(0.25, strength)),
    }


if __name__ == "__main__":
    history = []
    print("Розмова з Linum. Щоб вийти, напишіть: вихід")
    while True:
        text = input("Ви: ")
        if text.strip().lower() == "вихід":
            break
        history.append({"role": "user", "content": text})
        decision = decide(history)
        history.append({"role": "assistant", "content": decision["reply"]})
        print("Linum:", decision["reply"])
        if decision["action"] != "chat":
            print(f"   [{decision['action']}] {decision['prompt']}")
