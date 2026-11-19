# Порівняння моделей: однакові запити з однаковим seed, результат в одній таблиці.
# Запуск з папки E:\Linum:
#   python -m scripts.compare_models
# Таблиця зберігається в outputs/tmp/comparison.png

import time
from pathlib import Path

import torch
from PIL import Image, ImageDraw, ImageFont

from config.config import GUIDANCE_SCALE, NEGATIVE_PROMPT, STYLES
from src.ai.generator import load_pipeline

# Назва в таблиці, файл моделі, покращений VAE (декодер кольорів) або None
CANDIDATES = [
    ("Gaia зараз (SD 1.5)", "models/checkpoints/gaia_model.safetensors", None),
    ("DreamShaper 8", "models/checkpoints/dreamshaper_8.safetensors", None),
    ("Realistic Vision 6", "models/checkpoints/realistic_vision_v6.safetensors", "stabilityai/sd-vae-ft-mse"),
]

# Запит, стиль із config.py, seed
PROMPTS = [
    ("a human hand, open palm, five fingers clearly visible", "Фото", 1234),
    ("a cat sitting on a windowsill, morning light", "Фото", 2024),
    ("portrait of an old fisherman with a grey beard", "Фото", 777),
    ("a fox in an autumn forest", "Аніме", 42),
]

STEPS = 25
SIZE = 512


def main():
    results = {}
    for name, path, vae_name in CANDIDATES:
        if not Path(path).exists():
            print(f"Пропускаю {name}: немає файлу {path}")
            continue
        print(f"=== {name}", flush=True)
        pipe = load_pipeline(path, vae_name)
        for prompt, style, seed in PROMPTS:
            started = time.time()
            full = f"{prompt}, {STYLES[style]}" if STYLES.get(style) else prompt
            image = pipe(
                full,
                negative_prompt=NEGATIVE_PROMPT,
                width=SIZE,
                height=SIZE,
                num_inference_steps=STEPS,
                guidance_scale=GUIDANCE_SCALE,
                generator=torch.Generator(device="cpu").manual_seed(seed),
            ).images[0]
            results[(name, prompt)] = image
            print(f"  {prompt[:40]}: {time.time() - started:.0f} с", flush=True)
        del pipe
        torch.cuda.empty_cache()

    names = [name for name, _, _ in CANDIDATES if any(key[0] == name for key in results)]
    cell, label_height, left = 384, 40, 260
    sheet = Image.new("RGB", (left + cell * len(names), label_height + cell * len(PROMPTS)), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("segoeui.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    for column, name in enumerate(names):
        draw.text((left + column * cell + 10, 10), name, fill="black", font=font)
    for row, (prompt, style, _) in enumerate(PROMPTS):
        y = label_height + row * cell
        draw.multiline_text((10, y + 10), f"{style}\n" + "\n".join(prompt[i:i + 24] for i in range(0, len(prompt), 24)),
                            fill="black", font=font)
        for column, name in enumerate(names):
            image = results.get((name, prompt))
            if image is not None:
                sheet.paste(image.resize((cell, cell)), (left + column * cell, y))

    output = Path("outputs/tmp/comparison.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    print(f"Таблиця збережена: {output}")


if __name__ == "__main__":
    main()
