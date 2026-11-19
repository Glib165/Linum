# Агент-Тренер: Linum вчиться сам, без користувача.
#
# Один раунд тренування, у ньому працюють агенти (усі вони - Gaia з різними інструкціями):
#   1. Тренер придумує завдання, як від звичайного користувача, на одну з тем нижче.
#   2. Автор пише опис для художника, як завжди, з урахуванням уже відомих уроків.
#   3. Художник малює.
#   4. Критик перевіряє картинку.
#   5. Якщо Критик знайшов помилку, художник малює ще раз за виправленим описом,
#      і Критик перевіряє знову: чи допомогло виправлення.
#   6. Вчитель записує в зошит урок: що пішло не так і що з цим робити.
#
# Картинки тренування лежать окремо, в outputs/training, і не потрапляють у чати й галерею.

import json
import random
import shutil
from pathlib import Path

from src.ai import brain, lessons

TRAINING_DIR = Path("outputs/training")

# Теми тренувань. Найкорисніші ті, де художник найчастіше помиляється.
TRAINING_TOPICS = [
    "руки і пальці людей крупним планом",
    "кілька людей разом (сім'я, друзі, команда)",
    "прапори країн",
    "точна кількість предметів (три яблука, п'ять котів)",
    "предмети певних кольорів (червона машина біля синього будинку)",
    "розташування предметів (кіт ліворуч від собаки, лампа над столом)",
    "обличчя і портрети в різних стилях",
    "тварини в незвичних позах",
    "написи і вивіски",
    "відомі пам'ятки і будівлі",
    "транспорт: машини, велосипеди, літаки",
    "їжа і страви крупним планом",
    "пейзажі в різну пору року і доби",
    "фантастичні істоти й роботи",
    "одяг і костюми різних епох",
]

# Скільки останніх завдань Тренер пам'ятає, щоб не повторюватися
RECENT_LIMIT = 15

TASK_FORMAT = {
    "type": "object",
    "properties": {"request": {"type": "string"}},
    "required": ["request"],
}

TRAINER_RULES = """
Ти Тренер. Ти придумуєш тренувальні завдання для програми Linum, яка малює картинки.
Придумай ОДНЕ прохання на задану тему так, ніби його пише звичайний користувач: українською,
одне речення, конкретне (хто, що, де, які кольори), таке, що художня модель може помилитися.
Не повторюй завдання зі списку недавніх. Відповідай JSON {"request": "..."} без емодзі.
"""


class Stopped(Exception):
    # Користувач натиснув "Зупинити": раунд обривається між кроками
    pass


def invent_task(topic, recent, settings):
    # Тренер придумує завдання на тему
    brain.release_others(settings["model"])
    earlier = "\n".join(f"- {text}" for text in recent) or "(ще немає)"
    response = brain.chat_with_retry(
        model=settings["model"],
        messages=[
            {"role": "system", "content": brain.identity() + "\n" + TRAINER_RULES},
            {"role": "user", "content": f"Тема: {topic}\nНедавні завдання:\n{earlier}"},
        ],
        format=TASK_FORMAT,
        think=False,
        keep_alive=brain.KEEP_ALIVE,
        options={"temperature": 1.0},
    )
    return brain.clean(json.loads(response["message"]["content"]).get("request") or "")


def run_round(pipe, model_name, settings, recent, log, on_step=None, stop=lambda: False):
    """Один раунд тренування. Повертає підсумок: {"request", "problem", "fixed", "lesson"}.

    log(text): куди писати, що зараз відбувається (показується у вікні).
    stop(): повертає True, якщо користувач попросив зупинитися.
    """
    from config.config import NEGATIVE_PROMPT
    from src.ai.generator import free_gpu_memory, generate_image

    def check():
        if stop():
            raise Stopped()

    def draw(prompt):
        # Художник: мозок спершу звільняє відеопам'ять
        check()
        brain.unload()
        log("Художник малює...")
        path = generate_image(pipe, prompt, model_name, on_step, NEGATIVE_PROMPT, 512, 512, random.randint(0, 2**31 - 1))
        free_gpu_memory()
        TRAINING_DIR.mkdir(parents=True, exist_ok=True)
        return str(shutil.move(str(path), TRAINING_DIR / Path(path).name))

    topic = random.choice(TRAINING_TOPICS)
    log(f"Тренер придумує завдання на тему «{topic}»...")
    request = invent_task(topic, recent, settings)
    if not request:
        return {"request": "", "problem": "", "fixed": None, "lesson": None}
    recent.append(request)
    del recent[:-RECENT_LIMIT]

    check()
    log(f"Завдання: {request}\nАвтор пише опис...")
    decision = brain.decide([{"role": "user", "content": request}], settings)
    if decision["action"] != "image":
        return {"request": request, "problem": "", "fixed": None, "lesson": None}
    first_prompt = decision["prompt"]
    first_image = draw(first_prompt)

    check()
    log("Критик перевіряє...")
    verdict = brain.review(first_image, request, first_prompt, settings)
    if verdict is None or verdict["ok"]:
        return {"request": request, "problem": "", "fixed": None, "lesson": None, "image": first_image}

    problem = verdict["problem"]
    log(f"Критик знайшов проблему: {problem}\nПробуємо виправлений опис...")
    second_image = draw(verdict["prompt"])
    check()
    log("Критик перевіряє виправлення...")
    second = brain.review(second_image, request, verdict["prompt"], settings)
    fixed = bool(second and second["ok"])

    check()
    log("Вчитель записує урок...")
    message = {
        "prompt": request,
        "prompt_en": verdict["prompt"],
        "image": second_image,
        "review": problem,
        "first_image": first_image,
        "first_prompt": first_prompt,
        "fix_worked": fixed,
    }
    text = brain.learn(message, None, settings)
    # Записуємо лише новий урок: якщо такий уже є, Тренер просто підтвердив старий
    lesson = lessons.add(text, "training") if text and not lessons.is_known(text) else None
    return {"request": request, "problem": problem, "fixed": fixed, "lesson": lesson, "image": second_image}
