#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p app/app/src/main/assets/nvda
x86_64-w64-mingw32-gcc -std=c11 -O2 -Wall -Wextra -Werror -mwindows -static -static-libgcc \
  runtime-nvda/launcher.c -o app/app/src/main/assets/nvda/nvda-launcher.exe
