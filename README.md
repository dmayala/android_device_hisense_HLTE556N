# TWRP device tree — Hisense A9 (HLTE556N)

Unofficial TWRP device tree for the **Hisense A9**, the 6.1" E Ink Android
phone (`HLTE556N`, Snapdragon 662 / SM6115 `bengal`).

No TWRP build exists for this device. This tree is a work in progress.

## Device

| Property | Value |
|---|---|
| Model | Hisense A9 |
| Codename | `HLTE556N` |
| Platform | `bengal` (SM6115, Snapdragon 662) |
| Stock Android | 11, `RKQ1.210107.001` / `L2037.6.01.01` |
| Display | E Ink Carta 1200, 824×1648 |
| Slotting | Virtual A/B + dynamic partitions |
| Recovery | **Dedicated `recovery_a`/`recovery_b`, 96 MiB each** |
| Encryption | FBE + `dm-default-key` metadata + hardware-wrapped keys |

## Key facts

Everything below was measured directly from the stock firmware package, not
taken from forum posts.

**Dedicated recovery partition.** `recovery_a`/`recovery_b` are real, 24576
sectors × 4096 B = 100,663,296 B (96 MiB) each. This is *not* a
recovery-in-boot device, so `BOARD_USES_RECOVERY_AS_BOOT := false` and
`BUILD_TARGET=recovery`. `twrpdtgen` gets this wrong — it assumes A/B implies
recovery-as-boot.

**No kernel source needed.** `boot.img` and `recovery.img` ship the identical
kernel (both 15,050,789 bytes), so `prebuilt/kernel` extracted from the stock
recovery image is sufficient.

**Boot image geometry** (from the stock `recovery.img` header): header
version 2, page size 4096, base `0x00000000`, kernel offset `0x00008000`,
ramdisk offset `0x01000000`, tags offset `0x00000100`.

**Super is exactly 10 GiB** (start sector 225032, 2621440 sectors × 4096 B),
LP metadata group `qti_dynamic_partitions_a`/`_b` holding
`system`/`system_ext`/`product`/`vendor`. `twrpdtgen` guesses
`hisense_dynamic_partitions` from the brand name — also wrong.

**Frontlight node** is `/sys/class/backlight/panel0-backlight/brightness`,
taken from the stock `init.recovery.qcom.rc`, which writes `200` to it on
init.

## Known unknowns

- **Recovery framebuffer geometry.** The panel is 824×1648, but the stock
  recovery UI assets are 720×1280. `TARGET_RECOVERY_PIXEL_FORMAT` and
  `TARGET_SCREEN_DENSITY` are still guesses pending a runtime read of
  `/sys/class/graphics/fb0/{modes,virtual_size,bits_per_pixel}`.
- **E Ink rendering.** Stock `/system/bin/recovery` references no EPD or
  waveform sysfs nodes — only battery and thermal — which suggests the kernel
  panel driver auto-refreshes on framebuffer writes. If so, stock `minui` may
  work unmodified. Unproven.
- **Decryption is expected to fail.** Wrapped-key FBE plus `dm-default-key`,
  and the stock recovery ramdisk ships no keymaster or gatekeeper binaries to
  lift. The SD card (`/dev/block/mmcblk1p1`) is the intended working medium.
- **Virtual A/B flags.** `PRODUCT_VIRTUAL_AB_OTA` is deliberately *not* set in
  `device.mk` — it is not needed for a recovery-only build and adds build
  variables. Revisit if snapshot handling misbehaves.

## Building

```bash
repo init -u https://github.com/minimal-manifest-twrp/platform_manifest_twrp_aosp.git -b twrp-12.1
repo sync
. build/envsetup.sh
lunch twrp_HLTE556N-eng
mka recoveryimage
```

Or via GitHub Actions with
[Action-TWRP-Builder](https://github.com/azwhikaru/Action-TWRP-Builder):

| Input | Value |
|---|---|
| `MANIFEST_BRANCH` | `twrp-12.1` |
| `DEVICE_TREE_BRANCH` | `android-12.1` |
| `DEVICE_PATH` | `device/hisense/HLTE556N` |
| `DEVICE_NAME` | `HLTE556N` |
| `MAKEFILE_NAME` | `twrp_HLTE556N` |
| `BUILD_TARGET` | `recovery` |

## Flashing

Requires an unlocked bootloader and disabled AVB.

```bash
fastboot flash recovery_a twrp.img
adb reboot recovery
```

Do **not** use `fastboot boot` — Hisense's custom fastboot likely blocks it.
Keep an EDL cable and the stock firmware package on hand; flash `recovery_b`
only once `recovery_a` is proven.

## Credits

Initial skeleton generated with
[twrpdtgen](https://github.com/twrpdtgen/twrpdtgen) by SebaUbuntu, then
corrected against the stock firmware.
