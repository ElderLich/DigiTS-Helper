"""Lossless support for optional Time Stranger mod tables.

These helpers do not infer game behavior from undocumented numeric columns.
Chrono Devolution's six forms are explicit choices, separate from evolution edges.
"""

import csv
import re
from pathlib import Path


CHRONO_HEADER = ["int32 0", "empty 1"] + [f"int32 {i}" for i in range(2, 8)]
CHRONO_STAGES = ("Baby", "Rookie", "Champion", "Ultimate", "Mega", "Mega+")


def _typed_header(length, overrides):
    types = ['int32'] * length
    for kind, columns in overrides.items():
        for column in columns:
            types[column] = kind
    return [f'{kind} {index}' for index, kind in enumerate(types)]


# Source types: Header Reports/DSTS_Header_Report.md, battle_skill tables.
BUFF_SET_HEADER = _typed_header(60, {
    'empty': {4, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}, 'bool': {3},
})
SKILL_HEADER = _typed_header(73, {
    'empty': {1, 2, 3, 13, 15, 17, 19, 48, 51, 53, 55, 57, 59, 62, 65, 67, 69, 71},
    'bool': {7, 8}, 'int16': {36, 37, 45, 49, 50},
    'int8': {39, 40, 41, 42, 43, 44}, 'string2': {72},
})


def find_table(root, folder, stem, prefer_ap=False):
    """Resolve numbered or unnumbered CSV names, with explicit patch precedence."""
    directory = Path(root) / folder
    dlc = re.search(r"addcont_(\d+)\.dx11", str(root), re.IGNORECASE)
    if not directory.exists() and dlc and folder.endswith('.mbe'):
        directory = Path(root) / (folder[:-4] + '_dlc' + dlc.group(1) + '.mbe')
    suffixes = (".ap.csv", ".csv") if prefer_ap else (".csv", ".ap.csv")
    for suffix in suffixes:
        expected = stem + suffix
        for candidate in sorted(directory.glob("*.csv")):
            name = candidate.name
            if name == expected or ("_" in name and name.split("_", 1)[0].isdigit()
                                    and name.split("_", 1)[1] == expected):
                return candidate
    return directory / ("000_" + stem + suffixes[0])


def read_table(root, folder, stem, prefer_ap=False):
    path = find_table(root, folder, stem, prefer_ap)
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.reader(source))


def load_optional_model_tables(digimon, roots, prefer_ap=False):
    """Overlay complete rows in root order; later roots win (app_0 then patch)."""
    key = digimon.chr_id.strip('"')
    motions = {row["motion_key"]: row for row in digimon.model_locator_motion_data}
    for root in roots:
        for row in read_table(root, "model_locator.mbe", "model_locator", prefer_ap)[1:]:
            if len(row) >= 2 and row[0] == key:
                digimon.model_locator_data = {"chr_id": row[0], "locator_ref": row[1]}
        for row in read_table(root, "model_locator.mbe", "model_locator_motion", prefer_ap)[1:]:
            if len(row) >= 2 and row[0].startswith(key + "_"):
                motions[row[0]] = {"motion_key": row[0], "motion_name": row[1]}
        for row in read_table(root, "lod_chara.mbe", "lod", prefer_ap)[1:]:
            if len(row) >= 4 and row[0] == key:
                digimon.lod_data = {"chr_id": key, "raw_data": list(row)}
                for index in range(1, min(11, len(row))):
                    digimon.lod_data[f"lod_distance_{index}"] = float(row[index] or 0)
        for row in read_table(root, "lod_chara.mbe", "lod_model", prefer_ap)[1:]:
            if len(row) >= 3 and row[0] == key:
                digimon.lod_model_data = {"chr_id": key, "lod_model_ref": row[2], "raw_data": list(row)}
        for row in read_table(root, "evolution.mbe", "chronodevolution", prefer_ap)[1:]:
            if len(row) >= 8 and row[0] == str(digimon.id):
                digimon.chronodevolution_forms = [int(value or -1) for value in row[2:8]]
                digimon.chronodevolution_source_id = digimon.id
    digimon.model_locator_motion_data = list(motions.values())


def chrono_forms_for(digimon):
    """Remap a cloned template's self-reference without inventing other forms."""
    forms = list(getattr(digimon, "chronodevolution_forms", []))
    source_id = getattr(digimon, "chronodevolution_source_id", 0)
    if source_id > 0 and source_id != digimon.id:
        forms = [digimon.id if value == source_id else value for value in forms]
    return forms


def validate_typed_row(header, row):
    """Validate a raw numeric buff definition before creating a patch."""
    if len(row) != len(header):
        raise ValueError(f"Expected {len(header)} columns; got {len(row)}.")
    result = []
    for index, (column, value) in enumerate(zip(header, row)):
        value = str(value).strip()
        kind = column.split()[0].lower()
        if kind == "empty":
            value = ""
        elif kind == "bool":
            if value.lower() not in {"true", "false", "0", "1"}:
                raise ValueError(f"Column {index} requires true or false.")
            value = "true" if value.lower() in {"true", "1"} else "false"
        elif kind.startswith("int"):
            number = int(value)
            if not -(2 ** 31) <= number < 2 ** 31:
                raise ValueError(f"Column {index} exceeds the signed 32-bit range.")
            value = str(number)
        elif kind == "float":
            import math
            if not math.isfinite(float(value)):
                raise ValueError(f"Column {index} requires a finite number.")
        result.append(value)
    return result
