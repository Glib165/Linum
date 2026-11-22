# Creates Linum shortcuts on the Desktop and in the Start menu, with the Linum icon.
# Full version (archive from the website): Python lies in the "python" folder next to main.py.
#   Linum runs this script itself on the first start, and also puts the Linum icon
#   on the "Linum" shortcut next to the folder (before that it has a standard icon).
# Installed version (install.bat): Python lies in .venv.
# Linum starts through pythonw.exe, so there is no black console window.

$root = Split-Path -Parent $PSScriptRoot
$portable = Join-Path $root "python\pythonw.exe"
$installed = Join-Path $root ".venv\Scripts\pythonw.exe"
$main = Join-Path $root "main.py"
$icon = Join-Path $root "assets\icons\exported\linum.ico"
if (Test-Path $portable) {
    $target = $portable
    # -E -s: ignore any other Python settings on this computer
    $arguments = "-E -s `"$main`""
} elseif (Test-Path $installed) {
    $target = $installed
    $arguments = "`"$main`""
} else {
    Write-Host "Not found: $installed. Run install.bat first."
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
$places = @(
    [Environment]::GetFolderPath("Desktop"),
    (Join-Path ([Environment]::GetFolderPath("Programs")) "")
)
foreach ($place in $places) {
    $shortcut = $shell.CreateShortcut((Join-Path $place "Linum.lnk"))
    $shortcut.TargetPath = $target
    $shortcut.Arguments = $arguments
    $shortcut.WorkingDirectory = $root
    $shortcut.Description = "Linum: AI images and chat, locally"
    if (Test-Path $icon) { $shortcut.IconLocation = $icon }
    $shortcut.Save()
    Write-Host "Shortcut: $(Join-Path $place 'Linum.lnk')"
}

# Full version: the shortcut next to the folder gets the Linum icon (it keeps working the same way)
$top = Join-Path (Split-Path -Parent $root) "Linum.lnk"
if ((Test-Path $portable) -and (Test-Path $top) -and (Test-Path $icon)) {
    $shortcut = $shell.CreateShortcut($top)
    $shortcut.IconLocation = $icon
    $shortcut.Save()
}
