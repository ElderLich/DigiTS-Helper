"""Inspect Field Guide slot claims in Reloaded II mods and change one verified CSV cell."""
import csv
import hashlib
import io
import json
import os
import re
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtCore import QLockFile


CUSTOM_MIN, CUSTOM_MAX = 500, 999
_STATUS_FOLDER = re.compile(r"digimon_status(?:_dlc\d+)?\.mbe", re.I)
_STATUS_CSV = re.compile(r"(?:\d+_)?digimon_status_data(?:\.ap)?\.csv", re.I)
_NAMES_CSV = re.compile(r"(?:\d+_)?Sheet1(?:\.ap)?\.csv", re.I)
_ARCHIVE = re.compile(r"(?:app_\d+|patch|addcont_\d+)(?:\.dx11)?", re.I)
_TEXT_ARCHIVE = re.compile(r"(?:app(?:_\d+)?|patch|addcont_\d+)_text01(?:\.dx11)?", re.I)
_FIELD = re.compile(r'(?:"(?:[^"]|"")*"|[^,\r\n]*)(?=,|\r|\n|\Z)')


@dataclass(frozen=True)
class Entry:
    source: str
    mod: Path | None = None
    payload: Path | None = None
    table: Path | None = None
    record: int = 0        # Logical CSV record index, including the header at index zero.
    digimon_id: int | None = None
    key: str = ""
    chr_id: str = ""
    name: str = ""
    slot: int | None = None
    digest: str = ""
    editable: bool = False
    note: str = ""


@dataclass
class Inventory:
    root: Path
    entries: list = field(default_factory=list)
    mods: dict = field(default_factory=dict)   # Folder -> (Reloaded mod ID, version)
    warnings: list = field(default_factory=list)
    slots: dict = field(default_factory=lambda: defaultdict(list))
    ids: dict = field(default_factory=lambda: defaultdict(list))

    def add(self, entry):
        self.entries.append(entry)
        if entry.slot is not None and entry.slot >= 0:
            self.slots[entry.slot].append(entry)
        if entry.digimon_id is not None:
            self.ids[entry.digimon_id].append(entry)

    def state(self, entry):
        if entry.digimon_id is None:
            return entry.note or "No status rows"
        peers = self.slots.get(entry.slot, [])
        if len(peers) > 1:
            stock = {(p.digimon_id, p.key, p.chr_id) for p in peers if p.mod is None}
            mods = {(p.digimon_id, p.key, p.chr_id) for p in peers if p.mod is not None}
            if not mods:
                return "Shared stock slot"
            if (stock and not mods.issubset(stock)) or (not stock and len(mods) > 1):
                return "Slot conflict"
        if any(peer.slot != entry.slot for peer in self.ids[entry.digimon_id]):
            return "ID overlap"
        if len(peers) > 1:
            return "Shared entry"
        if entry.slot is None or entry.slot < 0:
            return "Unassigned"
        return "Assigned"


def _csv_rows(raw):
    return list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True))


def _read_names(files, names, warnings):
    for path in files:
        if not path.is_file():
            continue
        try:
            for row in _csv_rows(path.read_bytes())[1:]:
                if len(row) >= 2 and row[0] and row[1]:
                    names[row[0]] = row[1]
        except (ValueError, csv.Error, OSError) as exc:
            warnings.append(f"{path}: {exc}")


def _redirected(path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _within(root, path):
    """Never edit a status table through a redirected mod or archive folder."""
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    current = root
    for part in parts:
        current /= part
        if _redirected(current):
            return False
    return path.resolve().is_relative_to(root.resolve())


def _status(inventory, source, table, names, mod=None, payload=None):
    try:
        raw = table.read_bytes()
        rows = _csv_rows(raw)
        headings = tuple(rows[0][i].strip().lower() for i in (0, 2, 3, 131, 132)) if rows and len(rows[0]) > 132 else ()
        typed = ("int32 0", "string2 2", "string2 3", "int32 131", "int32 132")
        friendly = ("id", "char_key", "chr_id", "field_guide_id", "script_id")
        if headings not in (typed, friendly):
            raise ValueError("Unrecognized Digimon status header")
        digest = hashlib.sha256(raw).hexdigest()
        can_edit = mod is not None and table.name.lower().endswith(".ap.csv") and headings == typed
        note = "" if can_edit else ("Base / DLC reference" if mod is None else "Read-only status table")
        for index, cells in enumerate(rows[1:], 1):
            if not any(cell.strip() for cell in cells):
                continue
            try:
                identifier = int(cells[0])
                if len(cells) != len(rows[0]):
                    raise ValueError("Row width differs from header")
                slot = int(cells[131]) if cells[131].strip() else None
            except (IndexError, ValueError) as exc:
                inventory.warnings.append(f"{table}, record {index + 1}: {exc}")
                continue
            key = cells[2].strip()
            inventory.add(Entry(source, mod, payload, table, index, identifier, key, cells[3].strip(),
                                names.get(key, key), slot, digest, can_edit, note))
    except (ValueError, csv.Error, OSError) as exc:
        inventory.warnings.append(f"{table}: {exc}")
        inventory.add(Entry(source, mod, payload, table, note="Unreadable status table"))


def _stock(inventory, loader):
    names = {}
    if loader is None:
        inventory.warnings.append("Base and DLC data were not loaded.")
        return names
    native = loader._resolve_prefixed_file
    name_files = [native(loader.text_path / "char_name.mbe" / "000_Sheet1.csv")]
    name_files += [path for _, path in loader.iter_dlc_csv_files("text", "char_name", "000_Sheet1.csv")]
    _read_names(name_files, names, inventory.warnings)
    base = native(loader.data_path / "digimon_status.mbe" / "000_digimon_status_data.csv")
    _status(inventory, "Base game", base, names)
    for dlc, path in loader.iter_dlc_csv_files("data", "digimon_status", "000_digimon_status_data.csv"):
        _status(inventory, f"DLC {dlc}", path, names)
    return names


def _mod_tables(inventory, mod, source, stock_names):
    for payload in (mod / "dsts-loader", mod / "dts-loader"):
        if not payload.is_dir():
            continue
        if not _within(inventory.root, payload):
            inventory.add(Entry(source, mod, payload, note="Redirected loader folder"))
            continue
        tables = []
        name_files = []
        for archive in sorted(payload.iterdir()):
            if _ARCHIVE.fullmatch(archive.name):
                for table in sorted((archive / "data").glob("digimon_status*.mbe")):
                    if not _STATUS_FOLDER.fullmatch(table.name):
                        continue
                    if not _within(inventory.root, table):
                        inventory.add(Entry(source, mod, payload, table, note="Redirected status table"))
                        continue
                    if table.is_file():
                        inventory.add(Entry(source, mod, payload, table, note="Packed status table"))
                        continue
                    for sheet in sorted(table.iterdir()):
                        if not sheet.is_file():
                            continue
                        if _STATUS_CSV.fullmatch(sheet.name):
                            tables.append(sheet)
                        elif "digimon_status_data" in sheet.name.casefold() and sheet.suffix.lower() == ".csv":
                            inventory.add(Entry(source, mod, payload, sheet, note="Unsupported status patch"))
            elif _TEXT_ARCHIVE.fullmatch(archive.name):
                for path in sorted((archive / "text").glob("char_name*.mbe/*.csv")):
                    if _NAMES_CSV.fullmatch(path.name) and _within(inventory.root, path):
                        name_files.append(path)
        names = stock_names.copy()
        _read_names(name_files, names, inventory.warnings)
        for table in tables:
            if _within(inventory.root, table):
                _status(inventory, source, table, names, mod, payload)
            else:
                inventory.add(Entry(source, mod, payload, table, note="Redirected status table"))


def scan_inventory(mods_root, loader=None):
    root = Path(mods_root).resolve()
    if not root.is_dir():
        raise ValueError(f"Reloaded II Mods folder does not exist: {root}")
    result = Inventory(root)
    stock_names = _stock(result, loader)
    for mod in sorted(root.iterdir(), key=lambda p: p.name.casefold()):
        if not mod.is_dir():
            continue
        config = mod / "ModConfig.json"
        if not (config.is_file() or (mod / "dsts-loader").is_dir() or (mod / "dts-loader").is_dir()):
            continue
        result.mods[mod] = ("", "")
        source = mod.name
        previous = len(result.entries)
        try:
            if config.is_file():
                try:
                    settings = json.loads(config.read_text("utf-8-sig"))
                    source = str(settings.get("ModName") or mod.name)
                    result.mods[mod] = (str(settings.get("ModId") or ""), str(settings.get("ModVersion") or ""))
                except (OSError, ValueError, AttributeError) as exc:
                    result.warnings.append(f"{config}: {exc}")
            if _redirected(mod):
                result.add(Entry(source, mod, note="Redirected mod folder"))
            else:
                _mod_tables(result, mod, source, stock_names)
        except OSError as exc:
            result.warnings.append(f"{mod}: {exc}")
            result.add(Entry(source, mod, note="Unreadable mod folder"))
        if len(result.entries) == previous:
            result.add(Entry(source, mod, note="No status rows"))
        for entry in result.entries[previous:]:
            if entry.note.startswith(("Packed", "Unsupported", "Redirected")):
                result.warnings.append(f"{entry.table or entry.payload or mod}: {entry.note}")
    return result


@dataclass(frozen=True)
class SlotChange:
    table: Path
    mod: Path
    payload: Path
    digimon_id: int
    old_slot: int | None
    new_slot: int
    backup: Path


def _replace_cell(raw, index, slot):
    """Find the selected CSV field, retaining BOM, quotes, line endings and all other bytes."""
    text = raw.decode("utf-8-sig")
    lines = io.StringIO(text, newline="").readlines()
    reader = csv.reader(lines, strict=True)
    first_line = 0
    for i, row in enumerate(reader):
        if i == index:
            break
        first_line = reader.line_num
    else:
        raise ValueError("Selected record no longer exists")
    record = "".join(lines[first_line:reader.line_num])
    offset = 0
    for column in range(132):
        cell = _FIELD.match(record, offset)
        if cell is None:
            raise ValueError("Unsupported CSV quoting in selected record")
        if column == 131:
            value = f'"{slot}"' if cell.group().startswith('"') else str(slot)
            changed = record[:offset] + value + record[cell.end():]
            break
        if record[cell.end():cell.end() + 1] != ",":
            raise ValueError("Incomplete status record")
        offset = cell.end() + 1
    expected = row.copy()
    expected[131] = str(slot)
    if list(csv.reader(io.StringIO(changed, newline=""), strict=True)) != [expected]:
        raise ValueError("The updated status record could not be verified")
    lines[first_line:reader.line_num] = [changed]
    return "".join(lines).encode("utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8")


def change_slot(mods_root, loader, entry, new_slot):
    if type(new_slot) is not int or not CUSTOM_MIN <= new_slot <= CUSTOM_MAX:
        raise ValueError(f"Choose a custom Field Guide slot from {CUSTOM_MIN} to {CUSTOM_MAX}.")
    if not entry.editable or entry.record < 1:
        raise ValueError("Select an editable installed mod status row.")
    if new_slot == entry.slot:
        raise ValueError("Choose a different Field Guide slot.")
    # Two editor windows may pick the same free slot for different mods.
    # Hold a per-inventory lock through the re-scan and atomic replacement.
    root_key = os.path.normcase(str(Path(mods_root).resolve())).encode("utf-8")
    lock_name = "time-stranger-guide-" + hashlib.sha256(root_key).hexdigest() + ".lock"
    lock = QLockFile(str(Path(tempfile.gettempdir()) / lock_name))
    if not lock.tryLock(0):
        raise ValueError("Another Field Guide change is in progress. Try saving again.")
    try:
        return _save_slot(mods_root, loader, entry, new_slot)
    finally:
        lock.unlock()


def _save_slot(mods_root, loader, entry, new_slot):
    current = scan_inventory(mods_root, loader)
    if entry not in current.entries or not _within(current.root, entry.table):
        raise ValueError("The selected status row changed. Refresh and select it again.")
    if current.slots.get(new_slot):
        raise ValueError(f"Slot {new_slot} is already used by " +
                         ", ".join(e.source for e in current.slots[new_slot]))
    raw = entry.table.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry.digest:
        raise ValueError("The source table changed. Refresh before editing.")
    after = _replace_cell(raw, entry.record, new_slot)
    folder = entry.mod / "Time Stranger Mod Studio Backups" / "Field Guide"
    if not _within(current.root, folder):
        raise ValueError("The backup folder is redirected.")
    folder.mkdir(parents=True, exist_ok=True)
    backup = folder / (entry.table.name + "." + entry.digest + ".bak")
    try:
        stream = backup.open("xb")
    except FileExistsError:
        pass
    else:
        try:
            with stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            backup.unlink(missing_ok=True)
            raise
    if not _within(current.root, backup) or backup.read_bytes() != raw:
        raise ValueError("Could not verify the original status-table backup.")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=entry.table.parent, prefix=".guide-", suffix=".tmp", delete=False) as stream:
            temp = Path(stream.name)
            stream.write(after)
            stream.flush()
            os.fsync(stream.fileno())
        if temp.read_bytes() != after or entry.table.read_bytes() != raw:
            raise ValueError("The file changed while preparing the edit. Refresh before editing.")
        os.replace(temp, entry.table)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return SlotChange(entry.table, entry.mod, entry.payload, entry.digimon_id, entry.slot, new_slot, backup)
