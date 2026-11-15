"""Unlock the native Digipedia list in a version 5 PC save slot."""
import ctypes
import hashlib
import os
import re
import struct
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QLockFile, Qt
from PyQt6.QtWidgets import QFileDialog, QMessageBox


HEADER_SIZE = 0x400
PAYLOAD_SIZE = 0x2F4240
SAVE_SIZE = HEADER_SIZE + PAYLOAD_SIZE
# The PC serializer at 0x140D27325 and loader at 0x140D2A149 transfer
# 1,000 keyed 16-byte records plus one auxiliary 16-bit word per record.
GUIDE_OFFSET = HEADER_SIZE + 0x5CEA8
AUX_OFFSET = HEADER_SIZE + 0x2F2240
CAPACITY = 1000
RECORD_SIZE = 16
# UIDigipedia at 0x140813655 includes a species when bit 2 of field +4 is set.
REGISTERED = 0x04
_HEADER = re.compile(rb"5,\s*3097152,\s*176,")


def _aes(data, *, encrypt):
    """Time Stranger's PC format uses AES-128 ECB without padding."""
    if os.name != "nt":
        raise OSError("Editing Time Stranger PC saves requires Windows.")
    from ctypes import byref, c_uint32, c_void_p, c_wchar_p
    bcrypt = ctypes.WinDLL("bcrypt")

    def call(name, types, *args):
        function = getattr(bcrypt, name)
        function.argtypes = types
        function.restype = ctypes.c_int32
        status = function(*args)
        if status != 0:
            raise OSError(f"Windows AES failed at {name} (0x{status & 0xffffffff:08x}).")

    algorithm = c_void_p()
    key = c_void_p()
    output = ctypes.create_string_buffer(len(data))
    written = c_uint32()
    p, u = c_void_p, c_uint32
    call("BCryptOpenAlgorithmProvider", [p, c_wchar_p, c_wchar_p, u],
         byref(algorithm), "AES", None, 0)
    try:
        mode = ctypes.create_unicode_buffer("ChainingModeECB")
        call("BCryptSetProperty", [p, c_wchar_p, p, u, u],
             algorithm, "ChainingMode", mode, ctypes.sizeof(mode), 0)
        # The game's fixed on-disk format key (DSTS-Save-Editor, save_crypto.py).
        call("BCryptGenerateSymmetricKey", [p, p, p, u, p, u, u],
             algorithm, byref(key), None, 0, b"3962776754555883", 16, 0)
        try:
            call("BCryptEncrypt" if encrypt else "BCryptDecrypt",
                 [p, p, u, p, p, u, p, u, p, u],
                 key, data, len(data), None, None, 0, output, len(data), byref(written), 0)
            if written.value != len(data):
                raise OSError("Windows AES returned an incomplete save.")
            return output.raw
        finally:
            call("BCryptDestroyKey", [p], key)
    finally:
        call("BCryptCloseAlgorithmProvider", [p, u], algorithm, 0)


@dataclass(frozen=True)
class UnlockPlan:
    path: Path
    digest: bytes
    ids: tuple
    existing: int
    updated: int
    added: int


def _prepare(ciphertext, ids):
    if len(ciphertext) != SAVE_SIZE:
        raise ValueError("Select a Time Stranger PC savedata slot (3,098,176 bytes).")
    plain = bytearray(_aes(ciphertext, encrypt=False))
    if not _HEADER.match(plain) or 0 not in plain[:HEADER_SIZE]:
        raise ValueError("The selected file does not have a supported version 5 PC save header.")
    if not ids or any(type(i) is not int or not 0 < i <= 0x7fffffff for i in ids):
        raise ValueError("A catalogue of positive Digimon status IDs is required.")

    records, free = {}, []
    for index in range(CAPACITY):
        start = GUIDE_OFFSET + index * RECORD_SIZE
        identifier, = struct.unpack_from("<i", plain, start)
        if identifier == 0:
            aux = AUX_OFFSET + index * 2
            if any(plain[start:start + RECORD_SIZE]) or any(plain[aux:aux + 2]):
                raise ValueError("An empty Field Guide record contains unexpected data.")
            free.append(start)
        elif identifier < 0 or identifier in records:
            raise ValueError("The save contains an invalid or repeated Field Guide species ID.")
        else:
            records[identifier] = start
    if not records:
        raise ValueError("The save contains no native Field Guide species records.")

    missing = sorted(set(ids).difference(records))
    if len(missing) > len(free):
        raise ValueError(f"The catalogue needs {len(missing)} more species records. "
                         f"This save has {len(free)} free records out of {CAPACITY}.")
    updated = 0
    for identifier in ids:
        if identifier in records:
            offset = records[identifier] + 4
            if not plain[offset] & REGISTERED:
                plain[offset] |= REGISTERED
                updated += 1
    # The native loader consumes every record by status ID. Fill previously empty
    # positions so existing records retain their parallel auxiliary words.
    for identifier, start in zip(missing, free):
        struct.pack_into("<iB", plain, start, identifier, REGISTERED)
    return bytes(plain), updated, len(missing)


def preview_unlock(path, digimon_ids):
    path = Path(path).resolve(strict=True)
    if path.stat().st_size != SAVE_SIZE:
        raise ValueError("Select a Time Stranger PC savedata slot (3,098,176 bytes).")
    raw = path.read_bytes()
    ids = tuple(sorted(set(digimon_ids)))
    _, updated, added = _prepare(raw, ids)
    return UnlockPlan(path, hashlib.sha256(raw).digest(), ids,
                      len(ids) - updated - added, updated, added)


def apply_unlock(plan):
    """Back up the exact previewed file, verify the candidate and replace atomically."""
    path = plan.path
    lock = QLockFile(str(path) + ".tsms-guide.lock")
    if not lock.tryLock(0):
        raise OSError("Time Stranger Mod Studio could not lock this save for editing.")
    temporary = None
    try:
        original = path.read_bytes()
        if hashlib.sha256(original).digest() != plan.digest:
            raise ValueError("This save changed after the preview. Select it again.")
        plain, updated, added = _prepare(original, plan.ids)
        if not (updated or added):
            return None
        result = _aes(plain, encrypt=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".",
                                         suffix=".tmp", delete=False) as file:
            temporary = Path(file.name)
            file.write(result)
            file.flush()
            os.fsync(file.fileno())
        if _aes(temporary.read_bytes(), encrypt=False) != plain:
            raise OSError("Could not verify the encrypted save before replacement.")
        backup_prefix = f"{path.name}.pre-guide-{datetime.now():%Y%m%d-%H%M%S}-"
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=backup_prefix,
                                         suffix=".bak", delete=False) as file:
            backup = Path(file.name)
            file.write(original)
            file.flush()
            os.fsync(file.fileno())
        if backup.read_bytes() != original:
            raise OSError(f"Could not verify the backup at {backup}.")
        if path.read_bytes() != original:
            raise ValueError("This save changed during the edit. Select it again.")
        os.replace(temporary, path)
        return backup
    finally:
        try:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        finally:
            lock.unlock()


def _steam_client_paths():
    if os.name == "nt":
        import winreg

        for hive, value, view in (
            (winreg.HKEY_CURRENT_USER, "SteamPath", 0),
            (winreg.HKEY_LOCAL_MACHINE, "InstallPath", winreg.KEY_WOW64_32KEY),
            (winreg.HKEY_LOCAL_MACHINE, "InstallPath", winreg.KEY_WOW64_64KEY),
        ):
            try:
                with winreg.OpenKey(hive, r"Software\Valve\Steam", 0, winreg.KEY_READ | view) as key:
                    folder, _ = winreg.QueryValueEx(key, value)
                    if folder:
                        yield Path(folder)
            except OSError:
                continue
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        if folder := os.environ.get(variable):
            yield Path(folder) / "Steam"


def _steam_metadata(path):
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return ""


def find_steam_save_directory():
    """Locate the installed game's savedata folder across the user's Steam libraries."""
    libraries = []
    for client in dict.fromkeys(_steam_client_paths()):
        libraries.append(client)
        metadata = _steam_metadata(client / "steamapps" / "libraryfolders.vdf")
        # Modern entries use "path". Older Steam clients keyed library paths by number.
        for value in re.findall(r'^\s*"(?:path|\d+)"\s*"([^"\r\n]+)"', metadata, re.MULTILINE):
            library = Path(value.replace("\\\\", "\\"))
            if library.is_absolute():
                libraries.append(library)

    fallback = None
    for library in dict.fromkeys(libraries):
        steamapps = library / "steamapps"
        common = steamapps / "common"
        manifest = _steam_metadata(steamapps / "appmanifest_1984270.acf")
        install = re.search(r'^\s*"installdir"\s*"([^"\r\n]+)"', manifest, re.MULTILINE)
        if install:
            folder = install.group(1)
            if folder not in (".", "..") and Path(folder).name == folder:
                saves = common / folder / "gamedata" / "savedata"
                if saves.is_dir():
                    return saves
        standard = common / "Digimon Story Time Stranger" / "gamedata" / "savedata"
        if fallback is None and standard.is_dir():
            fallback = standard
    return fallback


def open_field_guide_unlock(parent, digimon_ids, *, inventory_warnings=()):
    directory = find_steam_save_directory()
    chosen, _ = QFileDialog.getOpenFileName(
        parent, "Choose a save slot (autosave is 0000.bin or savedata00.dat)",
        str(directory) if directory else "",
        "Time Stranger slots (????.bin savedata*.dat);;Autosave only (0000.bin savedata00.dat);;All files (*)")
    if not chosen:
        return
    try:
        plan = preview_unlock(chosen, digimon_ids)
        title = "Unlock Field Guide"
        box = QMessageBox(parent)
        box.setWindowTitle(title)
        box.setTextFormat(Qt.TextFormat.PlainText)
        label = "Autosave" if plan.path.name.casefold() in {"0000.bin", "savedata00.dat"} else "Save slot"
        box.setText(f"{label} · {plan.path.name} · {len(plan.ids)} catalogued species")
        message = (f"Already registered: {plan.existing}\n"
                   f"Register existing records: {plan.updated}\n"
                   f"Add records for newly catalogued species: {plan.added}")
        if inventory_warnings:
            message += "\n\nSome catalogue sources could not be read. See details."
            box.setDetailedText("\n".join(map(str, inventory_warnings)))
        if plan.updated or plan.added:
            message += ("\n\nClose Time Stranger before applying. Time Stranger Mod Studio will "
                        "back up this slot and register the species in its Field Guide. "
                        "A modded species appears when the game loads its mod.")
            box.setStandardButtons(QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        else:
            box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setInformativeText(message)
        if box.exec() == QMessageBox.StandardButton.Apply:
            backup = apply_unlock(plan)
            if backup is not None:
                QMessageBox.information(parent, title, f"Registered {plan.updated + plan.added} species.\n\n"
                                        f"Original save backup:\n{backup}\n\n"
                                        f"To restore, close the game and copy this backup over {plan.path.name}.")
    except (ValueError, OSError) as exc:
        QMessageBox.warning(parent, "Field Guide", str(exc))
