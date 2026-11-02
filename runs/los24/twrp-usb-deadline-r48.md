# Byakuya R48: recovery USB startup and 180-second fallback

Branch `twrp-self-crypto`, parent `b37182b0d8a3036baea152a02d3b7d5f7f94a333`,
worktree `/home/danny/A9-wt/twrp-self-crypto-r41`. Offline worker under Yamamoto.
Canonical checkpoint (same as R45):
`/home/danny/A9/local/agent-continuity/checkpoints/codex-b8c369dfa99b4edef30d119a.md`.

The strongest explanation is an advertised but unstartable health HAL, exposed
by R45's valid VINTF manifest. Install the existing recovery VINTF view before
hwservicemanager starts, fix a separate USB teardown race, and add an independent
180-second deadline to bootloader. All runtime changes are plain ramdisk files;
no native or product compile is needed.

## Why fastbootd can reach its page without exposing USB

I unpacked the **actual supplied R45 image**, read-only from the NAS:
`twrp-HLTE556N-41387194927-r45repack.img`, SHA-256
`af585d8e52b781c4062f675512744fad6107fa444e176070fe20dfe50a18e5ba`.
Its generated `/vendor/etc/vintf/manifest/android.hardware.health@2.1.xml`
declares `@2.1::IHealth/default` over hwbinder. Both
`/system/etc/init/android.hardware.health@2.{0,1}-service.rc` services are
**disabled**, with **no interface declaration for lazy start**. Neither is
explicitly started by this recovery's rc files. This is distinct from the
source-controlled top-level manifest, which does not list health.

R45's manifest diff removes only duplicate keymaster major 4 (`4.0` alongside
`4.1`); it **retains BootControl 1.1**. R44's duplicate made the entire device
manifest invalid. Fixing that defect exposes the generated health fragment in
direct-fastboot mode:

| Actual shipped parser/helper, separate QEMU processes | Boot 1.1 / inherited 1.0 | Health 2.0 default | Fastboot 1.1 |
|---|---|---|---|
| R45 direct-fastboot ramdisk view, fragments visible | 1 / 1 | **1** (inherited from 2.1) | 0 |
| R48 early recovery view, fragments hidden | 1 / 1 | **0** | 0 |

This uses the packed recovery's real `libkeystore2_vintf_cpp.so` and `libvintf`,
querying `getHidlInstances`; it is not merely an XML string check.

Fastbootd constructs its BootControl, health and optional fastboot HALs **before**
constructing `ClientUsbTransport`: [fastboot_device.cpp:66–74](https://github.com/TeamWin/android_system_core/blob/ac4f36c7eb076ea2c582061a21dfc49eaa71e623/fastboot/device/fastboot_device.cpp#L66).
`get_health_service()` calls `IHealth::getService("default")` before trying
`backup`: [HealthHalUtils.cpp:27–37](https://github.com/LineageOS/android_hardware_interfaces/blob/ae469cee0dce6d71489588126a15da8e67a50102/health/2.0/utils/libhealthhalutils/HealthHalUtils.cpp#L27).
The hwbinder retry path in [ServiceManagement.cpp:782–815](https://github.com/LineageOS/android_system_libhidl/blob/lineage-19.1/transport/ServiceManagement.cpp#L782) waits for a declared
service; absent undeclared services return null. Fastbootd tolerates null health.
The packed `libhidlbase.so` also contains the non-recovery-path diagnostic
`getService: defaultServiceManager() is null` from that lookup implementation;
this is not an assumption that the library forces every lookup to passthrough.

The previous VINTF bind runs only after `fstab.additional=1`
(`init.recovery.qcom.rc` parent lines92–94). TWRP's
`twrp.cpp:396` passes `!startup.Get_Fastboot_Mode()` to `Process_Fstab`;
`partitionmanager.cpp:413–426` publishes that property only in recovery mode.
Thus direct fastboot never hides the ramdisk fragments. The independent TWRP
GUI entering the Fastboot page does not show that fastbootd reached USB setup.
Source snapshot: `/home/danny/A9-build/twrp-self-crypto-r41/source/`, recovery
revision `6ed6897769bdf3e92ce7a95c531e45fd037fe8ae`.

**Evidence limit:** the supplied failed boot has no adb/log channel or fastbootd
stack. The manifest contents, missing service admission and lookup-before-USB
chain are demonstrated offline; the physical process's exact blocked PC is
not measured. This is the strongest source-supported cause, not a claimed live
reproduction. It specifically explains fastbootd; a general R45 adb regression
has not been demonstrated.

## Changes

* `recovery/root/init.recovery.qcom.rc:113–121` bind-mounts the existing
  `/system/etc/a9-recovery-vintf` over `/vendor/etc/vintf` during **early-init**,
  before `hwservicemanager` starts on **init**. It preserves BootControl 1.1,
  keymaster and gatekeeper while hiding generated fragments that recovery does
  not serve. No health/charging service is enabled. Normal recovery retains the
  later bind after mounting slot vendor, which can cover this initial RAM view.
* The crypto preparation service uses `start`, replacing `exec_start`, at
  `init.recovery.qcom.rc:93–96`. HALs and keystore2 still start only on
  `twrp.a9.crypto_ready=1`. A stalled firmware mount no longer freezes init's
  ordinary action queue. This replaces the synchronous wait with the existing
  readiness signal; no extra readiness gate is added.
* `system/etc/init/hw/init.rc:186–206` tears down configfs on `config=none`
  regardless of the transient configfs selector, and explicitly clears UDC,
  adb/MTP links and the shared ready bit before starting fastbootd. TWRP
  `startupArgs.cpp:45–51` sets `config=none`, immediately `configfs=0`, sleeps,
  then restores configfs=1 and requests fastboot. The old configfs=1 teardown
  can be missed in that ordering, leaving stale links. This is a separate
  source-proven race; it is not claimed as the measured R45 blocked stage.
* The early disabled/oneshot `a9-usb-deadline` service runs
  `/system/bin/a9-usb-deadline.sh` independently of recovery/fstab/crypto/default
  class startup. The marker is **`ro.twrp.a9.usb_deadline=180`**.

## Deadline behavior

The script records `/proc/uptime` at start and polls at one-second intervals
until start+180 seconds. Successful USB admission requires a nonempty bound
configfs UDC, the kernel UDC state **configured**, and matching USB state plus
adbd/fastbootd running and FunctionFS ready (or MTP ready for MTP-only).
A stale ready property or a running daemon cannot disarm it. Kernel configured
also proves host enumeration rather than merely a bound gadget without a host.

Once successful it sets `twrp.a9.usb_deadline=satisfied` and exits permanently.
Normal USB use and later cable removal therefore do not trigger reboots. With
no successful configuration it sets `expired`, logs one fixed kmsg line, and
runs `/system/bin/reboot bootloader`. It never requests recovery, restarts
itself or retries a recovery boot, so an absent host does not create a recovery
loop. Uptime seconds are truncated: polling is approximately 179–180 seconds
plus command/scheduling overhead; this is a userspace deadline, not a hardware
watchdog against a frozen kernel or init.

The standard reboot path uses init's normal bootloader/BCB handling. There are
no direct partition, data, key, NV or boot-chain writes in the new script.
`sys.powerctl` bypasses the ordinary action/exec queue in pinned
[init.cpp:330–340](https://github.com/TeamWin/android_system_core/blob/ac4f36c7eb076ea2c582061a21dfc49eaa71e623/init/init.cpp#L330).

## Validation and handoff

Evidence: `/home/danny/A9-build/twrp-usb-deadline-r48/`.

* `actual-r45-evidence.json`: actual image hash, health declarations/service rc,
  hwservicemanager ordering and source manifest/rc content.
* `hal-instances.json`, `r45-direct-fastboot.log`,
  `r48-early-ramdisk-view.log`, `hal-instances.c`: actual parser/helper results
  above. The QEMU path map models the early directory bind; it does not execute
  a privileged Android init mount on hardware.
* `usb-smoke.log`: five focused groups in the actual packed Android mksh under
  QEMU: attached adb/MTP/fastboot/sideload; stale ready/state with empty UDC;
  absent host with bound UDC; enumeration at179s; rc ordering/early view and
  async crypto. Reboot, sysfs and time are replaced only in the test copy.
  The same groups also pass with host sh. An initial test-only printf assumption
  was corrected to echo (mksh's printf is external); production was unaffected.
* `check-packed.py`, `full.cpio`, `packed-entries.json`, `packed/`,
  `closure-verified.json`, `usb-packaging.json`: unmodified mkbootfs12.1 fixture
  pack/unpack; existing crypto verifier PASS58 ELF nodes; deadline0755, rc0750,
  exact source/packed script bytes. No ELF was changed by R48.

Runtime delta from R45 is exactly two rc files and one new shell script under
`recovery/root`. `recovery/tools/check-usb-deadline.py` and this report are host
artifacts. Repack the actual R45 image with `scripts/twrp-repack.py`,
`--from b37182b --to <R48 commit> --allow-other`; no generated-fragment addition
or deletion is required. The early bind hides those fragments at runtime.
Do not use R44's source revision as --from for an image already repacked to R45.

The actual R45 image was also repacked offline with the existing tool:
`/home/danny/A9-build/twrp-usb-deadline-r48/recovery-r48.img`, 100663296 bytes,
SHA-256 `e8b70ee622e8352ebddc4390caa4cc9aa58196c880e7ffb773d11ddff4144f99`.
`actual-r48-delta.json` proves exactly the three runtime entries changed, with
source-identical bytes and a0755 deadline script; kernel, DTB and recovery_dtbo
are byte-identical to the actual R45 image. The offline ABL emulator returned
**PASS** for header, recovery_dtbo and DT selection/overlay. This does not
emulate kernel boot or USB. `abl-summary.json` records the observed command,
result and image hash. Its first sandbox invocation could not reach the Nix
daemon; the approved invocation completed successfully. No phone was used.

No phone access, adb/fastboot/edl command, NAS write, push, merge, shared-checkout
edit, subagent or independent review was performed. Coordinator owns physical
boot verification: confirm early bind/marker, fastboot enumeration/slot queries,
normal TWRP enumeration, and the absent-host 180-second return to bootloader.
Runtime USB recovery and decryption are not claimed as hardware passes.

BYAKUYA R48 DONE
