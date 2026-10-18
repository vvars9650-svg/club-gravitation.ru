#!/usr/bin/python3 -I
"""Root-owned public TEST release manager. No environment/path/shell overrides."""
import base64
import binascii
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile

BASE = Path('/srv/gravitation-test')
STATE = Path('/var/lib/gravitation-test-deploy')
MAX_INPUT = 48 * 1024 * 1024
MAX_FILE = 20 * 1024 * 1024
ID = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')
PAGES = {'index.html', '404.html', 'about/index.html', 'events/index.html',
         'first-contact/index.html', 'founders/index.html'}
CSS = {'assets/css/' + n + '.css' for n in
       ('site', 'story', 'polish', 'tz-20260831', 'events-hub', 'first-contact', 'founders')}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def release_id(value):
    require(isinstance(value, str) and ID.fullmatch(value), 'invalid release ID')
    return value


def trusted(path, directory=False):
    s = path.lstat()
    require(s.st_uid == 0 and not s.st_mode & 0o022, 'unsafe ownership/mode: ' + str(path))
    require(stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode),
            'unexpected file type: ' + str(path))
    if not directory:
        require(s.st_nlink == 1, 'hardlink rejected: ' + str(path))


def inventory(root):
    trusted(root, True)
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_dir() and not p.is_symlink():
            trusted(p, True)
        else:
            trusted(p)
            result[p.relative_to(root).as_posix()] = digest(p.read_bytes())
    return result


def load_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique)


def atomic_json(path, value):
    fd, name = tempfile.mkstemp(prefix='.state-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(value, out, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Manager:
    def __init__(self, base=BASE, state=STATE):
        self.base, self.state = base, state
        self.releases = base / 'releases'

    def read(self, name):
        p = self.state / name
        trusted(p)
        return load_json(p.read_bytes())

    def gate(self, directory):
        raw = (directory / 'assets/js/public-config.js').read_text()
        prefix = 'window.__V5_PUBLIC_CONFIG__='
        require(raw.startswith(prefix), 'unrecognized public config')
        config = load_json(raw[len(prefix):].strip().removesuffix(';'))
        require(config['mode'] == 'PUBLIC_BLOCKED' and config['prod_api_url'] == '',
                'PUBLIC_BLOCKED/empty PROD endpoint required')

    def target(self):
        link = self.base / 'current'
        s = link.lstat()
        require(stat.S_ISLNK(s.st_mode) and s.st_uid == 0, 'current must be root-owned symlink')
        target = Path(os.readlink(link))
        release_id(target.name)
        require(target == self.releases / target.name, 'current outside TEST releases')
        return target.name

    def verify(self, name):
        release_id(name)
        manifest = self.read(name + '.json')
        actual = inventory(self.releases / name)
        require(actual == manifest, 'release manifest mismatch: ' + name)
        policy = self.read('policy.json')
        require(actual.keys() == policy['baseline'].keys(), 'release file inventory changed')
        for key, value in policy['baseline'].items():
            if key not in policy['allowed']:
                require(actual[key] == value, 'protected file changed: ' + key)
        self.gate(self.releases / name)
        return actual

    def recover(self):
        state = self.read('state.json')
        current = self.target()
        if state.get('pending'):
            old, new = state['pending']
            require(current in (old, new), 'ambiguous switch; root intervention required')
            temporary = self.base / '.test-current-next'
            if os.path.lexists(temporary):
                require(temporary.is_symlink() and temporary.lstat().st_uid == 0 and
                        os.readlink(temporary) == str(self.releases / new),
                        'unexpected switch temporary path')
                temporary.unlink()
            if current == new:
                state = {'current': new, 'previous': old}
            else:
                state.pop('pending')
            atomic_json(self.state / 'state.json', state)
        require(current == state['current'], 'current/state mismatch')
        return state

    def switch(self, old, new, state):
        require(old != new, 'release already active')
        self.verify(old)
        self.verify(new)
        atomic_json(self.state / 'state.json', {**state, 'pending': [old, new]})
        link = self.base / '.test-current-next'
        require(not os.path.lexists(link), 'unexpected temporary link')
        os.symlink(str(self.releases / new), link)
        os.replace(link, self.base / 'current')
        sync_directory(self.base)
        atomic_json(self.state / 'state.json', {'current': new, 'previous': old})

    def initialize(self, initial):
        release_id(initial)
        require(not (self.state / 'state.json').exists(), 'already initialized')
        require(not os.path.lexists(self.base / 'current'), 'current already exists')
        data = inventory(self.releases / initial)
        self.gate(self.releases / initial)
        allowed = sorted(k for k in data if k in PAGES | CSS or
                         (k.startswith('assets/images/') and PurePosixPath(k).suffix.lower()
                          in {'.png', '.jpg', '.jpeg', '.webp'}))
        atomic_json(self.state / 'policy.json', {'allowed': allowed, 'baseline': data})
        atomic_json(self.state / (initial + '.json'), data)
        os.symlink(str(self.releases / initial), self.base / 'current')
        atomic_json(self.state / 'state.json', {'current': initial, 'previous': None})

    def deploy(self, name, checksum, payload):
        release_id(name)
        require(SHA.fullmatch(checksum), 'invalid SHA-256')
        require(len(payload) <= MAX_INPUT and digest(payload) == checksum, 'package checksum/size mismatch')
        bundle = load_json(payload)
        require(set(bundle) == {'base', 'files'}, 'invalid package fields')
        state = self.recover()
        require(bundle['base'] == state['current'], 'stale package base')
        old = self.verify(state['current'])
        files = bundle['files']
        require(isinstance(files, dict) and len(files) <= 64, 'invalid file count')
        policy = self.read('policy.json')
        decoded = {}
        for key, entry in files.items():
            require(key in policy['allowed'], 'file outside approved public allowlist: ' + key)
            require(isinstance(entry, dict) and set(entry) == {'sha256', 'base64'}, 'invalid file entry')
            try:
                content = base64.b64decode(entry['base64'], validate=True)
            except (ValueError, binascii.Error):
                raise ValueError('invalid base64') from None
            require(len(content) <= MAX_FILE and digest(content) == entry['sha256'], 'file checksum/size mismatch')
            decoded[key] = content
        final = self.releases / name
        require(not os.path.lexists(final) and not (self.state / (name + '.json')).exists(), 'release ID already used')
        require(sum(1 for p in self.releases.iterdir() if p.is_dir()) < 20,
                '20-release retention limit; owner must review cleanup')
        needed = sum(p.stat().st_size for p in (self.releases / state['current']).rglob('*') if p.is_file())
        needed += sum(len(v) for v in decoded.values()) + 512 * 1024 * 1024
        require(shutil.disk_usage(self.releases).free >= needed, 'insufficient free space including 512 MiB reserve')
        staging = Path(tempfile.mkdtemp(prefix='.test-build-', dir=self.releases))
        try:
            shutil.copytree(self.releases / state['current'], staging, dirs_exist_ok=True)
            for key, content in decoded.items():
                p = staging / key
                p.write_bytes(content)
                p.chmod(0o644)
            for p in staging.rglob('*'):
                if p.is_dir():
                    p.chmod(0o755)
                else:
                    with p.open('rb') as f:
                        os.fsync(f.fileno())
            staging.chmod(0o755)
            expected = {**old, **{k: digest(v) for k, v in decoded.items()}}
            require(inventory(staging) == expected, 'unexpected release differences')
            self.gate(staging)
            os.rename(staging, final)
            sync_directory(self.releases)
            atomic_json(self.state / (name + '.json'), expected)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        self.switch(state['current'], name, state)
        return {'current': name, 'previous': state['current'],
                'changed': sorted(k for k in decoded if old[k] != expected[k])}

    def rollback(self):
        state = self.recover()
        require(state['previous'] is not None, 'no previous release')
        self.switch(state['current'], state['previous'], state)
        return self.recover()


def main():
    require(os.geteuid() == 0, 'root-owned sudo entrypoint required')
    os.umask(0o077)
    for p in (Path('/srv'), BASE, BASE / 'releases', Path('/var/lib'), STATE):
        trusted(p, True)
    with (STATE / 'lock').open('a') as lock:
        trusted(STATE / 'lock')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manager = Manager()
        args = sys.argv[1:]
        if len(args) == 1 and args[0] == 'status':
            result = manager.recover()
            manager.verify(result['current'])
            if result['previous'] is not None:
                manager.verify(result['previous'])
        elif len(args) == 3 and args[0] == 'deploy':
            result = manager.deploy(args[1], args[2], sys.stdin.buffer.read(MAX_INPUT + 1))
        elif args == ['rollback']:
            result = manager.rollback()
        elif args == ['initialize', 'event01-20261016-7605aba']:
            manager.initialize(args[1])
            result = manager.recover()
        else:
            raise ValueError('usage: status | deploy ID SHA256 < package.json | rollback')
        print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        sys.exit(1)
