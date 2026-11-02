#!/usr/bin/env python3
"""Check an unpacked recovery ramdisk, with readelf; never accesses a device.

Example: python3 recovery/tools/verify-crypto.py --ramdisk /path/to/unpacked/rd
Run on the CI ramdisk too: a source-tree check cannot prove CI packaged an ELF.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ramdisk', type=Path, required=True)
parser.add_argument('--readelf', default='readelf')
args = parser.parse_args()
root = args.ramdisk.resolve()
inventory = json.loads((Path(__file__).parent.parent / 'crypto-blobs.json').read_text())
search = [Path('system/a9-crypto/lib64'), Path('system/lib64')]
# qseecomd's DT_NEEDED misses its listener dlopens. Gatekeeper's service also
# loads its passthrough implementation dynamically rather than via DT_NEEDED.
queue = [Path(x['ramdisk']) for x in inventory['files']]
queue += [Path('system/lib64/liba9_recovery_crypto_wait.so')]
queue += [Path('system/lib64/liba9_crypto_diagnostics.so')]
seen = {}
while queue:
    path = queue.pop(0)
    if str(path) in seen:
        continue
    f = root / path
    assert f.is_file(), f'missing ELF: {path}'
    assert stat.S_IMODE(f.stat().st_mode) & 0o444 == 0o444, f'not readable: {path}'
    text = subprocess.check_output([args.readelf, '-h', '-d', '-l', str(f)], text=True)
    assert 'AArch64' in text, f'not ARM64: {path}'
    # RPATH/RUNPATH would add an unchecked search path.
    assert not re.search(r'\((?:RPATH|RUNPATH)\)', text), f'extra search path: {path}'
    deps = re.findall(r'\(NEEDED\).*?\[(.*?)\]', text)
    resolved = []
    for dep in deps:
        assert '/' not in dep, f'absolute/non-SONAME dependency: {path}: {dep}'
        found = next((d / dep for d in search if (root / d / dep).is_file()), None)
        assert found is not None, f'unresolved dependency: {path}: {dep}'
        assert (root / found).resolve().is_relative_to(root), f'escapes ramdisk: {found}'
        resolved.append(str(found))
        queue.append(found)
    interpreter = re.search(r'Requesting program interpreter: (.*?)\]', text)
    if interpreter:
        queue.append(Path(interpreter[1].lstrip('/')))
    seen[str(path)] = {'sha256': hashlib.sha256(f.read_bytes()).hexdigest(), 'needed': resolved}
for entry in inventory['files']:
    assert seen[entry['ramdisk']]['sha256'] == entry['sha256'], f'blob changed: {entry["ramdisk"]}'
    if '/bin/' in entry['ramdisk']:
        assert stat.S_IMODE((root / entry['ramdisk']).stat().st_mode) == 0o755, f'not 0755: {entry["ramdisk"]}'
        assert entry['ramdisk'].startswith('system/bin/a9-crypto/'), f'outside fs_config executable rule: {entry["ramdisk"]}'
# Also check the prep interpreter/script and existing preloads in the packed
# ramdisk. A root-only os.access(X_OK) check does not require all execute bits.
for path in ('system/bin/sh', 'system/bin/linker64', 'system/bin/a9-crypto-vintf.sh',
             'system/bin/a9-crypto-snapshot.sh'):
    assert stat.S_IMODE((root / path).stat().st_mode) == 0o755, f'not 0755: {path}'
rc = (root / 'init.recovery.qcom.rc').read_text()
assert '/system/a9-crypto/bin/' not in rc, 'stale crypto service path'
for entry in inventory['files']:
    if '/bin/' in entry['ramdisk']:
        assert f"/{entry['ramdisk']}\n" in rc, f'service path missing: {entry["ramdisk"]}'
for path in ('system/etc/ld.config.txt', 'system/etc/a9-crypto.ld.config.txt'):
    selectors = (root / path).read_text().split('[crypto]', 1)[0]
    assert 'dir.crypto = /system/bin/a9-crypto\n' in selectors, f'wrong crypto selector: {path}'
    if 'dir.recovery' in selectors:
        assert selectors.index('dir.crypto') < selectors.index('dir.recovery'), f'crypto selector must precede recovery: {path}'
impl = 'android.hardware.gatekeeper@1.0-impl-qti.so'
assert (root / 'system/lib64/hw' / impl).resolve() == (root / 'system/a9-crypto/lib64/hw' / impl).resolve()
# libvintf rejects multiple versions with the same major in a single HAL.
# keystore2's VINTF helper dereferences the resulting null manifest.
manifest_paths = ('system/etc/a9-recovery-vintf/manifest.xml', 'vendor/etc/vintf/manifest.xml')
assert (root / manifest_paths[0]).read_bytes() == (root / manifest_paths[1]).read_bytes()
manifest = ET.parse(root / manifest_paths[0]).getroot()
for hal in manifest.findall('hal'):
    versions = [v.text for v in hal.findall('version')]
    majors = [v.split('.')[0] for v in versions]
    assert len(set(majors)) == len(majors), f'duplicate major: {hal.findtext("name")}'
    if hal.findtext('name') == 'android.hardware.keymaster':
        assert versions == ['4.1'], 'declare inherited keymaster 4.0 through 4.1'
keystore_rc = (root / 'system/etc/init/keystore2.rc').read_text()
assert '    disabled\n' in keystore_rc and 'on late-init' not in keystore_rc
ready_action = rc.split('on property:twrp.a9.crypto_ready=1\n', 1)[1].split('\nservice ', 1)[0]
assert '    start keystore2\n' in ready_action
for name in ('fstab.default', 'fstab.qcom'):
    rows = [x.split() for x in (root / 'system/etc' / name).read_text().splitlines() if x and not x.startswith('#')]
    assert {r[1] for r in rows} == {'/metadata', '/data'}
    data = next(r for r in rows if r[1] == '/data')
    assert all(x in data[4] for x in ('wrappedkey_v0', 'metadata_encryption=aes-256-xts:wrappedkey_v0', 'keydirectory=/metadata/vold/metadata_encryption'))
config = (root / 'system/etc/ld.config.txt').read_text().split('[crypto]', 1)[1].split('[recovery]', 1)[0]
assert 'namespace.default.isolated = true' in config and '/vendor' not in config and '/odm' not in config
print(json.dumps({'result': 'PASS', 'scope': 'static ELF closure, inventory and packaging; no TEE/decrypt execution', 'nodes': seen}, indent=2))
