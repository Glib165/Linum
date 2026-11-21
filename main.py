# Запуск програми Linum

import os
import sys
from pathlib import Path

# Переходимо в папку проєкту, щоб шляхи з config.py (outputs, models) працювали,
# навіть якщо програму запустили з іншої папки.
ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

# Повна версія (архів з сайту) несе все з собою: Ollama з моделями лежить у папці ollama,
# а маленькі моделі Hugging Face у models/huggingface. Тоді беремо їх звідти, а не з системи.
# Ollama слухає свій порт 11435, щоб не заважати Ollama, яка вже може бути встановлена.
# Це треба зробити до імпорту бібліотек, бо вони читають ці змінні при імпорті.
if (ROOT / "ollama" / "ollama.exe").exists():
    os.environ["OLLAMA_HOST"] = "127.0.0.1:11435"
    os.environ["OLLAMA_MODELS"] = str(ROOT / "ollama" / "models")
    os.environ["HF_HOME"] = str(ROOT / "models" / "huggingface")

# Запуск ярликом (pythonw.exe) іде без вікна терміналу, тож повідомлення й помилки
# пишемо в logs/linum.log, щоб їх можна було прочитати, якщо щось піде не так.
if sys.stdout is None or sys.stderr is None:
    Path("logs").mkdir(exist_ok=True)
    log = open("logs/linum.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log

from src.frontend.gui import LinumApp  # noqa: E402

app = LinumApp()
app.mainloop()
