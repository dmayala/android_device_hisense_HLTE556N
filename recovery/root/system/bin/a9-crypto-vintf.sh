#!/system/bin/sh
# Only a RAM bind mount: never modify the slot's vendor image or its files.
if [ ! -d /vendor/lib64/a9-wrapped-stock ]; then
    setprop twrp.a9.crypto_vintf stock
    exit 0
fi

if mount -o bind /system/etc/a9-recovery-vintf /vendor/etc/vintf; then
    setprop twrp.a9.crypto_vintf recovery
    echo 'A9: using recovery VINTF schema for wrapped LOS24 vendor' >> /tmp/a9-crypto-vintf.log
else
    setprop twrp.a9.crypto_vintf failed
    echo 'A9: recovery VINTF bind failed; crypto may remain unavailable' >> /tmp/a9-crypto-vintf.log
    exit 1
fi
