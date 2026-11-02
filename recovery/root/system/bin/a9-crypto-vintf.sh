#!/system/bin/sh
# All mounts are RAM views or read-only firmware, never writes to a partition.
setprop twrp.a9.crypto_ready 0
/system/bin/sh /system/bin/a9-crypto-rom-props.sh || exit 1
case "$(getprop ro.boot.slot_suffix)" in
    _a) modem=/dev/block/bootdevice/by-name/modem_a ;;
    _b) modem=/dev/block/bootdevice/by-name/modem_b ;;
    *) setprop twrp.a9.crypto_vintf failed; exit 1 ;;
esac

# KeymasterUtils hardcodes /vendor/firmware_mnt/image. Our path-only preload
# redirects that call to this read-only mount, including on mainline vendors
# which do not have a firmware_mnt directory. No TA or boot-chain blob copied.
mkdir -p /system/a9-crypto/firmware
if ! grep -q ' /system/a9-crypto/firmware ' /proc/mounts; then
    if ! mount -t vfat -o ro "$modem" /system/a9-crypto/firmware; then
        setprop twrp.a9.crypto_firmware failed
        exit 1
    fi
fi
setprop twrp.a9.crypto_firmware ro

# Mounted vendors may use a schema newer than recovery's libvintf. Hide their
# fragments for recovery only. The ramdisk view is already present unmounted.
if ! mount -o bind /system/etc/a9-recovery-vintf /vendor/etc/vintf; then
    setprop twrp.a9.crypto_vintf failed
    exit 1
fi
setprop twrp.a9.crypto_vintf recovery
setprop twrp.a9.crypto_ready 1
echo 'A9: self crypto firmware and recovery VINTF ready' >> /tmp/a9-crypto-vintf.log
