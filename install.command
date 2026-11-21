#!/bin/bash
# Linum setup for macOS (Apple Silicon: M1 or newer).
# Double-click this file in Finder, or run: bash install.command
# Python and Ollama are installed by this script, nothing has to be installed by hand.
cd "$(dirname "$0")" || exit 1
ROOT="$(pwd)"
TOOLS="$ROOT/tools"
UV="$TOOLS/uv"
PY="$ROOT/.venv/bin/python"
export UV_PYTHON_INSTALL_DIR="$TOOLS/python"
export UV_CACHE_DIR="$TOOLS/cache"
mkdir -p "$TOOLS"

fail() {
    echo
    echo "Installation failed. Read the error above, check the internet connection and run install.command again."
    echo "Everything already downloaded is kept, so the next run continues from where it stopped."
    read -r -p "Press Enter to close..."
    exit 1
}

echo
echo "=== Linum: 1/6 Mac ==="
if [ "$(uname -m)" != "arm64" ]; then
    echo "Linum needs a Mac with Apple Silicon (M1, M2, M3, M4 or newer). Intel Macs are not supported."
    read -r -p "Press Enter to close..."
    exit 1
fi
MEMORY_GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
echo "Apple Silicon, ${MEMORY_GB} GB of memory"

echo
echo "=== Linum: 2/6 Python ==="
if [ ! -x "$UV" ]; then
    echo "Downloading uv: a small tool that puts Python inside the Linum folder..."
    curl -L --fail --progress-bar https://github.com/astral-sh/uv/releases/latest/download/uv-aarch64-apple-darwin.tar.gz \
        | tar -xz -C "$TOOLS" --strip-components 1 || fail
fi
[ -x "$PY" ] || "$UV" venv --python 3.13 .venv || fail

echo
echo "=== Linum: 3/6 PyTorch + libraries, about 1 GB ==="
"$UV" pip install --python "$PY" torch==2.14.1 torchvision==0.29.1 || fail
"$UV" pip install --python "$PY" -r requirements.txt || fail

echo
echo "=== Linum: 4/6 Art models, about 4 GB ==="
"$PY" scripts/download_models.py || fail

echo
echo "=== Linum: 5/6 Gaia ==="
OLLAMA_APP=""
for app in "$HOME/Applications/Ollama.app" "/Applications/Ollama.app"; do
    [ -d "$app" ] && OLLAMA_APP="$app" && break
done
if [ -z "$OLLAMA_APP" ]; then
    echo "Downloading Ollama: the engine that runs Gaia..."
    mkdir -p "$HOME/Applications"
    curl -L --fail --progress-bar -o "$TOOLS/Ollama-darwin.zip" https://ollama.com/download/Ollama-darwin.zip || fail
    ditto -x -k "$TOOLS/Ollama-darwin.zip" "$HOME/Applications" || fail
    rm -f "$TOOLS/Ollama-darwin.zip"
    OLLAMA_APP="$HOME/Applications/Ollama.app"
fi
OLLAMA="$OLLAMA_APP/Contents/Resources/ollama"
if ! "$OLLAMA" list >/dev/null 2>&1; then
    echo "Starting Ollama..."
    open -g -a "$OLLAMA_APP"
    for _ in $(seq 30); do
        sleep 2
        "$OLLAMA" list >/dev/null 2>&1 && break
    done
    "$OLLAMA" list >/dev/null 2>&1 || { echo "Ollama did not start. Open it from Applications once and run install.command again."; fail; }
fi
"$OLLAMA" pull gemma4:e4b-it-qat || fail
if [ "$MEMORY_GB" -ge 32 ]; then
    "$OLLAMA" pull gemma4:26b || fail
    "$OLLAMA" create gaia-3.7 -f models/llm/Gaia.Modelfile || fail
else
    echo "This Mac has ${MEMORY_GB} GB of memory: the full Gaia 3.7 (26B) needs 32 GB."
    echo "Use the Low reasoning level in Linum: it runs on the smaller model."
fi

echo
echo "=== Linum: 6/6 Linum.app ==="
bash scripts/create_mac_app.sh || fail
# Downloaded package archives are not needed any more: the libraries are already in .venv
rm -rf "$UV_CACHE_DIR"

echo
echo "Linum is installed. Start it from Applications -> Linum, or with Spotlight (Cmd+Space, type Linum)."
read -r -p "Press Enter to close..."
