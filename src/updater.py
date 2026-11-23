# Оновлення Linum з GitHub.
#
# Як це працює:
# 1. latest_release() питає GitHub, яка версія Linum остання (розділ Releases).
# 2. is_newer() порівнює її з нашою (APP_VERSION у config.py).
# 3. install() завантажує код нової версії і кладе його поверх старого.
#    Моделі, чати, налаштування й пам'ять не чіпаються: їх немає в коді на GitHub.
#    Якщо змінився requirements.txt, ставить нові бібліотеки.
# Після цього програма перезапускається (це робить main.py).
#
# Перевірка в консолі, з папки Linum:
#   python -m src.updater

import io
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from config.config import APP_VERSION

REPOSITORY = "Glib165/Linum"
LATEST_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
# GitHub просить, щоб програми називали себе. Пишемо лише назву програми, нічого особистого.
HEADERS = {"User-Agent": "Linum-updater", "Accept": "application/vnd.github+json"}

ROOT = Path(__file__).resolve().parent.parent

# Ці папки й файли належать користувачу або лежать лише на цьому комп'ютері: оновлення їх не чіпає
KEEP = {"data", "outputs", "logs", "models", ".venv", "python", "ollama", "tools",
        "config/settings.json", "config/developer", "config/discord_token.txt"}


def can_update():
    """Чи можна оновлюватися самому. У папці розробника (з .git) оновлення йде через git."""
    return not (ROOT / ".git").exists()


def latest_release():
    """Остання версія на GitHub: {"version", "zip", "notes"}, або None, якщо немає інтернету чи релізів."""
    try:
        request = urllib.request.Request(LATEST_URL, headers=HEADERS)
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    version = str(data.get("tag_name", "")).lstrip("vV")
    if not version or not data.get("zipball_url"):
        return None
    return {"version": version, "zip": data["zipball_url"], "notes": data.get("body") or ""}


def is_newer(latest, current):
    """True, якщо версія latest новіша за current. Наприклад: is_newer("1.10", "1.9") -> True."""
    latest_parts = [int(part) for part in latest.split(".")]
    current_parts = [int(part) for part in current.split(".")]
    return latest_parts > current_parts


def kept(relative):
    # relative: шлях файлу всередині Linum, наприклад "src/ai/brain.py"
    parts = relative.split("/")
    return any("/".join(parts[:length]) in KEEP for length in range(1, len(parts) + 1))


def install(release, on_status=None):
    """Завантажує і ставить нову версію. Повертає True, якщо все вдалося."""
    def status(text):
        if on_status is not None:
            on_status(text)

    status("download")
    request = urllib.request.Request(release["zip"], headers=HEADERS)
    with urllib.request.urlopen(request, timeout=60) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))

    old_requirements = _read(ROOT / "requirements.txt")

    status("install")
    for item in archive.infolist():
        # GitHub кладе все в папку "Glib165-Linum-абвгд/": її назву відкидаємо
        relative = item.filename.split("/", 1)[-1]
        if not relative or item.is_dir() or kept(relative):
            continue
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(item) as source, open(target, "wb") as destination:
            shutil.copyfileobj(source, destination)

    if _read(ROOT / "requirements.txt") != old_requirements:
        status("libraries")
        subprocess.run([_console_python(), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")],
                       check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return True


def _read(path):
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _console_python():
    # Linum працює через pythonw.exe (без вікна), а pip краще запускати через python.exe поруч
    executable = Path(sys.executable)
    console = executable.with_name("python.exe")
    return str(console if executable.name.lower() == "pythonw.exe" and console.exists() else executable)


if __name__ == "__main__":
    print("Наша версія:", APP_VERSION)
    print("Можна оновлюватися самому:", can_update())
    release = latest_release()
    if release is None:
        print("Не вдалося дізнатися останню версію (немає інтернету або релізів).")
    else:
        print("Остання на GitHub:", release["version"])
        print("Є оновлення:", is_newer(release["version"], APP_VERSION))
