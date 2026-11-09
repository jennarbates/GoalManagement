#!/bin/bash
# Builds Workbook.app next to this script.
# Needs Xcode 16+ or the matching Command Line Tools (xcode-select --install).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HERE/Workbook.app"

cd "$HERE/mac"
swift build -c release
BIN_DIR="$(swift build -c release --show-bin-path)"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN_DIR/WorkbookApp" "$APP/Contents/MacOS/Workbook"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key><string>Workbook</string>
    <key>CFBundleIdentifier</key><string>local.goalmanagement.workbook</string>
    <key>CFBundleName</key><string>Workbook</string>
    <key>CFBundleDisplayName</key><string>Workbook</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>1.0</string>
    <key>CFBundleVersion</key><string>1</string>
    <key>LSMinimumSystemVersion</key><string>14.0</string>
    <key>NSHighResolutionCapable</key><true/>
    <key>NSPrincipalClass</key><string>NSApplication</string>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsLocalNetworking</key><true/>
    </dict>
</dict>
</plist>
PLIST

# Ad hoc signature so macOS will launch it locally.
codesign --force --sign - "$APP" >/dev/null

echo "Built $APP"
echo "Open it with: open \"$APP\""
