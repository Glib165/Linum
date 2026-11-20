# Перевірка: чи зберігає зміна фото оригінальний розмір і чи чіткіше домальовуються дрібниці.
#
# Робимо велику копію робота (1024x1536, як фото з телефона) і:
#   1. прибираємо штуку внизу ліворуч (художник отримує лише шматок навколо неї, збільшений);
#   2. змінюємо все фото цілком.
#
# Запуск з папки E:\Linum (з увімкненим .venv, Linum закритий):
#   python scripts/try_quality.py
# Результати з'являться в outputs/tmp: quality_before.png, quality_remove.png, quality_whole.png

import os
import shutil
import sys
import time

sys.path.insert(0, os.getcwd())

from PIL import Image

from config.config import NEGATIVE_PROMPT, STYLES
from src.ai.generator import edit_image, edit_region, load_model
from src.ai.segmenter import find_mask

os.makedirs("outputs/tmp", exist_ok=True)
BIG = "outputs/tmp/quality_before.png"
Image.open("outputs/generated/20261118_184535.png").resize((1024, 1536), Image.LANCZOS).save(BIG)

mask, found = find_mask(BIG, ["helmet", "metal object"], where="bottom-left", remove=True, box=(70, 964, 396, 1178))
print("Знайдено:", found, "| шматок для художника:", edit_region(mask.convert("L"), (1024, 1536)))

pipe = load_model("Gaia")

# 1. Прибрати штуку внизу ліворуч
started = time.time()
path, steps = edit_image(
    pipe, BIG, f"futuristic blue robot standing alone, clean grey studio floor, soft shadow, {STYLES['3D']}",
    mask=mask, strength=0.6, model_name="Gaia", negative_prompt="helmet, metal object, " + NEGATIVE_PROMPT,
    seed=7, fill=True,
)
print("Прибирання:", round(time.time() - started), "с | розмір:", Image.open(path).size)
shutil.move(str(path), "outputs/tmp/quality_remove.png")

# 2. Змінити все фото
started = time.time()
path, steps = edit_image(pipe, BIG, f"futuristic red robot, winter, snow on the floor, {STYLES['3D']}",
                         strength=0.5, model_name="Gaia", seed=3)
print("Зміна всього фото:", round(time.time() - started), "с | розмір:", Image.open(path).size)
shutil.move(str(path), "outputs/tmp/quality_whole.png")
