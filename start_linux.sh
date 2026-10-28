#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "请先安装 Python 3.11+ 和 python3-venv"
  exit 1
fi
if [ ! -f ".venv/bin/python" ]; then
  python3 -m venv .venv
fi
PY=".venv/bin/python"
"$PY" -m pip install --disable-pip-version-check -r requirements-local.txt
"$PY" -m playwright install chromium
if [ -z "$(printenv DISPLAY || true)" ] && [ -z "$(printenv WAYLAND_DISPLAY || true)" ]; then
  echo "注意：未检测到 X11 或 Wayland，无法显示需要扫码登录的 Chrome 窗口。"
fi
echo "请通过 SSH 本地端口转发，在自己电脑打开 http://127.0.0.1:8501"
exec "$PY" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
