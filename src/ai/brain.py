# Мозок Linum: мовна модель, яка розмовляє з користувачем
# і вирішує, що робити: просто відповісти, намалювати нове фото чи змінити останнє.
#
# Особистість (хто вона така) записана в models/llm/Gaia.Modelfile.
#
# Перевірка в консолі, з папки E:\Linum:
#   python -m src.ai.brain

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
import ollama

from config.config import DEFAULT_REASONING, LLM_MODEL, REASONING

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
- "reply": коротка відповідь користувачу ТІЄЮ САМОЮ мовою, якою написане його останнє повідомлення
  (китайською відповідай китайською, арабською арабською, англійською англійською і так далі),
  навіть якщо ці правила написані українською.
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
- "add": true, якщо треба ДОДАТИ новий предмет, якого на фото ще немає ("додай кота на диван").
  Тоді "targets" порожній, а "prompt" описує все фото вже з новим предметом. Інакше false.
- "place": тільки для "add": куди додати, коротко англійською ("on this sofa", "in the sky"). Інакше "".
- "remember": для будь-якого action. Якщо користувач розповів про себе щось варте пам'яті на майбутні
  розмови (ім'я, смаки, улюблені стилі й кольори, постійні прохання на кшталт "завжди малюй мені аніме"),
  запиши це одним коротким реченням українською про користувача в третій особі
  ("Просить звертатися до нього на «ти».", "Любить темні, похмурі тони."). Не записуй разові прохання про одну картинку
  і те, що вже є в пам'яті. Інакше "".
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
        "add": {"type": "boolean"},
        "place": {"type": "string"},
        "remember": {"type": "string"},
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
    "required": ["action", "reply", "prompt", "strength", "targets", "where", "remove", "colors", "add", "place", "remember"],
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


def level(name):
    # Налаштування рівня міркувань з config.py; невідома назва означає рівень за замовчуванням
    return REASONING.get(name, REASONING[DEFAULT_REASONING])


def _ollama_apps():
    # Де може лежати Ollama: спершу програма з іконкою в треї, потім сам сервер
    home = Path.home()
    if sys.platform == "win32":
        folder = Path(os.environ.get("LOCALAPPDATA", home)) / "Programs" / "Ollama"
        return [[str(folder / "ollama app.exe")], [str(folder / "ollama.exe"), "serve"]]
    if sys.platform == "darwin":
        apps = [home / "Applications" / "Ollama.app", Path("/Applications/Ollama.app")]
        return [["open", "-g", "-a", str(app)] for app in apps if app.exists()]
    return []


def start_ollama(wait=30):
    """Запускає Ollama, якщо вона встановлена, але не працює. Повертає True, коли вона відповідає."""
    try:
        ollama.list()
        return True
    except Exception:
        pass
    commands = _ollama_apps()
    server = shutil.which("ollama")
    if server:
        commands.append([server, "serve"])
    for command in commands:
        if command[0] != "open" and not Path(command[0]).exists():
            continue
        try:
            hidden = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=hidden, start_new_session=sys.platform != "win32")
        except OSError:
            continue
        deadline = time.time() + wait
        while time.time() < deadline:
            time.sleep(1)
            try:
                ollama.list()
                return True
            except Exception:
                pass
    return False


def is_available(model=LLM_MODEL):
    # Чи запущена Ollama і чи є в ній потрібна модель. Якщо Ollama вимкнена, вмикаємо її самі.
    if not start_ollama():
        return False
    try:
        names = [item.model for item in ollama.list().models]
    except Exception:
        return False
    return any(name == model or name.split(":")[0] == model or name == f"{model}:latest" for name in names)


def warm_up(model=LLM_MODEL):
    # Завантажує модель у пам'ять заздалегідь, щоб перша відповідь не чекала
    release_others(model)
    ollama.generate(model=model, prompt="", keep_alive=KEEP_ALIVE)


def release_others(model, wait=15):
    # Прибирає з пам'яті інші мовні моделі (наприклад, після зміни рівня міркувань).
    # Дві моделі разом у відеопам'ять не влазять, і тоді Ollama падає з "out of memory".
    try:
        others = [item.model for item in ollama.ps().models
                  if item.model not in (model, f"{model}:latest")]
        for name in others:
            ollama.generate(model=name, prompt="", keep_alive=0)
        deadline = time.time() + wait
        while others and time.time() < deadline and any(
            item.model in others for item in ollama.ps().models
        ):
            time.sleep(0.3)
    except Exception:
        pass


def unload(wait=15):
    # Звільняє пам'ять для художньої моделі і чекає, поки Ollama справді її віддасть.
    # Якщо художник почне раніше, йому не вистачить відеопам'яті і він працюватиме в рази повільніше.
    # Вивантажуємо всі мовні моделі, бо рівень міг змінитися і в пам'яті лишилась інша.
    try:
        for item in ollama.ps().models:
            ollama.generate(model=item.model, prompt="", keep_alive=0)
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


def persona(name):
    # Ким Gaia є в цій розмові: тією моделлю, яку користувач обрав у програмі (наприклад, Cygnus 2.0)
    return (f"ВАЖЛИВО: зараз користувач обрав у програмі модель {name}. У цій розмові ти {name}, "
            f"модель Linum від розробників проєкту Linum. Якщо тебе питають, хто ти чи як тебе звати, "
            f"відповідай, що ти {name}, навіть якщо вище сказано інакше.")


def decide(history, settings=None, model_name="", profile=""):
    """Повертає рішення: {"action", "reply", "prompt", "strength", "targets", "where", "remove", "colors"}.

    settings: рівень міркувань з REASONING (яка модель і чи думати перед відповіддю).
    model_name: назва обраної моделі з номером ("Cygnus 2.0"): мозок відповідає від її імені.
    profile: що користувач розповів про себе в профілі (ім'я, про себе), або "".
    """
    from src.ai import lessons

    settings = settings or level(DEFAULT_REASONING)
    release_others(settings["model"])
    # Уроки з досвіду Gaia читає разом із правилами
    experience = lessons.as_prompt()
    from src.ai import memory

    known = memory.as_prompt()
    if known:
        experience = (experience + "\n" if experience else "") + known
    # Нагадування наприкінці: маленькі моделі інакше часто відповідають мовою правил (українською)
    last = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    last = last.split("]\n", 1)[-1][:300]  # без службової примітки про фото
    reminder = {"role": "system", "content": f"Reminder: write \"reply\" in the same language as the user's "
                                             f"last message: \"{last}\". \"prompt\" is always in English."}
    system = identity() + ("\n" + persona(model_name) if model_name else "") + "\n" + RULES
    system += "\n" + experience if experience else ""
    if profile:
        system += "\n" + profile
    messages = [{"role": "system", "content": system}] + history + [reminder]
    response = chat_with_retry(
        model=settings["model"],
        messages=messages,
        format=DECISION_FORMAT,
        think=settings["think"],
        keep_alive=KEEP_ALIVE,
        options={"temperature": 0.6},
    )
    try:
        decision = json.loads(response["message"]["content"])
    except json.JSONDecodeError:
        return {"action": "chat", "reply": clean(response["message"]["content"]), "prompt": "", "strength": 0,
                "targets": [], "where": "", "remove": False, "colors": [], "add": False, "place": "", "remember": ""}

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
        "add": bool(decision.get("add")) and action == "edit",
        "place": str(decision.get("place") or "") if action == "edit" else "",
        # Що запам'ятати про користувача на майбутні розмови (одне речення) або ""
        "remember": clean(str(decision.get("remember") or ""))[:200],
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


def locate(image_path, name, where="", model=LLM_MODEL):
    """Просить Gaia обвести предмет рамкою. Повертає (x1, y1, x2, y2) у пікселях або None."""
    from PIL import Image

    hint = f" It is in the {where.replace('-', ' ')} part of the image." if where else ""
    try:
        response = chat_with_retry(
            model=model,
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


REVIEW_FORMAT = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "problem": {"type": "string"},
        "prompt": {"type": "string"},
        "fix": {"type": "string", "enum": ["redraw", "recolor"]},
        "targets": {"type": "array", "items": {"type": "string"}},
        "colors": DECISION_FORMAT["properties"]["colors"],
    },
    "required": ["ok", "problem", "prompt", "fix", "targets", "colors"],
}

REVIEW_RULES = """
Ти перевіряєш картинку, яку щойно намалювала художня модель Stable Diffusion на прохання користувача.
Подивись на зображення і суворо оціни, чи виконано прохання: головний предмет, кількість, кольори,
розташування, а також явні вади (зайві чи злиплі пальці, спотворені обличчя, зайві голови й кінцівки,
предмети, яких не просили). Дрібниці, які людина не помітить, не рахуються.
Відповідай JSON:
- "ok": true, якщо картинка добра і відповідає проханню; false, якщо є помітна проблема.
- "problem": коротко українською, що не так (одне речення). Якщо ok, "".
- "prompt": якщо ok false, новий опис АНГЛІЙСЬКОЮ для художника (20-60 слів через кому), який виправить
  проблему: головне пиши на початку і чітко. Якщо ok, "".
- "fix": як виправити. "recolor" ЛИШЕ тоді, коли на картинці саме той предмет, який просили, з правильною
  формою, кількістю частин і розташуванням, і неправильні тільки кольори (наприклад, справжній прапор
  з двома смугами, але смуги переплутані). Якщо предмет не той (тканина чи рушник замість прапора,
  забагато смуг, зайві деталі), це "redraw". "redraw" також для всього іншого і коли ok true.
- "targets": тільки для "recolor": 1-2 короткі англійські назви предмета, який треба перефарбувати
  (наприклад ["flag"], ["car"]). Інакше [].
- "colors": тільки для "recolor": які кольори на які міняти, так само як у рішеннях про зміну фото:
  [{"from": "#RRGGBB" або "", "to": "#RRGGBB", "part": "top"/"bottom"/"left"/"right"/""}].
  Наприклад, якщо на прапорі України жовта смуга зверху, а синя знизу (а має бути навпаки):
  [{"from": "", "to": "#0057B7", "part": "top"}, {"from": "", "to": "#FFD700", "part": "bottom"}]. Інакше [].
Ніколи не використовуй емодзі.
"""


def review(image_path, request, prompt, settings=None):
    """Gaia дивиться на готову картинку. Повертає {"ok", "problem", "prompt", "fix", "targets", "colors"}
    або None, якщо не вдалося. fix: "recolor" (перефарбувати targets у colors) або "redraw" (перемалювати за prompt)."""
    settings = settings or level(DEFAULT_REASONING)
    release_others(settings["model"])
    try:
        response = chat_with_retry(
            model=settings["model"],
            messages=[
                {"role": "system", "content": identity() + "\n" + REVIEW_RULES},
                {
                    "role": "user",
                    "content": f"Прохання користувача: {request}\nОпис, за яким малював художник: {prompt}",
                    "images": [Path(image_path).read_bytes()],
                },
            ],
            format=REVIEW_FORMAT,
            think=settings["think"],
            keep_alive=KEEP_ALIVE,
            options={"temperature": 0.2},
        )
        verdict = json.loads(response["message"]["content"])
    except Exception:
        return None
    better = str(verdict.get("prompt") or "").strip()
    colors = clean_colors(verdict.get("colors"))
    targets = clean_targets(verdict.get("targets"))
    # Перефарбування можливе, лише якщо Критик сказав, що саме і в які кольори
    fix = "recolor" if verdict.get("fix") == "recolor" and colors and targets else "redraw"
    ok = bool(verdict.get("ok")) or (fix == "redraw" and not better)
    return {
        "ok": ok,
        "problem": "" if ok else clean(str(verdict.get("problem") or "")),
        "prompt": better,
        "fix": fix,
        "targets": targets if fix == "recolor" else [],
        "colors": colors if fix == "recolor" else [],
    }


COMPARE_FORMAT = {
    "type": "object",
    "properties": {"better": {"type": "integer", "enum": [1, 2]}, "why": {"type": "string"}},
    "required": ["better", "why"],
}


def compare(first_path, second_path, request, settings=None):
    """Критик дивиться на два варіанти одного прохання. Повертає 1 або 2 (кращий), або None, якщо не вдалося."""
    settings = settings or level(DEFAULT_REASONING)
    release_others(settings["model"])
    try:
        response = chat_with_retry(
            model=settings["model"],
            messages=[
                {"role": "system", "content": identity() + "\nТи порівнюєш два варіанти картинки на одне прохання "
                 "і чесно обираєш той, що краще його виконує і має менше вад. Відповідай JSON "
                 '{"better": 1 або 2, "why": "коротко чому, українською"}, без емодзі.'},
                {
                    "role": "user",
                    "content": f"Прохання користувача: {request}\nПерше зображення - варіант 1, друге - варіант 2.",
                    "images": [Path(first_path).read_bytes(), Path(second_path).read_bytes()],
                },
            ],
            format=COMPARE_FORMAT,
            think=settings["think"],
            keep_alive=KEEP_ALIVE,
            options={"temperature": 0},
        )
        better = json.loads(response["message"]["content"]).get("better")
    except Exception:
        return None
    return better if better in (1, 2) else None


LEARN_FORMAT = {
    "type": "object",
    "properties": {"lesson": {"type": "string"}},
    "required": ["lesson"],
}

LEARN_RULES = """
Ти вчишся на досвіді. Перед тобою картинка, яку художня модель Stable Diffusion намалювала за твоїм
описом, і оцінка цієї картинки: від користувача або з твоєї власної перевірки.
Подивись на картинку, на прохання і на опис, і сформулюй ОДИН загальний урок:
як наступного разу краще писати опис для художника або який підхід обрати, щоб результат сподобався.
Урок має бути корисним і для інших схожих прохань, а не лише для цієї картинки.
Добрі уроки:
- "Художник не вміє порядок смуг на прапорах: прапор малюй будь-яким, а кольори виправляй перефарбуванням."
- "Слово bandana художник малює як медичну маску на обличчі; пиши neckerchief."
- "Для реалістичних облич пиши close-up portrait і natural skin texture."
Якщо картинка сподобалась, урок про те, що саме спрацювало і варто повторювати.
Не повторюй уроки, які вже є в списку. Якщо нового загального уроку немає, поверни "".
Відповідай JSON {"lesson": "..."}: одне речення українською, без емодзі.
"""


def learn(message, liked, settings=None):
    """Урок з картинки: текст уроку або "" (нічого нового), або None, якщо не вдалося.

    liked: True або False, якщо картинку оцінив користувач;
           None, якщо проблему знайшла сама Gaia під час перевірки (тоді вчимося на першому, невдалому варіанті).
    """
    from src.ai import lessons

    settings = settings or level(DEFAULT_REASONING)
    release_others(settings["model"])
    known = lessons.as_prompt() or "Уроків поки немає."
    image = message["image"]
    if liked is None:
        image = message.get("first_image") or image
        details = [
            f"Перевіряючи цю картинку, ти знайшла проблему: {message.get('review', '')}",
            f"Прохання користувача: {message.get('prompt', '')}",
            f"Опис, за яким художник намалював цю невдалу картинку: {message.get('first_prompt') or message.get('prompt_en', '')}",
        ]
        if "fix_worked" in message:
            # Тренування: виправлений опис уже випробувано, тож урок перевірений на практиці
            result = "проблему ВИПРАВЛЕНО" if message["fix_worked"] else "проблема ЛИШИЛАСЬ"
            details.append(f"Потім художник намалював за виправленим описом: {message.get('prompt_en', '')}. "
                           f"Повторна перевірка: {result}.")
            if not message["fix_worked"]:
                details.append("Значить, такий спосіб не допомагає: урок має застерігати від нього "
                               "або радити інший підхід.")
    else:
        verdict = "СПОДОБАЛАСЬ" if liked else "НЕ СПОДОБАЛАСЬ"
        details = [
            f"Користувачу картинка {verdict}.",
            f"Прохання користувача: {message.get('prompt', '')}",
            f"Опис, за яким малював художник: {message.get('prompt_en', '')}",
        ]
        if message.get("review"):
            details.append(f"Під час перевірки ти помітила: {message['review']} (картинку перемальовано)")
    if message.get("style") and message["style"] != "Без стилю":
        details.append(f"Стиль: {message['style']}")
    try:
        response = chat_with_retry(
            model=settings["model"],
            messages=[
                {"role": "system", "content": identity() + "\n" + LEARN_RULES + "\n" + known},
                {"role": "user", "content": "\n".join(details), "images": [Path(image).read_bytes()]},
            ],
            format=LEARN_FORMAT,
            think=settings["think"],
            keep_alive=KEEP_ALIVE,
            options={"temperature": 0.3},
        )
        text = clean(str(json.loads(response["message"]["content"]).get("lesson") or ""))
    except Exception:
        return None
    return " ".join(text.split())[:300]


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
