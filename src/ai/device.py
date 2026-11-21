# На чому працюють нейромережі Linum (художник, збільшувач):
#   "cuda" - відеокарта NVIDIA (Windows, як у розробника);
#   "mps"  - вбудована відеокарта Mac з чипом Apple M1, M2, M3, M4;
#   "cpu"  - процесор (дуже повільно, лише якщо відеокарти немає).

import torch


def device():
    """Повертає "cuda", "mps" або "cpu": найкраще, що є на цьому комп'ютері."""
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        return "mps"
    else:
        return "cpu"
