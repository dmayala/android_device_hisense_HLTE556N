# Byakuya R41 — vendor-independent TWRP crypto candidate

2026-11-02. **Implemented and validated offline. Decryption on the three phone
configurations is still unproven.** This is a device-tree candidate, not a
product image or a claim that all Android key formats are interchangeable.

Worktree `/home/danny/A9-wt/twrp-self-crypto-r41`; branch `twrp-self-crypto`;
base `twrp-los24-vendor` **0af2cfb**. The delivery commit is the commit containing
this report (`git rev-parse twrp-self-crypto`). Unsigned commit: no signing key is
configured in this repository; the brief permits unsigned in that case.
Coauthor: `GPT-6.1 Sol <noreply@openai.com>`.

Checkpoint:
`/home/danny/A9/local/agent-continuity/checkpoints/codex-2749f950b7555b46a364106e.md`.
Evidence/small probes:
`/home/danny/A9-build/twrp-self-crypto-r41/` (about 125 MiB, including the staged
unpacked ramdisk and downloaded source). No phone access, pushes, merges,
product builds, edits to shared checkouts, or NAS writes. No independent review
is claimed. The coordinator owns CI and all phone tests.

## Implementation

* `recovery/root/system/a9-crypto/` contains the three **unchanged stock**
  executables: qseecomd, keymaster 4.1, gatekeeper 1.0; plus **24 stock vendor
  DSOs**. They were extracted with read-only debugfs from
  `/home/danny/A9-build/stock-vendor-a/vendor_a.img`, SHA-256
  `2a7d5d8605181615d47ddc9ac992c4b06daec11eadb740d626a9fd0868678e2a`.
  `recovery/crypto-blobs.json` records every source/destination, size and hash.
  These files use the same proven ramdisk-file packaging route as libion and
  R40's repaired wait DSO; no unexported Soong module is relied on.

* `init.recovery.qcom.rc:59` points services at `/system/a9-crypto`, with
  `LD_LIBRARY_PATH=/system/a9-crypto/lib64:/system/lib64`. A dedicated isolated
  linker namespace permits only those ramdisk directories. It appears both in
  `system/etc/a9-crypto.ld.config.txt` (explicit per-service environment) and as
  a scoped stanza in `system/etc/ld.config.txt` (copied by recovery init to
  `/linkerconfig/ld.config.txt`). The existing recovery namespace is unchanged.
  This also rejects **absolute** slot-vendor passthrough dlopens; a library
  search path alone would not do that.

* Gatekeeper's stock service is a passthrough-service launcher. Its stock
  implementation is included under `a9-crypto/lib64/hw` and exposed through a
  relative symlink in ramdisk `/system/lib64/hw`, which recovery's HIDL loader
  scans. The vendor namespace refusal then allows the ramdisk implementation
  to be selected. Keymaster 4.1 supplies its inherited 4.0 interface; the
  separate 4.0 executable is no longer launched alongside it.

* qseecomd's listener **dlopen** modules are included, not merely DT_NEEDED.
  REA `start_listener` at ELF VA `0x206c` loads the ten-entry table at VA
  `0x5308`: RPMB, SSD, secure UI, time, two DRM/GP filesystem entries, QISL,
  SPL, GP request cancel and OPS. `libspl.so` is absent from the source stock
  image itself; its hierarchy-1 failure is nonfatal in the stock daemon.
  No fabricated SPL replacement is supplied.

* Stock KeymasterUtils waits for `vendor.sys.listeners.registered=true`, then
  calls `QSEECom_start_app` with `/vendor/firmware_mnt/image`, trying
  `keymaster64` then `keymaster`. **Mainline vendor has no firmware_mnt
  directory.** `crypto_paths.cpp` therefore redirects only that exact path to
  `/system/a9-crypto/firmware/image`; other arguments and paths pass through.
  Prep mounts **the selected slot's modem partition read-only** at the new
  ramdisk mount point. No TA, modem image, or boot-chain blob is copied or
  written. The 5,848-byte NDK-built preload is shipped as a ramdisk file;
  `recovery/build-crypto-paths.sh` reproduces it with an NDK Android31 C++
  compiler. SHA-256:
  `73db11d9da080b5f6fbc90cc1f72ebe88ffe0c73e4848994a885b445f1963441`.

* The normal `fstab.additional=1` event runs prep synchronously. Services are
  disabled until prep publishes `twrp.a9.crypto_ready=1`. Firmware or VINTF
  failure leaves them unstarted and does not assert successful decryption.
  `twrp.a9.crypto_firmware=ro` and `twrp.a9.crypto_vintf=recovery` report prep.

* `ro.twrp.a9.crypto=self` is the new capability marker. The existing
  `ro.twrp.a9.los24_vendor=1`, recovery/keystore2 preloads, keyring setup,
  device-node permissions, and timeout theme remain. The **unchanged** wait DSO
  is present, SHA-256
  `87d47fc92d378928362377df5d98c06fd2f6c7674b039a0358f906ebff93b1e1`.
  Its budget is still 30 seconds **per process for absent-service lookup**,
  shared across retries. It does not cancel an in-flight Binder/TEE call or
  establish a hard 30-second total startup bound.

## Fstab choice and vendor mount decision

Pinned TWRP source:
[dmayala/android_bootable_recovery 6ed6897769bdf3e92ce7a95c531e45fd037fe8ae](https://github.com/dmayala/android_bootable_recovery/tree/6ed6897769bdf3e92ce7a95c531e45fd037fe8ae),
retained at evidence `source/`.

`GetFstabPath()` in `twrp-functions.cpp:1574-1599` iterates boot fstab suffix,
hardware and hardware.platform; for each it searches ODM, vendor, then system
locations. `partitionmanager.cpp:420-427` copies the selected file to
`/etc/additional.fstab`, emits `fstab.additional=1`, and reparses **only Data and
metadata** (`:351-370`). The TWRP-format `/etc/twrp.fstab` supplies partition/UI
configuration; it is not the Android-format additional fstab.

The least invasive fallback is therefore **`/system/etc/fstab.default` and
`fstab.qcom`**, containing exactly the stock Android-format `/metadata` and
`/data` entries. Vendor fstabs retain their normal precedence. Both fallback
names cover this recovery's default suffix and qcom hardware; no property or
TWRP source override is required. `TW_SKIP_ADDITIONAL_FSTAB` stays off. The
entries retain `fileencryption=aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized+wrappedkey_v0`,
`metadata_encryption=aes-256-xts:wrappedkey_v0`, and
`keydirectory=/metadata/vold/metadata_encryption`. TWRP passes the selected file
to metadata decryption at `partitionmanager.cpp:599`.

**Retain TWRP's vendor mount in this candidate.** Crypto executables, DSOs,
gatekeeper implementation and the firmware mount no longer require it. TWRP
still mounts the selected vendor for fstab/properties, and libvintf still reads
its device view at `/vendor/etc/vintf`. Prep always bind-mounts the schema-1
ramdisk view there, including on stock/mainline. A ramdisk vendor manifest also
exists before any slot vendor is mounted. R40 already proved recovery's old
libvintf rejects LOS24 schema 9.0; this view declares keymaster 4.0/4.1,
gatekeeper 1.0 and boot 1.1.

The VINTF child mount itself can keep `/vendor` busy. **This patch does not
claim the installer's release_vendor/EBUSY problem is eliminated.** A later
coordinator-owned release must stop crypto services if appropriate, unmount
`/vendor/etc/vintf`, and then unmount `/vendor`; the firmware mount is outside
vendor. Do not lazy-unmount a live hierarchy. Fully avoiding the slot mount
would require changing TWRP's fstab/property/VINTF lifecycle. That is a separate
change, not necessary to deliver the offline self-crypto candidate.

## Closure and REA evidence

`runs/los24/twrp-self-crypto-r41-closure.json` records the **58 ELF nodes** found
with readelf in an overlay of the unpacked reference recovery (build
41344377139) and this device tree. This is a directory overlay, not a product
build. Every DT_NEEDED resolves under ramdisk `/system/a9-crypto/lib64` or
`/system/lib64`; none resolves into a slot vendor/ODM. Interpreter, listener
roots, passthrough implementation, both new/existing preload files, inventory
hashes and fallback files are checked by `recovery/tools/verify-crypto.py`.

Actual recovery-linker/QEMU results:

| Check | Evidence | Result / limit |
|---|---|---|
| Three stock executable dependency loads | `service-load-check.json`, `*.linker-list.log` | 0 for all `linker64 --list`; no HAL main run |
| Every added stock DSO | `load-all.log` | All 24 `dlopen(RTLD_NOW)` loads pass; no HIDL_FETCH/listener entrypoint run |
| Isolated namespace | `namespace-check.json` | Bundled gatekeeper loads; identical fake vendor copy is refused as inaccessible |
| Path preload | `path-check.log` | Exact firmware path redirected; unrelated and null paths forwarded; name/size/handle/return preserved |
| Prep script | `prep-check.json` | Slots A/B succeed; invalid slot, firmware-mount failure and VINTF-bind failure do not publish ready; mocked commands only |

Namespace probes translate absolute device paths to host fixture paths while
using the actual Android linker and libraries. They establish namespace
semantics, not phone service registration. `git diff --check` also passes.
No unchanged R40 timeout suite was repeated; source and DSO hashes are unchanged.

REA/Ghidra 12.1.4 retained evidence (provider image base `0x100000`, so subtract
that base for ELF VAs cited here):

* `qsee.rea.json`: `ev_188fecf93d4504831bf3cbcdf9f3edfb9dabab221e10d4c98dac471bbe16a7d5`
  (main thunk `0x3040` → `0x2334`),
  `ev_c1e3ebd60b14e283b7c611062516a803a76046a7aa70133e20da9decfa56b9e9`
  (listener dlopen), and
  `ev_126985ea381f278260284c2fd0e349a2820608022e2bb59d1cd64693e026e0e3`
  (relocated listener table). Main only treats the initial RPMB/SSD failures
  as fatal; hierarchy-1 listeners are attempted before publishing listeners.
* `gatekeeper-service.rea.json`:
  `ev_e0a33ca332cc749fe930f75d7f840e52ce28e1b2c43bca730b6ccadccfe32c8b`,
  ELF VA `0x1120`, calls `registerPassthroughServiceImplementation`.
* `gatekeeper-impl.rea.json`:
  `ev_70e851619f1c16db898f856ec7d54ec1a61161d19c4370ba8085c83bb7366b76`,
  `HIDL_FETCH_IGatekeeper`, creates KeymasterUtils at security level 1.
* `keymaster-utils.rea.json`:
  `ev_d8878899d88319aea3b3f9a1117b677c45b6b07cbddc6db48a0dd62577617af4`,
  ELF VA `0x22d8`, listener wait, trusted-app path/fallback, API version exchange
  and fatal QSEE errors. This is static evidence, not a TEE execution trace.

## Compatibility: what remains conditional

The source comparison uses TeamWin vold `android-12.1` commit
**a164ba05c5fef288059774a776b2e6e1119957cf** (downloaded into evidence `vold/`)
and the read-only local LOS24 vold at
`/share/build/los24/system/vold` **11d8982f824d52e8122c7aa732207ba66b8f23c8**.
The TeamWin sources can be inspected at
[that pinned revision](https://github.com/TeamWin/android_system_vold/tree/a164ba05c5fef288059774a776b2e6e1119957cf).

* **Directory and container format:** both `KeyStorage.cpp` implementations
  use format string `1`, `version`, `secdiscardable`, `keymaster_key_blob`, and
  `encrypted_key` (TeamWin `:64-73,:609-635`; LOS24 `:55-65,:574-605`). Both use
  a secdiscardable-derived application ID plus the authentication secret.
  Both `FsCrypt.cpp` files use `/data/misc/vold/user_keys/{de,ce}`
  (TeamWin `:87-92`; LOS24 `:86-91,:149-155`). These structural matches are
  encouraging; they do not verify the opaque keymaster blob's interpretation.

* **Metadata:** TeamWin reads `<keydirectory>/key` at
  `MetadataCrypt.cpp:105-127`, supports metadata option format 2 at `:272-275`
  and `aes-256-xts:wrappedkey_v0` at `:190-211`. LOS24 still supports that
  format, but can also use `<keydirectory>/default/key` plus per-device
  subdirectories when user devices are present (`MetadataCrypt.cpp:352-389`).
  TWRP12.1 does not implement that multi-device layout. An A9 using the
  existing single-device `/metadata/vold/metadata_encryption/key` layout
  avoids this mismatch; do not infer the actual layout from Android version.

* **fscrypt policy:** TWRP's vold `fscrypt_policy.cpp:139-195` and
  `Decrypt.cpp:146-148` support v1/v2 policies. The fallback explicitly chooses
  policy v2 and wrappedkey_v0. Newer LOS24 also accepts the newer `wrappedkey`
  spelling/type (`MetadataCrypt.cpp:243-247`); TeamWin's parser rejects that
  spelling. A newly chosen wrapped-key type or unsupported policy flag is a
  real boundary of this candidate, not fixed by shipping old HALs.

* **Opaque key blobs and upgrades:** both vold clients use Keystore2 BLOB
  descriptors in the vold namespace, with TEE security level and
  convertStorageKeyToEphemeral (TeamWin `Keymaster.cpp:106-174`; LOS24
  `Keystore.cpp:125-181`). The shared stock KeymasterUtils/TA ABI in REA shows
  why the same hardware can service them. It does **not** prove recovery's
  older keystore2 accepts every Android17-generated or upgraded blob.
  Current LOS24 keystore2 has explicit upgrade/legacy-blob handling
  (`system/security/keystore2/src/utils.rs:416-496`, security commit
  **123cc4af487922618cd99f28d05736e47eba7b00**). New OS/vendor patch-level
  binding, blob wrapping, storage-binding seed or TEE rollback state may
  still refuse a key. Do not strip headers, downgrade blobs or regenerate
  keys to make this test pass. Capture the exact error privately instead.

* **Credential-encrypted Data:** TeamWin handles synthetic-password blob
  versions 1/2/3 (`Decrypt.cpp:400-402,:454-468`) and the older `.pwd` scrypt
  fields (`:273-320`). LOS24 still declares those versions; its PasswordData
  adds trailing PIN length while preserving the earlier fields
  (`SyntheticPasswordManager.java:437-510`, frameworks commit
  **144f00521e8463bd0d8c28c07f51552f688d83bd**). This is evidence against a
  blanket claim that all Android17 password data is incompatible. Keystore
  alias/import behavior, actual protector state and secondary users still
  require a real test. A Data mount alone proves metadata/DE access, not CE
  access or all-user decryption.

The brief's measured stock-vendor decrypt pass is a baseline supplied by the
coordinator. This worker has not observed a decrypt with R41, LOS24-produced
Data, or mainline-owned Data. A fully successful universal-image claim waits
for the matrix below. No format or encryption migration is part of this work.

## Exact coordinator matrix and read-only acceptance checks

Build once from the delivery commit, then **unpack that CI recovery** and run:

```sh
python3 recovery/tools/verify-crypto.py --ramdisk /absolute/path/to/unpacked/rd
```

Do this against the CI artifact, not just the source tree: R40's missing-DSO
packaging failure must not recur. Confirm the two linker configs, executable
bits, gatekeeper symlink, fallback files, marker/preloads, and both new/old
DSOs are actually present. Apply the coordinator's normal offline ABL/image
size checks before its authorized recovery flash. No product build or flash
was performed by this worker.

Use **one identical recovery image** for every row. The coordinator must have
the correct existing Data/metadata belonging to the tested ROM already in
place; switching a vendor/slot does not itself manufacture that ROM's Data.
Do not format, initialize, restore another ROM's keys, or copy key directories
during these tests. Mainline B must be tested against **B's own Data**, using
the established coordinator ownership/restore procedure.

| ROM/vendor and existing Data owner | Recovery slot | Required result |
|---|---|---|
| Stock vendor_a, stock-owned Data | A | Startup + decrypted Data + all users |
| LOS23 GSI with stock vendor_a, LOS23-owned Data | A | Same (additional regression row for the user's all-ROM goal) |
| Persistent LOS24 vendor_a, LOS24-owned Data | A | Same; recovery VINTF view, no stock-vendor substitution |
| Mainline vendor_b specified in the brief, mainline B-owned Data | B | Same; `/system/etc/fstab.default` or `.qcom` selected, fallback copied |

After the coordinator boots each row, run only these observation commands on
its host (set `expected_slot=_a` or `_b` for that row):

```sh
expected_slot=_a
 timeout 45 adb wait-for-device
 test "$(timeout 10 adb shell getprop ro.boot.slot_suffix | tr -d '\r')" = "$expected_slot"
 test "$(timeout 10 adb shell getprop ro.twrp.a9.crypto | tr -d '\r')" = self
 timeout 120 adb shell 'until [ "$(getprop twrp.all.users.decrypted)" = true ]; do sleep 1; done'
 timeout 10 adb shell twrp get tw_is_decrypted
 timeout 10 adb shell twrp get tw_is_encrypted
 timeout 10 adb shell twrp get tw_all_users_decrypted
 timeout 10 adb shell 'getprop twrp.a9.crypto_ready; getprop twrp.a9.crypto_firmware; getprop twrp.a9.crypto_vintf; getprop twrp.a9.crypto_timeout; getprop vendor.sys.listeners.registered'
 timeout 10 adb shell 'getprop init.svc.recovery; getprop init.svc.vendor.qseecomd; getprop init.svc.vendor.keymaster-4-1; getprop init.svc.gatekeeper-1-0; getprop init.svc.keystore2'
 timeout 10 adb shell 'getprop twrp.all.users.decrypted; grep " /data " /proc/mounts; grep " /system/a9-crypto/firmware " /proc/mounts'
 timeout 10 adb shell 'grep -E "Fstab:|Reading /etc/additional.fstab|Successfully decrypted|All found users" /tmp/recovery.log'
```

Pass requires each queued `twrp get` to complete (startup), decrypted value 1,
all-user value 1/property true, a real decrypted Data mount, prep values
`1/ro/recovery`, listeners true, stable running services, and no timeout marker.
Observe the services again after 10 seconds to exclude a crash/restart loop.
Independently read/hash a known private **existing CE file** from that ROM's
reference, and compare privately with its expected hash; do not print private
paths/content. This is necessary in addition to the property and mount checks.
For mainline, confirm the recovery log selected the ramdisk fallback.

Also inspect each crypto service's `/proc/<pid>/maps` privately: every mapped
DSO must come from `/system/a9-crypto` or ramdisk `/system/lib64`, with no
`/vendor` or `/odm` DSO and no deleted vendor mapping. The boot HAL remains the
existing independent ramdisk boot HAL; its paths need not match crypto's.

If a row fails, leave its Data intact and capture `/tmp/recovery.log`,
`/tmp/logdw.txt`, `/tmp/a9-crypto-wait.log`, `/tmp/a9-crypto-vintf.log`, relevant
kernel assertions and service/mount states in that coordinator session.
The worker's namespace or mock passes do not substitute for this result.

## Added-blob licensing inventory

Every extracted vendor ELF is listed below, with exact hashes in
`recovery/crypto-blobs.json`. This is an intentionally inclusive inventory of
**all added vendor binaries**, including generated/open-source-derived ones;
it is not a claim that each has the same proprietary license. Extraction from
owned firmware does not establish permission to redistribute. Public-release
rights/source/notice obligations remain unverified. No redistribution license
for the Qualcomm/HMCT proprietary parts was supplied in this task.

All source paths below are under stock `/vendor/`; destinations are the same
relative paths under ramdisk `/system/a9-crypto/`:

```
bin/qseecomd
bin/hw/android.hardware.keymaster@4.1-service-qti
bin/hw/android.hardware.gatekeeper@1.0-service-qti
lib64/hw/android.hardware.gatekeeper@1.0-impl-qti.so
lib64/librpmb.so
lib64/libssd.so
lib64/libdrmfs.so
lib64/libdrmtime.so
lib64/libGPreqcancel.so
lib64/libqisl.so
lib64/libops.so
lib64/libsecureui.so
lib64/libQSEEComAPI.so
lib64/libqtikeymaster4.so
lib64/libdiag.so
lib64/libtime_genoff.so
lib64/libGPreqcancel_svc.so
lib64/libdrm.so
lib64/libdisplayconfig.qti.so
lib64/libStDrvInt.so
lib64/libsecureui_svcsock.so
lib64/vendor.display.config@1.0.so
lib64/libkeymasterdeviceutils.so
lib64/libqcbor.so
lib64/libkeymasterutils.so
lib64/vendor.display.config@2.0.so
lib64/vendor.qti.hardware.tui_comm@1.0.so
```

The gatekeeper symlink is a second directory entry for the same blob, not
another proprietary binary. `liba9_crypto_paths.so` is source-included
Apache-2.0 code. The existing R40 wait DSO and pre-existing libion/boot/display
blobs are unchanged and are not new proprietary additions in R41. No firmware
TA, key material, device identifier, or credential was added to git.

BYAKUYA R41 DONE
