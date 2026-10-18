#!/usr/bin/python3 -I
"""ONE-TIME ROOT INSTALLER. Requires Vlad's separate approval of this exact plan.

Run only from a reviewed, checksummed package in a root-controlled directory.
This file is NOT installed in sudoers and is NOT a permanent privileged command.
"""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

BASE = Path('/srv/gravitation-test')
STATE = Path('/var/lib/gravitation-test-deploy')
NGINX = Path('/etc/nginx/sites-available/test.club-gravitation.ru')
COMMAND = Path('/usr/local/sbin/gravitation-test-release')
SUDOERS = Path('/etc/sudoers.d/gravitation-test-public')
INITIAL = 'event01-20261016-7605aba'
EXPECTED_NGINX = 'c447613454acac782ee1a957a95d4ae5f5be8fda8bcc51d14fdd18eaa076f9a1'
OLD_ROOT = b'root /srv/gravitation-test/releases/event01-20261016-7605aba;'
NEW_ROOT = b'root /srv/gravitation-test/current;'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def run(*args):
    subprocess.run(args, check=True, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C'})


def write(path, data, mode):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as out:
        os.fchmod(out.fileno(), mode)
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def atomic_bytes(path, data, mode):
    temporary = path.with_name(path.name + '.test-install-new')
    write(temporary, data, mode)
    os.replace(temporary, path)


def main():
    require(os.geteuid() == 0 and len(sys.argv) == 1, 'one-time root session required; no arguments')
    os.umask(0o077)
    source = Path(__file__).resolve().parent
    for directory in [source, *source.parents]:
        info = directory.lstat()
        require(info.st_uid == 0 and not info.st_mode & 0o022, 'installer must run from root-controlled staging')
    for name in ('selectel-test-release.py', 'selectel-test-deploy.sudoers'):
        p = source / name
        info = p.lstat()
        require(info.st_uid == 0 and not info.st_mode & 0o022 and not p.is_symlink(), 'unsafe installation source')
    command = (source / 'selectel-test-release.py').read_bytes()
    sudoers = (source / 'selectel-test-deploy.sudoers').read_bytes()
    original = NGINX.read_bytes()
    require(hashlib.sha256(original).hexdigest() == EXPECTED_NGINX, 'TEST nginx baseline changed; review a new diff')
    require(original.count(OLD_ROOT) == 1, 'unexpected TEST root')
    require(all(not os.path.lexists(p) for p in (STATE, COMMAND, SUDOERS, BASE / 'current', BASE / '.test-current-next')),
            'existing installation or temporary state; stop for review')
    for p in (NGINX, BASE / 'releases' / INITIAL):
        require(p.lstat().st_uid == 0 and not p.lstat().st_mode & 0o022 and not p.is_symlink(), 'untrusted baseline')
    # Read-only isolation snapshots: these paths are never written by this installer.
    isolated = [Path('/srv/gravitation/current'), Path('/srv/gravitation-admin/current')]
    links = {str(p): os.readlink(p) for p in isolated}
    nginx_backup = original.replace(OLD_ROOT, NEW_ROOT)
    backup_parent = Path('/var/backups/gravitation-test-deploy')
    if not backup_parent.exists():
        backup_parent.mkdir(mode=0o700)
    require(backup_parent.lstat().st_uid == 0 and not backup_parent.is_symlink() and
            not backup_parent.lstat().st_mode & 0o077, 'unsafe backup directory')
    backup = backup_parent / datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup.mkdir(mode=0o700)
    write(backup / 'test-nginx.before', original, 0o600)
    write(backup / 'test-nginx.after', nginx_backup, 0o600)
    write(backup / 'isolation-links.json', json.dumps(links, sort_keys=True).encode(), 0o600)
    write(backup / 'installation-sources.sha256',
          ('%s  gravitation-test-release\n%s  gravitation-test-public\n' %
           (hashlib.sha256(command).hexdigest(), hashlib.sha256(sudoers).hexdigest())).encode(), 0o600)
    STATE.mkdir(mode=0o700)
    nginx_changed = False
    command_created = False
    sudoers_created = False
    current_created = False
    try:
        write(COMMAND, command, 0o755)
        command_created = True
        spec = importlib.util.spec_from_file_location('test_release', source / 'selectel-test-release.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.Manager().initialize(INITIAL)
        current_created = True
        # Only one root directive changes; Admin include and all other bytes remain identical.
        atomic_bytes(NGINX, nginx_backup, 0o644)
        nginx_changed = True
        run('/usr/sbin/nginx', '-t')
        candidate = backup / 'sudoers.candidate'
        write(candidate, sudoers, 0o440)
        run('/usr/sbin/visudo', '-cf', str(candidate))
        write(SUDOERS, sudoers, 0o440)
        sudoers_created = True
        run('/usr/sbin/visudo', '-c')
        run('/usr/bin/systemctl', 'reload', 'nginx')
        require(all(os.readlink(p) == links[str(p)] for p in isolated), 'isolation symlink changed')
        run(str(COMMAND), 'status')
        print('INSTALLED; backup=' + str(backup))
    except BaseException:
        if sudoers_created:
            SUDOERS.unlink()
        if nginx_changed:
            atomic_bytes(NGINX, original, 0o644)
            run('/usr/sbin/nginx', '-t')
            run('/usr/bin/systemctl', 'reload', 'nginx')
        if current_created:
            (BASE / 'current').unlink()
        if command_created:
            COMMAND.unlink()
        print('INSTALLATION FAILED; configuration restored; diagnostic state retained: ' + str(backup), file=sys.stderr)
        raise


if __name__ == '__main__':
    main()
