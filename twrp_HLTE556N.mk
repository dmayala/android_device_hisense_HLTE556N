#
# Copyright (C) 2026 The Android Open Source Project
# Copyright (C) 2026 SebaUbuntu's TWRP device tree generator
#
# SPDX-License-Identifier: Apache-2.0
#

# Inherit from those products. Most specific first.
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/full_base_telephony.mk)

# Inherit some common TWRP stuff.
# NOTE: twrpdtgen emits vendor/omni/config/common.mk, which does NOT exist in
# the twrp-12.1 minimal manifest. vendor/twrp (android_vendor_twrp) does.
$(call inherit-product, vendor/twrp/config/common.mk)

# Inherit from HLTE556N device
$(call inherit-product, device/hisense/HLTE556N/device.mk)

PRODUCT_DEVICE := HLTE556N
PRODUCT_NAME := twrp_HLTE556N
PRODUCT_BRAND := Hisense
PRODUCT_MODEL := A9
PRODUCT_MANUFACTURER := hisense

PRODUCT_GMS_CLIENTID_BASE := android-hisense

PRODUCT_BUILD_PROP_OVERRIDES += \
    PRIVATE_BUILD_DESC="HLTE556N-user 11 RKQ1.210107.001 L2037.6.01.01 release-keys"

BUILD_FINGERPRINT := Hisense/HLTE556N/HLTE556N:11/RKQ1.210107.001/L2037.6.01.01:user/release-keys
