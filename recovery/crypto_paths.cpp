// SPDX-License-Identifier: Apache-2.0
// Keep the exact stock KeymasterUtils binary; relocate only its firmware path.
#include <dlfcn.h>
#include <cstring>
#include <cerrno>

extern "C" int QSEECom_start_app(void** handle, const char* path,
                                 const char* name, unsigned int size) {
    using Start = int (*)(void**, const char*, const char*, unsigned int);
    const auto real = reinterpret_cast<Start>(dlsym(RTLD_NEXT, "QSEECom_start_app"));
    if (!real) { errno = ENOSYS; return -1; }
    if (path && !std::strcmp(path, "/vendor/firmware_mnt/image"))
        path = "/system/a9-crypto/firmware/image";
    return real(handle, path, name, size);
}
