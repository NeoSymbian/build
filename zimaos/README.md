# zimaos: the home-server build environment

The builds run on a ZimaOS home server under `/DATA/AppData/symbian-build/` (Docker; logs in `logs/`, never `/` or
`/tmp`). The build image itself is [`docker/toolchain`](../docker/toolchain); this folder holds the rest:

| File | What |
|---|---|
| `desk/` | A watchable build desktop: a tmux terminal on a virtual X screen, shared over VNC (`docker compose up -d`) |
| `profile` | `~/.profile` for that terminal (`HOME=/DATA/AppData/symbian-build/home`) |

Moved here from `symbian-pixel/zimaos` (2026-11-06). Its `a64dev` image is replaced by `docker/toolchain`; its
`build.sh`/`setup.sh` (an old Phorepoc PinePhone experiment) were dropped.
