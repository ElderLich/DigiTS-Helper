"""Package transactions use temporary mods only, including injected failures."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import Asset_Packages as assets


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / 'mod/dsts-loader'
        self.target.mkdir(parents=True)
        self.package = self.root / 'package'
        self.model = 'chr99123'
        self.files = {self.model + '.geom': b'fixture geom', self.model + '.anim': b'fixture anim',
                      self.model + '.nlst': b'fixture nlst', 'images/shared.img': b'fixture texture'}
        self.build()

    def build(self, external=None):
        folder = self.package / 'dsts-loader/patch'
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.rglob('*'):
            if old.is_file():
                old.unlink()
        index = {}
        for name, raw in self.files.items():
            destination = folder / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            index[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
        self.manifest = {'format': assets.FORMAT, 'model': self.model, 'files': index,
                         'external_native_dependencies': external or {}}
        self.save_manifest()

    def save_manifest(self):
        (self.package / 'model-package.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def plan(self, native=None):
        return assets.plan_model_package(self.package, self.target, self.model, native)

    def test_install_update_removal_and_unrelated_preservation(self):
        unrelated = self.target / 'patch/unrelated.geom'
        unrelated.parent.mkdir()
        unrelated.write_bytes(b'other mod data')
        first = assets.install_model_package(self.plan())
        self.assertEqual(first['written'], 4)
        self.files[self.model + '.geom'] = b'edited geometry'
        del self.files['images/shared.img']
        self.build()
        plan = self.plan()
        self.assertEqual(plan['removals'], ['images/shared.img'])
        result = assets.install_model_package(plan)
        self.assertEqual(result['written'], 1)
        self.assertEqual((Path(result['backup']) / 'patch' / (self.model + '.geom')).read_bytes(), b'fixture geom')
        self.assertFalse((self.target / 'patch/images/shared.img').exists())
        self.assertEqual(unrelated.read_bytes(), b'other mod data')
        self.assertEqual(assets.install_model_package(self.plan())['written'], 0)

    def test_rejects_unmanaged_conflict_and_preserves_existing(self):
        path = self.target / 'patch' / (self.model + '.geom')
        path.parent.mkdir()
        path.write_bytes(b'user work')
        with self.assertRaisesRegex(ValueError, 'Unmanaged'):
            self.plan()
        self.assertEqual(path.read_bytes(), b'user work')

    def test_identical_unmanaged_file_is_never_claimed_or_removed(self):
        path = self.target / 'patch/images/shared.img'
        path.parent.mkdir(parents=True)
        path.write_bytes(self.files['images/shared.img'])
        assets.install_model_package(self.plan())
        del self.files['images/shared.img']
        self.build()
        assets.install_model_package(self.plan())
        self.assertEqual(path.read_bytes(), b'fixture texture')

    def test_stale_review_and_edited_managed_file_rejected(self):
        plan = self.plan()
        self.files[self.model + '.geom'] = b'changed after review'
        self.build()
        with self.assertRaisesRegex(ValueError, 'changed after review'):
            assets.install_model_package(plan)
        self.assertFalse((self.target / 'patch').exists())
        assets.install_model_package(self.plan())
        (self.target / 'patch' / (self.model + '.geom')).write_bytes(b'user edit')
        with self.assertRaisesRegex(ValueError, 'was edited'):
            self.plan()

    def test_failure_after_first_write_rolls_back_and_keeps_receipt(self):
        assets.install_model_package(self.plan())
        receipt = self.target.parent / '.digits-asset-packages' / (self.model + '.json')
        before = receipt.read_bytes()
        self.files[self.model + '.anim'] = b'new animation'
        self.files[self.model + '.geom'] = b'new geometry'
        self.build()
        real_atomic = assets._atomic
        calls = 0
        def fail_second(path, raw):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise PermissionError('injected locked file')
            return real_atomic(path, raw)
        with patch.object(assets, '_atomic', side_effect=fail_second):
            with self.assertRaises(PermissionError):
                assets.install_model_package(self.plan())
        self.assertEqual((self.target / 'patch' / (self.model + '.anim')).read_bytes(), b'fixture anim')
        self.assertEqual((self.target / 'patch' / (self.model + '.geom')).read_bytes(), b'fixture geom')
        self.assertEqual(receipt.read_bytes(), before)

    def test_bad_paths_hashes_extra_files_and_wrong_identity_rejected(self):
        for name in ('../escape.geom', 'C:/escape.geom', 'images/CON.img', 'data/battle_skill.csv',
                     'images/trailing.img ', '/absolute.geom'):
            with self.subTest(name=name):
                self.build()
                self.manifest['files'][name] = next(iter(self.manifest['files'].values()))
                self.save_manifest()
                with self.assertRaises(ValueError):
                    self.plan()
        self.build()
        with self.assertRaisesRegex(ValueError, 'does not match'):
            assets.plan_model_package(self.package, self.target, 'chr11111')
        (self.package / 'dsts-loader/patch/extra.anim').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'inventory mismatch'):
            self.plan()
        self.build()
        (self.package / 'dsts-loader/patch' / (self.model + '.geom')).write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'changed or is corrupt'):
            self.plan()

    def test_external_dependencies_and_local_override_precedence(self):
        raw = b'exact shader'
        external = {'shaders/shared_vp.shad': {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}}
        self.build(external)
        with self.assertRaisesRegex(ValueError, 'External dependency'):
            self.plan()
        native = self.root / 'native'
        (native / 'shaders').mkdir(parents=True)
        (native / 'shaders/shared_vp.shad').write_bytes(raw)
        assets.install_model_package(self.plan(native))
        override = self.target / 'patch/shaders/shared_vp.shad'
        override.parent.mkdir(parents=True)
        override.write_bytes(b'conflicting override')
        with self.assertRaisesRegex(ValueError, 'External dependency'):
            self.plan(native)

    def test_shared_package_reference_blocks_dependency_removal(self):
        assets.install_model_package(self.plan())
        other = self.target.parent / '.digits-asset-packages/chr99124.json'
        meta = self.manifest['files']['images/shared.img']
        other.write_text(json.dumps({'format': assets.RECEIPT, 'model': 'chr99124',
            'managed_files': {}, 'referenced_files': {'images/shared.img': meta}}))
        del self.files['images/shared.img']
        self.build()
        with self.assertRaisesRegex(ValueError, 'also referenced'):
            self.plan()

    def test_case_only_update_cannot_remove_replacement(self):
        assets.install_model_package(self.plan())
        self.files['images/SHARED.img'] = self.files.pop('images/shared.img')
        self.build()
        with self.assertRaisesRegex(ValueError, 'Case-only'):
            self.plan()

    def test_external_reference_from_other_package_protects_managed_file(self):
        assets.install_model_package(self.plan())
        other = self.target.parent / '.digits-asset-packages/chr99124.json'
        meta = self.manifest['files']['images/shared.img']
        other.write_text(json.dumps({'format': assets.RECEIPT, 'model': 'chr99124',
            'managed_files': {}, 'referenced_files': {},
            'external_native_dependencies': {'images/shared.img': meta}}))
        self.files['images/shared.img'] = b'changed shared shader'
        self.build()
        with self.assertRaisesRegex(ValueError, 'also referenced'):
            self.plan()
        del self.files['images/shared.img']
        self.build()
        with self.assertRaisesRegex(ValueError, 'also referenced'):
            self.plan()


if __name__ == '__main__':
    unittest.main()
