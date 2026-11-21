@echo off
rem Linum setup from scratch: one double-click, everything else is downloaded automatically.
rem Needs: Windows 10/11, an NVIDIA graphics card with 6 GB+ and an internet connection.
rem Python and Ollama are installed by this script, nothing has to be installed by hand.
chcp 65001 >nul
cd /d "%~dp0"
set "ROOT=%~dp0"
set "TOOLS=%ROOT%tools"
set "UV=%TOOLS%\uv.exe"
set "UV_PYTHON_INSTALL_DIR=%TOOLS%\python"
set "UV_CACHE_DIR=%TOOLS%\cache"
set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo.
echo === Linum: 1/6 Graphics card ===
where nvidia-smi >nul 2>nul
if not errorlevel 1 goto gpu_ok
echo WARNING: no NVIDIA driver found. Linum draws on an NVIDIA graphics card.
echo Install the driver from https://www.nvidia.com/drivers - without it drawing is very slow.
goto gpu_done
:gpu_ok
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
:gpu_done

echo.
echo === Linum: 2/6 Python ===
if exist "%UV%" goto have_uv
echo Downloading uv: a small tool that puts Python inside the Linum folder...
curl.exe -L --fail --progress-bar -o "%TOOLS%\uv.zip" https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip
if errorlevel 1 goto failed
tar -xf "%TOOLS%\uv.zip" -C "%TOOLS%"
del "%TOOLS%\uv.zip"
if exist "%UV%" goto have_uv
for /f "delims=" %%f in ('dir /b /s "%TOOLS%\uv.exe" 2^>nul') do copy /y "%%f" "%UV%" >nul
if not exist "%UV%" goto failed
:have_uv
if not exist "%PY%" "%UV%" venv --python 3.13 .venv
if not exist "%PY%" goto failed

echo.
echo === Linum: 3/6 PyTorch + libraries, about 3 GB ===
"%UV%" pip install --python "%PY%" torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu126
if errorlevel 1 goto failed
"%UV%" pip install --python "%PY%" -r requirements.txt
if errorlevel 1 goto failed

echo.
echo === Linum: 4/6 Art models, about 4 GB ===
"%PY%" scripts\download_models.py
if errorlevel 1 goto failed

echo.
echo === Linum: 5/6 Gaia, about 24 GB ===
set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if exist "%OLLAMA%" goto have_ollama
for /f "delims=" %%f in ('where ollama 2^>nul') do set "OLLAMA=%%f"
if exist "%OLLAMA%" goto have_ollama
echo Downloading Ollama: the engine that runs Gaia...
curl.exe -L --fail --progress-bar -o "%TOOLS%\OllamaSetup.exe" https://ollama.com/download/OllamaSetup.exe
if errorlevel 1 goto failed
echo Installing Ollama...
"%TOOLS%\OllamaSetup.exe" /VERYSILENT /NORESTART /SUPPRESSMSGBOXES
del "%TOOLS%\OllamaSetup.exe"
set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not exist "%OLLAMA%" goto failed
:have_ollama
for %%f in ("%OLLAMA%") do set "OLLAMA_DIR=%%~dpf"
"%OLLAMA%" list >nul 2>nul
if not errorlevel 1 goto ollama_ready
echo Starting Ollama...
if exist "%OLLAMA_DIR%ollama app.exe" goto start_tray
start "Ollama" /min "%OLLAMA%" serve
goto wait_start
:start_tray
start "" "%OLLAMA_DIR%ollama app.exe"
:wait_start
set TRIES=0
:wait_ollama
timeout /t 2 /nobreak >nul
"%OLLAMA%" list >nul 2>nul
if not errorlevel 1 goto ollama_ready
set /a TRIES+=1
if %TRIES% lss 30 goto wait_ollama
echo Ollama did not start. Restart the computer and run install.bat again.
goto failed
:ollama_ready
"%OLLAMA%" pull gemma4:26b
if errorlevel 1 goto failed
"%OLLAMA%" create gaia-3.7 -f models\llm\Gaia.Modelfile
if errorlevel 1 goto failed
"%OLLAMA%" pull gemma4:e4b-it-qat
if errorlevel 1 goto failed

echo.
echo === Linum: 6/6 Shortcuts ===
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1
rem Downloaded package archives are not needed any more: the libraries are already in .venv
if exist "%UV_CACHE_DIR%" rmdir /s /q "%UV_CACHE_DIR%"

echo.
echo Linum is installed. Start it with the Linum shortcut on the Desktop.
pause
exit /b 0

:failed
echo.
echo Installation failed. Read the error above, check the internet connection and run install.bat again.
echo Everything already downloaded is kept, so the next run continues from where it stopped.
pause
exit /b 1
