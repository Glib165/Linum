# Як Linum виглядає на панелі завдань Windows.
#
# Linum запускається через python.exe / pythonw.exe, тому без підказок Windows показує на панелі
# завдань "Python": у меню правої кнопки, при закріпленні тощо. Тут ми кажемо Windows про вікно:
#   - ідентифікатор програми (усі вікна Linum - одна кнопка на панелі завдань);
#   - ім'я "Linum" і нашу іконку;
#   - як запустити Linum знову (для "Закріпити на панелі завдань").
# Це робиться через "сховище властивостей" вікна (IPropertyStore) - механізм самої Windows.

import ctypes
import sys
import uuid
from ctypes import wintypes
from pathlib import Path

APP_ID = "Linum.App"
# Група властивостей "AppUserModel" і номери властивостей у ній (з документації Windows)
APP_USER_MODEL = "{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}"
RELAUNCH_COMMAND, RELAUNCH_ICON, RELAUNCH_NAME, ID = 2, 3, 4, 5
PROPERTY_STORE = "{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}"
VT_LPWSTR = 31


class GUID(ctypes.Structure):
    _fields_ = [("data1", ctypes.c_ulong), ("data2", ctypes.c_ushort), ("data3", ctypes.c_ushort),
                ("data4", ctypes.c_ubyte * 8)]


def guid(text):
    value = uuid.UUID(text)
    result = GUID(value.fields[0], value.fields[1], value.fields[2])
    for index, byte in enumerate(value.bytes[8:]):
        result.data4[index] = byte
    return result


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]


class PROPVARIANT(ctypes.Structure):
    # Значення властивості: тип (vt) і вказівник на текст. Решта полів у нашому випадку порожні.
    _fields_ = [("vt", ctypes.c_ushort), ("reserved1", ctypes.c_ushort), ("reserved2", ctypes.c_ushort),
                ("reserved3", ctypes.c_ushort), ("pointer", ctypes.c_void_p), ("extra", ctypes.c_void_p)]


def launch_command():
    # Команда, якою Windows запустить Linum знову: pythonw.exe (без вікна терміналу) і main.py
    root = Path(__file__).resolve().parents[2]
    if (root / "Linum.exe").exists():
        # Повна версія запускається своїм Linum.exe
        return f'"{root / "Linum.exe"}"'
    folder = Path(sys.executable).parent
    python = folder / "pythonw.exe" if (folder / "pythonw.exe").exists() else Path(sys.executable)
    return f'"{python}" "{root / "main.py"}"'


def describe_window(window, name, icon_path):
    """Каже Windows, що вікно належить програмі name з іконкою icon_path. Повертає True, якщо вдалося."""
    if sys.platform != "win32":
        return False
    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        store = ctypes.c_void_p()
        iid = guid(PROPERTY_STORE)
        result = ctypes.windll.shell32.SHGetPropertyStoreForWindow(
            wintypes.HWND(hwnd), ctypes.byref(iid), ctypes.byref(store)
        )
        if result != 0 or not store:
            return False
        # Методи IPropertyStore за їхнім місцем у таблиці: 2 Release, 6 SetValue, 7 Commit
        table = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        set_value = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(PROPERTYKEY),
                                       ctypes.POINTER(PROPVARIANT))(table[6])
        commit = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p)(table[7])
        release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])
        values = [
            (ID, APP_ID),
            (RELAUNCH_COMMAND, launch_command()),
            (RELAUNCH_ICON, f"{icon_path},0"),
            (RELAUNCH_NAME, name),
        ]
        texts = []  # тримаємо тексти живими, поки Windows їх копіює
        for pid, text in values:
            texts.append(ctypes.c_wchar_p(text))
            key = PROPERTYKEY(guid(APP_USER_MODEL), pid)
            value = PROPVARIANT(VT_LPWSTR, 0, 0, 0, ctypes.cast(texts[-1], ctypes.c_void_p), None)
            set_value(store, ctypes.byref(key), ctypes.byref(value))
        commit(store)
        release(store)
        return True
    except (OSError, AttributeError, ValueError):
        return False
