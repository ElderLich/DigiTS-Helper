"""
Build MVGL structure overrides for Digimon Story Time Stranger.

MVGL stores the real column types inside each .mbe, but DSTS ships without
friendly field names in structures/dsts. This script reads the currently
extracted CSV headers, applies the field names we know, and writes:

- _internal/structures/dsts/*.json for the packaged CLI
- MVGLTools/structures/dsts/*.json for the source tree
- Header Reports/DSTS_Header_Report.md for humans
- Header Reports/DSTS_Header_Source_Map.csv for spreadsheet/data-mining use
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


HELPER_DIR = Path(__file__).resolve().parent
DEFAULT_EXTRACTED_ROOT = HELPER_DIR / "New Extracted"
STRUCTURE_TARGETS = (
    HELPER_DIR / "_internal" / "structures" / "dsts",
    HELPER_DIR / "MVGLTools" / "structures" / "dsts",
)
REPORT_DIR = HELPER_DIR / "Header Reports"


LOCALIZED_TEXT_FILES = (
    "belong",
    "buff_name",
    "char_name",
    "digimon_class_name",
    "digimon_profile",
    "digimon_type",
    "digitter_message",
    "element",
    "field_name",
    "generation_name",
    "info_message",
    "item_explanation",
    "item_name",
    "item_ruby",
    "jogress_skill_name",
    "personality_name",
    "quest_outline",
    "quest_step",
    "quest_title",
    "skill_auto_explanation",
    "skill_explanation",
    "skill_name",
    "status_name",
)


@dataclass(frozen=True)
class TableDefinition:
    table_pattern: str
    known_names: dict[int, str]
    manual_types: list[str] | None = None


@dataclass(frozen=True)
class SchemaDefinition:
    structure_pattern: str
    file_name: str
    mbe_pattern: str
    tables: tuple[TableDefinition, ...]


HeaderRecord = tuple[Path, str, str, list[tuple[str, str]]]


def indexed(prefix: str, start: int, count: int, first: int = 1) -> dict[int, str]:
    return {start + i: f"{prefix}_{first + i:02d}" for i in range(count)}


def digimon_status_names() -> dict[int, str]:
    names: dict[int, str] = {
        0: "id",
        1: "empty_001",
        2: "char_key",
        3: "chr_id",
        4: "stage_id",
        5: "personality_id",
        6: "type_id",
        7: "res_null",
        8: "res_fire",
        9: "res_water",
        10: "res_ice",
        11: "res_grass",
        12: "res_wind",
        13: "res_elec",
        14: "res_ground",
        15: "res_steel",
        16: "res_light",
        17: "res_dark",
        18: "empty_018",
        61: "base_personality",
        64: "base_hp",
        65: "base_sp",
        66: "base_atk",
        67: "base_def",
        68: "base_int",
        69: "base_spi",
        70: "base_spd",
        71: "growth_pattern_id",
        120: "unknown_after_generic_skills",
        121: "model_type",
        122: "animation_set",
        123: "unknown_float_123",
        124: "unknown_bool_124",
        125: "unknown_bool_125",
        131: "field_guide_id",
        132: "script_id",
    }
    names.update(indexed("trait_flag", 19, 32))
    names.update(indexed("trait_flag", 52, 9, first=33))

    signature_slots = [
        (72, 73, 74),
        (75, 76, 77),
        (78, 79, 80),
        (81, 82, 83),
        (84, 85, 86),
        (87, 88, 89),
        (90, 91, 92),
        (93, 94, 95),
        (96, 97, 98),
        (99, 100, 101),
        (102, 103, 104),
        (105, 106, 107),
    ]
    for slot, (skill_id, empty, slot_id) in enumerate(signature_slots, 1):
        names[skill_id] = f"signature_skill_{slot:02d}_id"
        names[empty] = f"signature_skill_{slot:02d}_empty"
        names[slot_id] = f"signature_skill_{slot:02d}_slot"

    generic_slots = [(108, 109, 110), (111, 112, 113), (114, 115, 116), (117, 118, 119)]
    for slot, (skill_id, empty, level) in enumerate(generic_slots, 1):
        names[skill_id] = f"generic_skill_{slot:02d}_id"
        names[empty] = f"generic_skill_{slot:02d}_empty"
        names[level] = f"generic_skill_{slot:02d}_level"

    return names


def battle_skill_names() -> dict[int, str]:
    names = {
        0: "skill_id",
        1: "empty_001",
        2: "empty_002",
        3: "empty_003",
        4: "name_id",
        5: "fixed_description_id",
        7: "bool_007",
        8: "bool_008",
        10: "animation_id",
        12: "effect_id",
        16: "effect_group_id",
        21: "unknown_021",
        22: "damage_type",
        23: "power",
        26: "additional_property_1",
        27: "additional_property",
        28: "element",
        29: "increased_damage_against_class",
        30: "unused_030",
        31: "unused_031",
        32: "menu_icon",
        33: "target_type",
        34: "min_hits",
        35: "max_hits",
        36: "sp_cost",
        37: "unknown_037",
        38: "cp_cost",
        39: "always_hits",
        40: "accuracy",
        41: "unknown_041",
        42: "crit_rate",
        43: "hp_drain",
        44: "sp_drain",
        45: "recoil",
        46: "conditional_type",
        47: "conditional_effect",
        48: "conditional_empty",
        49: "conditional_arg",
        50: "conditional_effect_arg",
        51: "conditional_empty_2",
        61: "mode_change_id",
        63: "jogress_skill_id",
        64: "jogress_partner_1",
        66: "jogress_partner_2",
        72: "skill_debug_name",
    }
    for slot, start in enumerate((52, 54, 56, 58, 60), 1):
        names[start] = f"buff_set_{slot:02d}"
        names[start + 1] = f"buff_set_{slot:02d}_empty"
    return names


def buff_set_names() -> dict[int, str]:
    names = {0: "set_id", 1: "unknown_001", 2: "unknown_002", 3: "unknown_003"}
    for slot, start in enumerate((6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56), 1):
        names[start] = f"buff_{slot:02d}_effect"
        names[start + 1] = f"buff_{slot:02d}_rate"
        names[start + 2] = f"buff_{slot:02d}_change_percent"
        names[start + 3] = f"buff_{slot:02d}_turn_override"
    return names


def evolution_condition_names() -> dict[int, str]:
    return {
        0: "target_digimon_id",
        1: "empty_001",
        2: "mode",
        3: "tamer_level",
        4: "hp",
        5: "sp",
        6: "atk",
        7: "def",
        8: "int",
        9: "spi",
        10: "spd",
        11: "unknown_011",
        12: "unknown_012",
        13: "skill_count_valor",
        14: "skill_count_philanthropy",
        15: "skill_count_amicable",
        16: "skill_count_wisdom",
        22: "needs_item",
        24: "jogress_db_id_a",
        26: "jogress_personality_a",
        27: "jogress_db_id_b",
        29: "jogress_personality_b",
    }


def enemy_parameter_names() -> dict[int, str]:
    return {
        0: "enemy_id",
        1: "empty_001",
        2: "base_digimon_id",
        5: "enemy_param_id",
        7: "flag_007",
        8: "flag_008",
        9: "flag_009",
        10: "level",
        11: "unknown_011",
        12: "unknown_float_012",
        13: "unknown_float_013",
        14: "name_key",
        15: "unknown_015",
        16: "unknown_016",
        17: "hp",
        18: "sp",
        19: "attack",
        20: "defense",
        21: "intelligence",
        22: "spirit",
        23: "speed",
    }


def encount_group_names() -> dict[int, str]:
    names = {
        0: "encounter_group_id",
        2: "primary_enemy_id",
        75: "battle_event_key",
        82: "unknown_bool_082",
        83: "unknown_bool_083",
        84: "unknown_bool_084",
    }
    for slot, start in enumerate((6, 18, 30, 42, 54, 66), 1):
        names[start] = f"enemy_slot_{slot:02d}_rate"
        names[start + 1] = f"enemy_slot_{slot:02d}_type"
        names[start + 2] = f"enemy_slot_{slot:02d}_param_a"
        names[start + 3] = f"enemy_slot_{slot:02d}_param_b"
        names[start + 4] = f"enemy_slot_{slot:02d}_param_c"
        names[start + 5] = f"enemy_slot_{slot:02d}_param_d"
        names[start + 6] = f"enemy_slot_{slot:02d}_param_e"
        names[start + 7] = f"enemy_slot_{slot:02d}_count"
        names[start + 8] = f"enemy_slot_{slot:02d}_enemy_id"
    return names


def model_setting_names() -> dict[int, str]:
    return {
        0: "chr_id",
        10: "npc_collision",
        38: "digimon_distance_from_agent",
        39: "agent_distance_2",
        40: "agent_distance",
        43: "camera_distance_skill",
        47: "shield_size",
        56: "battle_scale",
        58: "menu_scale",
        59: "field_scale",
        71: "rideable",
    }


def lod_model_names() -> dict[int, str]:
    names = {0: "chr_id"}
    names.update(indexed("lod_model_ref", 1, 10))
    return names


SCHEMAS: tuple[SchemaDefinition, ...] = (
    SchemaDefinition(
        r"digimon_status(_dlc\d+)?\.mbe",
        "digimon_status.json",
        r"digimon_status(_dlc\d+)?\.mbe",
        (TableDefinition(r"digimon_status_data", digimon_status_names()),),
    ),
    SchemaDefinition(
        r"battle_skill(_dlc\d+)?\.mbe",
        "battle_skill.json",
        r"battle_skill(_dlc\d+)?\.mbe",
        (
            TableDefinition(r"battle_skill_list", battle_skill_names()),
            TableDefinition(r"buff_set", buff_set_names()),
        ),
    ),
    SchemaDefinition(
        r"evolution(_dlc\d+)?\.mbe",
        "evolution.json",
        r"evolution(_dlc\d+)?\.mbe",
        (
            TableDefinition(r"evolution_condition", evolution_condition_names()),
            TableDefinition(r"evolution_to", {0: "idx", 1: "id_from", 3: "id_to"}),
        ),
    ),
    SchemaDefinition(
        r"char_info(_dlc\d+)?\.mbe",
        "char_info.json",
        r"char_info(_dlc\d+)?\.mbe",
        (
            TableDefinition(
                r"char_info",
                {
                    0: "char_key",
                    1: "empty_001",
                    2: "empty_002",
                    3: "chr_id",
                    4: "numeric_id",
                    5: "empty_005",
                    6: "gender_flag",
                    7: "flag_007",
                    8: "motion_ref",
                    9: "flag_009",
                    10: "model_ref",
                    11: "flag_011",
                    12: "empty_012",
                    13: "flag_013",
                },
            ),
        ),
    ),
    SchemaDefinition(
        r"model_setting(_dlc\d+)?\.mbe",
        "model_setting.json",
        r"model_setting(_dlc\d+)?\.mbe",
        (TableDefinition(r"model_setting", model_setting_names()),),
    ),
    SchemaDefinition(
        r"model_locator(_dlc\d+)?\.mbe",
        "model_locator.json",
        r"model_locator(_dlc\d+)?\.mbe",
        (
            TableDefinition(r"model_locator", {0: "chr_id", 1: "locator_ref"}),
            TableDefinition(r"model_locator_motion", {0: "motion_key", 1: "motion_name"}),
        ),
    ),
    SchemaDefinition(
        r"lod_chara(_dlc\d+)?\.mbe",
        "lod_chara.json",
        r"lod_chara(_dlc\d+)?\.mbe",
        (
            TableDefinition(
                r"lod",
                {
                    0: "chr_id",
                    1: "lod_distance_1",
                    2: "lod_distance_2",
                    3: "lod_distance_3",
                    4: "lod_distance_4",
                    5: "lod_distance_5",
                    6: "lod_distance_6",
                    7: "lod_distance_7",
                    8: "lod_distance_8",
                    9: "lod_distance_9",
                    10: "lod_distance_10",
                },
            ),
            TableDefinition(r"lod_model", lod_model_names()),
        ),
    ),
    SchemaDefinition(
        r"field_anime(_dlc\d+)?\.mbe",
        "field_anime.json",
        r"field_anime(_dlc\d+)?\.mbe",
        (
            TableDefinition(
                r"field_move_animation",
                {
                    0: "animation_key",
                    1: "motion_1",
                    2: "motion_2",
                    3: "motion_3",
                    4: "move_speed_1",
                    5: "move_param_1",
                    6: "move_speed_2",
                    9: "unknown_int_009",
                    14: "unknown_int_014",
                },
            ),
        ),
    ),
    SchemaDefinition(
        r"digimon_growth(_dlc\d+)?\.mbe",
        "digimon_growth.json",
        r"digimon_growth(_dlc\d+)?\.mbe",
        (
            TableDefinition(
                r"digimon_growth_\d+",
                {
                    0: "level",
                    1: "hp_growth",
                    2: "sp_growth",
                    3: "attack_growth",
                    4: "defense_growth",
                    5: "intelligence_growth",
                    6: "spirit_growth",
                    7: "speed_growth",
                },
            ),
        ),
    ),
    SchemaDefinition(
        r"battle_enemy(_dlc\d+)?\.mbe",
        "battle_enemy.json",
        r"battle_enemy(_dlc\d+)?\.mbe",
        (
            TableDefinition(r"enemy_parameter", enemy_parameter_names()),
            TableDefinition(r"encount_group", encount_group_names()),
        ),
    ),
    SchemaDefinition(
        r"battle_formation(_dlc\d+)?\.mbe",
        "battle_formation.json",
        r"battle_formation(_dlc\d+)?\.mbe",
        (
            TableDefinition(
                r"battle_formation",
                {0: "formation_id", 1: "empty_001", 2: "formation_type", 3: "formation_key"},
            ),
        ),
    ),
    SchemaDefinition(
        r"anim_setting(_dlc\d+)?\.mbe",
        "anim_setting.json",
        r"anim_setting(_dlc\d+)?\.mbe",
        (
            TableDefinition(
                r"animation_loop_data",
                {
                    0: "animation_key",
                    1: "empty_001",
                    2: "empty_002",
                    3: "loop_start_frame",
                    4: "loop_end_frame",
                    5: "motion_set",
                },
            ),
            TableDefinition(
                r"same_animation_data",
                {0: "chr_id", 1: "same_animation_as_chr_id"},
            ),
        ),
    ),
    SchemaDefinition(
        rf"({'|'.join(LOCALIZED_TEXT_FILES)})(_dlc\d+)?\.mbe",
        "localized_text.json",
        rf"({'|'.join(LOCALIZED_TEXT_FILES)})(_dlc\d+)?\.mbe",
        (
            TableDefinition(
                r"Sheet1",
                {0: "key", 1: "text"},
                manual_types=["string2", "string"],
            ),
        ),
    ),
)


def table_name_from_csv(path: Path) -> str:
    stem = path.stem
    return stem.split("_", 1)[1] if "_" in stem else stem


def parse_header(header: str) -> list[tuple[str, str]]:
    row = next(csv.reader([header]))
    result: list[tuple[str, str]] = []
    for cell in row:
        source = cell.strip()
        if " " in source:
            field_type = source.rsplit(" ", 1)[0]
        else:
            field_type = source
        result.append((field_type, source))
    return result


def iter_csv_headers(root: Path) -> Iterable[tuple[Path, str, str, list[tuple[str, str]]]]:
    if not root.exists():
        return
    for csv_path in sorted(root.rglob("*.csv")):
        try:
            header = csv_path.read_text(encoding="utf-8-sig").splitlines()[0]
        except (IndexError, UnicodeDecodeError, OSError):
            continue
        mbe_name = csv_path.parent.name
        yield csv_path, mbe_name, table_name_from_csv(csv_path), parse_header(header)


def sample_priority(path: Path) -> tuple[int, str]:
    normalized = path.as_posix().lower()
    if "/patch.dx11/" in normalized:
        priority = 0
    elif "/app_0.dx11/" in normalized:
        priority = 1
    elif "/addcont_01.dx11/" in normalized:
        priority = 2
    elif "/addcont_01_text01.dx11/" in normalized:
        priority = 3
    else:
        priority = 10
    return priority, normalized


def find_header(
    header_records: list[HeaderRecord], mbe_pattern: str, table_pattern: str
) -> tuple[Path | None, list[tuple[str, str]] | None]:
    candidates: list[tuple[tuple[int, str], Path, list[tuple[str, str]]]] = []
    mbe_re = re.compile(rf"^{mbe_pattern}$", re.IGNORECASE)
    table_re = re.compile(rf"^{table_pattern}$", re.IGNORECASE)
    for path, mbe_name, table_name, header in header_records:
        if mbe_re.match(mbe_name) and table_re.match(table_name):
            candidates.append((sample_priority(path), path, header))
    if not candidates:
        return None, None
    _, path, header = sorted(candidates, key=lambda item: item[0])[0]
    return path, header


def fallback_name(field_type: str, index: int) -> str:
    if field_type == "empty":
        return f"empty_{index:03d}"
    return f"unk_{field_type.replace(' ', '_')}_{index:03d}"


def unique_name(name: str, used: set[str], index: int) -> str:
    clean = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_")
    if not clean:
        clean = f"field_{index:03d}"
    if clean[0].isdigit():
        clean = f"field_{clean}"
    original = clean
    suffix = 2
    while clean in used:
        clean = f"{original}_{suffix}"
        suffix += 1
    used.add(clean)
    return clean


def build_table(
    table: TableDefinition, header: list[tuple[str, str]] | None
) -> tuple[dict[str, str], list[dict[str, str]]]:
    if header is None and table.manual_types is None:
        raise ValueError(f"No sample CSV found for table pattern {table.table_pattern}")

    typed_header = header or [
        (field_type, f"{field_type} {index}") for index, field_type in enumerate(table.manual_types or [])
    ]
    used: set[str] = set()
    schema: dict[str, str] = {}
    report_rows: list[dict[str, str]] = []

    for index, (field_type, source_header) in enumerate(typed_header):
        is_known = index in table.known_names
        field_name = table.known_names.get(index, fallback_name(field_type, index))
        field_name = unique_name(field_name, used, index)
        schema[field_name] = field_type
        report_rows.append(
            {
                "table": table.table_pattern,
                "column_index": str(index),
                "source_header": source_header,
                "type": field_type,
                "friendly_header": field_name,
                "status": "named" if is_known else "unknown",
            }
        )

    return schema, report_rows


def build_all(extracted_root: Path) -> tuple[dict[str, dict[str, dict[str, str]]], list[dict[str, str]], list[str]]:
    schema_files: dict[str, dict[str, dict[str, str]]] = {}
    report_rows: list[dict[str, str]] = []
    warnings: list[str] = []
    header_records = list(iter_csv_headers(extracted_root))

    for schema in SCHEMAS:
        output_tables: dict[str, dict[str, str]] = {}
        for table in schema.tables:
            sample_path, header = find_header(header_records, schema.mbe_pattern, table.table_pattern)
            if header is None and table.manual_types is None:
                warnings.append(
                    f"No sample found for {schema.mbe_pattern}/{table.table_pattern}; skipped table."
                )
                continue
            table_schema, rows = build_table(table, header)
            output_tables[table.table_pattern] = table_schema
            for row in rows:
                row.update(
                    {
                        "structure_pattern": schema.structure_pattern,
                        "schema_file": schema.file_name,
                        "sample_csv": str(sample_path.relative_to(HELPER_DIR))
                        if sample_path and sample_path.is_relative_to(HELPER_DIR)
                        else str(sample_path or "<manual>"),
                    }
                )
                report_rows.append(row)
        if output_tables:
            schema_files[schema.file_name] = output_tables

    return schema_files, report_rows, warnings


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_reports(report_rows: list[dict[str, str]], warnings: list[str]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = REPORT_DIR / "DSTS_Header_Source_Map.csv"
    fieldnames = [
        "schema_file",
        "structure_pattern",
        "table",
        "column_index",
        "source_header",
        "type",
        "friendly_header",
        "status",
        "sample_csv",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)

    named_count = sum(1 for row in report_rows if row["status"] == "named")
    unknown_count = sum(1 for row in report_rows if row["status"] == "unknown")
    md_lines = [
        "# DSTS Header Source Map",
        "",
        "Generated by `DSTS_Header_Schema_Builder.py`.",
        "",
        f"- Named columns: {named_count}",
        f"- Unknown/source-only columns: {unknown_count}",
        f"- Spreadsheet map: `{csv_path.name}`",
        "",
        "The `source_header` column is the original MVGL type/index such as `string2 0`.",
        "The `friendly_header` column is what MVGL will write when these schemas are active.",
        "",
    ]
    if warnings:
        md_lines.extend(["## Warnings", ""])
        md_lines.extend(f"- {warning}" for warning in warnings)
        md_lines.append("")

    current_schema = None
    current_table = None
    for row in report_rows:
        if row["schema_file"] != current_schema:
            current_schema = row["schema_file"]
            md_lines.extend([f"## {current_schema}", ""])
            current_table = None
        if row["table"] != current_table:
            current_table = row["table"]
            md_lines.extend([f"### {current_table}", "", "| # | Source | Friendly | Status |", "|---:|---|---|---|"])
        md_lines.append(
            f"| {row['column_index']} | `{row['source_header']}` | `{row['friendly_header']}` | {row['status']} |"
        )
    md_lines.append("")
    (REPORT_DIR / "DSTS_Header_Report.md").write_text("\n".join(md_lines), encoding="utf-8")


def write_structures(schema_files: dict[str, dict[str, dict[str, str]]]) -> None:
    structure_index = {schema.structure_pattern: schema.file_name for schema in SCHEMAS if schema.file_name in schema_files}
    for target in STRUCTURE_TARGETS:
        target.mkdir(parents=True, exist_ok=True)
        write_json(target / "structure.json", structure_index)
        for file_name, payload in sorted(schema_files.items()):
            write_json(target / file_name, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate DSTS MVGL header schemas.")
    parser.add_argument(
        "--extracted-root",
        type=Path,
        default=DEFAULT_EXTRACTED_ROOT,
        help="Root containing unpacked DSTS CSV folders.",
    )
    parser.add_argument("--reports-only", action="store_true", help="Do not write MVGL structure JSON files.")
    args = parser.parse_args()

    schema_files, report_rows, warnings = build_all(args.extracted_root)
    if not args.reports_only:
        write_structures(schema_files)
    write_reports(report_rows, warnings)

    print(f"Generated {len(schema_files)} DSTS schema files.")
    print(f"Source map rows: {len(report_rows)}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
