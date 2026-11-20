# Експеримент: чи вийде з Gaia (DreamShaper) швидка модель Fornax.
#
# Ідея: до звичайної моделі додаємо маленьку надбудову LCM-LoRA (~135 МБ).
# З нею художнику вистачає 4-6 кроків замість 25, тож картинка виходить у кілька разів швидше.
#
# Запуск з папки E:\Linum (з увімкненим .venv):
#   python scripts/try_fornax.py
# Перший запуск завантажить LCM-LoRA з інтернету. Картинки з'являться в outputs/tmp.

import os
import sys
import time

sys.path.insert(0, os.getcwd())

import torch
from diffusers import LCMScheduler

from src.ai.generator import load_pipeline

PROMPT = "a cozy wooden cabin in a snowy pine forest at dusk, warm light in the windows, highly detailed"
os.makedirs("outputs/tmp", exist_ok=True)


def seed():
    # Однаковий seed: обидві картинки малюються з одного й того самого "шуму", тож їх чесно порівнювати
    return torch.Generator("cpu").manual_seed(42)


pipe = load_pipeline("models/checkpoints/dreamshaper_8.safetensors")

# 1. Звичайна Gaia: 25 кроків
started = time.time()
pipe(PROMPT, num_inference_steps=25, guidance_scale=6.0, generator=seed()).images[0].save("outputs/tmp/gaia.png")
print("Gaia, 25 кроків:", round(time.time() - started), "с")

# 2. Перетворюємо Gaia на Fornax
pipe.load_lora_weights("latent-consistency/lcm-lora-sdv1-5")
pipe.fuse_lora()
pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)

# 3. Fornax: лише 6 кроків
started = time.time()
pipe(PROMPT, num_inference_steps=6, guidance_scale=1.5, generator=seed()).images[0].save("outputs/tmp/fornax.png")
print("Fornax, 6 кроків:", round(time.time() - started), "с")
