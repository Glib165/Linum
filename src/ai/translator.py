# Переклад запитів на англійську.
# Stable Diffusion розуміє тільки англійську, тому українські й російські
# запити спершу перекладаємо невеликими моделями Helsinki-NLP.
# Вони працюють на процесорі, щоб не забирати пам'ять у відеокарти.

import re

UKRAINIAN_LETTERS = set("іїєґІЇЄҐ")
RUSSIAN_LETTERS = set("ыэъёЫЭЪЁ")
CYRILLIC = re.compile("[А-Яа-яЁёІіЇїЄєҐґ]")

MODEL_NAMES = {
    "uk": "Helsinki-NLP/opus-mt-uk-en",
    "ru": "Helsinki-NLP/opus-mt-ru-en",
}

_loaded = {}


def detect_language(text):
    # Повертає "en", "uk", "ru" або "unknown", якщо за літерами мову не визначити
    if not CYRILLIC.search(text):
        return "en"
    letters = set(text)
    has_ukrainian = bool(letters & UKRAINIAN_LETTERS)
    has_russian = bool(letters & RUSSIAN_LETTERS)
    # Літери і, ї, є, ґ бувають лише в українській, а ы, э, ъ, ё лише в російській
    if has_ukrainian and not has_russian:
        return "uk"
    if has_russian and not has_ukrainian:
        return "ru"
    return "unknown"


def load_translator(language):
    if language not in _loaded:
        from transformers import MarianMTModel, MarianTokenizer

        name = MODEL_NAMES[language]
        _loaded[language] = (MarianTokenizer.from_pretrained(name), MarianMTModel.from_pretrained(name))
    return _loaded[language]


def _translate(language, text):
    # Повертає переклад і оцінку впевненості моделі (чим ближче до нуля, тим краще)
    import torch

    tokenizer, model = load_translator(language)
    tokens = tokenizer([text], return_tensors="pt", truncation=True)
    with torch.no_grad():
        output = model.generate(
            **tokens,
            max_new_tokens=200,
            num_beams=4,
            return_dict_in_generate=True,
            output_scores=True,
        )
    english = tokenizer.decode(output.sequences[0], skip_special_tokens=True)
    english = english.replace("#", "").strip().rstrip(".").strip()
    return english, float(output.sequences_scores[0])


def to_english(text):
    # Повертає переклад і мову, з якої перекладали
    language = detect_language(text)
    if language == "en":
        return text, language
    if language in MODEL_NAMES:
        return _translate(language, text)[0], language

    # Мову не видно з літер: перекладаємо обома моделями і беремо впевненішу
    results = {name: _translate(name, text) for name in MODEL_NAMES}
    best = max(results, key=lambda name: results[name][1])
    return results[best][0], best
