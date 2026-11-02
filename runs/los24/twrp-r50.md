# Byakuya R50: configure recovery crypto from the booted ROM

2026-11-02. Offline worker under Yamamoto; no phone access or independent
review. Branch `twrp-self-crypto`, worktree
`/home/danny/A9-wt/twrp-self-crypto-r41`; parent
`d6fc30bd27c6189207b2a978fdfc8a6b7b137f62`. Checkpoint:
`/home/danny/A9/local/agent-continuity/checkpoints/codex-9156685b0c4cac85ece86eb0.md`.

**Candidate ready for coordinator testing.** R50 reads the booted slot's
system/vendor properties before releasing crypto services. Each service also
pins recovery's VINTF view in its own mount namespace before its native daemon
starts. Offline tests and ABL admission pass; kernel boot, first-start stability,
and stock/LOS23/LOS24 decryption still require hardware testing. Mainline vendor
without a patch property deliberately leaves data locked.

Image: **`/share/build/twrp-crypto-r50/recovery-r50.img`**, **100663296 bytes**,
SHA-256 **`9fae569466293df6d9bc583a687bfea520fa0127339e70b61deadb06b51b9102`**.
Base is the actual requested `/share/build/twrp-crypto-r49/recovery-r49.img`,
SHA-256 `d4e3cb55dc7f92c47c5665a30c98d7848a67d6a4d78e8c63a34ce8e4ee71441b`.

## Why R49 failed, and which component reads the versions

The brief supplies the coordinator's measured R49 result: `begin()` led to
an upgrade attempt, which failed with `INVALID_ARGUMENT` (-38), while recovery
advertised Android16.1.0 and a2099 patch. The blob came from Android17.
Keymaster's upgrade rule rejects a component that moves backward, even when
another component moves forward. A future patch cannot compensate for a lower
OS version. This matches the pinned
[Keymaster4 upgrade contract](https://android.googlesource.com/platform/hardware/interfaces/+/refs/heads/android11-release/keymaster/4.0/IKeymasterDevice.hal#803).
The private R49 capture and its key files were not opened or copied by this worker.

The shipped QTI library configures the TA **in its HAL constructor**, before
registering the service. This is not an OS-version argument supplied by recovery
vold or keystore2. Existing REA constructor evidence
`ev_224ccdf7f7c48240710379e4ea423670321cffdae3a0887d575f3e1b4123cb20`,
for `libqtikeymaster4.so` SHA
`beb923d3e09579bbf54360a55fa19af3b4a8ee5be9446d9798199a909d46b274`,
shows these inputs:

| Keymaster value | Shipped QTI source and conversion |
|---|---|
| OS_VERSION, tag0x300002c1 | `ro.build.version.release`; major×10000 + minor×100 + subminor |
| OS_PATCHLEVEL, tag0x300002c2 | `ro.build.version.security_patch`; YYYYMM |
| VENDOR_PATCHLEVEL, tag0x300002ce | `ro.vendor.build.security_patch`; YYYYMM or YYYYMMDD, depending on the TA's date-support response |
| BOOT_PATCHLEVEL | No property read or BOOT_PATCHLEVEL argument in this constructor's three-tag `KeymasterHalDevice::configure()` call. It is outside this userspace property configuration. |

Fresh static REA getter analyses confirm the first three conversions:
`get-os-version-final.rea.json` / `ev_eb3c6b53430715078fc053042420ca70f3b05b5a0df82b6f3f8d71571a276d41`,
`vendor-patchlevel.rea.json` / `ev_1f35862e7a40587739a3e3f264651a4c6e2c4c1f60d2343b3db2b48aa5f51ea3`,
and `os-patchlevel.rea.json` / `ev_cf153e5b33d385a71c6ec68d51e097db09dd16659e188e1d7bc73646ed113c68`.
They are decompiler observations, not recorded TA execution. They show that
the old HAL can parse release17; recovery's SDK32 is not that parser's input.

BOOT_PATCHLEVEL's exact secure-side source on this firmware was **not proved**
offline. The Android contract assigns boot version information to the boot
chain; Keymaster4 no longer uses the boot footer's OS version for OS_VERSION.
R50 neither fabricates a `ro.bootimage.*` property nor changes the recovery
header. That header still says16.1.0/2099-12; the three QTI configure values now
come from the ROM instead. No claim is made that the actual TA boot patch or
an already-old blob needs no upgrade. The RAM-only handling below is therefore
also relevant. General partition version binding is described by
[AOSP](https://source.android.com/docs/security/features/keystore/version-binding).

`TW_OVERRIDE_SYSTEM_PROPS` in the pinned `twrp.cpp:148–206` uses resetprop, but
runs in `process_recovery_mode()`. Initial fstab processing and metadata
decryption happen earlier. Setting that build flag alone would not reliably
precede the QTI constructor. R50 uses the already-shipped `resetprop -n` at
the earlier fstab/preparation boundary, with a service-level wait before exec.

## R50 behavior

`a9-crypto-rom-props.sh` runs at the beginning of existing crypto preparation,
after TWRP has mapped logical partitions and signalled `fstab.additional=1`.
It accepts only boot suffix `_a` or `_b`, then mounts that suffix's **system
and vendor** at private scratch paths under `/tmp/a9-crypto-rom/`. These are
ordinary temporary mount locations in the recovery namespace; no partition
content is copied. Mounts use ext4 `ro,noload`, with EROFS `ro` fallback.
It does not use the unsuffixed partition aliases, the other slot, ramdisk
build properties, or whichever vendor happens to be visible at `/vendor`.

System property locations supported: `system/build.prop`, `build.prop`, then
`system/etc/build.prop` within the selected system filesystem. Vendor locations:
`build.prop`, then `etc/build.prop`. Only the selected build.prop is parsed;
it is never sourced or evaluated. Required values are release, OS patch and
vendor patch. The QTI vendor spelling takes priority; AOSP's
`ro.vendor.build.version.security_patch` is accepted when it is the only
spelling. Duplicate requested properties, disagreeing vendor aliases,
malformed numeric releases/dates, missing files/mappings, mount/unmount errors
or resetprop/readback failure prevent readiness. There is no2099 fallback.

After unmounting both scratch mounts, the script sets and reads back:

* `ro.build.version.release` from system;
* `ro.build.version.security_patch` from system;
* `ro.vendor.build.security_patch` and its `version.security_patch` alias from vendor.

It uses `resetprop -n`, the same property override facility TWRP uses, without
property-service triggers or persistent-property operations. It leaves the
recovery SDK and runtime libraries alone. `twrp.a9.crypto_rom_props=ready` is
published only after success. Existing firmware/VINTF preparation must also
succeed before `twrp.a9.crypto_ready=1` starts the services.

The new8192-byte NDK `a9-crypto/launcher` waits for both readiness conditions
before exec of exactly keymaster, gatekeeper or keystore2. Even an early
`ctl.start` cannot enter a daemon's native constructor ahead of preparation.
Each of those services has init `namespace mnt`; the launcher makes it
recursively private, then binds `/system/etc/a9-recovery-vintf` onto
`/vendor/etc/vintf`. This fixes the first-start VINTF race even if TWRP changes
the global vendor mount later. The HALs, firmware, crypto paths and keystore2
database argument are unchanged. Launchers have a30s readiness bound in
their child processes; init's USB/reboot action queue remains independent.

R50 does not implement hot slot changes during a recovery session. Reboot
recovery after changing the boot slot or replacing its ROM before decrypting
again. A missing mainline vendor patch refuses preparation and leaves the
existing absent-service timeout to return to the UI. It does not guess an OS
version or start crypto against the2099 ramdisk defaults.

## Can recovery persist upgraded blobs?

The answer differs between normal Android vold and this recovery build:

1. **Normal Android can persist upgrades.** LOS24 vold's `KeyStorage.cpp`
   writes `keymaster_key_blob_upgraded`, renames it over the old blob and
   deletes the old Keymaster key, immediately or after checkpoint commit.
   Normal keystore2 also updates its persistent database for app-managed keys.
   Reporting an invented newer version on that path would be dangerous.
2. **This recovery's existing storage-key retrieval does not commit them.**
   Pinned TeamWin vold `a164ba05c5fef288059774a776b2e6e1119957cf`,
   `KeyStorage.cpp:339–393`, reads the original key, receives the optional
   upgraded blob from keystore2 and writes only
   `/tmp/keymaster_key_blob/keymaster_key_blob`. Persistent upgrade commit,
   rename and deletion of the old key are commented out. `Keymaster.cpp:163–188`
   also ignores any upgraded wrapped-storage blob returned by export. Metadata
   decrypt calls `fscrypt_mount_metadata_encrypted(..., false, false, ...)`;
   its `neverGen()` path fails rather than replacing a missing metadata key.
3. **Vold BLOB operations do not update keystore2's database.** In pinned
   TeamWin security `14737db1429b8eebc15568bc748b2cd79ccad5c2`,
   `security_level.rs:220–242`, Domain::BLOB uses no database key-ID guard.
   The upgrade path at824–889 stores to DB only with such a guard, otherwise
   returns the upgraded bytes to vold. It makes no old-key deletion call in
   that path. See the
   [pinned source](https://github.com/TeamWin/android_system_security/blob/14737db1429b8eebc15568bc748b2cd79ccad5c2/keystore2/src/security_level.rs#L824).
4. **Recovery app-key upgrades use a RAM database.** The service still passes
   `/tmp/misc/keystore`, which `keystore2_main.rs` selects as DB_PATH. Recovery
   `Decrypt.cpp:427–439` copies `/data/misc/keystore/persistent.sqlite` **into**
   `/tmp/misc/keystore/persistent.sqlite`; it does not copy it back. Thus a
   database upgrade during CE/PIN handling is not a write to Android's DB.

These facts cover host-side upgrade persistence in the inspected decrypt
paths, not every possible TWRP action or proprietary TA internal state.
R50 changes no key/blob interpretation or persistence code. Exact ROM values
remove the artificial OS/patch mismatch; old blobs may still legitimately
need an in-memory upgrade after an OS update. The secure TA's rollback state
was not inspected, and static source analysis is not a before/after disk audit.

The existing `Upgrading key:` log in recovery `KeyStorage.cpp` is unconditional
after successful begin. That text by itself does **not** prove a real upgrade
or a disk replacement. The source also lacks the normal optional-blob guard
there; no unrelated binary patch was added in R50.

**Why stock could decrypt with2099:** a stock11 blob can be upgraded in memory
to recovery's then-higher version/patch and used for that operation. Unlike
Android17→16.1, that direction is allowed by Keymaster. This recovery code
would retain the original disk blob and put an upgrade only in `/tmp`.
This explains the reported success without requiring a persistent2099 rewrite.
No historical before/after key-file evidence was supplied, so the precise old
boot and any secure-world side effects cannot be certified retroactively.

A successful recovery boot is not wholly read-only: existing fscrypt code
can update key-reference/policy files and perform normal filesystem writes.
The collection commands below are read-only. Do not treat a successful
decrypt as permission to copy a RAM upgrade back to `/metadata` or `/data`.

## Offline verification and packaging

Evidence/scratch: `/home/danny/A9-build/twrp-crypto-r50/` (about121MiB).
`source-evidence.json` pins the inspected source bytes. Static QTI constructor
evidence is in `qti-constructor-evidence.json`; new getter evidence is named
above. REA MCP tools were unavailable; the installed6.5.0 CLI and local Ghidra
were used. Initial CLI attempts reported Java unavailable; a minimal probe
identified sandbox `spawnSync` EPERM. Approved escalation resolved it without
changing REA/client configuration.

* `rom-props-smoke.json`, `check-rom-props.py`: actual packed Android mksh and
  awk, synthetic mount/property backends. Stock11/A, LOS23-16/B and LOS24-17/A
  select exact values; opposite-slot decoys remain untouched. Mainline missing
  vendor properties and invalid date refuse before any override. Input fixture
  hashes remain equal; scratch mounts release before publication. The initial
  test fixture's log-path substitution was corrected, then the cases reran.
* `launcher-smoke.json`, `check-launcher.py`: actual compiled ARM64 launcher
  under QEMU, with mount/property/time/exec mocks. An early start waits before
  private-namespace/bind/exec in all three roles. Failed properties, timeout,
  mount failure and wrong argv prevent exec. No daemon or TEE operation ran.
  This verifies syscall ordering, not actual init namespace propagation.
* `recovery/build-crypto-launcher.sh` builds with NDK27
  `aarch64-linux-android31-clang++`, `-Wall -Wextra -Werror`, no product build.
  The packed resetprop's own help confirms `-n` bypasses property_service.
* `repack-command.json`/`repack.log`: existing `scripts/twrp-repack.py`, actual
  R49 base, `--from d6fc30b --to 2984250 --allow-other`. Frozen runtime commit
  **`2984250e1abcfef12599ad5cefe46e01bbd912cc`**. Final delivery adds this report;
  its `recovery/root` bytes are identical to that frozen runtime commit.
* `actual-image-check.json`: exactly six changed ramdisk entries, all matching
  source, with old entry ownership/modes preserved: qcom init rc, ROM-property
  script, snapshot script, VINTF prep script, launcher, keystore2 rc. New script
  and launcher are0755. Kernel, DTB, recovery_dtbo, USB deadline script and USB
  init file are byte-identical to R49. R49 native diagnostics/wait libraries
  are also byte-identical; its snapshot retains every old field and adds
  ROM-preparation/vendor-alias/boot-patch properties.
* `closure-verified.json`: updated actual-ramdisk verifier passes **60 ELF
  closure nodes**, including launcher; existing blob hashes match. No native
  daemon, linker or crypto-library replacement.
* `abl.json`: **PASS header / recovery_dtbo / DT selection and overlay** for
  `/home/danny/A9/scripts/abl-check.sh /share/build/twrp-crypto-r50/recovery-r50.img recovery --json`.
  Initial sandbox invocation could not reach the Nix daemon; the approved
  escalation completed0. This proves image admission, not boot or decrypt.

Only the requested new `/share/build` build artifact was written outside the
worktree/scratch/required continuity files, with sandbox approval. No A9-data
write, main-checkout implementation edit, phone command, push, merge or
subagent. No active jobs/locks or phone attempt/cleanup obligation remains.

## Coordinator's next recovery boot: read-only collection

The coordinator owns installation and phone access. After installing through
the existing workflow, boot normal recovery once for the selected ROM. Leave
services running and wait60s after USB appears. Use the coordinator's pinned
connection and a private host capture directory (`umask077`):

```sh
adb shell getprop ro.twrp.a9.rom_props
adb shell getprop ro.twrp.a9.crypto_diagnostics
adb shell getprop ro.twrp.a9.usb_deadline
adb shell getprop twrp.a9.crypto_rom_props
adb shell getprop twrp.a9.crypto_ready
adb shell getprop twrp.a9.crypto_vintf
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.security_patch
adb shell getprop ro.vendor.build.security_patch
adb shell getprop ro.vendor.build.version.security_patch
adb shell getprop keystore.crash_count
adb shell twrp get tw_is_decrypted
adb shell twrp get tw_is_encrypted
adb shell getprop twrp.all.users.decrypted
adb shell df -h /data
# CAPTURE is a private host directory, not a phone path.
adb exec-out 'cd /tmp && tar -cf - a9-crypto-*.log a9-crypto-*.stdio logdw.txt recovery.log' > "$CAPTURE/crypto.tar"
adb exec-out dmesg > "$CAPTURE/dmesg.txt"
```

The tar intentionally matches **log/stdio files only**. Do not collect all
`/tmp`, all `a9-crypto-*` paths, key directories or databases. New
`a9-crypto-rom/` scratch mount locations could still cover a ROM on a failed
cleanup; they must not be recursively captured. Raw logs remain private.

Expected markers: `ro.twrp.a9.rom_props=r50`, diagnostics=`r49`, USB deadline=180,
ROM props=`ready`, crypto readiness=1, plus an `R50 slot=... release=...` record
with the selected ROM values. `a9-crypto-service.log` must show exec for the
three services; initial keystore startup should have no vendor-schema9.0
parse failure. Crash_count0 is expected for a first instance that stays alive;
later `running` alone does not establish first-start success. Diagnose the
first native error with R49 logs if decrypt still fails.

For missing properties, retain the refusal reason and locked-data result.
For a mainline vendor without a patch property, that is the expected result
today. For stock/LOS23/LOS24 success, record metadata mapping and decrypted
state; offline property tests are not those hardware passes. One recovery
cannot reverse a genuine Android downgrade of already-upgraded shared-data
keys simply by selecting the older ROM's properties.

Do not restart services, retry decrypt, change a PIN, format/wipe/fsck, copy
upgrades to disk, or unmount/remount `/data` for this collection. Keep a
successful mounted session intact.

BYAKUYA R50 DONE
