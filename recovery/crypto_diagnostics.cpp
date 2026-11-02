// SPDX-License-Identifier: Apache-2.0
// Recovery-only observability. No key buffers or binder payloads are inspected.
#include <android/log.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/uio.h>
#include <time.h>
#include <unistd.h>

#include <cstdio>
#include <cstring>
#include <atomic>

namespace {
int log_fd = -1;
constexpr off_t kLogLimit = 2 * 1024 * 1024;
std::atomic<__android_logger_function> downstream{__android_log_logd_logger};

void install_logger(__android_logger_function function) {
    using SetLogger = void (*)(__android_logger_function);
    auto real = reinterpret_cast<SetLogger>(dlsym(RTLD_NEXT, "__android_log_set_logger"));
    if (real) real(function);
}

void logger(const __android_log_message* message) {
    if (log_fd >= 0) {
        struct stat st{};
        if (fstat(log_fd, &st) == 0 && st.st_size < kLogLimit) {
            timespec now{};
            clock_gettime(CLOCK_MONOTONIC, &now);
            char header[160];
            int n = snprintf(header, sizeof(header), "[%lld.%03ld pid=%d tid=%d p=%d] ",
                             static_cast<long long>(now.tv_sec), now.tv_nsec / 1000000,
                             getpid(), gettid(), message->priority);
            const char* tag = message->tag ? message->tag : "";
            const char* body = message->message ? message->message : "";
            iovec parts[] = {{header, static_cast<size_t>(n)},
                             {const_cast<char*>(tag), strnlen(tag, 128)},
                             {const_cast<char*>(": "), 2},
                             {const_cast<char*>(body), strnlen(body, 8192)},
                             {const_cast<char*>("\n"), 1}};
            (void)writev(log_fd, parts, 5);
        }
    }
    // Keep logdstub's existing /tmp/logdw.txt channel too.
    downstream.load()(message);
}

int private_file(const char* name, const char* suffix) {
    char path[128];
    snprintf(path, sizeof(path), "/tmp/a9-crypto-%s.%s", name, suffix);
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd >= 0) (void)fchmod(fd, 0600);
    return fd;
}

__attribute__((constructor)) void initialize() {
    char exe[256];
    const ssize_t n = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
    if (n < 0) return;
    exe[n] = 0;
    const char* basename = strrchr(exe, '/');
    basename = basename ? basename + 1 : exe;
    const char* name = nullptr;
    if (!strcmp(basename, "recovery")) name = "recovery";
    if (!strcmp(basename, "keystore2")) name = "keystore2";
    if (!strcmp(basename, "qseecomd")) name = "qseecomd";
    if (!strcmp(basename, "android.hardware.keymaster@4.1-service-qti")) name = "keymaster";
    if (!strcmp(basename, "android.hardware.gatekeeper@1.0-service-qti")) name = "gatekeeper";
    if (!name) return;
    log_fd = private_file(name, "log");
    if (strcmp(name, "recovery")) {
        // Preserve recovery's existing stdout/stderr recovery.log destination.
        const int fd = private_file(name, "stdio");
        if (fd >= 0) {
            timespec now{};
            clock_gettime(CLOCK_MONOTONIC, &now);
            dprintf(fd, "[%lld.%03ld pid=%d] process start; stdout/stderr follow\n",
                    static_cast<long long>(now.tv_sec), now.tv_nsec / 1000000, getpid());
            (void)dup2(fd, STDOUT_FILENO);
            (void)dup2(fd, STDERR_FILENO);
            close(fd);
        }
    }
    install_logger(logger);
    __android_log_set_minimum_priority(ANDROID_LOG_DEBUG);
    __android_log_write(ANDROID_LOG_INFO, "A9Crypto", "R49 diagnostic logger installed");
}
}  // namespace

// libbase InitLogging/SetLogger may install a process logger after constructors.
// Preserve that destination while retaining our file copy (e.g. UiLogger).
extern "C" void __android_log_set_logger(__android_logger_function function) {
    if (log_fd < 0) { install_logger(function); return; }
    if (function != logger) downstream.store(function ? function : __android_log_logd_logger);
    install_logger(logger);
}
