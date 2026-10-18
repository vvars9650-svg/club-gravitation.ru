#!/usr/bin/env python3
"""Build a TEST delta package. No server writes and no deployment."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--base', required=True, help='current TEST release ID from status')
p.add_argument('--root', type=Path, required=True, help='approved source directory')
p.add_argument('--output', type=Path, required=True)
p.add_argument('files', nargs='*', help='explicit relative file paths; empty = unchanged smoke release')
a = p.parse_args()
files = {}
root = a.root.resolve(strict=True)
for name in a.files:
    path = (root / name).resolve(strict=True)
    if not path.is_relative_to(root) or name in files:
        p.error('invalid/duplicate source path: ' + name)
    content = path.read_bytes()
    files[name] = {'sha256': hashlib.sha256(content).hexdigest(),
                   'base64': base64.b64encode(content).decode('ascii')}
payload = json.dumps({'base': a.base, 'files': files}, sort_keys=True, separators=(',', ':')).encode()
a.output.write_bytes(payload)
print(hashlib.sha256(payload).hexdigest())
