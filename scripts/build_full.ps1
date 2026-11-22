# Builds the full version of Linum: one folder with everything inside
# (Python, libraries, Ollama, Gaia and all art models), so people only unpack it and open the Linum shortcut.
# Only for the developer's computer, where Linum is already installed and works.
#
# Run from the Linum folder:
#   powershell -ExecutionPolicy Bypass -File scripts\build_full.ps1
#
# Result:
#   <Out>\Linum\Linum.lnk   the shortcut people open (works only next to the "app" folder)
#   <Out>\Linum\app\        everything else
#   <Out>\Linum-<version>-full.zip   the same as one archive (about 36 GB)
# Running it again only copies what changed. Personal files (chats, settings, memory, avatar)
# never get in: the code is taken from git, and test traces are removed before archiving.

param(
    [string]$Out = "E:\Linum-full",
    [switch]$NoZip,
    [switch]$ZipOnly
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = (Select-String -Path config\config.py -Pattern '^APP_VERSION = "(.+)"').Matches[0].Groups[1].Value
$top = Join-Path $Out "Linum"
$dest = Join-Path $top "app"
$zip = Join-Path $Out "Linum-$version-full.zip"

function Copy-Folder($from, $to, [string[]]$skipFolders = @(), [string[]]$skipFiles = @()) {
    # robocopy: fast, copies only what changed. Exit codes below 8 mean success.
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
    # The first start puts the Linum icon on the shortcut with this computer's path: make it again
    New-TopShortcut
}

function New-TopShortcut {
    # A shortcut that starts Linum from the "app" folder next to it. It has no fixed path inside:
    # Windows starts it from the folder where it lies, so it works wherever the archive is unpacked.
    # Its own icon is a standard Windows picture icon: Linum changes it to the Linum icon on the first start.
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut((Join-Path $top "Linum.lnk"))
    $shortcut.TargetPath = Join-Path $env:WINDIR "System32\cmd.exe"
    $shortcut.Arguments = '/c start "" "app\python\pythonw.exe" -E -s "app\main.py"'
    $shortcut.WorkingDirectory = ""
    $shortcut.WindowStyle = 7
    $shortcut.Description = "Linum: AI images and chat, locally"
    $shortcut.IconLocation = "%SystemRoot%\System32\imageres.dll,108"
    $shortcut.Save()
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
New-Item -ItemType Directory -Force $dest | Out-Null
$code = Join-Path $Out "code"
if (Test-Path $code) { Remove-Item -Recurse -Force $code }
New-Item -ItemType Directory -Force $code | Out-Null
git archive --format=zip -o "$code.zip" HEAD
tar -xf "$code.zip" -C $code
Remove-Item "$code.zip"
Copy-Folder $code $dest
Remove-Item -Recurse -Force $code
# Not needed in the full version: everything is already here
Remove-Item (Join-Path $dest "install.bat"), (Join-Path $dest "install.command"), (Join-Path $dest "Linum.exe") -ErrorAction SilentlyContinue

Write-Host "=== 2/7 Python 3.13 + libraries ==="
$pythonHome = (Select-String -Path .venv\pyvenv.cfg -Pattern '^home = (.+)$').Matches[0].Groups[1].Value.Trim()
Copy-Folder $pythonHome (Join-Path $dest "python") @((Join-Path $pythonHome "Lib\site-packages"), (Join-Path $pythonHome "Scripts"), (Join-Path $pythonHome "Doc"), (Join-Path $pythonHome "include"), (Join-Path $pythonHome "libs"), "__pycache__")
Copy-Folder (Join-Path $root ".venv\Lib\site-packages") (Join-Path $dest "python\Lib\site-packages") @("__pycache__")

Write-Host "=== 3/7 Art models and upscaler ==="
New-Item -ItemType Directory -Force (Join-Path $dest "models\checkpoints"), (Join-Path $dest "models\upscalers") | Out-Null
foreach ($file in "dreamshaper_8.safetensors", "realistic_vision_v6.safetensors") {
    $target = Join-Path $dest "models\checkpoints\$file"
    if (-not (Test-Path $target)) { Copy-Item (Join-Path $root "models\checkpoints\$file") $target }
}
Copy-Item (Join-Path $root "models\upscalers\RealESRGAN_x4plus.pth") (Join-Path $dest "models\upscalers\") -Force

Write-Host "=== 4/7 Small models (CLIPSeg, SAM, LCM-LoRA, VAE, translator) ==="
Copy-Folder (Join-Path $env:USERPROFILE ".cache\huggingface\hub") (Join-Path $dest "models\huggingface\hub") @(".locks")

Write-Host "=== 5/7 Ollama + Gaia ==="
$ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama"
# Without the tray app, the uninstaller and the AMD (ROCm) libraries: Linum needs NVIDIA
Copy-Folder $ollama (Join-Path $dest "ollama") @((Join-Path $ollama "lib\ollama\rocm_v7_1")) @("ollama app.exe", "unins000.*", "app.ico")
# Only the models folder: the rest of .ollama holds this computer's private key
Copy-Folder (Join-Path $env:USERPROFILE ".ollama\models") (Join-Path $dest "ollama\models")

Write-Host "=== 6/7 Shortcut and licenses ==="
New-TopShortcut
Copy-Item (Join-Path $root "scripts\MODEL_LICENSES.txt") (Join-Path $dest "MODEL_LICENSES.txt") -Force

$size = (Get-ChildItem $top -Recurse -File | Measure-Object Length -Sum).Sum / 1GB
Write-Host ("Folder: {0} ({1:N1} GB)" -f $top, $size)

if ($NoZip) { exit 0 }
New-Archive
