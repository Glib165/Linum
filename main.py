# Запуск програми Linum

import os
from pathlib import Path

# Переходимо в папку проєкту, щоб шляхи з config.py (outputs, models) працювали,
# навіть якщо програму запустили з іншої папки.
os.chdir(Path(__file__).resolve().parent)

from src.frontend.gui import LinumApp  # noqa: E402

app = LinumApp()
app.mainloop()
