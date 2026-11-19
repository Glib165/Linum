# Навчання LoRA для моделі Gaia на ваших фото.
#
# LoRA це маленький файл (кілька мегабайтів), який "доповнює" модель:
# сама Gaia не змінюється, а LoRA вчить її новому об'єкту чи стилю.
#
# Запуск з папки E:\Linum:
#   python -m scripts.train_lora --subject cat
#
# Як це працює коротко:
#   1. Кожне фото один раз перетворюється на "латент", стиснену версію,
#      з якою працює модель. Підписи один раз перетворюються на числа.
#   2. Далі багато разів: до латенту додаємо випадковий шум і просимо модель
#      вгадати цей шум. Помилку модель виправляє лише в маленьких шарах LoRA.
#   3. Результат зберігається в models/loras/gaia_lora.

import argparse
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from diffusers import DDPMScheduler, StableDiffusionPipeline
from diffusers.utils import convert_state_dict_to_diffusers
from peft import LoraConfig
from peft.utils import get_peft_model_state_dict
from PIL import Image, ImageOps

from config.config import MODELS

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp"}


def parse_args():
    parser = argparse.ArgumentParser(description="Навчання LoRA для Gaia")
    parser.add_argument("--subject", required=True, help="що на фото одним англійським словом: cat, man, style")
    parser.add_argument("--token", default="lnm", help="особливе слово, яке потім пишемо в запиті")
    parser.add_argument("--data", default="data/datasets/gaia_lora", help="папка з фото")
    parser.add_argument("--output", default="models/loras/gaia_lora", help="куди зберегти LoRA")
    parser.add_argument("--model", default="Gaia", help="модель, яку доповнюємо")
    parser.add_argument("--steps", type=int, default=1500, help="кількість кроків навчання")
    parser.add_argument("--rank", type=int, default=16, help="розмір LoRA: більше значить точніше, але важче")
    parser.add_argument("--lr", type=float, default=1e-4, help="швидкість навчання")
    parser.add_argument("--resolution", type=int, default=512, help="розмір фото під час навчання")
    parser.add_argument("--save-every", type=int, default=500, help="як часто зберігати проміжний результат")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_photo(path, size):
    # Обертаємо фото так, як його показує телефон, обрізаємо до квадрата по центру і зменшуємо
    image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    side = min(image.size)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    image = image.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
    return image


def to_tensor(image):
    # Картинка стає таблицею чисел від -1 до 1, як очікує модель
    array = torch.from_numpy(np.array(image)).float() / 127.5 - 1.0
    return array.permute(2, 0, 1).unsqueeze(0)


def collect_dataset(folder, subject, token):
    photos = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in IMAGE_TYPES)
    items = []
    for photo in photos:
        caption_file = photo.with_suffix(".txt")
        if caption_file.exists():
            caption = caption_file.read_text(encoding="utf-8").strip()
            if token not in caption:
                caption = f"{token} {subject}, {caption}"
        elif subject == "style":
            caption = f"an image in {token} style"
        else:
            caption = f"a photo of {token} {subject}"
        items.append((photo, caption))
    return items


def save_lora(unet, folder):
    folder.mkdir(parents=True, exist_ok=True)
    layers = convert_state_dict_to_diffusers(get_peft_model_state_dict(unet))
    StableDiffusionPipeline.save_lora_weights(save_directory=str(folder), unet_lora_layers=layers, safe_serialization=True)


def main():
    args = parse_args()
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    items = collect_dataset(args.data, args.subject, args.token)
    if len(items) < 5:
        print(f"Знайдено лише {len(items)} фото в {args.data}. Потрібно хоча б 15.")
        return
    print(f"Фото: {len(items)}. Приклад підпису: {items[0][1]}")

    # Повна точність (fp32): на GTX 16xx половинна дає помилки
    pipe = StableDiffusionPipeline.from_single_file(MODELS[args.model]["path"], torch_dtype=torch.float32)
    vae, text_encoder, tokenizer, unet = pipe.vae, pipe.text_encoder, pipe.tokenizer, pipe.unet
    noise_scheduler = DDPMScheduler.from_config(pipe.scheduler.config)

    # Крок 1: один раз готуємо латенти фото (і дзеркальні копії) та підписи
    print("Готую фото...")
    vae.to(device)
    text_encoder.to(device)
    samples = []
    with torch.no_grad():
        for photo, caption in items:
            image = load_photo(photo, args.resolution)
            tokens = tokenizer(
                caption, padding="max_length", max_length=tokenizer.model_max_length,
                truncation=True, return_tensors="pt",
            ).input_ids.to(device)
            text = text_encoder(tokens)[0].cpu()
            for variant in (image, ImageOps.mirror(image)):
                latent = vae.encode(to_tensor(variant).to(device)).latent_dist.sample() * vae.config.scaling_factor
                samples.append((latent.cpu(), text))
    # Ці частини моделі більше не потрібні, звільняємо відеопам'ять для навчання
    vae.to("cpu")
    text_encoder.to("cpu")
    del pipe
    torch.cuda.empty_cache()

    # Крок 2: додаємо до моделі маленькі шари LoRA, лише їх і навчаємо
    unet.requires_grad_(False)
    unet.add_adapter(LoraConfig(
        r=args.rank,
        lora_alpha=args.rank,
        init_lora_weights="gaussian",
        target_modules=["to_k", "to_q", "to_v", "to_out.0"],
    ))
    unet.to(device)
    unet.enable_gradient_checkpointing()
    unet.train()
    trainable = [p for p in unet.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=args.lr, weight_decay=1e-2)
    print(f"Навчаю {sum(p.numel() for p in trainable) / 1e6:.1f} млн параметрів LoRA, кроків: {args.steps}")

    output = Path(args.output)
    started = time.time()
    running_loss = 0.0
    for step in range(1, args.steps + 1):
        latent, text = random.choice(samples)
        latent, text = latent.to(device), text.to(device)

        noise = torch.randn_like(latent)
        timestep = torch.randint(0, noise_scheduler.config.num_train_timesteps, (1,), device=device).long()
        noisy = noise_scheduler.add_noise(latent, noise, timestep)

        prediction = unet(noisy, timestep, encoder_hidden_states=text).sample
        loss = F.mse_loss(prediction, noise)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(trainable, 1.0)
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)

        running_loss += loss.item()
        if step % 10 == 0 or step == args.steps:
            elapsed = time.time() - started
            per_step = elapsed / step
            left = per_step * (args.steps - step)
            peak = torch.cuda.max_memory_allocated() / 1024**3 if device == "cuda" else 0
            print(
                f"Крок {step}/{args.steps} | помилка {running_loss / 10:.4f} | {per_step:.2f} с/крок | "
                f"залишилось ~{math.ceil(left / 60)} хв | відеопам'ять {peak:.2f} ГБ",
                flush=True,
            )
            running_loss = 0.0
        if step % args.save_every == 0 and step != args.steps:
            save_lora(unet, output / f"step_{step}")
            print(f"Проміжний результат збережено: {output / f'step_{step}'}", flush=True)

    save_lora(unet, output)
    print(f"Готово за {math.ceil((time.time() - started) / 60)} хв. LoRA збережено в {output}")
    print(f"У запиті пишіть слово '{args.token}', наприклад: a photo of {args.token} {args.subject} on the beach")


if __name__ == "__main__":
    main()
