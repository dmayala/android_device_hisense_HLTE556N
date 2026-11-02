// SPDX-License-Identifier: Apache-2.0
// Keep the exact stock KeymasterUtils binary; relocate only its firmware path.
#include <dlfcn.h>
#include <cstring>
#include <cerrno>
#include <pthread.h>

namespace {
pthread_once_t qsee_once = PTHREAD_ONCE_INIT;
void* qsee;
void loadQsee() {
    qsee = dlopen("libQSEEComAPI.so", RTLD_NOW | RTLD_LOCAL);
}
}

extern "C" int QSEECom_start_app(void** handle, const char* path,
                                 const char* name, unsigned int size) {
    using Start = int (*)(void**, const char*, const char*, unsigned int);
    // Gatekeeper dlopens its passthrough implementation RTLD_LOCAL. Its QSEE
    // dependency is outside the preload's RTLD_NEXT search group, even though
    // it is loaded and visible to the implementation. Resolve by a handle in
    // the same linker namespace instead. Keep that handle for process lifetime.
    pthread_once(&qsee_once, loadQsee);
    const auto real = qsee ? reinterpret_cast<Start>(dlsym(qsee, "QSEECom_start_app")) : nullptr;
    if (!real) { errno = ENOSYS; return -1; }
    if (path && !std::strcmp(path, "/vendor/firmware_mnt/image"))
        path = "/system/a9-crypto/firmware/image";
    return real(handle, path, name, size);
}
