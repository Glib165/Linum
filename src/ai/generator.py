# генерація картинок для Linum

from datetime import datetime 
from pathlib import Path

import torch
from PIL import Image, ImageFilter
from diffusers import AutoencoderKL, LCMScheduler, DPMSolverMultistepScheduler, StableDiffusionPipeline, StableDiffusionInpaintPipeline 

from config.config import MODELS, DEFAULT_MODEL, GUIDANCE_SCALE, IMAGE_WIDTH, IMAGE_HEIGHT, OUTPUTS_DIR
from src.ai.device import device


def load_pipeline(model_path, vae_name=None, lora=None):
    pipe = StableDiffusionPipeline.from_single_file(model_path, torch_dtype=torch.float32)
    # Деякі моделі краще працюють з окремим покращеним декодером кольорів (VAE)
    if vae_name:
        pipe.vae = AutoencoderKL.from_pretrained(vae_name, torch_dtype=torch.float32)
    # Семплер вирішує, як саме прибирати шум крок за кроком.
    # DPM++ 2M Karras дає чисті картинки на доопрацьованих моделях і працює швидше
    # за стандартний, з яким на них з'являються кольорові плями.
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(
        pipe.scheduler.config, use_karras_sigmas=True, algorithm_type="dpmsolver++"
    )
    if lora: 
        pipe.load_lora_weights(lora)
        pipe.fuse_lora()
        pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)
    place_on_device(pipe)
    pipe.enable_attention_slicing()
    return pipe


def place_on_device(pipe):
    # NVIDIA: частини моделі по черзі переходять з оперативної пам'яті на відеокарту (6 ГБ замало для всієї).
    # Mac (mps) має спільну пам'ять для процесора й відеокарти, тож модель кладемо туди цілком.
    place = device()
    if place == "cuda":
        pipe.enable_model_cpu_offload()
    else:
        pipe.to(place)


def load_model(model_name):
    model = MODELS[model_name]
    return load_pipeline(model["path"], model.get("vae"), model.get("lora"))


def generate_image(
    pipe,
    prompt,
    model_name=DEFAULT_MODEL,
    on_step=None,
    negative_prompt=None,
    width=IMAGE_WIDTH,
    height=IMAGE_HEIGHT,
    seed=None,
):
    steps = MODELS[model_name]["steps"]

    # seed це число, від якого залежить випадковість. Той самий seed і запит
    # дають ту саму картинку, а новий seed дає новий варіант.
    generator = None
    if seed is not None:
        generator = torch.Generator(device="cpu").manual_seed(seed)

    # Ця функція викликається після кожного кроку генерації.
    # Через неї вікно дізнається, скільки кроків уже пройдено.
    def step_callback(pipeline, step, timestep, callback_kwargs):
        if on_step is not None:
            on_step(step + 1, steps)
        return callback_kwargs

    image = pipe(
        prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        num_inference_steps=steps,
        guidance_scale=MODELS[model_name].get("guidance", GUIDANCE_SCALE),
        generator=generator,
        callback_on_step_end=step_callback,
    ).images[0]

    free_gpu_memory()
    return save_image(image)


def free_gpu_memory():
    # PyTorch тримає звільнену відеопам'ять "про запас". Віддаємо її,
    # щоб нею могла скористатися мовна модель Gaia.
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    elif torch.backends.mps.is_available():
        torch.mps.empty_cache()


def save_image(image):
    Path(OUTPUTS_DIR).mkdir(parents=True, exist_ok=True)
    filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".png"
    path = Path(OUTPUTS_DIR) / filename
    image.save(path)
    return path


def working_size(width, height, longest=768, enlarge=1.0):
    # enlarge: у скільки разів максимум можна збільшити маленький шматок фото,
    # щоб художник домалював його з деталями (1.0 означає лише зменшувати)
    scale = min(enlarge, longest / max(width, height))
    new_width = int(width * scale) // 8 * 8
    new_height = int(height * scale) // 8 * 8
    return new_width, new_height


_edit_pipes = {}


def edit_pipeline(pipe):
    # Та сама модель, але в режимі "домалювати частину фото". Частини моделі спільні
    # зі звичайним режимом, тож додаткової пам'яті він не займає.
    # Важливо ввімкнути для нього перенос на процесор: інакше після редагування
    # частини моделі лишаються на відеокарті, пам'ять переповнюється, і все працює в рази повільніше.
    key = id(pipe)
    if key not in _edit_pipes:
        _edit_pipes.clear()
        edit_pipe = StableDiffusionInpaintPipeline(**pipe.components)
        edit_pipe.set_progress_bar_config(disable=True)
        place_on_device(edit_pipe)
        _edit_pipes[key] = edit_pipe
    return _edit_pipes[key]


def fill_from_surroundings(image, mask):
    """Заливає виділене місце кольорами навколо нього.

    Потрібно, щоб прибрати предмет: звичайна модель погано вигадує фон "з нуля",
    але добре доробляє розмиту пляму потрібного кольору до справжнього фону.
    Як це працює: зменшуємо фото без виділеної частини в 4, 8, 16... разів.
    На маленькій копії кольори фону "розтікаються" на місце предмета,
    і кожна точка виділення бере колір з найдрібнішої копії, де його вже видно.
    """
    import numpy as np

    selected = (np.asarray(mask.convert("L")) > 127).astype(np.float32)
    keep = 1.0 - selected
    pixels = np.asarray(image.convert("RGB")).astype(np.float32)
    width, height = image.size

    def shrink(array, factor):
        small = Image.fromarray(array.astype(np.float32), "F").resize(
            (max(1, width // factor), max(1, height // factor)), Image.BOX
        )
        return np.asarray(small.resize((width, height), Image.BILINEAR))

    result = pixels.copy()
    done = np.zeros_like(selected)
    for factor in (4, 8, 16, 32, 64, 128):
        weight = shrink(keep, factor)
        colors = np.stack([shrink(pixels[..., channel] * keep, factor) for channel in range(3)], -1)
        ready = (weight > 0.05) & (selected > 0) & (done == 0)
        result[ready] = colors[ready] / weight[ready][:, None]
        done[ready] = 1
    filled = Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))
    # Легке розмиття прибирає "сходинки" від зменшених копій
    return Image.composite(filled.filter(ImageFilter.GaussianBlur(6)), image.convert("RGB"), mask.convert("L"))


def edit_image(pipe, image_path, prompt, mask=None, strength=0.6,
               model_name=DEFAULT_MODEL, on_step=None, negative_prompt=None, seed=None, fill=False):
    """Змінює фото. mask: біле = перемалювати. fill=True: спершу залити виділене фоном (щоб прибрати предмет)."""
    edit_pipe = edit_pipeline(pipe)

    original = Image.open(image_path).convert("RGB")
    full_mask = mask.convert("L").resize(original.size) if mask is not None else None

    # Якою частиною фото займається художник: усім фото або шматком навколо виділення.
    # Шматок збільшується до робочого розміру, тож дрібні місця домальовуються з деталями.
    region = edit_region(full_mask, original.size)
    crop = original.crop(region)
    width, height = working_size(crop.width, crop.height, enlarge=3.0 if mask is not None else 1.0)
    source = crop.resize((width, height), Image.LANCZOS)

    # Маска: біле = перемалювати, чорне = не чіпати
    if mask is None:
        work_mask = Image.new("L", (width, height), 255)
    else:
        work_mask = full_mask.crop(region).resize((width, height))
        work_mask = work_mask.filter(ImageFilter.MaxFilter(15))

    # Модель бачить фото з уже залитим фоном місцем, а поза маскою все одно залишиться оригінал
    model_input = fill_from_surroundings(source, work_mask) if fill and mask is not None else source

    # Скільки кроків реально буде зроблено
    steps = MODELS[model_name]["steps"]
    total = max(1, int(steps * strength))

    generator = None
    if seed is not None:
        generator = torch.Generator(device="cpu").manual_seed(seed)

    def step_callback(pipeline, step, timestep, callback_kwargs):
        if on_step is not None:
            on_step(min(step + 1, total), total)
        return callback_kwargs

    result = edit_pipe(
        prompt,
        image=model_input,
        mask_image=work_mask,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        strength=strength,
        num_inference_steps=steps,
        guidance_scale=MODELS[model_name].get("guidance", GUIDANCE_SCALE),
        generator=generator,
        callback_on_step_end=step_callback,
    ).images[0]
    free_gpu_memory()

    # Повертаємо результат до розміру оригіналу. Поза виділенням лишаються оригінальні пікселі
    # (у повному розмірі, без втрати якості), а межу робимо м'якою.
    patch = result.resize(crop.size, Image.LANCZOS)
    if mask is None:
        return save_image(patch), total
    soft_mask = work_mask.filter(ImageFilter.GaussianBlur(6)).resize(crop.size, Image.LANCZOS)
    final = original.copy()
    final.paste(patch, region[:2], soft_mask)
    return save_image(final), total


def edit_region(mask, size, margin=0.6, smallest=256):
    """Прямокутник (лівий, верхній, правий, нижній) частини фото, яку отримає художник.

    Без маски - усе фото. З маскою - виділене місце з запасом навколо (margin від його розміру
    з кожного боку), щоб художник бачив, що довкола, і домалював у тому ж стилі.
    """
    width, height = size
    box = mask.getbbox() if mask is not None else None
    if box is None:
        return 0, 0, width, height
    left, top, right, bottom = box
    # Запас навколо, але шматок не менший за smallest пікселів (менший художник малює гірше)
    pad_x = max((right - left) * margin, (smallest - (right - left)) / 2, 0)
    pad_y = max((bottom - top) * margin, (smallest - (bottom - top)) / 2, 0)
    left, right = max(0, int(left - pad_x)), min(width, int(right + pad_x))
    top, bottom = max(0, int(top - pad_y)), min(height, int(bottom + pad_y))
    return left, top, right, bottom
