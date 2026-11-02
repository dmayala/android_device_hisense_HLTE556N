#!/system/bin/sh
# Recovery only. No direct partition writes or automatic recovery retry;
# reboot uses init's normal bootloader request (including its BCB handling).
# Use uptime rather than loop counts so time spent in helpers counts as well.
PATH=/system/bin:/sbin
export PATH
read -r started _ < /proc/uptime || started=0
deadline=$(( ${started%%.*} + 180 ))

usb_configured() {
    # Neither a running daemon nor a stale ready/state property proves that
    # the gadget bound successfully. Require an actual host configuration.
    read -r controller < /config/usb_gadget/g1/UDC || return 1
    case "$controller" in ''|none) return 1 ;; esac
    case "$controller" in *[!a-zA-Z0-9._-]*) return 1 ;; esac
    read -r state < "/sys/class/udc/$controller/state" || return 1
    [ "$state" = configured ] || return 1
    case "$(getprop sys.usb.state)" in
        adb|sideload|mtp,adb)
            [ "$(getprop sys.usb.ffs.ready)" = 1 ] &&
                [ "$(getprop init.svc.adbd)" = running ] ;;
        fastboot)
            [ "$(getprop sys.usb.ffs.ready)" = 1 ] &&
                [ "$(getprop init.svc.fastbootd)" = running ] ;;
        mtp) [ "$(getprop sys.usb.ffs.mtp.ready)" = 1 ] ;;
        *) return 1 ;;
    esac
}

while :; do
    if usb_configured 2>/dev/null; then
        setprop twrp.a9.usb_deadline satisfied
        exit 0
    fi
    read -r now _ < /proc/uptime || break
    [ "${now%%.*}" -lt "$deadline" ] || break
    sleep 1
done

setprop twrp.a9.usb_deadline expired
echo 'A9: USB did not configure in 180s; rebooting to bootloader' > /dev/kmsg
# reboot(8) requests sys.powerctl; init handles this specially, even while an
# exec service is pending. Bootloader is the destination, never recovery.
/system/bin/reboot bootloader
