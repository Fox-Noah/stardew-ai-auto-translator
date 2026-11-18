#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
BUILD_ROOT=${STARDEW_APPIMAGE_BUILD_DIR:-"${ROOT}/.appimage"}
RUN_ID=$(date +%Y%m%d-%H%M%S)
APPDIR="${BUILD_ROOT}/AppDir-${RUN_ID}"
DISTDIR="${BUILD_ROOT}/dist-${RUN_ID}"
WORKDIR="${BUILD_ROOT}/work-${RUN_ID}"
OUTPUT=${1:-"${ROOT}/stardew-ai-auto-translator-${RUN_ID}.AppImage"}

command -v appimagetool >/dev/null || { echo '缺少 appimagetool' >&2; exit 1; }
python3 -m PyInstaller --version >/dev/null || { echo '缺少 PyInstaller' >&2; exit 1; }
python3 -c 'import requests' >/dev/null 2>&1 || {
  echo '缺少 Python 依赖 requests；请重建 AppImage 打包镜像或先安装 requirements.txt' >&2
  exit 1
}

mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/applications" "${DISTDIR}" "${WORKDIR}"
python3 -m PyInstaller --noconfirm --clean --onedir \
  --name stardew-ai-auto-translator \
  --paths "${ROOT}" \
  --distpath "${DISTDIR}" --workpath "${WORKDIR}" --specpath "${WORKDIR}" \
  "${ROOT}/main.py"
cp -a "${DISTDIR}/stardew-ai-auto-translator/." "${APPDIR}/usr/bin/"
cp "${ROOT}/packaging/appimage/AppRun" "${APPDIR}/AppRun"
cp "${ROOT}/packaging/appimage/stardew-ai-auto-translator.desktop" \
  "${APPDIR}/usr/share/applications/stardew-ai-auto-translator.desktop"
cp "${ROOT}/packaging/appimage/stardew-ai-auto-translator.desktop" "${APPDIR}/"
chmod +x "${APPDIR}/AppRun"
mkdir -p "$(dirname -- "${OUTPUT}")"
appimagetool "${APPDIR}" "${OUTPUT}"
echo "已生成：${OUTPUT}"
