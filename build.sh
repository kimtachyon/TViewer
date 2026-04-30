#!/usr/bin/env bash
# TViewer 빌드 & 설치
# PyInstaller 빌드 → /Applications 이동 → quarantine 제거 → LaunchServices 재등록
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="TViewer.app"
DIST="$ROOT/dist/$APP"
INSTALL="/Applications/$APP"
PY=/opt/homebrew/bin/python3.12
LSREG=/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister

cd "$ROOT"

echo "==> Build"
"$PY" -m PyInstaller TViewer_mac.spec --clean --noconfirm

[ -d "$DIST" ] || { echo "ERROR: 빌드 산출물 없음: $DIST" >&2; exit 1; }

echo "==> Install to /Applications"
[ -d "$INSTALL" ] && rm -rf "$INSTALL"
mv "$DIST" "$INSTALL"

echo "==> Strip quarantine"
xattr -dr com.apple.quarantine "$INSTALL" 2>/dev/null || true

echo "==> Re-register with LaunchServices"
"$LSREG" -u "$DIST" 2>/dev/null || true
"$LSREG" -f "$INSTALL"

echo "==> Done: $INSTALL"
