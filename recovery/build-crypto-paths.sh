#!/bin/sh
# Standalone NDK compile only; never invokes a product build.
set -eu
: "${CXX:?Set CXX to an NDK aarch64-linux-android31-clang++}"
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"$CXX" -shared -fPIC -O2 -Wall -Wextra -Werror -fno-exceptions \
    -fno-rtti -nostdlib++ -Wl,-z,defs -Wl,-soname,liba9_crypto_paths.so \
    "$base/crypto_paths.cpp" -ldl \
    -o "$base/root/system/a9-crypto/lib64/liba9_crypto_paths.so"
