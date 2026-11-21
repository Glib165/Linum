# Збільшувач фото: модель Real-ESRGAN збільшує картинку в 4 рази і дорисовує дрібні деталі,
# а не просто розтягує пікселі (тоді фото вийшло б розмитим).
#
# Модель лежить у models/upscalers (64 МБ). Завантажити її:
#   Invoke-WebRequest -Uri https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth -OutFile models\upscalers\RealESRGAN_x4plus.pth

import numpy as np
import torch
from PIL import Image

MODEL_PATH = "models/upscalers/RealESRGAN_x4plus.pth"

# Фото обробляємо шматками такого розміру: ціле фото не влізло б у 6 ГБ відеопам'яті
TILE = 256
# Шматки трохи накладаються, щоб на стиках не було видно швів
OVERLAP = 16

_model = None


def load():
    global _model
    if _model is None:
        from spandrel import ModelLoader

        _model = ModelLoader().load_from_file(MODEL_PATH).eval()
        from src.ai.device import device

        _model.to(device())
    return _model


def upscale_x4(image):
    """Збільшує фото рівно в 4 рази, шматок за шматком."""
    model = load()
    device = next(model.model.parameters()).device
    pixels = np.asarray(image.convert("RGB"), dtype=np.float32) / 255
    height, width = pixels.shape[:2]
    result = np.zeros((height * 4, width * 4, 3), dtype=np.float32)

    for top in range(0, height, TILE):
        for left in range(0, width, TILE):
            # Шматок з невеликим запасом довкола (запас потім відкидаємо)
            y1, x1 = max(0, top - OVERLAP), max(0, left - OVERLAP)
            y2, x2 = min(height, top + TILE + OVERLAP), min(width, left + TILE + OVERLAP)
            tile = torch.from_numpy(pixels[y1:y2, x1:x2]).permute(2, 0, 1)[None].to(device)
            with torch.no_grad():
                bigger = model(tile)[0].permute(1, 2, 0).clamp(0, 1).cpu().numpy()
            # З результату беремо лише середину шматка, без запасу
            inner_top, inner_left = (top - y1) * 4, (left - x1) * 4
            inner_height, inner_width = (min(top + TILE, height) - top) * 4, (min(left + TILE, width) - left) * 4
            result[top * 4:top * 4 + inner_height, left * 4:left * 4 + inner_width] = \
                bigger[inner_top:inner_top + inner_height, inner_left:inner_left + inner_width]

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    elif torch.backends.mps.is_available():
        torch.mps.empty_cache()
    return Image.fromarray((result * 255 + 0.5).astype(np.uint8))


def upscale(image, scale=2):
    """Збільшує фото в scale разів (2 або 4)."""
    # Модель вміє лише в 4 рази. Для 2 разів збільшуємо в 4, а потім акуратно зменшуємо:
    # так деталі чіткіші, ніж якби одразу розтягувати вдвічі.
    result = upscale_x4(image)

    # Потрібний розмір: оригінал, помножений на scale
    width = image.width * scale
    height = image.height * scale

    # Зменшуємо збільшене в 4 рази до потрібного розміру
    result = result.resize((width, height), Image.LANCZOS)
    return result
