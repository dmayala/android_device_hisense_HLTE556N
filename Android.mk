#
# Copyright (C) 2026 The Android Open Source Project
# Copyright (C) 2026 SebaUbuntu's TWRP device tree generator
#
# SPDX-License-Identifier: Apache-2.0
#

LOCAL_PATH := $(call my-dir)

ifeq ($(TARGET_DEVICE),HLTE556N)
include $(call all-subdir-makefiles,$(LOCAL_PATH))

# Hisense E Ink library, extracted from stock recovery's librecovery_ui.so.
#
# minuitwrp's graphics_hmct_epd backend dlopens this to drive the panel through
# Hisense's software TCON -- this panel is not driven by DRM (stock's own
# atomic commits fail exactly as TWRP's do).
#
# LOCAL_CHECK_ELF_FILES := false is required: the library's DT_NEEDED entries
# (libpng, libz, liblog, libcutils, libutils, libbase, libc++) are resolved at
# runtime inside the recovery ramdisk, and the build-time checker cannot see
# recovery variants of all of them.
include $(CLEAR_VARS)
LOCAL_MODULE := libhmct_epd
LOCAL_MODULE_OWNER := hisense
LOCAL_SRC_FILES := prebuilt/libhmct_epd.so
LOCAL_MODULE_CLASS := SHARED_LIBRARIES
LOCAL_MODULE_SUFFIX := .so
LOCAL_MULTILIB := 64
LOCAL_MODULE_PATH := $(TARGET_RECOVERY_ROOT_OUT)/system/lib64
LOCAL_CHECK_ELF_FILES := false
LOCAL_STRIP_MODULE := false
include $(BUILD_PREBUILT)

# libion, taken from the stock recovery ramdisk. Required by the vendor
# keymaster HAL (/vendor/lib64/libkeymasterdeviceutils.so needs it) and absent
# from TWRP's ramdisk, so without it the HAL cannot link and /data cannot
# decrypt:
#   CANNOT LINK EXECUTABLE ".../android.hardware.keymaster@4.1-service-qti":
#   library "libion.so" not found
# Verified on-device: with libion present, init.svc.vendor.keymaster-4-1 and
# gatekeeper-1-0 both go to "running" and keystore2 stops crash-looping.
include $(CLEAR_VARS)
LOCAL_MODULE := libion_recovery
LOCAL_MODULE_STEM := libion
LOCAL_MODULE_OWNER := hisense
LOCAL_SRC_FILES := prebuilt/libion.so
LOCAL_MODULE_CLASS := SHARED_LIBRARIES
LOCAL_MODULE_SUFFIX := .so
LOCAL_MULTILIB := 64
LOCAL_MODULE_PATH := $(TARGET_RECOVERY_ROOT_OUT)/system/lib64
LOCAL_CHECK_ELF_FILES := false
LOCAL_STRIP_MODULE := false
include $(BUILD_PREBUILT)
endif
