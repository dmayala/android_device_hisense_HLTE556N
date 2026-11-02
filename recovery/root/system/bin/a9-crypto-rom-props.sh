#!/system/bin/sh
# Read the BOOTED slot, never the ramdisk's build.prop or the other slot.
# Private read-only mounts avoid racing TWRP's vendor mount/unmount. noload
# also prevents ext4 journal replay. No key directory is read or written here.
umask 077
exec >> /tmp/a9-crypto-rom-props.log 2>&1
setprop twrp.a9.crypto_rom_props preparing
base=/tmp/a9-crypto-rom
sys=$base/system
ven=$base/vendor
sys_mounted=0
ven_mounted=0
cleanup() {
    [ "$ven_mounted" = 0 ] || umount "$ven"
    [ "$sys_mounted" = 0 ] || umount "$sys"
}
trap cleanup EXIT
fail() {
    echo "R50 ROM properties refused: $1"
    setprop twrp.a9.crypto_rom_props failed
    exit 1
}
case "$(getprop ro.boot.slot_suffix)" in
    _a) slot=_a ;;
    _b) slot=_b ;;
    *) fail unknown-slot ;;
esac
mkdir -p "$sys" "$ven" || fail mkdir

mount_slot() {
    part=$1
    point=$2
    for device in /dev/block/mapper/"$part$slot" /dev/block/bootdevice/by-name/"$part$slot"; do
        [ -b "$device" ] || continue
        if mount -t ext4 -o ro,noload "$device" "$point"; then return 0; fi
        if mount -t erofs -o ro "$device" "$point"; then return 0; fi
    done
    return 1
}
mount_slot system "$sys" || fail system-mount
sys_mounted=1
mount_slot vendor "$ven" || fail vendor-mount
ven_mounted=1

# Only key=value records; never source/eval a ROM file. Duplicate definitions
# of a requested property refuse instead of selecting an ambiguous version.
prop_from() {
    awk -v key="$1" '
        /^[ \t]*#/ { next }
        { p=index($0,"="); if (!p) next
          k=substr($0,1,p-1); gsub(/^[ \t]+|[ \t]+$/, "", k)
          if (k==key) { v=substr($0,p+1); gsub(/^[ \t]+|[ \t\r]+$/, "", v); n++ } }
        END { if (n==1 && length(v)>0) print v; else if (n==0) exit 1; else exit 2 }
    ' "$2"
}
system_prop=
for path in "$sys/system/build.prop" "$sys/build.prop" "$sys/system/etc/build.prop"; do
    if [ -f "$path" ]; then system_prop=$path; break; fi
done
vendor_prop=
for path in "$ven/build.prop" "$ven/etc/build.prop"; do
    if [ -f "$path" ]; then vendor_prop=$path; break; fi
done
[ -n "$system_prop" ] && [ -n "$vendor_prop" ] || fail build-prop-missing
release=$(prop_from ro.build.version.release "$system_prop") || fail release-missing
patch=$(prop_from ro.build.version.security_patch "$system_prop") || fail os-patch-missing
# QTI reads this spelling. AOSP's version.security_patch is the fallback on
# vendors that supply only that spelling. Reject conflicting aliases.
vendor_patch=$(prop_from ro.vendor.build.security_patch "$vendor_prop")
[ "$?" -le 1 ] || fail vendor-patch-invalid
vendor_alias=$(prop_from ro.vendor.build.version.security_patch "$vendor_prop")
[ "$?" -le 1 ] || fail vendor-patch-invalid
if [ -n "$vendor_patch" ] && [ -n "$vendor_alias" ] && [ "$vendor_patch" != "$vendor_alias" ]; then
    fail vendor-patch-conflict
fi
[ -n "$vendor_patch" ] || vendor_patch=$vendor_alias
[ -n "$vendor_patch" ] || fail vendor-patch-missing

# Match QTI's numeric version input. No invented "new enough" fallback.
echo "$release" | awk '/^[0-9]{1,2}(\.[0-9]{1,2})?(\.[0-9]{1,2})?$/ { ok=1 } END { exit !ok }' || fail release-invalid
valid_date() {
    echo "$1" | awk '
        /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/ {
            split($0,a,"-"); y=a[1]+0; m=a[2]+0; d=a[3]+0
            days=31
            if (m==4 || m==6 || m==9 || m==11) days=30
            if (m==2) days=28+(y%4==0 && (y%100!=0 || y%400==0))
            if (y>0 && m>=1 && m<=12 && d>=1 && d<=days) ok=1
        } END { exit !ok }'
}
valid_date "$patch" && valid_date "$vendor_patch" || fail patch-invalid

# Release mounts BEFORE publishing readiness. Leave no extra slot mount for
# fastbootd, installs or TWRP partition management to contend with.
umount "$ven" || fail vendor-unmount
ven_mounted=0
umount "$sys" || fail system-unmount
sys_mounted=0
set_exact() {
    /system/bin/resetprop -n "$1" "$2" || fail resetprop
    [ "$(getprop "$1")" = "$2" ] || fail property-readback
}
set_exact ro.build.version.release "$release"
set_exact ro.build.version.security_patch "$patch"
set_exact ro.vendor.build.security_patch "$vendor_patch"
set_exact ro.vendor.build.version.security_patch "$vendor_patch"
echo "R50 slot=$slot release=$release os_patch=$patch vendor_patch=$vendor_patch"
setprop twrp.a9.crypto_rom_props ready
