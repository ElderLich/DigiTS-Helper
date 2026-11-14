"""Run with Blender --background --python ... -- --importer ... --fixture ...

Exercises the actual Importer -> package -> Helper -> isolated mod handoff.
Needs local extracted assets; no game files are modified or published.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

import bpy

parser = argparse.ArgumentParser()
parser.add_argument('--importer', type=Path, required=True)
parser.add_argument('--fixture', type=Path, required=True)
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
root = args.importer.resolve()
spec = importlib.util.spec_from_file_location('Time_Stranger_Importer', root / '__init__.py',
                                             submodule_search_locations=[str(root)])
addon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = addon
spec.loader.exec_module(addon)
addon.register()
from Time_Stranger_Importer.src.model_package import package_native_model
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Asset_Packages import plan_model_package, install_model_package

fixture = args.fixture.resolve()
with tempfile.TemporaryDirectory(prefix='digits-real-package-') as temporary:
    temp = Path(temporary)
    source = temp / 'source'
    source.mkdir()
    for suffix in ('.geom', '.anim', '.nlst'):
        shutil.copyfile(fixture.with_suffix(suffix), source / (fixture.stem + suffix))
    package = temp / 'package'
    exported = package_native_model(source / fixture.name, package, fixture.parent, False)
    target = temp / 'mod/dsts-loader'
    target.mkdir(parents=True)
    plan = plan_model_package(package, target, fixture.stem, fixture.parent)
    result = install_model_package(plan)
    for name, meta in exported['files'].items():
        assert hashlib.sha256((target / 'patch' / name).read_bytes()).hexdigest() == meta['sha256']
    repeated = install_model_package(plan_model_package(package, target, fixture.stem, fixture.parent))
    assert repeated['written'] == 0 and repeated['removed'] == 0
    evidence = {'blender': bpy.app.version_string, 'fixture': str(fixture),
                'fixture_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(),
                'packaged_files': len(exported['files']),
                'verified_external_dependencies': len(exported['external_native_dependencies']),
                'installed_hashes_match': True, 'repeat_writes': repeated['written'],
                'live_mod_changed': False, 'runtime_verified': False}
args.report.parent.mkdir(parents=True, exist_ok=True)
args.report.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
addon.unregister()
print('IMPORTER TO HELPER PACKAGE HANDOFF PASS', json.dumps(evidence))
