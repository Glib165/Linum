# Перевірка, чи PyTorch бачить відеокарту

import torch

if torch.cuda.is_available():
    print("Відеокарта знайдена:", torch.cuda.get_device_name(0))
else:
    print("Відеокарта не знайдена, програма працюватиме на процесорі")
