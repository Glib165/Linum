#!/bin/bash
# Linum setup for macOS (Apple Silicon: M1 or newer).
# Double-click this file in Finder, or run: bash install.command
cd "$(dirname "$0")" || exit 1

fail() {
    echo
    echo "Installation failed. Read the error above."
    read -r -p "Press Enter to close..."
    exit 1
}

echo
echo "=== Linum: 1/5 Python ==="
if [ "$(uname -m)" != "arm64" ]; then
    echo "Linum needs a Mac with Apple Silicon (M1, M2, M3, M4 or newer). Intel Macs are not supported."
    read -r -p "Press Enter to close..."
    exit 1
fi
PYTHON=python3.13
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON=python3
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Python 3.13 not found. Install it from https://www.python.org/downloads/macos/ and run install.command again."
    read -r -p "Press Enter to close..."
    exit 1
fi
[ -d .venv ] || "$PYTHON" -m venv .venv || fail
source .venv/bin/activate
python -m pip install --upgrade pip

echo
echo "=== Linum: 2/5 PyTorch + libraries ==="
pip install torch==2.14.1 torchvision==0.29.1 || fail
pip install -r requirements.txt || fail

echo
echo "=== Linum: 3/5 Art models (about 4 GB) ==="
python scripts/download_models.py || fail

echo
echo "=== Linum: 4/5 Gaia (Ollama) ==="
OLLAMA=ollama
command -v ollama >/dev/null 2>&1 || OLLAMA="/Applications/Ollama.app/Contents/Resources/ollama"
if "$OLLAMA" --version >/dev/null 2>&1; then
    MEMORY_GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
    "$OLLAMA" pull gemma4:e4b-it-qat
    if [ "$MEMORY_GB" -ge 32 ]; then
        "$OLLAMA" pull gemma4:26b
        "$OLLAMA" create gaia-3.7 -f models/llm/Gaia.Modelfile
    else
        echo "This Mac has ${MEMORY_GB} GB of memory: the full Gaia 3.7 (26B) needs 32 GB."
        echo "Use the Low reasoning level in Linum: it runs on the smaller model."
    fi
else
    echo "Ollama not found. Install it from https://ollama.com, open it once, then run install.command again."
    echo "Without Ollama, Linum can still draw, but cannot chat or edit photos."
fi

echo
echo "=== Linum: 5/5 Linum.app ==="
bash scripts/create_mac_app.sh || fail

echo
echo "Linum is installed. Start it from Applications -> Linum, or with Spotlight (Cmd+Space, type Linum)."
read -r -p "Press Enter to close..."
