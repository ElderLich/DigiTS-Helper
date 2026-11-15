"""Read and author native skill rows in a dsts-loader payload."""
import csv
import io
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QIODevice, QLockFile, QSaveFile

from Mod_Tables import SKILL_HEADER, validate_typed_row


MAX_SKILL_ID = 2**31 - 1  # Native battle_skill_list key type.
ATTACK_ID = 10011
TEXT_HEADER = ["string2 0", "string 1"]
TEXT_KEYS = ["key", "text"]
BATTLE = "battle_skill"
NAME = "skill_name"
DESCRIPTION = "skill_explanation"
# These two native tables use the battle skill ID as their primary key.
BOUND_SHEETS = {
    "battle_skill_offset_pos": ("006", ["int32 0", "empty 1", "float 2", "float 3", "float 4"]),
    "battle_skill_voice_number": ("007", ["int32 0", "empty 1", "int32 2", "empty 3"]),
}


def _layout(table):
    if table in BOUND_SHEETS:
        prefix, header = BOUND_SHEETS[table]
        return BATTLE, table, prefix, header
    if table == BATTLE:
        return BATTLE, "battle_skill_list", "000", SKILL_HEADER
    return table, "Sheet1", "000", TEXT_HEADER


@dataclass(frozen=True)
class SkillRecord:
    skill_id: int
    name: str
    description: str
    row: tuple[str, ...]
    source: str
    source_file: Path | None = None
    bound_rows: tuple[tuple[str, tuple[str, ...]], ...] = ()


def _sheet(directory, stem, append=False, prefix="000"):
    """Use the canonical 000_ prefix first, including in older two-digit extracts."""
    suffix = ".ap.csv" if append else ".csv"
    filename = stem + suffix
    path = directory / (prefix + "_" + filename)
    if path.is_file():
        return path
    for other in sorted(directory.glob("*" + filename)):
        if re.fullmatch(r"(?:\d+_)?" + re.escape(filename), other.name, re.I):
            return other
    return path


def _sheets(root, table, dlc=None):
    name, stem, prefix, _ = _layout(table)
    directory = root / ((name + "_dlc" + dlc if dlc else name) + ".mbe")
    return [p for append in (False, True) if (p := _sheet(directory, stem, append, prefix)).is_file()]


def _mod_layers(payload):
    if not payload.is_dir():
        return
    # A patch in the same mod takes precedence over the app archive.
    for folder in sorted(payload.iterdir(), key=lambda p: (p.name.startswith("patch"), p.name)):
        archive = folder.name.removesuffix(".dx11")
        if archive in ("app_0", "patch", "app_text01", "patch_text01"):
            dlc = None
        else:
            match = re.fullmatch(r"addcont_(\d+)(?:_text01)?", archive)
            if not match:
                continue
            dlc = match[1]
        english = archive.endswith("_text01")
        kind = "text" if english else "data"
        for root in (folder / kind, folder / kind / "mbe"):
            if root.is_dir():
                yield root, english, dlc


def _rows(path):
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as stream:
        reader = csv.reader(stream)
        next(reader, None)
        yield from (row for row in reader if row and row[0].strip())


class SkillCatalog:
    def __init__(self):
        self.records = {}
        self._occupied = set()
        self._base_attack = None
        self.unreadable_sheets = []

    @classmethod
    def load(cls, loader, mod_roots=(), active_root=None, drafts=()):
        catalog = cls()
        battles, names, descriptions = {}, {}, {}
        bindings = {}

        def read_layer(root, english, dlc, label):
            for table in ((NAME, DESCRIPTION) if english else (BATTLE, *BOUND_SHEETS)):
                for path in _sheets(Path(root), table, dlc):
                    try:
                        rows = list(_rows(path))
                    except OSError as exc:
                        catalog.unreadable_sheets.append(f"{path}: {exc}")
                        continue
                    for row in rows:
                        try:
                            key = int(row[0])
                        except ValueError:
                            continue
                        catalog._occupied.add(key)
                        if table == BATTLE:
                            for ref in row[4:6]:
                                if ref.isdecimal():
                                    catalog._occupied.add(int(ref))
                            try:
                                _validate_battle(row)
                            except ValueError:
                                continue  # Reserve the key, retain a usable lower-layer donor.
                            battles[key] = (tuple(row), label, path)
                        elif table in BOUND_SHEETS:
                            try:
                                validate_typed_row(BOUND_SHEETS[table][1], row)
                            except ValueError:
                                continue
                            bindings.setdefault(key, {})[table] = tuple(row)
                        elif table in (NAME, DESCRIPTION) and len(row) >= 2:
                            (names if table == NAME else descriptions)[key] = row[1]

        read_layer(loader.data_path, False, None, "Base")
        if ATTACK_ID in battles:
            row, label, path = battles[ATTACK_ID]
            catalog._base_attack = SkillRecord(ATTACK_ID, "Attack", "", row, label, path)
        read_layer(loader.text_path, True, None, "Base")
        for dlc, root in loader.iter_dlc_data_roots():
            read_layer(root, False, dlc, f"DLC {dlc}")
        for dlc, root in loader.iter_dlc_text_roots():
            read_layer(root, True, dlc, f"DLC {dlc}")
        active = Path(active_root).resolve() if active_root else None
        roots = dict.fromkeys(Path(root).resolve() for root in mod_roots if root)
        if active:
            roots.pop(active, None)
            roots[active] = None
        for root in roots:
            for folder, english, dlc in _mod_layers(root):
                read_layer(folder, english, dlc, "Active Mod" if root == active else root.parent.name)

        for skill_id, (row, label, path) in battles.items():
            name_id, desc_id = int(row[4]), int(row[5])
            name = names.get(name_id, "") or f"Skill {skill_id}"
            description = descriptions.get(desc_id, "") if desc_id > 0 else ""
            bound = tuple(bindings.get(skill_id, {}).items())
            catalog.records[skill_id] = SkillRecord(skill_id, name, description, row, label, path, bound)
        for draft in drafts:
            catalog.add_draft(draft)
        return catalog

    def _check_free(self, skill_id):
        if not isinstance(skill_id, int) or not 1 <= skill_id <= MAX_SKILL_ID:
            raise ValueError(f"Choose a skill ID from 1 to {MAX_SKILL_ID}.")
        if skill_id in self._occupied:
            record = self.records.get(skill_id)
            owner = f"{record.name} ({record.source})" if record else "a native skill text key"
            raise ValueError(f"ID {skill_id} is already used by {owner}. Choose a free ID.")

    def add_draft(self, draft):
        self._check_free(draft.skill_id)
        self._occupied.add(draft.skill_id)
        self.records[draft.skill_id] = draft

    def suggest_id(self):
        for skill_id in range(100_000, MAX_SKILL_ID + 1):
            if skill_id not in self._occupied:
                return skill_id
        raise ValueError("No free skill ID was found in the suggested range.")

    def template_for(self, template_id=None):
        return self._base_attack if template_id is None else self.records.get(template_id)

    def create(self, skill_id, name, *, template_id=None, description=None):
        self._check_free(skill_id)
        name = _skill_name(name)
        template = self.template_for(template_id)
        if template is None:
            raise ValueError(f"Template skill {ATTACK_ID if template_id is None else template_id} is unavailable.")
        _validate_battle(template.row)
        row = list(template.row)
        row[0] = row[4] = str(skill_id)
        original_desc = int(row[5] or 0)
        if description is None:
            description = template.description
            if original_desc > 0 and not description:
                raise ValueError("The template's fixed description is missing. Enter a description or choose automatic.")
        if description.strip():
            if "\x00" in description:
                raise ValueError("A skill description cannot contain a null character.")
            row[5] = str(skill_id)
        else:
            description = ""
            row[5] = str(original_desc if original_desc <= 0 else 0)
        bound = tuple((sheet, (str(skill_id), *values[1:])) for sheet, values in template.bound_rows)
        return SkillRecord(skill_id, name, description, tuple(row), "Draft", bound_rows=bound)


def _skill_name(name):
    name = name.strip()
    if not name or any(c in name for c in "\r\n\x00"):
        raise ValueError("Enter a nonempty, single-line skill name.")
    return name


def _validate_battle(row):
    validate_typed_row(SKILL_HEADER, row)
    for column, value in zip(SKILL_HEADER, row):
        kind = column.split()[0]
        if kind in ("int8", "int16"):
            limit = 2 ** (int(kind[3:]) - 1)
            if not -limit <= int(value) < limit:
                raise ValueError(f"Skill column {column} exceeds the native range.")


def _destination(payload, table):
    name, stem, prefix, _ = _layout(table)
    folder = payload / ("patch/data" if name == BATTLE else "patch_text01/text") / (name + ".mbe")
    patch = _sheet(folder, stem, True, prefix)
    existing = _sheet(folder, stem, prefix=prefix)
    return existing if existing.is_file() and not patch.is_file() else patch


def _serialized_row(header, row):
    cells = []
    for column, value in zip(header, row, strict=True):
        kind = column.split()[0]
        if kind.startswith("string"):
            cells.append('"' + value.replace('"', '""') + '"')
        elif kind == "empty" or not value:
            cells.append('""')
        else:
            cells.append(value)
    return ",".join(cells) + "\n"


def _append_rows(original, header, rows, named_header=None):
    if original is None:
        original = (",".join(header) + "\n").encode()
    else:
        reader = csv.reader(io.StringIO(original.decode("utf-8-sig"), newline=""))
        actual = next(reader, None)
        if not actual or len(actual) != len(header) or actual not in (header, named_header):
            raise ValueError("The existing mod sheet has an unexpected column layout.")
        if not original.endswith((b"\n", b"\r")):
            original += b"\n"
    return original + "".join(_serialized_row(header, row) for row in rows).encode()


def _read_existing(path):
    return path.read_bytes() if path.exists() else None


def _replace(path, data):
    if data is None:
        path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    output = QSaveFile(str(path))
    if not output.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError(f"Could not open {path}. Close any CSV editor using it and retry. {output.errorString()}")
    if output.write(data) != len(data) or not output.commit():
        output.cancelWriting()
        raise OSError(f"Could not write {path}. Close any CSV editor using it and retry. {output.errorString()}")


@contextmanager
def _locked(payload):
    payload.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(payload / ".studio-skills.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        raise OSError(f"Another Studio skill save is using {payload}. Retry after it finishes.")
    try:
        yield
    finally:
        lock.unlock()


@contextmanager
def skill_record_transaction(payload, drafts, loader, mod_roots=()):
    """Publish the pending records together and restore them if the caller's export fails."""
    drafts = tuple(drafts)
    if not drafts:
        yield
        return
    payload = Path(payload)
    with _locked(payload):
        SkillCatalog.load(loader, mod_roots=mod_roots, active_root=payload, drafts=drafts)
        tables = {table: [] for table in (BATTLE, NAME, DESCRIPTION, *BOUND_SHEETS)}
        for draft in drafts:
            _validate_battle(draft.row)
            key = str(draft.skill_id)
            if draft.row[0] != key or draft.row[4] != key:
                raise ValueError(f"Skill {key} must have its own row and name key.")
            tables[BATTLE].append(draft.row)
            tables[NAME].append((key, _skill_name(draft.name)))
            if draft.description:
                if draft.row[5] != key or "\x00" in draft.description:
                    raise ValueError(f"Skill {key} must have its own valid fixed description.")
                tables[DESCRIPTION].append((key, draft.description))
            elif int(draft.row[5]) > 0:
                raise ValueError(f"Skill {key} needs text for its fixed description.")
            for table, row in draft.bound_rows:
                if table not in BOUND_SHEETS or row[0] != key:
                    raise ValueError(f"Invalid skill binding for {key}.")
                validate_typed_row(BOUND_SHEETS[table][1], row)
                tables[table].append(row)
        changes = {}
        for table, rows in tables.items():
            if rows:
                path = _destination(payload, table)
                original = _read_existing(path)
                header = _layout(table)[3]
                named_header = TEXT_KEYS if table in (NAME, DESCRIPTION) else None
                if original is not None and table == BATTLE:
                    sources = _sheets(loader.data_path, table)
                    if sources:
                        with sources[0].open(encoding="utf-8-sig", newline="") as source:
                            named_header = next(csv.reader(source), None)
                changes[path] = (original, _append_rows(original, header, rows, named_header))
        written = []
        try:
            for path, (original, data) in changes.items():
                if _read_existing(path) != original:
                    raise OSError(f"{path} changed during save. Reload it and retry.")
                _replace(path, data)
                written.append(path)
            yield
        except BaseException:
            failures = []
            for path in reversed(written):
                before, after = changes[path]
                try:
                    if _read_existing(path) != after:
                        raise OSError(f"Another program changed {path}.")
                    _replace(path, before)
                except OSError as exc:
                    failures.append(str(exc))
            if failures:
                raise OSError("Could not restore every skill sheet: " + "\n".join(failures))
            raise


def commit_skill_records(payload, drafts, loader, mod_roots=()):
    with skill_record_transaction(payload, drafts, loader, mod_roots):
        pass


def save_skill_name_override(payload, name_id, name):
    """Set one English skill-name key in this payload."""
    name = _skill_name(name)
    if not 0 < name_id <= 2**31 - 1:
        raise ValueError("This skill needs a valid native name key.")
    payload = Path(payload)
    with _locked(payload):
        path = _destination(payload, NAME)
        key = str(name_id)
        if path.name.endswith(".ap.csv"):
            replacement = _sheet(path.parent, "Sheet1")
            if replacement.is_file() and not (path.is_file() and any(row[0] == key for row in _rows(path))):
                if any(row[0] == key for row in _rows(replacement)):
                    path = replacement
        original = _read_existing(path)
        if original is not None:
            lines = io.StringIO(original.decode("utf-8"), newline="").readlines()
            reader = csv.reader(lines)
            header = next(reader, [])
            if not header or [header[0].lstrip("\ufeff"), *header[1:]] not in (TEXT_HEADER, TEXT_KEYS):
                raise ValueError(f"Unexpected name table layout in {path}.")
            match = None
            start = reader.line_num
            for row in reader:
                if row and row[0] == key:
                    if match is not None:
                        raise ValueError(f"More than one row uses skill name key {key} in {path}.")
                    match = start, reader.line_num, row
                start = reader.line_num
            if match:
                first, end, row = match
                if row[1:] == [name]:
                    return
                lines[first:end] = [_serialized_row(TEXT_HEADER, [key, name])]
                data = "".join(lines).encode()
            else:
                data = _append_rows(original, TEXT_HEADER, [[key, name]], TEXT_KEYS)
        else:
            data = _append_rows(None, TEXT_HEADER, [[key, name]])
        if _read_existing(path) != original:
            raise OSError(f"{path} changed during save. Reload it and retry.")
        _replace(path, data)
