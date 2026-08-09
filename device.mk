#
# Copyright (C) 2026 The Android Open Source Project
# Copyright (C) 2026 SebaUbuntu's TWRP device tree generator
#
# SPDX-License-Identifier: Apache-2.0
#

LOCAL_PATH := device/hisense/HLTE556N
# A/B
AB_OTA_POSTINSTALL_CONFIG += \
    RUN_POSTINSTALL_system=true \
    POSTINSTALL_PATH_system=system/bin/otapreopt_script \
    FILESYSTEM_TYPE_system=ext4 \
    POSTINSTALL_OPTIONAL_system=true

# Boot control HAL
#
# NOTE: twrpdtgen emits PRODUCT_STATIC_BOOT_CONTROL_HAL, which was removed in
# Android 12 and hard-errors in build/make:
#   "PRODUCT_STATIC_BOOT_CONTROL_HAL is obsolete. Use shared library module
#    instead."  (see build/make Changes.md)
# The replacement is to ship the HAL as a normal module plus its .recovery
# variant, so it is present in the recovery ramdisk for A/B slot switching.
PRODUCT_PACKAGES += \
    android.hardware.boot@1.0-impl \
    android.hardware.boot@1.0-impl.recovery \
    android.hardware.boot@1.0-service

PRODUCT_PACKAGES += \
    bootctrl.bengal \
    bootctrl.bengal.recovery

PRODUCT_PACKAGES += \
    otapreopt_script \
    cppreopts.sh \
    update_engine \
    update_verifier \
    update_engine_sideload

# Hisense E Ink prebuilt (extracted from stock recovery's librecovery_ui.so).
#
# This panel is NOT driven by DRM -- stock's own atomic commits fail exactly as
# TWRP's do. Stock renders through a Hisense software TCON that streams E Ink
# waveform frames, and that whole implementation is exported from this library,
# so minuitwrp's graphics_hmct_epd backend dlopens it rather than
# reimplementing waveform generation.
#
# The backend probes for this file at runtime: if it is missing, minui simply
# falls back to DRM. Renamed from librecovery_ui.so to avoid colliding with
# AOSP's library of that name.
# NOTE: this must NOT be a PRODUCT_COPY_FILES entry. build/make rejects ELF
# files there:
#   "found ELF prebuilt in PRODUCT_COPY_FILES, use cc_prebuilt_binary /
#    cc_prebuilt_library_shared instead"
# It is installed by the BUILD_PREBUILT rule in Android.mk instead, which also
# lets us disable the ELF dependency check (the library's DT_NEEDED entries are
# satisfied at runtime inside the recovery ramdisk, not at build time).
PRODUCT_PACKAGES += \
    libhmct_epd

# BCB-clearing hook for "Reboot System" from the TWRP UI.
#
# TWRP's rb_system path calls /system/bin/rebootsystem.sh but never clears the
# bootloader control block itself, so `boot-recovery` survives and the device
# boots straight back into recovery. Copied explicitly as well as via
# recovery/root/ so it cannot be missed. Shell script, not an ELF, so
# PRODUCT_COPY_FILES is fine here.
PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/recovery/root/system/bin/rebootsystem.sh:$(TARGET_COPY_OUT_RECOVERY)/root/system/bin/rebootsystem.sh

# libion is required by the vendor keymaster HAL and is NOT in TWRP's ramdisk
# (stock recovery's ramdisk does ship it). Without it the HAL cannot start:
#   CANNOT LINK EXECUTABLE ".../android.hardware.keymaster@4.1-service-qti":
#   library "libion.so" not found: needed by /vendor/lib64/libkeymasterdeviceutils.so
# and keystore2 then crash-loops, so /data never decrypts. Verified live on
# device: pushing libion.so let the HAL start and keystore2 go from
# "restarting" to "running".
PRODUCT_PACKAGES += \
    libion
