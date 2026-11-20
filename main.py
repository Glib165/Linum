# Запуск програми Linum

import os
import sys
from pathlib import Path

# Переходимо в папку проєкту, щоб шляхи з config.py (outputs, models) працювали,
# навіть якщо програму запустили з іншої папки.
os.chdir(Path(__file__).resolve().parent)

# Запуск ярликом (pythonw.exe) іде без вікна терміналу, тож повідомлення й помилки
# пишемо в logs/linum.log, щоб їх можна було прочитати, якщо щось піде не так.
if sys.stdout is None or sys.stderr is None:
    Path("logs").mkdir(exist_ok=True)
    log = open("logs/linum.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log

from src.frontend.gui import LinumApp  # noqa: E402

app = LinumApp()
app.mainloop()
