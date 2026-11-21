# Creates Linum shortcuts on the Desktop and in the Start menu, with the Linum icon.
# Full version (archive from the website): the shortcut opens Linum.exe.
# Installed version (install.bat): Linum starts through pythonw.exe, so there is no black console window.

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $root "Linum.exe"
$python = Join-Path $root ".venv\Scripts\pythonw.exe"
$icon = Join-Path $root "assets\icons\exported\linum.ico"
if (Test-Path $launcher) {
    $target = $launcher
    $arguments = ""
} elseif (Test-Path $python) {
    $target = $python
    $arguments = "`"$(Join-Path $root 'main.py')`""
} else {
    Write-Host "Not found: $python. Run install.bat first."
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
