// SPDX-License-Identifier: Apache-2.0
// Recovery must remain usable when the slot's crypto HAL cannot start.
#include <android/binder_manager.h>
#include <hidl/ServiceManagement.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <time.h>
#include <unistd.h>
#include <sys/system_properties.h>

#include <cstring>
#include <cstdio>

namespace {
// One budget per process, shared by repeated lookups. This limits waiting for
// absent services, not a transaction to a service which has already registered.
constexpr int kWaitSeconds = 30;

void trace(const char* stage, const char* service) {
    timespec now{};
    clock_gettime(CLOCK_MONOTONIC, &now);
    int fd = open("/tmp/a9-crypto-wait.log", O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd >= 0) {
        dprintf(fd, "[%lld.%03ld pid=%d] %s %s\n", static_cast<long long>(now.tv_sec),
                now.tv_nsec / 1000000, getpid(), stage, service);
        close(fd);
    }
}

bool expired() {
    static const time_t deadline = [] {
        timespec now{};
        clock_gettime(CLOCK_MONOTONIC, &now);
        return now.tv_sec + kWaitSeconds;
    }();
    timespec now{};
    return clock_gettime(CLOCK_MONOTONIC, &now) != 0 || now.tv_sec >= deadline;
}

void timeout() {
    // The theme skips the startup password dialog and offers external MTP.
    // Never change tw_is_encrypted/tw_is_decrypted or any key material.
    __system_property_set("twrp.a9.crypto_timeout", "1");
    const char message[] = "A9: crypto service lookup timed out; data remains locked\n";
    int fd = open("/tmp/a9-crypto-wait.log", O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0600);
    if (fd >= 0) {
        (void)write(fd, message, sizeof(message) - 1);
        close(fd);
    }
}

bool cryptoInterface(const std::string& descriptor) {
    return descriptor.compare(0, 27, "android.hardware.keymaster@") == 0 ||
           descriptor.compare(0, 28, "android.hardware.gatekeeper@") == 0 ||
           descriptor.compare(0, 24, "android.hardware.weaver@") == 0;
}

AIBinder* waitForKeystore(const char* instance) {
    trace("lookup-enter", instance);
    do {
        // checkService returns an owned strong reference, as waitForService does.
        AIBinder* service = AServiceManager_checkService(instance);
        if (service) { trace("lookup-acquired", instance); return service; }
        if (expired()) break;
        usleep(100000);
    } while (true);
    timeout();
    trace("lookup-timeout", instance);
    return nullptr;
}

bool isKeystore(const char* instance) {
    return instance && !strcmp(instance, "android.system.keystore2.IKeystoreService/default");
}
}  // namespace

extern "C" AIBinder* AServiceManager_waitForService(const char* instance) {
    if (isKeystore(instance)) return waitForKeystore(instance);
    auto real = reinterpret_cast<decltype(&AServiceManager_waitForService)>(
        dlsym(RTLD_NEXT, "AServiceManager_waitForService"));
    return real ? real(instance) : nullptr;
}

namespace android::hardware::details {
sp<::android::hidl::base::V1_0::IBase> getRawServiceInternal(
        const std::string& descriptor, const std::string& instance, bool retry, bool getStub) {
    using Lookup = sp<::android::hidl::base::V1_0::IBase> (*)(
        const std::string&, const std::string&, bool, bool);
    static auto real = reinterpret_cast<Lookup>(dlsym(RTLD_NEXT,
        "_ZN7android8hardware7details21getRawServiceInternalERKNSt3__112basic_stringIcNS2_11char_traitsIcEENS2_9allocatorIcEEEESA_bb"));
    if (!real) return nullptr;
    if (!retry || getStub || !cryptoInterface(descriptor))
        return real(descriptor, instance, retry, getStub);
    trace("hidl-lookup-enter", descriptor.c_str());
    do {
        auto service = real(descriptor, instance, false, false);
        if (service != nullptr) { trace("hidl-lookup-acquired", descriptor.c_str()); return service; }
        if (expired()) break;
        usleep(100000);
    } while (true);
    timeout();
    trace("hidl-lookup-timeout", descriptor.c_str());
    return nullptr;
}
}  // namespace android::hardware::details
