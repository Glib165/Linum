@echo off
rem Linum setup from scratch.
rem Requirements: Windows 10/11, NVIDIA GPU 6 GB+, Python 3.13, Ollama (https://ollama.com).
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo === Linum: 1/5 Python ===
where python >nul 2>nul
if errorlevel 1 (
    echo Python 3.13 not found. Install it from https://www.python.org/downloads/ and run install.bat again.
    pause
    exit /b 1
)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip

echo.
echo === Linum: 2/5 PyTorch + libraries ===
pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu126
if errorlevel 1 goto failed
pip install -r requirements.txt
if errorlevel 1 goto failed

echo.
echo === Linum: 3/5 Art models (about 4 GB) ===
python scripts\download_models.py
if errorlevel 1 goto failed

echo.
echo === Linum: 4/5 Gaia (Ollama, about 24 GB) ===
set OLLAMA=ollama
where ollama >nul 2>nul
if errorlevel 1 set OLLAMA="%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
%OLLAMA% --version >nul 2>nul
if errorlevel 1 (
    echo Ollama not found. Install it from https://ollama.com, then run install.bat again.
    echo Without Ollama, Linum can still draw, but cannot chat or edit photos.
) else (
    %OLLAMA% pull gemma4:26b
    %OLLAMA% create gaia-3.7 -f models\llm\Gaia.Modelfile
    %OLLAMA% pull gemma4:e4b-it-qat
)

echo.
echo === Linum: 5/5 Shortcuts ===
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1

echo.
echo Linum is installed. Start it with the Linum shortcut on the Desktop.
pause
exit /b 0

:failed
echo.
echo Installation failed. Read the error above.
pause
exit /b 1
