# Linum

AI-генератор фото. Працює локально на відеокарті, без інтернету.

## Запуск

У терміналі з папки `E:\Linum`:

```
.venv\Scripts\activate
python main.py
```

Встановлення бібліотек з нуля описано на початку `requirements.txt`.

## Основні файли

| Файл | Що робить |
|---|---|
| `main.py` | Запускає програму |
| `config/config.py` | Налаштування: моделі, розмір картинки, папки |
| `src/ai/generator.py` | Завантаження моделі і створення картинки |
| `src/ai/brain.py` | Мозок: мовна модель Gaia в Ollama, розмовляє і вирішує, що малювати чи змінювати |
| `models/llm/Gaia.Modelfile` | Особистість Gaia. Після змін: `ollama create gaia-3.7 -f models/llm/Gaia.Modelfile` |
| `src/ai/segmenter.py` | "Шукач" CLIPSeg: знаходить предмет на фото за назвою і робить маску для точного прибирання чи зміни |
| `src/frontend/widgets.py` | Поле вводу, текст, який можна виділяти, меню правої кнопки, плавна поява |
| `src/frontend/spinner.py` | Анімація "думаю" (кільце з точок) |
| `src/ai/translator.py` | Переклад запитів з української і російської на англійську (коли мозок недоступний) |
| `src/frontend/gui.py` | Вікно програми: чати, вибір моделі, налаштування |
| `src/frontend/theme.py` | Кольори світлої і темної теми |
| `src/frontend/icons.py` | Іконки інтерфейсу, намальовані кодом |
| `src/backend/services/chat_store.py` | Збереження чатів у `data/chats.json` |
| `src/backend/services/settings_store.py` | Збереження налаштувань у `config/settings.json` |
| `scripts/check_gpu.py` | Перевірка, чи бачить PyTorch відеокарту |
| `scripts/console.py` | Перша, консольна версія програми |
| `scripts/train_lora.py` | Навчання LoRA для Gaia на фото з `data/datasets/gaia_lora` |

## Структура папок

| Папка | Призначення |
|---|---|
| `assets/icons/source/` | Оригінальні іконки проєкту (без змін) |
| `assets/icons/exported/` | Іконки для використання в застосунку (після обробки) |
| `assets/branding/` | Логотип, кольори, шрифти |
| `docs/architecture/` | Архітектура системи, схеми |
| `docs/api/` | Опис API endpoint-ів |
| `src/frontend/` | Інтерфейс користувача |
| `src/backend/api/` | HTTP-маршрути (endpoints) |
| `src/backend/services/` | Бізнес-логіка |
| `src/backend/db/` | Моделі та міграції бази даних |
| `src/ai/pipelines/` | Пайплайни генерації зображень |
| `src/ai/prompts/` | Шаблони промптів |
| `src/ai/postprocessing/` | Постобробка: upscale, фільтри, обрізка |
| `models/checkpoints/` | Базові моделі генерації (великі файли, не в git) |
| `models/loras/` | LoRA-адаптери стилів |
| `models/embeddings/` | Текстові embeddings |
| `data/datasets/` | Набори даних для навчання/тестів |
| `data/prompts/` | Збережені промпти та пресети |
| `data/uploads/` | Файли, завантажені користувачами |
| `outputs/generated/` | Згенеровані фото |
| `outputs/thumbnails/` | Мініатюри результатів |
| `outputs/tmp/` | Тимчасові файли (можна очищати) |
| `config/` | Конфігурації (без секретів) |
| `scripts/` | Допоміжні скрипти (запуск, міграції, утиліти) |
| `tests/unit/` | Юніт-тести |
| `tests/integration/` | Інтеграційні тести |
| `logs/` | Логи |

## Іконки

- `assets/icons/source/linum-icon-1-outline.jpg` - іконка 1 (контурна, перша версія)
- `assets/icons/source/linum-icon-2-dashed.jpg` - іконка 2 (пунктирна версія)
