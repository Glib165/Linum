# "Шукач": знаходить на фото предмет за англійським описом і робить маску
# (чорно-біла картинка: біле там, де предмет). Маску потім використовує edit_image,
# щоб перемалювати лише цей предмет, а решту фото не чіпати.
#
# Модель CLIPSeg маленька (близько 600 МБ) і працює на процесорі, тож не заважає художнику.

from PIL import Image, ImageFilter

MODEL_NAME = "CIDAS/clipseg-rd64-refined"

# Точка належить предмету, якщо впевненість у ній не менша за цю частку від найвищої.
# Більше значення дає вужчу маску і краще відокремлює сусідні предмети:
# для прибирання беремо вужчу (щоб не зачепити сусідів), для зміни ширшу (щоб охопити весь предмет).
PEAK_SHARE_REMOVE = 0.7
PEAK_SHARE_CHANGE = 0.5

_model = None
_processor = None


def load():
    global _model, _processor
    if _model is None:
        from transformers import CLIPSegForImageSegmentation, CLIPSegProcessor

        _processor = CLIPSegProcessor.from_pretrained(MODEL_NAME)
        _model = CLIPSegForImageSegmentation.from_pretrained(MODEL_NAME)
        _model.eval()
    return _model, _processor


# Центри частин фото (частка ширини, частка висоти), щоб шукати предмет там, де його бачила Gaia
REGIONS = {
    "top": (0.5, 0.2), "bottom": (0.5, 0.8), "left": (0.2, 0.5), "right": (0.8, 0.5), "center": (0.5, 0.5),
    "top-left": (0.2, 0.2), "top-right": (0.8, 0.2), "bottom-left": (0.2, 0.8), "bottom-right": (0.8, 0.8),
}


def region_weight(shape, where):
    # Карта "наскільки ця точка в потрібній частині фото": 1 у центрі частини, плавно спадає до країв
    import numpy as np

    if where not in REGIONS:
        return None
    height, width = shape
    cx, cy = REGIONS[where]
    ys, xs = np.mgrid[0:height, 0:width]
    distance = (xs / width - cx) ** 2 + (ys / height - cy) ** 2
    return np.exp(-distance / (2 * 0.28 ** 2))


def only_peak_blob(selected, heat):
    # Залишає лише одну суцільну пляму: ту, де модель найвпевненіша.
    # Без цього до предмета можуть "приліпитися" сусідні шматки, наприклад нога робота.
    # Як це працює: починаємо з найвпевненішої точки і крок за кроком "розростаємося"
    # на сусідні виділені точки, доки є куди рости. Окремі плями так і не будуть досягнуті.
    import numpy as np

    y, x = np.unravel_index(int(heat.argmax()), heat.shape)
    blob = np.zeros_like(selected)
    if not selected[y, x]:
        return blob
    blob[y, x] = True
    while True:
        grown = blob.copy()
        grown[1:, :] |= blob[:-1, :]
        grown[:-1, :] |= blob[1:, :]
        grown[:, 1:] |= blob[:, :-1]
        grown[:, :-1] |= blob[:, 1:]
        grown &= selected
        if grown.sum() == blob.sum():
            return blob
        blob = grown


def find_mask(image_path, targets, where="", remove=False, threshold=0.35, min_area=0.004):
    """Шукає предмет за кількома назвами (англійською) і повертає (маска, назва).

    Якщо жодну назву не знайдено впевнено, повертає (None, None).
    where: у якій частині фото шукати ("bottom-left" тощо), "" означає скрізь.
    remove: маска для прибирання (вужча, щоб не зачепити сусідні предмети).
    threshold: наскільки впевнено модель має бачити предмет у точці, від 0 до 1.
    min_area: найменша частка фото, яку може займати предмет (крихітні плями відкидаємо).
    """
    if isinstance(targets, str):
        targets = [targets]
    if not targets:
        return None, None
    share = PEAK_SHARE_REMOVE if remove else PEAK_SHARE_CHANGE
    mask, found = _search(image_path, targets, where, threshold, min_area, share)
    if mask is None and where in REGIONS:
        # Запасна назва: якщо Gaia назвала предмет так, що шукач не розуміє,
        # шукаємо "будь-який предмет" у вказаній частині фото
        mask, found = _search(image_path, ["object"], where, threshold, min_area, share)
    return mask, found


def _search(image_path, targets, where, threshold, min_area, share):
    import torch

    model, processor = load()
    image = Image.open(image_path).convert("RGB")
    inputs = processor(text=list(targets), images=[image] * len(targets), return_tensors="pt", padding=True)
    with torch.no_grad():
        logits = model(**inputs).logits
    # Для кожної назви модель дає карту 352x352: чим більше число, тим впевненіше "тут предмет"
    heats = torch.sigmoid(logits).reshape(len(targets), *logits.shape[-2:]).numpy()

    weight = region_weight(heats.shape[-2:], where)
    best = None
    for target, heat in zip(targets, heats):
        if weight is not None:
            # Предмети далеко від указаної частини фото майже не враховуються
            heat = heat * weight
        peak = float(heat.max())
        if peak < threshold:
            continue
        # Точки, де впевненість більша за поріг (або за половину найвищої), стають білими
        cutoff = max(threshold * 0.6, peak * share)
        selected = only_peak_blob(heat >= cutoff, heat)
        if selected.mean() < min_area:
            continue
        if best is None or peak > best[0]:
            best = (peak, target, selected)
    if best is None:
        return None, None

    _, target, selected = best
    mask = Image.fromarray((selected * 255).astype("uint8")).resize(image.size, Image.BILINEAR)
    # Трохи розширюємо і згладжуємо, щоб захопити краї й тінь предмета
    mask = mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(4))
    return mask.point(lambda value: 255 if value > 60 else 0), target
