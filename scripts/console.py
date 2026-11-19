# Консольна версія Linum: перший варіант програми, без вікна.
# Запуск з папки E:\Linum: python -m scripts.console

from config.config import DEFAULT_MODEL
from src.ai.generator import load_model, generate_image

print("Завантажую модель", DEFAULT_MODEL)
pipe = load_model(DEFAULT_MODEL)

prompt = input("Введіть опис фотографії: ")
path = generate_image(pipe, prompt)

print("Ваше зображення збережено", path)
