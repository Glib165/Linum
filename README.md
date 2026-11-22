# Linum

**A local AI image studio with a chat assistant. Everything runs on your own computer: no cloud, no accounts, no internet needed after setup.**

[Українською](README.uk.md) · **Website: [glib165.github.io/Linum](https://glib165.github.io/Linum/)**

## Download

There are two ways to get Linum:

1. **Full version, from the website** (Windows, 36 GB): open [glib165.github.io/Linum](https://glib165.github.io/Linum/) and press **Download Linum**. Everything is already inside: Python, Ollama, Gaia and all the models. Unpack the archive and double-click the **Linum** shortcut in the Linum folder. Nothing to install, no internet needed after the download. On the first start Linum also puts its shortcut on the Desktop and in the Start menu.
2. **Small version, from GitHub** (Windows and Mac, 1 MB): open the [latest release](https://github.com/Glib165/Linum/releases/latest) and download **Linum-1.8.zip** under Assets. Unpack it and run the installer: it downloads Python, Ollama and the models by itself (see [Installation on Windows](#installation-on-windows) or [on Mac](#installation-on-mac)).

You talk to **Gaia**, Linum's assistant, in any language. She answers questions, draws new images, edits your photos and learns from her own mistakes.

## Features

**Chat and drawing**
- Chat with Gaia in any language; she replies in the language you write in.
- Three art models: **Fornax** (fast, about 7 s per image), **Gaia** (balanced), **Cygnus** (photorealistic).
- Styles (Cinema, Anime, Oil painting, Pixel art and more), plus **your own styles** written in plain words.
- Four **reasoning levels** (Low, Medium, High, Ultra): from instant answers to thinking first and checking the finished image.

**Photo editing, just by asking**
- Send your own photo (attach or paste with Ctrl+V).
- **Remove** an object: "remove that thing in the bottom left".
- **Recolor** precisely, pixel by pixel, keeping texture and shadows: "swap the colors", "make the robot red".
- **Add** an object: "add a cat on the sofa".
- Change the whole photo: season, time of day, style.
- Edited photos keep their **original size**; everything outside the edit stays untouched.
- **Upscale ×2** with Real-ESRGAN.

**Gaia learns**
- A **Critic** agent checks finished images and fixes mistakes: recolors wrong colors or redraws, then keeps the better version.
- A **notebook of lessons**: Gaia learns from the Critic and from your thumbs up / down, and reads the lessons before every image.
- **Training mode**: agents invent tasks, draw, check themselves and write down lessons on their own.
- **Memory**: Gaia remembers your name and tastes between chats. You can see and delete everything she remembers.

**App**
- Chats with pin, rename, projects, sections, archive and "open in new window".
- Interface in Ukrainian, English and Russian; light and dark theme.

## Requirements

**Windows**
- Windows 10 or 11.
- NVIDIA graphics card with **6 GB** of video memory or more (developed on a GTX 1660 Super).
- **32 GB RAM** recommended: Gaia's brain (Gemma 4, 26B) partly runs from RAM.

**macOS** (experimental, not tested on a real Mac yet)
- A Mac with **Apple Silicon** (M1, M2, M3, M4 or newer). Intel Macs are not supported.
- **32 GB** of memory for the full Gaia 3.7; with 16 GB use the **Low** reasoning level.

**Both**
- About **35 GB** of free disk space for the models.
- An internet connection during installation. Nothing has to be installed beforehand: the installer downloads Python and [Ollama](https://ollama.com) by itself.

## Installation on Mac

1. Download **Linum-1.8.zip** from the [latest release](https://github.com/Glib165/Linum/releases/latest) and unpack it.
2. Double-click **`install.command`** (if macOS blocks it: right-click it, Open, Open). It downloads Python, Ollama, the libraries and the models (about 30 GB, this takes a while) and creates **Linum** in your Applications folder.
3. Start Linum from Applications, Launchpad or Spotlight.

## Installation on Windows

1. Download **Linum-1.8.zip** from the [latest release](https://github.com/Glib165/Linum/releases/latest) and unpack it.
2. Double-click **`install.bat`**. It downloads Python, Ollama, the libraries and the models (about 30 GB, this takes a while) and creates **Linum shortcuts** on the Desktop and in the Start menu.
3. Start Linum with the shortcut.

If the download breaks, run the installer again: it continues from where it stopped.

<details>
<summary>Manual installation</summary>

```
python -m venv .venv
.venv\Scripts\activate
pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu126
pip install -r requirements.txt
python scripts\download_models.py
ollama pull gemma4:26b
ollama create gaia-3.7 -f models\llm\Gaia.Modelfile
ollama pull gemma4:e4b-it-qat
python main.py
```
</details>

If something goes wrong when Linum is started with the shortcut, the error is written to `logs/linum.log`.

## Models and their licenses

Linum's own code is under the [MIT license](LICENSE). The models are made by other people and have their own licenses; they are downloaded during installation and are not part of this repository.

| Model | What it does in Linum | License |
|---|---|---|
| [DreamShaper 8](https://huggingface.co/Lykon/DreamShaper) | Art model "Gaia", and with LCM-LoRA "Fornax" | CreativeML Open RAIL-M (see the model page) |
| [Realistic Vision V6.0](https://huggingface.co/SG161222/Realistic_Vision_V6.0_B1_noVAE) | Art model "Cygnus" | CreativeML Open RAIL-M |
| [LCM-LoRA SD 1.5](https://huggingface.co/latent-consistency/lcm-lora-sdv1-5) | Speeds Fornax up to 6 steps | OpenRAIL++ |
| [sd-vae-ft-mse](https://huggingface.co/stabilityai/sd-vae-ft-mse) | Color decoder for Cygnus | MIT |
| [Gemma 4](https://ollama.com/library/gemma4) (26B and E4B) | Gaia's brain: chat, decisions, Critic, Teacher | Apache 2.0 |
| [CLIPSeg](https://huggingface.co/CIDAS/clipseg-rd64-refined) | Finds an object by its name | Apache 2.0 |
| [SAM ViT-B](https://huggingface.co/facebook/sam-vit-base) | Draws the exact outline of an object | Apache 2.0 |
| [Real-ESRGAN x4plus](https://github.com/xinntao/Real-ESRGAN) | Upscaling | BSD 3-Clause |
| [opus-mt uk-en](https://huggingface.co/Helsinki-NLP/opus-mt-uk-en), [ru-en](https://huggingface.co/Helsinki-NLP/opus-mt-ru-en) | Translates prompts when Gaia is not running | Apache 2.0, CC BY 4.0 |

The CreativeML Open RAIL-M license allows free and commercial use of the generated images, but forbids using the models for a list of harmful purposes. Read the license on the model pages before using Linum commercially.

## Project structure

| Path | Purpose |
|---|---|
| `main.py` | Starts the app |
| `config/config.py` | Models, styles, reasoning levels, version |
| `src/frontend/` | The window: chats, settings, the level popup, translations (`i18n.py`) |
| `src/ai/generator.py` | Drawing and photo editing (Stable Diffusion 1.5 via diffusers) |
| `src/ai/brain.py` | Gaia: chat, decisions, Critic, Teacher |
| `src/ai/segmenter.py` | Finding objects (CLIPSeg + SAM) |
| `src/ai/recolor.py` | Pixel-exact recoloring |
| `src/ai/upscaler.py` | Upscaling (Real-ESRGAN) |
| `src/ai/lessons.py`, `src/ai/trainer.py`, `src/ai/memory.py` | Self-learning and memory |
| `models/llm/Gaia.Modelfile` | Gaia's personality for Ollama |
| `scripts/` | Model download, shortcuts, small experiments |
