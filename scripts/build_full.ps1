# Builds the full version of Linum: one folder with everything inside
# (Python, libraries, Ollama, Gaia and all art models), so people only unpack it and start Linum.exe.
# Only for the developer's computer, where Linum is already installed and works.
#
# Run from the Linum folder:
#   powershell -ExecutionPolicy Bypass -File scripts\build_full.ps1
#
# Result: <Out>\Linum (the folder) and <Out>\Linum-<version>-full.zip (about 37 GB).
# Personal files (chats, settings, memory, avatar) never get in: the code is taken from git.

param(
    [string]$Out = "E:\Linum-full",
    [switch]$NoZip,
    [switch]$ZipOnly
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = (Select-String -Path config\config.py -Pattern '^APP_VERSION = "(.+)"').Matches[0].Groups[1].Value
$dest = Join-Path $Out "Linum"
$zip = Join-Path $Out "Linum-$version-full.zip"

function Copy-Folder($from, $to, [string[]]$skipFolders = @(), [string[]]$skipFiles = @()) {
    # robocopy: fast, copies only what changed when run again. Exit codes below 8 mean success.
    $arguments = @($from, $to, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP", "/R:1", "/W:1")
    if ($skipFolders.Count) { $arguments += "/XD"; $arguments += $skipFolders }
    if ($skipFiles.Count) { $arguments += "/XF"; $arguments += $skipFiles }
    & robocopy @arguments | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE): $from" }
}

function Remove-TestTraces {
    # If the folder was started for a test, it now has chats, settings and pictures: they must not get into the archive
    foreach ($item in "data", "outputs", "logs", "config\settings.json", "config\settings.tmp", "config\developer") {
        $path = Join-Path $dest $item
        if (Test-Path $path) { Remove-Item -Recurse -Force $path }
    }
    Get-ChildItem $dest -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
}

function New-Archive {
    Write-Host "=== 7/7 Archive (no compression: the models do not shrink anyway) ==="
    Remove-TestTraces
    if (Test-Path $zip) { Remove-Item $zip }
    tar --format=zip --options zip:compression=store -cf $zip -C $Out Linum
    if ($LASTEXITCODE -ne 0) { throw "The archive was not made" }
    Write-Host ("Archive: {0} ({1:N1} GB)" -f $zip, ((Get-Item $zip).Length / 1GB))
}

if ($ZipOnly) {
    New-Archive
    exit 0
}

if (git status --porcelain) {
    Write-Host "Commit your changes first: the full version is built from the last commit."
    exit 1
}

Write-Host "=== 1/7 Code from git (no personal files) ==="
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
New-Item -ItemType Directory -Force $Out | Out-Null
$code = Join-Path $Out "code.zip"
git archive --format=zip --prefix=Linum/ -o $code HEAD
tar -xf $code -C $Out
Remove-Item $code

Write-Host "=== 2/7 Python 3.13 + libraries ==="
$pythonHome = (Select-String -Path .venv\pyvenv.cfg -Pattern '^home = (.+)$').Matches[0].Groups[1].Value.Trim()
Copy-Folder $pythonHome (Join-Path $dest "python") @((Join-Path $pythonHome "Lib\site-packages"), (Join-Path $pythonHome "Scripts"), (Join-Path $pythonHome "Doc"), (Join-Path $pythonHome "include"), (Join-Path $pythonHome "libs"), "__pycache__")
Copy-Folder (Join-Path $root ".venv\Lib\site-packages") (Join-Path $dest "python\Lib\site-packages") @("__pycache__")

Write-Host "=== 3/7 Art models and upscaler ==="
New-Item -ItemType Directory -Force (Join-Path $dest "models\checkpoints"), (Join-Path $dest "models\upscalers") | Out-Null
foreach ($file in "dreamshaper_8.safetensors", "realistic_vision_v6.safetensors") {
    Copy-Item (Join-Path $root "models\checkpoints\$file") (Join-Path $dest "models\checkpoints\$file")
}
Copy-Item (Join-Path $root "models\upscalers\RealESRGAN_x4plus.pth") (Join-Path $dest "models\upscalers\")

Write-Host "=== 4/7 Small models (CLIPSeg, SAM, LCM-LoRA, VAE, translator) ==="
Copy-Folder (Join-Path $env:USERPROFILE ".cache\huggingface\hub") (Join-Path $dest "models\huggingface\hub") @(".locks")

Write-Host "=== 5/7 Ollama + Gaia ==="
$ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama"
# Without the tray app, the uninstaller and the AMD (ROCm) libraries: Linum needs NVIDIA
Copy-Folder $ollama (Join-Path $dest "ollama") @((Join-Path $ollama "lib\ollama\rocm_v7_1")) @("ollama app.exe", "unins000.*", "app.ico")
# Only the models folder: the rest of .ollama holds this computer's private key
Copy-Folder (Join-Path $env:USERPROFILE ".ollama\models") (Join-Path $dest "ollama\models")

Write-Host "=== 6/7 Linum.exe and licenses ==="
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
& $csc /nologo /target:winexe /win32icon:"$root\assets\icons\exported\linum.ico" /reference:System.Windows.Forms.dll /out:"$dest\Linum.exe" "$root\scripts\launcher\Linum.cs"
if ($LASTEXITCODE -ne 0) { throw "Linum.exe was not built" }
Copy-Item (Join-Path $root "scripts\MODEL_LICENSES.txt") (Join-Path $dest "MODEL_LICENSES.txt")
# The installer is not needed in the full version: everything is already here
Remove-Item (Join-Path $dest "install.bat"), (Join-Path $dest "install.command") -ErrorAction SilentlyContinue

$size = (Get-ChildItem $dest -Recurse -File | Measure-Object Length -Sum).Sum / 1GB
Write-Host ("Folder: {0} ({1:N1} GB)" -f $dest, $size)

if ($NoZip) { exit 0 }
New-Archive
