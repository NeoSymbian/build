#!/bin/sh
set -eu
export DISPLAY=:0
rm -f /tmp/.X0-lock /tmp/.X11-unix/X0   # stale after a container restart
Xvfb :0 -screen 0 1600x1000x24 -nolisten tcp &
i=0; while [ ! -e /tmp/.X11-unix/X0 ] && [ $i -lt 100 ]; do sleep 0.1; i=$((i+1)); done
fluxbox >/dev/null 2>&1 &
x11vnc -display :0 -rfbauth /secrets/vncpass -rfbport 5900 -forever -shared -quiet &
cd /DATA/AppData/symbian-build
# keep a terminal attached to the "build" tmux session; reopen it if someone closes the window
while true; do
  xterm -fa Monospace -fs 11 -geometry 175x52+0+0 -title "symbian-build" -e tmux new -A -s build || true
  sleep 1
done
