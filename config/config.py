# почнемо писати код для конфігураційного файлу config.py

from pathlib import Path

APP_NAME = "Linum"

# Режим розробника: тренування агентів, оцінки й запис уроків, тобто навчання Linum.
# Він увімкнений лише на комп'ютері, де є файл config/developer. Цього файлу немає в Git,
# тож у звичайних користувачів режиму розробника немає, і в самій програмі його не ввімкнути.
DEVELOPER = (Path(__file__).parent / "developer").exists()
APP_VERSION = "1.9"
IMAGE_WIDTH = 512
IMAGE_HEIGHT = 512
OUTPUTS_DIR = "outputs/generated"
# Сюди копіюються фото, які користувач додав у чат
UPLOADS_DIR = "data/uploads"
# Найбільший розмір фото, яке користувач додає в чат (довша сторона, у пікселях)
UPLOAD_MAX_SIZE = 2048

# Моделі Linum. "version" - номер моделі, він показується поруч з назвою (Gaia 3.7).
# Покращили модель - підніміть її номер.
MODELS = {
    "Fornax": {"version": "1.0", "steps": 6, "path": "models/checkpoints/dreamshaper_8.safetensors", "lora": "latent-consistency/lcm-lora-sdv1-5", "guidance": 1.5},
    "Gaia": {"version": "3.7", "steps": 25, "path": "models/checkpoints/dreamshaper_8.safetensors"},
    "Cygnus": {"version": "2.0", "steps": 30, "path": "models/checkpoints/realistic_vision_v6.safetensors", "vae": "stabilityai/sd-vae-ft-mse"},
}

DEFAULT_MODEL = "Gaia"

# Наскільки суворо модель слідує запиту. Більше значить точніше, але різкіше й з артефактами.
GUIDANCE_SCALE = 6.0

# Файли, де програма зберігає чати і налаштування користувача
CHATS_FILE = "data/chats.json"
SETTINGS_FILE = "config/settings.json"

# Стилі: текст англійською, який дописується до запиту
STYLES = {
    "Без стилю": "",
    "Фото": "photorealistic photo, 35mm, natural lighting, sharp focus, high detail",
    "Кіно": "cinematic film still, dramatic lighting, shallow depth of field, color graded",
    "Аніме": "anime style illustration, clean lines, vibrant colors",
    "Олійний живопис": "oil painting, visible brush strokes, rich colors, fine art",
    "Акварель": "watercolor painting, soft washes, paper texture",
    "3D": "3d render, soft studio lighting, highly detailed",
    "Піксель-арт": "pixel art, 16-bit, retro game style",
    "Ескіз": "pencil sketch, graphite drawing, detailed linework",
}

# Чого модель має уникати. Помітно покращує якість, особливо рук і облич.
NEGATIVE_PROMPT = (
    "blurry, low quality, worst quality, jpeg artifacts, deformed, distorted, disfigured, "
    "bad anatomy, extra fingers, missing fingers, extra limbs, watermark, text, signature"
)

# Формати зображення: (ширина, висота)
SIZES = {
    "Квадрат 1:1": (512, 512),
    "Портрет 2:3": (512, 768),
    "Альбом 3:2": (768, 512),
}

# Мовна модель (мозок), яка розмовляє і вирішує, що робити.
# gaia-3.7 це наша власна модель в Ollama, зібрана з gemma4:26b (див. models/llm/Gaia.Modelfile)
LLM_MODEL = "gaia-3.7"

# Рівні міркувань Gaia.
# model: яка мовна модель в Ollama відповідає
# think: чи міркує вона перед відповіддю (довше, але розумніше)
# check: чи дивиться на готову картинку і перемальовує, якщо вийшло не те
REASONING = {
    "Низький": {"model": "gemma4:e4b-it-qat", "think": False, "check": False},
    "Середній": {"model": "gaia-3.7", "think": False, "check": True},
    "Високий": {"model": "gaia-3.7", "think": True, "check": False},
    "Ультра": {"model": "gaia-3.7", "think": True, "check": True}
}
DEFAULT_REASONING = "Середній"

# Іконка програми
ICON_PATH = "assets/icons/source/linum-icon-1-outline.jpg"
ICO_PATH = "assets/icons/exported/linum.ico"