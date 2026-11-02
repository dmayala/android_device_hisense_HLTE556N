#!/system/bin/sh
# Passive RAM-only diagnostics. Never read key bytes, hashes, credentials or IDs.
# Known file names only; no recursive dump of /metadata or /data.
umask 077
exec > /tmp/a9-crypto-snapshot.log 2>&1

snapshot() {
    read uptime rest < /proc/uptime
    echo "=== R49 uptime=$uptime ==="
    for prop in fstab.additional twrp.a9.crypto_ready twrp.a9.crypto_vintf \
        twrp.a9.crypto_firmware twrp.a9.crypto_rom_props vendor.sys.listeners.registered \
        init.svc.vendor.qseecomd init.svc.vendor.keymaster-4-1 \
        init.svc.gatekeeper-1-0 init.svc.keystore2 keystore.crash_count \
        twrp.a9.crypto_timeout ro.crypto.fs_crypto_blkdev ro.crypto.metadata.enabled \
        ro.crypto.state ro.crypto.type vold.storage_seed_bound \
        ro.crypto.dm_default_key.options_format.version ro.crypto.set_dun \
        ro.build.version.release ro.build.version.security_patch \
        ro.vendor.build.version.release ro.vendor.build.security_patch \
        ro.vendor.build.version.security_patch ro.bootimage.build.version.security_patch; do
        echo "$prop=$(getprop "$prop")"
    done
    # Avoid dmsetup table/targets: these can contain raw encryption keys.
    for point in /metadata /data /tmp /system/a9-crypto/firmware; do
        awk -v point="$point" '$2 == point { print "mount", $2, $3, $4 }' /proc/mounts
    done
    for base in /metadata/vold/metadata_encryption /metadata/vold/metadata_encryption/key; do
        if [ -d "$base" ]; then
            echo "$base directory present"
        else
            echo "$base directory absent"
        fi
    done
    for name in version secdiscardable stretching encrypted_key keymaster_key_blob keymaster_key_blob_upgraded; do
        path=/metadata/vold/metadata_encryption/key/$name
        if [ -f "$path" ] && [ ! -L "$path" ]; then
            stat -c '%n size=%s mode=%a uid=%u gid=%g' "$path"
            if [ "$name" = version ]; then
                # Classify exactly one ASCII byte, never print arbitrary bytes.
                if [ "$(stat -c %s "$path")" = 1 ] && [ "$(cat "$path")" = 1 ]; then
                    echo 'metadata key storage version=1'
                else
                    echo 'metadata key storage version differs from expected single byte 1'
                fi
            fi
        else
            echo "$path absent-or-not-regular"
        fi
    done
    # Only the crypto fstab fields; never dump props, cmdline or process argv.
    if [ -f /etc/additional.fstab ]; then
        awk '$1 !~ /^#/ && $2 == "/data" { print "data fs=" $3, "mount_flags=" $4, "fs_mgr_flags=" $5 }' /etc/additional.fstab
    fi
    for path in /tmp/misc /tmp/misc/keystore; do
        if [ -d "$path" ]; then stat -c '%n directory mode=%a uid=%u gid=%g' "$path"; fi
    done
}

snapshot
# Relative waits: snapshots at approximately 0, 2, 5, 10, 20 and 40 seconds.
# Runs as its own oneshot service, never blocks init or USB.
for delay in 2 3 5 10 20; do
    sleep "$delay"
    snapshot
done
echo 'R49 snapshot complete'
