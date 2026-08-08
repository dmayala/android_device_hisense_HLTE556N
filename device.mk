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
