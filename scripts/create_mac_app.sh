#!/bin/bash
# Creates ~/Applications/Linum.app: a small app bundle that starts Linum with its icon,
# so it shows up in Launchpad, Spotlight and the Dock as "Linum", not "Python".
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$HOME/Applications/Linum.app"
PYTHON="$ROOT/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "Not found: $PYTHON. Run install.command first."
    exit 1
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# The program inside the bundle: go to the Linum folder and start main.py
cat > "$APP/Contents/MacOS/Linum" <<EOF
#!/bin/bash
cd "$ROOT"
exec "$PYTHON" "$ROOT/main.py"
EOF
chmod +x "$APP/Contents/MacOS/Linum"

# Icon: the Linum picture in all the sizes macOS wants
ICONSET="$(mktemp -d)/linum.iconset"
mkdir -p "$ICONSET"
SOURCE="$ROOT/assets/icons/source/linum-icon-1-outline.jpg"
for size in 16 32 128 256 512; do
    sips -s format png -z $size $size "$SOURCE" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
    sips -s format png -z $((size * 2)) $((size * 2)) "$SOURCE" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/linum.icns"

cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>Linum</string>
    <key>CFBundleDisplayName</key><string>Linum</string>
    <key>CFBundleIdentifier</key><string>app.linum</string>
    <key>CFBundleExecutable</key><string>Linum</string>
    <key>CFBundleIconFile</key><string>linum.icns</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>LSMinimumSystemVersion</key><string>12.0</string>
    <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
EOF

echo "App: $APP"
