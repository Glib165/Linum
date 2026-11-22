# Бот Linum для Discord: малює картинки командою /draw.
# Малює та сама модель, що й у програмі Linum, на вашій відеокарті.
#
# Перед запуском:
#   1. Токен бота збережіть у файлі config\discord_token.txt (один рядок, нічого зайвого).
#   2. Закрийте програму Linum: двом програмам не вистачить відеопам'яті.
# Запуск з папки Linum:
#   .venv\Scripts\python.exe discord_bot\bot.py

import asyncio
import os
import sys
import traceback
from pathlib import Path

import discord
from discord import app_commands

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # шляхи до моделей і файлів у config.py відносні до папки Linum

from config.config import DEFAULT_MODEL, MODELS, NEGATIVE_PROMPT, STYLES  # noqa: E402
from src.ai import generator  # noqa: E402
from src.ai.translator import to_english  # noqa: E402

TOKEN_FILE = ROOT / "config" / "discord_token.txt"

# Для бота беремо найшвидшу модель, щоб друзі не чекали хвилину
BOT_MODEL = "Fornax"

# Одна картинка за раз: відеокарта одна, і дві генерації разом не влізуть у 6 ГБ
gpu_lock = asyncio.Lock()
loaded = {}  # тут зберігається завантажена модель (після першого виклику)


def load_once(model_name):
    # Модель завантажуємо один раз і тримаємо в пам'яті.
    # Якщо потрібна інша, спершу звільняємо стару.
    if model_name not in loaded:
        loaded.clear()
        loaded[model_name] = generator.load_model(model_name)
    return loaded[model_name]


def draw(model_name, prompt, style_name):
    # Ця функція виконується в окремому потоці, бо малювання довге і блокує програму
    english, _language = to_english(prompt)
    style = STYLES.get(style_name, "")
    full_prompt = f"{english}, {style}" if style else english
    pipe = load_once(model_name)
    return generator.generate_image(
        pipe, full_prompt, model_name=model_name, negative_prompt=NEGATIVE_PROMPT,
    )


intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@tree.command(name="draw", description="Намалювати картинку за описом")
@app_commands.describe(prompt="Що намалювати (українською, англійською чи російською)",
                       model="Модель: Fornax швидка, Gaia збалансована, Cygnus фотореалістична",
                       style="Стиль малюнка")
@app_commands.choices(
    model=[app_commands.Choice(name=f"{name} {MODELS[name]['version']}", value=name) for name in MODELS],
    style=[app_commands.Choice(name=style, value=style) for style in STYLES],
)
async def draw_command(interaction: discord.Interaction, prompt: str,
                       model: app_commands.Choice[str] = None,
                       style: app_commands.Choice[str] = None):
    # Малювання займає кілька секунд, тому спершу просимо Discord почекати
    await interaction.response.defer()
    model_name = model.value if model else BOT_MODEL
    style_name = style.value if style else "Без стилю"
    try:
        async with gpu_lock:
            path = await asyncio.to_thread(draw, model_name, prompt, style_name)
        await interaction.followup.send(content=f"**{prompt}** ({model_name})", file=discord.File(path))
    except Exception:
        traceback.print_exc()
        await interaction.followup.send("Не вдалося намалювати. Спробуйте ще раз або інший опис.")


@client.event
async def on_ready():
    await tree.sync()
    print(f"Бот {client.user} готовий. Команда /draw доступна на серверах, де він є.")


def read_token():
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


if __name__ == "__main__":
    token = read_token()
    if not token:
        print(f"Токен не знайдено. Вставте його в файл: {TOKEN_FILE}")
        sys.exit(1)
    client.run(token)
