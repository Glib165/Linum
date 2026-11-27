# Макет сцени: Архітектор розставляє предмети рамками до того, як почнеться малювання.
#
# Формат тут той самий, що в Gaia для пошуку предметів (brain.locate):
# рамка box = [ymin, xmin, ymax, xmax], числа від 0 до 1000 (частка від висоти і ширини).
# Так ми не залежимо від розміру картинки, поки її не намалювали.
#
# Цей файл нічого не малює і не звертається до моделі. Він лише перевіряє і перетворює дані.
#
# Перевірка з папки Linum:  .venv\Scripts\python.exe src\ai\layout.py

MAX_OBJECTS = 8
MIN_SIDE = 10          # рамка менша за 10 одиниць (1% сторони) - майже точка, її не беремо


def clean_layout(objects):
    """Залишає лише правильні предмети: є назва, є рамка з 4 чисел, рамка не вироджена.
    Числа обрізаємо до діапазону 0-1000, а рамки з перевернутими сторонами відкидаємо."""
    result = []
    for item in objects if isinstance(objects, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:40]
        box = item.get("box")
        if not name or not isinstance(box, list) or len(box) != 4:
            continue
        try:
            top, left, bottom, right = [min(1000.0, max(0.0, float(v))) for v in box]
        except (TypeError, ValueError):
            continue
        if bottom - top < MIN_SIDE or right - left < MIN_SIDE:
            continue
        result.append({"name": name, "box": [top, left, bottom, right]})
    return result[:MAX_OBJECTS]


def position_word(box):
    """Словесно, де рамка: 'top left', 'center', 'bottom right' і так далі.
    Беремо центр рамки і ділимо поле на 3 частини по горизонталі і по вертикалі."""
    top, left, bottom, right = box
    center_y = (top + bottom) / 2
    center_x = (left + right) / 2
    # ЗАВДАННЯ 1. Визначити вертикальну частину: "top" якщо center_y < 333,
    # "bottom" якщо center_y > 666, інакше "middle".
    # Підказка: зробіть так само, як у блоці горизонталі нижче, тільки для center_y.
    if center_y < 333:
        vertical = "top"

    elif center_y > 666:
        vertical = "bottom"
    else:
        vertical = "middle"

    # Горизонталь: "left", "right" або "center" (з такими самими межами 333 і 666 для center_x)
    if center_x < 333:
        horizontal = "left"
        
    elif center_x > 666:
        horizontal = "right"
    else:
        horizontal = "center"
    # ЗАВДАННЯ 2. Скласти з двох частин одне слово через пробіл, але якщо "middle center",
    # повернути просто "center". Підказка: спершу перевірте, чи обидві частини "middle" і "center".
    if vertical == "middle" and horizontal == "center":
        return "center"
    return f"{vertical} {horizontal}"


def to_pixels(box, width, height):
    """Перетворює рамку 0-1000 на пікселі картинки: (x1, y1, x2, y2).
    ЗАВДАННЯ 3. Вивести формулу. Пікселі = частка від розміру, помножена на розмір картинки.
    Увага: порядок у box - [ymin, xmin, ymax, xmax], а в результаті потрібен (x1, y1, x2, y2)."""
    top, left, bottom, right = box
    return (left * width / 1000, top * height / 1000, right * width / 1000, bottom * height / 1000)


def layout_prompt(prompt, objects):
    """Додає до промпту для малювання опис розташування: 'cat in the bottom left, sofa in the center'.
    Так художник бачить, де що має бути, навіть без точного керування рамками.
    Stable Diffusion читає лише перші ~75 токенів промпту, тому беремо не більше 4 предметів."""
    placed = [f"{item['name']} in the {position_word(item['box'])}" for item in objects[:4]]
    if not placed:
        return prompt
    return f"{prompt}, " + ", ".join(placed)


if __name__ == "__main__":
    raw = [
        {"name": "cat", "box": [600, 100, 900, 400]},
        {"name": "sofa", "box": [300, 0, 1000, 1000]},
        {"name": "lamp", "box": [0, 800, 20, 805]},          # занадто мала, має відпасти
        {"name": "", "box": [0, 0, 500, 500]},                # без назви, має відпасти
        {"name": "plant", "box": [-50, 700, 300, 1200]},      # вийде за межі, обріжеться
    ]
    cleaned = clean_layout(raw)
    print("Після перевірки:", cleaned)
    for item in cleaned:
        print(item["name"], "->", position_word(item["box"]), "| пікселі 800x600:", to_pixels(item["box"], 800, 600))
    print(layout_prompt("a living room at evening", cleaned))
