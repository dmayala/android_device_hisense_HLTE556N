#!/usr/bin/env python3
"""Five focused offline USB checks; optionally run the script with Android mksh.

  python3 recovery/tools/check-usb-deadline.py --shell /path/to/host/sh
  python3 recovery/tools/check-usb-deadline.py --shell /rd/system/bin/sh \
      --qemu /path/to/qemu-aarch64 --ramdisk /rd

No phone access. All absolute script paths and reboot are replaced in the test
copy only. The production script has no test switches or configurable timeout.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--shell', default='/bin/sh')
ap.add_argument('--qemu')
ap.add_argument('--ramdisk', type=Path)
args = ap.parse_args()
root = Path(__file__).resolve().parents[1] / 'root'
script = (root / 'system/bin/a9-usb-deadline.sh').read_text()
rc = (root / 'system/etc/init/hw/init.rc').read_text()
qcom = (root / 'init.recovery.qcom.rc').read_text()

with tempfile.TemporaryDirectory(prefix='a9-usb-deadline-') as tmp:
    fixture = Path(tmp)
    for name in ('proc', 'config/usb_gadget/g1', 'sys/class/udc/test.udc', 'dev'):
        (fixture / name).mkdir(parents=True)
    body = script
    for prefix in ('/proc/uptime', '/config/usb_gadget/g1/UDC', '/sys/class/udc/', '/dev/kmsg'):
        body = body.replace(prefix, str(fixture) + prefix)
    body = body.replace('/system/bin/reboot bootloader', 'record_reboot bootloader')
    # Virtual clock and properties: helpers are shell builtins, including when
    # the real Android mksh is executed under QEMU. No host reboot can execute.
    prelude = '''
ticks=0
update() {
    echo "$ticks.00 0.00" > FIXTURE/proc/uptime
    echo test.udc > FIXTURE/config/usb_gadget/g1/UDC
    state=configured
    case "$scenario" in
        stale) echo > FIXTURE/config/usb_gadget/g1/UDC ;;
        absent) state='not attached' ;;
        late) [ "$ticks" -ge 179 ] || state='not attached' ;;
    esac
    echo "$state" > FIXTURE/sys/class/udc/test.udc/state
}
getprop() {
    case "$1" in
        sys.usb.state) echo "$mode" ;;
        sys.usb.ffs.ready|sys.usb.ffs.mtp.ready) echo 1 ;;
        init.svc.adbd|init.svc.fastbootd) echo running ;;
    esac
}
setprop() { echo "$1 $2" >> FIXTURE/events; }
sleep() { ticks=$((ticks + 1)); update; }
record_reboot() { echo "reboot $1 ticks=$ticks" >> FIXTURE/events; }
update
'''.replace('FIXTURE', str(fixture))
    def run(scenario, mode, expected):
        events = fixture / 'events'
        events.unlink(missing_ok=True)
        program = fixture / 'probe.sh'
        program.write_text(f'scenario={scenario}\nmode={mode}\n' + prelude + body)
        cmd = [args.shell, str(program)]
        if args.qemu:
            assert args.ramdisk, '--qemu needs --ramdisk'
            cmd = [args.qemu, '-L', str(args.ramdisk), '-E',
                   f'LD_LIBRARY_PATH={args.ramdisk}/system/lib64'] + cmd
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, (result.returncode, result.stderr)
        assert events.read_text() == expected, (scenario, mode, events.read_text())

    # Group 1: normal attached TWRP and fastbootd all disarm immediately.
    for mode in ('adb', 'mtp,adb', 'mtp', 'fastboot', 'sideload'):
        run('attached', mode, 'twrp.a9.usb_deadline satisfied\n')
    print('PASS attached adb/MTP/fastbootd/sideload: deadline exits once')
    # Group 2: readiness properties and daemons alone cannot cancel fallback.
    run('stale', 'fastboot', 'twrp.a9.usb_deadline expired\nreboot bootloader ticks=180\n')
    print('PASS stale ready/state/running with empty UDC: bootloader at 180s')
    # Group 3: bound gadget without a host is not enumeration success.
    run('absent', 'adb', 'twrp.a9.usb_deadline expired\nreboot bootloader ticks=180\n')
    print('PASS absent host with bound UDC: one bootloader request at 180s')
    # Group 4: last-second enumeration cancels the fallback.
    run('late', 'fastboot', 'twrp.a9.usb_deadline satisfied\n')
    print('PASS enumeration at 179s: deadline disarmed')

# Group 5: replay the observed startupArgs selector ordering against the rc.
# The old configfs=1 none trigger is false while configfs=0; the new action is
# unconditional. Fastboot cleans links BEFORE starting its descriptor writer.
def action(text, header):
    lines = text.splitlines()
    start = lines.index(header) + 1
    end = next((i for i in range(start, len(lines))
                if lines[i] and not lines[i].startswith((' ', '#'))), len(lines))
    return '\n'.join(lines[start:end])

none = action(rc, 'on property:sys.usb.config=none')
fastboot = action(rc, 'on property:sys.usb.config=fastboot && property:sys.usb.configfs=1')
for block in (none, fastboot):
    for command in ('write /config/usb_gadget/g1/UDC "none"', 'stop adbd',
                    'stop fastbootd', 'setprop sys.usb.ffs.ready 0',
                    'rm /config/usb_gadget/g1/configs/b.1/f1',
                    'rm /config/usb_gadget/g1/configs/b.1/f2'):
        assert command in block, command
        if block == fastboot:
            assert block.index(command) < block.index('start fastbootd')
assert 'on property:sys.usb.config=fastboot\n' not in rc
assert 'exec_start a9-crypto-vintf' not in qcom
assert '    start a9-crypto-vintf\n' in action(qcom, 'on property:fstab.additional=1')
assert '    start a9-usb-deadline\n' in qcom
assert 'setprop ro.twrp.a9.usb_deadline 180' in qcom
assert '    start keystore2\n' in action(qcom, 'on property:twrp.a9.crypto_ready=1')
assert '    mount none /system/etc/a9-recovery-vintf /vendor/etc/vintf bind\n' in qcom
view = ET.parse(root / 'system/etc/a9-recovery-vintf/manifest.xml').getroot()
names = {h.findtext('name') for h in view.findall('hal')}
assert 'android.hardware.boot' in names and 'android.hardware.health' not in names
print('PASS disabled health undeclared, selector-race ordering, async crypto and early deadline')
