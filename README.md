# TWRP device tree — Hisense A9 (HLTE556N)

Unofficial TWRP for the **Hisense A9**, the 6.1" E Ink Android phone
(`HLTE556N`, Snapdragon 662 / SM6115 `bengal`).

**Status: working.** Boots, renders the full GUI on the E Ink panel, takes
touch input, decrypts `/data`, reaches fastbootd, and transfers files over MTP.
All of it builds from this tree — nothing here is a hand-patched image.

Everything below was measured on a real device or extracted from the stock
firmware. Where something is unproven it says so.

---

## Read this before you flash

Four rules. Each one is here because breaking it cost hours.

1. **Flash to *both* `recovery_a` and `recovery_b`, and leave the active slot
   alone.** A recovery that fails to boot does not consume the slot retry
   budget, so covering both slots means a bad recovery can never strand you.
2. **Flash only from *bootloader* fastboot.** Check `fastboot getvar
   is-userspace` prints `no`. From fastbootd (`yes`) the flash prints
   `Sending… OKAY / Writing… OKAY` **and writes nothing** — the old recovery
   boots and no error appears anywhere.
3. **`fastboot boot` does not exist on this device.** Hisense's fastboot
   returns `unknown command`. There is no RAM-boot rescue path; recovery must
   be flashed to be tested.
4. **Never `fastboot erase misc`.** It destroys the Virtual A/B header at
   offset 32768. To clear a stuck BCB, zero only the first 2048 bytes.

Keep an EDL cable and the stock firmware package on hand before you start.

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
| SD card | `/dev/block/mmcblk1p1` (vfat) |

**Dedicated recovery partition.** `recovery_a`/`recovery_b` are real, 24576
sectors × 4096 B = 100,663,296 B (96 MiB) each. This is *not* a
recovery-in-boot device, so `BOARD_USES_RECOVERY_AS_BOOT := false` and
`BUILD_TARGET=recovery`. `twrpdtgen` gets this wrong — it assumes A/B implies
recovery-as-boot.

**Super is exactly 10 GiB** (start sector 225032, 2621440 sectors × 4096 B),
LP metadata group `qti_dynamic_partitions_a`/`_b` holding
`system`/`system_ext`/`product`/`vendor`. `twrpdtgen` guesses
`hisense_dynamic_partitions` from the brand name — also wrong.

## What works

| Capability | Notes |
|---|---|
| E Ink display, full 824×1648 | see below; log line `Using hmct epd graphics.` |
| Touch input | |
| Root adb shell | `uid=0`, `u:r:su:s0` |
| `/data` decryption | FBE + wrapped keys, mounts at full size |
| Raw partition backup and restore | byte-exact, size-verified |
| `Wipe → Format Data` | |
| fastbootd | `adb reboot fastboot`; `fastboot flash system <gsi>` resolves the slot |
| MTP | enumerates as `18d1:4ee2`; transfers both ways; adb stays up |
| Returns to Android cleanly | no sticky BCB |

### How the display works

This panel is **not driven by DRM**. Stock recovery's own atomic commits fail
exactly as TWRP's did — the failure was never a TWRP bug. Stock renders through
a Hisense **software TCON** that streams E Ink waveform frames, and that entire
implementation is *exported* from stock's `librecovery_ui.so`.

So minuitwrp gained a `graphics_hmct_epd` backend that ships that library as a
prebuilt (`prebuilt/libhmct_epd.so`), `dlopen`s it, and calls
`gr_init → InitEpd → EpdUnblank → drawImage(824x1648 RGBA)`. It is selected by
**runtime probe**: if the library is absent, minui falls back to DRM.

`prebuilt/libhmct_epd.so` **is Hisense's binary**, not ours. It is extracted
unmodified from the stock recovery image on the device and renamed only to avoid
colliding with AOSP's own `librecovery_ui.so`. It is included here because the
recovery does not render without it and there is no reimplementation.

It is **not covered by this tree's licence**, and Hisense has published no terms
that permit redistributing it. It ships here on the same footing as the vendor
blobs in most unofficial device trees for Qualcomm hardware. If that matters for
your use, delete it and extract your own from your device's `recovery_b` — the
backend probes for it at runtime and minui falls back to DRM when it is absent,
so the build succeeds either way. It just will not render on this panel.

Do not re-investigate the EPD sysfs nodes, the waveform, the DSI-to-DPI bridge,
or ADF — all were measured against live stock and excluded. The
`tc358767 ret=-107` error is benign; Android logs it constantly while rendering
perfectly.

## Building

You need **these forks**, not upstream. The `graphics_hmct_epd` backend and the
monochrome theme live in the recovery fork; a build against stock
minimal-manifest-twrp will compile and produce an image that does not render.

| Repo | Branch |
|---|---|
| `dmayala/platform_manifest_twrp_aosp` (manifest) | `twrp-12.1` |
| `dmayala/android_bootable_recovery` (recovery) | `android-12.1` |
| `dmayala/android_device_hisense_HLTE556N` (this tree) | `android-12.1` |

```bash
repo init -u https://github.com/dmayala/platform_manifest_twrp_aosp.git -b twrp-12.1
repo sync
. build/envsetup.sh
lunch twrp_HLTE556N-eng
mka recoveryimage
```

Or via GitHub Actions with
[Action-TWRP-Builder](https://github.com/dmayala/Action-TWRP-Builder):

| Input | Value |
|---|---|
| `MANIFEST_BRANCH` | `twrp-12.1` |
| `DEVICE_TREE_BRANCH` | `android-12.1` |
| `DEVICE_PATH` | `device/hisense/HLTE556N` |
| `DEVICE_NAME` | `HLTE556N` |
| `MAKEFILE_NAME` | `twrp_HLTE556N` |
| `BUILD_TARGET` | `recovery` |

`BUILD_TARGET` is `recovery`, **not** `recovery.img` — the workflow runs
`make ${BUILD_TARGET}image`. Its "Display Run Parameters" step echoes
`${BUILD_TARGET}.img`, so copying that value out of an old run's log fails with
`ninja: unknown target 'recovery.imgimage'`.

### Re-extract the prebuilts from your own device

`prebuilt/` carries `kernel`, `dtb.img`, `dtbo.img` and `libhmct_epd.so`. The
kernel and device trees here came from **this** device's `recovery_b`, and
**if your firmware differs you must re-extract your own.**

This is not hypothetical. The device runs a kernel of **15,047,394** bytes
while the stock firmware package ships **15,050,789** — even though both report
`ro.vendor.build.version.incremental = L2037.6.01.01`. That property is not a
build identifier on this device. A mismatched kernel produces a recovery that
**does not boot at all** — no splash, no adb, no clue as to why.

Pull them from the device, not from the firmware package.

### Verify the built image before flashing

Unpack it and check the contents. Do **not** trust the package list or the
build log — four separate mechanisms have "installed" a library that then did
not ship.

Two things to confirm:

- `recovery_dtbo size: 88722`. Builds with `size=0` do not boot.
  `BOARD_PREBUILT_DTBOIMAGE` alone does not embed it; `--recovery_dtbo` must be
  passed to `mkbootimg` (it is, in `BoardConfig.mk`).
- `system/lib64/libion.so` is present. It comes from AOSP, not from this tree;
  without it the vendor keymaster HAL cannot link and `/data` never decrypts.

## Flashing

Requires an unlocked bootloader and disabled AVB.

```bash
# from BOOTLOADER fastboot -- verify first
fastboot getvar is-userspace      # must print: no

fastboot flash recovery_a recovery.img
fastboot flash recovery_b recovery.img
```

Do not change the active slot. Then boot it:

```bash
adb reboot recovery
```

**Verify the flash actually took by booting it, not by the flash output.** TWRP
comes up **authorized** over adb; stock recovery comes up **`unauthorized`**.
That is the only reliable signal — a no-op flash from fastbootd reports success.

To leave, reboot from the TWRP UI or `adb reboot`. TWRP does not clear the BCB
on its own; this tree adds a hook that does, so a normal reboot returns to
Android instead of looping back into recovery.

## Backup and restore

**Read this section before relying on a backup.** Restore on this device is
narrower than TWRP's UI suggests.

### The supported procedure

**Back up `super` and `boot`. Restore `super` and `boot`. Then
`Wipe → Format Data`.**

That is the whole of it, and it always works.

### What this does and does not protect

This protects **the ROM**, not your data. `Format Data` erases `/data` —
accounts, apps, settings, internal storage. Copy anything you care about off
the phone first, over MTP or to the SD card.

**File-level `/data` backup and restore is not supported here.** Restoring a
stock Android 11 `/data` produces a device that will not boot, and the cause is
unexplained after ruling out slot flags, AVB, `boot`, Virtual A/B merge state,
`misc`, Magisk modules, and missing credential-encrypted data. Restoring a
LineageOS 21 `/data` happened to work, but one success is not a rule and this
tree does not offer it as one. `Format Data` is the only action that has
recovered every observed failure.

A related, *explained* case: restoring a system from one Android version onto
`/data` from another crashes `system_server` in a zygote restart loop, because
APEX data directories are labelled by the running platform's policy and the
labels disagree. TWRP's **Advanced → Fix Contexts does not repair this** — it
relabels from the recovery ramdisk's `file_contexts`, which carries no
APEX-specific rules.

### Why you do not need to handle `misc`

Restoring `super` without a matching `misc` leaves the device unbootable —
`misc` holds the Virtual A/B message at offset 32768 (magic `0x56740AB0`)
carrying snapshot and merge state, and if that disagrees with the LP metadata
in the restored `super`, boot fails and `/data` will not decrypt. `Format Data`
resolves it, which is the prescribed final step anyway. So back up `misc` if
you like — this tree offers it as of `9eb5fbf` — but the procedure above does
not depend on it.

If you do restore `misc`, note its first 2048 bytes are the BCB, rewritten on
every reboot-to-recovery. A backup may carry a stale `boot-recovery` and send
the device straight back into recovery. Fix by zeroing only those 2048 bytes.

### Diagnosing a failed boot

The only symptom is a frozen boot animation, and on this panel it is worse: the
display driver logs `CheckImageIsBlack: epd:: is black image, not display`, so
the boot animation never paints at all. The screen simply sits there. `logcat`
is the only way to see what happened:

```bash
adb logcat -d -b crash | grep -E "FATAL|Exit zygote"
```

## Known limitations

- **Do not unmount `/data` if you want decrypted access — reboot recovery
  instead.** fscrypt keys are held per-superblock and are installed only during
  startup decrypt, so unmounting evicts them and the remount silently returns
  **ciphertext**. A backup taken after an unmount contains encrypted junk and
  nothing warns you. This is pre-existing TWRP behaviour, not specific to this
  device.
- `/vendor`, `/system`, `/system_ext` and `/product` mount **read-only**
  (`fsflags=ro`) — ext4 `shared_blocks` cannot mount rw.
- MTP may report a stale 0-byte size for a file created behind its back while
  MTP is running. Affects files made from an adb shell, not normal use.
- **Tested on exactly one device.** Everything here is verified, but verified
  once, on one A9.
- `TARGET_RECOVERY_PIXEL_FORMAT` and `TARGET_SCREEN_DENSITY` in `BoardConfig.mk`
  are still the generator's guesses. They are not on the rendering path used by
  `graphics_hmct_epd`, so they have no observed effect — but they are unverified.

## Solved — root causes worth keeping

- **Keymaster never registered** because `libkeymasterdeviceutils.so` calls
  `WaitForPropertyCreation("vendor.sys.listeners.registered")` with no timeout,
  *before* `registerAsService()`. That property comes from
  `/vendor/bin/qseecomd`, which TWRP never started. Not SELinux, not HIDL
  versions, not a missing trustlet.
- **Hardware-wrapped keys were never the problem.** The FBE failure was a
  missing `fscrypt` session keyring — AOSP init creates it, TWRP's does not.
- **Sticky BCB, empty Startup Commands and an ignored `--fastboot` were one
  bug:** `libfs_mgr` cannot parse a TWRP-format `recovery.fstab`, so
  `ReadDefaultFstab()` failed and `get_args()` could neither read nor write the
  BCB. Anything reaching `ReadDefaultFstab()` fails silently until
  `/etc/recovery.fstab` is AOSP-format.
- **fastbootd fell back to bootloader** because `ro.boot.dynamic_partitions` is
  empty — the bootloader does not pass it on the recovery cmdline.
- **`slot-count 0`** because a lazy-started HAL always loses the race:
  fastbootd caches `IBootControl` in its constructor. Start such HALs at
  `on post-fs`.
- **"Stuck at splash" means startup stalled, not a rendering fault.** Check
  `ps -A | grep " recovery$"`: `futex_wait_queue_me` = blocked,
  `do_sys_poll` = healthy.
- **A build flag does nothing unless `vendor/twrp` exports it to Soong.** It is
  a silent no-op otherwise, so a build that "tested" a flag may never have
  contained it.

## Credits

Initial skeleton generated with
[twrpdtgen](https://github.com/twrpdtgen/twrpdtgen) by SebaUbuntu, then
corrected against the stock firmware and the device itself.

`prebuilt/libhmct_epd.so` is Hisense's code, extracted unmodified from the stock
recovery image. It is not covered by this tree's licence — see the display
section above.
