# Watchable build desktop: a terminal (tmux session "build") on a virtual X screen, shared over VNC.
FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      xvfb x11vnc fluxbox xterm fonts-dejavu-core tmux docker-cli \
      git curl ca-certificates python3 file xxd procps less \
    && rm -rf /var/lib/apt/lists/*
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
