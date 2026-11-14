"""Install validated Time Stranger Importer model packages into a chosen mod.

The manifest is an integrity/ownership contract, not proof of game rendering.
This module never rewrites models, assigns IDs, edits tables, or replaces an
unmanaged file with different bytes. Backups live outside dsts-loader scanning.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import uuid
import csv
import io
import subprocess


FORMAT = 'dsts-native-model-package-v1'
RECEIPT = 'digits-installed-model-package-v1'


def ensure_game_closed():
    if os.name != 'nt':
        raise RuntimeError('Game-process checks are currently supported on Windows only')
    try:
        result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH', '/FI',
                                 'IMAGENAME eq Digimon Story Time Stranger.exe'],
                                capture_output=True, text=True, check=True,
                                creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f'Could not verify that Time Stranger is closed: {error}') from error
    if any(row and row[0].casefold() == 'digimon story time stranger.exe'
           for row in csv.reader(io.StringIO(result.stdout))):
        raise RuntimeError('Close Time Stranger before installing a reviewed asset package; loaded assets cannot be replaced')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _relative(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError(f'Invalid package path: {value!r}')
    parts = value.split('/')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(i) for i in range(1, 10)),
                *('LPT'+str(i) for i in range(1, 10))}
    if any(p in ('', '.', '..') or p.rstrip(' .') != p or
           any(ord(c) < 32 or c in ':*?"<>|' for c in p) or
           p.split('.')[0].upper() in reserved for p in parts):
        raise ValueError(f'Unsafe package path: {value!r}')
    path = PurePosixPath(value)
    if len(parts) == 1 and path.suffix.lower() in ('.geom', '.nlst', '.anim'):
        return value
    if len(parts) == 2 and ((parts[0] == 'images' and path.suffix.lower() == '.img') or
                            (parts[0] == 'shaders' and path.suffix.lower() == '.shad')):
        return value
    raise ValueError(f'Unsupported model package resource: {value}; effects, tables and audio need their own validated contract')


def _within(root, relative):
    result = root / relative
    if result.resolve() != result.absolute() or not result.resolve().is_relative_to(root):
        raise ValueError(f'Redirected package path: {result}')
    return result


def _index(value):
    if not isinstance(value, dict):
        raise ValueError('Package resource index must be an object')
    result, folded = {}, set()
    for name, metadata in value.items():
        _relative(name)
        if name.casefold() in folded:
            raise ValueError(f'Case-insensitive duplicate resource: {name}')
        folded.add(name.casefold())
        if (not isinstance(metadata, dict) or not isinstance(metadata.get('sha256'), str) or
                not re.fullmatch(r'[0-9a-f]{64}', metadata['sha256']) or
                type(metadata.get('bytes')) is not int or metadata['bytes'] < 0):
            raise ValueError(f'Invalid resource hash/size: {name}')
        result[name] = {'sha256': metadata['sha256'], 'bytes': metadata['bytes']}
    return result


def _matches(path, meta):
    return path.is_file() and path.stat().st_size == meta['bytes'] and _sha(path.read_bytes()) == meta['sha256']


def _atomic(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix='.digits-write-', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def plan_model_package(package, dsts_loader, expected_model, native_root=None):
    package, target = Path(package).resolve(), Path(dsts_loader).resolve()
    if target.name.lower() not in ('dsts-loader', 'dts-loader') or not target.is_dir():
        raise ValueError('Choose an existing mod dsts-loader folder')
    manifest = package / 'model-package.json'
    raw_manifest = manifest.read_bytes()
    report = json.loads(raw_manifest)
    if not isinstance(report, dict) or report.get('format') != FORMAT:
        raise ValueError('Select a native model package exported by Time Stranger Importer')
    model = report.get('model')
    if not isinstance(model, str) or model != expected_model:
        raise ValueError(f'Package model {model!r} does not match selected Chr ID {expected_model!r}; export with the chosen target ID first')
    _relative(model + '.geom')
    if '/' in model:
        raise ValueError('Model identity cannot contain a path')
    files = _index(report.get('files'))
    external = _index(report.get('external_native_dependencies', {}))
    required = {model + suffix for suffix in ('.geom', '.anim', '.nlst')}
    if not required <= files.keys():
        raise ValueError('Package lacks the matching GEOM, base ANIM or NLST')
    if {n.casefold() for n in files} & {n.casefold() for n in external}:
        raise ValueError('Resource is both packaged and external')
    patch = _within(package, 'dsts-loader/patch')
    actual = {p.relative_to(patch).as_posix() for p in patch.rglob('*') if p.is_file()}
    if actual != set(files):
        raise ValueError(f'Package inventory mismatch (missing: {sorted(set(files)-actual)}, extra: {sorted(actual-set(files))})')
    for name, metadata in files.items():
        if not _matches(_within(patch, name), metadata):
            raise ValueError(f'Package file changed or is corrupt: {name}')
    native = Path(native_root).resolve() if native_root else None
    for name, metadata in external.items():
        # A mod-local override wins over the native resource, including conflicts.
        override = _within(target / 'patch', name)
        candidate = override if override.exists() else _within(native, name) if native else None
        if candidate is None or not _matches(candidate, metadata):
            raise ValueError(f'External dependency missing or overridden with different bytes: {name}; choose the exact extracted resource folder')
    receipt_path = _within(target.parent, '.digits-asset-packages/' + model + '.json')
    receipt_raw = receipt_path.read_bytes() if receipt_path.exists() else None
    previous = {}
    if receipt_raw:
        receipt = json.loads(receipt_raw)
        if not isinstance(receipt, dict) or receipt.get('format') != RECEIPT or receipt.get('model') != model:
            raise ValueError('Existing ownership receipt is invalid')
        previous = _index(receipt.get('managed_files'))
    all_names = set(files) | set(previous)
    if len({name.casefold() for name in all_names}) != len(all_names):
        raise ValueError('Case-only resource renames require an explicit migration; keep the existing spelling')
    changes, removals, unchanged, preconditions, managed = [], [], [], {}, {}
    for name in sorted(set(files) | set(previous)):
        destination = _within(target / 'patch', name)
        if destination.exists() and not destination.is_file():
            raise ValueError(f'Destination is not a file: {destination}')
        before = destination.read_bytes() if destination.exists() else None
        preconditions[name] = _sha(before) if before is not None else None
        if name in previous and before is not None and not _matches(destination, previous[name]):
            raise ValueError(f'Previously installed resource was edited: {name}; preserve or export those changes before updating')
        if name not in files:
            if before is not None:
                removals.append(name)
            continue
        if before is not None and _sha(before) == files[name]['sha256']:
            unchanged.append(name)
            if name in previous:
                managed[name] = files[name]
        elif before is not None and name not in previous:
            raise ValueError(f'Unmanaged resource conflict: {name}; existing mod assets will not be overwritten')
        else:
            changes.append(name)
            managed[name] = files[name]
    # Shared shaders/textures can be referenced by another installed package.
    # Their receipt protects them even when it did not originally create them.
    for other_path in receipt_path.parent.glob('*.json'):
        if other_path == receipt_path:
            continue
        other = json.loads(_within(receipt_path.parent, other_path.name).read_bytes())
        if not isinstance(other, dict) or other.get('format') != RECEIPT:
            raise ValueError(f'Unknown ownership receipt: {other_path.name}')
        references = {name.casefold(): metadata for name, metadata in
                      _index(other.get('referenced_files', other.get('managed_files', {}))).items()}
        for name in changes + removals:
            if name.casefold() in references and (name not in files or files[name] != references[name.casefold()]):
                raise ValueError(f'{name} is also referenced by package {other.get("model")}; update that dependency explicitly first')
    return {'package': str(package), 'target': str(target), 'model': model,
            'manifest_sha256': _sha(raw_manifest), 'native_root': str(native) if native else None,
            'files': files, 'external': external, 'changes': changes, 'removals': removals,
            'unchanged': unchanged, 'preconditions': preconditions, 'managed_files': managed,
            'receipt_path': str(receipt_path), 'receipt_before': receipt_raw,
            'runtime_verified': False, 'limitations': report.get('limitations', [])}


def install_model_package(plan):
    """Revalidate a reviewed plan, install, and restore all modified files on error."""
    fresh = plan_model_package(plan['package'], plan['target'], plan['model'], plan['native_root'])
    if fresh != plan:
        raise ValueError('Package or destination changed after review; review a fresh plan')
    target = Path(plan['target'])
    backup = _within(target.parent, '.digits-asset-backups/' + uuid.uuid4().hex)
    backup.mkdir(parents=True)
    originals, completed = {}, []
    receipt_path = Path(plan['receipt_path'])
    try:
        # Persist backups before making any destination changes.
        for name in plan['changes'] + plan['removals']:
            destination = _within(target / 'patch', name)
            originals[name] = destination.read_bytes() if destination.exists() else None
            if originals[name] is not None:
                saved = backup / 'patch' / name
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_bytes(originals[name])
                if saved.read_bytes() != originals[name]:
                    raise OSError(f'Backup verification failed: {name}')
        if plan['receipt_before'] is not None:
            (backup / 'previous-receipt.json').write_bytes(plan['receipt_before'])
        (backup / 'transaction.json').write_text(json.dumps({
            'model': plan['model'], 'target': str(target), 'changes': plan['changes'],
            'removals': plan['removals'], 'manifest_sha256': plan['manifest_sha256'],
            'original_hashes': plan['preconditions']}, indent=2), encoding='utf-8')
        for name in plan['changes']:
            raw = _within(Path(plan['package']) / 'dsts-loader/patch', name).read_bytes()
            if _sha(raw) != plan['files'][name]['sha256']:
                raise ValueError(f'Package changed during installation: {name}')
            destination = _within(target / 'patch', name)
            current = _sha(destination.read_bytes()) if destination.exists() else None
            if current != plan['preconditions'][name]:
                raise ValueError(f'Destination changed during installation: {name}')
            _atomic(destination, raw)
            completed.append(name)
        for name in plan['removals']:
            destination = _within(target / 'patch', name)
            if _sha(destination.read_bytes()) != plan['preconditions'][name]:
                raise ValueError(f'Destination changed before removal: {name}')
            destination.unlink()
            completed.append(name)
        for name, metadata in plan['files'].items():
            if not _matches(_within(target / 'patch', name), metadata):
                raise OSError(f'Installed hash verification failed: {name}')
        receipt = {'format': RECEIPT, 'model': plan['model'],
                   'manifest_sha256': plan['manifest_sha256'], 'managed_files': plan['managed_files'],
                   'referenced_files': plan['files'],
                   'external_native_dependencies': plan['external'], 'backup': str(backup),
                   'runtime_verified': False}
        _atomic(receipt_path, (json.dumps(receipt, indent=2) + '\n').encode())
    except BaseException as error:
        failures = []
        for name in reversed(completed):
            destination = target / 'patch' / name
            try:
                if originals[name] is None:
                    destination.unlink(missing_ok=True)
                else:
                    _atomic(destination, originals[name])
            except OSError as rollback_error:
                failures.append(f'{name}: {rollback_error}')
        if failures:
            raise OSError(f'Install failed ({error}); rollback needs recovery from {backup}: {failures}') from error
        raise
    return {'model': plan['model'], 'written': len(plan['changes']),
            'removed': len(plan['removals']), 'unchanged': len(plan['unchanged']),
            'backup': str(backup), 'receipt': str(receipt_path), 'runtime_verified': False}
