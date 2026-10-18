"""Linux unit tests using temporary fixtures, never /srv or sudo."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

if 'release' not in globals():
    spec = importlib.util.spec_from_file_location('release', Path(__file__).parents[1] / 'scripts/selectel-test-release.py')
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base, self.state = self.root / 'test', self.root / 'state'
        self.base.mkdir(mode=0o755)
        self.state.mkdir(mode=0o700)
        self.initial = self.base / 'releases/event01-20261016-7605aba'
        self.initial.mkdir(parents=True, mode=0o755)
        for name, content in {
            'index.html': b'approved homepage', 'about/index.html': b'old ABOUT',
            'assets/css/story.css': b'approved CSS', 'apply/index.html': b'blocked form',
            'assets/js/apply.js': b'PUBLIC_BLOCKED',
            'assets/js/public-config.js': b'window.__V5_PUBLIC_CONFIG__={"mode":"PUBLIC_BLOCKED","prod_api_url":""};',
            'legal/frozen/FORM-2.3.txt': b'frozen', 'admin/index.html': b'admin placeholder',
        }.items():
            p = self.initial / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)
            p.chmod(0o644)
        for p in self.base.rglob('*'):
            if p.is_dir():
                p.chmod(0o755)
        # Emulate root ownership for fixtures under an unprivileged Linux account.
        # Mode, type, link and manifest validation remain the real implementation.
        real_lstat = Path.lstat
        def root_stat(p, *args, **kwargs):
            values = list(real_lstat(p, *args, **kwargs))
            values[4] = 0
            return os.stat_result(values)
        self.stat_patch = patch.object(Path, 'lstat', root_stat)
        self.stat_patch.start()
        self.addCleanup(self.stat_patch.stop)
        self.manager = release.Manager(self.base, self.state)
        self.manager.initialize(self.initial.name)

    def bundle(self, files=None, base=None):
        entries = {k: {'sha256': release.digest(v), 'base64': base64.b64encode(v).decode()}
                   for k, v in (files or {}).items()}
        return json.dumps({'base': base or self.initial.name, 'files': entries}).encode()

    def deploy(self, files=None, name='smoke-test', base=None):
        payload = self.bundle(files, base)
        return self.manager.deploy(name, release.digest(payload), payload)

    def test_deploy_clone_and_rollback(self):
        baseline = release.inventory(self.initial)
        result = self.deploy({'about/index.html': b'new approved ABOUT'})
        self.assertEqual(result['changed'], ['about/index.html'])
        self.assertEqual(release.inventory(self.initial), baseline)
        self.assertEqual(self.manager.target(), 'smoke-test')
        self.assertEqual(self.manager.rollback()['current'], self.initial.name)
        self.assertEqual(self.manager.rollback()['current'], 'smoke-test')

    def test_unchanged_smoke_release(self):
        self.assertEqual(self.deploy()['changed'], [])
        self.assertEqual(release.inventory(self.base / 'releases/smoke-test'), release.inventory(self.initial))

    def test_protected_files(self):
        for name in ['assets/js/public-config.js', 'assets/js/apply.js', 'apply/index.html',
                     'admin/index.html', 'admin-prod/index.html', 'legal/frozen/FORM-2.3.txt',
                     '../production/index.html', '/etc/sudoers', 'new-file.html']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.deploy({name: b'unsafe'})
        self.assertEqual(self.manager.target(), self.initial.name)

    def test_invalid_ids_checksums_and_stale_base(self):
        for name in ['../prod', '/srv/gravitation/current', 'a b', 'a;id', '.hidden', 'x' * 97]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.deploy(name=name)
        with self.assertRaises(ValueError):
            self.manager.deploy('bad', '0' * 64, self.bundle())
        with self.assertRaises(ValueError):
            self.deploy(base='stale')
        self.deploy()
        with self.assertRaises(ValueError):
            self.deploy(name='smoke-test', base='smoke-test')

    def test_file_checksum_and_duplicate_json(self):
        p = json.loads(self.bundle({'about/index.html': b'new'}))
        p['files']['about/index.html']['sha256'] = '0' * 64
        payload = json.dumps(p).encode()
        with self.assertRaises(ValueError):
            self.manager.deploy('bad', release.digest(payload), payload)
        with self.assertRaises(ValueError):
            release.load_json(b'{"files":{},"files":{}}')

    def test_symlink_hardlink_and_mode_rejected(self):
        p = self.initial / 'about/index.html'
        original = p.read_bytes()
        p.unlink()
        p.symlink_to(self.initial / 'index.html')
        with self.assertRaises(ValueError):
            self.manager.verify(self.initial.name)
        p.unlink()
        os.link(self.initial / 'index.html', p)
        with self.assertRaises(ValueError):
            self.manager.verify(self.initial.name)
        p.unlink()
        p.write_bytes(original)
        p.chmod(0o666)
        with self.assertRaises(ValueError):
            self.manager.verify(self.initial.name)

    def test_untrusted_uid_rejected(self):
        from types import SimpleNamespace
        s = self.initial.stat()
        values = list(s)
        values[4] = 1001
        with self.assertRaises(ValueError):
            release.trusted(SimpleNamespace(lstat=lambda: os.stat_result(values)), True)

    def test_release_tamper_and_gate(self):
        (self.initial / 'index.html').write_bytes(b'tampered')
        with self.assertRaises(ValueError):
            self.deploy()
        (self.initial / 'assets/js/public-config.js').write_text('window.__V5_PUBLIC_CONFIG__={"mode":"PROD","prod_api_url":""};')
        with self.assertRaises(ValueError):
            self.manager.gate(self.initial)

    def test_recover_interrupted_switch_before_and_after(self):
        self.deploy()
        self.manager.rollback()
        state = self.manager.recover()
        release.atomic_json(self.state / 'state.json', {**state, 'pending': [self.initial.name, 'smoke-test']})
        temp = self.base / '.test-current-next'
        temp.symlink_to(self.base / 'releases/smoke-test')
        self.assertEqual(self.manager.recover()['current'], self.initial.name)
        self.assertFalse(os.path.lexists(temp))
        release.atomic_json(self.state / 'state.json', {**state, 'pending': [self.initial.name, 'smoke-test']})
        temp.symlink_to(self.base / 'releases/smoke-test')
        os.replace(temp, self.base / 'current')
        result = self.manager.recover()
        self.assertEqual(result, {'current': 'smoke-test', 'previous': self.initial.name})

    def test_no_previous_rollback(self):
        with self.assertRaises(ValueError):
            self.manager.rollback()

    def test_size_count_and_disk_limits(self):
        with patch.object(release, 'MAX_INPUT', 1), self.assertRaises(ValueError):
            self.deploy()
        with patch.object(release, 'MAX_FILE', 1), self.assertRaises(ValueError):
            self.deploy({'about/index.html': b'large'})
        from types import SimpleNamespace
        with patch.object(release.shutil, 'disk_usage', return_value=SimpleNamespace(free=1)), self.assertRaises(ValueError):
            self.deploy()
        for i in range(19):
            (self.base / 'releases' / ('retained-' + str(i))).mkdir()
        with self.assertRaises(ValueError):
            self.deploy()
        self.assertEqual(self.manager.target(), self.initial.name)

    def test_exclusive_lock(self):
        with (self.state / 'lock').open('a') as first, (self.state / 'lock').open('a') as second:
            release.fcntl.flock(first, release.fcntl.LOCK_EX | release.fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                release.fcntl.flock(second, release.fcntl.LOCK_EX | release.fcntl.LOCK_NB)


if __name__ == '__main__':
    unittest.main()
