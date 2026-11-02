# Byakuya R49: metadata decrypt diagnostics for LOS 24

2026-11-02. Offline worker under Yamamoto. Branch `twrp-self-crypto`, worktree
`/home/danny/A9-wt/twrp-self-crypto-r41`, parent `980433ccdc3220c26aea1f6317681dd11e2206ff`.
Checkpoint: `/home/danny/A9/local/agent-continuity/checkpoints/codex-9156685b0c4cac85ece86eb0.md`;
prior R41–R48 history is linked there. No independent review or hardware decrypt
pass is claimed. This is an instrumented candidate; the exact R48 failure
cannot be established from the supplied capture because its Android error
channel was not collected.

## What the supplied boot establishes

Evidence: `/home/danny/A9/runs/los24/twrp-r48-live-20261102/`.
Recovery selects keymaster4.1 and the additional fstab, then returns false from
`fscrypt_mount_metadata_encrypted()`. The subsequent FDE fallback is a
consequence of that failure, not evidence that LOS24 uses FDE. `/data` remains
locked; a running service at115s does not prove it served the original request.

The first keystore2 process has binder activity at3.513s and SIGCHLD-related
messages at3.525s; init starts a new process at8.444s, with its binder activity
at8.508s. The exact first exit time/reason is not recorded. Recovery's
first recorded binder initialization is4.678s, between those processes.
`keystore.crash_count=1` confirms a second start: the pinned
[metrics code](https://github.com/TeamWin/android_system_security/blob/14737db1429b8eebc15568bc748b2cd79ccad5c2/keystore2/src/metrics_store.rs#L609)
sets0 on the first start and increments on subsequent starts. This identifies
a startup instability to investigate, but neither the first exit reason nor
the failing decrypt operation is present. It does not establish that the
restart caused the decrypt failure.

`logcat.txt` is not the error channel here: init runs `logdstub`, which writes
Android log records to **`/tmp/logdw.txt`**. That file is absent from the supplied
capture. Most vold and keystore2 errors use Android logging, while the visible
"Using additional fstab" and final failure use stdout. The resulting gap hides
file-read errors, keystore2 exceptions, wrapped-key export failures and
dm-default-key errors. Empty `twrp.a9.crypto_timeout` only excludes the shim's
absent-service timeout; it does not exclude a registered service returning an
error, dying during a transaction, or failing a key operation.

## Source comparison and limits

Pinned recovery sources: `/home/danny/A9-build/twrp-self-crypto-r41/source`
(`partitionmanager.cpp:586–620`) and sibling `vold/`, TeamWin vold
`a164ba05c5fef288059774a776b2e6e1119957cf`. LOS24 sources:
`/share/build/los24/system/vold`, revision
`11d8982f824d52e8122c7aa732207ba66b8f23c8`; file hashes are recorded in
`/home/danny/A9-build/twrp-crypto-r49/source-evidence.json`.

Both `MetadataCrypt.cpp` implementations use
`/metadata/vold/metadata_encryption/key`. Both `KeyStorage.cpp` implementations
use storage version **the single ASCII byte1**, the same secdiscardable SHA512
prefix, `secdiscardable`, `encrypted_key`, and `keymaster_key_blob`, with the
same AES-GCM nonce/MAC layout. Both mix an optional storage-binding seed into
the application ID when configured. The filename/version format alone does
not explain a new Android17 incompatibility. This comparison does **not** prove
that the current on-device directory is complete, a seed was unused, or a
newer opaque KeyMint/Keymaster blob is accepted by recovery's older keystore2.

Recovery `MetadataCrypt.cpp:246–285` supports FBEv2,
`aes-256-xts:wrappedkey_v0`, retrieval of the stored key and ephemeral wrapped-key
export. It does not lack wrapped-key support categorically. Recovery
`Keymaster.cpp:106–128` first obtains **keystore2**, then its TEE security level;
the HAL process merely being `running` is insufficient. Metadata uses empty
authentication, before CE/PIN/gatekeeper verification. Do not attribute this
failure to the user's PIN or change/clear it.

R49 preserves the startup order and crypto/key interpretation to capture the
original failure. It adds no sleeps to decryption, service restart, decrypt
retry, key upgrade policy, format operation or new partition access.

## R49 instrumentation

* A standalone NDK-built `liba9_crypto_diagnostics.so` is preloaded into recovery,
  keystore2 and the three existing crypto daemons. Its liblog copy records
  monotonic time, PID, TID, priority and the original message in private0600
  files. It preserves later `__android_log_set_logger` destinations, including
  libbase's custom logger, and retains the original logdstub destination.
  Native log copies stop appending after approximately2MiB per process role
  (one final record can cross that limit).
* Files: `/tmp/a9-crypto-{recovery,keystore2,keymaster,gatekeeper,qseecomd}.log`.
  The four daemons additionally send stdout/stderr to matching **`.stdio`**
  files with timestamped process-start separators. Stdio is append-only and
  is not size-capped. Recovery's existing stdout/stderr destination is retained.
  These are private raw diagnostic logs; do not paste them to public reports.
* The existing wait preload additionally records lookup entry, acquisition and
  timeout with monotonic time/PID in `/tmp/a9-crypto-wait.log`. Its shared30s
  absent-service budget and passthrough behavior are unchanged. The new trace
  does not poll or log individual lookup iterations.
* A separate oneshot `a9-crypto-snapshot` service starts alongside crypto prep
  at `fstab.additional=1`, without blocking init. At approximately0/2/5/10/20/40s
  it records selected properties, mount flags, actual service names
  **`vendor.qseecomd` / `vendor.keymaster-4-1` / `gatekeeper-1-0`**, crash count,
  selected build/crypto properties, the `/data` fstab flags, and known key-file
  presence, sizes and permissions. Only `version` is read and classified;
  key bytes and key hashes are never emitted by this inventory. No `/data`
  contents, process argv, kernel cmdline or broad property dump is collected.
* Marker: **`ro.twrp.a9.crypto_diagnostics=r49`**. R48's
  **`ro.twrp.a9.usb_deadline=180`**, deadline script and USB setup are retained.

The logging source/build script, wait source and both native prebuilt outputs
are in this commit. No product build is needed. The native source changes are
represented by those committed libraries in `recovery/root`; `--allow-other`
on the ramdisk repacker is therefore intentional.

## Validation and image

Scratch/evidence: `/home/danny/A9-build/twrp-crypto-r49/`.

* `native-smoke.json`, `check-native.py`: actual Android binaries under QEMU,
  using both the actual R48 recovery liblog and bundled stock liblog in an
  isolated namespace. Debug/error logging, timestamp/PID/TID fields,0600 modes,
  stdout/stderr capture, recovery stdout preservation, later logger replacement
  and forwarding, and the2MiB native limit pass. Only a synthetic executable
  with a daemon's basename runs; no stock daemon main or TEE access occurs.
* `wait-smoke.json`, `wait-trace.log`: real rebuilt wait preload against the
  existing R40 fake backend. Acquired-keystore lookup and noncrypto passthrough
  pass with expected trace records. The original timeout budget is unchanged;
  R40's timeout evidence is retained rather than rerunning an unchanged30s wait.
* `snapshot-smoke.json`, `snapshot-*.log`, `check-snapshot.py`: actual packed
  Android mksh and its awk/stat/cat under QEMU. Absent key directory, valid
  version1 and mismatched version cases pass; six snapshots complete, fixtures
  remain unchanged, and synthetic key content is absent from output. A first
  test fixture incorrectly invoked Toybox awk; the corrected fixture uses the
  packed standalone awk. No production change was needed for that fixture.
* `wait-{compile,link}-command.json` and logs record the standalone wait build.
  The diagnostic library builds with `recovery/build-crypto-diagnostics.sh`
  using NDK27 `aarch64-linux-android31-clang++`.

Image: **`/share/build/twrp-crypto-r49/recovery-r49.img`**, **100663296 bytes**,
SHA-256 **`d4e3cb55dc7f92c47c5665a30c98d7848a67d6a4d78e8c63a34ce8e4ee71441b`**. Based on
`~/A9-data/recovery/twrp-HLTE556N-41387194927-r48repack.img` (read-only), SHA-256
`e8b70ee622e8352ebddc4390caa4cc9aa58196c880e7ffb773d11ddff4144f99`.

The existing `/home/danny/A9/scripts/twrp-repack.py` produced it from frozen
runtime commit `a33909ac62c3a1ee63d342487b12155e219d06a8`, using
`--from 980433ccdc3220c26aea1f6317681dd11e2206ff --to a33909a --allow-other`.
The final commit is a report-only amendment of that runtime commit;
`recovery/root` bytes remain identical. `repack-command.json` and `repack.log`
retain the exact invocation. The supplied `/share/build` destination required
the approved sandbox escalation; no A9-data/NAS reference file was written.

`actual-image-check.json` verifies the actual packed image has exactly these
five changed entries, all source-identical, with prior entries retaining their
ownership/mode/metadata: `init.recovery.qcom.rc`,
`system/bin/a9-crypto-snapshot.sh`, `system/etc/init/keystore2.rc`,
`system/lib64/liba9_crypto_diagnostics.so`,
`system/lib64/liba9_recovery_crypto_wait.so`. The new script is0755 and the
new library0644. Kernel, DTB and recovery_dtbo match the actual R48 image
byte-for-byte; the USB deadline script and USB init file are unchanged.
`actual-r49-rd/` is the unpacked output. The updated crypto verifier passes
**59 ELF closure nodes** on that actual image (`closure-verified.json`), using
the explicit NDK llvm-readelf path. An earlier setup invocation lacked
`readelf` on PATH; it did not test the candidate.

**Offline ABL PASS:**
`/home/danny/A9/scripts/abl-check.sh /share/build/twrp-crypto-r49/recovery-r49.img recovery --json`.
The header, recovery_dtbo and DT selection/overlay stages pass; full result
is `abl.json`. Its Nix dependency required the approved sandbox escalation.
This verifies bootloader image admission, not kernel boot, USB or decryption.

## Coordinator's next boot: read-only collection, no format

The coordinator owns image installation and the phone. Once R49 is installed
through the existing recovery workflow, boot normal recovery **once** and leave
its original services running. Wait60s after adb appears, then collect with the
coordinator's pinned adb connection into a private host directory:

```sh
adb shell getprop ro.twrp.a9.crypto_diagnostics
adb shell getprop ro.twrp.a9.usb_deadline
adb shell getprop twrp.a9.usb_deadline
adb shell twrp get tw_is_decrypted
adb shell twrp get tw_is_encrypted
adb shell df -h /data
# CAPTURE is an existing private host directory (umask077).
# Pull only these log files; do not pull all /tmp (it contains keystore data).
adb exec-out 'cd /tmp && tar -cf - a9-crypto-* logdw.txt recovery.log' > "$CAPTURE/crypto.tar"
adb exec-out dmesg > "$CAPTURE/dmesg.txt"
```

The tar command should exit0. Missing files or a missing `R49 diagnostic logger
installed` marker indicate an instrumentation/startup problem; retain that
result instead of treating the boot as a successful crypto diagnosis. The
snapshot should end with `R49 snapshot complete`. The inventory and native
logs cover the original auto-decrypt attempt, including a first keystore2
crash and its later restart. Stdio has process-start times; native liblog and
lookup records have per-record monotonic timestamps.

Interpret the **first** error in `a9-crypto-recovery.log` with the corresponding
keystore2/keymaster/qseecomd logs, not only final `running` properties:

| First failing stage | Evidence and next conclusion |
|---|---|
| Fstab/options | Parser error before key retrieval; snapshot shows selected flags |
| Key directory/file read | Path/errno plus known-file inventory; distinguish absence, permissions and version mismatch |
| Service lookup | Enter/acquired/timeout sequence and actual service/listener state |
| keystore2/TEE request | First panic/native fatal or getSecurityLevel/createOperation/finish error, with restart PID/timing; a later stable service does not erase that failure |
| Blob/auth/upgrade | Exact KeyMint error and compat/QTI diagnostic; investigate version/application-ID/seed compatibility without overwriting stored blobs |
| Wrapped key export | convertStorageKeyToEphemeral/exportKey result; separate stored-key decryption from hardware wrapping |
| dm-default-key or filesystem mount | Mapper/kernel error after successful retrieval/export; retain dmesg, never dump a dm table containing keys |

Do not format, wipe, run fsck, alter a PIN, delete/upgrade key files manually,
restart services, retry decryption or unmount/remount `/data` for this capture.
`df` failure while locked is expected. If decryption unexpectedly succeeds,
record that result and preserve the successful mounted session; the added
diagnostics themselves can affect timing, so success alone is not proof of a
specific ordering fix.

No phone access, adb/fastboot/edl execution, A9-data reference write, push, merge,
shared-checkout implementation edit, subagent or independent review performed.

BYAKUYA R49 DONE
