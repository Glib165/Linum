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
- "targets": тільки для "edit", коли зміна стосується конкретного предмета на фото (прибрати його,
  перефарбувати, замінити, змінити): 2-3 варіанти короткої англійської назви цього предмета, 1-2 слова кожен.
  Називай те, що реально ВИДНО на зображенні, а не слова користувача. Якщо користувач каже
  "ота штука внизу" або "літаюча штука", подивись на фото і назви, що це: ["helmet", "robot head", "metal object"].
  Якщо користувач просить перефарбувати чи змінити головний об'єкт (наприклад "зроби робота червоним"),
  це теж предмет: ["robot", "metal robot"].
  Порожній список лише тоді, коли змінюється все фото цілком: стиль, пора року, освітлення, час доби.
- "where": де на фото цей предмет: "top", "bottom", "left", "right", "center", "top-left", "top-right",
  "bottom-left", "bottom-right". Подивись на зображення. Якщо предмет займає майже все фото або "targets" порожній, "".
- "remove": true, якщо цей предмет треба прибрати. Тоді "prompt" описує, що має бути на його місці
  (фон, підлога, небо), наприклад "empty grey studio floor, soft shadow". Інакше false.
- "colors": тільки для "edit", коли треба ЛИШЕ змінити колір предмета, а форма і все інше лишаються
  (перефарбувати, поміняти кольори місцями). Список змін {"from": ..., "to": ...}, кольори у форматі "#RRGGBB".
  "from" - колір, який ЗАРАЗ є на предметі (подивись на фото), або "", якщо весь предмет стає одного кольору.
  "to" - новий колір. "targets" тоді називає весь предмет.
  Приклади:
  "зроби робота червоним": [{"from": "", "to": "#C62828"}]
  "поміняй місцями червоний і чорний": [{"from": "#8E2B2B", "to": "#1C1C1C"}, {"from": "#1C1C1C", "to": "#8E2B2B"}]
  "хай червоне буде зверху, а чорне знизу", коли на фото навпаки: це теж обмін, як у прикладі вище.
  "зроби червоні частини синіми": [{"from": "#B71C1C", "to": "#1E4FB0"}]
  "part" - у яку частину предмета йде колір: "top", "bottom", "left", "right" або "" (весь предмет).
  Потрібно, коли користувач хоче змінити, ДЕ на предметі який колір (наприклад, кольори порівну, навпіл):
  "зроби прапор навпіл: червоний зверху, чорний знизу":
  [{"from": "", "to": "#C62828", "part": "top"}, {"from": "", "to": "#1C1C1C", "part": "bottom"}]
  Якщо змінюється не лише колір (форма, новий предмет, стиль, освітлення) або все фото цілком: [].

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

WHERE = ["top", "bottom", "left", "right", "center", "top-left", "top-right", "bottom-left", "bottom-right"]
PARTS = ["top", "bottom", "left", "right"]

DECISION_FORMAT = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["chat", "image", "edit"]},
        "reply": {"type": "string"},
        "prompt": {"type": "string"},
        "strength": {"type": "number"},
        "targets": {"type": "array", "items": {"type": "string"}},
        "where": {"type": "string", "enum": ["", *WHERE]},
        "remove": {"type": "boolean"},
        "colors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "part": {"type": "string", "enum": ["", *PARTS]},
                },
                "required": ["from", "to", "part"],
            },
        },
    },
    "required": ["action", "reply", "prompt", "strength", "targets", "where", "remove", "colors"],
}

# Рамка предмета: [верх, лівий край, низ, правий край] у частках від 0 до 1000.
# Саме в такому вигляді модель навчена позначати предмети на фото.
BOX_FORMAT = {
    "type": "object",
    "properties": {"box_2d": {"type": "array", "items": {"type": "integer"}}},
    "required": ["box_2d"],
}

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


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


def unload(wait=15):
    # Звільняє пам'ять для художньої моделі і чекає, поки Ollama справді її віддасть.
    # Якщо художник почне раніше, йому не вистачить відеопам'яті і він працюватиме в рази повільніше.
    try:
        ollama.generate(model=LLM_MODEL, prompt="", keep_alive=0)
        deadline = time.time() + wait
        while time.time() < deadline and ollama.ps().models:
            time.sleep(0.3)
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


def latest_image(messages):
    # Останнє зображення в чаті: створене Linum або надіслане користувачем
    for message in reversed(messages):
        for key in ("image", "attachment"):
            if message.get(key) and Path(message[key]).exists():
                return message[key]
    return None


def history_from_chat(messages):
    # Перетворює повідомлення чату Linum на розмову, зрозумілу моделі.
    # Модель бачить лише одне, останнє зображення чату: кожне фото вона розглядає
    # кілька секунд, тож старі фото лише згадуємо словами.
    visible = latest_image(messages)
    last_user = max((i for i, m in enumerate(messages) if m.get("kind") == "user"), default=None)

    history = []
    for index, message in enumerate(messages):
        kind = message.get("kind")
        if kind == "user":
            entry = {"role": "user", "content": message["text"] or "(фото без тексту)"}
            attachment = message.get("attachment")
            if attachment and attachment == visible:
                entry["images"] = [Path(attachment).read_bytes()]
                entry["content"] = "[Користувач надіслав фото, воно додане до цього повідомлення]\n" + entry["content"]
            elif attachment:
                entry["content"] = "[Користувач раніше надсилав фото]\n" + entry["content"]
            elif index == last_user and visible:
                # Показуємо останнє зображення, щоб модель бачила, про що мова ("прибери ось це")
                entry["images"] = [Path(visible).read_bytes()]
                entry["content"] = (
                    "[До цього повідомлення додано останнє зображення з чату, щоб ти бачила, про що мова]\n"
                    + entry["content"]
                )
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
    """Повертає рішення: {"action", "reply", "prompt", "strength", "targets", "where", "remove", "colors"}."""
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
        return {"action": "chat", "reply": clean(response["message"]["content"]), "prompt": "", "strength": 0,
                "targets": [], "where": "", "remove": False, "colors": []}

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
        # Назви предмета для "шукача": лише перші кілька слів, бо він розуміє короткі назви
        "targets": clean_targets(decision.get("targets")) if action == "edit" else [],
        "where": decision.get("where") if decision.get("where") in WHERE and action == "edit" else "",
        "remove": bool(decision.get("remove")) and action == "edit",
        "colors": clean_colors(decision.get("colors")) if action == "edit" and not decision.get("remove") else [],
    }


def clean_colors(colors):
    # Лишаємо тільки правильні зміни кольору: "to" обов'язково у форматі #RRGGBB
    result = []
    for change in colors if isinstance(colors, list) else []:
        if not isinstance(change, dict) or not HEX.match(str(change.get("to", ""))):
            continue
        start = str(change.get("from") or "")
        part = change.get("part") if change.get("part") in PARTS else ""
        result.append({"from": start if HEX.match(start) else "", "to": change["to"], "part": part})
    if any(not change["from"] and not change["part"] for change in result):
        # "Весь предмет одним кольором" не поєднується з іншими змінами
        result = [next(change for change in result if not change["from"] and not change["part"])]
    return result[:4]


def locate(image_path, name, where=""):
    """Просить Gaia обвести предмет рамкою. Повертає (x1, y1, x2, y2) у пікселях або None."""
    from PIL import Image

    hint = f" It is in the {where.replace('-', ' ')} part of the image." if where else ""
    try:
        response = chat_with_retry(
            model=LLM_MODEL,
            messages=[{
                "role": "user",
                "content": f"Detect the {name} in the image.{hint} Return its bounding box as box_2d "
                           "[ymin, xmin, ymax, xmax] normalized to 0-1000.",
                "images": [Path(image_path).read_bytes()],
            }],
            format=BOX_FORMAT,
            think=False,
            keep_alive=KEEP_ALIVE,
            options={"temperature": 0},
        )
        top, left, bottom, right = [min(1000.0, max(0.0, float(v))) for v in
                                    json.loads(response["message"]["content"])["box_2d"][:4]]
        with Image.open(image_path) as image:
            width, height = image.size
    except Exception:
        return None
    if right - left < 10 or bottom - top < 10:
        return None
    return left * width / 1000, top * height / 1000, right * width / 1000, bottom * height / 1000


def clean_targets(targets):
    if isinstance(targets, str):
        targets = [targets]
    result = []
    for target in targets or []:
        short = " ".join(str(target).split()[:3]).strip().lower()
        if short and short not in result:
            result.append(short)
    return result[:3]


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
