#
# Copyright (C) 2026 The Android Open Source Project
# Copyright (C) 2026 SebaUbuntu's TWRP device tree generator
#
# SPDX-License-Identifier: Apache-2.0
#
# Hisense A9 (HLTE556N) — TWRP device tree
#
# Values marked [MEASURED] were read directly out of the stock firmware
# package (recovery.img headers, rawprogram*.xml, super LP metadata,
# COM4_PartitionsList.xml). Values marked [GUESS] came from twrpdtgen and
# still need runtime confirmation. See docs/twrp-port-findings.md.
#

DEVICE_PATH := device/hisense/HLTE556N

# For building with minimal manifest
ALLOW_MISSING_DEPENDENCIES := true

# A/B — Virtual A/B (ro.virtual_ab.enabled=true) [MEASURED]
AB_OTA_UPDATER := true
AB_OTA_PARTITIONS += \
    system \
    system_ext \
    product \
    vendor

# [MEASURED] This device has DEDICATED recovery_a/recovery_b partitions
# (24576 sectors x 4096 = 96 MiB each). It is NOT recovery-in-boot.
# twrpdtgen defaulted this to true because the device is A/B — that is wrong
# here and would produce an unbootable/incorrectly-targeted image.
BOARD_USES_RECOVERY_AS_BOOT := false

# Architecture
TARGET_ARCH := arm64
TARGET_ARCH_VARIANT := armv8-a
TARGET_CPU_ABI := arm64-v8a
TARGET_CPU_ABI2 :=
TARGET_CPU_VARIANT := generic
TARGET_CPU_VARIANT_RUNTIME := generic

TARGET_2ND_ARCH := arm
TARGET_2ND_ARCH_VARIANT := armv7-a-neon
TARGET_2ND_CPU_ABI := armeabi-v7a
TARGET_2ND_CPU_ABI2 := armeabi
TARGET_2ND_CPU_VARIANT := generic
TARGET_2ND_CPU_VARIANT_RUNTIME := cortex-a9

# APEX
OVERRIDE_TARGET_FLATTEN_APEX := true

# Bootloader
TARGET_BOOTLOADER_BOARD_NAME := bengal
TARGET_NO_BOOTLOADER := true

# Display [GUESS — confirm from /sys/class/graphics/fb0 in Phase 3]
TARGET_SCREEN_DENSITY := 360

# Kernel [MEASURED from recovery.img header]
#   header_version 2, page_size 4096, base 0x0,
#   kernel 0x8000, ramdisk 0x1000000, tags 0x100
BOARD_BOOT_HEADER_VERSION := 2
BOARD_BOOTIMG_HEADER_VERSION := $(BOARD_BOOT_HEADER_VERSION)
BOARD_KERNEL_BASE := 0x00000000
BOARD_KERNEL_PAGESIZE := 4096
BOARD_KERNEL_OFFSET := 0x00008000
BOARD_RAMDISK_OFFSET := 0x01000000
BOARD_KERNEL_TAGS_OFFSET := 0x00000100
BOARD_KERNEL_CMDLINE := console=ttyMSM0,115200n8 earlycon=msm_geni_serial,0x4a90000 androidboot.hardware=qcom androidboot.console=ttyMSM0 androidboot.memcg=1 lpm_levels.sleep_disabled=1 video=vfb:640x400,bpp=32,memsize=3072000 msm_rtb.filter=0x237 service_locator.enable=1 swiotlb=2048 loop.max_part=7 buildvariant=user
BOARD_MKBOOTIMG_ARGS += --header_version $(BOARD_BOOT_HEADER_VERSION)
BOARD_MKBOOTIMG_ARGS += --base $(BOARD_KERNEL_BASE)
BOARD_MKBOOTIMG_ARGS += --kernel_offset $(BOARD_KERNEL_OFFSET)
BOARD_MKBOOTIMG_ARGS += --ramdisk_offset $(BOARD_RAMDISK_OFFSET)
BOARD_MKBOOTIMG_ARGS += --tags_offset $(BOARD_KERNEL_TAGS_OFFSET)
BOARD_KERNEL_IMAGE_NAME := Image

# Kernel - prebuilt [MEASURED]
# kernel, dtb.img and dtbo.img are extracted from the DEVICE's own recovery_b
# (kernel 15,047,394 bytes). Do not use the stock package's images -- the
# device runs a different build despite reporting the same version prop.
TARGET_FORCE_PREBUILT_KERNEL := true
ifeq ($(TARGET_FORCE_PREBUILT_KERNEL),true)
TARGET_PREBUILT_KERNEL := $(DEVICE_PATH)/prebuilt/kernel
TARGET_PREBUILT_DTB := $(DEVICE_PATH)/prebuilt/dtb.img
BOARD_MKBOOTIMG_ARGS += --dtb $(TARGET_PREBUILT_DTB)
BOARD_INCLUDE_DTB_IN_BOOTIMG :=
BOARD_PREBUILT_DTBOIMAGE := $(DEVICE_PATH)/prebuilt/dtbo.img
BOARD_KERNEL_SEPARATED_DTBO :=

# Embed the recovery DTBO in the recovery image.
#
# WHY: builds 1 and 2 both produced images with `recovery_dtbo: size=0`, while
# the device's own stock recovery_b has size=88722 at offset 26202112. Setting
# BOARD_PREBUILT_DTBOIMAGE alone is NOT enough -- it builds dtbo.img as a
# separate artifact and never passes it to mkbootimg, so the overlays that
# adapt the device tree to this hardware were simply absent. Both of those
# builds failed to boot with no splash and no adb, which is exactly how a
# kernel with a mismatched device tree dies.
#
# Verify after building:
#   dd if=recovery.img bs=1 skip=1632 count=4 | od -A none -t u4   # must be 88722
BOARD_MKBOOTIMG_ARGS += --recovery_dtbo $(BOARD_PREBUILT_DTBOIMAGE)
endif

# Partitions [MEASURED]
BOARD_FLASH_BLOCK_SIZE := 262144 # (BOARD_KERNEL_PAGESIZE * 64)
BOARD_BOOTIMAGE_PARTITION_SIZE := 100663296     # 96 MiB
BOARD_RECOVERYIMAGE_PARTITION_SIZE := 100663296 # 96 MiB
BOARD_HAS_LARGE_FILESYSTEM := true
BOARD_SYSTEMIMAGE_PARTITION_TYPE := ext4
BOARD_USERDATAIMAGE_FILE_SYSTEM_TYPE := f2fs
BOARD_VENDORIMAGE_FILE_SYSTEM_TYPE := ext4
TARGET_COPY_OUT_VENDOR := vendor

# Metadata partition is present and required (dm-default-key lives here)
BOARD_USES_METADATA_PARTITION := true

# Dynamic partitions [MEASURED]
#   super: start_sector 225032, num_partition_sectors 2621440 @ 4096 B
#          = 10,737,418,240 bytes (exactly 10 GiB)
#   LP metadata group name is qti_dynamic_partitions_a / _b —
#   twrpdtgen guessed "hisense_dynamic_partitions" from the brand. Wrong.
BOARD_SUPER_PARTITION_SIZE := 10737418240
BOARD_SUPER_PARTITION_GROUPS := qti_dynamic_partitions
BOARD_QTI_DYNAMIC_PARTITIONS_PARTITION_LIST := system system_ext product vendor
BOARD_QTI_DYNAMIC_PARTITIONS_SIZE := 5364514816 # (super / 2) - 4 MiB

# Platform
TARGET_BOARD_PLATFORM := bengal

# Recovery
TARGET_RECOVERY_PIXEL_FORMAT := RGBX_8888 # [GUESS — confirm in Phase 3]
TARGET_USERIMAGES_USE_EXT4 := true
TARGET_USERIMAGES_USE_F2FS := true
TARGET_USES_MKE2FS := true

# Verified Boot
BOARD_AVB_ENABLE := true
BOARD_AVB_MAKE_VBMETA_IMAGE_ARGS += --flags 3

# Hack: prevent anti rollback
PLATFORM_SECURITY_PATCH := 2099-12-31
VENDOR_SECURITY_PATCH := 2099-12-31
PLATFORM_VERSION := 16.1.0
# build/make validates PLATFORM_VERSION against the known-version list; without
# this it can reject the 16.1.0 anti-rollback value outright.
PLATFORM_VERSION_LAST_STABLE := $(PLATFORM_VERSION)

# TWRP Configuration
TW_THEME := portrait_hdpi
TW_EXTRA_LANGUAGES := true
TW_SCREEN_BLANK_ON_BOOT := true
TW_INPUT_BLACKLIST := "hbtp_vm"
TW_USE_TOOLBOX := true
TW_INCLUDE_REPACKTOOLS := true
TW_INCLUDE_FASTBOOTD := true
TW_INCLUDE_NTFS_3G := true

# Frontlight [MEASURED from stock init.recovery.qcom.rc, which writes 200 to
# this node on init]
TW_BRIGHTNESS_PATH := /sys/class/backlight/panel0-backlight/brightness
TW_MAX_BRIGHTNESS := 255
TW_DEFAULT_BRIGHTNESS := 200

# Crypto — expected to FAIL on this device (wrapped-key FBE + dm-default-key,
# and stock recovery ships no keymaster/gatekeeper to lift). Left on so the
# failure is visible in the log; the SD card is the intended working medium.
TW_INCLUDE_CRYPTO := true
TW_INCLUDE_CRYPTO_FBE := true

# MUST be set explicitly alongside TW_INCLUDE_CRYPTO.
#
# bootable/recovery/Android.mk has two separate conditionals:
#   ifneq ($(TW_INCLUDE_LIBRESETPROP),)      -> LINKS the binary against it
#   ifeq  ($(TW_INCLUDE_LIBRESETPROP), true) -> INSTALLS it (TWRP_REQUIRED_MODULES)
#
# TW_INCLUDE_CRYPTO enables the first but not reliably the second, so build 3
# produced a recovery binary linked against a library that was never packaged:
#   CANNOT LINK EXECUTABLE "/system/bin/recovery":
#   library "libresetprop.so" not found: needed by main executable
# The GUI therefore never started -- blank screen, while adb still worked
# because adbd is a separate process. libresetprop.so was built and installed
# to out/.../system/lib64/ but never to out/.../recovery/root/system/lib64/.
TW_INCLUDE_LIBRESETPROP := true
TW_INCLUDE_RESETPROP := true
