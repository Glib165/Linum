# Завантажує художні моделі й збільшувач, яких немає в Git (вони великі).
# Download the art models and the upscaler that are not stored in Git (they are large).
#
# Запуск з папки Linum / Run from the Linum folder:
#   python scripts/download_models.py
#
# Решта моделей (CLIPSeg, SAM, LCM-LoRA, VAE, перекладач) завантажуються самі при першому використанні.
# Other models (CLIPSeg, SAM, LCM-LoRA, VAE, translator) download automatically on first use.

import os
import shutil
import sys
import urllib.request
from pathlib import Path

os.chdir(Path(__file__).resolve().parent.parent)

from huggingface_hub import hf_hub_download  # noqa: E402

# (репозиторій на Hugging Face, файл там, куди покласти)
HUGGING_FACE = [
    ("Lykon/DreamShaper", "DreamShaper_8_pruned.safetensors", "models/checkpoints/dreamshaper_8.safetensors"),
    ("SG161222/Realistic_Vision_V6.0_B1_noVAE", "Realistic_Vision_V6.0_NV_B1_fp16.safetensors",
     "models/checkpoints/realistic_vision_v6.safetensors"),
]
UPSCALER = ("https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
            "models/upscalers/RealESRGAN_x4plus.pth")


def main():
    for repo, filename, target in HUGGING_FACE:
        target = Path(target)
        if target.exists():
            print(f"Вже є / already here: {target}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"Завантажую / downloading {repo}/{filename} (~2 GB)...")
        # Обірване завантаження Hugging Face продовжує сам. Готовий файл переносимо, а не копіюємо,
        # щоб він не лежав на диску двічі.
        cached = Path(hf_hub_download(repo, filename)).resolve()
        partial = target.with_suffix(".part")
        shutil.move(cached, partial)
        partial.replace(target)
    url, target = UPSCALER
    target = Path(target)
    if target.exists():
        print(f"Вже є / already here: {target}")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        print("Завантажую / downloading Real-ESRGAN x4plus (67 MB)...")
        # Спершу у файл .part: якщо завантаження обірветься, недокачаний файл не вважатиметься готовим
        partial = target.with_suffix(".part")
        urllib.request.urlretrieve(url, partial)
        partial.replace(target)
    print("Готово / done.")


if __name__ == "__main__":
    sys.exit(main())
