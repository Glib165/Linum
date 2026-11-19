# "Шукач": знаходить на фото предмет і робить маску
# (чорно-біла картинка: біле там, де предмет). Маску потім використовує edit_image
# або recolor, щоб змінити лише цей предмет, а решту фото не чіпати.
#
# Працює у два кроки:
# 1. Де предмет? Рамку дає Gaia (вона бачить фото), а якщо рамки немає,
#    грубо шукає CLIPSeg за англійською назвою.
# 2. Точний контур у цій рамці малює SAM (Segment Anything від Meta).
#
# Обидві моделі невеликі (600 і 375 МБ) і працюють на процесорі, тож не заважають художнику.

from PIL import Image, ImageChops, ImageFilter

MODEL_NAME = "CIDAS/clipseg-rd64-refined"
SAM_NAME = "facebook/sam-vit-base"

# Наскільки розширювати грубу рамку CLIPSeg перед SAM (частка від її розміру з кожного боку).
# CLIPSeg часто бачить лише частину предмета, наприклад лише червону половину прапора.
BOX_MARGIN = 0.15

# Точка належить предмету, якщо впевненість у ній не менша за цю частку від найвищої.
# Більше значення дає вужчу маску і краще відокремлює сусідні предмети:
# для прибирання беремо вужчу (щоб не зачепити сусідів), для зміни ширшу (щоб охопити весь предмет).
PEAK_SHARE_REMOVE = 0.7
PEAK_SHARE_CHANGE = 0.5

_model = None
_processor = None
_sam = None
_sam_processor = None


def load():
    global _model, _processor
    if _model is None:
        from transformers import CLIPSegForImageSegmentation, CLIPSegProcessor

        _processor = CLIPSegProcessor.from_pretrained(MODEL_NAME)
        _model = CLIPSegForImageSegmentation.from_pretrained(MODEL_NAME)
        _model.eval()
    return _model, _processor


def load_sam():
    global _sam, _sam_processor
    if _sam is None:
        from transformers import SamModel, SamProcessor

        _sam_processor = SamProcessor.from_pretrained(SAM_NAME)
        _sam = SamModel.from_pretrained(SAM_NAME)
        _sam.eval()
    return _sam, _sam_processor


def outline(image, box, point=None):
    """SAM: точний контур головного предмета в рамці box = (x1, y1, x2, y2) у пікселях.

    point: точка, яка точно лежить на предметі (підказка для SAM), або None.
    Повертає маску або None.
    """
    import torch

    model, processor = load_sam()
    extra = {"input_points": [[[list(map(float, point))]]]} if point else {}
    inputs = processor(image, input_boxes=[[list(map(float, box))]], return_tensors="pt", **extra)
    with torch.no_grad():
        output = model(**inputs, multimask_output=True)
    masks = processor.image_processor.post_process_masks(
        output.pred_masks, inputs["original_sizes"], inputs["reshaped_input_sizes"]
    )[0][0].numpy()
    # SAM дає три варіанти контуру і свою оцінку кожного. Беремо найкращий.
    best = masks[int(output.iou_scores[0, 0].argmax())]
    if not best.any():
        return None
    return Image.fromarray(best.astype("uint8") * 255)


def widen(box, size, margin=BOX_MARGIN):
    x1, y1, x2, y2 = box
    dx, dy = (x2 - x1) * margin, (y2 - y1) * margin
    return max(0, x1 - dx), max(0, y1 - dy), min(size[0], x2 + dx), min(size[1], y2 + dy)


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


def find_mask(image_path, targets, where="", remove=False, box=None, threshold=0.35, min_area=0.004):
    """Шукає предмет і повертає (маска, назва). Якщо не знайдено, (None, None).

    targets: кілька англійських назв предмета.
    box: рамка предмета (x1, y1, x2, y2) у пікселях від Gaia, або None.
    where: у якій частині фото шукати ("bottom-left" тощо), "" означає скрізь.
    remove: маска для прибирання (вужча, щоб не зачепити сусідні предмети).
    threshold: наскільки впевнено CLIPSeg має бачити предмет у точці, від 0 до 1.
    min_area: найменша частка фото, яку може займати предмет (крихітні плями відкидаємо).
    """
    if isinstance(targets, str):
        targets = [targets]
    if not targets and box is None:
        return None, None
    image = Image.open(image_path).convert("RGB")
    rough, found, point = None, (targets or ["object"])[0], None
    if box is None:
        share = PEAK_SHARE_REMOVE if remove else PEAK_SHARE_CHANGE
        rough, found, point = _search(image, targets, where, threshold, min_area, share)
        if rough is None and where in REGIONS:
            # Запасна назва: якщо Gaia назвала предмет так, що шукач не розуміє,
            # шукаємо "будь-який предмет" у вказаній частині фото
            rough, found, point = _search(image, ["object"], where, threshold, min_area, share)
        if rough is None:
            return None, None
        box = widen(rough.getbbox(), image.size)

    try:
        mask = outline(image, box, point)
    except Exception:
        mask = None
    if remove and targets:
        # Для прибирання краще захопити трохи більше, ніж недобрати: рамка від Gaia буває
        # закороткою, і тоді SAM обводить лише частину предмета. Тому додаємо грубу пляму CLIPSeg,
        # якщо вона накладається на знайдений предмет (а не лежить десь окремо).
        if rough is None:
            rough, _, _ = _search(image, targets, where, threshold, min_area, PEAK_SHARE_REMOVE)
        if mask is not None and rough is not None and _overlap(rough, mask) > 0.3:
            mask = ImageChops.lighter(mask, rough)
    if mask is None or _area(mask) < min_area:
        return rough, (found if rough is not None else None)
    return mask, found


def _overlap(part, whole):
    # Яка частка маски part лежить усередині маски whole
    import numpy as np

    part, whole = np.asarray(part) > 127, np.asarray(whole) > 127
    return float((part & whole).sum() / max(part.sum(), 1))


def _area(mask):
    import numpy as np

    return float((np.asarray(mask) > 127).mean())


def _search(image, targets, where, threshold, min_area, share):
    import numpy as np
    import torch

    model, processor = load()
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
            best = (peak, target, selected, heat)
    if best is None:
        return None, None, None

    _, target, selected, heat = best
    mask = Image.fromarray((selected * 255).astype("uint8")).resize(image.size, Image.BILINEAR)
    # Трохи розширюємо і згладжуємо, щоб захопити краї й тінь предмета
    mask = mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(4))
    # Найвпевненіша точка: підказка для SAM, де саме предмет
    y, x = np.unravel_index(int(heat.argmax()), heat.shape)
    point = ((x + 0.5) * image.width / heat.shape[1], (y + 0.5) * image.height / heat.shape[0])
    return mask.point(lambda value: 255 if value > 60 else 0), target, point
