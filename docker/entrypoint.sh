#!/usr/bin/env bash
set -euo pipefail
mkdir -p /app/.local /app/outputs
export DISPLAY=:99
Xvfb :99 -screen 0 1440x900x24 -nolisten tcp > /tmp/xvfb.log 2>&1 &
xvfb_pid=$!
sleep 1
if ! kill -0 "$xvfb_pid" 2>/dev/null; then
  cat /tmp/xvfb.log
  exit 1
fi
openbox --sm-disable > /tmp/openbox.log 2>&1 &
x11vnc -display :99 -localhost -nopw -forever -shared -rfbport 5900 -quiet > /tmp/x11vnc.log 2>&1 &
websockify --web=/usr/share/novnc 0.0.0.0:6080 127.0.0.1:5900 > /tmp/websockify.log 2>&1 &
exec python -m streamlit run app.py \
  --server.address 0.0.0.0 \
  --server.port 8501 \
  --server.headless true \
  --browser.gatherUsageStats false
