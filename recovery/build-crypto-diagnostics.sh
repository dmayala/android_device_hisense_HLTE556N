#!/bin/sh
# Standalone NDK build; no product build.
set -eu
: "${CXX:?Set CXX to an NDK aarch64-linux-android31-clang++}"
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"$CXX" -shared -fPIC -O2 -Wall -Wextra -Werror -fno-exceptions \
    -fno-rtti -nostdlib++ -Wl,-z,defs -Wl,-soname,liba9_crypto_diagnostics.so \
    "$base/crypto_diagnostics.cpp" -llog -ldl \
    -o "$base/root/system/lib64/liba9_crypto_diagnostics.so"
