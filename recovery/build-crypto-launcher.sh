#!/bin/sh
# Standalone NDK compile only; never invokes a product build.
set -eu
: "${CXX:?Set CXX to an NDK aarch64-linux-android31-clang++}"
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"$CXX" -O2 -Wall -Wextra -Werror -fno-exceptions -fno-rtti -nostdlib++ \
    -Wl,-z,defs "$base/crypto_launcher.cpp" \
    -o "$base/root/system/bin/a9-crypto/launcher"
