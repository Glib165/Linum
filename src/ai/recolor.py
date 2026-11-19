# Перефарбування без художника: точна математика по пікселях.
#
# Художник (Stable Diffusion) погано розуміє прохання на кшталт "поміняй кольори місцями":
# він бачить старі кольори і малює їх знову. Тому колір міняємо самі:
# кожен піксель предмета зсуваємо до нового кольору, а світлі й темні місця
# (складки тканини, блиск, тіні) лишаються, тож текстура не зникає.
#
# Працюємо в просторі кольорів Lab, а не RGB:
#   L - яскравість (0 чорний, 100 білий),
#   a - від зеленого до червоного,
#   b - від синього до жовтого.
# У Lab відстань між кольорами схожа на те, як різницю бачить людина.

import numpy as np
from PIL import Image, ImageFilter

# Наскільки піксель може відрізнятися від усіх "старих" кольорів, щоб його все одно змінити.
# Далекі пікселі (наприклад, біла нитка на чорно-червоному прапорі) лишаються як були.
KEEP_DISTANCE = 45

# Наскільки м'яко пікселі між двома кольорами змішують обидві зміни (без різких меж)
SOFTNESS = 4

WHITE = np.array([0.95047, 1.0, 1.08883])
TO_XYZ = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041],
])
FROM_XYZ = np.linalg.inv(TO_XYZ)


def rgb_to_lab(rgb):
    # rgb: числа від 0 до 1, остання вісь - три канали
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = linear @ TO_XYZ.T / WHITE
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def lab_to_rgb(lab):
    fy = (lab[..., 0] + 16) / 116
    f = np.stack([fy + lab[..., 1] / 500, fy, fy - lab[..., 2] / 200], axis=-1)
    xyz = np.where(f > 6 / 29, f ** 3, 3 * (6 / 29) ** 2 * (f - 4 / 29)) * WHITE
    linear = np.clip(xyz @ FROM_XYZ.T, 0, 1)
    return np.where(linear <= 0.0031308, linear * 12.92, 1.055 * linear ** (1 / 2.4) - 0.055)


def hex_to_lab(color):
    color = color.lstrip("#")
    rgb = np.array([int(color[i:i + 2], 16) for i in (0, 2, 4)]) / 255
    return rgb_to_lab(rgb)


def features(lab):
    # Ознаки, за якими пікселі ділимо на кольори. Головне тут відтінок відносно яскравості:
    # складка червоної тканини в тіні темна, але все одно "червона", а не чорна.
    # Тому a і b ділимо на яскравість, а саму яскравість майже не враховуємо.
    scale = 40 / (lab[..., :1] + 20)
    return np.concatenate([lab[..., :1] * 0.25, lab[..., 1:] * scale], axis=-1)


def distances(pixels, centers):
    # Відстань від кожного пікселя до кожного кольору (у просторі ознак)
    return np.sqrt(((features(pixels)[:, None, :] - features(centers)[None, :, :]) ** 2).sum(-1))


def shift(pixels, mean, new_mean, light_ratio):
    # Зсуває групу пікселів з кольору mean у колір new_mean, зберігаючи текстуру.
    # Яскравість: світлі й темні місця лишаються, контраст множимо на light_ratio.
    light = (pixels[:, :1] - mean[0]) * light_ratio + new_mean[0]
    # Відтінок: якщо новий колір блідіший (наприклад, червоний стає чорним), різнокольорові
    # цятки теж бліднуть, інакше на чорному з'являться зелені й бірюзові плями.
    old_chroma, new_chroma = np.linalg.norm(mean[1:]), np.linalg.norm(new_mean[1:])
    keep = min(1.0, (new_chroma + 3) / (old_chroma + 3))
    tint = (pixels[:, 1:] - mean[1:]) * keep + new_mean[1:]
    return np.concatenate([light, tint], axis=1)


def recolor(image, mask, changes, even=False):
    """Перефарбовує предмет під маскою.

    even=True: зробити всю маску рівно кольором "to" (для recolor_parts): змінюються всі пікселі,
    а "старі" кольори беруться точно такими, як передані, без уточнення по фото.

    changes: список {"from": "#RRGGBB" або "", "to": "#RRGGBB"}.
    "from" порожній означає "весь предмет у колір to".
    Кілька змін з "from" дозволяють поміняти кольори місцями.
    """
    image = image.convert("RGB")
    if any(change.get("part") for change in changes):
        return recolor_parts(image, mask, changes)
    lab = rgb_to_lab(np.asarray(image, dtype=float) / 255)
    inside = np.asarray(mask.convert("L").resize(image.size)) > 127
    pixels = lab[inside]
    if len(pixels) == 0:
        return image

    with_from = [change for change in changes if change.get("from")]
    if with_from:
        targets = [hex_to_lab(change["to"]) for change in with_from]
        centers = np.array([hex_to_lab(change["from"]) for change in with_from])
        if not even:
            centers = groups_of_colors(pixels, centers)
    else:
        targets = [hex_to_lab(changes[0]["to"])]
        centers = pixels.mean(0, keepdims=True)

    # even: змінити всі пікселі предмета, навіть зовсім несхожі на "старі" кольори
    limit = KEEP_DISTANCE if with_from and not even else 1e6
    distance = distances(pixels, centers)
    nearest = distance.argmin(1)
    close = distance.min(1) < limit

    # Скільки кожна зміна впливає на піксель: найближчий колір майже повністю,
    # а пікселі на межі двох кольорів отримують суміш, тож межа не буде "рваною"
    scores = np.concatenate([distance, np.full((len(pixels), 1), limit)], axis=1)
    weights = np.exp(-(scores ** 2 - (scores.min(1, keepdims=True)) ** 2) / (2 * SOFTNESS ** 2))
    weights /= weights.sum(1, keepdims=True)
    if len(with_from) > 1:
        weights = ask_neighbours(weights, pixels, scores, inside)

    result = pixels * weights[:, -1:]
    for index, target in enumerate(targets):
        group = pixels[(nearest == index) & close]
        if len(group) == 0:
            group = pixels
        mean, spread = group.mean(0), max(group[:, 0].std(), 2)
        # Якщо новий колір уже є на предметі (обмін кольорів), беремо його справжній вигляд
        # з фото: той самий відтінок, ті самі тіні. Так результат виглядає природно.
        # (Серед кандидатів і сама група: якщо колір уже потрібний, вона лишається як є)
        match = min(range(len(centers)), key=lambda i: distances(target[None], centers[i:i + 1])[0, 0])
        other = pixels[(nearest == match) & close] if match is not None else pixels[:0]
        if not even and len(other) and distances(target[None], centers[match:match + 1])[0, 0] < 20:
            new_mean = other.mean(0)
            light_ratio = np.clip(max(other[:, 0].std(), 2) / spread, 0.5, 2)
        else:
            # Новий колір: темніші кольори мають менший перепад світла і тіні
            new_mean = target
            light_ratio = np.clip((target[0] + 15) / (mean[0] + 15), 0.5, 1.5)
        result += shift(pixels, mean, new_mean, light_ratio) * weights[:, index:index + 1]

    changed = lab.copy()
    changed[inside] = result
    recolored = Image.fromarray((lab_to_rgb(changed) * 255 + 0.5).astype("uint8"))
    # М'який край маски, щоб предмет не виглядав вирізаним ножицями
    edge = Image.fromarray(inside.astype("uint8") * 255).filter(ImageFilter.GaussianBlur(1.2))
    return Image.composite(recolored, image, edge)


def split_mask(mask, part):
    """Повертає половину маски предмета: "top", "bottom", "left" або "right".

    Ділимо кожен стовпчик пікселів окремо (для "left"/"right" кожен рядок), тож межа
    йде вздовж форми предмета: на хвилястому прапорі вона теж хвиляста, а не пряма.
    """
    inside = np.asarray(mask.convert("L")) > 127
    if part in ("left", "right"):
        # Повертаємо маску набік (рядки стають стовпчиками), щоб ліве і праве рахувати так само, як верх і низ
        inside = inside.T
    rows = np.arange(inside.shape[0])[:, None]
    columns = np.arange(inside.shape[1])
    filled = inside.any(axis=0)
    # Для кожного стовпчика: де предмет починається і де закінчується
    first = np.where(filled, inside.argmax(axis=0), 0)
    last = np.where(filled, inside.shape[0] - 1 - inside[::-1].argmax(axis=0), 0)
    span = (last - first + 1) * filled
    # Середина кожного стовпчика надійна лише там, де предмет "повний". Біля скошених країв
    # стовпчик зачіпає лише шматочок предмета, і його середина хибна. Тому через надійні
    # середини проводимо плавну криву (параболу) і беремо середину з неї для всіх стовпчиків.
    good = span >= np.median(span[filled]) * 0.6
    if good.sum() >= 3:
        curve = np.polyfit(columns[good], ((first + last + 1) / 2)[good], deg=2, w=span[good])
        middle = np.polyval(curve, columns)
    else:
        middle = (first + last + 1) / 2
    half = inside & ((rows < middle) if part in ("top", "left") else (rows >= middle))
    if part in ("left", "right"):
        half = half.T
    return Image.fromarray(half.astype("uint8") * 255)


def main_colors(pixels, count=2):
    # Головні кольори предмета (наприклад, червоний і чорний на прапорі).
    # Починаємо з "середнього" пікселя і з того, що найбільше від нього відрізняється,
    # а потім уточнюємо методом k-середніх.
    start = np.median(pixels, axis=0)
    far = distances(pixels, start[None])[:, 0]
    # Не найдальший піксель (це може бути випадкова цятка), а один з найдальших
    second = pixels[np.argsort(far)[int(len(far) * 0.95)]]
    starts = np.array([start, second])[:count]
    return groups_of_colors(pixels, starts)


def lab_to_hex(lab):
    red, green, blue = (np.clip(lab_to_rgb(lab), 0, 1) * 255 + 0.5).astype(int)
    return f"#{red:02X}{green:02X}{blue:02X}"


def recolor_parts(image, mask, changes):
    # Кожна зміна з "part" фарбує свою частину предмета одним рівним кольором,
    # навіть якщо там зараз кілька кольорів (наприклад, і червоне, і чорне).
    # Для цього кожен з головних кольорів предмета окремо переводимо в новий колір:
    # так стара межа між червоним і чорним зникає, а складки й текстура лишаються.
    lab = rgb_to_lab(np.asarray(image, dtype=float) / 255)
    # Трохи ширше за контур, щоб захопити край тканини: інакше вздовж краю лишається стара смужка
    mask = mask.convert("L").resize(image.size).filter(ImageFilter.MaxFilter(5))
    inside = np.asarray(mask) > 127
    if not inside.any():
        return image
    found = [lab_to_hex(color) for color in main_colors(lab[inside])]
    full = Image.fromarray(inside.astype("uint8") * 255)
    for change in changes:
        part = split_mask(full, change["part"]) if change.get("part") else full
        image = recolor(image, part, [{"from": color, "to": change["to"]} for color in found], even=True)
    return image


def blur(array, radius):
    # Розмиття двовимірного масиву: тричі середнє в квадраті (дуже схоже на розмиття Гаусса)
    radius = max(1, int(radius))
    size = 2 * radius + 1
    for _ in range(3):
        for axis in (0, 1):
            pad = [(0, 0), (0, 0)]
            pad[axis] = (radius + 1, radius)
            # Сума "наростаючим підсумком": різниця двох сум дає суму квадрата за одну дію
            total = np.cumsum(np.pad(array, pad, mode="edge"), axis=axis)
            length = total.shape[axis]
            array = (total.take(range(size, length), axis=axis) - total.take(range(0, length - size), axis=axis)) / size
    return array


def ask_neighbours(weights, pixels, scores, inside):
    # Дуже темні пікселі (глибока тінь) і майже безбарвні (подряпини, відблиски) за самим
    # кольором не розрізнити: тінь у складці червоної тканини схожа на чорний.
    # Такі "непевні" пікселі беруть рішення в сусідів: складка серед червоного теж червона.
    ordered = np.sort(scores, axis=1)
    margin = ordered[:, 1] - ordered[:, 0]
    sure = np.clip((pixels[:, 0] - 4) / 12, 0, 1) * np.clip(margin / 8, 0, 1)

    height, width = inside.shape
    radius = max(height, width) * 0.02
    sure_map = np.zeros((height, width))
    sure_map[inside] = sure
    sure_blurred = blur(sure_map, radius) + 1e-6
    tiny_blurred = blur(inside.astype(float), 2) + 1e-6
    result = np.empty_like(weights)
    for index in range(weights.shape[1]):
        layer = np.zeros((height, width))
        layer[inside] = weights[:, index]
        # Думка сусідів: середнє серед упевнених пікселів поруч
        neighbours = blur(layer * sure_map, radius)[inside] / sure_blurred[inside]
        mixed = np.zeros((height, width))
        mixed[inside] = sure * weights[:, index] + (1 - sure) * neighbours
        # Ще трохи згладжуємо, щоб тонкі подряпини не випадали з кольору
        result[:, index] = blur(mixed, 2)[inside] / tiny_blurred[inside]
    total = result.sum(1, keepdims=True)
    # Якщо поруч узагалі немає впевнених пікселів, лишаємо рішення за кольором
    return np.where(total > 1e-3, result / np.maximum(total, 1e-3), weights)


def groups_of_colors(pixels, starts, rounds=10):
    # Уточнює "старі" кольори за справжніми пікселями фото (метод k-середніх):
    # Gaia каже "червоний", а на фото він темно-вишневий. Кожен колір переходить
    # у середнє пікселів, які до нього найближчі.
    centers = starts.astype(float).copy()
    for _ in range(rounds):
        distance = distances(pixels, centers)
        nearest = distance.argmin(1)
        close = distance.min(1) < KEEP_DISTANCE * 1.5
        for index in range(len(centers)):
            members = pixels[(nearest == index) & close]
            if len(members):
                centers[index] = members.mean(0)
    return centers
