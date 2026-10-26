#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p app/app/src/main/assets/accessibility
x86_64-w64-mingw32-gcc -std=c11 -O2 -Wall -Wextra -Werror -mwindows -static -static-libgcc \
  runtime-accessibility/bridge.c -o app/app/src/main/assets/accessibility/winlator-a11y.exe \
  -loleacc -loleaut32 -lole32 -luuid -lws2_32 -luser32 -lgdi32
