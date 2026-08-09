#!/system/bin/sh
#
# Clear the bootloader control block (BCB) when leaving TWRP for Android.
#
# WHY: TWRP's rb_system path never clears it --
#     case rb_system:
#         Update_Intent_File("s");
#         sync();
#         check_and_run_script("/system/bin/rebootsystem.sh", "reboot system");
#         return property_set(ANDROID_RB_PROPERTY, "reboot,");
# so the "boot-recovery" command written by `adb reboot recovery` survives and
# the bootloader sends the device straight back into recovery. Reported on
# device 2026-08-09: "Reboot System" from the TWRP UI booted back to recovery.
# TWRP calls this hook first, which is where the clear belongs.
#
# Only the 2048-byte bootloader_message is zeroed. Do NOT wipe more, and never
# `fastboot erase misc`: this is a Virtual A/B device and misc also holds
# misc_virtual_ab_message at offset 32768 (magic 02 b0 0a 74 56 00 01 00).
# Destroying that breaks snapshot/merge state.

MISC=/dev/block/bootdevice/by-name/misc

if [ -e "$MISC" ]; then
    dd if=/dev/zero of="$MISC" bs=1 count=2048 conv=notrunc 2>/dev/null
    sync
fi
