# Byakuya R45 — gatekeeper forwarding and keystore2 VINTF crash

2026-11-02. **Both failures reproduced and fixed offline. Phone qualification remains pending.**
Worktree `/home/danny/A9-wt/twrp-self-crypto-r41`, branch `twrp-self-crypto`,
parent `b103c07492c9e0f6424ca1bd15f7b4f33eeb8484`. Delivery is the commit containing
this report. No phone access, pushes, merges, shared-checkout edits, NAS writes,
subagents, or product builds. No independent review claimed.
Canonical checkpoint, continued from R44:
`/home/danny/A9/local/agent-continuity/checkpoints/codex-b8c369dfa99b4edef30d119a.md`.
Current session pointer: `codex-27a64c744bb13a07f630af50.md` in the same directory.

## 1. Gatekeeper: the path matched; RTLD_NEXT could not find the backend

This stock implementation uses the **keymaster TA**, not a separate
`gatekeeper.*` image. Stock `android.hardware.gatekeeper@1.0-impl-qti.so`
SHA-256 `7cce2abe8ba7908d9ee66546885a5b4989cfb929b399bba0a7deb4565265f27c`:

* `HIDL_FETCH_IGatekeeper`, ELF VA `0x5e14` (REA `0x105e14`), constructs
  `KeymasterUtils(1)` at ELF VA `0x5e80`.
* In stock `libkeymasterdeviceutils.so` (not similarly named `libkeymasterutils.so`),
  SHA-256 `1231b993bde4c65982a7c8a22233e7063152596580e5b7d7f318917e8262fffd`,
  constructor ELF VA `0x22d8` calls `QSEECom_start_app` at `0x23d8` with
  `/vendor/firmware_mnt/image`, `keymaster64`, buffer size `0xa000`.
  Failure retries `keymaster` at `0x23f8`; failure of both asserts
  `QSEECom_start_app failed`. These are base directory/app-name arguments;
  R45 needs no new `gatekeeper` firmware and changes neither TA bytes nor name.

REA/Ghidra 12.1.4 evidence:
`ev_70e851619f1c16db898f856ec7d54ec1a61161d19c4370ba8085c83bb7366b76`
(reused R41 factory dossier) and
`ev_ee6ec9f2531ff26be70242bca0c2be45c7ff5d8cbf62b895f52d8316b94e6a10`
(R45 constructor dossier). REA addresses have a `0x100000` analysis base;
ELF VAs above do not include it.

R41's exact-string path redirect was correct. Its `dlsym(RTLD_NEXT, ...)`
backend lookup was wrong for the local group created by gatekeeper's passthrough
`dlopen`. HIDL loads these libraries with `RTLD_LAZY` without `RTLD_GLOBAL`
(also visible in local `system/libhidl/transport/ServiceManagement.cpp:506,538`).
QSEECom is a dependency of the dynamically loaded implementation, outside the
preload's RTLD_NEXT group. The wrapper returned `-1`/`ENOSYS` before invoking
QSEECom, so the stock constructor printed the generic assertion. The old R41
path probe linked its mock backend at process startup and missed this case.

**Fix:** `crypto_paths.cpp` opens `libQSEEComAPI.so` in its own linker namespace,
keeps that handle using libc's `pthread_once`, and resolves the function through
that handle. The existing isolated namespace still selects the bundled stock
API. Path rewriting remains exactly
`/vendor/firmware_mnt/image` → `/system/a9-crypto/firmware/image`.
The prep script already mounts the selected slot's `modem_a` or `modem_b`
read-only at `/system/a9-crypto/firmware`. No bind/path broadening, firmware copy,
TA substitution, or new proprietary blob is required.

The **actual stock HIDL_FETCH factory**, with actual recovery libraries and a
mock QSEE backend under the translated isolated crypto namespace, aborts with
the parent preload and succeeds with R45. Forcing `keymaster64` failure proves
that the unchanged `keymaster` fallback also forwards correctly. Unrelated and
null paths pass through unchanged. This observes constructor/linker behavior;
the mock does not establish TEE operation on the phone.

## 2. keystore2: invalid recovery manifest, followed by an unchecked null

The R40/R41 recovery manifest declared **both `<version>4.0</version>` and
`<version>4.1</version>` inside one Keymaster HAL**. The actual recovery
`libvintf.so` rejects it:

```
'android.hardware.keymaster' is not a valid Manifest HAL:
Duplicated major version: 4.1 vs. 4.0.
```

Actual `libkeystore2_vintf_cpp.so`, SHA-256
`43a3f48f03dafeaaf3b4fc9da4f32bca131ca34bc5aab203742495ba91adeecf`,
then dereferences the null device manifest. In `getHidlInstances` it calls
`GetDeviceHalManifest` at ELF VA `0x1810`, loads the result into x21 at `0x1814`,
and unconditionally executes `ldr x1, [x21]` at **`0x1824`**. REA canonical
export `0x1020d8` resolves the implementation; evidence
`ev_384d83a2929206b23526f7813dc9e9621131bc94bea8fe59788c402968b1ec74`.

This matches the upstream recovery source:
[TeamWin vintf.cpp:48–54](https://github.com/TeamWin/android_system_security/blob/14737db1429b8eebc15568bc748b2cd79ccad5c2/keystore2/src/vintf/vintf.cpp#L48)
uses `manifest->getHidlInstances` without a null check.
[shared_secret_negotiation.rs:111–124](https://github.com/TeamWin/android_system_security/blob/14737db1429b8eebc15568bc748b2cd79ccad5c2/keystore2/src/shared_secret_negotiation.rs#L111)
enumerates Keymaster 4.1/4.0 participants at startup, independently of gatekeeper.

A QEMU probe calling the **actual shipped keystore2 helper and libvintf** with
read-only path fixtures reproduces SIGSEGV for both the R44 recovery view
(duplicate major) and the initializer LOS 24 view (unsupported schema 9.0).
Replacing the recovery declaration with **4.1 only** returns `default`
successfully for **both 4.1 and inherited 4.0**. The stock-vendor manifest parses
without a crash and returns no 4.1 instance, as expected for its 4.0 declaration.
No Binder device, TEE, or gatekeeper is involved in this probe.

**R40 comparison:** its prep script applied the faulty overlay only to wrapped
LOS 24 vendors; stock retained its valid manifest. That explains the reported
stock-vendor success and LOS-vendor failure. R41 made the faulty overlay
unconditional. The supplied R40 LOS log already has repeated keystore2 SIGSEGVs;
the R44 log shows its first crash around 3.09 s, before gatekeeper's first abort
around 4.54 s. A live crash PC/tombstone was not supplied, so attribution of each
phone crash remains an inference; the exact manifest rejection and ensuing
helper SIGSEGV are reproduced offline.

**The ioctl is not BINDER_SET_CONTEXT_MGR_EXT.** `0x40046210` decodes as
`_IOW('b', 16, uint32_t)`, `BINDER_ENABLE_ONEWAY_SPAM_DETECTION`.
The current local bionic UAPI lists context-manager EXT as command 13;
`frameworks/native/libs/binder/ProcessState.cpp:596–604` treats spam-detection
failure as a log message and proceeds. The supplied R44 dmesg has this same
`-22` for servicemanager, hwservicemanager, qseecomd and the running keymaster.
No Binder ABI/kernel change is justified by this warning.

**Fixes in the tree:** remove 4.0 from both the ramdisk `/vendor/etc/vintf` copy
and the bind-view `/system/etc/a9-recovery-vintf` copy. Also remove keystore2's
`on late-init` start, mark it disabled, and start it on `twrp.a9.crypto_ready=1`.
This avoids its earlier race with mounted LOS vendor schema 9.0; preparation
sets ready only after firmware and the valid recovery VINTF view are installed.
The absent-service timeout shim, service credentials, temporary database,
crypto flags, keys and decryption behavior are unchanged.

## 3. Is gatekeeper needed for decryption?

Pinned TWRP 12.1 sources reused from R41:
[dmayala recovery 6ed6897](https://github.com/dmayala/android_bootable_recovery/tree/6ed6897769bdf3e92ce7a95c531e45fd037fe8ae)
and [TeamWin vold a164ba0](https://github.com/TeamWin/android_system_vold/tree/a164ba05c5fef288059774a776b2e6e1119957cf).

* **Fresh unencrypted Data:** no encrypted user-key unlock is required.
  A gatekeeper startup failure does not itself prove that Data is inaccessible.
* **FBE without a PIN:** gatekeeper verification is bypassed. Recovery
  `partitionmanager.cpp:623–625` sends `"!"` for password type zero. Vold
  `Decrypt.cpp:896–906` first tries `Decrypt_CE_storage(user, 0, "!")` and falls
  back to synthetic-password handling. That fallback's secdiscardable branch
  only obtains/verifies gatekeeper when `Password != "!"`
  (`Decrypt.cpp:751–779`). DE initialization itself calls systemwide-key/user0
  initialization, without a gatekeeper verification (`Decrypt.cpp:185–196`).
  Keymaster and, for synthetic-password unwrap, keystore2 can still be needed;
  "no PIN" does not mean "unencrypted".
* **PIN/password on this A9's non-Weaver path:** gatekeeper is required.
  Synthetic-password handling calls `IGatekeeper::getService` and `verify`
  (`Decrypt.cpp:751–779`), then passes the authentication token to keystore2
  (`:784–800`). Legacy non-synthetic handling also requires gatekeeper
  (`:924–952`). The source has an alternative Weaver branch (`:684–737`);
  it is not evidence that this A9 has a functioning Weaver HAL, and this
  recovery does not declare one. These observations do not prove compatibility
  with every newer Android synthetic-password format or successful PIN decrypt.

## Packaging, checks, and coordinator handoff

**All runtime changes are ramdisk-only and repackable with
`scripts/twrp-repack.py`; no full TWRP/product compile is required.** The one
native change needed a standalone NDK compile, already done with
`recovery/build-crypto-paths.sh` and the existing NDK's
`aarch64-linux-android31-clang++`. Its rebuilt prebuilt DSO is committed:
6536 bytes, SHA-256
`221b7678a2c77baa3faa38cded75d4dd4f28e00f2a92ff7c04ef0dfafeebb343`.
The inventory hash/size is updated. It adds no C++ runtime dependency.
The two manifests and two init files are plain ramdisk content.
`crypto_paths.cpp`, the build script, inventory, verifier and this report are
source/host artifacts; their runtime output is the committed prebuilt DSO.
The new verifier checks the measured duplicate-major defect and service ordering.

For the **existing R44 repack** use `--from b103c07 --to <R45 commit>`.
For **original CI 41379390386**, whose source was `266fb05`, use
`--from 266fb05 --to <R45 commit>` so R44's executable relocations are included.
Use `--allow-other` for the source/inventory/verifier/report files above; their
runtime counterpart is already present under `recovery/root`. Repacking is not
an automatic source compilation. Preserve the normal coordinator-owned image
validation/readback workflow. This worker has not produced or flashed a boot image.

Evidence directory `/home/danny/A9-build/twrp-gatekeeper-r45/` (~217 MiB):

1. `check-gatekeeper.py`, `gatekeeper-check.json`, `old-local.log`,
   `fixed-local.log`, `fixed-fallback.log`, `paths.log`: actual stock factory,
   isolated namespace, old/fixed preload, fallback and argument passthrough PASS.
2. `check-vintf.py`, `vintf-final.json`, `vintf-*-final.log`,
   `vintf-inheritance.log`: actual shipped parser/helper, old/LOS/fixed/stock
   results above. Invalid inputs intentionally reproduce signals, not passes.
3. `check-packed.py`, `full.cpio`, `packed-entries.json`, `packed/`,
   `closure-verified.json`: unmodified TWRP 12.1 mkbootfs from R44, full fixture
   packed/unpacked, verifier **PASS, 58 ELF nodes**, services0755/preload0644.
   The fixture overlays the supplied unpacked CI baseline; it is not a new CI build.
   `verifier-reject-r44.json` confirms the new verifier refuses the old duplicate declaration.
4. `vintf.cpp`, `shared_secret_negotiation.rs`, `security-ref.json` retain the
   upstream source. REA bundles are the sibling files
   `/home/danny/A9-build/twrp-gatekeeper-r45-{keymasterutils,hidl,keystore-vintf}.rea.json`;
   factory evidence is the preserved R41 `gatekeeper-impl.rea.json`.

`git diff --check` passes. Remaining coordinator test: repack this commit and
verify stable gatekeeper/keymaster/keystore2 plus successful Data unlock on the
intended encrypted installation, including a real PIN test if desired. Current
unencrypted Data can establish service startup, not FBE/PIN decryption. No
format, key copying, partition write, or device action is part of this delivery.

BYAKUYA R45 DONE
