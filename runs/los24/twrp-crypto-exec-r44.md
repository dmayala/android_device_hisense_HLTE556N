# Byakuya R44 — packed crypto executable permissions

2026-11-02. **Offline PASS.** Worktree `/home/danny/A9-wt/twrp-self-crypto-r41`,
branch `twrp-self-crypto`, parent `266fb05`. Delivery is the commit containing
this report. No device access, pushes, merges, shared-checkout edits or product
builds. Coordinator owns push, CI and runtime testing; keystore2 stability and
decryption remain unproven. No independent review is claimed.

Moved the three unchanged stock executables to:

```
/system/bin/a9-crypto/qseecomd
/system/bin/a9-crypto/hw/android.hardware.keymaster@4.1-service-qti
/system/bin/a9-crypto/hw/android.hardware.gatekeeper@1.0-service-qti
```

Updated init service paths, blob inventory, and `dir.crypto` in **both** linker
configs. The specific crypto selector remains before the broader recovery
selector. Library search/permitted paths and all ELF bytes are unchanged;
libraries stay under `/system/a9-crypto/lib64`. The verifier now requires 0755
on these executables, prep script/interpreter and linker, checks every closure
ELF is readable, and checks the service paths and namespace selectors.

## Why this survives packing

The minimal manifest's
[twrp-12.1 overrides](https://github.com/minimal-manifest-twrp/platform_manifest_twrp_aosp/blob/twrp-12.1/twrp-default.xml)
select TeamWin `android-12.1` system/core and build/make. At pinned system/core
`ac4f36c7eb076ea2c582061a21dfc49eaa71e623`:

- [fs_config.cpp:215–229](https://github.com/TeamWin/android_system_core/blob/ac4f36c7eb076ea2c582061a21dfc49eaa71e623/libcutils/fs_config.cpp#L215)
  gives `system/bin/*` 0755 and unmatched files 0644.
- [fs_config_cmp:276–300](https://github.com/TeamWin/android_system_core/blob/ac4f36c7eb076ea2c582061a21dfc49eaa71e623/libcutils/fs_config.cpp#L276)
  uses wildcard matching across slashes, so the nested `a9-crypto/hw` files
  match. [fs_config:319–386](https://github.com/TeamWin/android_system_core/blob/ac4f36c7eb076ea2c582061a21dfc49eaa71e623/libcutils/fs_config.cpp#L319)
  replaces the input permission bits. Git/chmod alone cannot fix an unmatched path.
- [mkbootfs.c:60–108](https://github.com/TeamWin/android_system_core/blob/ac4f36c7eb076ea2c582061a21dfc49eaa71e623/mkbootfs/mkbootfs.c#L60)
  calls fs_config before emitting CPIO headers.
- The pinned [recovery Makefile:2258–2280](https://github.com/TeamWin/android_build/blob/1b692e2248609f50a27c48cce53b7445cecdcfc5/core/Makefile#L2258)
  copies device `recovery/root`, then packs with `mkbootfs -d TARGET_OUT`.

This uses an existing packing rule; no new config.fs mechanism is needed.

## Offline evidence and remaining mode differences

Evidence: `/home/danny/A9-build/twrp-crypto-exec-r44/` (~226 MiB).
Compiled the above **unmodified** mkbootfs.c and fs_config.cpp using GCC in
nix-shell. Narrow host header shims supply StartsWith/EndsWith, stderr logging,
and unistd; they change no fs_config rules, matching or archive logic.
`source/` retains inputs/shims/revisions. Used an empty product-output directory
with `-d`, with no fs_config override files, matching this device's default rules.

`python3 /home/danny/A9-build/twrp-crypto-exec-r44/pack-check.py` produced
before/after CPIOs and parsed their headers: all three old paths are **0644**,
all three new paths **0755**, and corresponding SHA-256 values are identical.
It also packed a fresh overlay of CI recovery **41344377139** plus this tree,
then unpacked it. The updated verifier passed **58 ELF nodes** on that unpacked
fixture (`closure-verified.json`). This is an offline fixture, not a new CI image.

All **140 tracked regular ramdisk files** were checked. These are the complete
remaining differences from git permissions (paths relative to ramdisk root):

| File | Git | Packed | Effect |
|---|---|---|---|
| `init.recovery.qcom.rc` | 0644 | 0750 | `init*` rule; init reads it |
| `init.recovery.usb.rc` | 0755 | 0750 | Same; init reads it |
| `system/a9-crypto/lib64/liba9_crypto_paths.so` | 0755 | 0644 | Preload only needs read permission |
| `system/lib64/liba9_recovery_crypto_wait.so` | 0755 | 0644 | Preload only needs read permission |

The one tracked symlink, `system/lib64/hw/android.hardware.gatekeeper@1.0-impl-qti.so`,
has git type 120000 (no permission bits stored). Its source lstat mode is 0777;
CPIO records 0644. Linux ignores symlink permission bits; the relative target
and readable 0644 DSO are intact. `pack-check.json` and `after-entries.json`
retain the complete audit, including directories and hashes.

R41's prep script is `/system/bin/a9-crypto-vintf.sh` (packed0755), invoked via
`/system/bin/sh` (0755). Recovery, keystore2, linker64 and existing helpers also
use `/system/bin`. All bundled DSOs are readable0644; neither preload needs an
execute bit. No other R41 executable uses an unmatched path.

Reused R41's Android/QEMU dlopen probe at the **new executable prefix**:
both linker configs load the bundled gatekeeper DSO and refuse an identical
fake slot-vendor DSO (four cases, `namespace-check.json`). The full config case
also proves the broader recovery selector did not win. Deliberately changing
the unpacked qseecomd to0644 makes the verifier fail with `not 0755`, then its
mode was restored (`verifier-negative.json`). `git diff --check` passes.
R41's report/closure remain historical records of its old paths.

After CI, run `python3 recovery/tools/verify-crypto.py --ramdisk /path/to/unpacked/rd`
on the actual artifact before coordinator runtime testing. This fix establishes
packed executable modes; it does not establish TEE/service/decryption success.

Checkpoint: `/home/danny/A9/local/agent-continuity/checkpoints/codex-b8c369dfa99b4edef30d119a.md`.

BYAKUYA R44 DONE
