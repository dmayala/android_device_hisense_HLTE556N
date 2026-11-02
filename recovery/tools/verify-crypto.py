#!/usr/bin/env python3
"""Check an unpacked recovery ramdisk, with readelf; never accesses a device.

Example: python3 recovery/tools/verify-crypto.py --ramdisk /path/to/unpacked/rd
Run on the CI ramdisk too: a source-tree check cannot prove CI packaged an ELF.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

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
seen = {}
while queue:
    path = queue.pop(0)
    if str(path) in seen:
        continue
    f = root / path
    assert f.is_file(), f'missing ELF: {path}'
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
        assert os.access(root / entry['ramdisk'], os.X_OK), f'not executable: {entry["ramdisk"]}'
impl = 'android.hardware.gatekeeper@1.0-impl-qti.so'
assert (root / 'system/lib64/hw' / impl).resolve() == (root / 'system/a9-crypto/lib64/hw' / impl).resolve()
for name in ('fstab.default', 'fstab.qcom'):
    rows = [x.split() for x in (root / 'system/etc' / name).read_text().splitlines() if x and not x.startswith('#')]
    assert {r[1] for r in rows} == {'/metadata', '/data'}
    data = next(r for r in rows if r[1] == '/data')
    assert all(x in data[4] for x in ('wrappedkey_v0', 'metadata_encryption=aes-256-xts:wrappedkey_v0', 'keydirectory=/metadata/vold/metadata_encryption'))
config = (root / 'system/etc/ld.config.txt').read_text().split('[crypto]', 1)[1].split('[recovery]', 1)[0]
assert 'namespace.default.isolated = true' in config and '/vendor' not in config and '/odm' not in config
print(json.dumps({'result': 'PASS', 'scope': 'static ELF closure, inventory and packaging; no TEE/decrypt execution', 'nodes': seen}, indent=2))
