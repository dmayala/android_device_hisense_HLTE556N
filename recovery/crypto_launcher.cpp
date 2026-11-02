// SPDX-License-Identifier: Apache-2.0
// Service-local ordering and VINTF view, including an early ctl.start.
#include <fcntl.h>
#include <sys/mount.h>
#include <sys/system_properties.h>
#include <time.h>
#include <unistd.h>
#include <cstdio>
#include <cstring>

namespace {
bool propertyIs(const char* name, const char* expected) {
    char value[PROP_VALUE_MAX]{};
    __system_property_get(name, value);
    return !strcmp(value, expected);
}
time_t now() {
    timespec t{};
    return clock_gettime(CLOCK_MONOTONIC, &t) == 0 ? t.tv_sec : -1;
}
}

int main(int argc, char** argv) {
    if (argc < 3) return 1;
    const bool keystore = argc == 4 && !strcmp(argv[1], "keystore2") &&
        !strcmp(argv[2], "/system/bin/keystore2") && !strcmp(argv[3], "/tmp/misc/keystore");
    const bool keymaster = argc == 3 && !strcmp(argv[1], "keymaster") &&
        !strcmp(argv[2], "/system/bin/a9-crypto/hw/android.hardware.keymaster@4.1-service-qti");
    const bool gatekeeper = argc == 3 && !strcmp(argv[1], "gatekeeper") &&
        !strcmp(argv[2], "/system/bin/a9-crypto/hw/android.hardware.gatekeeper@1.0-service-qti");
    if (!keystore && !keymaster && !gatekeeper) return 1;
    const int fd = open("/tmp/a9-crypto-service.log",
                        O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC | O_NOFOLLOW, 0600);
    auto fail = [&](const char* reason) {
        if (fd >= 0) dprintf(fd, "R50 %s refused: %s\n", argv[1], reason);
        return 1;
    };
    const time_t start = now();
    if (start < 0) return fail("clock");
    while (!propertyIs("twrp.a9.crypto_ready", "1")) {
        const time_t current = now();
        if (propertyIs("twrp.a9.crypto_rom_props", "failed")) return fail("ROM properties");
        if (current < start || current - start >= 30) return fail("readiness timeout");
        usleep(100000);
    }
    if (!propertyIs("twrp.a9.crypto_rom_props", "ready")) return fail("ROM properties");
    // init's `namespace mnt` gives this process its own mount namespace, but
    // leaves it slave to the parent. Stop incoming vendor mount events too,
    // after preparation: TWRP can then unmount/remount vendor independently.
    if (mount(nullptr, "/", nullptr, MS_PRIVATE | MS_REC, nullptr)) return fail("private namespace");
    if (mount("/system/etc/a9-recovery-vintf", "/vendor/etc/vintf", nullptr, MS_BIND, nullptr))
        return fail("recovery VINTF bind");
    if (fd >= 0) dprintf(fd, "R50 %s executing with ROM properties and private recovery VINTF\n", argv[1]);
    execv(argv[2], argv + 2);
    return fail("exec");
}
