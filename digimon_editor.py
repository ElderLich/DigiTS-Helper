"""
DTS Creator - Digimon Editor GUI using PyQt6
"""

import sys
import os
import json
import re
import shutil
import textwrap
import time
from pathlib import Path
from typing import Optional, List, Dict, Iterable, Set, Tuple
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QSpinBox, QComboBox, QPushButton, QTabWidget,
    QScrollArea, QGroupBox, QGridLayout, QCheckBox, QTextEdit,
    QMessageBox, QFileDialog, QTableWidget, QTableWidgetItem, QPlainTextEdit,
    QHeaderView, QSplitter, QListWidget, QListWidgetItem, QDoubleSpinBox, QFormLayout,
    QDialog, QDialogButtonBox, QWizard, QWizardPage, QFrame, QAbstractSpinBox,
    QAbstractScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QObject
from PyQt6.QtGui import QFont, QPixmap, QIcon, QPalette, QColor

from Data_Loader import MBELoader, DigimonData, DLCExporter
from CSV_Exporter import CSVExporter, repack_mbe_files, repack_dlc_mbe_files


DEFAULT_MOD_LOADER_PATH = Path(r"D:\Digimon Modding\Programs\Reloaded II\Mods")
DEFAULT_EXTRACTED_GAME_PATH = Path(r"D:\Digimon Modding\Time Stranger Extracted")
PATH_SETTINGS_FILE_NAME = "DigiTS_Helper_Paths.json"
PATH_SETTINGS_MODS_KEY = "reloaded_mods_path"
PATH_SETTINGS_EXTRACTED_KEY = "extracted_game_path"
FIELD_GUIDE_ID_COLUMN = 131
FIELD_GUIDE_CHR_ID_COLUMN = 3
FIELD_GUIDE_DIGIMON_ID_COLUMN = 0
FIELD_GUIDE_CUSTOM_MIN = 500
FIELD_GUIDE_CUSTOM_MAX = 999
PROFILE_WRAP_WIDTH = 50
EVOLUTION_TYPE_NORMAL = 0
EVOLUTION_TYPE_MODE_CHANGE = 2
EVOLUTION_CONDITION_HEADER = (
    "int32 0,empty 1,int32 2,int32 3,int32 4,int32 5,int32 6,int32 7,"
    "int32 8,int32 9,int32 10,int32 11,int32 12,int32 13,int32 14,"
    "int32 15,int32 16,int32 17,empty 18,int32 19,int32 20,int32 21,"
    "int32 22,empty 23,int32 24,empty 25,int32 26,int32 27,empty 28,int32 29"
)
RELATED_SOURCE_PROMPT = "Select source Digimon..."
GEOM_TEXTURE_TOKEN_RE = re.compile(rb"[A-Za-z0-9_]{4,64}")
GEOM_INDEXED_TEXTURE_RE = re.compile(r"^(?P<head>.*?)(?P<idx>\d{2})(?P<tail>[A-Za-z_]+)?$")
TINY_EFFECT_TEXTURE_RE = re.compile(r"^chr\d+(?:e\d{2}|f\d{2}em)$", re.IGNORECASE)
# digimon_status column 132 is a numeric status/profile reference. Official rows
# usually mirror column 0, while recolors/model variants may point at a source
# Digimon. It is not the Field Guide number from column 131.
STATUS_REFERENCE_ID_COLUMN = 132
RELOADED_SUPPORTED_APP_ID = "digimon story time stranger.exe"
DEBUG_LOGGING = os.environ.get("DIGITS_HELPER_DEBUG", "").lower() in {"1", "true", "yes", "on"}
DSTS_LOADER_DIR_NAMES = {"dsts-loader", "dts-loader"}
TEXT_LANGUAGE_FOLDERS = (
    ("patch_text00", "Japanese"),
    ("patch_text01", "English"),
    ("patch_text02", "French"),
    ("patch_text03", "Spanish"),
    ("patch_text04", "German"),
    ("patch_text05", "Italian"),
    ("patch_text07", "Brazilian Portuguese"),
    ("patch_text09", "Korean"),
    ("patch_text10", "Chinese Traditional"),
    ("patch_text11", "Chinese Simplified"),
    ("patch_text30", "Spanish Alternate"),
)
TEXT_LANGUAGE_LABELS = dict(TEXT_LANGUAGE_FOLDERS)
TEXT_LANGUAGE_FOLDER_RE = re.compile(r"^patch_text(?P<code>\d+)$")
ENGLISH_TEXT_FOLDER = "patch_text01"
_PATH_SETTINGS_CACHE: Optional[Dict[str, str]] = None


def get_app_settings_dir() -> Path:
    """Return the folder where portable per-PC settings should be stored."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_path_settings_file() -> Path:
    """Return the user-editable path settings JSON beside the editor."""
    return get_app_settings_dir() / PATH_SETTINGS_FILE_NAME


def load_path_settings() -> Dict[str, str]:
    """Load per-PC paths while preserving hardcoded defaults as fallback."""
    global _PATH_SETTINGS_CACHE
    if _PATH_SETTINGS_CACHE is not None:
        return dict(_PATH_SETTINGS_CACHE)

    config_path = get_path_settings_file()
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    except Exception as exc:
        print(f"Could not load path settings {config_path}: {exc}")
        data = {}

    if not isinstance(data, dict):
        data = {}

    _PATH_SETTINGS_CACHE = {
        key: str(value).strip()
        for key, value in data.items()
        if isinstance(value, str) and value.strip()
    }
    return dict(_PATH_SETTINGS_CACHE)


def save_path_settings(settings: Dict[str, str]):
    """Persist per-PC path settings."""
    global _PATH_SETTINGS_CACHE
    config_path = get_path_settings_file()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    clean_settings = {
        key: str(value).strip()
        for key, value in settings.items()
        if str(value).strip()
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(clean_settings, f, indent=2)
        f.write("\n")
    _PATH_SETTINGS_CACHE = dict(clean_settings)


def config_path_from_text(value: str, fallback: Path) -> Path:
    """Convert a settings value to a Path without requiring it to exist yet."""
    text = str(value or "").strip()
    if not text:
        return fallback
    return Path(os.path.expandvars(text)).expanduser()


def get_configured_path(key: str, fallback: Path) -> Path:
    """Return a configured path or its fallback default."""
    return config_path_from_text(load_path_settings().get(key, ""), fallback)


def get_default_extracted_game_path() -> Path:
    """Return the configured extracted Time Stranger folder."""
    return get_configured_path(PATH_SETTINGS_EXTRACTED_KEY, DEFAULT_EXTRACTED_GAME_PATH)


def get_existing_directory_start(path: Path) -> Path:
    """Return an existing folder suitable for file-dialog start paths."""
    current = Path(path).expanduser()
    while current and not current.exists():
        parent = current.parent
        if parent == current:
            return Path.cwd()
        current = parent
    return current if current.exists() else Path.cwd()


def get_default_mod_loader_path() -> Path:
    """Return the configured Reloaded II Mods folder."""
    return get_configured_path(PATH_SETTINGS_MODS_KEY, DEFAULT_MOD_LOADER_PATH)


def get_mvgl_fileloader_cache_path() -> Path:
    """Return MVGL FileLoader's generated cache for Time Stranger."""
    return get_default_mod_loader_path() / "MVGL.FileLoader.Reloaded" / "cached" / RELOADED_SUPPORTED_APP_ID


def debug_log(message: str) -> None:
    """Print reverse-engineering diagnostics only when DIGITS_HELPER_DEBUG is enabled."""
    if DEBUG_LOGGING:
        print(f"DEBUG: {message}")


def sanitize_mod_folder_name(value: str, fallback: str = "CustomDigimon") -> str:
    """Create a Windows-safe single folder name while preserving readable text."""
    name = (value or "").strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name or fallback


def make_default_mod_folder_name(digimon_name: str) -> str:
    compact_name = re.sub(r"[^A-Za-z0-9]+", "", digimon_name or "")
    return compact_name or "CustomDigimon"


def make_mod_id_from_folder_name(folder_name: str) -> str:
    mod_id = re.sub(r"[^A-Za-z0-9._-]+", "", folder_name or "")
    return mod_id or "CustomDigimon"


def build_reloaded_mod_config(mod_id: str, mod_name: str, author: str, description: str, version: str = "1.0.0") -> dict:
    """Build a Reloaded II ModConfig.json compatible with DSTS ModLoader + MVGL FileLoader."""
    return {
        "ModId": mod_id,
        "ModName": mod_name,
        "ModAuthor": author,
        "ModVersion": version,
        "ModDescription": description,
        "ModDll": "",
        "ModIcon": "",
        "ModR2RManagedDll32": "",
        "ModR2RManagedDll64": "",
        "ModNativeDll32": "",
        "ModNativeDll64": "",
        "Tags": [],
        "CanUnload": None,
        "HasExports": None,
        "IsLibrary": False,
        "ReleaseMetadataFileName": f"{mod_id}.ReleaseMetadata.json",
        "PluginData": {
            "GitHubDependencies": {
                "IdToConfigMap": {
                    "DSTS.ModLoader": {
                        "Config": {
                            "UserName": "RyoTune",
                            "RepositoryName": "DSTS.ModLoader",
                            "UseReleaseTag": False,
                            "AssetFileName": "Mod.zip"
                        },
                        "ReleaseMetadataName": "DSTS.ModLoader.ReleaseMetadata.json"
                    },
                    "MVGL.FileLoader.Reloaded": {
                        "Config": {
                            "UserName": "RyoTune",
                            "RepositoryName": "MVGL.FileLoader",
                            "UseReleaseTag": False,
                            "AssetFileName": "Mod.zip"
                        },
                        "ReleaseMetadataName": "MVGL.FileLoader.Reloaded.ReleaseMetadata.json"
                    },
                    "Reloaded.Memory.SigScan.ReloadedII": {
                        "Config": {
                            "UserName": "Reloaded-Project",
                            "RepositoryName": "Reloaded.Memory.SigScan",
                            "UseReleaseTag": False,
                            "AssetFileName": "Mod.zip"
                        },
                        "ReleaseMetadataName": "Reloaded.Memory.SigScan.ReloadedII.ReleaseMetadata.json"
                    },
                    "reloaded.sharedlib.hooks": {
                        "Config": {
                            "UserName": "Sewer56",
                            "RepositoryName": "Reloaded.SharedLib.Hooks.ReloadedII",
                            "UseReleaseTag": True,
                            "AssetFileName": "reloaded.sharedlib.hooks.zip"
                        },
                        "ReleaseMetadataName": "Sewer56.Update.ReleaseMetadata.json"
                    }
                }
            }
        },
        "IsUniversalMod": False,
        "ModDependencies": [
            "DSTS.ModLoader",
            "MVGL.FileLoader.Reloaded"
        ],
        "OptionalDependencies": [],
        "SupportedAppId": [
            RELOADED_SUPPORTED_APP_ID
        ],
        "ProjectUrl": "",
        "CreatorUrl": "",
        "IsSeparator": False
    }


class SpinBoxWheelGuard(QObject):
    """Keep mouse-wheel scrolling from accidentally changing value fields."""

    def _guarded_value_widget(self, watched):
        current = watched
        while current:
            if isinstance(current, (QAbstractSpinBox, QComboBox)):
                return current
            current = current.parent()
        return None

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Wheel:
            guarded_widget = self._guarded_value_widget(watched)
            if not guarded_widget:
                return False

            if isinstance(guarded_widget, QComboBox) and guarded_widget.view().isVisible():
                return False

            scroll_parent = guarded_widget.parent()
            while scroll_parent and not isinstance(scroll_parent, QAbstractScrollArea):
                scroll_parent = scroll_parent.parent()

            if isinstance(scroll_parent, QAbstractScrollArea):
                delta = event.pixelDelta().y() if not event.pixelDelta().isNull() else event.angleDelta().y()
                if delta:
                    scrollbar = scroll_parent.verticalScrollBar()
                    scrollbar.setValue(scrollbar.value() - delta)

            return True
        return False


class ComboPromptClearFilter(QObject):
    """Clear a combo-box prompt item as soon as the user starts typing into it."""

    def __init__(self, combo: QComboBox, prompt: str):
        super().__init__(combo)
        self.combo = combo
        self.prompt = prompt

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress):
            current_text = self.combo.currentText().strip()
            if self.combo.currentData() is None and current_text == self.prompt:
                # The prompt is a real combo item so the empty state is obvious.
                # Once editing starts, remove it from the line edit so searches
                # begin from a clean field instead of appending to the prompt.
                self.combo.blockSignals(True)
                self.combo.setCurrentIndex(-1)
                self.combo.setEditText("")
                if self.combo.lineEdit():
                    self.combo.lineEdit().clear()
                self.combo.blockSignals(False)
        return False


def install_spinbox_wheel_guard():
    app = QApplication.instance()
    if app and not hasattr(app, "_digimon_spinbox_wheel_guard"):
        app._digimon_spinbox_wheel_guard = SpinBoxWheelGuard(app)
        app.installEventFilter(app._digimon_spinbox_wheel_guard)


def format_profile_text_for_game(text: str, width: int = PROFILE_WRAP_WIDTH) -> str:
    """Normalize profile text into hard-wrapped lines that fit the in-game profile panel."""
    # Normalize copied text first so Windows, Unix, and pasted multiline descriptions
    # are handled the same way before wrapping.
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    wrapped_lines: List[str] = []

    for paragraph in normalized.split("\n"):
        # Collapse accidental spacing inside each paragraph, but preserve intentional
        # paragraph breaks as blank lines in the final profile text.
        paragraph = " ".join(paragraph.split())
        if not paragraph:
            if wrapped_lines and wrapped_lines[-1]:
                wrapped_lines.append("")
            continue

        # The game profile panel expects hard line breaks. Relying on QTextEdit's
        # visual wrapping would look correct in the editor but export a bad CSV cell.
        wrapped_lines.extend(textwrap.wrap(
            paragraph,
            width=width,
            break_long_words=False,
            break_on_hyphens=False
        ))

    return "\n".join(wrapped_lines).strip()


def digimon_profile_key(digimon_id: int) -> str:
    """Return the game text key for a Digimon profile entry."""
    try:
        numeric_id = int(digimon_id)
    except (TypeError, ValueError):
        return f"digimon_{digimon_id}_profile"

    if numeric_id >= 0:
        return f"digimon_{numeric_id:04d}_profile"
    return f"digimon_{numeric_id}_profile"


def digimon_profile_key_variants(digimon_id) -> set[str]:
    """Return canonical and legacy profile keys that should update the same row."""
    if digimon_id in (None, ""):
        return set()

    raw_id = str(digimon_id)
    keys = {f"digimon_{raw_id}_profile"}
    try:
        keys.add(digimon_profile_key(int(raw_id)))
    except (TypeError, ValueError):
        pass
    return keys


def normalize_status_reference_id(digimon_id: int, field_guide_id: int, reference_id: int) -> int:
    """Return a safe value for digimon_status column 132.

    Column 131 is the visible Field Guide number. Column 132 is a numeric
    status/profile reference used by the game to look up related text/script
    data. For normal custom Digimon it should mirror column 0. Some recolors
    deliberately point at a source Digimon, so only repair obviously broken
    values such as empty/zero or a copied Field Guide number.
    """
    try:
        digimon_id = int(digimon_id)
    except (TypeError, ValueError):
        digimon_id = -1

    try:
        field_guide_id = int(field_guide_id)
    except (TypeError, ValueError):
        field_guide_id = -1

    try:
        reference_id = int(reference_id)
    except (TypeError, ValueError):
        reference_id = -1

    if digimon_id <= 0:
        return reference_id if reference_id > 0 else -1
    if reference_id <= 0:
        return digimon_id
    if field_guide_id >= 0 and reference_id == field_guide_id and reference_id != digimon_id:
        return digimon_id
    return reference_id


def _parse_optional_int(value: str) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _clean_status_cell(value: str) -> str:
    return str(value).strip().strip('"')


def safe_evolution_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        text = str(value).strip().strip('"')
        if not text:
            return default
        return int(text)
    except (TypeError, ValueError):
        return default


def default_evolution_conditions(mode: int = 1) -> Dict[str, int]:
    return {
        'mode': mode,
        'tamerLevel': 0,
        'HP': 0,
        'SP': 0,
        'ATK': 0,
        'DEF': 0,
        'INT': 0,
        'SPI': 0,
        'SPD': 0,
        'unknown1': 0,
        'unknown2': 0,
        'skillCountValor': 0,
        'skillCountPhilantropy': 0,
        'skillCountAmicable': 0,
        'skillCountWisdom': 0,
        'needsItem': 0,
        'jogressDbIdA': 0,
        'jogressPersonalityA': 0,
        'jogressDbIdB': 0,
        'jogressPersonalityB': 0,
    }


def normalize_evolution_conditions(conditions, default_mode: int = 1) -> Dict[str, int]:
    normalized = default_evolution_conditions(default_mode)

    if isinstance(conditions, list):
        if not conditions:
            return normalized
        first = conditions[0]
        if isinstance(first, dict):
            conditions = first
        else:
            row = conditions
            conditions = {
                'mode': safe_evolution_int(row[2], default_mode) if len(row) > 2 else default_mode,
                'tamerLevel': safe_evolution_int(row[3]) if len(row) > 3 else 0,
                'HP': safe_evolution_int(row[4]) if len(row) > 4 else 0,
                'SP': safe_evolution_int(row[5]) if len(row) > 5 else 0,
                'ATK': safe_evolution_int(row[6]) if len(row) > 6 else 0,
                'DEF': safe_evolution_int(row[7]) if len(row) > 7 else 0,
                'INT': safe_evolution_int(row[8]) if len(row) > 8 else 0,
                'SPI': safe_evolution_int(row[9]) if len(row) > 9 else 0,
                'SPD': safe_evolution_int(row[10]) if len(row) > 10 else 0,
                'unknown1': safe_evolution_int(row[11]) if len(row) > 11 else 0,
                'unknown2': safe_evolution_int(row[12]) if len(row) > 12 else 0,
                'skillCountValor': safe_evolution_int(row[13]) if len(row) > 13 else 0,
                'skillCountPhilantropy': safe_evolution_int(row[14]) if len(row) > 14 else 0,
                'skillCountAmicable': safe_evolution_int(row[15]) if len(row) > 15 else 0,
                'skillCountWisdom': safe_evolution_int(row[16]) if len(row) > 16 else 0,
                'needsItem': safe_evolution_int(row[22]) if len(row) > 22 else 0,
                'jogressDbIdA': safe_evolution_int(row[24]) if len(row) > 24 else 0,
                'jogressPersonalityA': safe_evolution_int(row[26]) if len(row) > 26 else 0,
                'jogressDbIdB': safe_evolution_int(row[27]) if len(row) > 27 else 0,
                'jogressPersonalityB': safe_evolution_int(row[29]) if len(row) > 29 else 0,
            }

    if isinstance(conditions, dict):
        for key in normalized:
            if key in conditions:
                normalized[key] = safe_evolution_int(conditions.get(key), normalized[key])

    return normalized


def evolution_conditions_have_jogress(conditions) -> bool:
    if not isinstance(conditions, dict):
        conditions = normalize_evolution_conditions(conditions)
    return (
        safe_evolution_int(conditions.get("jogressDbIdA"), 0) > 0
        or safe_evolution_int(conditions.get("jogressDbIdB"), 0) > 0
    )


def jogress_partner_ids_from_conditions(conditions) -> List[int]:
    if not isinstance(conditions, dict):
        conditions = normalize_evolution_conditions(conditions)
    partner_ids = []
    for key in ("jogressDbIdA", "jogressDbIdB"):
        partner_id = safe_evolution_int(conditions.get(key), 0)
        if partner_id > 0 and partner_id not in partner_ids:
            partner_ids.append(partner_id)
    return partner_ids


def collect_field_guide_usage(
    loader: Optional[MBELoader],
    exclude_chr_id: str = "",
    exclude_chr_ids: Optional[Iterable[str]] = None,
    exclude_digimon_ids: Optional[Iterable[int]] = None,
) -> Dict[int, List[str]]:
    """Collect occupied custom field guide IDs from base, DLC, and imported data."""
    usage: Dict[int, List[str]] = {}
    if not loader:
        return usage

    excluded_chr_ids = {exclude_chr_id.strip().casefold()} if exclude_chr_id else set()
    if exclude_chr_ids:
        excluded_chr_ids.update(str(chr_id).strip().casefold() for chr_id in exclude_chr_ids if str(chr_id).strip())
    excluded_digimon_ids = {str(digimon_id).strip() for digimon_id in (exclude_digimon_ids or []) if str(digimon_id).strip()}

    def add_rows(rows: List[List[str]], source_name: str):
        for row in rows[1:]:
            if len(row) <= FIELD_GUIDE_ID_COLUMN:
                continue

            field_guide_id = _parse_optional_int(row[FIELD_GUIDE_ID_COLUMN])
            if field_guide_id is None:
                continue
            if not FIELD_GUIDE_CUSTOM_MIN <= field_guide_id <= FIELD_GUIDE_CUSTOM_MAX:
                continue

            chr_id = _clean_status_cell(row[FIELD_GUIDE_CHR_ID_COLUMN]) if len(row) > FIELD_GUIDE_CHR_ID_COLUMN else ""
            digimon_id = _clean_status_cell(row[FIELD_GUIDE_DIGIMON_ID_COLUMN]) if len(row) > FIELD_GUIDE_DIGIMON_ID_COLUMN else "?"
            if chr_id.casefold() in excluded_chr_ids or digimon_id in excluded_digimon_ids:
                continue

            label = f"{source_name}: {chr_id or 'unknown chr'} (Digimon ID {digimon_id})"
            usage.setdefault(field_guide_id, []).append(label)

    try:
        base_file = loader._resolve_prefixed_file(loader.data_path / "digimon_status.mbe" / "000_digimon_status_data.csv")
        if base_file.exists():
            add_rows(loader.load_csv(base_file), "Base")
    except Exception as exc:
        print(f"Could not scan base field guide IDs: {exc}")

    try:
        for dlc_id, status_file in loader.iter_dlc_csv_files("data", "digimon_status", "000_digimon_status_data.csv"):
            add_rows(loader.load_csv(status_file), f"DLC addcont_{dlc_id}")
    except Exception as exc:
        print(f"Could not scan DLC field guide IDs: {exc}")

    try:
        mods_root = get_default_mod_loader_path()
        if mods_root.exists():
            for status_file in mods_root.rglob("*.ap.csv"):
                if status_file.parent.name != "digimon_status.mbe":
                    continue
                if not status_file.name.endswith("digimon_status_data.ap.csv"):
                    continue

                try:
                    mod_name = status_file.relative_to(mods_root).parts[0]
                except ValueError:
                    mod_name = status_file.parent.name

                add_rows(loader.load_csv(status_file), f"Mod {mod_name}")
    except Exception as exc:
        print(f"Could not scan mod-loader field guide IDs: {exc}")

    for digimon in getattr(loader, "imported_digimon", []):
        field_guide_id = getattr(digimon, "field_guide_id", -1)
        chr_id = getattr(digimon, "chr_id", "")
        digimon_id = str(getattr(digimon, "id", "")).strip()
        if chr_id.strip().casefold() in excluded_chr_ids or digimon_id in excluded_digimon_ids:
            continue
        if FIELD_GUIDE_CUSTOM_MIN <= field_guide_id <= FIELD_GUIDE_CUSTOM_MAX:
            usage.setdefault(field_guide_id, []).append(
                f"Imported: {getattr(digimon, 'name', 'Unknown')} ({chr_id})"
            )

    return usage


def first_free_field_guide_id(
    loader: Optional[MBELoader],
    exclude_chr_id: str = "",
    exclude_chr_ids: Optional[Iterable[str]] = None,
    exclude_digimon_ids: Optional[Iterable[int]] = None,
) -> int:
    occupied = set(collect_field_guide_usage(loader, exclude_chr_id, exclude_chr_ids, exclude_digimon_ids))
    for field_guide_id in range(FIELD_GUIDE_CUSTOM_MIN, FIELD_GUIDE_CUSTOM_MAX + 1):
        if field_guide_id not in occupied:
            return field_guide_id
    return -1


def choose_field_guide_id(
    parent: QWidget,
    loader: Optional[MBELoader],
    current_value: int = -1,
    exclude_chr_id: str = "",
    exclude_chr_ids: Optional[Iterable[str]] = None,
    exclude_digimon_ids: Optional[Iterable[int]] = None,
) -> Optional[int]:
    usage = collect_field_guide_usage(loader, exclude_chr_id, exclude_chr_ids, exclude_digimon_ids)
    first_free = first_free_field_guide_id(loader, exclude_chr_id, exclude_chr_ids, exclude_digimon_ids)

    dialog = QDialog(parent)
    dialog.setWindowTitle("Select Field Guide ID")
    dialog.setMinimumSize(620, 640)

    layout = QVBoxLayout(dialog)

    info = QLabel(
        f"Custom Digimon field guide IDs use {FIELD_GUIDE_CUSTOM_MIN}-{FIELD_GUIDE_CUSTOM_MAX}. "
        "Light red rows are already occupied in Base, DLC, or imported mod-loader data."
    )
    info.setWordWrap(True)
    layout.addWidget(info)

    guide_list = QListWidget()
    guide_list.setAlternatingRowColors(True)

    selected_item = None
    first_free_item = None
    for field_guide_id in range(FIELD_GUIDE_CUSTOM_MIN, FIELD_GUIDE_CUSTOM_MAX + 1):
        occupied_by = usage.get(field_guide_id, [])
        if occupied_by:
            label = f"{field_guide_id}  occupied by {occupied_by[0]}"
            if len(occupied_by) > 1:
                label += f" (+{len(occupied_by) - 1} more)"
        else:
            label = f"{field_guide_id}  free"

        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, field_guide_id)
        if occupied_by:
            item.setBackground(QColor("#ffd6d6"))
            item.setForeground(QColor("#7a1f1f"))
            item.setToolTip("\n".join(occupied_by[:20]))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
        else:
            item.setToolTip(f"Field Guide ID {field_guide_id} is free")
            if first_free_item is None:
                first_free_item = item

        guide_list.addItem(item)
        if field_guide_id == current_value:
            selected_item = item

    if selected_item and bool(selected_item.flags() & Qt.ItemFlag.ItemIsEnabled):
        guide_list.setCurrentItem(selected_item)
    elif first_free_item:
        guide_list.setCurrentItem(first_free_item)

    layout.addWidget(guide_list)

    button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    first_free_button = QPushButton("Use First Free")
    button_box.addButton(first_free_button, QDialogButtonBox.ButtonRole.ActionRole)

    ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
    ok_button.setEnabled(guide_list.currentItem() is not None)

    def update_ok_button():
        item = guide_list.currentItem()
        ok_button.setEnabled(item is not None and bool(item.flags() & Qt.ItemFlag.ItemIsEnabled))

    def use_first_free():
        if first_free == -1:
            QMessageBox.warning(dialog, "No Free IDs", "Every custom field guide ID from 500-999 is occupied.")
            return
        for index in range(guide_list.count()):
            item = guide_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == first_free:
                guide_list.setCurrentItem(item)
                break
        dialog.accept()

    def accept_selected_item(item: QListWidgetItem):
        if item and bool(item.flags() & Qt.ItemFlag.ItemIsEnabled):
            dialog.accept()

    guide_list.currentItemChanged.connect(lambda _current, _previous: update_ok_button())
    guide_list.itemDoubleClicked.connect(accept_selected_item)
    first_free_button.clicked.connect(use_first_free)
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)

    if dialog.exec() == QDialog.DialogCode.Accepted and guide_list.currentItem():
        return int(guide_list.currentItem().data(Qt.ItemDataRole.UserRole))
    return None


def create_field_guide_slot_button() -> QPushButton:
    """Create the shared visible button used to open the field guide slot picker."""
    button = QPushButton("Choose Slot...")
    button.setToolTip("Show custom field guide slots and mark occupied IDs in light red")
    button.setMinimumWidth(130)
    button.setStyleSheet("""
        QPushButton {
            color: white;
            background-color: #3f7de8;
            border: none;
            border-radius: 6px;
            padding: 8px 12px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #316ad0;
        }
    """)
    return button


def get_skill_options(loader: Optional[MBELoader]) -> List[tuple]:
    """Return available skills as (skill_id, display_label) pairs."""
    if not loader:
        return []

    options = []
    try:
        skills_file = loader._resolve_prefixed_file(loader.data_path / "battle_skill.mbe" / "000_battle_skill_list.csv")
        if not skills_file.exists():
            return []

        rows = loader.load_csv(skills_file)
        seen = set()
        for row in rows[1:]:
            if not row or not row[0]:
                continue
            try:
                skill_id = int(row[0])
            except (ValueError, TypeError):
                continue
            if skill_id in seen:
                continue
            seen.add(skill_id)

            skill_name = loader.get_skill_name(skill_id)
            if skill_name and skill_name != f"skill_{skill_id}":
                skill_name = loader.clean_ui_text(skill_name)
            if not skill_name or skill_name == str(skill_id) or skill_name.startswith("Skill_"):
                skill_name = row[4].strip('"') if len(row) > 4 and row[4] else f"Skill {skill_id}"

            options.append((skill_id, f"ID {skill_id}: {skill_name}"))
    except Exception as exc:
        print(f"Error loading skill options: {exc}")

    return sorted(options, key=lambda option: option[0])


def configure_searchable_combo(combo: QComboBox):
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    combo.setMaxVisibleItems(20)
    combo.setMinimumHeight(40)
    combo.setMinimumWidth(320)
    combo.view().setMinimumWidth(520)
    combo.setStyleSheet("""
        QComboBox {
            color: #333333;
            background-color: white;
            border: 2px solid #dee2e6;
            border-radius: 6px;
            padding: 7px 34px 7px 8px;
            font-size: 10pt;
        }
        QComboBox:hover {
            border-color: #667eea;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 30px;
            border-left: 1px solid #dee2e6;
            background-color: #f8f9fa;
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
        }
        QComboBox QAbstractItemView {
            color: #333333;
            background-color: white;
            selection-background-color: #667eea;
            selection-color: white;
        }
    """)
    if combo.lineEdit():
        combo.lineEdit().setClearButtonEnabled(True)
    completer = combo.completer()
    if completer:
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)


def choose_skill_id(parent: QWidget, loader: Optional[MBELoader], title: str, current_skill_id: int = 0) -> Optional[int]:
    """Open a compact searchable skill dropdown and return the selected skill ID."""
    options = get_skill_options(loader)
    if not options:
        QMessageBox.warning(parent, "No Skills Found", "Could not load battle_skill.mbe skill data.")
        return None

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(560)

    layout = QVBoxLayout(dialog)
    label = QLabel("Type a skill name or ID, then choose it from the dropdown.")
    label.setWordWrap(True)
    layout.addWidget(label)

    combo = QComboBox()
    configure_searchable_combo(combo)
    combo.addItem("Select a skill...", 0)
    for skill_id, display_label in options:
        combo.addItem(display_label, skill_id)
        if skill_id == current_skill_id:
            combo.setCurrentIndex(combo.count() - 1)
    combo.lineEdit().setPlaceholderText("Search skills by name or ID...")
    layout.addWidget(combo)

    button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        skill_id = combo.currentData()
        return int(skill_id) if skill_id else None
    return None


class SkillEditor(QWidget):
    """Widget for editing signature and generic skills"""
    skillChanged = pyqtSignal()

    def __init__(self, skill_type: str = "signature", loader=None):
        super().__init__()
        self.skill_type = skill_type
        self.loader = loader
        self.skill_widgets = []
        self.skill_options = get_skill_options(loader)
        self._syncing_skill_widgets = False
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        hint = QLabel("Choose a skill from each slot dropdown, or type a skill ID directly.")
        hint.setStyleSheet("color: #666; font-size: 9pt; padding: 4px;")
        layout.addWidget(hint)

        # Skills container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(4, 4, 4, 4)
        scroll_layout.setSpacing(8)

        # Create skill input widgets
        max_skills = 12 if self.skill_type == "signature" else 4
        for i in range(max_skills):
            skill_widget = self.create_skill_widget(i)
            self.skill_widgets.append(skill_widget)
            scroll_layout.addWidget(skill_widget)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_widget)
        if self.skill_type == "generic":
            scroll.setMinimumHeight(300)
        else:
            scroll.setMinimumHeight(260)
            scroll.setMaximumHeight(420)
        layout.addWidget(scroll, 1)

        self.setLayout(layout)

    def create_skill_widget(self, index: int) -> QWidget:
        """Create a single skill input widget"""
        widget = QFrame()
        widget.setObjectName(f"skill_slot_{index}")
        widget.setStyleSheet("""
            QFrame#skill_slot_0, QFrame#skill_slot_1, QFrame#skill_slot_2, QFrame#skill_slot_3,
            QFrame#skill_slot_4, QFrame#skill_slot_5, QFrame#skill_slot_6, QFrame#skill_slot_7,
            QFrame#skill_slot_8, QFrame#skill_slot_9, QFrame#skill_slot_10, QFrame#skill_slot_11 {
                background-color: #ffffff;
                border: 1px solid #d8dee9;
                border-radius: 8px;
            }
        """)
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        slot_title = QLabel(f"Slot {index + 1}")
        slot_title.setMinimumWidth(58)
        slot_title.setStyleSheet("font-weight: bold; color: #667eea;")
        layout.addWidget(slot_title)

        # Skill ID with name display
        layout.addWidget(QLabel("ID:"))
        skill_id = QSpinBox()
        skill_id.setRange(0, 9999999)
        skill_id.setObjectName(f"skill_id_{index}")
        skill_id.setMinimumWidth(110)
        skill_id.valueChanged.connect(lambda _value, idx=index: self.on_skill_value_changed(idx))
        layout.addWidget(skill_id)

        # Skill dropdown
        skill_combo = QComboBox()
        skill_combo.setObjectName(f"skill_combo_{index}")
        configure_searchable_combo(skill_combo)
        skill_combo.addItem("Select a skill...", 0)
        for skill_option_id, skill_label in self.skill_options:
            skill_combo.addItem(skill_label, skill_option_id)
        skill_combo.activated.connect(lambda _combo_index, idx=index: self.on_skill_combo_selected(idx))
        layout.addWidget(skill_combo, 1)

        open_dropdown_button = QPushButton("+ Select")
        open_dropdown_button.setObjectName(f"add_skill_{index}")
        open_dropdown_button.setMinimumWidth(86)
        open_dropdown_button.setToolTip("Open the skill dropdown for this slot")
        open_dropdown_button.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #667eea;
                border: none;
                border-radius: 6px;
                padding: 8px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5568d3;
            }
        """)
        open_dropdown_button.clicked.connect(lambda _checked=False, idx=index: self.open_skill_dropdown(idx))
        layout.addWidget(open_dropdown_button)

        # Skill Level/Slot
        slot_label = "Learn Slot:" if self.skill_type == "signature" else "Level:"
        layout.addWidget(QLabel(slot_label))
        skill_level = QSpinBox()
        skill_level.setRange(0, 100)
        skill_level.setObjectName(f"skill_level_{index}")
        skill_level.setMinimumWidth(90)
        skill_level.valueChanged.connect(self.skillChanged.emit)
        layout.addWidget(skill_level)

        remove_button = QPushButton("- Remove")
        remove_button.setObjectName(f"remove_skill_{index}")
        remove_button.setMinimumWidth(90)
        remove_button.setToolTip("Clear this skill slot")
        remove_button.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #e34556;
                border: none;
                border-radius: 6px;
                padding: 8px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c92f40;
            }
            QPushButton:disabled {
                color: #9aa1aa;
                background-color: #edf0f4;
            }
        """)
        remove_button.clicked.connect(lambda _checked=False, idx=index: self.clear_skill_slot(idx))
        layout.addWidget(remove_button)

        widget.setLayout(layout)
        return widget

    def on_skill_value_changed(self, index: int):
        if self._syncing_skill_widgets:
            return
        self.update_skill_name(index)
        self.skillChanged.emit()

    def on_skill_combo_selected(self, index: int):
        if self._syncing_skill_widgets:
            return

        skill_combo = self.skill_widgets[index].findChild(QComboBox, f"skill_combo_{index}")
        skill_id_widget = self.skill_widgets[index].findChild(QSpinBox, f"skill_id_{index}")
        if not skill_combo or not skill_id_widget:
            return

        skill_id = skill_combo.currentData()
        self._syncing_skill_widgets = True
        skill_id_widget.setValue(int(skill_id) if skill_id else 0)
        self._syncing_skill_widgets = False
        self.update_skill_name(index)
        self.skillChanged.emit()

    def load_skills(self, skills: List[dict]):
        """Load skills into the widget"""
        for i, skill_widget in enumerate(self.skill_widgets):
            skill_id_widget = skill_widget.findChild(QSpinBox, f"skill_id_{i}")
            skill_level_widget = skill_widget.findChild(QSpinBox, f"skill_level_{i}")

            if i < len(skills):
                skill_id_widget.setValue(skills[i].get("id", 0))
                level_key = "slot" if self.skill_type == "signature" else "level"
                skill_level_widget.setValue(skills[i].get(level_key, 0))
            else:
                skill_id_widget.setValue(0)
                skill_level_widget.setValue(0)
            self.update_skill_name(i)

    def get_skills(self) -> List[dict]:
        """Get skills from the widget"""
        skills = []
        for i, skill_widget in enumerate(self.skill_widgets):
            skill_id_widget = skill_widget.findChild(QSpinBox, f"skill_id_{i}")
            skill_level_widget = skill_widget.findChild(QSpinBox, f"skill_level_{i}")

            skill_id = skill_id_widget.value()
            skill_level = skill_level_widget.value()

            if skill_id > 0:
                level_key = "slot" if self.skill_type == "signature" else "level"
                skills.append({"id": skill_id, level_key: skill_level})

        return skills

    def update_skill_name(self, index: int):
        """Update skill name display when skill ID changes"""
        skill_id_widget = self.skill_widgets[index].findChild(QSpinBox, f"skill_id_{index}")
        skill_combo = self.skill_widgets[index].findChild(QComboBox, f"skill_combo_{index}")

        if skill_id_widget and skill_combo:
            skill_id = skill_id_widget.value()
            combo_index = skill_combo.findData(skill_id)
            self._syncing_skill_widgets = True
            if combo_index >= 0:
                skill_combo.setCurrentIndex(combo_index)
            elif skill_id > 0:
                skill_name = self.loader.get_skill_name(skill_id) if self.loader else f"Skill {skill_id}"
                clean_name = self.loader.clean_ui_text(skill_name) if self.loader else skill_name
                skill_combo.setCurrentIndex(0)
                skill_combo.setEditText(f"Custom ID {skill_id}: {clean_name}")
            else:
                skill_combo.setCurrentIndex(0)
                if skill_combo.lineEdit():
                    skill_combo.lineEdit().clear()
                    skill_combo.lineEdit().setPlaceholderText("Select a skill...")
            self._syncing_skill_widgets = False

        add_button = self.skill_widgets[index].findChild(QPushButton, f"add_skill_{index}")
        remove_button = self.skill_widgets[index].findChild(QPushButton, f"remove_skill_{index}")
        if add_button:
            add_button.setText("+ Change" if skill_id_widget and skill_id_widget.value() > 0 else "+ Select")
        if remove_button:
            remove_button.setEnabled(bool(skill_id_widget and skill_id_widget.value() > 0))

    def update_all_skill_names(self):
        """Update skill names for all skill widgets"""
        for i in range(len(self.skill_widgets)):
            self.update_skill_name(i)

    def open_skill_dropdown(self, index: int):
        skill_combo = self.skill_widgets[index].findChild(QComboBox, f"skill_combo_{index}")
        if skill_combo:
            skill_combo.setFocus(Qt.FocusReason.MouseFocusReason)
            skill_combo.showPopup()

    def clear_skill_slot(self, index: int):
        skill_id_widget = self.skill_widgets[index].findChild(QSpinBox, f"skill_id_{index}")
        skill_level_widget = self.skill_widgets[index].findChild(QSpinBox, f"skill_level_{index}")
        skill_combo = self.skill_widgets[index].findChild(QComboBox, f"skill_combo_{index}")
        self._syncing_skill_widgets = True
        if skill_id_widget:
            skill_id_widget.setValue(0)
        if skill_level_widget:
            skill_level_widget.setValue(0)
        if skill_combo:
            skill_combo.setCurrentIndex(0)
            if skill_combo.lineEdit():
                skill_combo.lineEdit().clear()
                skill_combo.lineEdit().setPlaceholderText("Select a skill...")
        self._syncing_skill_widgets = False
        self.update_skill_name(index)
        self.skillChanged.emit()


class DigimonCreationWizard(QWizard):
    """Multi-step wizard for creating new Digimon and exporting to dsts-loader"""

    def __init__(self, parent=None, loader=None):
        super().__init__(parent)
        self.loader = loader
        self.template_digimon: Optional[DigimonData] = None
        self.new_digimon: Optional[DigimonData] = None
        self.last_export_path: Optional[Path] = None  # Store export path for later import

        self.setWindowTitle("✨ Digimon Creation Wizard - Export to dsts-loader")
        self.setMinimumSize(700, 600)
        self.resize(900, 700)  # Set a larger default size

        # Enable maximize button and make window resizable
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)

        # Set wizard style
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.HaveHelpButton, False)

        # Add pages
        self.addPage(TemplateSelectionPage(self))
        self.addPage(BasicInfoPage(self))
        self.addPage(ClassificationPage(self))
        self.addPage(ProfilePage(self))
        self.addPage(StatsPage(self))
        self.addPage(ResistancesPage(self))
        self.addPage(SkillsPage(self))
        self.addPage(EvolutionPage(self))
        self.addPage(ModelPage(self))
        self.addPage(ReviewPage(self))

        # Connect signals
        self.button(QWizard.WizardButton.FinishButton).clicked.connect(self.finish_wizard)

        # Apply styling
        self.setStyleSheet("""
            QWizard {
                background-color: #f5f7fa;
            }
            QWizardPage {
                background-color: white;
                border-radius: 8px;
                padding: 20px;
            }
        """)

    def finish_wizard(self):
        """Called when wizard is finished - export to DLC"""
        try:
            # Get all data from pages
            template_page = self.page(0)
            basic_page = self.page(1)
            class_page = self.page(2)
            profile_page = self.page(3)
            stats_page = self.page(4)
            resist_page = self.page(5)
            skills_page = self.page(6)
            evolution_page = self.page(7)
            model_page = self.page(8)
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            QMessageBox.critical(
                self,
                "Wizard Error",
                f"Error getting wizard pages:\n\n{str(e)}\n\nSee console for details."
            )
            print(f"\n{'='*80}")
            print("WIZARD PAGE ERROR:")
            print(error_trace)
            print(f"{'='*80}\n")
            return

        # Create new Digimon from template
        try:
            if not self.template_digimon:
                QMessageBox.warning(self, "Error", "No template Digimon selected!")
                return

            # Copy template
            from copy import deepcopy
            self.new_digimon = deepcopy(self.template_digimon)

            # Store template chr_id for reference
            template_chr_id = self.template_digimon.chr_id

            # Update with wizard data
            self.new_digimon.id = basic_page.id_spin.value()
            self.new_digimon.name = basic_page.name_edit.text()
            self.new_digimon.char_key = basic_page.char_key_edit.text()
            new_chr_id = basic_page.chr_id_edit.text()
            self.new_digimon.chr_id = new_chr_id
            self.new_digimon.field_guide_id = basic_page.field_guide_id_spin.value()
            self.new_digimon.script_id = self.new_digimon.id
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            QMessageBox.critical(
                self,
                "Wizard Error",
                f"Error collecting basic data:\n\n{str(e)}\n\nSee console for details."
            )
            print(f"\n{'='*80}")
            print("DATA COLLECTION ERROR:")
            print(error_trace)
            print(f"{'='*80}\n")
            return

        try:
            self.new_digimon.stage_id = class_page.stage_combo.currentData() if class_page.stage_combo.currentData() is not None else 0
            self.new_digimon.type_id = class_page.type_combo.currentData() if class_page.type_combo.currentData() is not None else 0
            self.new_digimon.generation_id = self.new_digimon.stage_id
            self.new_digimon.personality_id = class_page.personality_combo.currentData() if class_page.personality_combo.currentData() is not None else 0
            self.new_digimon.base_personality = self.new_digimon.personality_id
            self.new_digimon.growth_pattern_id = class_page.growth_combo.currentData() if class_page.growth_combo.currentData() is not None else 1
            self.new_digimon.tribe_name = class_page.tribe_combo.currentText() if class_page.tribe_combo.currentText() else "None"

            # Store selected tribe name for belong export
            if not hasattr(self.new_digimon, 'tribe_name'):
                self.new_digimon.tribe_name = None
            self.new_digimon.tribe_name = class_page.tribe_combo.currentText()

            # Profile
            self.new_digimon.profile_text = format_profile_text_for_game(profile_page.profile_edit.toPlainText())

            # Stats
            self.new_digimon.base_hp = stats_page.hp_spin.value()
            self.new_digimon.base_sp = stats_page.sp_spin.value()
            self.new_digimon.base_atk = stats_page.atk_spin.value()
            self.new_digimon.base_def = stats_page.def_spin.value()
            self.new_digimon.base_int = stats_page.int_spin.value()
            self.new_digimon.base_spi = stats_page.spi_spin.value()
            self.new_digimon.base_spd = stats_page.spd_spin.value()

            self.new_digimon.res_null = resist_page.resist_widgets["null"].value()
            self.new_digimon.res_fire = resist_page.resist_widgets["fire"].value()
            self.new_digimon.res_water = resist_page.resist_widgets["water"].value()
            self.new_digimon.res_ice = resist_page.resist_widgets["ice"].value()
            self.new_digimon.res_grass = resist_page.resist_widgets["grass"].value()
            self.new_digimon.res_wind = resist_page.resist_widgets["wind"].value()
            self.new_digimon.res_elec = resist_page.resist_widgets["elec"].value()
            self.new_digimon.res_ground = resist_page.resist_widgets["ground"].value()
            self.new_digimon.res_steel = resist_page.resist_widgets["steel"].value()
            self.new_digimon.res_light = resist_page.resist_widgets["light"].value()
            self.new_digimon.res_dark = resist_page.resist_widgets["dark"].value()

            # Skills
            self.new_digimon.signature_skills = skills_page.signature_skills_editor.get_skills()
            self.new_digimon.generic_skills = skills_page.generic_skills_editor.get_skills()

            # Evolution paths (from EvolutionPage)
            self.new_digimon.evolution_paths = evolution_page.evolution_paths.copy()
            self.new_digimon.deevolution_sources = evolution_page.deevolution_sources.copy()

            # Get evolution requirements from the single requirements section
            self.new_digimon.evolution_conditions = [evolution_page.evolution_requirements]

            self.new_digimon.model_id = model_page.model_id_edit.text()
            self.new_digimon.motion_id = model_page.motion_id_edit.text()

            # Update chr_id references in all data structures
            self._update_chr_id_references(self.new_digimon, template_chr_id, new_chr_id)
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            QMessageBox.critical(
                self,
                "Wizard Error",
                f"Error collecting wizard data:\n\n{str(e)}\n\nSee console for details."
            )
            print(f"\n{'='*80}")
            print("WIZARD DATA COLLECTION ERROR:")
            print(error_trace)
            print(f"{'='*80}\n")
            return

        # Get animation reference
        animation_ref = model_page.animation_ref_edit.text().strip() if model_page.animation_ref_edit.text().strip() else template_chr_id

        # Ask user where to export. If the main editor has an imported mod
        # loaded, default to that payload so adding a second Digimon naturally
        # appends to the same Reloaded II mod instead of starting a new one.
        parent_editor = self.parent()
        default_path = get_default_mod_loader_path()
        if parent_editor and hasattr(parent_editor, "_active_dsts_loader_root"):
            active_root = parent_editor._active_dsts_loader_root()
            if active_root:
                default_path = active_root

        export_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Reloaded II Mod or dsts-loader Directory",
            str(get_existing_directory_start(default_path)),
            QFileDialog.Option.ShowDirsOnly
        )

        if not export_dir:
            # Don't lose work if user cancels - ask if they want to retry or exit
            reply = QMessageBox.question(
                self,
                "Export Cancelled",
                "Do you want to go back and review your Digimon, or discard all changes?",
                QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Discard,
                QMessageBox.StandardButton.Retry
            )

            if reply == QMessageBox.StandardButton.Retry:
                # Go back to review page
                self.back()
                return
            else:
                # User chose to discard - close wizard
                return

        selected_export_path = Path(export_dir)
        output_path = selected_export_path
        if parent_editor and hasattr(parent_editor, "_resolve_dsts_loader_root"):
            output_path = parent_editor._resolve_dsts_loader_root(selected_export_path, allow_create=True) or selected_export_path

        # Store export path for later import
        self.last_export_path = output_path

        # Export to dsts-loader format. Prefer the editor merge path so existing
        # Digimon rows in a loaded mod are preserved when adding another entry.
        try:
            if parent_editor and hasattr(parent_editor, "_merge_digimon_to_dsts_loader"):
                success = parent_editor._merge_digimon_to_dsts_loader(
                    output_path,
                    self.new_digimon,
                    animation_ref=animation_ref,
                    sync_form=False,
                )
                if success and hasattr(parent_editor, "_set_active_dsts_loader_root"):
                    parent_editor._set_active_dsts_loader_root(output_path)
            else:
                success = self._export_to_dsts_loader(output_path, self.new_digimon, animation_ref)
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            QMessageBox.critical(
                self,
                "Export Error",
                f"An error occurred during export:\n\n{str(e)}\n\nSee console for full traceback."
            )
            print(f"\n{'='*80}")
            print("EXPORT ERROR:")
            print(error_trace)
            print(f"{'='*80}\n")
            return

        if success:
            QMessageBox.information(
                self,
                "Success! 🎉",
                f"✅ {self.new_digimon.name} has been successfully exported!\n\n"
                f"ID: {self.new_digimon.id}\n"
                f"Chr ID: {self.new_digimon.chr_id}\n"
                f"Animation Reference: {animation_ref}\n\n"
                f"📁 Files created in dsts-loader format:\n\n"
                f"patch/data/:\n"
                f"  • digimon_status_data.ap.csv\n"
                f"  • char_info.ap.csv\n"
                f"  • model_setting.ap.csv\n"
                f"  • lod.ap.csv + lod_model.ap.csv\n"
                f"  • evolution_to.ap.csv + evolution_condition.ap.csv\n"
                f"  • same_animation_data.ap.csv\n\n"
                f"patch_text01/text/:\n"
                f"  • char_name.ap.csv\n"
                f"  • digimon_profile.ap.csv\n"
                f"  • belong.ap.csv\n\n"
                f"app_0/data/:\n"
                f"  • model_outline_battle.ap.csv\n\n"
                f"Ready to use with dsts-loader! ✨"
            )
        else:
            QMessageBox.warning(self, "Error", "Failed to export Digimon")

    def _update_chr_id_references(self, digimon: DigimonData, old_chr_id: str, new_chr_id: str):
        """Update all chr_id references in digimon data structures"""
        import json

        old_chr_id_clean = old_chr_id.strip('"')
        new_chr_id_clean = new_chr_id.strip('"')

        # Update char_info_data
        if digimon.char_info_data:
            for key, value in digimon.char_info_data.items():
                if isinstance(value, str) and old_chr_id_clean in value:
                    digimon.char_info_data[key] = value.replace(old_chr_id_clean, new_chr_id_clean)

        # Update model_setting_data
        if digimon.model_setting_data:
            for key, value in digimon.model_setting_data.items():
                if isinstance(value, str) and old_chr_id_clean in value:
                    digimon.model_setting_data[key] = value.replace(old_chr_id_clean, new_chr_id_clean)
                elif key == 'raw_data' and isinstance(value, list):
                    # Update raw_data array - replace chr_id references in all string elements
                    for idx, item in enumerate(value):
                        if isinstance(item, str) and old_chr_id_clean in item:
                            value[idx] = item.replace(old_chr_id_clean, new_chr_id_clean)

        # Update model_locator_data
        if digimon.model_locator_data:
            for key, value in digimon.model_locator_data.items():
                if isinstance(value, str) and old_chr_id_clean in value:
                    digimon.model_locator_data[key] = value.replace(old_chr_id_clean, new_chr_id_clean)

        # Update model_locator_motion_data - update motion keys
        for motion_entry in digimon.model_locator_motion_data:
            motion_key = motion_entry.get('motion_key', '')
            if isinstance(motion_key, str) and old_chr_id_clean in motion_key:
                motion_entry['motion_key'] = motion_key.replace(old_chr_id_clean, new_chr_id_clean)
            motion_name = motion_entry.get('motion_name', '')
            if isinstance(motion_name, str) and old_chr_id_clean in motion_name:
                motion_entry['motion_name'] = motion_name.replace(old_chr_id_clean, new_chr_id_clean)

        # Update lod_data
        if digimon.lod_data:
            for key, value in digimon.lod_data.items():
                if isinstance(value, str) and old_chr_id_clean in value:
                    digimon.lod_data[key] = value.replace(old_chr_id_clean, new_chr_id_clean)

        # Update lod_model_data
        if digimon.lod_model_data:
            for key, value in digimon.lod_model_data.items():
                if isinstance(value, str) and old_chr_id_clean in value:
                    digimon.lod_model_data[key] = value.replace(old_chr_id_clean, new_chr_id_clean)

        # Update field_move_animation_data - update animation keys
        for anim_entry in digimon.field_move_animation_data:
            anim_key = anim_entry.get('animation_key', '')
            if isinstance(anim_key, str) and old_chr_id_clean in anim_key:
                anim_entry['animation_key'] = anim_key.replace(old_chr_id_clean, new_chr_id_clean)
            for motion_key in ['motion1', 'motion2', 'motion3']:
                motion_value = anim_entry.get(motion_key, '')
                if isinstance(motion_value, str) and old_chr_id_clean in motion_value:
                    anim_entry[motion_key] = motion_value.replace(old_chr_id_clean, new_chr_id_clean)

    def _escape_csv_value(self, value: str) -> str:
        """Properly escape a value for CSV output"""
        if not value:
            return value
        # Escape quotes by doubling them
        if '"' in value:
            value = value.replace('"', '""')
        return value

    def _export_to_dsts_loader(self, base_path: Path, digimon: DigimonData, animation_ref: str) -> bool:
        """Export digimon to dsts-loader format (.ap.csv files)"""
        try:
            from pathlib import Path
            import csv

            # Create directory structure
            patch_data = base_path / "patch" / "data"
            patch_text = base_path / "patch_text01" / "text"
            app_data = base_path / "app_0" / "data"

            # Create all needed directories
            (patch_data / "digimon_status.mbe").mkdir(parents=True, exist_ok=True)
            (patch_data / "char_info.mbe").mkdir(parents=True, exist_ok=True)
            (patch_data / "model_setting.mbe").mkdir(parents=True, exist_ok=True)
            (patch_data / "lod_chara.mbe").mkdir(parents=True, exist_ok=True)
            (patch_data / "evolution.mbe").mkdir(parents=True, exist_ok=True)
            (patch_data / "anim_setting.mbe").mkdir(parents=True, exist_ok=True)
            (patch_text / "char_name.mbe").mkdir(parents=True, exist_ok=True)
            (patch_text / "digimon_profile.mbe").mkdir(parents=True, exist_ok=True)
            (patch_text / "belong.mbe").mkdir(parents=True, exist_ok=True)
            (app_data / "model_outline.mbe").mkdir(parents=True, exist_ok=True)

            # Export digimon_status_data
            self._write_digimon_status_ap_csv(patch_data / "digimon_status.mbe" / "000_digimon_status_data.ap.csv", digimon)

            # Export char_info
            self._write_char_info_ap_csv(patch_data / "char_info.mbe" / "000_char_info.ap.csv", digimon)

            # Export model_setting
            if digimon.model_setting_data:
                self._write_model_setting_ap_csv(patch_data / "model_setting.mbe" / "000_model_setting.ap.csv", digimon)

            # Export lod data
            if digimon.lod_data:
                self._write_lod_ap_csv(patch_data / "lod_chara.mbe" / "000_lod.ap.csv", digimon)
                self._write_lod_model_ap_csv(patch_data / "lod_chara.mbe" / "001_lod_model.ap.csv", digimon)

            # Export animation reference
            self._write_anim_setting_ap_csv(patch_data / "anim_setting.mbe" / "001_same_animation_data.ap.csv", digimon.chr_id, animation_ref)

            # Export evolution data (includes both evolutions FROM this Digimon and pre-evolutions TO this Digimon)
            if digimon.evolution_paths or digimon.deevolution_sources:
                self._write_evolution_ap_csv(patch_data / "evolution.mbe" / "001_evolution_to.ap.csv", digimon)
                self._write_evolution_condition_ap_csv(patch_data / "evolution.mbe" / "000_evolution_condition.ap.csv", digimon)

            # Export char_name
            self._write_char_name_ap_csv(patch_text / "char_name.mbe" / "000_Sheet1.ap.csv", digimon)

            # Export digimon_profile (always export, even if empty - use default text)
            self._write_profile_ap_csv(patch_text / "digimon_profile.mbe" / "000_Sheet1.ap.csv", digimon)

            # Export belong (classification text)
            self._write_belong_ap_csv(patch_text / "belong.mbe" / "000_Sheet1.ap.csv", digimon)

            # Export model_outline
            self._write_model_outline_ap_csv(app_data / "model_outline.mbe" / "000_model_outline_battle.ap.csv", digimon)

            return True

        except Exception as e:
            print(f"Error exporting to dsts-loader: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _write_digimon_status_ap_csv(self, filepath: Path, digimon: DigimonData):
        """Write digimon_status_data.ap.csv"""
        # Header from dsts-loader format
        header = "int32 0,empty 1,string2 2,string2 3,int32 4,int32 5,int32 6,int32 7,int32 8,int32 9,int32 10,int32 11,int32 12,int32 13,int32 14,int32 15,int32 16,int32 17,empty 18,bool 19,bool 20,bool 21,bool 22,bool 23,bool 24,bool 25,bool 26,bool 27,bool 28,bool 29,bool 30,bool 31,bool 32,bool 33,bool 34,bool 35,bool 36,bool 37,bool 38,bool 39,bool 40,bool 41,bool 42,bool 43,bool 44,bool 45,bool 46,bool 47,bool 48,bool 49,bool 50,int32 51,bool 52,bool 53,bool 54,bool 55,bool 56,bool 57,bool 58,bool 59,bool 60,int32 61,int32 62,int32 63,int32 64,int32 65,int32 66,int32 67,int32 68,int32 69,int32 70,int32 71,int32 72,empty 73,int32 74,int32 75,empty 76,int32 77,int32 78,empty 79,int32 80,int32 81,empty 82,int32 83,int32 84,empty 85,int32 86,int32 87,empty 88,int32 89,int32 90,empty 91,int32 92,int32 93,empty 94,int32 95,int32 96,empty 97,int32 98,int32 99,empty 100,int32 101,int32 102,empty 103,int32 104,int32 105,empty 106,int32 107,int32 108,empty 109,int32 110,int32 111,empty 112,int32 113,int32 114,empty 115,int32 116,int32 117,empty 118,int32 119,int32 120,int32 121,int32 122,float 123,bool 124,bool 125,int32 126,empty 127,int32 128,int32 129,int32 130,int32 131,int32 132,int32 133,int32 134,int32 135"

        # Build data row
        parts = []
        parts.append(str(digimon.id))  # 0
        parts.append('')  # 1 empty (blank, not quoted)
        parts.append(f'"{self._escape_csv_value(digimon.char_key)}"')  # 2
        parts.append(f'"{self._escape_csv_value(digimon.chr_id)}"')  # 3
        parts.append(str(digimon.stage_id))  # 4
        parts.append(str(digimon.personality_id))  # 5
        parts.append(str(digimon.type_id))  # 6

        # Resistances (7-17)
        parts.append(str(digimon.res_null))
        parts.append(str(digimon.res_fire))
        parts.append(str(digimon.res_water))
        parts.append(str(digimon.res_ice))
        parts.append(str(digimon.res_grass))
        parts.append(str(digimon.res_wind))
        parts.append(str(digimon.res_elec))
        parts.append(str(digimon.res_ground))
        parts.append(str(digimon.res_steel))
        parts.append(str(digimon.res_light))
        parts.append(str(digimon.res_dark))
        parts.append('')  # 18 empty

        # Traits part 1 (19-50 bool) - 32 traits
        for i in range(32):
            if i < len(digimon.traits):
                parts.append("true" if digimon.traits[i] else "false")
            else:
                parts.append("false")

        parts.append("0")  # 51 int32

        # Traits part 2 (52-60 bool) - 9 traits
        for i in range(32, 41):
            if i < len(digimon.traits):
                parts.append("true" if digimon.traits[i] else "false")
            else:
                parts.append("false")

        parts.append(str(digimon.base_personality))  # 61 int32
        parts.append("1")  # 62
        parts.append("99")  # 63
        parts.append(str(digimon.base_hp))  # 64
        parts.append(str(digimon.base_sp))  # 65
        parts.append(str(digimon.base_atk))  # 66
        parts.append(str(digimon.base_def))  # 67
        parts.append(str(digimon.base_int))  # 68
        parts.append(str(digimon.base_spi))  # 69
        parts.append(str(digimon.base_spd))  # 70
        parts.append(str(digimon.growth_pattern_id))  # 71 - Growth Pattern (1-18)

        # Signature skills (72-107) - pattern: id, empty, slot
        for i in range(12):
            if i < len(digimon.signature_skills):
                skill = digimon.signature_skills[i]
                parts.append(str(skill.get('id', 0)))
                parts.append('')  # empty
                parts.append(str(skill.get('slot', 0)))
            else:
                parts.append("0")
                parts.append('')  # empty
                parts.append("0")

        # Generic skills (108-119) - pattern: id, empty, level
        for i in range(4):
            if i < len(digimon.generic_skills):
                skill = digimon.generic_skills[i]
                parts.append(str(skill.get('id', 0)))
                parts.append('')  # empty
                parts.append(str(skill.get('level', 0)))
            else:
                parts.append("0")
                parts.append('')  # empty
                parts.append("0")

        # Remaining fields (120-135)
        # Column 126: Signature Animation Reference - Formula: 20000 + (ID × 10) + 1
        anim_ref = 20000 + (digimon.id * 10) + 1
        status_reference_id = normalize_status_reference_id(
            digimon.id,
            digimon.field_guide_id,
            getattr(digimon, "script_id", -1),
        )

        parts.extend([
            "2",  # 120 - Size category
            str(digimon.model_type) if hasattr(digimon, 'model_type') else "1",  # 121 - Model type
            str(digimon.animation_set) if hasattr(digimon, 'animation_set') else "1",  # 122 - Animation set
            "0",  # 123 - Model scale override (float, 0 = normal)
            "true",  # 124 - Boolean flag
            "false",  # 125 - Boolean flag
            str(anim_ref),  # 126 - Signature Animation Reference (calculated)
            '',  # 127 - empty
            "0",  # 128 - Color/Palette ID (0 for new Digimon)
            "0",  # 129 - Texture/Material ID (0 for new Digimon)
            "0",  # 130 - Model Variant (0 for new Digimon)
            str(digimon.field_guide_id),  # 131 - Field Guide ID (-1 = none, 0+ = valid ID)
            str(status_reference_id),  # 132 - Status/profile reference ID, usually the Digimon ID
            "-1",  # 133 - Reserved (don't touch)
            "0",  # 134 - Reserved (always 0)
            "-1"  # 135 - Reserved (always -1)
        ])

        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(header + '\n')
            f.write(','.join(parts) + '\n')

    def _write_char_info_ap_csv(self, filepath: Path, digimon: DigimonData):
        """Write char_info.ap.csv

        Columns:
        0: char_key, 1-2: empty, 3: chr_id, 4: id, 5: empty
        6-7: 0,0, 8: audio_id (motion_id), 9: 0, 10: model_id
        11: 0, 12: empty, 13: 0
        """
        header = 'string2 0,empty 1,empty 2,string2 3,string2 4,empty 5,int32 6,int32 7,string2 8,int32 9,string2 10,int32 11,string2 12,int32 13'

        # Get audio_id (motion_id) - prefer wizard value, fallback to template
        audio_id = ""
        if hasattr(digimon, 'motion_id') and digimon.motion_id:
            audio_id = digimon.motion_id
        elif hasattr(digimon, 'char_info_data') and digimon.char_info_data:
            audio_id = digimon.char_info_data.get('motion_ref', '')

        # Get model_id - prefer wizard value, fallback to template
        model_id = ""
        if hasattr(digimon, 'model_id') and digimon.model_id:
            model_id = digimon.model_id
        elif hasattr(digimon, 'char_info_data') and digimon.char_info_data:
            model_id = digimon.char_info_data.get('model_ref', '')

        parts = [
            f'"{self._escape_csv_value(digimon.char_key)}"',  # 0: char_key
            '', '',  # 1-2: empty columns
            f'"{self._escape_csv_value(digimon.chr_id)}"',  # 3: chr_id
            f'"{str(digimon.id)}"',  # 4: id
            '',  # 5: empty
            '0', '0',  # 6-7
            f'"{audio_id}"',  # 8: audio_id (motion_id in our code)
            '0',  # 9
            f'"{model_id}"',  # 10: model_id
            '0',  # 11
            '""',  # 12: empty string
            '0'  # 13
        ]

        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(header + '\n')
            f.write(','.join(parts) + '\n')

    def _write_model_setting_ap_csv(self, filepath: Path, digimon: DigimonData):
        """Write model_setting.ap.csv"""
        if not digimon.model_setting_data or 'raw_data' not in digimon.model_setting_data:
            return

        header = 'string2 0,empty 1,string2 2,string2 3,string2 4,float 5,empty 6,empty 7,float 8,float 9,float 10,float 11,float 12,float 13,float 14,float 15,float 16,float 17,float 18,float 19,float 20,float 21,float 22,float 23,float 24,float 25,float 26,string2 27,string2 28,string2 29,string2 30,string2 31,string2 32,float 33,float 34,float 35,float 36,int32 37,float 38,float 39,int32 40,float 41,float 42,float 43,float 44,float 45,float 46,float 47,empty 48,empty 49,empty 50,float 51,string2 52,float 53,float 54,float 55,float 56,float 57,float 58,float 59,float 60,float 61,float 62,float 63,int32 64,int32 65,int32 66,int8 67,int8 68,int8 69,int8 70,int32 71,empty 72,int32 73,int32 74,int8 75,int8 76,int8 77,int8 78,string2 79,int32 80,int32 81'

        # Convert raw_data to proper format and replace chr_id references
        raw_data = digimon.model_setting_data['raw_data'].copy()
        header_types = header.split(',')
        parts = []

        # Get the template chr_id from raw_data[0] to know what to replace
        template_chr_id = raw_data[0].strip('"') if raw_data[0] else ""
        new_chr_id = digimon.chr_id

        # Model/audio references live in char_info. Preserve model_setting's
        # raw string columns instead of forcing the form's Model ID/Audio ID
        # into unrelated slots; doing so can break imported recolor mods.

        for i, value in enumerate(raw_data):
            col_type = header_types[i] if i < len(header_types) else ''

            if 'string' in col_type:
                # String columns: quote non-empty values, use "" for empty
                if value and value != '""':
                    # Remove existing quotes if present
                    clean_value = value.strip('"') if isinstance(value, str) else str(value)

                    # Replace template chr_id with new chr_id in ALL string columns
                    if template_chr_id and template_chr_id in clean_value:
                        clean_value = clean_value.replace(template_chr_id, new_chr_id)

                    escaped_value = self._escape_csv_value(clean_value)
                    parts.append(f'"{escaped_value}"')
                else:
                    parts.append('""')
            elif 'empty' in col_type:
                # Empty columns: just blank
                parts.append('')
            else:
                # Numeric columns: no quotes
                parts.append(str(value) if value else '0')

        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(header + '\n')
            f.write(','.join(parts) + '\n')

    def _write_lod_ap_csv(self, filepath: Path, digimon: DigimonData):
        """Write lod.ap.csv"""
        header = 'string2 0,float 1,float 2,float 3,float 4,float 5,float 6,float 7,float 8,float 9,float 10'
        parts = [
            f'"{self._escape_csv_value(digimon.chr_id)}"',
            str(digimon.lod_data.get('lod_distance_1', 20)),
            str(digimon.lod_data.get('lod_distance_2', 65)),
            str(digimon.lod_data.get('lod_distance_3', 500)),
            '0', '0', '0', '0', '0', '0', '0'
        ]

        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(header + '\n')
            f.write(','.join(parts) + '\n')

    def _write_lod_model_ap_csv(self, filepath: Path, digimon: DigimonData):
        """Write lod_model.ap.csv"""
        header = 'string2 0,string2 1,string2 2,string2 3,string2 4,string2 5,string2 6,string2 7,string2 8,string2 9,string2 10'
        escaped_chr_id = self._escape_csv_value(digimon.chr_id)
        parts = [
            f'"{escaped_chr_id}"',
            '""',  # empty string
            f'"{escaped_chr_id}_LOD_2"',  # LOD model name
            '""', '""', '""', '""', '""', '""', '""', '""'  # 8 empty strings
        ]

        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(header + '\n')
            f.write(','.join(parts) + '\n')

    def _write_anim_setting_ap_csv(self, filepath: Path, chr_id: str, animation_ref: str):
        """Write same_animation_data.ap.csv"""
        header = 'string2 0,string2 1'
        parts = [f'"{self._escape_csv_value(chr_id)}"', f'"{self._escape_csv_value(animation_ref)}"']

        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(header + '\n')
            f.write(','.join(parts) + '\n')

    def _write_evolution_ap_csv(self, filepath: Path, digimon: DigimonData):
        """Write evolution_to.ap.csv

        This file contains ALL evolution relationships:
        - Evolutions FROM this Digimon (what it evolves into)
        - Pre-evolutions TO this Digimon (what evolves into it)

        Format: [evo_id], [source_id], "", [target_id], "", [type], -1, -1, -1, -1, -1
        - type 0 = Normal evolution, including Jogress/DNA source edges
        - type 2 = Mode Change

        Note: Max 6 evolutions per source Digimon or game will crash!
        """
        header = 'int32 0,int32 1,empty 2,int32 3,empty 4,int32 5,int32 6,int32 7,int32 8,int32 9,int32 10'

        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(header + '\n')

            # Use user's suggested formula: (digimon.id * 100) + counter
            # For ID 640: 64000, 64001, 64002, etc.
            counter = 0

            # Track seen entries to avoid duplicates
            seen_entries = set()  # (source_id, target_id)

            # 1. Write evolutions FROM this Digimon (what it evolves into)
            for evo in digimon.evolution_paths:
                to_id = safe_evolution_int(evo.get('to_id'), 0)
                source_ids = [safe_evolution_int(evo.get('from_id'), digimon.id) or digimon.id]
                conditions = normalize_evolution_conditions(evo.get('conditions', {}))
                if evo.get('export_partner_rows') and evolution_conditions_have_jogress(conditions):
                    for partner_id in jogress_partner_ids_from_conditions(conditions):
                        if partner_id not in source_ids:
                            source_ids.append(partner_id)

                if to_id == 0:
                    continue

                # Get evolution type/mode (default to 0 for normal evolution)
                evo_type = safe_evolution_int(evo.get('evolution_type'), EVOLUTION_TYPE_NORMAL)

                for source_id in source_ids:
                    entry_key = (source_id, to_id)
                    if source_id == 0 or entry_key in seen_entries:
                        continue
                    seen_entries.add(entry_key)

                    # Calculate evolution ID
                    evo_id = (source_id * 100) + counter
                    counter += 1

                    parts = [
                        str(evo_id),
                        str(source_id),  # Source Digimon
                        '',  # empty column
                        str(to_id),  # Target: what it evolves into
                        '',  # empty column
                        str(evo_type),  # Evolution type: 0=Normal/Jogress source edge, 2=Mode Change
                        '-1', '-1', '-1', '-1', '-1'
                    ]
                    f.write(','.join(parts) + '\n')

            # 2. Write pre-evolutions TO this Digimon (what evolves into it)
            # These are stored as: [pre-evo ID] evolves TO [this Digimon's ID]
            for deevo in digimon.deevolution_sources:
                from_id = deevo.get('from_id', 0)

                # Skip if from_id is 0 or already written
                entry_key = (from_id, digimon.id)
                if from_id == 0 or entry_key in seen_entries:
                    continue
                seen_entries.add(entry_key)

                # Get evolution type (default to 0 for normal evolution)
                evo_type = safe_evolution_int(deevo.get('evolution_type'), EVOLUTION_TYPE_NORMAL)

                # Calculate evolution ID using the PRE-evolution's ID as base
                evo_id = (from_id * 100) + 50 + counter  # Offset by 50 to avoid collision
                counter += 1

                parts = [
                    str(evo_id),
                    str(from_id),  # Source: the pre-evolution Digimon
                    '',  # empty column
                    str(digimon.id),  # Target: this Digimon (what it evolves into)
                    '',  # empty column
                    str(evo_type),  # Evolution type: 0=Normal, 2=Mode Change
                    '-1', '-1', '-1', '-1', '-1'
                ]
                f.write(','.join(parts) + '\n')

    def _write_char_name_ap_csv(self, filepath: Path, digimon: DigimonData, name_text: Optional[str] = None):
        """Write char_name.ap.csv"""
        import csv

        header = 'string2 0,string 1'
        display_name = digimon.name if name_text is None else name_text

        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(header + '\n')
            # Use csv.writer to properly handle special characters
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow([digimon.char_key, display_name])

    def _write_profile_ap_csv(self, filepath: Path, digimon: DigimonData, profile_text: Optional[str] = None, name_text: Optional[str] = None):
        """Write digimon_profile.ap.csv"""
        import csv

        header = 'string2 0,string 1'
        fallback_name = digimon.name if name_text is None else name_text
        if profile_text is None:
            profile = digimon.profile_text if digimon.profile_text else f"A mysterious Digimon known as {fallback_name}."
        else:
            profile = profile_text
        profile = format_profile_text_for_game(profile)

        profile_key = digimon_profile_key(digimon.id)

        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(header + '\n')
            # Use csv.writer to properly handle multi-line text
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow([profile_key, profile])

    def _write_model_outline_ap_csv(self, filepath: Path, digimon: DigimonData):
        """Write model_outline_battle.ap.csv"""
        header = 'string2 0,float 1,float 2'
        parts = [
            f'"{self._escape_csv_value(digimon.chr_id)}"',
            '-0.003',  # Default outline thickness values
            '-0.003'
        ]

        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(header + '\n')
            f.write(','.join(parts) + '\n')

    def _write_evolution_condition_ap_csv(self, filepath: Path, digimon: DigimonData):
        """Write evolution_condition.ap.csv - requirements to evolve INTO this new Digimon"""
        header = EVOLUTION_CONDITION_HEADER

        def condition_row(target_id: int, condition: dict) -> List[str]:
            condition = normalize_evolution_conditions(condition)
            return [
                str(target_id),  # 0: target Digimon ID
                '',  # 1: empty
                str(condition.get('mode', 1)),  # 2: condition type/mode
                str(condition.get('tamerLevel', 0)),  # 3: tamer level
                str(condition.get('HP', 0)),  # 4: HP requirement
                str(condition.get('SP', 0)),  # 5: SP requirement
                str(condition.get('ATK', 0)),  # 6: ATK requirement
                str(condition.get('DEF', 0)),  # 7: DEF requirement
                str(condition.get('INT', 0)),  # 8: INT requirement
                str(condition.get('SPI', 0)),  # 9: SPI requirement
                str(condition.get('SPD', 0)),  # 10: SPD requirement
                str(condition.get('unknown1', 0)),  # 11
                str(condition.get('unknown2', 0)),  # 12
                str(condition.get('skillCountValor', 0)),  # 13
                str(condition.get('skillCountPhilantropy', 0)),  # 14
                str(condition.get('skillCountAmicable', 0)),  # 15
                str(condition.get('skillCountWisdom', 0)),  # 16
                '0',  # 17
                '',  # 18: empty
                '0', '0', '0',  # 19-21
                str(condition.get('needsItem', 0)),  # 22
                '',  # 23: empty
                str(condition.get('jogressDbIdA', 0)),  # 24
                '',  # 25: empty
                str(condition.get('jogressPersonalityA', 0)),  # 26
                str(condition.get('jogressDbIdB', 0)),  # 27
                '',  # 28: empty
                str(condition.get('jogressPersonalityB', 0))  # 29
            ]

        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(header + '\n')

            target_conditions = {
                safe_evolution_int(digimon.id): normalize_evolution_conditions(digimon.evolution_conditions)
            }

            # Outgoing DNA paths may target another Digimon. Only export those
            # target condition rows when they were created/edited by this mod flow.
            for evo in getattr(digimon, 'evolution_paths', []):
                if not evo.get('export_conditions'):
                    continue
                target_id = safe_evolution_int(evo.get('to_id'), 0)
                if target_id <= 0:
                    continue
                target_conditions[target_id] = normalize_evolution_conditions(evo.get('conditions', {}))

            for target_id, condition in target_conditions.items():
                if target_id > 0:
                    f.write(','.join(condition_row(target_id, condition)) + '\n')

    def _write_belong_ap_csv(self, filepath: Path, digimon: DigimonData, tribe_name: Optional[str] = None):
        """Write belong.ap.csv (tribe/species classification)"""
        import csv

        header = 'string2 0,string 1'

        # Use the tribe_name if available, otherwise fallback to "Unknown"
        if tribe_name is None:
            tribe_name = "Unknown"
            if hasattr(digimon, 'tribe_name') and digimon.tribe_name:
                tribe_name = digimon.tribe_name

        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(header + '\n')
            # Use csv.writer to properly handle any special characters
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow([str(digimon.id), tribe_name])





class TemplateSelectionPage(QWizardPage):
    """Step 1: Select template Digimon"""

    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("📋 Step 1: Select Template")
        self.setSubTitle("Choose an existing Digimon to use as a template. The new Digimon will copy all properties from the template.")

        layout = QVBoxLayout()

        # Instructions
        info_label = QLabel(
            "Select a Digimon to use as a template.\n"
            "All stats, skills, traits, and properties will be copied from the template.\n"
            "You can customize them in the following steps."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; padding: 10px; background-color: #f8f9fa; border-radius: 6px;")
        layout.addWidget(info_label)

        # Template selection
        layout.addWidget(QLabel("\n🔍 Template Digimon:"))
        self.template_combo = QComboBox()

        # Populate with all Digimon
        chr_ids = wizard.loader.get_all_digimon_chr_ids()

        # Sort by numeric part
        def sort_key(chr_id):
            try:
                numeric_part = ''
                for char in chr_id.replace('chr', ''):
                    if char.isdigit():
                        numeric_part += char
                    else:
                        break
                return int(numeric_part) if numeric_part else 999999
            except:
                return 999999

        # Deduplicate chr_ids (in case same Digimon appears in base game and DLC)
        chr_ids_unique = list(dict.fromkeys(chr_ids))  # Preserves order, removes duplicates
        chr_ids_sorted = sorted(chr_ids_unique, key=sort_key)

        for chr_id in chr_ids_sorted:
            name = wizard.loader._get_digimon_name_by_chr_id(chr_id)

            # Skip entries where name lookup failed (returns char_key or chr_id)
            if not name or name.startswith("char_") or name == chr_id:
                continue  # Skip - no proper name found

            self.template_combo.addItem(f"{name} ({chr_id})", chr_id)

        # Default to chr805 (Darkshadow)
        default_index = self.template_combo.findData("chr805")
        if default_index >= 0:
            self.template_combo.setCurrentIndex(default_index)

        self.template_combo.currentIndexChanged.connect(self.on_template_changed)
        layout.addWidget(self.template_combo)

        # Preview info
        self.preview_label = QLabel("")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("padding: 10px; background-color: #e7f5ff; border-radius: 6px; margin-top: 10px;")
        layout.addWidget(self.preview_label)

        layout.addStretch()
        self.setLayout(layout)

        # Load initial preview
        self.on_template_changed()

    def on_template_changed(self):
        """Update preview when template changes"""
        chr_id = self.template_combo.currentData()
        if chr_id:
            digimon = self.wizard.loader.get_digimon_by_chr_id(chr_id)
            if digimon:
                # Ensure all model data is loaded
                self.wizard.loader._load_model_data(digimon)
                # Ensure all extended data is loaded
                self.wizard.loader._load_extended_character_data(digimon)

                self.wizard.template_digimon = digimon
                self.preview_label.setText(
                    f"📊 Template Preview:\n"
                    f"Name: {digimon.name}\n"
                    f"ID: {digimon.id} | Stage: {self.wizard.loader.get_generation_name(digimon.stage_id)}\n"
                    f"HP: {digimon.base_hp} | ATK: {digimon.base_atk} | DEF: {digimon.base_def}\n"
                    f"Signature Skills: {len([s for s in digimon.signature_skills if s.get('id', 0) > 0])}\n"
                    f"Model Data: {'✅' if digimon.model_setting_data else '❌'}\n"
                    f"LOD Data: {'✅' if digimon.lod_data else '❌'}\n"
                    f"Field Animation: {'✅' if digimon.field_move_animation_data else '❌'}"
                )

    def validatePage(self):
        """Validate that a template is selected"""
        if not self.wizard.template_digimon:
            QMessageBox.warning(self, "Error", "Please select a template Digimon")
            return False
        return True


class BasicInfoPage(QWizardPage):
    """Step 2: Basic Information"""

    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("📝 Step 2: Basic Information")
        self.setSubTitle("Enter the basic information for your new Digimon")

        layout = QFormLayout()
        layout.setSpacing(15)

        # ID
        self.id_spin = QSpinBox()
        self.id_spin.setRange(1, 9999999)
        # Find next available ID - check both base game and DLC
        existing_ids = list(self.collect_existing_ids())
        next_id = max(existing_ids) + 1 if existing_ids else 1000
        self.id_spin.setValue(next_id)
        layout.addRow("🆔 Digimon ID:", self.id_spin)

        # Name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter Digimon name")
        layout.addRow("📛 Name:", self.name_edit)

        # Character Key
        self.char_key_edit = QLineEdit()
        self.char_key_edit.setPlaceholderText("e.g., char_NEW_DIGIMON")
        layout.addRow("🔑 Character Key:", self.char_key_edit)

        # Chr ID
        self.chr_id_edit = QLineEdit()
        self.chr_id_edit.setPlaceholderText("e.g., chr1000")
        layout.addRow("🔢 Chr ID:", self.chr_id_edit)

        # Field Guide ID
        field_guide_widget = QWidget()
        field_guide_layout = QHBoxLayout(field_guide_widget)
        field_guide_layout.setContentsMargins(0, 0, 0, 0)
        field_guide_layout.setSpacing(8)

        self.field_guide_id_spin = QSpinBox()
        self.field_guide_id_spin.setRange(FIELD_GUIDE_CUSTOM_MIN, FIELD_GUIDE_CUSTOM_MAX)
        self.field_guide_id_spin.setToolTip(
            f"Custom field guide slot. Use {FIELD_GUIDE_CUSTOM_MIN}-{FIELD_GUIDE_CUSTOM_MAX} for new Digimon."
        )
        next_field_guide_id = first_free_field_guide_id(wizard.loader)
        self.field_guide_id_spin.setValue(
            next_field_guide_id if next_field_guide_id != -1 else FIELD_GUIDE_CUSTOM_MIN
        )
        field_guide_layout.addWidget(self.field_guide_id_spin)

        pick_field_guide_button = create_field_guide_slot_button()
        pick_field_guide_button.clicked.connect(self.pick_field_guide_id)
        field_guide_layout.addWidget(pick_field_guide_button)
        field_guide_layout.addStretch()
        layout.addRow("📘 Field Guide ID:", field_guide_widget)

        # Leave Chr ID and Character Key under user control. The ID spinner is
        # only a suggestion; validation below catches collisions before export.

        self.setLayout(layout)

    def pick_field_guide_id(self):
        """Open the occupied/free field guide ID picker."""
        chosen_id = choose_field_guide_id(
            self,
            self.wizard.loader,
            self.field_guide_id_spin.value(),
            self.chr_id_edit.text().strip()
        )
        if chosen_id is not None:
            self.field_guide_id_spin.setValue(chosen_id)

    def collect_existing_ids(self) -> Set[int]:
        """Collect Digimon IDs from base, DLC, and imported mod rows."""
        existing_ids = set(self.wizard.loader.get_all_digimon_ids())
        try:
            for _dlc_id, dlc_status_file in self.wizard.loader.iter_dlc_csv_files(
                "data", "digimon_status", "000_digimon_status_data.csv"
            ):
                dlc_rows = self.wizard.loader.load_csv(dlc_status_file)
                for row in dlc_rows[1:]:
                    if len(row) > 0 and row[0]:
                        try:
                            existing_ids.add(int(row[0]))
                        except ValueError:
                            continue
        except Exception:
            pass

        for digimon in getattr(self.wizard.loader, "imported_digimon", []):
            try:
                existing_ids.add(int(getattr(digimon, "id", 0)))
            except (TypeError, ValueError):
                continue
        return {digimon_id for digimon_id in existing_ids if digimon_id > 0}

    def collect_existing_chr_ids(self) -> Set[str]:
        """Collect Chr IDs from base, DLC, and imported mod rows."""
        existing_chr_ids = set()
        for from_dlc in (False, True):
            try:
                existing_chr_ids.update(
                    chr_id.strip().casefold()
                    for chr_id in self.wizard.loader.get_all_digimon_chr_ids(from_dlc=from_dlc)
                    if chr_id
                )
            except Exception:
                continue

        for digimon in getattr(self.wizard.loader, "imported_digimon", []):
            chr_id = str(getattr(digimon, "chr_id", "")).strip()
            if chr_id:
                existing_chr_ids.add(chr_id.casefold())
        return existing_chr_ids

    def validatePage(self):
        """Validate basic info"""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Error", "Please enter a name for the Digimon")
            return False
        if not self.char_key_edit.text().strip():
            QMessageBox.warning(self, "Error", "Please enter a character key")
            return False
        if not self.chr_id_edit.text().strip():
            QMessageBox.warning(self, "Error", "Please enter a Chr ID")
            return False

        digimon_id = self.id_spin.value()
        if digimon_id in self.collect_existing_ids():
            QMessageBox.warning(
                self,
                "Digimon ID Occupied",
                f"Digimon ID {digimon_id} already exists in base, DLC, or the imported mod.\n\n"
                "Pick a free ID before continuing."
            )
            return False

        chr_id = self.chr_id_edit.text().strip()
        if chr_id.casefold() in self.collect_existing_chr_ids():
            QMessageBox.warning(
                self,
                "Chr ID Occupied",
                f"Chr ID {chr_id} already exists in base, DLC, or the imported mod.\n\n"
                "Pick a free Chr ID before continuing."
            )
            return False

        field_guide_id = self.field_guide_id_spin.value()
        usage = collect_field_guide_usage(self.wizard.loader, self.chr_id_edit.text().strip())
        if field_guide_id in usage:
            QMessageBox.warning(
                self,
                "Field Guide ID Occupied",
                f"Field Guide ID {field_guide_id} is already used by:\n\n"
                + "\n".join(usage[field_guide_id][:12])
                + "\n\nPick a free ID before continuing."
            )
            return False
        return True


class ClassificationPage(QWizardPage):
    """Step 3: Classification"""

    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("🏷️ Step 3: Classification")
        self.setSubTitle("Set the Digimon's stage, type/tribe, personality, and growth pattern")

        layout = QFormLayout()
        layout.setSpacing(15)

        # Stage
        self.stage_combo = QComboBox()
        for i in range(15):  # Stages 0-14 (based on generation_name.mbe CSV)
            stage_name = wizard.loader.get_generation_name(i)
            clean_name = wizard.loader.clean_ui_text(stage_name)
            self.stage_combo.addItem(clean_name, i)
        self.stage_combo.setToolTip("Digimon stage/level (Baby, In-Training, Rookie, Champion, Ultimate, Mega, etc.)")
        layout.addRow("⭐ Stage:", self.stage_combo)

        # Type (for game mechanics)
        self.type_combo = QComboBox()
        for i in range(20):
            type_name = wizard.loader.get_type_name(i)
            if not type_name or type_name == str(i):
                type_name = f"Type {i}"
            else:
                type_name = wizard.loader.clean_ui_text(type_name)
            self.type_combo.addItem(type_name, i)
        self.type_combo.setToolTip("Digimon type (for game mechanics like weaknesses)")
        layout.addRow("🔷 Type:", self.type_combo)

        # Tribe/Species (Belong) - Load unique tribes from belong.mbe
        self.tribe_combo = QComboBox()
        unique_tribes = self._load_unique_tribes(wizard)
        for tribe_name in sorted(unique_tribes):
            self.tribe_combo.addItem(tribe_name)
        self.tribe_combo.setToolTip("Digimon tribe/species classification (shown in Digimon profile)")
        layout.addRow("🦁 Tribe/Species (Belong):", self.tribe_combo)

        # Growth Pattern
        self.growth_combo = QComboBox()
        for i in range(1, 19):  # Growth patterns 1-18
            self.growth_combo.addItem(f"Growth Pattern {i}", i)
        self.growth_combo.setToolTip("Growth curve pattern (1-18) - determines stat growth per level")
        layout.addRow("📈 Growth Pattern:", self.growth_combo)

        # Personality
        self.personality_combo = QComboBox()
        for i in range(17):
            personality_name = wizard.loader.get_personality_name(i)
            clean_name = wizard.loader.clean_ui_text(personality_name)
            self.personality_combo.addItem(clean_name, i)
        self.personality_combo.setToolTip("Digimon personality type (affects skill learning)")
        layout.addRow("🎭 Personality:", self.personality_combo)

        # Set defaults from template
        if wizard.template_digimon:
            stage_idx = self.stage_combo.findData(wizard.template_digimon.stage_id)
            if stage_idx >= 0:
                self.stage_combo.setCurrentIndex(stage_idx)
            type_idx = self.type_combo.findData(wizard.template_digimon.type_id)
            if type_idx >= 0:
                self.type_combo.setCurrentIndex(type_idx)
            personality_idx = self.personality_combo.findData(wizard.template_digimon.personality_id)
            if personality_idx >= 0:
                self.personality_combo.setCurrentIndex(personality_idx)
            growth_idx = self.growth_combo.findData(wizard.template_digimon.growth_pattern_id)
            if growth_idx >= 0:
                self.growth_combo.setCurrentIndex(growth_idx)

            # Load template's tribe from belong.mbe if available
            if hasattr(wizard.template_digimon, 'tribe_name') and wizard.template_digimon.tribe_name:
                tribe_idx = self.tribe_combo.findText(wizard.template_digimon.tribe_name)
                if tribe_idx >= 0:
                    self.tribe_combo.setCurrentIndex(tribe_idx)

        self.setLayout(layout)

    def _load_unique_tribes(self, wizard):
        """Load unique tribe names from belong.mbe"""
        unique_tribes = set()
        try:
            # Try to load from backup folder first (most complete)
            belong_file = wizard.loader._resolve_prefixed_file(Path("backup") / "text" / "belong.mbe" / "000_Sheet1.csv")
            if not belong_file.exists():
                # Try loader's text path
                belong_file = wizard.loader._resolve_prefixed_file(wizard.loader.text_path / "belong.mbe" / "000_Sheet1.csv")

            if belong_file.exists():
                rows = wizard.loader.load_csv(belong_file)
                for row in rows[1:]:  # Skip header
                    if len(row) >= 2:
                        tribe_name = row[1].strip('"')
                        if tribe_name:
                            unique_tribes.add(tribe_name)
        except Exception as e:
            print(f"Error loading tribes: {e}")
            # Fallback to common tribes
            unique_tribes = {"None", "Mammal", "Beast Man", "Dragon", "Machine", "Beast"}

        return unique_tribes

    def initializePage(self):
        """Initialize page with template data when shown"""
        if self.wizard.template_digimon:
            stage_idx = self.stage_combo.findData(self.wizard.template_digimon.stage_id)
            if stage_idx >= 0:
                self.stage_combo.setCurrentIndex(stage_idx)
            type_idx = self.type_combo.findData(self.wizard.template_digimon.type_id)
            if type_idx >= 0:
                self.type_combo.setCurrentIndex(type_idx)
            personality_idx = self.personality_combo.findData(self.wizard.template_digimon.personality_id)
            if personality_idx >= 0:
                self.personality_combo.setCurrentIndex(personality_idx)
            growth_idx = self.growth_combo.findData(self.wizard.template_digimon.growth_pattern_id)
            if growth_idx >= 0:
                self.growth_combo.setCurrentIndex(growth_idx)

            # Load template's tribe from belong.mbe if available
            if hasattr(self.wizard.template_digimon, 'tribe_name') and self.wizard.template_digimon.tribe_name:
                tribe_idx = self.tribe_combo.findText(self.wizard.template_digimon.tribe_name)
                if tribe_idx >= 0:
                    self.tribe_combo.setCurrentIndex(tribe_idx)


class ProfilePage(QWizardPage):
    """Step 4: Profile / Description"""

    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("📖 Step 4: Profile / Description")
        self.setSubTitle("Enter the Digimon's profile text (will be wrapped automatically for display)")

        layout = QVBoxLayout()

        # Info label
        info = QLabel(
            "The profile text will be automatically wrapped to 50 characters per line for proper in-game display.\n"
            "You can enter it as one paragraph or pre-format it with line breaks."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; padding: 8px; background: #f0f0f0; border-radius: 4px; margin-bottom: 10px;")
        layout.addWidget(info)

        # Profile text editor
        layout.addWidget(QLabel("Profile Text:"))
        self.profile_edit = QTextEdit()
        self.profile_edit.setPlaceholderText("Enter Digimon profile/description here...")
        self.profile_edit.setMinimumHeight(200)
        layout.addWidget(self.profile_edit)

        profile_button_layout = QHBoxLayout()
        format_button = QPushButton("Format for Game")
        format_button.setToolTip("Wrap the description to the same narrow lines used by the in-game profile panel")
        format_button.clicked.connect(self.apply_game_format)
        profile_button_layout.addWidget(format_button)
        profile_button_layout.addStretch()
        layout.addLayout(profile_button_layout)

        # Character counter
        self.char_count_label = QLabel("Characters: 0")
        self.char_count_label.setStyleSheet("color: #666; font-size: 9pt;")
        self.profile_edit.textChanged.connect(self.update_char_count)
        layout.addWidget(self.char_count_label)

        layout.addStretch()
        self.setLayout(layout)

    def update_char_count(self):
        """Update character counter"""
        text = self.profile_edit.toPlainText()
        char_count = len(text)
        lines = text.splitlines() or [""]
        longest_line = max(len(line) for line in lines)
        self.char_count_label.setText(
            f"Characters: {char_count} | Lines: {len(lines)} | Longest line: {longest_line}/{PROFILE_WRAP_WIDTH}"
        )
        self.char_count_label.setStyleSheet(
            "color: #b02a37; font-size: 9pt;" if longest_line > PROFILE_WRAP_WIDTH else "color: #666; font-size: 9pt;"
        )

    def apply_game_format(self):
        """Wrap profile text to the in-game profile width."""
        self.profile_edit.setPlainText(format_profile_text_for_game(self.profile_edit.toPlainText()))
        self.update_char_count()

    def initializePage(self):
        """Initialize with template data"""
        if self.wizard.template_digimon and self.wizard.template_digimon.profile_text:
            self.profile_edit.setPlainText(self.wizard.template_digimon.profile_text)

    def validatePage(self):
        """Apply the game format before the review/export pages read this text."""
        self.apply_game_format()
        return True


class StatsPage(QWizardPage):
    """Step 5: Base Stats"""

    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("📊 Step 5: Base Stats")
        self.setSubTitle("Set the base stats for your Digimon")

        layout = QFormLayout()
        layout.setSpacing(15)

        self.hp_spin = QSpinBox()
        self.hp_spin.setRange(1, 9999)
        layout.addRow("❤️ HP:", self.hp_spin)

        self.sp_spin = QSpinBox()
        self.sp_spin.setRange(1, 9999)
        layout.addRow("💙 SP:", self.sp_spin)

        self.atk_spin = QSpinBox()
        self.atk_spin.setRange(1, 9999)
        layout.addRow("⚔️ ATK:", self.atk_spin)

        self.def_spin = QSpinBox()
        self.def_spin.setRange(1, 9999)
        layout.addRow("🛡️ DEF:", self.def_spin)

        self.int_spin = QSpinBox()
        self.int_spin.setRange(1, 9999)
        layout.addRow("🧠 INT:", self.int_spin)

        self.spi_spin = QSpinBox()
        self.spi_spin.setRange(1, 9999)
        layout.addRow("✨ SPI:", self.spi_spin)

        self.spd_spin = QSpinBox()
        self.spd_spin.setRange(1, 9999)
        layout.addRow("⚡ SPD:", self.spd_spin)

        # Set defaults from template
        if wizard.template_digimon:
            self.hp_spin.setValue(wizard.template_digimon.base_hp)
            self.sp_spin.setValue(wizard.template_digimon.base_sp)
            self.atk_spin.setValue(wizard.template_digimon.base_atk)
            self.def_spin.setValue(wizard.template_digimon.base_def)
            self.int_spin.setValue(wizard.template_digimon.base_int)
            self.spi_spin.setValue(wizard.template_digimon.base_spi)
            self.spd_spin.setValue(wizard.template_digimon.base_spd)

        self.setLayout(layout)

    def initializePage(self):
        """Initialize page with template data when shown"""
        if self.wizard.template_digimon:
            self.hp_spin.setValue(self.wizard.template_digimon.base_hp)
            self.sp_spin.setValue(self.wizard.template_digimon.base_sp)
            self.atk_spin.setValue(self.wizard.template_digimon.base_atk)
            self.def_spin.setValue(self.wizard.template_digimon.base_def)
            self.int_spin.setValue(self.wizard.template_digimon.base_int)
            self.spi_spin.setValue(self.wizard.template_digimon.base_spi)
            self.spd_spin.setValue(self.wizard.template_digimon.base_spd)


class ResistancesPage(QWizardPage):
    """Step 5: Elemental Resistances"""

    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("🛡️ Step 6: Elemental Resistances")
        self.setSubTitle("Set elemental resistances (0=Normal, 1=Weak, 2=Very Weak, 3=Resist, 4=Immune)")

        layout = QGridLayout()

        self.resist_widgets = {}
        # IMPORTANT: Order must match CSV columns 7-17 (resNull, resFire, resWater, resGrass, resIce, resElec, resGround, resSteel, resWind, resLight, resDark)
        resistances = [
            ("null", "Null"),
            ("fire", "Fire"),
            ("water", "Water"),
            ("grass", "Plant"),
            ("ice", "Ice"),
            ("elec", "Electric"),
            ("ground", "Earth"),
            ("steel", "Steel"),
            ("wind", "Wind"),
            ("light", "Light"),
            ("dark", "Dark")
        ]

        resistance_labels = {
            0: "Normal (1.0x)",
            1: "Weak (1.5x)",
            2: "Very Weak (2.0x)",
            3: "Resist (0.5x)",
            4: "Immune (0.0x)"
        }

        for i, (resist_key, resist_name) in enumerate(resistances):
            row = i // 2
            col = (i % 2) * 3
            layout.addWidget(QLabel(f"{resist_name}:"), row, col)

            spin = QSpinBox()
            spin.setRange(0, 4)
            spin.setObjectName(f"resist_{resist_key}")
            spin.setToolTip(
                f"Set {resist_name} resistance:\n"
                "0 = Weak (150% damage - 1.5x)\n"
                "1 = Normal (100% damage - 1.0x)\n"
                "2 = Resist (75% damage - 0.75x)\n"
                "3 = Null (50% damage - 0.5x)\n"
                "4 = Absorb (heals instead of damages)"
            )
            self.resist_widgets[resist_key] = spin
            layout.addWidget(spin, row, col + 1)

            value_label = QLabel(resistance_labels[0])
            value_label.setObjectName(f"resist_label_{resist_key}")
            value_label.setStyleSheet("color: #666; font-size: 9pt;")
            layout.addWidget(value_label, row, col + 2)

            spin.valueChanged.connect(lambda v, label=value_label: label.setText(resistance_labels.get(v, "Unknown")))

        # Set defaults from template
        if wizard.template_digimon:
            self.resist_widgets["null"].setValue(wizard.template_digimon.res_null)
            self.resist_widgets["fire"].setValue(wizard.template_digimon.res_fire)
            self.resist_widgets["water"].setValue(wizard.template_digimon.res_water)
            self.resist_widgets["ice"].setValue(wizard.template_digimon.res_ice)
            self.resist_widgets["grass"].setValue(wizard.template_digimon.res_grass)
            self.resist_widgets["wind"].setValue(wizard.template_digimon.res_wind)
            self.resist_widgets["elec"].setValue(wizard.template_digimon.res_elec)
            self.resist_widgets["ground"].setValue(wizard.template_digimon.res_ground)
            self.resist_widgets["steel"].setValue(wizard.template_digimon.res_steel)
            self.resist_widgets["light"].setValue(wizard.template_digimon.res_light)
            self.resist_widgets["dark"].setValue(wizard.template_digimon.res_dark)

        self.setLayout(layout)

    def initializePage(self):
        """Initialize page with template data when shown"""
        if self.wizard.template_digimon:
            self.resist_widgets["null"].setValue(self.wizard.template_digimon.res_null)
            self.resist_widgets["fire"].setValue(self.wizard.template_digimon.res_fire)
            self.resist_widgets["water"].setValue(self.wizard.template_digimon.res_water)
            self.resist_widgets["ice"].setValue(self.wizard.template_digimon.res_ice)
            self.resist_widgets["grass"].setValue(self.wizard.template_digimon.res_grass)
            self.resist_widgets["wind"].setValue(self.wizard.template_digimon.res_wind)
            self.resist_widgets["elec"].setValue(self.wizard.template_digimon.res_elec)
            self.resist_widgets["ground"].setValue(self.wizard.template_digimon.res_ground)
            self.resist_widgets["steel"].setValue(self.wizard.template_digimon.res_steel)
            self.resist_widgets["light"].setValue(self.wizard.template_digimon.res_light)
            self.resist_widgets["dark"].setValue(self.wizard.template_digimon.res_dark)


class SkillsPage(QWizardPage):
    """Step 6: Skills"""

    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("⚔️ Step 7: Skills")
        self.setSubTitle("Configure signature and generic skills for your Digimon")

        layout = QVBoxLayout()

        # Instructions
        info_label = QLabel(
            "Configure the Digimon's skills.\n"
            "Signature skills are unique moves, while generic skills are common abilities.\n"
            "Click 'Add Skill' to select from a list, or enter skill ID manually."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; padding: 10px; background-color: #f8f9fa; border-radius: 6px;")
        layout.addWidget(info_label)

        # Signature Skills
        sig_group = QGroupBox("Signature Skills (up to 12)")
        sig_layout = QVBoxLayout()

        self.signature_skills_editor = SkillEditor("signature", wizard.loader)
        sig_layout.addWidget(self.signature_skills_editor)
        sig_group.setLayout(sig_layout)
        layout.addWidget(sig_group)

        # Generic Skills
        gen_group = QGroupBox("Generic Skills (up to 4)")
        gen_layout = QVBoxLayout()

        self.generic_skills_editor = SkillEditor("generic", wizard.loader)
        gen_layout.addWidget(self.generic_skills_editor)
        gen_group.setLayout(gen_layout)
        layout.addWidget(gen_group)

        layout.addStretch()
        self.setLayout(layout)

    def add_skill(self, skill_type: str):
        """Show dialog to select a skill from list"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Select {skill_type.title()} Skill")
        dialog.setMinimumSize(500, 400)

        layout = QVBoxLayout(dialog)

        # Search box
        search_label = QLabel("Search:")
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("Type to search skills...")
        layout.addWidget(search_label)
        layout.addWidget(search_edit)

        # Skill list
        skill_list = QListWidget()
        layout.addWidget(QLabel("Available Skills:"))
        layout.addWidget(skill_list)

        # Populate skill list
        self.populate_skill_list(skill_list)

        # Filter on search
        def filter_skills(text):
            for i in range(skill_list.count()):
                item = skill_list.item(i)
                item.setHidden(text.lower() not in item.text().lower())
        search_edit.textChanged.connect(filter_skills)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_item = skill_list.currentItem()
            if selected_item:
                skill_id = selected_item.data(Qt.ItemDataRole.UserRole)
                self.add_skill_to_editor(skill_type, skill_id)

    def populate_skill_list(self, skill_list: QListWidget):
        """Populate skill list with all available skills"""
        try:
            skills_file = self.wizard.loader.data_path / "battle_skill.mbe" / "000_battle_skill_list.csv"
            skills_file = self.wizard.loader._resolve_prefixed_file(skills_file)
            if not skills_file.exists():
                return

            rows = self.wizard.loader.load_csv(skills_file)

            for row in rows[1:]:
                if not row or len(row) < 1:
                    continue

                try:
                    skill_id = int(row[0])
                    skill_name = self.wizard.loader.get_skill_name(skill_id)
                    if skill_name and skill_name != f"skill_{skill_id}":
                        skill_name = self.wizard.loader.clean_ui_text(skill_name)
                        item = QListWidgetItem(f"ID {skill_id}: {skill_name}")
                        item.setData(Qt.ItemDataRole.UserRole, skill_id)
                        skill_list.addItem(item)
                except (ValueError, IndexError, TypeError):
                    continue
        except Exception as e:
            print(f"Error loading skills: {e}")

    def add_skill_to_editor(self, skill_type: str, skill_id: int):
        """Add a skill to the appropriate editor"""
        editor = self.signature_skills_editor if skill_type == "signature" else self.generic_skills_editor

        # Find first empty slot
        for i, skill_widget in enumerate(editor.skill_widgets):
            skill_id_widget = skill_widget.findChild(QSpinBox, f"skill_id_{i}")
            if skill_id_widget.value() == 0:
                skill_id_widget.setValue(skill_id)
                editor.update_skill_name(i)
                break

    def initializePage(self):
        """Load skills from template when page is shown"""
        if self.wizard.template_digimon:
            self.signature_skills_editor.load_skills(self.wizard.template_digimon.signature_skills)
            self.generic_skills_editor.load_skills(self.wizard.template_digimon.generic_skills)
            self.signature_skills_editor.update_all_skill_names()
            self.generic_skills_editor.update_all_skill_names()


class EvolutionPage(QWizardPage):
    """Step 7: Evolution"""

    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("🔄 Step 8: Evolution")
        self.setSubTitle("Configure evolution requirements and paths")

        layout = QVBoxLayout()

        # Instructions
        info_label = QLabel(
            "First, set the requirements needed to evolve INTO this new Digimon.\n"
            "Then configure evolution paths (what this Digimon can evolve into) and pre-evolutions."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; padding: 10px; background-color: #f8f9fa; border-radius: 6px;")
        layout.addWidget(info_label)

        # Evolution Requirements section (for obtaining THIS Digimon)
        req_group = QGroupBox("⭐ Requirements to Obtain This Digimon")
        req_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        req_layout = QVBoxLayout()

        req_info = QLabel(
            "These are the requirements that other Digimon must meet to evolve INTO this new Digimon.\n"
            "Leave values at 0 for no requirement."
        )
        req_info.setWordWrap(True)
        req_info.setStyleSheet("color: #555; font-size: 10pt; font-weight: normal;")
        req_layout.addWidget(req_info)

        action_button_style = """
            QPushButton {
                color: white;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                border: none;
                border-radius: 7px;
                padding: 10px 16px;
                font-size: 10pt;
                font-weight: bold;
                min-height: 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5568d3, stop:1 #653b8e);
            }
        """

        edit_req_btn = QPushButton("Edit Evolution Requirements")
        edit_req_btn.setMinimumHeight(44)
        edit_req_btn.setToolTip("Open the full requirements editor for obtaining this Digimon")
        edit_req_btn.setStyleSheet(action_button_style)
        edit_req_btn.clicked.connect(self.edit_evolution_requirements)
        req_layout.addWidget(edit_req_btn)

        self.requirements_label = QLabel("Mode: No Requirements (default)")
        self.requirements_label.setStyleSheet("color: #666; padding: 5px; background: #f0f0f0; border-radius: 3px;")
        self.requirements_label.setWordWrap(True)
        req_layout.addWidget(self.requirements_label)

        req_group.setLayout(req_layout)
        layout.addWidget(req_group)

        # Store the evolution requirements (for THIS Digimon)
        self.evolution_requirements = {
            'mode': 1,  # Default: no requirements
            'tamerLevel': 0,
            'HP': 0, 'SP': 0, 'ATK': 0, 'DEF': 0, 'INT': 0, 'SPI': 0, 'SPD': 0,
            'unknown1': 0, 'unknown2': 0,
            'skillCountValor': 0, 'skillCountPhilantropy': 0,
            'skillCountAmicable': 0, 'skillCountWisdom': 0,
            'needsItem': 0,
            'jogressDbIdA': 0, 'jogressPersonalityA': 0,
            'jogressDbIdB': 0, 'jogressPersonalityB': 0
        }

        # Evolution paths section
        evo_group = QGroupBox("Evolution Paths (what this Digimon evolves into)")
        evo_layout = QVBoxLayout()

        evo_buttons = QHBoxLayout()
        add_evo_btn = QPushButton("Add Evolution Path")
        add_evo_btn.setMinimumHeight(40)
        add_evo_btn.setStyleSheet(action_button_style)
        add_evo_btn.clicked.connect(self.add_evolution)
        remove_evo_btn = QPushButton("Remove Selected Evolution")
        remove_evo_btn.setMinimumHeight(40)
        remove_evo_btn.setStyleSheet(action_button_style)
        remove_evo_btn.clicked.connect(self.remove_evolution)
        evo_buttons.addWidget(add_evo_btn)
        evo_buttons.addWidget(remove_evo_btn)
        evo_buttons.addStretch()
        evo_layout.addLayout(evo_buttons)

        self.evolution_list = QListWidget()
        self.evolution_list.setMaximumHeight(200)
        evo_layout.addWidget(self.evolution_list)
        evo_group.setLayout(evo_layout)
        layout.addWidget(evo_group)

        # Pre-evolution section
        deevo_group = QGroupBox("⬅️ Pre-Evolutions (Digimon that evolve INTO this one)")
        deevo_layout = QVBoxLayout()

        deevo_info = QLabel(
            "💡 Adding a pre-evolution creates an evolution entry where THAT Digimon evolves into THIS one.\n"
            "⚠️ Each Digimon can only have 6 evolution targets. If a Digimon is full, you cannot add it as a pre-evolution."
        )
        deevo_info.setStyleSheet("color: #666; font-size: 9pt; padding: 5px; background-color: #fff3cd; border-radius: 4px;")
        deevo_info.setWordWrap(True)
        deevo_layout.addWidget(deevo_info)

        deevo_buttons = QHBoxLayout()
        add_deevo_btn = QPushButton("Add Pre-Evolution")
        add_deevo_btn.setMinimumHeight(40)
        add_deevo_btn.setStyleSheet(action_button_style)
        add_deevo_btn.clicked.connect(self.add_pre_evolution)
        remove_deevo_btn = QPushButton("Remove Selected Pre-Evolution")
        remove_deevo_btn.setMinimumHeight(40)
        remove_deevo_btn.setStyleSheet(action_button_style)
        remove_deevo_btn.clicked.connect(self.remove_pre_evolution)
        deevo_buttons.addWidget(add_deevo_btn)
        deevo_buttons.addWidget(remove_deevo_btn)
        deevo_buttons.addStretch()
        deevo_layout.addLayout(deevo_buttons)

        self.deevolution_list = QListWidget()
        self.deevolution_list.setMaximumHeight(150)
        deevo_layout.addWidget(self.deevolution_list)
        deevo_group.setLayout(deevo_layout)
        layout.addWidget(deevo_group)

        # Store evolution data
        self.evolution_paths = []
        self.deevolution_sources = []

        layout.addStretch()
        self.setLayout(layout)

    def edit_evolution_requirements(self):
        """Show dialog to edit evolution requirements for THIS Digimon"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Requirements to Obtain This Digimon")
        dialog.setMinimumWidth(500)

        layout = QVBoxLayout(dialog)

        # Scroll area for all fields
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # Info label
        info = QLabel("Configure the requirements needed for other Digimon to evolve INTO this new Digimon.\nLeave values at 0 for no requirement.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; padding: 8px; background: #f0f0f0; border-radius: 4px; margin-bottom: 10px;")
        scroll_layout.addWidget(info)

        # Agent Rank Requirement
        rank_group = QGroupBox("Agent Rank Requirement")
        rank_layout = QFormLayout()
        rank_spin = QSpinBox()
        rank_spin.setRange(1, 8)
        rank_spin.setValue(self.evolution_requirements.get('mode', 1))  # Column 2 is actually Agent Rank
        rank_spin.setToolTip("Required Agent Rank to evolve into this Digimon (1-8)")
        rank_layout.addRow("Agent Rank:", rank_spin)
        rank_group.setLayout(rank_layout)

        # Digimon Level Requirement
        level_group = QGroupBox("Digimon Level Requirement")
        level_layout = QFormLayout()
        digimon_level_spin = QSpinBox()
        digimon_level_spin.setRange(0, 99)
        digimon_level_spin.setValue(self.evolution_requirements.get('tamerLevel', 0))  # tamerLevel is actually Digimon level
        digimon_level_spin.setSuffix(" (0 = no requirement)")
        digimon_level_spin.setToolTip("Required Digimon level to evolve (0 = no level requirement)")
        level_layout.addRow("Digimon Level:", digimon_level_spin)
        level_group.setLayout(level_layout)
        scroll_layout.addWidget(rank_group)
        scroll_layout.addWidget(level_group)

        # Stat Requirements
        stats_group = QGroupBox("Stat Requirements")
        stats_layout = QFormLayout()

        hp_spin = QSpinBox()
        hp_spin.setRange(0, 99999)
        hp_spin.setValue(self.evolution_requirements.get('HP', 0))
        stats_layout.addRow("HP:", hp_spin)

        sp_spin = QSpinBox()
        sp_spin.setRange(0, 99999)
        sp_spin.setValue(self.evolution_requirements.get('SP', 0))
        stats_layout.addRow("SP:", sp_spin)

        atk_spin = QSpinBox()
        atk_spin.setRange(0, 9999)
        atk_spin.setValue(self.evolution_requirements.get('ATK', 0))
        stats_layout.addRow("ATK:", atk_spin)

        def_spin = QSpinBox()
        def_spin.setRange(0, 9999)
        def_spin.setValue(self.evolution_requirements.get('DEF', 0))
        stats_layout.addRow("DEF:", def_spin)

        int_spin = QSpinBox()
        int_spin.setRange(0, 9999)
        int_spin.setValue(self.evolution_requirements.get('INT', 0))
        stats_layout.addRow("INT:", int_spin)

        spi_spin = QSpinBox()
        spi_spin.setRange(0, 9999)
        spi_spin.setValue(self.evolution_requirements.get('SPI', 0))
        stats_layout.addRow("SPI:", spi_spin)

        spd_spin = QSpinBox()
        spd_spin.setRange(0, 9999)
        spd_spin.setValue(self.evolution_requirements.get('SPD', 0))
        stats_layout.addRow("SPD:", spd_spin)

        stats_group.setLayout(stats_layout)
        scroll_layout.addWidget(stats_group)

        extra_group = QGroupBox("Extra Requirement Fields")
        extra_layout = QFormLayout()

        extra_011_spin = QSpinBox()
        extra_011_spin.setRange(0, 9999)
        extra_011_spin.setValue(self.evolution_requirements.get('unknown1', 0))
        extra_011_spin.setToolTip(
            "evolution_condition column 11. Official data only uses this on Lucemon (30) and Parallelmon (40); all known Jogress rows use 0."
        )
        extra_layout.addRow("Column 11:", extra_011_spin)

        extra_012_spin = QSpinBox()
        extra_012_spin.setRange(0, 9999)
        extra_012_spin.setValue(self.evolution_requirements.get('unknown2', 0))
        extra_012_spin.setToolTip(
            "evolution_condition column 12. No nonzero official Base/DLC rows were found in the local data scan."
        )
        extra_layout.addRow("Column 12:", extra_012_spin)

        extra_group.setLayout(extra_layout)
        scroll_layout.addWidget(extra_group)

        # Skill Count Requirements
        skills_group = QGroupBox("Skill Count Requirements (by Personality Type)")
        skills_layout = QFormLayout()

        valor_spin = QSpinBox()
        valor_spin.setRange(0, 999)
        valor_spin.setValue(self.evolution_requirements.get('skillCountValor', 0))
        skills_layout.addRow("Valor Skills:", valor_spin)

        philanthropy_spin = QSpinBox()
        philanthropy_spin.setRange(0, 999)
        philanthropy_spin.setValue(self.evolution_requirements.get('skillCountPhilantropy', 0))
        skills_layout.addRow("Philanthropy Skills:", philanthropy_spin)

        amicable_spin = QSpinBox()
        amicable_spin.setRange(0, 999)
        amicable_spin.setValue(self.evolution_requirements.get('skillCountAmicable', 0))
        skills_layout.addRow("Amicable Skills:", amicable_spin)

        wisdom_spin = QSpinBox()
        wisdom_spin.setRange(0, 999)
        wisdom_spin.setValue(self.evolution_requirements.get('skillCountWisdom', 0))
        skills_layout.addRow("Wisdom Skills:", wisdom_spin)

        skills_group.setLayout(skills_layout)
        scroll_layout.addWidget(skills_group)

        # Item Requirement
        item_group = QGroupBox("Item Requirement")
        item_layout = QFormLayout()
        item_spin = QSpinBox()
        item_spin.setRange(0, 999999)
        item_spin.setValue(self.evolution_requirements.get('needsItem', 0))
        item_spin.setSuffix(" (0 = no item needed)")
        item_layout.addRow("Item ID:", item_spin)
        item_group.setLayout(item_layout)
        scroll_layout.addWidget(item_group)

        # Jogress Requirements
        jogress_group = QGroupBox("Jogress/DNA Digivolution Requirements")
        jogress_layout = QFormLayout()

        jogress_a_id = QSpinBox()
        jogress_a_id.setRange(0, 999999)
        jogress_a_id.setValue(self.evolution_requirements.get('jogressDbIdA', 0))
        jogress_layout.addRow("Jogress Partner A ID:", jogress_a_id)

        jogress_a_personality = QSpinBox()
        jogress_a_personality.setRange(0, 9999)
        jogress_a_personality.setValue(self.evolution_requirements.get('jogressPersonalityA', 0))
        jogress_layout.addRow("Partner A Personality:", jogress_a_personality)

        jogress_b_id = QSpinBox()
        jogress_b_id.setRange(0, 999999)
        jogress_b_id.setValue(self.evolution_requirements.get('jogressDbIdB', 0))
        jogress_layout.addRow("Jogress Partner B ID:", jogress_b_id)

        jogress_b_personality = QSpinBox()
        jogress_b_personality.setRange(0, 9999)
        jogress_b_personality.setValue(self.evolution_requirements.get('jogressPersonalityB', 0))
        jogress_layout.addRow("Partner B Personality:", jogress_b_personality)

        jogress_group.setLayout(jogress_layout)
        scroll_layout.addWidget(jogress_group)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Update requirements
            self.evolution_requirements = {
                'mode': rank_spin.value(),  # Agent Rank (1-8)
                'tamerLevel': digimon_level_spin.value(),  # Digimon Level
                'HP': hp_spin.value(),
                'SP': sp_spin.value(),
                'ATK': atk_spin.value(),
                'DEF': def_spin.value(),
                'INT': int_spin.value(),
                'SPI': spi_spin.value(),
                'SPD': spd_spin.value(),
                'unknown1': extra_011_spin.value(),
                'unknown2': extra_012_spin.value(),
                'skillCountValor': valor_spin.value(),
                'skillCountPhilantropy': philanthropy_spin.value(),
                'skillCountAmicable': amicable_spin.value(),
                'skillCountWisdom': wisdom_spin.value(),
                'needsItem': item_spin.value(),
                'jogressDbIdA': jogress_a_id.value(),
                'jogressPersonalityA': jogress_a_personality.value(),
                'jogressDbIdB': jogress_b_id.value(),
                'jogressPersonalityB': jogress_b_personality.value()
            }

            # Update label
            self.update_requirements_label()

    def update_requirements_label(self):
        """Update the requirements display label"""
        parts = []
        agent_rank = self.evolution_requirements.get('mode', 1)  # mode is actually Agent Rank
        parts.append(f"Agent Rank: {agent_rank}")

        if self.evolution_requirements.get('tamerLevel', 0) > 0:
            parts.append(f"Digimon Lv{self.evolution_requirements['tamerLevel']}")

        stats = []
        for stat in ['HP', 'SP', 'ATK', 'DEF', 'INT', 'SPI', 'SPD']:
            if self.evolution_requirements.get(stat, 0) > 0:
                stats.append(f"{stat}{self.evolution_requirements[stat]}")
        if stats:
            parts.append(", ".join(stats))

        if self.evolution_requirements.get('needsItem', 0) > 0:
            parts.append(f"Item#{self.evolution_requirements['needsItem']}")

        extras = []
        if self.evolution_requirements.get('unknown1', 0) > 0:
            extras.append(f"Col11 {self.evolution_requirements['unknown1']}")
        if self.evolution_requirements.get('unknown2', 0) > 0:
            extras.append(f"Col12 {self.evolution_requirements['unknown2']}")
        if extras:
            parts.append(", ".join(extras))

        jogress_partners = jogress_partner_ids_from_conditions(self.evolution_requirements)
        if jogress_partners:
            parts.append(f"Jogress {' + '.join(f'ID{partner_id}' for partner_id in jogress_partners)}")

        self.requirements_label.setText(" | ".join(parts) if len(parts) > 1 else parts[0])

    def add_evolution(self):
        """Show dialog to select a Digimon to evolve into"""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Select Evolution Target")
            dialog.setMinimumSize(500, 450)

            layout = QVBoxLayout(dialog)

            # Search box
            search_label = QLabel("Search:")
            search_edit = QLineEdit()
            search_edit.setPlaceholderText("Type to search Digimon...")
            layout.addWidget(search_label)
            layout.addWidget(search_edit)

            # Digimon list
            digimon_list = QListWidget()
            layout.addWidget(QLabel("Available Digimon:"))
            layout.addWidget(digimon_list)

            # Populate Digimon list
            self.populate_digimon_list(digimon_list)

            # Filter on search
            def filter_digimon(text):
                for i in range(digimon_list.count()):
                    item = digimon_list.item(i)
                    if item:
                        item.setHidden(text.lower() not in item.text().lower())
            search_edit.textChanged.connect(filter_digimon)

            # Custom ID option (for mod Digimon not in base game)
            custom_id_group = QGroupBox("Or Enter Custom ID")
            custom_id_layout = QHBoxLayout()
            custom_id_label = QLabel("Digimon ID:")
            custom_id_spin = QSpinBox()
            custom_id_spin.setRange(1, 999999)
            custom_id_spin.setValue(1000)
            custom_id_spin.setToolTip("Enter the ID of a custom/modded Digimon")
            custom_id_layout.addWidget(custom_id_label)
            custom_id_layout.addWidget(custom_id_spin)
            custom_id_group.setLayout(custom_id_layout)
            layout.addWidget(custom_id_group)

            # Buttons
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_item = digimon_list.currentItem()
                if selected_item:
                    digimon_id = selected_item.data(Qt.ItemDataRole.UserRole)
                    chr_id = selected_item.data(Qt.ItemDataRole.UserRole + 1)
                    if digimon_id and chr_id:
                        self.add_evolution_path(digimon_id, chr_id)
                else:
                    # No selection in list - use custom ID
                    custom_id = custom_id_spin.value()
                    custom_chr_id = f"chr{custom_id}"
                    self.add_evolution_path(custom_id, custom_chr_id)
        except Exception as e:
            print(f"Error in add_evolution: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"Failed to open evolution dialog: {str(e)}")

    def get_evolution_count_for_digimon(self, digimon_id: int) -> int:
        """Count unique evolution targets in base, DLC, Reloaded II mods, and pending additions."""
        targets: Set[str] = set()

        def add_targets_from_file(evolution_to_file: Path):
            if not evolution_to_file.exists():
                return
            rows = self.wizard.loader.load_csv(evolution_to_file)
            for row in rows[1:]:
                if len(row) <= 3:
                    continue
                source_id = _clean_status_cell(row[1])
                target_id = _clean_status_cell(row[3])
                if source_id == str(digimon_id) and target_id:
                    targets.add(target_id)

        # Check base game evolution_to.csv
        try:
            evolution_to_file = self.wizard.loader._resolve_prefixed_file(self.wizard.loader.data_path / "evolution.mbe" / "001_evolution_to.csv")
            add_targets_from_file(evolution_to_file)

            # Also check DLC files
            for _dlc_id, dlc_path in self.wizard.loader.iter_dlc_csv_files(
                "data", "evolution", "001_evolution_to.csv"
            ):
                add_targets_from_file(dlc_path)

            mods_root = get_default_mod_loader_path()
            if mods_root.exists():
                for mod_dir in sorted((path for path in mods_root.iterdir() if path.is_dir()), key=lambda path: path.name.casefold()):
                    for loader_name in sorted(DSTS_LOADER_DIR_NAMES):
                        evolution_dir = mod_dir / loader_name / "patch" / "data" / "evolution.mbe"
                        if evolution_dir.exists():
                            for mod_evolution_file in sorted(evolution_dir.glob("*_evolution_to.ap.csv")):
                                add_targets_from_file(mod_evolution_file)
        except Exception as e:
            print(f"Error counting evolutions: {e}")

        # Also count pending pre-evolutions we've added that use this Digimon as source
        for deevo in self.deevolution_sources:
            if deevo.get('from_id') == digimon_id:
                targets.add(str(getattr(self.wizard.new_digimon, "id", "")))

        return len(targets)

    def add_pre_evolution(self):
        """Show dialog to select a Digimon that evolves into this one"""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Select Pre-Evolution Source")
            dialog.setMinimumSize(550, 550)

            layout = QVBoxLayout(dialog)

            # Info banner
            info_banner = QLabel(
                "⚠️ IMPORTANT: When you add a pre-evolution, that Digimon gains a new evolution target.\n"
                "Each Digimon can only have 6 evolution targets maximum. Base, DLC, and Reloaded II mod rows are counted."
            )
            info_banner.setStyleSheet("background-color: #fff3cd; padding: 10px; border-radius: 6px; color: #856404;")
            info_banner.setWordWrap(True)
            layout.addWidget(info_banner)

            # Search box
            search_label = QLabel("Search:")
            search_edit = QLineEdit()
            search_edit.setPlaceholderText("Type to search Digimon...")
            layout.addWidget(search_label)
            layout.addWidget(search_edit)

            # Evolution count display
            self.evo_count_label = QLabel("Select a Digimon to see their evolution count")
            self.evo_count_label.setStyleSheet("padding: 5px; font-style: italic; color: #666;")
            layout.addWidget(self.evo_count_label)

            # Digimon list
            digimon_list = QListWidget()
            layout.addWidget(QLabel("Available Digimon:"))
            layout.addWidget(digimon_list)

            # Populate Digimon list with evolution counts
            self.populate_digimon_list_with_evo_count(digimon_list)

            # Update count on selection
            def update_evo_count():
                current = digimon_list.currentItem()
                if current:
                    data = current.data(100)  # Qt.UserRole
                    if data:
                        from_id = data.get('id', 0)
                        count = self.get_evolution_count_for_digimon(from_id)
                        status = "✅ Can add" if count < 6 else "❌ FULL - Cannot add!"
                        color = "#28a745" if count < 6 else "#dc3545"
                        self.evo_count_label.setText(f"Evolution slots: {count}/6 — {status} (base/DLC/mods)")
                        self.evo_count_label.setStyleSheet(f"padding: 5px; font-weight: bold; color: {color};")

            digimon_list.currentItemChanged.connect(lambda: update_evo_count())

            # Filter on search
            def filter_digimon(text):
                for i in range(digimon_list.count()):
                    item = digimon_list.item(i)
                    if item:
                        item.setHidden(text.lower() not in item.text().lower())
            search_edit.textChanged.connect(filter_digimon)

            # Custom ID option (for mod Digimon not in base game)
            custom_id_group = QGroupBox("Or Enter Custom ID (for modded Digimon)")
            custom_id_layout = QHBoxLayout()
            custom_id_label = QLabel("Digimon ID:")
            custom_id_spin = QSpinBox()
            custom_id_spin.setRange(1, 999999)
            custom_id_spin.setValue(1000)
            custom_id_spin.setToolTip("Enter the ID of a custom/modded Digimon")
            custom_id_layout.addWidget(custom_id_label)
            custom_id_layout.addWidget(custom_id_spin)
            custom_id_group.setLayout(custom_id_layout)
            layout.addWidget(custom_id_group)

            # Buttons
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_item = digimon_list.currentItem()
                if selected_item:
                    # Data is stored as a dictionary at role 100
                    data = selected_item.data(100)
                    if data:
                        digimon_id = data.get('id')
                        chr_id = data.get('chr_id')
                        if digimon_id and chr_id:
                            self.add_pre_evolution_source(digimon_id, chr_id)
                else:
                    # No selection in list - use custom ID
                    custom_id = custom_id_spin.value()
                    custom_chr_id = f"chr{custom_id}"
                    self.add_pre_evolution_source(custom_id, custom_chr_id)
        except Exception as e:
            print(f"Error in add_pre_evolution: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"Failed to open pre-evolution dialog: {str(e)}")

    def populate_digimon_list(self, digimon_list: QListWidget):
        """Populate list with all available Digimon"""
        try:
            # Show loading message
            digimon_list.clear()
            digimon_list.addItem("Loading Digimon list...")
            QApplication.processEvents()  # Update UI

            chr_ids = self.wizard.loader.get_all_digimon_chr_ids()

            # Also get DLC Digimon
            try:
                dlc_chr_ids = self.wizard.loader.get_all_digimon_chr_ids(from_dlc=True)
                chr_ids.extend(dlc_chr_ids)
            except:
                pass

            # Remove duplicates
            chr_ids = list(dict.fromkeys(chr_ids))

            digimon_list.clear()

            # Cache status file data to avoid reading multiple times
            id_cache = {}
            try:
                # Load base game IDs
                status_file = self.wizard.loader._resolve_prefixed_file(self.wizard.loader.data_path / "digimon_status.mbe" / "000_digimon_status_data.csv")
                if status_file.exists():
                    rows = self.wizard.loader.load_csv(status_file)
                    for row in rows[1:]:
                        if len(row) > 3 and row[3]:
                            chr_id = row[3].strip('"')
                            if len(row) > 0 and row[0]:
                                try:
                                    digimon_id = int(row[0])
                                    id_cache[chr_id] = digimon_id
                                except:
                                    pass

                # Load DLC IDs
                for _dlc_id, dlc_status_file in self.wizard.loader.iter_dlc_csv_files(
                    "data", "digimon_status", "000_digimon_status_data.csv"
                ):
                    rows = self.wizard.loader.load_csv(dlc_status_file)
                    for row in rows[1:]:
                        if len(row) > 3 and row[3]:
                            chr_id = row[3].strip('"')
                            if len(row) > 0 and row[0]:
                                try:
                                    digimon_id = int(row[0])
                                    id_cache[chr_id] = digimon_id
                                except:
                                    pass
            except Exception as e:
                print(f"Error caching IDs: {e}")

            # Load Digimon data more efficiently - just get names and IDs
            loaded_count = 0
            for chr_id in chr_ids:
                try:
                    # Get name directly without loading full Digimon
                    name = self.wizard.loader._get_digimon_name_by_chr_id(chr_id)
                    if not name or name == chr_id:
                        name = chr_id

                    # Get ID from cache
                    digimon_id = id_cache.get(chr_id, 0)

                    item = QListWidgetItem(f"{name} (ID: {digimon_id}, {chr_id})")
                    item.setData(Qt.ItemDataRole.UserRole, digimon_id)
                    item.setData(Qt.ItemDataRole.UserRole + 1, chr_id)
                    digimon_list.addItem(item)
                    loaded_count += 1

                    # Update UI every 50 items to prevent freezing
                    if loaded_count % 50 == 0:
                        QApplication.processEvents()
                except Exception as e:
                    # Skip individual Digimon that fail to load
                    print(f"Error loading Digimon {chr_id}: {e}")
                    continue

            if digimon_list.count() == 0:
                digimon_list.addItem("(No Digimon found)")
        except Exception as e:
            print(f"Error loading Digimon list: {e}")
            import traceback
            traceback.print_exc()
            digimon_list.clear()
            digimon_list.addItem(f"Error loading Digimon list: {str(e)}")

    def populate_digimon_list_with_evo_count(self, digimon_list: QListWidget):
        """Populate list with all available Digimon including evolution slot count"""
        try:
            # Show loading message
            digimon_list.clear()
            digimon_list.addItem("Loading Digimon list with evolution counts...")
            QApplication.processEvents()

            chr_ids = self.wizard.loader.get_all_digimon_chr_ids()

            # Also get DLC Digimon
            try:
                dlc_chr_ids = self.wizard.loader.get_all_digimon_chr_ids(from_dlc=True)
                chr_ids.extend(dlc_chr_ids)
            except:
                pass

            # Remove duplicates
            chr_ids = list(dict.fromkeys(chr_ids))

            # Cache status file data
            id_cache = {}
            try:
                status_file = self.wizard.loader._resolve_prefixed_file(self.wizard.loader.data_path / "digimon_status.mbe" / "000_digimon_status_data.csv")
                if status_file.exists():
                    rows = self.wizard.loader.load_csv(status_file)
                    for row in rows[1:]:
                        if len(row) > 3 and row[3]:
                            chr_id = row[3].strip('"')
                            if len(row) > 0 and row[0]:
                                try:
                                    digimon_id = int(row[0])
                                    id_cache[chr_id] = digimon_id
                                except:
                                    pass

                # Load DLC IDs
                for _dlc_id, dlc_status_file in self.wizard.loader.iter_dlc_csv_files(
                    "data", "digimon_status", "000_digimon_status_data.csv"
                ):
                    rows = self.wizard.loader.load_csv(dlc_status_file)
                    for row in rows[1:]:
                        if len(row) > 3 and row[3]:
                            chr_id = row[3].strip('"')
                            if len(row) > 0 and row[0]:
                                try:
                                    digimon_id = int(row[0])
                                    id_cache[chr_id] = digimon_id
                                except:
                                    pass
            except Exception as e:
                print(f"Error caching IDs: {e}")

            # Count evolutions for each Digimon
            evo_counts = {}
            try:
                evolution_to_file = self.wizard.loader._resolve_prefixed_file(self.wizard.loader.data_path / "evolution.mbe" / "001_evolution_to.csv")
                if evolution_to_file.exists():
                    rows = self.wizard.loader.load_csv(evolution_to_file)
                    for row in rows[1:]:
                        if len(row) > 1 and row[1]:
                            try:
                                source_id = int(row[1])
                                evo_counts[source_id] = evo_counts.get(source_id, 0) + 1
                            except:
                                pass

                # Also count DLC evolutions
                for _dlc_id, dlc_evo_file in self.wizard.loader.iter_dlc_csv_files(
                    "data", "evolution", "001_evolution_to.csv"
                ):
                    rows = self.wizard.loader.load_csv(dlc_evo_file)
                    for row in rows[1:]:
                        if len(row) > 1 and row[1]:
                            try:
                                source_id = int(row[1])
                                evo_counts[source_id] = evo_counts.get(source_id, 0) + 1
                            except:
                                pass
            except Exception as e:
                print(f"Error counting evolutions: {e}")

            digimon_list.clear()

            loaded_count = 0
            for chr_id in chr_ids:
                try:
                    name = self.wizard.loader._get_digimon_name_by_chr_id(chr_id)
                    if not name or name == chr_id:
                        name = chr_id

                    digimon_id = id_cache.get(chr_id, 0)
                    evo_count = evo_counts.get(digimon_id, 0)

                    # Show slot status
                    if evo_count >= 6:
                        status = "❌ FULL"
                        style_hint = "full"
                    elif evo_count >= 5:
                        status = f"⚠️ {evo_count}/6"
                        style_hint = "warning"
                    else:
                        status = f"✅ {evo_count}/6"
                        style_hint = "ok"

                    item = QListWidgetItem(f"{name} [{status}] (ID: {digimon_id})")
                    item.setData(100, {'id': digimon_id, 'chr_id': chr_id, 'evo_count': evo_count})

                    # Color code items
                    if style_hint == "full":
                        item.setForeground(Qt.GlobalColor.red)
                    elif style_hint == "warning":
                        item.setForeground(Qt.GlobalColor.darkYellow)

                    digimon_list.addItem(item)
                    loaded_count += 1

                    if loaded_count % 50 == 0:
                        QApplication.processEvents()
                except Exception as e:
                    continue

            if digimon_list.count() == 0:
                digimon_list.addItem("(No Digimon found)")
        except Exception as e:
            print(f"Error loading Digimon list with evo counts: {e}")
            import traceback
            traceback.print_exc()
            digimon_list.clear()
            digimon_list.addItem(f"Error: {str(e)}")

    def add_evolution_path(self, to_id: int, to_chr_id: str):
        """Add an evolution path (no longer needs per-path requirements)"""
        try:
            # Check if already exists
            for evo in self.evolution_paths:
                if evo.get('to_id') == to_id:
                    QMessageBox.information(self, "Already Added", f"This evolution path already exists.")
                    return

            # Get Digimon name
            to_name = self.wizard.loader._get_digimon_name_by_chr_id(to_chr_id)
            if not to_name or to_name == to_chr_id:
                to_name = f"Unknown (ID: {to_id})"

            # Add to list (no per-evolution requirements anymore)
            evo_data = {
                'to_id': to_id,
                'to_chr_id': to_chr_id,
                'raw_data': [0, self.wizard.template_digimon.id if self.wizard.template_digimon else 0, 0, to_id]
            }
            self.evolution_paths.append(evo_data)

            # Update display - remove placeholder if present
            if self.evolution_list.count() == 1:
                item = self.evolution_list.item(0)
                if item and item.text().startswith("(No evolution"):
                    self.evolution_list.clear()

            # Simple display without requirements
            self.evolution_list.addItem(f"→ {to_name} (ID: {to_id})")
        except Exception as e:
            print(f"Error adding evolution path: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"Failed to add evolution path: {str(e)}")

    def add_pre_evolution_source(self, from_id: int, from_chr_id: str):
        """Add a pre-evolution source (creates an evolution from that Digimon to this one)"""
        try:
            # Check if already exists
            for deevo in self.deevolution_sources:
                if deevo.get('from_id') == from_id:
                    QMessageBox.information(self, "Already Added", f"This pre-evolution already exists.")
                    return

            # Check the 6-evolution limit for the source Digimon
            evo_count = self.get_evolution_count_for_digimon(from_id)
            if evo_count >= 6:
                from_name = self.wizard.loader._get_digimon_name_by_chr_id(from_chr_id)
                if not from_name or from_name == from_chr_id:
                    from_name = f"Unknown (ID: {from_id})"

                QMessageBox.warning(
                    self,
                    "Evolution Limit Reached",
                    f"❌ Cannot add pre-evolution!\n\n"
                    f"{from_name} already has 6 evolution targets.\n\n"
                    f"Each Digimon can only have 6 evolutions maximum.\n"
                    f"Adding this pre-evolution would make {from_name} evolve into your Digimon, "
                    f"but they have no available evolution slots.\n\n"
                    f"Choose a different Digimon with available slots."
                )
                return

            # Get Digimon name
            from_name = self.wizard.loader._get_digimon_name_by_chr_id(from_chr_id)
            if not from_name or from_name == from_chr_id:
                from_name = f"Unknown (ID: {from_id})"

            # Add to list
            deevo_data = {
                'from_id': from_id,
                'from_chr_id': from_chr_id
            }
            self.deevolution_sources.append(deevo_data)

            # Update display - remove placeholder if present
            if self.deevolution_list.count() == 1 and self.deevolution_list.item(0).text().startswith("(No pre-evolution"):
                self.deevolution_list.clear()

            remaining_slots = 5 - evo_count  # After adding this one
            self.deevolution_list.addItem(f"← {from_name} (ID: {from_id}) [{evo_count + 1}/6 slots used]")
        except Exception as e:
            print(f"Error adding pre-evolution: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"Failed to add pre-evolution: {str(e)}")

    def remove_evolution(self):
        """Remove selected evolution path"""
        current_row = self.evolution_list.currentRow()
        if current_row >= 0 and current_row < len(self.evolution_paths):
            self.evolution_paths.pop(current_row)
            self.evolution_list.takeItem(current_row)

    def remove_pre_evolution(self):
        """Remove selected pre-evolution"""
        current_row = self.deevolution_list.currentRow()
        if current_row >= 0 and current_row < len(self.deevolution_sources):
            self.deevolution_sources.pop(current_row)
            self.deevolution_list.takeItem(current_row)

    def show_evolution_requirements_dialog(self, target_name: str):
        """Show dialog to configure evolution requirements"""
        existing_conditions = normalize_evolution_conditions(getattr(self, "evolution_requirements", {}))
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Evolution Requirements → {target_name}")
        dialog.setMinimumWidth(500)

        layout = QVBoxLayout(dialog)

        # Scroll area for all fields
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # Info label
        info = QLabel("Configure the requirements needed to evolve to this Digimon.\nLeave values at 0 for no requirement.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; padding: 8px; background: #f0f0f0; border-radius: 4px; margin-bottom: 10px;")
        scroll_layout.addWidget(info)

        # Agent Rank (column 2 in evolution_condition.csv)
        mode_group = QGroupBox("Agent Rank Requirement")
        mode_layout = QVBoxLayout()
        mode_combo = QComboBox()
        mode_combo.addItem("Rank 1", 1)
        mode_combo.addItem("Rank 2", 2)
        mode_combo.addItem("Rank 3", 3)
        mode_combo.addItem("Rank 4", 4)
        mode_combo.addItem("Rank 5", 5)
        mode_combo.addItem("Rank 6", 6)
        mode_combo.addItem("Rank 7", 7)
        mode_combo.addItem("Rank 8", 8)
        mode_combo.addItem("Rank 9", 9)
        mode_combo.addItem("Rank 10", 10)
        mode_index = mode_combo.findData(existing_conditions.get('mode', 1))
        mode_combo.setCurrentIndex(mode_index if mode_index >= 0 else 0)
        mode_layout.addWidget(mode_combo)
        mode_group.setLayout(mode_layout)
        scroll_layout.addWidget(mode_group)

        # Tamer Level
        tamer_group = QGroupBox("Tamer Requirements")
        tamer_layout = QFormLayout()
        tamer_level_spin = QSpinBox()
        tamer_level_spin.setRange(0, 99)
        tamer_level_spin.setValue(existing_conditions.get('tamerLevel', 0))
        tamer_level_spin.setSuffix(" (0 = no requirement)")
        tamer_layout.addRow("Tamer Level:", tamer_level_spin)
        tamer_group.setLayout(tamer_layout)
        scroll_layout.addWidget(tamer_group)

        # Stat Requirements
        stats_group = QGroupBox("Stat Requirements")
        stats_layout = QFormLayout()

        hp_spin = QSpinBox()
        hp_spin.setRange(0, 99999)
        hp_spin.setValue(existing_conditions.get('HP', 0))
        hp_spin.setSuffix(" HP")
        stats_layout.addRow("HP:", hp_spin)

        sp_spin = QSpinBox()
        sp_spin.setRange(0, 99999)
        sp_spin.setValue(existing_conditions.get('SP', 0))
        sp_spin.setSuffix(" SP")
        stats_layout.addRow("SP:", sp_spin)

        atk_spin = QSpinBox()
        atk_spin.setRange(0, 9999)
        atk_spin.setValue(existing_conditions.get('ATK', 0))
        atk_spin.setSuffix(" ATK")
        stats_layout.addRow("ATK:", atk_spin)

        def_spin = QSpinBox()
        def_spin.setRange(0, 9999)
        def_spin.setValue(existing_conditions.get('DEF', 0))
        def_spin.setSuffix(" DEF")
        stats_layout.addRow("DEF:", def_spin)

        int_spin = QSpinBox()
        int_spin.setRange(0, 9999)
        int_spin.setValue(existing_conditions.get('INT', 0))
        int_spin.setSuffix(" INT")
        stats_layout.addRow("INT:", int_spin)

        spi_spin = QSpinBox()
        spi_spin.setRange(0, 9999)
        spi_spin.setValue(existing_conditions.get('SPI', 0))
        spi_spin.setSuffix(" SPI")
        stats_layout.addRow("SPI:", spi_spin)

        spd_spin = QSpinBox()
        spd_spin.setRange(0, 9999)
        spd_spin.setValue(existing_conditions.get('SPD', 0))
        spd_spin.setSuffix(" SPD")
        stats_layout.addRow("SPD:", spd_spin)

        stats_group.setLayout(stats_layout)
        scroll_layout.addWidget(stats_group)

        # Extra requirement fields observed in evolution_condition columns 11/12.
        extra_group = QGroupBox("Extra Requirement Fields")
        extra_layout = QFormLayout()

        extra_011_spin = QSpinBox()
        extra_011_spin.setRange(0, 9999)
        extra_011_spin.setValue(existing_conditions.get('unknown1', 0))
        extra_011_spin.setToolTip(
            "evolution_condition column 11. Official data only uses this on Lucemon (30) and Parallelmon (40); all known Jogress rows use 0."
        )
        extra_layout.addRow("Column 11:", extra_011_spin)

        extra_012_spin = QSpinBox()
        extra_012_spin.setRange(0, 9999)
        extra_012_spin.setValue(existing_conditions.get('unknown2', 0))
        extra_012_spin.setToolTip(
            "evolution_condition column 12. No nonzero official Base/DLC rows were found in the local data scan."
        )
        extra_layout.addRow("Column 12:", extra_012_spin)

        extra_group.setLayout(extra_layout)
        scroll_layout.addWidget(extra_group)

        # Skill Count Requirements
        skills_group = QGroupBox("Skill Count Requirements (by Personality)")
        skills_layout = QFormLayout()

        valor_spin = QSpinBox()
        valor_spin.setRange(0, 999)
        valor_spin.setValue(existing_conditions.get('skillCountValor', 0))
        skills_layout.addRow("Valor Skills:", valor_spin)

        philanthropy_spin = QSpinBox()
        philanthropy_spin.setRange(0, 999)
        philanthropy_spin.setValue(existing_conditions.get('skillCountPhilantropy', 0))
        skills_layout.addRow("Philanthropy Skills:", philanthropy_spin)

        amicable_spin = QSpinBox()
        amicable_spin.setRange(0, 999)
        amicable_spin.setValue(existing_conditions.get('skillCountAmicable', 0))
        skills_layout.addRow("Amicable Skills:", amicable_spin)

        wisdom_spin = QSpinBox()
        wisdom_spin.setRange(0, 999)
        wisdom_spin.setValue(existing_conditions.get('skillCountWisdom', 0))
        skills_layout.addRow("Wisdom Skills:", wisdom_spin)

        skills_group.setLayout(skills_layout)
        scroll_layout.addWidget(skills_group)

        # Item Requirement
        item_group = QGroupBox("Item Requirement (Mode 2)")
        item_layout = QFormLayout()
        item_spin = QSpinBox()
        item_spin.setRange(0, 999999)
        item_spin.setValue(existing_conditions.get('needsItem', 0))
        item_spin.setSuffix(" (Item ID, 0 = none)")
        item_layout.addRow("Required Item:", item_spin)
        item_group.setLayout(item_layout)
        scroll_layout.addWidget(item_group)

        # Jogress Requirements
        jogress_group = QGroupBox("Jogress/DNA Digivolution Requirements")
        jogress_layout = QFormLayout()

        jogress_a_id_spin = QSpinBox()
        jogress_a_id_spin.setRange(0, 999999)
        jogress_a_id_spin.setValue(existing_conditions.get('jogressDbIdA', 0))
        jogress_a_id_spin.setSuffix(" (Partner A ID)")
        jogress_layout.addRow("Partner A Digimon ID:", jogress_a_id_spin)

        jogress_a_personality_spin = QSpinBox()
        jogress_a_personality_spin.setRange(0, 99)
        jogress_a_personality_spin.setValue(existing_conditions.get('jogressPersonalityA', 0))
        jogress_a_personality_spin.setSuffix(" (Personality)")
        jogress_layout.addRow("Partner A Personality:", jogress_a_personality_spin)

        jogress_b_id_spin = QSpinBox()
        jogress_b_id_spin.setRange(0, 999999)
        jogress_b_id_spin.setValue(existing_conditions.get('jogressDbIdB', 0))
        jogress_b_id_spin.setSuffix(" (Partner B ID)")
        jogress_layout.addRow("Partner B Digimon ID:", jogress_b_id_spin)

        jogress_b_personality_spin = QSpinBox()
        jogress_b_personality_spin.setRange(0, 99)
        jogress_b_personality_spin.setValue(existing_conditions.get('jogressPersonalityB', 0))
        jogress_b_personality_spin.setSuffix(" (Personality)")
        jogress_layout.addRow("Partner B Personality:", jogress_b_personality_spin)

        jogress_group.setLayout(jogress_layout)
        scroll_layout.addWidget(jogress_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return {
                'mode': mode_combo.currentData(),
                'tamerLevel': tamer_level_spin.value(),
                'HP': hp_spin.value(),
                'SP': sp_spin.value(),
                'ATK': atk_spin.value(),
                'DEF': def_spin.value(),
                'INT': int_spin.value(),
                'SPI': spi_spin.value(),
                'SPD': spd_spin.value(),
                'unknown1': extra_011_spin.value(),
                'unknown2': extra_012_spin.value(),
                'skillCountValor': valor_spin.value(),
                'skillCountPhilantropy': philanthropy_spin.value(),
                'skillCountAmicable': amicable_spin.value(),
                'skillCountWisdom': wisdom_spin.value(),
                'needsItem': item_spin.value(),
                'jogressDbIdA': jogress_a_id_spin.value(),
                'jogressPersonalityA': jogress_a_personality_spin.value(),
                'jogressDbIdB': jogress_b_id_spin.value(),
                'jogressPersonalityB': jogress_b_personality_spin.value()
            }
        return None  # Cancelled

    def _format_requirements_summary(self, conditions: dict) -> str:
        """Format evolution requirements as a short summary"""
        parts = []
        if conditions.get('tamerLevel', 0) > 0:
            parts.append(f"Tamer Lv{conditions['tamerLevel']}")

        stats = []
        for stat in ['HP', 'SP', 'ATK', 'DEF', 'INT', 'SPI', 'SPD']:
            if conditions.get(stat, 0) > 0:
                stats.append(f"{stat}{conditions[stat]}")
        if stats:
            parts.append(", ".join(stats))

        if conditions.get('needsItem', 0) > 0:
            parts.append(f"Item#{conditions['needsItem']}")

        extras = []
        if conditions.get('unknown1', 0) > 0:
            extras.append(f"Col11 {conditions['unknown1']}")
        if conditions.get('unknown2', 0) > 0:
            extras.append(f"Col12 {conditions['unknown2']}")
        if extras:
            parts.append(", ".join(extras))

        jogress_partners = jogress_partner_ids_from_conditions(normalize_evolution_conditions(conditions))
        if jogress_partners:
            parts.append(f"Jogress {' + '.join(f'ID{partner_id}' for partner_id in jogress_partners)}")

        if parts:
            return f"[{'; '.join(parts)}]"
        return "[No requirements]"

    def initializePage(self):
        """Load evolution data from template when page is shown"""
        if not self.wizard.template_digimon:
            return

        digimon = self.wizard.template_digimon

        # Clear existing data
        self.evolution_list.clear()
        self.deevolution_list.clear()
        self.evolution_paths = []
        self.deevolution_sources = []

        # Populate evolution paths (deduplicate by to_id)
        seen_to_ids = set()
        for evo in digimon.evolution_paths:
            to_id = evo.get('to_id', 0)
            if to_id > 0 and to_id not in seen_to_ids:
                seen_to_ids.add(to_id)

                # Get name by numeric ID
                to_name = self.wizard.loader._get_digimon_name_by_id(to_id)
                if not to_name:
                    to_name = f"Unknown (ID: {to_id})"

                # Store evolution data
                evo_data = evo.copy()
                self.evolution_paths.append(evo_data)

                # Build requirements string
                reqs = []
                if 'raw_data' in evo and len(evo['raw_data']) > 2:
                    level_req = evo['raw_data'][2] if len(evo['raw_data']) > 2 else 0
                    if level_req and str(level_req).isdigit() and int(level_req) > 0:
                        reqs.append(f"Lv{level_req}")

                req_str = f" [{', '.join(reqs)}]" if reqs else ""
                self.evolution_list.addItem(f"→ {to_name}{req_str}")

        # Populate de-evolution sources (deduplicate by from_id)
        seen_from_ids = set()
        for deevo in digimon.deevolution_sources:
            from_id = deevo.get('from_id', 0)
            if from_id > 0 and from_id not in seen_from_ids:
                seen_from_ids.add(from_id)

                # Get name by numeric ID
                from_name = self.wizard.loader._get_digimon_name_by_id(from_id)
                if not from_name:
                    from_name = f"Unknown (ID: {from_id})"

                # Store deevolution data
                deevo_data = deevo.copy()
                self.deevolution_sources.append(deevo_data)

                self.deevolution_list.addItem(f"← {from_name} (ID: {from_id})")

        if self.evolution_list.count() == 0:
            self.evolution_list.addItem("(No evolution paths - click 'Add Evolution' to add)")
        if self.deevolution_list.count() == 0:
            self.deevolution_list.addItem("(No pre-evolutions - click 'Add Pre-Evolution' to add)")


class ModelPage(QWizardPage):
    """Step 8: Model & Animation"""

    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("🎨 Step 9: Model & Animation")
        self.setSubTitle("Set model and animation references")

        layout = QFormLayout()
        layout.setSpacing(15)

        # Model ID
        self.model_id_edit = QLineEdit()
        self.model_id_edit.setPlaceholderText("e.g., model_001")
        layout.addRow("🎭 Model ID:", self.model_id_edit)

        # Audio ID (motion_ref in char_info)
        self.motion_id_edit = QLineEdit()
        self.motion_id_edit.setPlaceholderText("e.g., ymc007")
        layout.addRow("🔊 Audio ID:", self.motion_id_edit)

        # Animation Reference
        self.animation_ref_edit = QLineEdit()
        self.animation_ref_edit.setPlaceholderText("e.g., chr805 (which Digimon's animations to use)")
        layout.addRow("🔄 Animation Reference:", self.animation_ref_edit)

        # Info label
        info_label = QLabel("💡 The Animation Reference determines which Digimon's animations this Digimon uses.\nSet to the template's chr_id or another Digimon with similar animations.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 9pt; padding: 10px; background-color: #f8f9fa; border-radius: 6px;")
        layout.addRow("", info_label)

        # Set defaults from template
        if wizard.template_digimon:
            self.model_id_edit.setText(wizard.template_digimon.model_id)
            self.motion_id_edit.setText(wizard.template_digimon.motion_id)
            self.animation_ref_edit.setText(wizard.template_digimon.chr_id)

        self.setLayout(layout)

    def initializePage(self):
        """Initialize page with template data when shown"""
        if self.wizard.template_digimon:
            self.model_id_edit.setText(self.wizard.template_digimon.model_id)
            self.motion_id_edit.setText(self.wizard.template_digimon.motion_id)
            self.animation_ref_edit.setText(self.wizard.template_digimon.chr_id)


class ReviewPage(QWizardPage):
    """Step 9: Review & Export"""

    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("✅ Step 10: Review & Export")
        self.setSubTitle("Review your Digimon settings and export to dsts-loader")

        layout = QVBoxLayout()

        # Review text
        self.review_text = QTextEdit()
        self.review_text.setReadOnly(True)
        self.review_text.setMaximumHeight(400)
        layout.addWidget(self.review_text)

        # Info
        info_label = QLabel(
            "✨ Click 'Finish' to export this Digimon to dsts-loader format.\n"
            "You will be asked to select an export directory.\n"
            "The wizard will create .ap.csv files ready for dsts-loader!"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #495057; padding: 10px; background-color: #e7f5ff; border-radius: 6px; margin-top: 10px;")
        layout.addWidget(info_label)

        self.setLayout(layout)

    def initializePage(self):
        """Update review text when page is shown"""
        template_page = self.wizard.page(0)
        basic_page = self.wizard.page(1)
        class_page = self.wizard.page(2)
        profile_page = self.wizard.page(3)  # New page
        stats_page = self.wizard.page(4)    # Updated index
        resist_page = self.wizard.page(5)   # Updated index
        skills_page = self.wizard.page(6)   # Updated index
        evolution_page = self.wizard.page(7) # Updated index
        model_page = self.wizard.page(8)    # Updated index

        # Get profile text preview (first 100 chars)
        profile_text = profile_page.profile_edit.toPlainText()
        profile_preview = profile_text[:100] + "..." if len(profile_text) > 100 else profile_text

        review_html = f"""
        <h2>📋 Digimon Summary</h2>
        <table style="width: 100%; border-collapse: collapse;">
        <tr><td style="padding: 5px;"><b>Name:</b></td><td style="padding: 5px;">{basic_page.name_edit.text()}</td></tr>
        <tr><td style="padding: 5px;"><b>ID:</b></td><td style="padding: 5px;">{basic_page.id_spin.value()}</td></tr>
        <tr><td style="padding: 5px;"><b>Chr ID:</b></td><td style="padding: 5px;">{basic_page.chr_id_edit.text()}</td></tr>
        <tr><td style="padding: 5px;"><b>Field Guide ID:</b></td><td style="padding: 5px;">{basic_page.field_guide_id_spin.value()}</td></tr>
        <tr><td style="padding: 5px;"><b>Character Key:</b></td><td style="padding: 5px;">{basic_page.char_key_edit.text()}</td></tr>
        <tr><td style="padding: 5px;"><b>Stage:</b></td><td style="padding: 5px;">{class_page.stage_combo.currentText()}</td></tr>
        <tr><td style="padding: 5px;"><b>Type:</b></td><td style="padding: 5px;">{class_page.type_combo.currentText()}</td></tr>
        <tr><td style="padding: 5px;"><b>Personality:</b></td><td style="padding: 5px;">{class_page.personality_combo.currentText()}</td></tr>
        <tr><td style="padding: 5px;"><b>Profile:</b></td><td style="padding: 5px; font-style: italic;">{profile_preview}</td></tr>
        <tr><td style="padding: 5px;"><b>HP:</b></td><td style="padding: 5px;">{stats_page.hp_spin.value()}</td></tr>
        <tr><td style="padding: 5px;"><b>SP:</b></td><td style="padding: 5px;">{stats_page.sp_spin.value()}</td></tr>
        <tr><td style="padding: 5px;"><b>ATK:</b></td><td style="padding: 5px;">{stats_page.atk_spin.value()}</td></tr>
        <tr><td style="padding: 5px;"><b>DEF:</b></td><td style="padding: 5px;">{stats_page.def_spin.value()}</td></tr>
        <tr><td style="padding: 5px;"><b>INT:</b></td><td style="padding: 5px;">{stats_page.int_spin.value()}</td></tr>
        <tr><td style="padding: 5px;"><b>SPI:</b></td><td style="padding: 5px;">{stats_page.spi_spin.value()}</td></tr>
        <tr><td style="padding: 5px;"><b>SPD:</b></td><td style="padding: 5px;">{stats_page.spd_spin.value()}</td></tr>
        <tr><td style="padding: 5px;"><b>Signature Skills:</b></td><td style="padding: 5px;">{len([s for s in skills_page.signature_skills_editor.get_skills() if s.get('id', 0) > 0])}</td></tr>
        <tr><td style="padding: 5px;"><b>Generic Skills:</b></td><td style="padding: 5px;">{len([s for s in skills_page.generic_skills_editor.get_skills() if s.get('id', 0) > 0])}</td></tr>
        <tr><td style="padding: 5px;"><b>Evolution Paths:</b></td><td style="padding: 5px;">{len(evolution_page.evolution_paths)}</td></tr>
        <tr><td style="padding: 5px;"><b>Pre-Evolutions:</b></td><td style="padding: 5px;">{len(evolution_page.deevolution_sources)}</td></tr>
        <tr><td style="padding: 5px;"><b>Animation Reference:</b></td><td style="padding: 5px;">{model_page.animation_ref_edit.text()}</td></tr>
        </table>
        <p><b>Template:</b> {template_page.template_combo.currentText()}</p>
        """

        self.review_text.setHtml(review_html)


class TraitsEditor(QWidget):
    """Widget for editing Digimon traits (boolean flags)"""

    def __init__(self, loader=None):
        super().__init__()
        self.loader = loader
        self.trait_checkboxes = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Title
        title = QLabel("Traits")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # Traits container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QGridLayout(scroll_widget)
        scroll_layout.setContentsMargins(8, 8, 8, 8)
        scroll_layout.setHorizontalSpacing(12)
        scroll_layout.setVerticalSpacing(8)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        for column in range(3):
            scroll_layout.setColumnStretch(column, 1)

        # Trait descriptions for tooltips
        trait_descriptions = {
            0: "Searcher - Find items more easily",
            1: "Fighter - Better at combat",
            2: "Brainy - Higher INT growth",
            3: "Defender - Higher DEF growth",
            4: "Nimble - Higher SPD growth",
            5: "Builder - Better at construction",
            6: "Durable - Higher HP growth",
            7: "Lively - Higher SP growth",
            8: "Fire Specialist - Fire attacks more effective",
            9: "Water Specialist - Water attacks more effective",
            10: "Plant Specialist - Grass attacks more effective",
            11: "Earth Specialist - Ground attacks more effective",
            12: "Wind Specialist - Wind attacks more effective",
            13: "Electricity Specialist - Electric attacks more effective",
            14: "Light Specialist - Light attacks more effective",
            15: "Dark Specialist - Dark attacks more effective"
        }

        # Create 41 trait checkboxes in a grid
        for i in range(41):
            trait_name = f"Trait {i + 1}"
            if self.loader:
                trait_name = self.loader.get_trait_name(i)
                clean_name = self.loader.clean_ui_text(trait_name)
                trait_name = clean_name if clean_name else f"Trait {i + 1}"
            checkbox = QCheckBox(trait_name)
            checkbox.setObjectName(f"trait_{i}")
            checkbox.setMinimumHeight(30)
            checkbox.setFont(QFont("Segoe UI", 10))
            checkbox.setStyleSheet("""
                QCheckBox {
                    padding: 5px 8px;
                    spacing: 8px;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                }
            """)

            # Add tooltip if available
            if i in trait_descriptions:
                checkbox.setToolTip(trait_descriptions[i])
            else:
                checkbox.setToolTip(f"{trait_name} - Check to enable this trait")

            self.trait_checkboxes.append(checkbox)

            row = i // 3
            col = i % 3
            scroll_layout.addWidget(checkbox, row, col)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, 1)

        self.setLayout(layout)

    def load_traits(self, traits: List[bool]):
        """Load traits into checkboxes"""
        for i, checkbox in enumerate(self.trait_checkboxes):
            if i < len(traits):
                checkbox.setChecked(traits[i])
            else:
                checkbox.setChecked(False)

    def get_traits(self) -> List[bool]:
        """Get traits from checkboxes"""
        return [checkbox.isChecked() for checkbox in self.trait_checkboxes]


class DigimonEditor(QMainWindow):
    """Main Digimon Editor window"""

    def __init__(self):
        super().__init__()
        install_spinbox_wheel_guard()
        # Use Base folders for base game data
        self.loader = MBELoader(data_path="Base/data", text_path="Base/text")
        self.exporter = CSVExporter(data_path="Base/data", text_path="Base/text")
        self.current_digimon: Optional[DigimonData] = None
        self.current_digimon_from_dlc = False
        self.active_dsts_loader_root: Optional[Path] = None
        self.active_reloaded_mod_root: Optional[Path] = None
        self.has_unsaved_changes = False
        self._related_source_entries_cache: Optional[List[dict]] = None
        self._evolution_picker_entries_cache: Optional[List[dict]] = None
        self._evolution_char_name_map_cache: Optional[Dict[str, str]] = None
        self._evolution_target_map_cache: Optional[Dict[int, Set[str]]] = None
        self._buff_set_cache: Dict[Tuple[str, float], Dict[int, List[dict]]] = {}
        self._auto_loaded_mod_roots: Set[str] = set()
        self._status_ref_user_edited = False
        self._syncing_status_reference = False
        self._syncing_multilanguage_ui = False
        self._loading_digimon_form = False
        self.localized_text_widgets: Dict[str, Dict[str, QWidget]] = {}
        self.setup_ui()
        self.connect_change_signals()
        self.load_digimon_list()

    def mark_as_modified(self):
        """Mark the current Digimon as having unsaved changes"""
        if self.current_digimon and not self.has_unsaved_changes:
            self.has_unsaved_changes = True
            # Update window title to show unsaved indicator
            current_title = self.windowTitle()
            if not current_title.endswith("*"):
                self.setWindowTitle(current_title + " *")
            # Update current digimon label
            if hasattr(self, 'current_digimon_label'):
                label_text = self.current_digimon_label.text()
                if not label_text.endswith("*"):
                    self.current_digimon_label.setText(label_text + " *")

    def clear_modified_flag(self):
        """Clear the unsaved changes flag"""
        self.has_unsaved_changes = False
        # Remove asterisk from window title
        current_title = self.windowTitle()
        if current_title.endswith(" *"):
            self.setWindowTitle(current_title[:-2])
        # Remove asterisk from label
        if hasattr(self, 'current_digimon_label'):
            label_text = self.current_digimon_label.text()
            if label_text.endswith(" *"):
                self.current_digimon_label.setText(label_text[:-2])

    def refresh_path_settings_ui(self, update_extract_field: bool = False):
        """Update labels/tooltips that show configured shared paths."""
        mods_path = get_default_mod_loader_path()
        extracted_path = get_default_extracted_game_path()
        settings_file = get_path_settings_file()

        if hasattr(self, "export_dlc_button"):
            self.export_dlc_button.setToolTip(
                "Create or copy into a Reloaded II mod folder with ModConfig.json and dsts-loader files.\n"
                "For an imported mod, Save to Loaded Source is enough when you only want to update the same mod.\n"
                f"Configured Mods folder: {mods_path}"
            )

        if hasattr(self, "export_button"):
            self.export_button.setToolTip(
                "Export CSV files\n"
                f"Folder picker starts at: {mods_path}\n"
                "WARNING: This will DELETE and replace all existing files in the destination directory!\n"
                "Only data currently in your DLC folder will be exported."
            )

        if hasattr(self, "configure_paths_button"):
            self.configure_paths_button.setToolTip(
                "Configure per-PC paths used by imports, exports, related assets, and cache cleanup.\n\n"
                f"Reloaded II Mods:\n{mods_path}\n\n"
                f"Extracted Game Folder:\n{extracted_path}\n\n"
                f"Settings file:\n{settings_file}"
            )

        if update_extract_field and hasattr(self, "related_extract_path_edit"):
            self.related_extract_path_edit.setText(str(extracted_path))

    def configure_paths(self):
        """Open the per-PC path settings dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Configure Paths")
        dialog.setMinimumWidth(760)

        layout = QVBoxLayout(dialog)
        info = QLabel(
            "Set these folders for this PC. They are saved in a local JSON file beside DigiTS Helper, "
            "so shared copies of the editor do not need hardcoded personal paths."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #555; padding: 10px; background-color: #eef4ff; border-radius: 6px;")
        layout.addWidget(info)

        form = QGridLayout()
        form.setColumnStretch(1, 1)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(10)

        mods_path_edit = QLineEdit(str(get_default_mod_loader_path()))
        mods_path_edit.setPlaceholderText(str(DEFAULT_MOD_LOADER_PATH))
        mods_path_edit.setToolTip("Folder containing Reloaded II mod folders, for example ...\\Reloaded II\\Mods")

        extracted_path_edit = QLineEdit(str(get_default_extracted_game_path()))
        extracted_path_edit.setPlaceholderText(str(DEFAULT_EXTRACTED_GAME_PATH))
        extracted_path_edit.setToolTip("Root extracted Time Stranger folder containing app_0.dx11, patch.dx11, and DLC folders")

        def browse_path(line_edit: QLineEdit, title: str):
            start = get_existing_directory_start(config_path_from_text(line_edit.text(), Path.cwd()))
            selected = QFileDialog.getExistingDirectory(
                dialog,
                title,
                str(start),
                QFileDialog.Option.ShowDirsOnly
            )
            if selected:
                line_edit.setText(selected)

        mods_browse = QPushButton("Browse...")
        mods_browse.clicked.connect(lambda: browse_path(mods_path_edit, "Select Reloaded II Mods Folder"))
        extracted_browse = QPushButton("Browse...")
        extracted_browse.clicked.connect(lambda: browse_path(extracted_path_edit, "Select Extracted Time Stranger Folder"))

        form.addWidget(QLabel("Reloaded II Mods:"), 0, 0)
        form.addWidget(mods_path_edit, 0, 1)
        form.addWidget(mods_browse, 0, 2)
        form.addWidget(QLabel("Extracted Game Folder:"), 1, 0)
        form.addWidget(extracted_path_edit, 1, 1)
        form.addWidget(extracted_browse, 1, 2)
        layout.addLayout(form)

        settings_path_label = QLabel(f"Settings file: {get_path_settings_file()}")
        settings_path_label.setWordWrap(True)
        settings_path_label.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(settings_path_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        defaults_button = buttons.addButton("Use Defaults", QDialogButtonBox.ButtonRole.ResetRole)
        defaults_button.clicked.connect(lambda: (
            mods_path_edit.setText(str(DEFAULT_MOD_LOADER_PATH)),
            extracted_path_edit.setText(str(DEFAULT_EXTRACTED_GAME_PATH))
        ))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        mods_text = mods_path_edit.text().strip()
        extracted_text = extracted_path_edit.text().strip()
        if not mods_text or not extracted_text:
            QMessageBox.warning(dialog, "Missing Path", "Both paths need a value.")
            return

        mods_path = config_path_from_text(mods_text, DEFAULT_MOD_LOADER_PATH)
        extracted_path = config_path_from_text(extracted_text, DEFAULT_EXTRACTED_GAME_PATH)

        missing = []
        if not mods_path.exists():
            missing.append(f"Reloaded II Mods:\n{mods_path}")
        if not extracted_path.exists():
            missing.append(f"Extracted Game Folder:\n{extracted_path}")
        if missing:
            reply = QMessageBox.question(
                dialog,
                "Path Does Not Exist",
                "These paths do not exist yet:\n\n"
                + "\n\n".join(missing)
                + "\n\nSave them anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            save_path_settings({
                PATH_SETTINGS_MODS_KEY: str(mods_path),
                PATH_SETTINGS_EXTRACTED_KEY: str(extracted_path),
            })
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", f"Could not save path settings:\n\n{exc}")
            return

        self._invalidate_evolution_picker_cache()
        self.refresh_path_settings_ui(update_extract_field=True)
        QMessageBox.information(self, "Paths Saved", "Path settings saved successfully.")

    def validate_digimon_uniqueness(self, original_id: int, original_chr_id: str, original_char_key: str = "") -> bool:
        """Validate that ID, Chr ID, and Character Key are unique."""
        new_id = self.current_digimon.id
        new_chr_id = self.current_digimon.chr_id.strip()
        new_char_key = self.current_digimon.char_key.strip()
        original_chr_id = (original_chr_id or "").strip()
        original_char_key = (original_char_key or "").strip()

        # If values haven't changed, no need to validate
        if (
            new_id == original_id
            and new_chr_id.casefold() == original_chr_id.casefold()
            and new_char_key.casefold() == original_char_key.casefold()
        ):
            return True

        # Check ID uniqueness
        if new_id != original_id:
            used_ids = self._collect_used_digimon_ids()
            if new_id in used_ids:
                QMessageBox.warning(
                    self,
                    "Duplicate ID",
                    f"ID {new_id} already exists in base, DLC, imported entries, or the active mod.\n\n"
                    "Choose a different Digimon ID before saving."
                )
                return False

        # Check chr_id uniqueness
        if new_chr_id.casefold() != original_chr_id.casefold():
            if new_chr_id.casefold() in self._collect_used_chr_ids():
                QMessageBox.warning(
                    self,
                    "Duplicate Chr ID",
                    f"Chr ID '{new_chr_id}' already exists in base, DLC, imported entries, or the active mod.\n\n"
                    "Choose a different Chr ID before saving."
                )
                return False

        # Check Character Key uniqueness. This is separate from Chr ID; text,
        # char_info, and status rows all use it as a join key.
        if new_char_key.casefold() != original_char_key.casefold():
            if new_char_key.casefold() in self._collect_used_char_keys():
                QMessageBox.warning(
                    self,
                    "Duplicate Character Key",
                    f"Character Key '{new_char_key}' already exists in base, DLC, imported entries, or the active mod.\n\n"
                    "Choose a different Character Key before saving."
                )
                return False

        return True

    def connect_change_signals(self):
        """Connect all form widgets to mark_as_modified"""
        # Basic info
        self.id_spin.valueChanged.connect(self.mark_as_modified)
        self.char_key_edit.textChanged.connect(self.mark_as_modified)
        self.chr_id_edit.textChanged.connect(self.mark_as_modified)
        self.name_edit.textChanged.connect(self.mark_as_modified)
        self.name_edit.textChanged.connect(self.sync_english_text_from_basic_info)
        self.stage_combo.currentIndexChanged.connect(self.mark_as_modified)
        self.type_combo.currentIndexChanged.connect(self.mark_as_modified)
        self.personality_combo.currentIndexChanged.connect(self.mark_as_modified)
        self.tribe_combo.currentIndexChanged.connect(self.mark_as_modified)
        self.tribe_combo.currentIndexChanged.connect(self.sync_english_text_from_basic_info)
        self.profile_text_edit.textChanged.connect(self.mark_as_modified)
        self.profile_text_edit.textChanged.connect(self.sync_english_text_from_basic_info)
        self.profile_text_edit.textChanged.connect(self.update_profile_text_stats)
        self.field_guide_id_spin.valueChanged.connect(self.mark_as_modified)
        self.field_guide_id_spin.valueChanged.connect(self.sync_status_reference_to_current_id)
        self.script_id_spin.valueChanged.connect(self.mark_as_modified)
        self.script_id_spin.valueChanged.connect(self.on_status_reference_changed)
        self.id_spin.valueChanged.connect(self.sync_status_reference_to_current_id)

        # Stats
        for widget in self.stat_widgets.values():
            widget.valueChanged.connect(self.mark_as_modified)
        self.growth_pattern_combo.currentIndexChanged.connect(self.mark_as_modified)

        # Resistances
        for widget in self.resist_widgets.values():
            widget.valueChanged.connect(self.mark_as_modified)

        # Model settings
        self.model_id_edit.textChanged.connect(self.mark_as_modified)
        self.motion_id_edit.textChanged.connect(self.mark_as_modified)
        self.animation_ref_edit.textChanged.connect(self.mark_as_modified)

    def on_status_reference_changed(self, value: int):
        """Remember when the user deliberately points column 132 at another Digimon."""
        if getattr(self, "_loading_digimon_form", False) or getattr(self, "_syncing_status_reference", False):
            return

        if hasattr(self, "id_spin") and value == self.id_spin.value():
            self._status_ref_user_edited = False
        else:
            self._status_ref_user_edited = True

    def sync_status_reference_to_current_id(self, *_args):
        """Keep column 132 aligned with the Digimon ID until the user edits it."""
        if (
            getattr(self, "_loading_digimon_form", False)
            or getattr(self, "_syncing_status_reference", False)
            or getattr(self, "_status_ref_user_edited", False)
            or not hasattr(self, "script_id_spin")
            or not hasattr(self, "id_spin")
        ):
            return

        digimon_id = self.id_spin.value()
        if digimon_id <= 0:
            return

        current_ref = self.script_id_spin.value()
        if current_ref == digimon_id:
            return

        self._syncing_status_reference = True
        try:
            self.script_id_spin.blockSignals(True)
            self.script_id_spin.setValue(digimon_id)
        finally:
            self.script_id_spin.blockSignals(False)
            self._syncing_status_reference = False

    def pick_field_guide_id(self):
        """Open the occupied/free field guide ID picker."""
        identity_values = self._current_identity_values()
        chosen_id = choose_field_guide_id(
            self,
            self.loader,
            self.field_guide_id_spin.value(),
            self.chr_id_edit.text().strip(),
            identity_values["chr_ids"],
            identity_values["digimon_ids"],
        )
        if chosen_id is not None:
            self.field_guide_id_spin.setValue(chosen_id)

    def validate_field_guide_id(self) -> bool:
        """Prevent custom field guide ID collisions before saving/exporting."""
        if not hasattr(self, "field_guide_id_spin"):
            return True

        field_guide_id = self.field_guide_id_spin.value()
        if field_guide_id == -1:
            return True
        if 0 <= field_guide_id < FIELD_GUIDE_CUSTOM_MIN:
            return True

        if FIELD_GUIDE_CUSTOM_MIN <= field_guide_id <= FIELD_GUIDE_CUSTOM_MAX:
            identity_values = self._current_identity_values()
            exclude_chr_id = "" if identity_values.get("pending_new_mod_entry") else self.chr_id_edit.text().strip()
            usage = collect_field_guide_usage(
                self.loader,
                exclude_chr_id,
                identity_values["chr_ids"],
                identity_values["digimon_ids"],
            )
            if field_guide_id in usage:
                QMessageBox.warning(
                    self,
                    "Field Guide ID Occupied",
                    f"Field Guide ID {field_guide_id} is already used by:\n\n"
                    + "\n".join(usage[field_guide_id][:12])
                    + "\n\nPick a free ID before saving."
                )
                return False
            return True

        reply = QMessageBox.question(
            self,
            "Field Guide ID Outside Custom Range",
            f"Field Guide ID {field_guide_id} is outside the custom range "
            f"{FIELD_GUIDE_CUSTOM_MIN}-{FIELD_GUIDE_CUSTOM_MAX}.\n\n"
            "Keep this value anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    def format_current_profile_text(self):
        """Wrap the current description to the game profile width."""
        formatted_text = format_profile_text_for_game(self.profile_text_edit.toPlainText())
        if formatted_text != self.profile_text_edit.toPlainText():
            self.profile_text_edit.setPlainText(formatted_text)
            self.mark_as_modified()
        self.update_profile_text_stats()

    def update_profile_text_stats(self):
        """Show whether the current profile has lines that are too wide for the game UI."""
        if not hasattr(self, "profile_text_stats_label"):
            return
        text = self.profile_text_edit.toPlainText()
        lines = text.splitlines() or [""]
        longest_line = max(len(line) for line in lines)
        self.profile_text_stats_label.setText(
            f"Lines: {len(lines)} | Longest: {longest_line}/{PROFILE_WRAP_WIDTH}"
        )
        self.profile_text_stats_label.setStyleSheet(
            "color: #b02a37; font-size: 9pt;" if longest_line > PROFILE_WRAP_WIDTH else "color: #666; font-size: 9pt;"
        )

    def setup_ui(self):
        self.setWindowTitle("DTS Creator - Digimon Editor")
        # Set initial size smaller to fit most screens, window is resizable
        self.setGeometry(100, 100, 1400, 800)

        # Modern stylesheet for the entire application
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f7fa;
            }
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QTabWidget::pane {
                border: 2px solid #667eea;
                border-radius: 8px;
                background-color: white;
                padding: 5px;
            }
            QTabBar::tab {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f8f9fa, stop:1 #e9ecef);
                color: #495057;
                border: 2px solid #dee2e6;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 20px;
                margin-right: 2px;
                font-weight: bold;
                font-size: 11pt;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border-color: #667eea;
            }
            QTabBar::tab:hover:!selected {
                background: #f1f3f5;
            }

            /* Modern Input Fields */
            QLineEdit, QSpinBox, QDoubleSpinBox {
                background-color: white;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                padding: 8px;
                font-size: 10pt;
                color: #495057;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #667eea;
                background-color: #f8f9fa;
            }
            QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
                background-color: #e9ecef;
                color: #adb5bd;
            }

            /* ComboBox Styling */
            QComboBox {
                background-color: white;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                padding: 8px;
                font-size: 10pt;
                color: #495057;
            }
            QComboBox:hover {
                border-color: #cbd3da;
            }
            QComboBox:focus {
                border-color: #667eea;
                background-color: #f8f9fa;
            }
            QComboBox::drop-down {
                border: none;
            }

            /* Group Box Styling */
            QGroupBox {
                font-weight: bold;
                border: 2px solid #667eea;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
                font-size: 11pt;
            }
            QGroupBox::title {
                color: #667eea;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }

            /* Scrollbars */
            QScrollBar:vertical {
                background: #f1f3f5;
                width: 16px;
                margin: 2px;
                border-radius: 7px;
            }
            QScrollBar::handle:vertical {
                background: #8b94d6;
                min-height: 36px;
                border-radius: 7px;
            }
            QScrollBar::handle:vertical:hover {
                background: #667eea;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
                background: transparent;
            }
            QScrollBar:horizontal {
                background: #f1f3f5;
                height: 14px;
                margin: 2px;
                border-radius: 7px;
            }
            QScrollBar::handle:horizontal {
                background: #8b94d6;
                min-width: 36px;
                border-radius: 7px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #667eea;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0px;
                border: none;
                background: transparent;
            }

            /* Modern Buttons */
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5568d3, stop:1 #653b8e);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a5bc4, stop:1 #563380);
            }
            QPushButton:disabled {
                background: #e9ecef;
                color: #adb5bd;
            }

            /* List Widget Styling */
            QListWidget {
                background-color: white;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                margin: 2px;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background-color: #e7f5ff;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
            }

            /* Label Styling */
            QLabel {
                color: #495057;
            }
        """)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Left panel - Digimon list
        left_panel = self.create_left_panel()
        main_layout.addWidget(left_panel, 1)

        # Right panel - Editor
        right_panel = self.create_right_panel()
        main_layout.addWidget(right_panel, 3)

    def create_left_panel(self) -> QWidget:
        """Create the left panel with Digimon list"""
        panel = QWidget()
        panel.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 12px;
                border: 2px solid #dee2e6;
            }
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Title
        title = QLabel("📚 Digimon Database")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("""
            QLabel {
                color: #667eea;
                padding: 12px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f8f9fa, stop:1 #e9ecef);
                border-radius: 8px;
                border: 2px solid #dee2e6;
            }
        """)
        layout.addWidget(title)

        # Source selector (Base Game vs DLC)
        source_container = QWidget()
        source_container.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-radius: 8px;
                border: 2px solid #dee2e6;
                padding: 8px;
            }
        """)
        source_layout = QHBoxLayout(source_container)
        source_layout.setContentsMargins(10, 5, 10, 5)

        source_label = QLabel("📂 Source:")
        source_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        source_label.setStyleSheet("border: none; background: transparent; color: #667eea;")
        source_layout.addWidget(source_label)

        self.source_combo = QComboBox()
        self.source_combo.addItem("Base + DLC + Mods", "all")
        self.source_combo.addItem("Base Game", "base")
        self.source_combo.addItem("DLC (addcont_01-03,17)", "dlc")
        self.source_combo.addItem("Mods Folder", "mods")
        self.source_combo.setToolTip(
            "Select which Digimon to view:\n"
            "• Base + DLC + Mods - Combined list, including Reloaded II mod entries\n"
            "• Base Game - Original game Digimon\n"
            "• DLC - addcont_01-03 and addcont_17 Digimon\n"
            "• Mods Folder - Digimon found in configured Reloaded II mod folders\n\n"
            "Saving/removal follows the loaded Digimon source"
        )
        self.source_combo.currentIndexChanged.connect(self.load_digimon_list)
        self.source_combo.currentIndexChanged.connect(self.on_source_changed)
        self.source_combo.setStyleSheet("""
            QComboBox {
                border: none;
                background: white;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 10pt;
                color: #333333;
            }
            QComboBox:hover {
                background: #f1f3f5;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background: white;
                color: #333333;
                selection-background-color: #667eea;
                selection-color: white;
            }
            QComboBox QAbstractItemView::item {
                color: #333333;
                padding: 5px;
            }
        """)
        # Fix for Windows 11 - explicitly set view palette
        source_view = self.source_combo.view()
        source_palette = source_view.palette()
        source_palette.setColor(QPalette.ColorRole.Text, QColor("#333333"))
        source_palette.setColor(QPalette.ColorRole.Base, QColor("white"))
        source_view.setPalette(source_palette)
        source_layout.addWidget(self.source_combo)
        layout.addWidget(source_container)

        # Sort selector
        sort_container = QWidget()
        sort_container.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-radius: 8px;
                border: 2px solid #dee2e6;
                padding: 8px;
            }
        """)
        sort_layout = QHBoxLayout(sort_container)
        sort_layout.setContentsMargins(10, 5, 10, 5)

        sort_label = QLabel("↕ Sort:")
        sort_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        sort_label.setStyleSheet("border: none; background: transparent; color: #667eea;")
        sort_layout.addWidget(sort_label)

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Name", "name")
        self.sort_combo.addItem("Chr ID", "chr_id")
        self.sort_combo.setToolTip("Sort the Digimon list by display name or chr ID")
        self.sort_combo.currentIndexChanged.connect(lambda: self.refresh_digimon_list_view())
        self.sort_combo.setStyleSheet(self.source_combo.styleSheet())
        sort_view = self.sort_combo.view()
        sort_palette = sort_view.palette()
        sort_palette.setColor(QPalette.ColorRole.Text, QColor("#333333"))
        sort_palette.setColor(QPalette.ColorRole.Base, QColor("white"))
        sort_view.setPalette(sort_palette)
        sort_layout.addWidget(self.sort_combo)
        layout.addWidget(sort_container)

        # Search box
        search_container = QWidget()
        search_container.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-radius: 8px;
                border: 2px solid #dee2e6;
                padding: 5px;
            }
        """)
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(10, 5, 10, 5)

        search_icon = QLabel("🔎")
        search_icon.setFont(QFont("Segoe UI", 12))
        search_icon.setStyleSheet("border: none; background: transparent;")
        search_layout.addWidget(search_icon)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search Digimon...")
        self.search_box.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-size: 11pt;
                padding: 5px;
                color: #495057;
            }
            QLineEdit:focus {
                color: #667eea;
            }
        """)
        self.search_box.textChanged.connect(self.filter_digimon_list)
        search_layout.addWidget(self.search_box)
        layout.addWidget(search_container)

        # Digimon list
        self.digimon_list = QComboBox()
        self.digimon_list.currentTextChanged.connect(self.on_digimon_selected)
        self.digimon_list.setStyleSheet("""
            QComboBox {
                background: white;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                padding: 10px;
                font-size: 11pt;
                color: #333333;
            }
            QComboBox:hover {
                border-color: #cbd3da;
                background: #f8f9fa;
            }
            QComboBox:focus {
                border-color: #667eea;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QComboBox QAbstractItemView {
                background: white;
                color: #333333;
                selection-background-color: #667eea;
                selection-color: white;
                border: 1px solid #dee2e6;
                padding: 5px;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px;
                color: #333333;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #e9ecef;
                color: #333333;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #667eea;
                color: white;
            }
        """)
        # Fix for Windows 11 - explicitly set view palette to ensure text is visible
        view = self.digimon_list.view()
        palette = view.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor("#333333"))
        palette.setColor(QPalette.ColorRole.Base, QColor("white"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#667eea"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
        view.setPalette(palette)
        layout.addWidget(self.digimon_list)

        # Buttons with modern styling
        button_style = """
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {color1}, stop:1 {color2});
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-weight: bold;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {hover1}, stop:1 {hover2});
            }}
            QPushButton:disabled {{
                background: #e9ecef;
                color: #adb5bd;
            }}
        """

        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)

        self.load_button = QPushButton("📖 Load Selected")
        self.load_button.clicked.connect(self.load_selected_digimon)
        self.load_button.setToolTip("Load the selected Digimon for editing")
        self.load_button.setStyleSheet(button_style.format(
            color1="#667eea", color2="#764ba2",
            hover1="#5568d3", hover2="#653b8e"
        ))
        button_layout.addWidget(self.load_button)

        self.add_selected_to_mod_button = QPushButton("➕ Add Selected as New Entry")
        self.add_selected_to_mod_button.clicked.connect(self.add_selected_to_active_mod)
        self.add_selected_to_mod_button.setEnabled(False)
        self.add_selected_to_mod_button.setToolTip(
            "Load the selected base/DLC/imported Digimon as a pending entry for the active mod.\n"
            "You choose the new ID, Chr ID, Character Key, and Field Guide slot before saving."
        )
        self.add_selected_to_mod_button.setStyleSheet(button_style.format(
            color1="#14b8a6", color2="#0f766e",
            hover1="#0f9f94", hover2="#115e59"
        ))
        button_layout.addWidget(self.add_selected_to_mod_button)

        self.new_button = QPushButton("➕ Create New")
        self.new_button.clicked.connect(self.launch_creation_wizard)
        self.new_button.setToolTip(
            "Create a new Digimon using the step-by-step wizard.\n"
            "If a mod is loaded, the wizard defaults to that mod and merges the new Digimon into it."
        )
        self.new_button.setStyleSheet(button_style.format(
            color1="#10b981", color2="#059669",
            hover1="#059669", hover2="#047857"
        ))
        button_layout.addWidget(self.new_button)

        self.import_button = QPushButton("📥 Import Mod / dsts-loader")
        self.import_button.clicked.connect(self.import_from_dsts_loader)
        self.import_button.setToolTip(
            "Import Digimon from a Reloaded II mod folder or its dsts-loader payload.\n"
            "Imported Digimon remember this folder for Save Changes."
        )
        self.import_button.setStyleSheet(button_style.format(
            color1="#f59e0b", color2="#d97706",
            hover1="#d97706", hover2="#b45309"
        ))
        button_layout.addWidget(self.import_button)

        self.remove_selected_from_mod_button = QPushButton("🗑️ Remove Selected from Mod")
        self.remove_selected_from_mod_button.clicked.connect(self.remove_selected_from_active_mod)
        self.remove_selected_from_mod_button.setEnabled(False)
        self.remove_selected_from_mod_button.setToolTip(
            "Remove the selected imported Digimon from its Reloaded II/dsts-loader mod files.\n"
            "Use this to clean up entries that were added by mistake."
        )
        self.remove_selected_from_mod_button.setStyleSheet(button_style.format(
            color1="#ef4444", color2="#b91c1c",
            hover1="#dc2626", hover2="#991b1b"
        ))
        button_layout.addWidget(self.remove_selected_from_mod_button)

        self.remove_button = QPushButton("🗑️ Remove from DLC")
        self.remove_button.clicked.connect(self.remove_digimon_from_dlc)
        self.remove_button.setEnabled(False)
        self.remove_button.setToolTip("Permanently delete this Digimon from DLC files\nOnly works for DLC Digimon")
        self.remove_button.setStyleSheet(button_style.format(
            color1="#f5576c", color2="#f093fb",
            hover1="#e34556", hover2="#de7fe9"
        ))
        button_layout.addWidget(self.remove_button)

        self.save_button = QPushButton("💾 Save to Loaded Source")
        self.save_button.clicked.connect(self.save_current_digimon)
        self.save_button.setEnabled(False)
        self.save_button.setToolTip(
            "Update the currently loaded source.\n"
            "• Base Game -> extracted base files\n"
            "• DLC -> helper DLC workspace\n"
            "• Imported/active mod -> same remembered dsts-loader payload"
        )
        self.save_button.setStyleSheet(button_style.format(
            color1="#f093fb", color2="#f5576c",
            hover1="#de7fe9", hover2="#e34556"
        ))
        button_layout.addWidget(self.save_button)

        # Separator line
        separator = QWidget()
        separator.setFixedHeight(2)
        separator.setStyleSheet("background-color: #dee2e6; border-radius: 1px;")
        button_layout.addWidget(separator)

        self.export_dlc_button = QPushButton("📦 Export / Copy Mod")
        self.export_dlc_button.clicked.connect(self.export_to_dlc)
        self.export_dlc_button.setEnabled(False)
        self.export_dlc_button.setToolTip(
            "Create or copy into a Reloaded II mod folder with ModConfig.json and dsts-loader files.\n"
            "For an imported mod, Save to Loaded Source is enough when you only want to update the same mod.\n"
            f"Default folder: {get_default_mod_loader_path()}"
        )
        self.export_dlc_button.setStyleSheet(button_style.format(
            color1="#4CAF50", color2="#45a049",
            hover1="#45a049", hover2="#3d8b40"
        ))
        button_layout.addWidget(self.export_dlc_button)

        # Disabled for now: these utility actions are too easy to hit from the
        # main editor and are not part of the normal Reloaded II mod workflow.
        # self.export_button = QPushButton("📄 Export CSV")
        # self.export_button.clicked.connect(self.export_csv)
        # self.export_button.setToolTip(
        #     "Export CSV files\n"
        #     f"Folder picker starts at: {get_default_mod_loader_path()}\n"
        #     "⚠️ WARNING: This will DELETE and replace all existing files in the destination directory!\n"
        #     "Only data currently in your DLC folder will be exported."
        # )
        # self.export_button.setStyleSheet(button_style.format(
        #     color1="#fa709a", color2="#fee140",
        #     hover1="#e85c89", hover2="#ecd32f"
        # ))
        # button_layout.addWidget(self.export_button)

        # self.repack_button = QPushButton("📦 Repack to MBE Files")
        # self.repack_button.clicked.connect(self.repack_mbe_files)
        # self.repack_button.setToolTip("Repack DLC CSV files back into .mbe format\nRequired after making DLC changes")
        # self.repack_button.setStyleSheet(button_style.format(
        #     color1="#667eea", color2="#764ba2",
        #     hover1="#5568d3", hover2="#653b8e"
        # ))
        # button_layout.addWidget(self.repack_button)

        layout.addLayout(button_layout)
        layout.addStretch()

        self.configure_paths_button = QPushButton("⚙️ Configure Paths")
        self.configure_paths_button.clicked.connect(self.configure_paths)
        self.configure_paths_button.setMinimumHeight(42)
        self.configure_paths_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                color: #333333;
                border: 2px solid #adb5bd;
                border-radius: 8px;
                padding: 10px 14px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                border-color: #667eea;
                background-color: #eef4ff;
            }
        """)
        layout.addWidget(self.configure_paths_button)
        self.refresh_path_settings_ui()

        return panel

    def create_right_panel(self) -> QWidget:
        """Create the right panel with editor tabs"""
        panel = QWidget()
        panel.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 12px;
                border: 2px solid #dee2e6;
            }
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Current Digimon info header
        self.current_digimon_label = QLabel("📂 No Digimon loaded")
        self.current_digimon_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.current_digimon_label.setStyleSheet("""
            QLabel {
                color: white;
                padding: 15px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 8px;
                border: none;
            }
        """)
        self.current_digimon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.current_digimon_label)

        # Tab widget
        self.tab_widget = QTabWidget()

        # Basic Info Tab
        self.basic_tab = self.create_basic_tab()
        self.tab_widget.addTab(self.basic_tab, "📝 Basic Info")

        # Stats Tab
        self.stats_tab = self.create_stats_tab()
        self.tab_widget.addTab(self.stats_tab, "📊 Stats")

        # Skills Tab
        self.skills_tab = self.create_skills_tab()
        self.tab_widget.addTab(self.skills_tab, "⚡ Skills")

        # Advanced Skills Tab
        self.advanced_skills_tab = self.create_advanced_skills_tab()
        self.tab_widget.addTab(self.advanced_skills_tab, "🎯 Advanced Skills")

        # Traits Tab
        self.traits_tab = TraitsEditor(self.loader)
        self.tab_widget.addTab(self.traits_tab, "✨ Traits")

        # Model Tab
        self.model_tab = self.create_model_tab()
        self.tab_widget.addTab(self.model_tab, "🎨 Model & Animation")

        # Evolution Tab
        self.evolution_tab = self.create_evolution_tab()
        self.tab_widget.addTab(self.evolution_tab, "🔄 Evolution")

        # Battle Tab
        self.battle_tab = self.create_battle_tab()
        self.tab_widget.addTab(self.battle_tab, "⚔️ Battle Data")

        # Multi Language Tab
        self.multi_language_tab = self.create_multi_language_tab()
        self.tab_widget.addTab(self.multi_language_tab, "🌐 Other Languages")

        layout.addWidget(self.tab_widget)

        return panel

    def create_basic_tab(self) -> QWidget:
        """Create basic information tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)

        # Main Information Group
        main_info_group = QGroupBox("📋 Main Information")
        main_info_layout = QGridLayout(main_info_group)
        main_info_layout.setSpacing(10)

        # ID
        id_label = QLabel("🆔 ID:")
        id_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        main_info_layout.addWidget(id_label, 0, 0)
        self.id_spin = QSpinBox()
        self.id_spin.setRange(0, 9999999)
        main_info_layout.addWidget(self.id_spin, 0, 1)

        # Character Key
        char_key_label = QLabel("🔑 Character Key:")
        char_key_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        main_info_layout.addWidget(char_key_label, 1, 0)
        self.char_key_edit = QLineEdit()
        main_info_layout.addWidget(self.char_key_edit, 1, 1)

        # Chr ID
        chr_id_label = QLabel("🔢 Chr ID:")
        chr_id_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        main_info_layout.addWidget(chr_id_label, 2, 0)
        self.chr_id_edit = QLineEdit()
        main_info_layout.addWidget(self.chr_id_edit, 2, 1)

        # Name
        name_label = QLabel("📛 Name:")
        name_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        main_info_layout.addWidget(name_label, 3, 0)
        self.name_edit = QLineEdit()
        main_info_layout.addWidget(self.name_edit, 3, 1)

        # Field Guide ID
        field_guide_label = QLabel("📘 Field Guide ID:")
        field_guide_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        main_info_layout.addWidget(field_guide_label, 4, 0)

        field_guide_widget = QWidget()
        field_guide_layout = QHBoxLayout(field_guide_widget)
        field_guide_layout.setContentsMargins(0, 0, 0, 0)
        field_guide_layout.setSpacing(8)

        self.field_guide_id_spin = QSpinBox()
        self.field_guide_id_spin.setRange(-1, 99999)
        self.field_guide_id_spin.setValue(-1)
        self.field_guide_id_spin.setToolTip(
            f"Column {FIELD_GUIDE_ID_COLUMN} in 000_digimon_status_data.ap.csv. "
            f"Use {FIELD_GUIDE_CUSTOM_MIN}-{FIELD_GUIDE_CUSTOM_MAX} for custom Digimon."
        )
        field_guide_layout.addWidget(self.field_guide_id_spin)

        pick_field_guide_button = create_field_guide_slot_button()
        pick_field_guide_button.clicked.connect(self.pick_field_guide_id)
        field_guide_layout.addWidget(pick_field_guide_button)
        field_guide_layout.addStretch()
        main_info_layout.addWidget(field_guide_widget, 4, 1)

        layout.addWidget(main_info_group)

        # Classification Group
        classification_group = QGroupBox("🏷️ Classification")
        classification_layout = QGridLayout(classification_group)
        classification_layout.setSpacing(10)

        # Stage with dropdown
        stage_label = QLabel("⭐ Stage:")
        stage_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        classification_layout.addWidget(stage_label, 0, 0)
        self.stage_combo = QComboBox()
        self.populate_stage_dropdown()
        classification_layout.addWidget(self.stage_combo, 0, 1)

        # Type ID with dropdown
        type_label = QLabel("🔷 Type:")
        type_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        classification_layout.addWidget(type_label, 1, 0)
        self.type_combo = QComboBox()
        self.populate_type_dropdown()
        classification_layout.addWidget(self.type_combo, 1, 1)

        # Personality with dropdown
        personality_label = QLabel("🎭 Personality:")
        personality_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        classification_layout.addWidget(personality_label, 2, 0)
        self.personality_combo = QComboBox()
        self.populate_personality_dropdown()
        classification_layout.addWidget(self.personality_combo, 2, 1)

        # Tribe/Belong with dropdown
        tribe_label = QLabel("🦁 Tribe (Belong):")
        tribe_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        classification_layout.addWidget(tribe_label, 3, 0)
        self.tribe_combo = QComboBox()
        self.populate_tribe_dropdown()
        self.tribe_combo.setToolTip("Tribe/species classification shown in Digimon profile")
        classification_layout.addWidget(self.tribe_combo, 3, 1)

        layout.addWidget(classification_group)

        # Profile/Description Group
        profile_group = QGroupBox("📖 Profile / Description")
        profile_group.setStyleSheet("""
            QGroupBox {
                border-color: #84fab0;
            }
            QGroupBox::title {
                color: #2c9558;
            }
        """)
        profile_layout = QVBoxLayout(profile_group)

        self.profile_text_edit = QTextEdit()
        self.profile_text_edit.setPlaceholderText("Enter Digimon description/profile text...")
        self.profile_text_edit.setMinimumHeight(240)
        self.profile_text_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                padding: 10px;
                font-size: 10pt;
                color: #495057;
            }
            QTextEdit:focus {
                border-color: #84fab0;
                background-color: #f8f9fa;
            }
        """)
        profile_layout.addWidget(self.profile_text_edit, 1)

        profile_tools_layout = QHBoxLayout()
        format_profile_button = QPushButton("Format Text")
        format_profile_button.setObjectName("formatProfileTextButton")
        format_profile_button.setMinimumWidth(120)
        format_profile_button.setToolTip("Wrap the description so it fits the in-game profile panel")
        format_profile_button.clicked.connect(self.format_current_profile_text)
        format_profile_button.setStyleSheet("""
            QPushButton#formatProfileTextButton {
                background-color: #2c9558;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton#formatProfileTextButton:hover {
                background-color: #247a49;
            }
            QPushButton#formatProfileTextButton:pressed {
                background-color: #1d633b;
            }
        """)
        profile_tools_layout.addWidget(format_profile_button)
        profile_tools_layout.addStretch()

        self.profile_text_stats_label = QLabel("")
        self.profile_text_stats_label.setStyleSheet("color: #666; font-size: 9pt;")
        profile_tools_layout.addWidget(self.profile_text_stats_label)
        profile_layout.addLayout(profile_tools_layout)

        layout.addWidget(profile_group, 1)

        return tab

    def create_multi_language_tab(self) -> QWidget:
        """Create localized name/profile/belong text tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        self.localized_text_widgets = {}
        self.localized_text_tab_widget = QTabWidget()

        for folder, language_name in TEXT_LANGUAGE_FOLDERS:
            if folder == ENGLISH_TEXT_FOLDER:
                continue

            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setSpacing(10)

            text_group = QGroupBox(f"{folder} - {language_name}")
            text_layout = QGridLayout(text_group)
            text_layout.setSpacing(10)

            name_label = QLabel("Name:")
            name_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            text_layout.addWidget(name_label, 0, 0)
            name_edit = QLineEdit()
            text_layout.addWidget(name_edit, 0, 1)

            belong_label = QLabel("Belong:")
            belong_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            text_layout.addWidget(belong_label, 1, 0)
            belong_edit = QLineEdit()
            text_layout.addWidget(belong_edit, 1, 1)

            profile_label = QLabel("Profile:")
            profile_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            text_layout.addWidget(profile_label, 2, 0, Qt.AlignmentFlag.AlignTop)
            profile_edit = QTextEdit()
            profile_edit.setMinimumHeight(260)
            profile_edit.setStyleSheet("""
                QTextEdit {
                    background-color: white;
                    border: 2px solid #dee2e6;
                    border-radius: 6px;
                    padding: 10px;
                    font-size: 10pt;
                    color: #495057;
                }
                QTextEdit:focus {
                    border-color: #84fab0;
                    background-color: #f8f9fa;
                }
            """)
            text_layout.addWidget(profile_edit, 2, 1)

            page_layout.addWidget(text_group, 1)

            tools_layout = QHBoxLayout()
            format_button = QPushButton("Format Text")
            format_button.setMinimumWidth(120)
            format_button.setToolTip("Wrap this localized profile for the in-game profile panel")
            format_button.clicked.connect(
                lambda _checked=False, folder=folder: self.format_localized_profile_text(folder)
            )
            format_button.setStyleSheet("""
                QPushButton {
                    background-color: #2c9558;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 14px;
                    font-weight: bold;
                    font-size: 10pt;
                }
                QPushButton:hover {
                    background-color: #247a49;
                }
                QPushButton:pressed {
                    background-color: #1d633b;
                }
            """)
            tools_layout.addWidget(format_button)
            tools_layout.addStretch()

            stats_label = QLabel("")
            stats_label.setStyleSheet("color: #666; font-size: 9pt;")
            tools_layout.addWidget(stats_label)
            page_layout.addLayout(tools_layout)

            self.localized_text_widgets[folder] = {
                "name": name_edit,
                "tribe_name": belong_edit,
                "profile_text": profile_edit,
                "stats_label": stats_label,
            }

            name_edit.textChanged.connect(
                lambda _text, folder=folder: self.on_localized_text_changed(folder)
            )
            belong_edit.textChanged.connect(
                lambda _text, folder=folder: self.on_localized_text_changed(folder)
            )
            profile_edit.textChanged.connect(
                lambda folder=folder: self.on_localized_text_changed(folder)
            )

            self.localized_text_tab_widget.addTab(page, self._localized_tab_title(folder))

        layout.addWidget(self.localized_text_tab_widget)

        return tab

    def _localized_tab_title(self, folder: str) -> str:
        """Return a compact language tab label."""
        language_name = TEXT_LANGUAGE_LABELS.get(folder, "Language")
        code = folder.replace("patch_text", "")
        return f"{code} {language_name}"

    def on_localized_text_changed(self, folder: str):
        """React to edits in one localized text page."""
        self.update_localized_profile_stats(folder)
        if getattr(self, "_loading_digimon_form", False) or getattr(self, "_syncing_multilanguage_ui", False):
            return
        if folder == ENGLISH_TEXT_FOLDER:
            self.sync_basic_info_from_english_text()
        self.mark_as_modified()

    def format_localized_profile_text(self, folder: str):
        """Wrap one localized profile text field to the game profile width."""
        widgets = getattr(self, "localized_text_widgets", {}).get(folder)
        if not widgets:
            return
        profile_edit = widgets["profile_text"]
        formatted_text = format_profile_text_for_game(profile_edit.toPlainText())
        if formatted_text != profile_edit.toPlainText():
            profile_edit.setPlainText(formatted_text)
            self.mark_as_modified()
        self.update_localized_profile_stats(folder)

    def update_localized_profile_stats(self, folder: str):
        """Update the line stats label for one localized profile."""
        widgets = getattr(self, "localized_text_widgets", {}).get(folder)
        if not widgets:
            return
        profile_edit = widgets["profile_text"]
        stats_label = widgets["stats_label"]
        text = profile_edit.toPlainText()
        lines = text.splitlines() or [""]
        longest_line = max(len(line) for line in lines)
        stats_label.setText(f"Lines: {len(lines)} | Longest: {longest_line}/{PROFILE_WRAP_WIDTH}")
        stats_label.setStyleSheet(
            "color: #b02a37; font-size: 9pt;" if longest_line > PROFILE_WRAP_WIDTH else "color: #666; font-size: 9pt;"
        )

    def _normalize_text_folder_name(self, folder: str) -> str:
        """Normalize text language ids to patch_textXX folder names."""
        text = str(folder or "").strip()
        if not text:
            return ""
        match = TEXT_LANGUAGE_FOLDER_RE.match(text)
        if not match:
            digits = re.search(r"(\d+)$", text)
            if not digits:
                return ""
            code = digits.group(1)
        else:
            code = match.group("code")
        if len(code) == 1:
            code = code.zfill(2)
        return f"patch_text{code}"

    def _language_sort_key(self, folder: str) -> Tuple[int, str]:
        """Sort text language folders by numeric suffix."""
        normalized = self._normalize_text_folder_name(folder)
        match = TEXT_LANGUAGE_FOLDER_RE.match(normalized)
        if not match:
            return (9999, normalized)
        try:
            return (int(match.group("code")), normalized)
        except ValueError:
            return (9999, normalized)

    def _normalize_localized_text_map(self, localized_text) -> Dict[str, Dict[str, str]]:
        """Normalize stored localized text maps from old or imported shapes."""
        normalized: Dict[str, Dict[str, str]] = {}
        if not isinstance(localized_text, dict):
            return normalized

        for raw_folder, raw_values in localized_text.items():
            folder = self._normalize_text_folder_name(raw_folder)
            if not folder or not isinstance(raw_values, dict):
                continue

            values = {
                "name": str(raw_values.get("name", "") or ""),
                "profile_text": str(raw_values.get("profile_text", raw_values.get("profile", "")) or ""),
                "tribe_name": str(raw_values.get("tribe_name", raw_values.get("belong", "")) or ""),
            }
            normalized[folder] = values

        return normalized

    def _basic_info_language_payload(self) -> Dict[str, str]:
        """Return the Basic Info tab's English text payload."""
        tribe_name = self.tribe_combo.currentText() if self.tribe_combo.currentText() else "None"
        return {
            "name": self.name_edit.text(),
            "profile_text": self.profile_text_edit.toPlainText(),
            "tribe_name": tribe_name,
        }

    def sync_english_text_from_basic_info(self, *_args):
        """Mirror Basic Info into the English localized tab."""
        if (
            getattr(self, "_loading_digimon_form", False)
            or getattr(self, "_syncing_multilanguage_ui", False)
            or ENGLISH_TEXT_FOLDER not in getattr(self, "localized_text_widgets", {})
        ):
            return

        widgets = self.localized_text_widgets[ENGLISH_TEXT_FOLDER]
        payload = self._basic_info_language_payload()
        self._syncing_multilanguage_ui = True
        try:
            if widgets["name"].text() != payload["name"]:
                widgets["name"].setText(payload["name"])
            if widgets["tribe_name"].text() != payload["tribe_name"]:
                widgets["tribe_name"].setText(payload["tribe_name"])
            if widgets["profile_text"].toPlainText() != payload["profile_text"]:
                widgets["profile_text"].setPlainText(payload["profile_text"])
        finally:
            self._syncing_multilanguage_ui = False
        self.update_localized_profile_stats(ENGLISH_TEXT_FOLDER)

    def sync_basic_info_from_english_text(self):
        """Mirror the English localized tab back into Basic Info."""
        widgets = getattr(self, "localized_text_widgets", {}).get(ENGLISH_TEXT_FOLDER)
        if not widgets:
            return

        name = widgets["name"].text()
        tribe_name = widgets["tribe_name"].text().strip()
        profile_text = widgets["profile_text"].toPlainText()

        self._syncing_multilanguage_ui = True
        try:
            if self.name_edit.text() != name:
                self.name_edit.setText(name)
            if tribe_name:
                tribe_index = self.tribe_combo.findText(tribe_name)
                if tribe_index < 0:
                    self.tribe_combo.addItem(tribe_name)
                    tribe_index = self.tribe_combo.findText(tribe_name)
                if tribe_index >= 0 and self.tribe_combo.currentIndex() != tribe_index:
                    self.tribe_combo.setCurrentIndex(tribe_index)
            if self.profile_text_edit.toPlainText() != profile_text:
                self.profile_text_edit.setPlainText(profile_text)
        finally:
            self._syncing_multilanguage_ui = False

        self.update_profile_text_stats()

    def load_multilanguage_text_tab(self, digimon: DigimonData):
        """Load localized text values into the Multi Language tab."""
        if not hasattr(self, "localized_text_widgets"):
            return

        localized_text = self._normalize_localized_text_map(getattr(digimon, "localized_text", {}))
        english_values = dict(localized_text.get(ENGLISH_TEXT_FOLDER, {}))
        if not english_values.get("name"):
            english_values["name"] = getattr(digimon, "name", "")
        if not english_values.get("profile_text"):
            english_values["profile_text"] = getattr(digimon, "profile_text", "")
        if not english_values.get("tribe_name"):
            english_values["tribe_name"] = getattr(digimon, "tribe_name", "") or "None"
        localized_text[ENGLISH_TEXT_FOLDER] = english_values
        digimon.localized_text = localized_text

        self._syncing_multilanguage_ui = True
        try:
            for folder, widgets in self.localized_text_widgets.items():
                values = localized_text.get(folder, {})
                widgets["name"].setText(values.get("name", ""))
                widgets["tribe_name"].setText(values.get("tribe_name", ""))
                widgets["profile_text"].setPlainText(values.get("profile_text", ""))
        finally:
            self._syncing_multilanguage_ui = False

        for folder in self.localized_text_widgets:
            self.update_localized_profile_stats(folder)

    def collect_multilanguage_text_from_form(self):
        """Collect localized text edits back onto the current Digimon."""
        if not self.current_digimon or not hasattr(self, "localized_text_widgets"):
            return

        localized_text = self._normalize_localized_text_map(getattr(self.current_digimon, "localized_text", {}))

        for folder, widgets in self.localized_text_widgets.items():
            if folder == ENGLISH_TEXT_FOLDER:
                values = self._basic_info_language_payload()
            else:
                values = {
                    "name": widgets["name"].text().strip(),
                    "profile_text": widgets["profile_text"].toPlainText(),
                    "tribe_name": widgets["tribe_name"].text().strip(),
                }

            has_text = any(str(value).strip() for value in values.values())
            if has_text or folder in localized_text:
                localized_text[folder] = values
            else:
                localized_text.pop(folder, None)

        english_values = self._basic_info_language_payload()
        if any(str(value).strip() for value in english_values.values()):
            localized_text[ENGLISH_TEXT_FOLDER] = english_values

        self.current_digimon.localized_text = localized_text

    def create_stats_tab(self) -> QWidget:
        """Create stats tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Base Stats Group
        stats_group = QGroupBox("Base Stats")
        stats_layout = QGridLayout(stats_group)

        # Create stat spinboxes
        self.stat_widgets = {}
        stats = ["HP", "SP", "ATK", "DEF", "INT", "SPI", "SPD"]

        for i, stat in enumerate(stats):
            stats_layout.addWidget(QLabel(f"{stat}:"), i, 0)
            spin = QSpinBox()
            spin.setRange(0, 9999)
            self.stat_widgets[stat.lower()] = spin
            stats_layout.addWidget(spin, i, 1)

        layout.addWidget(stats_group)

        # Growth Pattern Group
        growth_group = QGroupBox("📈 Growth Pattern")
        growth_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #f093fb;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
                font-size: 11pt;
            }
            QGroupBox::title {
                color: #c967cc;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        growth_layout = QHBoxLayout(growth_group)

        growth_label = QLabel("Growth Pattern (determines stat gains per level):")
        growth_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        growth_layout.addWidget(growth_label)

        self.growth_pattern_combo = QComboBox()
        for i in range(1, 19):  # Growth patterns 1-18
            self.growth_pattern_combo.addItem(f"Pattern {i}", i)
        growth_layout.addWidget(self.growth_pattern_combo)
        growth_layout.addStretch()

        layout.addWidget(growth_group)

        # Elemental Resistances Group
        resist_group = QGroupBox("🛡️ Elemental Resistances")
        resist_layout = QGridLayout(resist_group)

        # Create resistance spinboxes with element names
        self.resist_widgets = {}
        # IMPORTANT: Order must match CSV columns 7-17 (resNull, resFire, resWater, resGrass, resIce, resElec, resGround, resSteel, resWind, resLight, resDark)
        resistances = [
            ("null", "Null"),
            ("fire", "Fire"),
            ("water", "Water"),
            ("grass", "Plant"),
            ("ice", "Ice"),
            ("elec", "Electric"),
            ("ground", "Earth"),
            ("steel", "Steel"),
            ("wind", "Wind"),
            ("light", "Light"),
            ("dark", "Dark")
        ]

        resistance_labels = {
            0: "Normal (1.0x)",
            1: "Weak (1.5x)",
            2: "Very Weak (2.0x)",
            3: "Resist (0.5x)",
            4: "Immune (0.0x)"
        }

        for i, (resist_key, resist_name) in enumerate(resistances):
            row = i // 2
            col = (i % 2) * 3  # Changed to *3 to make room for label
            resist_layout.addWidget(QLabel(f"{resist_name}:"), row, col)

            spin = QSpinBox()
            spin.setRange(0, 4)
            spin.setObjectName(f"resist_{resist_key}")
            spin.setToolTip(
                f"Set {resist_name} resistance:\n"
                "0 = Normal (100% damage - 1.0x)\n"
                "1 = Weak (150% damage - 1.5x)\n"
                "2 = Very Weak (200% damage - 2.0x)\n"
                "3 = Resistant (50% damage - 0.5x)\n"
                "4 = Immune (0% damage - no damage taken)"
            )
            self.resist_widgets[resist_key] = spin
            resist_layout.addWidget(spin, row, col + 1)

            # Add label that updates based on value
            value_label = QLabel(resistance_labels[0])
            value_label.setObjectName(f"resist_label_{resist_key}")
            value_label.setStyleSheet("color: #666; font-size: 9pt;")
            resist_layout.addWidget(value_label, row, col + 2)

            # Connect to update label when value changes
            spin.valueChanged.connect(lambda v, label=value_label: label.setText(resistance_labels.get(v, "Unknown")))

        layout.addWidget(resist_group)
        layout.addStretch()

        return tab

    def create_skills_tab(self) -> QWidget:
        """Create skills tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Signature Skills Section
        sig_group = QGroupBox("Signature Skills (up to 12)")
        sig_layout = QVBoxLayout()

        self.signature_skills_editor = SkillEditor("signature", self.loader)
        self.signature_skills_editor.skillChanged.connect(self.mark_as_modified)
        sig_layout.addWidget(self.signature_skills_editor)
        sig_group.setLayout(sig_layout)
        layout.addWidget(sig_group)

        # Generic Skills Section
        gen_group = QGroupBox("Generic Skills (up to 4)")
        gen_layout = QVBoxLayout()

        self.generic_skills_editor = SkillEditor("generic", self.loader)
        self.generic_skills_editor.skillChanged.connect(self.mark_as_modified)
        gen_layout.addWidget(self.generic_skills_editor)
        gen_group.setLayout(gen_layout)
        layout.addWidget(gen_group, 1)

        return tab

    def add_skill_from_list(self, skill_type: str):
        """Show dialog to select a skill from list"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Select {skill_type.title()} Skill")
        dialog.setMinimumSize(600, 500)

        layout = QVBoxLayout(dialog)

        # Info label
        info_label = QLabel(f"Select a skill to add to the first empty slot in {skill_type} skills.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; padding: 8px; background-color: #f0f0f0; border-radius: 4px;")
        layout.addWidget(info_label)

        # Search box
        search_label = QLabel("🔍 Search:")
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("Type to search skills by name or ID...")
        layout.addWidget(search_label)
        layout.addWidget(search_edit)

        # Skill list
        skill_list = QListWidget()
        layout.addWidget(QLabel("Available Skills:"))
        layout.addWidget(skill_list)

        # Populate skill list
        self._populate_skill_list(skill_list)

        # Filter on search
        def filter_skills(text):
            for i in range(skill_list.count()):
                item = skill_list.item(i)
                item.setHidden(text.lower() not in item.text().lower())
        search_edit.textChanged.connect(filter_skills)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_item = skill_list.currentItem()
            if selected_item:
                skill_id = selected_item.data(Qt.ItemDataRole.UserRole)
                self._add_skill_to_editor(skill_type, skill_id)

    def _populate_skill_list(self, skill_list: QListWidget):
        """Populate skill list with all available skills"""
        try:
            skills_file = self.loader.data_path / "battle_skill.mbe" / "000_battle_skill_list.csv"
            skills_file = self._resolve_prefixed_file(skills_file)
            if not skills_file.exists():
                return

            rows = self.loader.load_csv(skills_file)

            for row in rows[1:]:  # Skip header
                if len(row) > 4:
                    skill_id = int(row[0]) if row[0] else 0
                    skill_name_id = row[4].strip('"') if len(row) > 4 else ""

                    # Get skill name
                    skill_name = self.loader.get_skill_name(skill_id)
                    if not skill_name or skill_name == str(skill_id) or skill_name.startswith("Skill_"):
                        skill_name = skill_name_id if skill_name_id else f"Skill {skill_id}"

                    # Create list item
                    item = QListWidgetItem(f"{skill_name} (ID: {skill_id})")
                    item.setData(Qt.ItemDataRole.UserRole, skill_id)
                    skill_list.addItem(item)
        except Exception as e:
            print(f"Error loading skills: {e}")

    def _add_skill_to_editor(self, skill_type: str, skill_id: int):
        """Add a skill to the appropriate editor"""
        editor = self.signature_skills_editor if skill_type == "signature" else self.generic_skills_editor

        # Find first empty slot
        for i, skill_widget in enumerate(editor.skill_widgets):
            skill_id_widget = skill_widget.findChild(QSpinBox, f"skill_id_{i}")
            if skill_id_widget and skill_id_widget.value() == 0:
                skill_id_widget.setValue(skill_id)
                editor.update_skill_name(i)
                self.mark_as_modified()
                QMessageBox.information(self, "Skill Added", f"Skill {skill_id} added to slot {i+1}")
                return

        # No empty slots found
        max_slots = 12 if skill_type == "signature" else 4
        QMessageBox.warning(self, "No Empty Slots", f"All {max_slots} {skill_type} skill slots are filled.\nClear a slot first by setting its ID to 0.")

    def create_model_tab(self) -> QWidget:
        """Create model and animation tab"""
        tab = QWidget()

        # Use scroll area for the tab content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)

        # Model Info Group
        model_group = QGroupBox("Model Information")
        model_layout = QGridLayout(model_group)

        # Model ID
        model_layout.addWidget(QLabel("Model ID:"), 0, 0)
        self.model_id_edit = QLineEdit()
        model_layout.addWidget(self.model_id_edit, 0, 1)

        # Audio ID (motion_ref in char_info)
        model_layout.addWidget(QLabel("Audio ID:"), 1, 0)
        self.motion_id_edit = QLineEdit()
        model_layout.addWidget(self.motion_id_edit, 1, 1)

        # Animation Reference (chr_id used for animations)
        model_layout.addWidget(QLabel("Animation Reference:"), 2, 0)
        self.animation_ref_edit = QLineEdit()
        self.animation_ref_edit.setPlaceholderText("e.g., chr805 (which model's animations to use)")
        model_layout.addWidget(self.animation_ref_edit, 2, 1)

        # Add explanation label
        anim_note = QLabel("💡 This determines which chr_id's animations this Digimon uses.\nSet to same as Chr ID in Basic Info (e.g., chr805 for Darkshadow)")
        anim_note.setStyleSheet("color: #666; font-size: 9pt; font-style: italic;")
        anim_note.setWordWrap(True)
        model_layout.addWidget(anim_note, 3, 0, 1, 2)

        layout.addWidget(model_group)

        related_group = QGroupBox("Related Asset Import")
        related_layout = QGridLayout(related_group)
        related_layout.setColumnStretch(1, 1)
        related_layout.setHorizontalSpacing(8)
        related_layout.setVerticalSpacing(8)

        related_layout.addWidget(QLabel("Extracted Folder:"), 0, 0)
        related_path_widget = QWidget()
        related_path_layout = QHBoxLayout(related_path_widget)
        related_path_layout.setContentsMargins(0, 0, 0, 0)
        related_path_layout.setSpacing(8)
        self.related_extract_path_edit = QLineEdit(str(get_default_extracted_game_path()))
        self.related_extract_path_edit.setToolTip("Root folder that contains app_0.dx11, patch.dx11, and extracted asset folders.")
        related_path_layout.addWidget(self.related_extract_path_edit, 1)
        browse_related_button = QPushButton("Browse...")
        browse_related_button.setMinimumWidth(96)
        browse_related_button.setToolTip("Choose the extracted Time Stranger folder")
        browse_related_button.clicked.connect(self.browse_related_extract_path)
        browse_related_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                color: #333333;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                font-weight: bold;
                padding: 7px 10px;
            }
            QPushButton:hover {
                border-color: #667eea;
                background-color: #eef4ff;
            }
        """)
        related_path_layout.addWidget(browse_related_button)
        related_layout.addWidget(related_path_widget, 0, 1, 1, 2)

        related_layout.addWidget(QLabel("Source Digimon:"), 1, 0)
        related_source_widget = QWidget()
        related_source_layout = QHBoxLayout(related_source_widget)
        related_source_layout.setContentsMargins(0, 0, 0, 0)
        related_source_layout.setSpacing(8)
        self.related_source_combo = QComboBox()
        self.related_source_combo.setEditable(True)
        self.related_source_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.related_source_combo.setToolTip("Original Digimon to copy model and image assets from, e.g. Kyubimon (chr395).")
        configure_searchable_combo(self.related_source_combo)
        self.related_source_combo.setStyleSheet(self.related_source_combo.styleSheet() + """
            QComboBox {
                padding-right: 8px;
            }
            QComboBox::drop-down {
                width: 0px;
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }
        """)
        if self.related_source_combo.lineEdit():
            self.related_source_combo.lineEdit().setPlaceholderText("Search by name or chr ID...")
            self.related_source_prompt_filter = ComboPromptClearFilter(
                self.related_source_combo,
                RELATED_SOURCE_PROMPT
            )
            self.related_source_combo.lineEdit().installEventFilter(self.related_source_prompt_filter)
        related_source_layout.addWidget(self.related_source_combo, 1)

        related_dropdown_button = QPushButton("Open ▼")
        related_dropdown_button.setMinimumWidth(96)
        related_dropdown_button.setToolTip("Open source Digimon list")
        related_dropdown_button.clicked.connect(self.related_source_combo.showPopup)
        related_dropdown_button.setStyleSheet("""
            QPushButton {
                background-color: #667eea;
                color: white;
                border: 2px solid #667eea;
                border-radius: 6px;
                font-weight: bold;
                padding: 7px 10px;
            }
            QPushButton:hover {
                background-color: #5568d3;
                border-color: #5568d3;
            }
        """)
        related_source_layout.addWidget(related_dropdown_button)
        related_layout.addWidget(related_source_widget, 1, 1, 1, 2)

        related_layout.addWidget(QLabel("Import Options:"), 2, 0)
        related_options_widget = QWidget()
        related_options_layout = QHBoxLayout(related_options_widget)
        related_options_layout.setContentsMargins(0, 0, 0, 0)
        related_options_layout.setSpacing(8)

        self.related_normals_toggle = QPushButton("Normals/Extras: OFF")
        self.related_normals_toggle.setCheckable(True)
        self.related_normals_toggle.setToolTip(
            "Include optional texture maps such as l/m/n/h/s files. Leave OFF for simple recolors."
        )
        self.related_normals_toggle.toggled.connect(
            lambda checked: self.related_normals_toggle.setText(
                "Normals/Extras: ON" if checked else "Normals/Extras: OFF"
            )
        )
        self.related_normals_toggle.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #333333;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                font-weight: bold;
                padding: 8px 12px;
                text-align: left;
            }
            QPushButton:hover {
                border-color: #667eea;
                background-color: #f8f9fa;
            }
            QPushButton:checked {
                background-color: #10b981;
                color: white;
                border-color: #059669;
            }
        """)
        related_options_layout.addWidget(self.related_normals_toggle)

        self.related_all_assets_toggle = QPushButton("All Model Files: OFF")
        self.related_all_assets_toggle.setCheckable(True)
        self.related_all_assets_toggle.setToolTip(
            "Include every matching model/animation/effect file. Leave OFF to import only chr*.anim/.geom/.nlst and chr*_lod_2 files."
        )
        self.related_all_assets_toggle.toggled.connect(
            lambda checked: self.related_all_assets_toggle.setText(
                "All Model Files: ON" if checked else "All Model Files: OFF"
            )
        )
        self.related_all_assets_toggle.setStyleSheet(self.related_normals_toggle.styleSheet())
        related_options_layout.addWidget(self.related_all_assets_toggle)
        related_options_layout.addStretch()
        related_layout.addWidget(related_options_widget, 2, 1, 1, 2)

        related_layout.addWidget(QLabel("Related Files:"), 3, 0)
        related_actions_widget = QWidget()
        related_actions_layout = QHBoxLayout(related_actions_widget)
        related_actions_layout.setContentsMargins(0, 0, 0, 0)
        related_actions_layout.setSpacing(8)

        import_related_button = QPushButton("Import Now")
        import_related_button.setToolTip("Copy related files into the loaded/selected dsts-loader patch folder.")
        import_related_button.clicked.connect(self.import_related_files_now)
        import_related_button.setStyleSheet("""
            QPushButton {
                background-color: #667eea;
                color: white;
                border: 2px solid #667eea;
                border-radius: 6px;
                font-weight: bold;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background-color: #5568d3;
                border-color: #5568d3;
            }
        """)
        related_actions_layout.addWidget(import_related_button)

        rename_geom_textures_button = QPushButton("Rename .geom Textures")
        rename_geom_textures_button.setToolTip(
            "Patch copied .geom files to use bumped texture names and rename matching images."
        )
        rename_geom_textures_button.clicked.connect(self.rename_geom_textures_now)
        rename_geom_textures_button.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: 2px solid #10b981;
                border-radius: 6px;
                font-weight: bold;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background-color: #059669;
                border-color: #059669;
            }
        """)
        related_actions_layout.addWidget(rename_geom_textures_button)
        related_actions_layout.addStretch()
        related_layout.addWidget(related_actions_widget, 3, 1, 1, 2)

        self.related_import_status_label = QLabel("No related files imported yet.")
        self.related_import_status_label.setStyleSheet("color: #666; font-size: 9pt;")
        related_layout.addWidget(self.related_import_status_label, 4, 0, 1, 3)

        layout.addWidget(related_group)
        self.populate_related_source_combo()

        # Model Settings Group (from model_setting.mbe)
        settings_group = QGroupBox("Model Settings (model_setting.mbe)")
        settings_layout = QGridLayout(settings_group)

        # Scale settings
        settings_layout.addWidget(QLabel("<b>Scale Settings</b>"), 0, 0, 1, 4)

        settings_layout.addWidget(QLabel("Battle Scale:"), 1, 0)
        self.battle_scale_spin = QDoubleSpinBox()
        self.battle_scale_spin.setRange(0.0, 100.0)
        self.battle_scale_spin.setDecimals(3)
        self.battle_scale_spin.setSingleStep(0.1)
        self.battle_scale_spin.setValue(1.0)
        settings_layout.addWidget(self.battle_scale_spin, 1, 1)

        settings_layout.addWidget(QLabel("Menu Scale:"), 1, 2)
        self.menu_scale_spin = QDoubleSpinBox()
        self.menu_scale_spin.setRange(0.0, 100.0)
        self.menu_scale_spin.setDecimals(3)
        self.menu_scale_spin.setSingleStep(0.1)
        self.menu_scale_spin.setValue(1.0)
        settings_layout.addWidget(self.menu_scale_spin, 1, 3)

        settings_layout.addWidget(QLabel("Field Scale:"), 2, 0)
        self.field_scale_spin = QDoubleSpinBox()
        self.field_scale_spin.setRange(0.0, 100.0)
        self.field_scale_spin.setDecimals(3)
        self.field_scale_spin.setSingleStep(0.1)
        self.field_scale_spin.setValue(1.0)
        settings_layout.addWidget(self.field_scale_spin, 2, 1)

        # Collision and Shield
        settings_layout.addWidget(QLabel("<b>Collision & Shield</b>"), 3, 0, 1, 4)

        settings_layout.addWidget(QLabel("NPC Collision:"), 4, 0)
        self.npc_collision_spin = QDoubleSpinBox()
        self.npc_collision_spin.setRange(0.0, 1000.0)
        self.npc_collision_spin.setDecimals(3)
        self.npc_collision_spin.setSingleStep(0.1)
        settings_layout.addWidget(self.npc_collision_spin, 4, 1)

        settings_layout.addWidget(QLabel("Shield Size:"), 4, 2)
        self.shield_size_spin = QDoubleSpinBox()
        self.shield_size_spin.setRange(0.0, 1000.0)
        self.shield_size_spin.setDecimals(3)
        self.shield_size_spin.setSingleStep(0.1)
        settings_layout.addWidget(self.shield_size_spin, 4, 3)

        # Distance settings
        settings_layout.addWidget(QLabel("<b>Distance Settings</b>"), 5, 0, 1, 4)

        settings_layout.addWidget(QLabel("Agent Distance:"), 6, 0)
        self.agent_distance_spin = QSpinBox()
        self.agent_distance_spin.setRange(0, 99999)
        settings_layout.addWidget(self.agent_distance_spin, 6, 1)

        settings_layout.addWidget(QLabel("Agent Distance 2:"), 6, 2)
        self.agent_distance_2_spin = QDoubleSpinBox()
        self.agent_distance_2_spin.setRange(0.0, 1000.0)
        self.agent_distance_2_spin.setDecimals(3)
        self.agent_distance_2_spin.setSingleStep(0.1)
        settings_layout.addWidget(self.agent_distance_2_spin, 6, 3)

        settings_layout.addWidget(QLabel("Digimon Distance from Agent:"), 7, 0)
        self.digimon_distance_spin = QDoubleSpinBox()
        self.digimon_distance_spin.setRange(0.0, 1000.0)
        self.digimon_distance_spin.setDecimals(3)
        self.digimon_distance_spin.setSingleStep(0.1)
        settings_layout.addWidget(self.digimon_distance_spin, 7, 1)

        settings_layout.addWidget(QLabel("Camera Distance (Skill):"), 7, 2)
        self.camera_distance_skill_spin = QDoubleSpinBox()
        self.camera_distance_skill_spin.setRange(0.0, 1000.0)
        self.camera_distance_skill_spin.setDecimals(3)
        self.camera_distance_skill_spin.setSingleStep(0.1)
        self.camera_distance_skill_spin.setToolTip("Camera distance when selecting a skill (camera faces front of digimon)")
        settings_layout.addWidget(self.camera_distance_skill_spin, 7, 3)

        # Rideable checkbox
        settings_layout.addWidget(QLabel("<b>Other Settings</b>"), 8, 0, 1, 4)

        self.rideable_checkbox = QCheckBox("Rideable")
        self.rideable_checkbox.setToolTip("Enable/disable if this Digimon can be ridden")
        settings_layout.addWidget(self.rideable_checkbox, 9, 0, 1, 2)

        layout.addWidget(settings_group)

        # LOD Data Group
        lod_group = QGroupBox("LOD (Level of Detail) Data")
        lod_layout = QGridLayout(lod_group)

        # LOD distances
        self.lod_widgets = {}
        for i in range(1, 4):
            lod_layout.addWidget(QLabel(f"LOD Distance {i}:"), i-1, 0)
            spin = QSpinBox()
            spin.setRange(0, 1000)
            self.lod_widgets[f"lod_distance_{i}"] = spin
            lod_layout.addWidget(spin, i-1, 1)

        layout.addWidget(lod_group)

        # References Group
        ref_group = QGroupBox("References")
        ref_layout = QGridLayout(ref_group)

        # Column 132 links this row to the profile/script reference the game
        # should read. Normal custom Digimon use their own numeric Digimon ID.
        status_ref_label = QLabel("Status/Profile Ref ID:")
        status_ref_label.setToolTip(
            "Column 132 in digimon_status. Usually this equals the Digimon ID, not the Field Guide ID."
        )
        ref_layout.addWidget(status_ref_label, 0, 0)
        self.script_id_spin = QSpinBox()
        self.script_id_spin.setRange(-1, 999999999)
        self.script_id_spin.setValue(-1)
        self.script_id_spin.setToolTip(
            "Column 132 in 000_digimon_status_data. Keep it equal to the Digimon ID for normal custom entries; "
            "use another Digimon ID only when intentionally sharing or redirecting profile/status data."
        )
        ref_layout.addWidget(self.script_id_spin, 0, 1)

        layout.addWidget(ref_group)
        layout.addStretch()

        scroll.setWidget(scroll_content)

        # Main tab layout
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)

        return tab

    def create_files_tab(self) -> QWidget:
        """Create files information tab showing all 12 required files"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Title
        title = QLabel("Complete Digimon Files (9 Required)")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Info text
        info_text = QLabel("A complete Digimon requires data in all 9 files below:")
        info_text.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info_text)

        # Files status table
        self.files_table = QTableWidget()
        self.files_table.setColumnCount(3)
        self.files_table.setHorizontalHeaderLabels(["File", "Status", "Data Count"])
        self.files_table.horizontalHeader().setStretchLastSection(True)
        self.files_table.setRowCount(9)

        # Set up the 9 required files
        required_files = [
            "digimon_status.mbe/00_digimon_status_data.csv",
            "char_info.mbe/00_char_info.csv",
            "text/char_name.mbe/00_Sheet1.csv",
            "model_setting.mbe/00_model_setting.csv",
            "model_locator.mbe/00_model_locator.csv",
            "model_locator.mbe/01_model_locator_motion.csv",
            "lod_chara.mbe/00_lod.csv",
            "lod_chara.mbe/01_lod_model.csv",
            "field_anime.mbe/00_field_move_animation.csv"
        ]

        for i, file_name in enumerate(required_files):
            self.files_table.setItem(i, 0, QTableWidgetItem(file_name))
            self.files_table.setItem(i, 1, QTableWidgetItem("Not Loaded"))
            self.files_table.setItem(i, 2, QTableWidgetItem("0"))

        layout.addWidget(self.files_table)

        # Export info
        export_info = QGroupBox("Export Information")
        export_layout = QVBoxLayout(export_info)

        export_text = QLabel("When you export a Digimon, all 9 files will be created/updated with the complete data.")
        export_text.setWordWrap(True)
        export_layout.addWidget(export_text)

        self.export_status_label = QLabel("Status: Ready to export")
        self.export_status_label.setStyleSheet("font-weight: bold; color: green;")
        export_layout.addWidget(self.export_status_label)

        layout.addWidget(export_info)

        return tab

    def create_advanced_skills_tab(self) -> QWidget:
        """Create advanced skills tab with detailed skill system"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area for all content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title with modern styling
        title = QLabel("🎯 Advanced Skill System Editor")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("""
            QLabel {
                color: white;
                padding: 15px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 8px;
                border: none;
            }
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Skill selection
        skill_selection_group = QGroupBox("🔍 Skill Selection")
        skill_selection_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #667eea;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
                font-size: 11pt;
            }
            QGroupBox::title {
                color: #667eea;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        skill_selection_layout = QHBoxLayout(skill_selection_group)
        skill_selection_layout.setSpacing(15)

        skill_id_label = QLabel("🆔 Skill ID:")
        skill_id_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        skill_selection_layout.addWidget(skill_id_label)

        self.advanced_skill_id_edit = QSpinBox()
        self.advanced_skill_id_edit.setRange(0, 9999999)
        self.advanced_skill_id_edit.setMinimumWidth(150)
        self.advanced_skill_id_edit.valueChanged.connect(self.update_advanced_skill_display)
        skill_selection_layout.addWidget(self.advanced_skill_id_edit)

        skill_selection_layout.addSpacing(20)

        skill_name_prefix = QLabel("📝 Skill Name:")
        skill_name_prefix.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        skill_selection_layout.addWidget(skill_name_prefix)

        self.advanced_skill_name_edit = QLineEdit()
        self.advanced_skill_name_edit.setPlaceholderText("(No skill selected)")
        self.advanced_skill_name_edit.setMinimumWidth(250)
        self.advanced_skill_name_edit.setStyleSheet("""
            QLineEdit {
                font-weight: bold;
                color: #667eea;
                font-size: 11pt;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                padding: 6px;
            }
            QLineEdit:focus {
                border-color: #667eea;
            }
        """)
        skill_selection_layout.addWidget(self.advanced_skill_name_edit)

        skill_selection_layout.addStretch()
        layout.addWidget(skill_selection_group)

        # Skill description preview (read-only)
        desc_group = QGroupBox("🧾 Skill Description (read-only)")
        desc_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #c9d6ff;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 12px;
                background-color: white;
                font-size: 10pt;
            }
            QGroupBox::title {
                color: #667eea;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        desc_layout = QVBoxLayout(desc_group)
        self.advanced_skill_desc = QPlainTextEdit()
        self.advanced_skill_desc.setReadOnly(True)
        self.advanced_skill_desc.setPlaceholderText("No description for this skill")
        self.advanced_skill_desc.setMaximumHeight(90)
        desc_layout.addWidget(self.advanced_skill_desc)
        layout.addWidget(desc_group)

        # Skill Browser
        browser_group = QGroupBox("📚 Skill Browser")
        browser_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #8fd3f4;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
                font-size: 11pt;
            }
            QGroupBox::title {
                color: #4aa3c7;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        browser_layout = QVBoxLayout(browser_group)
        browser_layout.setSpacing(10)

        browser_hint = QLabel("Search by name or ID, then load the selected skill.")
        browser_hint.setStyleSheet("color: #555; font-size: 9pt;")
        browser_layout.addWidget(browser_hint)

        browser_row = QHBoxLayout()
        self.skill_browser_combo = QComboBox()
        configure_searchable_combo(self.skill_browser_combo)
        self.skill_browser_combo.lineEdit().setPlaceholderText("Search skills by name or ID...")
        self.skill_browser_combo.activated.connect(self.load_skill_from_browser)
        browser_row.addWidget(self.skill_browser_combo, 1)

        browse_skill_button = QPushButton("+ Browse")
        browse_skill_button.setMinimumHeight(40)
        browse_skill_button.setMinimumWidth(110)
        browse_skill_button.setToolTip("Open the available skills dropdown")
        browse_skill_button.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #667eea;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5568d3;
            }
        """)
        browse_skill_button.clicked.connect(self.open_skill_browser_dropdown)
        browser_row.addWidget(browse_skill_button)

        load_skill_button = QPushButton("+ Load")
        load_skill_button.setMinimumHeight(40)
        load_skill_button.setMinimumWidth(96)
        load_skill_button.setToolTip("Load the selected skill into the editor fields")
        load_skill_button.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #10b981;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        load_skill_button.clicked.connect(self.load_skill_from_browser)
        browser_row.addWidget(load_skill_button)
        browser_layout.addLayout(browser_row)

        # Populate skill list
        self.populate_skill_browser()

        layout.addWidget(browser_group)

        # Basic skill properties
        basic_group = QGroupBox("📊 Basic Properties")
        basic_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #84fab0;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
                font-size: 11pt;
            }
            QGroupBox::title {
                color: #2c9558;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(12)
        basic_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        basic_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        power_label = QLabel("⚡ Power:")
        power_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        power_label.setMinimumWidth(180)
        self.skill_power_edit = QSpinBox()
        self.skill_power_edit.setRange(0, 9999)
        self.skill_power_edit.setMinimumWidth(150)
        basic_layout.addRow(power_label, self.skill_power_edit)

        sp_label = QLabel("💧 SP Cost:")
        sp_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        sp_label.setMinimumWidth(180)
        self.skill_sp_cost_edit = QSpinBox()
        self.skill_sp_cost_edit.setRange(0, 999)
        self.skill_sp_cost_edit.setMinimumWidth(150)
        basic_layout.addRow(sp_label, self.skill_sp_cost_edit)

        cp_label = QLabel("⚙️ CP Cost:")
        cp_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        cp_label.setMinimumWidth(180)
        self.skill_cp_cost_edit = QSpinBox()
        self.skill_cp_cost_edit.setRange(0, 9999)
        self.skill_cp_cost_edit.setMinimumWidth(150)
        basic_layout.addRow(cp_label, self.skill_cp_cost_edit)

        anim_label = QLabel("🎞️ Animation/Action ID:")
        anim_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        anim_label.setMinimumWidth(180)
        self.skill_animation_id_edit = QSpinBox()
        self.skill_animation_id_edit.setRange(0, 999999)
        self.skill_animation_id_edit.setMinimumWidth(150)
        basic_layout.addRow(anim_label, self.skill_animation_id_edit)

        effect_label = QLabel("✨ Effect ID:")
        effect_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        effect_label.setMinimumWidth(180)
        self.skill_effect_id_edit = QSpinBox()
        self.skill_effect_id_edit.setRange(0, 999999)
        self.skill_effect_id_edit.setMinimumWidth(150)
        basic_layout.addRow(effect_label, self.skill_effect_id_edit)

        accuracy_label = QLabel("🎯 Accuracy:")
        accuracy_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        accuracy_label.setMinimumWidth(180)
        self.skill_accuracy_edit = QSpinBox()
        self.skill_accuracy_edit.setRange(0, 100)
        self.skill_accuracy_edit.setMinimumWidth(150)
        basic_layout.addRow(accuracy_label, self.skill_accuracy_edit)

        crit_label = QLabel("💥 Critical Rate:")
        crit_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        crit_label.setMinimumWidth(180)
        self.skill_crit_rate_edit = QSpinBox()
        self.skill_crit_rate_edit.setRange(0, 100)
        self.skill_crit_rate_edit.setMinimumWidth(150)
        basic_layout.addRow(crit_label, self.skill_crit_rate_edit)

        layout.addWidget(basic_group)

        # Damage and targeting
        damage_group = QGroupBox("🎯 Damage & Targeting")
        damage_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #fa709a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
                font-size: 11pt;
            }
            QGroupBox::title {
                color: #e85c89;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        damage_layout = QFormLayout(damage_group)
        damage_layout.setSpacing(12)
        damage_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        damage_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        dtype_label = QLabel("💢 Damage Type:")
        dtype_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        dtype_label.setMinimumWidth(180)
        self.skill_damage_type_combo = QComboBox()
        damage_types = ["None/Self", "Physical", "Magic", "Fixed damage at", "Fixed %", "Buff", "Major Damage"]
        self.skill_damage_type_combo.addItems(damage_types)
        self.skill_damage_type_combo.setMinimumWidth(200)
        damage_layout.addRow(dtype_label, self.skill_damage_type_combo)

        element_label = QLabel("🔥 Element:")
        element_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        element_label.setMinimumWidth(180)
        self.skill_element_combo = QComboBox()
        for i in range(11):  # Elements 0-10
            element_name = self.loader.get_element_name(i)
            clean_name = self.loader.clean_ui_text(element_name)
            self.skill_element_combo.addItem(clean_name, i)
        self.skill_element_combo.setMinimumWidth(200)
        damage_layout.addRow(element_label, self.skill_element_combo)

        min_hits_label = QLabel("🎲 Min Hits:")
        min_hits_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        min_hits_label.setMinimumWidth(180)
        self.skill_min_hits_edit = QSpinBox()
        self.skill_min_hits_edit.setRange(1, 10)
        self.skill_min_hits_edit.setMinimumWidth(150)
        damage_layout.addRow(min_hits_label, self.skill_min_hits_edit)

        max_hits_label = QLabel("🎲 Max Hits:")
        max_hits_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        max_hits_label.setMinimumWidth(180)
        self.skill_max_hits_edit = QSpinBox()
        self.skill_max_hits_edit.setRange(1, 10)
        self.skill_max_hits_edit.setMinimumWidth(150)
        damage_layout.addRow(max_hits_label, self.skill_max_hits_edit)

        layout.addWidget(damage_group)

        # Mode change
        mode_group = QGroupBox("🔁 Mode Change")
        mode_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ffd166;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
                font-size: 11pt;
            }
            QGroupBox::title {
                color: #c77d00;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setSpacing(10)

        mode_form = QFormLayout()
        mode_form.setSpacing(10)
        mode_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        mode_change_label = QLabel("Mode Row ID (col 61):")
        mode_change_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        mode_change_label.setMinimumWidth(220)
        self.skill_mode_change_edit = QSpinBox()
        self.skill_mode_change_edit.setRange(-1, 99999999)
        self.skill_mode_change_edit.setMinimumWidth(150)
        self.skill_mode_change_edit.setToolTip("battle_skill column 61. Use -1 for no mode change; positive values must exist in 003_skill_mode_change.")
        mode_form.addRow(mode_change_label, self.skill_mode_change_edit)

        mode_source_label = QLabel("Source Digimon ID:")
        mode_source_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        mode_source_label.setMinimumWidth(220)
        self.mode_change_source_digimon_edit = QSpinBox()
        self.mode_change_source_digimon_edit.setRange(0, 9999999)
        self.mode_change_source_digimon_edit.setMinimumWidth(150)
        self.mode_change_source_digimon_edit.setToolTip("003_skill_mode_change column 1: the Digimon whose mode-change skill set this row describes.")
        mode_form.addRow(mode_source_label, self.mode_change_source_digimon_edit)

        mode_flags_widget = QWidget()
        mode_flags_layout = QHBoxLayout(mode_flags_widget)
        mode_flags_layout.setContentsMargins(0, 0, 0, 0)
        mode_flags_layout.setSpacing(8)
        self.mode_change_flag_4_edit = QSpinBox()
        self.mode_change_flag_4_edit.setRange(0, 99)
        self.mode_change_flag_4_edit.setValue(1)
        self.mode_change_flag_4_edit.setToolTip("003_skill_mode_change column 4. Official rows usually use 1.")
        self.mode_change_flag_5_edit = QSpinBox()
        self.mode_change_flag_5_edit.setRange(0, 99)
        self.mode_change_flag_5_edit.setValue(1)
        self.mode_change_flag_5_edit.setToolTip("003_skill_mode_change column 5. Official rows usually use 1; one official MagnaGarurumon row uses 2.")
        mode_flags_layout.addWidget(QLabel("Col 4:"))
        mode_flags_layout.addWidget(self.mode_change_flag_4_edit)
        mode_flags_layout.addSpacing(12)
        mode_flags_layout.addWidget(QLabel("Col 5:"))
        mode_flags_layout.addWidget(self.mode_change_flag_5_edit)
        mode_flags_layout.addStretch()
        mode_form.addRow("Mode Flags:", mode_flags_widget)

        mode_skills_widget = QWidget()
        mode_skills_grid = QGridLayout(mode_skills_widget)
        mode_skills_grid.setContentsMargins(0, 0, 0, 0)
        mode_skills_grid.setHorizontalSpacing(8)
        mode_skills_grid.setVerticalSpacing(6)
        self.mode_change_skill_widgets = []
        for index in range(12):
            skill_spin = QSpinBox()
            skill_spin.setRange(0, 9999999)
            skill_spin.setMinimumWidth(105)
            skill_spin.setToolTip(f"003_skill_mode_change skill slot {index + 1}")
            self.mode_change_skill_widgets.append(skill_spin)
            row_index = index // 4
            column_index = (index % 4) * 2
            mode_skills_grid.addWidget(QLabel(f"{index + 1}:"), row_index, column_index)
            mode_skills_grid.addWidget(skill_spin, row_index, column_index + 1)
        mode_form.addRow("Mode Skill Set:", mode_skills_widget)
        mode_layout.addLayout(mode_form)

        mode_button_row = QHBoxLayout()
        self.mode_change_use_current_button = QPushButton("Use Current Digimon")
        self.mode_change_use_current_button.setToolTip("Set source ID to the current Digimon, use ID*10+1 as the mode row, and copy signature skills into the mode row.")
        self.mode_change_use_current_button.clicked.connect(self.populate_mode_change_from_current_digimon)
        mode_button_row.addWidget(self.mode_change_use_current_button)

        self.mode_change_load_button = QPushButton("Load Mode Row")
        self.mode_change_load_button.setToolTip("Load 003_skill_mode_change data for the row ID above.")
        self.mode_change_load_button.clicked.connect(lambda: self.load_mode_change_row_for_current_skill(show_messages=True))
        mode_button_row.addWidget(self.mode_change_load_button)

        self.mode_change_clear_button = QPushButton("Clear Mode")
        self.mode_change_clear_button.setToolTip("Set the battle-skill mode pointer to -1 and clear the displayed row fields.")
        self.mode_change_clear_button.clicked.connect(self.clear_mode_change_fields)
        mode_button_row.addWidget(self.mode_change_clear_button)
        mode_button_row.addStretch()
        mode_layout.addLayout(mode_button_row)

        self.mode_change_status_label = QLabel("No mode row loaded.")
        self.mode_change_status_label.setWordWrap(True)
        self.mode_change_status_label.setStyleSheet("color: #6c757d; font-size: 9pt;")
        mode_layout.addWidget(self.mode_change_status_label)

        layout.addWidget(mode_group)

        # Jogress battle-skill fields
        jogress_group = QGroupBox("🧬 Jogress Battle Skill")
        jogress_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #9b5de5;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
                font-size: 11pt;
            }
            QGroupBox::title {
                color: #6f42c1;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        jogress_layout = QFormLayout(jogress_group)
        jogress_layout.setSpacing(10)
        jogress_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        jogress_skill_label = QLabel("Jogress Flag/Type (col 63):")
        jogress_skill_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        jogress_skill_label.setMinimumWidth(220)
        self.skill_jogress_skill_edit = QSpinBox()
        self.skill_jogress_skill_edit.setRange(0, 999999)
        self.skill_jogress_skill_edit.setMinimumWidth(150)
        self.skill_jogress_skill_edit.setToolTip("battle_skill column 63. Official Jogress skills usually use 1 here.")
        jogress_layout.addRow(jogress_skill_label, self.skill_jogress_skill_edit)

        jogress_p1_label = QLabel("Partner A Digimon ID (col 64):")
        jogress_p1_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        jogress_p1_label.setMinimumWidth(220)
        self.skill_jogress_p1_edit = QSpinBox()
        self.skill_jogress_p1_edit.setRange(-1, 9999999)
        self.skill_jogress_p1_edit.setMinimumWidth(150)
        self.skill_jogress_p1_edit.setToolTip("battle_skill column 64. Use -1 when this skill is not a Jogress skill.")
        jogress_layout.addRow(jogress_p1_label, self.skill_jogress_p1_edit)

        jogress_p2_label = QLabel("Partner B Digimon ID (col 66):")
        jogress_p2_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        jogress_p2_label.setMinimumWidth(220)
        self.skill_jogress_p2_edit = QSpinBox()
        self.skill_jogress_p2_edit.setRange(-1, 9999999)
        self.skill_jogress_p2_edit.setMinimumWidth(150)
        self.skill_jogress_p2_edit.setToolTip("battle_skill column 66. Use -1 when this skill is not a Jogress skill.")
        jogress_layout.addRow(jogress_p2_label, self.skill_jogress_p2_edit)

        self.jogress_skill_status_label = QLabel("These fields are for battle skills; evolution Jogress/DNA requirements are edited on the Evolution tab.")
        self.jogress_skill_status_label.setWordWrap(True)
        self.jogress_skill_status_label.setStyleSheet("color: #6c757d; font-size: 9pt;")
        jogress_layout.addRow("", self.jogress_skill_status_label)

        layout.addWidget(jogress_group)

        # Advanced properties
        advanced_group = QGroupBox("⚙️ Advanced Properties")
        advanced_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #f093fb;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
                font-size: 11pt;
            }
            QGroupBox::title {
                color: #c967cc;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        advanced_layout = QFormLayout(advanced_group)
        advanced_layout.setSpacing(12)
        advanced_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        advanced_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        prop1_label = QLabel("🔧 Additional Property 1:")
        prop1_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        prop1_label.setMinimumWidth(220)
        self.skill_additional_prop1_combo = QComboBox()
        additional_props = [
            "None", "Lower HP = Higher damage", "Lower allies HP = Higher damage",
            "Lower HP = Lower damage", "Lower allies HP = Lower damage",
            "Lower SP = Higher damage", "Lower allies SP = Higher damage",
            "Lower SP = Lower damage", "Lower allies SP = Lower damage",
            "More KO'd = Higher damage", "More allies KO'd = Higher damage",
            "More uses = Higher damage", "More rounds = Higher damage",
            "More buffs = Higher damage"
        ]
        self.skill_additional_prop1_combo.addItems(additional_props)
        self.skill_additional_prop1_combo.setMinimumWidth(300)
        advanced_layout.addRow(prop1_label, self.skill_additional_prop1_combo)

        prop2_label = QLabel("🔧 Additional Property 2:")
        prop2_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        prop2_label.setMinimumWidth(220)
        self.skill_additional_prop2_combo = QComboBox()
        additional_effects = [
            "None", "No Effect", "Nullifies unfavorable compatibility",
            "Inverts stat changes", "Steals stat changes", "Recovers beyond Max HP",
            "Consumes all SP", "Nullifies attribute compatibility",
            "Attack as Vaccine", "Attack as Data", "Attack as Virus",
            "Attack as Free", "Attack as Variable"
        ]
        self.skill_additional_prop2_combo.addItems(additional_effects)
        self.skill_additional_prop2_combo.setMinimumWidth(300)
        advanced_layout.addRow(prop2_label, self.skill_additional_prop2_combo)

        layout.addWidget(advanced_group)

        # Conditional effects
        conditional_group = QGroupBox("🔀 Conditional Effects")
        conditional_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #8fd3f4;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
                font-size: 11pt;
            }
            QGroupBox::title {
                color: #4aa3c7;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        conditional_layout = QFormLayout(conditional_group)
        conditional_layout.setSpacing(12)
        conditional_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        conditional_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        cond_type_label = QLabel("❓ Conditional Type:")
        cond_type_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        cond_type_label.setMinimumWidth(220)
        self.skill_conditional_type_combo = QComboBox()
        conditional_types = [
            "None", "User has (de)buff", "Target has (de)buff", "Target attribute",
            "Target element", "Target higher generation", "Target lower generation",
            "Target acted", "Target hasn't acted", "Target HP ≥ 50%",
            "Target HP ≤ X%", "Target SP ≥ X%", "Target SP ≤ X%", "Target KO'd"
        ]
        self.skill_conditional_type_combo.addItems(conditional_types)
        self.skill_conditional_type_combo.setMinimumWidth(300)
        conditional_layout.addRow(cond_type_label, self.skill_conditional_type_combo)

        cond_effect_label = QLabel("✨ Conditional Effect:")
        cond_effect_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        cond_effect_label.setMinimumWidth(220)
        self.skill_conditional_effect_combo = QComboBox()
        conditional_effects = [
            "None", "+X% damage", "Increased Damage", "CRT Rate up",
            "Restore HP", "Restore SP", "Restore SP/HP", "Reduce Target SP"
        ]
        self.skill_conditional_effect_combo.addItems(conditional_effects)
        self.skill_conditional_effect_combo.setMinimumWidth(300)
        conditional_layout.addRow(cond_effect_label, self.skill_conditional_effect_combo)

        cond_arg_label = QLabel("📊 Conditional Argument:")
        cond_arg_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        cond_arg_label.setMinimumWidth(220)
        self.skill_conditional_arg_edit = QSpinBox()
        self.skill_conditional_arg_edit.setRange(0, 100)
        self.skill_conditional_arg_edit.setMinimumWidth(150)
        conditional_layout.addRow(cond_arg_label, self.skill_conditional_arg_edit)

        layout.addWidget(conditional_group)

        # Buff sets
        buff_group = QGroupBox("✨ Buff Sets (up to 5)")
        buff_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #fee140;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
                font-size: 11pt;
            }
            QGroupBox::title {
                color: #d9b12f;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        buff_layout = QVBoxLayout(buff_group)
        buff_layout.setSpacing(8)

        self.buff_set_widgets = []
        self.buff_name_labels = []
        buff_icons = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        for i in range(5):
            buff_widget = QWidget()
            buff_widget_layout = QHBoxLayout(buff_widget)
            buff_widget_layout.setSpacing(10)

            buff_label = QLabel(f"{buff_icons[i]} Buff Set {i+1}:")
            buff_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            buff_label.setMinimumWidth(120)
            buff_widget_layout.addWidget(buff_label)

            buff_set_edit = QSpinBox()
            buff_set_edit.setRange(0, 9999)
            buff_set_edit.setObjectName(f"buff_set_{i}")
            buff_set_edit.setMinimumWidth(100)
            buff_widget_layout.addWidget(buff_set_edit)

            # Add label to show buff name
            buff_name_label = QLabel("")
            buff_name_label.setObjectName(f"buff_name_{i}")
            buff_name_label.setStyleSheet("""
                QLabel {
                    color: #667eea;
                    font-weight: bold;
                    font-size: 10pt;
                    padding: 5px 10px;
                    background-color: #e7f5ff;
                    border-radius: 4px;
                    border-left: 3px solid #667eea;
                }
            """)
            buff_name_label.setMinimumWidth(360)
            buff_name_label.setWordWrap(True)
            buff_widget_layout.addWidget(buff_name_label)
            self.buff_name_labels.append(buff_name_label)

            # Connect to update buff name when value changes
            buff_set_edit.valueChanged.connect(lambda v, idx=i: self.update_buff_name_display(idx, v))

            buff_widget_layout.addStretch()

            self.buff_set_widgets.append(buff_set_edit)
            buff_layout.addWidget(buff_widget)

        layout.addWidget(buff_group)

        # Special effects
        special_group = QGroupBox("💫 Special Effects")
        special_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #a18cd1;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
                font-size: 11pt;
            }
            QGroupBox::title {
                color: #7d6aad;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        special_layout = QFormLayout(special_group)
        special_layout.setSpacing(12)
        special_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        special_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        hp_drain_label = QLabel("🩸 HP Drain %:")
        hp_drain_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        hp_drain_label.setMinimumWidth(180)
        self.skill_hp_drain_edit = QSpinBox()
        self.skill_hp_drain_edit.setRange(0, 100)
        self.skill_hp_drain_edit.setMinimumWidth(150)
        special_layout.addRow(hp_drain_label, self.skill_hp_drain_edit)

        sp_drain_label = QLabel("💙 SP Drain %:")
        sp_drain_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        sp_drain_label.setMinimumWidth(180)
        self.skill_sp_drain_edit = QSpinBox()
        self.skill_sp_drain_edit.setRange(0, 100)
        self.skill_sp_drain_edit.setMinimumWidth(150)
        special_layout.addRow(sp_drain_label, self.skill_sp_drain_edit)

        recoil_label = QLabel("💥 Recoil %:")
        recoil_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        recoil_label.setMinimumWidth(180)
        self.skill_recoil_edit = QSpinBox()
        self.skill_recoil_edit.setRange(0, 100)
        self.skill_recoil_edit.setMinimumWidth(150)
        special_layout.addRow(recoil_label, self.skill_recoil_edit)

        always_hits_label = QLabel("🎯 Special:")
        always_hits_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        always_hits_label.setMinimumWidth(180)
        self.skill_always_hits_check = QCheckBox("Always Hits")
        self.skill_always_hits_check.setFont(QFont("Segoe UI", 10))
        special_layout.addRow(always_hits_label, self.skill_always_hits_check)

        layout.addWidget(special_group)

        # Save button with modern styling
        save_skill_button = QPushButton("💾 Save Skill Data")
        save_skill_button.clicked.connect(self.save_advanced_skill)
        save_skill_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f093fb, stop:1 #f5576c);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 15px;
                font-weight: bold;
                font-size: 12pt;
                margin-top: 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #de7fe9, stop:1 #e34556);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #cd6fd7, stop:1 #d13443);
            }
        """)
        layout.addWidget(save_skill_button)

        layout.addStretch()

        # Set the scroll content and add to main layout
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        return tab

    def _safe_evolution_int(self, value, default: int = 0) -> int:
        return safe_evolution_int(value, default)

    def _first_evolution_condition_dict(self, conditions):
        return normalize_evolution_conditions(conditions)

    def _set_current_evolution_conditions(self, conditions: dict):
        if self.current_digimon:
            normalized = normalize_evolution_conditions(conditions)
            self.current_digimon.evolution_conditions = [normalized]
            return normalized
        return normalize_evolution_conditions(conditions)

    def _format_obtain_requirements_summary(self, conditions) -> str:
        """Format requirements for the current Digimon's inbound evolution row."""
        conditions = normalize_evolution_conditions(conditions)
        parts = [f"Agent Rank: {conditions.get('mode', 1)}"]

        tamer_level = safe_evolution_int(conditions.get('tamerLevel'), 0)
        if tamer_level > 0:
            parts.append(f"Digimon Lv{tamer_level}")

        stats = []
        for stat in ['HP', 'SP', 'ATK', 'DEF', 'INT', 'SPI', 'SPD']:
            value = safe_evolution_int(conditions.get(stat), 0)
            if value > 0:
                stats.append(f"{stat}{value}")
        if stats:
            parts.append(", ".join(stats))

        item_value = safe_evolution_int(conditions.get('needsItem'), 0)
        if item_value > 0:
            parts.append(f"Item#{item_value}")

        skill_counts = []
        skill_labels = [
            ('skillCountValor', "Valor"),
            ('skillCountPhilantropy', "Philanthropy"),
            ('skillCountAmicable', "Amicable"),
            ('skillCountWisdom', "Wisdom"),
        ]
        for key, label in skill_labels:
            value = safe_evolution_int(conditions.get(key), 0)
            if value > 0:
                skill_counts.append(f"{label} {value}")
        if skill_counts:
            parts.append("Skills: " + ", ".join(skill_counts))

        extras = []
        column_11 = safe_evolution_int(conditions.get('unknown1'), 0)
        column_12 = safe_evolution_int(conditions.get('unknown2'), 0)
        if column_11 > 0:
            extras.append(f"Col11 {column_11}")
        if column_12 > 0:
            extras.append(f"Col12 {column_12}")
        if extras:
            parts.append(", ".join(extras))

        jogress_partners = jogress_partner_ids_from_conditions(conditions)
        if jogress_partners:
            parts.append(f"Jogress {' + '.join(f'ID{partner_id}' for partner_id in jogress_partners)}")

        return " | ".join(parts)

    def _path_type_combo_is_jogress(self, combo: QComboBox) -> bool:
        return combo.currentText().strip().lower().startswith("jogress")

    def _chr_id_for_digimon_id(self, digimon_id: int) -> str:
        digimon_id = safe_evolution_int(digimon_id, 0)
        if digimon_id <= 0:
            return ""
        if self.current_digimon and self.current_digimon.id == digimon_id:
            return self.current_digimon.chr_id or f"chr{digimon_id:03d}"
        if hasattr(self.loader, 'imported_digimon'):
            for imported_digimon in self.loader.imported_digimon:
                if imported_digimon.id == digimon_id:
                    return imported_digimon.chr_id or f"chr{digimon_id:03d}"
        for entry in self._evolution_picker_entries():
            if entry.get("id") == digimon_id:
                return entry.get("chr_id") or f"chr{digimon_id:03d}"
        return f"chr{digimon_id:03d}"

    def _base_personality_for_digimon_id(self, digimon_id: int) -> int:
        digimon_id = safe_evolution_int(digimon_id, 0)
        if digimon_id <= 0:
            return 0
        if self.current_digimon and self.current_digimon.id == digimon_id:
            return safe_evolution_int(getattr(self.current_digimon, "base_personality", 0), 0)
        if hasattr(self.loader, 'imported_digimon'):
            for imported_digimon in self.loader.imported_digimon:
                if imported_digimon.id == digimon_id:
                    return safe_evolution_int(getattr(imported_digimon, "base_personality", 0), 0)

        def scan_status_file(status_file: Path) -> Optional[int]:
            if not status_file.exists():
                return None
            rows = self.loader.load_csv(status_file)
            for row in rows[1:]:
                if len(row) > 61 and _clean_status_cell(row[0]) == str(digimon_id):
                    return safe_evolution_int(row[61], 0)
            return None

        try:
            status_file = self.loader._resolve_prefixed_file(
                self.loader.data_path / "digimon_status.mbe" / "000_digimon_status_data.csv"
            )
            personality = scan_status_file(status_file)
            if personality is not None:
                return personality
            for _dlc_id, dlc_status_file in self.loader.iter_dlc_csv_files(
                "data", "digimon_status", "000_digimon_status_data.csv"
            ):
                personality = scan_status_file(dlc_status_file)
                if personality is not None:
                    return personality
        except Exception:
            pass
        return 0

    def _find_evolution_conditions_for_target(self, target_id: int) -> dict:
        target_id = safe_evolution_int(target_id, 0)
        if target_id <= 0:
            return default_evolution_conditions()

        if self.current_digimon:
            if self.current_digimon.id == target_id and self.current_digimon.evolution_conditions:
                return normalize_evolution_conditions(self.current_digimon.evolution_conditions)
            for evo in self.current_digimon.evolution_paths:
                if safe_evolution_int(evo.get("to_id"), 0) == target_id and evo.get("conditions"):
                    return normalize_evolution_conditions(evo.get("conditions"))

        if hasattr(self.loader, 'imported_digimon'):
            for imported_digimon in self.loader.imported_digimon:
                if imported_digimon.id == target_id and imported_digimon.evolution_conditions:
                    return normalize_evolution_conditions(imported_digimon.evolution_conditions)

        def scan_condition_file(condition_file: Path) -> Optional[dict]:
            if not condition_file.exists():
                return None
            rows = self.loader.load_csv(condition_file)
            for row in rows[1:]:
                if row and _clean_status_cell(row[0]) == str(target_id):
                    return normalize_evolution_conditions(row)
            return None

        try:
            condition_file = self.loader._resolve_prefixed_file(
                self.loader.data_path / "evolution.mbe" / "000_evolution_condition.csv"
            )
            conditions = scan_condition_file(condition_file)
            if conditions is not None:
                return conditions
            for _dlc_id, dlc_condition_file in self.loader.iter_dlc_csv_files(
                "data", "evolution", "000_evolution_condition.csv"
            ):
                conditions = scan_condition_file(dlc_condition_file)
                if conditions is not None:
                    return conditions
        except Exception:
            pass

        return default_evolution_conditions()

    def _prefill_jogress_partner(self, conditions: dict, partner_id: int) -> dict:
        conditions = normalize_evolution_conditions(conditions)
        partner_id = safe_evolution_int(partner_id, 0)
        if partner_id <= 0:
            return conditions
        if partner_id in jogress_partner_ids_from_conditions(conditions):
            return conditions

        personality = self._base_personality_for_digimon_id(partner_id)
        if safe_evolution_int(conditions.get('jogressDbIdA'), 0) <= 0:
            conditions['jogressDbIdA'] = partner_id
            conditions['jogressPersonalityA'] = personality
        elif safe_evolution_int(conditions.get('jogressDbIdB'), 0) <= 0:
            conditions['jogressDbIdB'] = partner_id
            conditions['jogressPersonalityB'] = personality
        return conditions

    def _validate_jogress_conditions(self, conditions: dict, required_partner_id: int, title: str) -> bool:
        partner_ids = jogress_partner_ids_from_conditions(normalize_evolution_conditions(conditions))
        if len(partner_ids) < 2:
            QMessageBox.warning(
                self,
                title,
                "Jogress/DNA needs two different partner Digimon IDs in the requirements."
            )
            return False
        required_partner_id = safe_evolution_int(required_partner_id, 0)
        if required_partner_id > 0 and required_partner_id not in partner_ids:
            QMessageBox.warning(
                self,
                title,
                f"The selected Digimon ID {required_partner_id} must be Partner A or Partner B."
            )
            return False
        return True

    def _ensure_deevolution_source(self, from_id: int, from_chr_id: str = "", evolution_type: int = EVOLUTION_TYPE_NORMAL) -> bool:
        from_id = safe_evolution_int(from_id, 0)
        if from_id <= 0:
            return False
        for deevo in self.current_digimon.deevolution_sources:
            if safe_evolution_int(deevo.get('from_id'), 0) == from_id:
                deevo['from_chr_id'] = from_chr_id or deevo.get('from_chr_id') or self._chr_id_for_digimon_id(from_id)
                deevo['evolution_type'] = evolution_type
                return False
        self.current_digimon.deevolution_sources.append({
            'from_id': from_id,
            'from_chr_id': from_chr_id or self._chr_id_for_digimon_id(from_id),
            'evolution_type': evolution_type
        })
        return True

    def _evolution_type_value(self, path_data: dict) -> int:
        if not isinstance(path_data, dict):
            return EVOLUTION_TYPE_NORMAL
        if "evolution_type" in path_data:
            return self._safe_evolution_int(path_data.get("evolution_type"), EVOLUTION_TYPE_NORMAL)
        flags = path_data.get("condition_flags", [])
        if flags:
            return self._safe_evolution_int(flags[0], EVOLUTION_TYPE_NORMAL)
        raw_data = path_data.get("raw_data", [])
        if len(raw_data) > 5:
            return self._safe_evolution_int(raw_data[5], EVOLUTION_TYPE_NORMAL)
        return EVOLUTION_TYPE_NORMAL

    def _conditions_have_jogress(self, conditions: dict) -> bool:
        return evolution_conditions_have_jogress(conditions)

    def _evolution_path_category(self, path_data: dict, target_conditions: Optional[dict] = None) -> str:
        if self._evolution_type_value(path_data) == EVOLUTION_TYPE_MODE_CHANGE:
            return "mode_change"
        path_conditions = path_data.get("conditions") if isinstance(path_data, dict) else {}
        if self._conditions_have_jogress(path_conditions) or self._conditions_have_jogress(target_conditions or {}):
            return "jogress"
        return "normal"

    def _make_path_list_widget(self, selected_color: str, hover_color: str, min_height: int = 120) -> QListWidget:
        list_widget = QListWidget()
        list_widget.setMinimumHeight(min_height)
        list_widget.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 5px;
                background-color: white;
            }}
            QListWidget::item {{
                padding: 8px;
                border-radius: 4px;
                margin: 2px;
            }}
            QListWidget::item:selected {{
                background-color: {selected_color};
                color: #1a1a1a;
            }}
            QListWidget::item:hover {{
                background-color: {hover_color};
            }}
        """)
        return list_widget

    def _add_path_box(self, parent_layout, title: str, attr_name: str, selected_color: str, hover_color: str, min_height: int = 120):
        box = QGroupBox(title)
        box.setStyleSheet("QGroupBox { font-weight: bold; }")
        box_layout = QVBoxLayout(box)
        list_widget = self._make_path_list_widget(selected_color, hover_color, min_height)
        setattr(self, attr_name, list_widget)
        box_layout.addWidget(list_widget)
        parent_layout.addWidget(box)

    def _clear_path_peer_selections(self, active_list: QListWidget, list_names: Iterable[str]):
        for list_name in list_names:
            list_widget = getattr(self, list_name, None)
            if list_widget is not None and list_widget is not active_list:
                list_widget.clearSelection()
                list_widget.setCurrentRow(-1)

    def _connect_path_list_group(self, list_names: Iterable[str], edit_on_double_click: bool = False):
        list_names = tuple(list_names)
        for list_name in list_names:
            list_widget = getattr(self, list_name, None)
            if list_widget is None:
                continue
            list_widget.itemClicked.connect(
                lambda _item, active=list_widget, names=list_names: self._clear_path_peer_selections(active, names)
            )
            if edit_on_double_click:
                list_widget.itemDoubleClicked.connect(lambda _item: self.edit_evolution())

    def _selected_path_index(self, list_names: Iterable[str]) -> Optional[int]:
        for list_name in list_names:
            list_widget = getattr(self, list_name, None)
            if list_widget is None:
                continue
            selected_items = list_widget.selectedItems()
            item = selected_items[0] if selected_items else list_widget.currentItem()
            if not item:
                continue
            path_index = item.data(Qt.ItemDataRole.UserRole)
            if path_index is None:
                continue
            try:
                return int(path_index)
            except (TypeError, ValueError):
                continue
        return None

    def _add_path_item(self, list_widget: QListWidget, text: str, path_index: int):
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, path_index)
        list_widget.addItem(item)

    def _add_empty_path_placeholder(self, list_widget: QListWidget, text: str):
        if list_widget.count() == 0:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, None)
            item.setForeground(Qt.GlobalColor.darkGray)
            list_widget.addItem(item)

    def create_evolution_tab(self) -> QWidget:
        """Create evolution management tab - matching wizard layout"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)

        # Title
        title = QLabel("🔄 Evolution Management")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("""
            QLabel {
                color: #667eea;
                padding: 15px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f8f9fa, stop:1 #e9ecef);
                border-radius: 8px;
                border: 2px solid #dee2e6;
            }
        """)
        layout.addWidget(title)

        # Instructions
        info_label = QLabel(
            "First, set the requirements needed to evolve INTO this Digimon.\n"
            "Then configure evolution paths (what this Digimon can evolve into) and view pre-evolutions."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; padding: 10px; background-color: #f8f9fa; border-radius: 6px;")
        layout.addWidget(info_label)

        # Evolution Requirements section (for obtaining THIS Digimon)
        req_group = QGroupBox("⭐ Requirements to Obtain This Digimon")
        req_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11pt; }")
        req_layout = QVBoxLayout()

        req_info = QLabel(
            "These are the requirements that other Digimon must meet to evolve INTO this Digimon.\n"
            "Leave values at 0 for no requirement."
        )
        req_info.setWordWrap(True)
        req_info.setStyleSheet("color: #555; font-size: 10pt; font-weight: normal;")
        req_layout.addWidget(req_info)

        action_button_style = """
            QPushButton {
                color: white;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                border: none;
                border-radius: 7px;
                padding: 10px 16px;
                font-size: 10pt;
                font-weight: bold;
                min-height: 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5568d3, stop:1 #653b8e);
            }
        """

        edit_req_btn = QPushButton("Edit Evolution Requirements")
        edit_req_btn.setMinimumHeight(44)
        edit_req_btn.setToolTip("Open the full requirements editor for obtaining this Digimon")
        edit_req_btn.setStyleSheet(action_button_style)
        edit_req_btn.clicked.connect(self.edit_evolution_requirements)
        req_layout.addWidget(edit_req_btn)

        self.requirements_label = QLabel("Mode: No Requirements (default)")
        self.requirements_label.setStyleSheet("color: #666; padding: 5px; background: #f0f0f0; border-radius: 3px;")
        self.requirements_label.setWordWrap(True)
        req_layout.addWidget(self.requirements_label)

        req_group.setLayout(req_layout)
        layout.addWidget(req_group)

        # Evolution paths section
        evo_group = QGroupBox("➡️ Evolution Paths (What this Digimon evolves into)")
        evo_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11pt; }")
        evo_layout = QVBoxLayout()

        evo_buttons = QHBoxLayout()
        add_evo_btn = QPushButton("Add Evolution Path")
        add_evo_btn.setMinimumHeight(40)
        add_evo_btn.setStyleSheet(action_button_style)
        add_evo_btn.clicked.connect(self.add_evolution)
        add_jogress_evo_btn = QPushButton("Add Jogress / DNA")
        add_jogress_evo_btn.setMinimumHeight(40)
        add_jogress_evo_btn.setStyleSheet(action_button_style)
        add_jogress_evo_btn.clicked.connect(lambda _checked=False: self.add_evolution(force_jogress=True))
        edit_evo_btn = QPushButton("Edit Selected Evolution")
        edit_evo_btn.setMinimumHeight(40)
        edit_evo_btn.setStyleSheet(action_button_style)
        edit_evo_btn.clicked.connect(self.edit_evolution)
        remove_evo_btn = QPushButton("Remove Selected Evolution")
        remove_evo_btn.setMinimumHeight(40)
        remove_evo_btn.setStyleSheet(action_button_style)
        remove_evo_btn.clicked.connect(self.remove_evolution)
        evo_buttons.addWidget(add_evo_btn)
        evo_buttons.addWidget(add_jogress_evo_btn)
        evo_buttons.addWidget(edit_evo_btn)
        evo_buttons.addWidget(remove_evo_btn)
        evo_buttons.addStretch()
        evo_layout.addLayout(evo_buttons)

        evo_lists = QHBoxLayout()
        evo_lists.setSpacing(10)
        self._add_path_box(evo_lists, "Normal", "evolution_list", "#84fab0", "#e8f5e9", 150)
        self._add_path_box(evo_lists, "Jogress / DNA", "evolution_jogress_list", "#bde0fe", "#edf6ff", 150)
        self._add_path_box(evo_lists, "Mode Change", "evolution_mode_change_list", "#ffd166", "#fff4d6", 150)
        evo_layout.addLayout(evo_lists)
        self._connect_path_list_group(
            ("evolution_list", "evolution_jogress_list", "evolution_mode_change_list"),
            edit_on_double_click=True,
        )
        evo_group.setLayout(evo_layout)
        layout.addWidget(evo_group)

        # Pre-evolution section
        deevo_group = QGroupBox("⬅️ Pre-Evolutions (Digimon that evolve INTO this one)")
        deevo_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11pt; }")
        deevo_layout = QVBoxLayout()

        deevo_info = QLabel(
            "💡 Adding a pre-evolution creates an evolution entry where THAT Digimon evolves into THIS one.\n"
            "⚠️ Each Digimon can only have 6 evolution targets maximum. Base, DLC, and Reloaded II mod rows are counted."
        )
        deevo_info.setWordWrap(True)
        deevo_info.setStyleSheet("""
            color: #856404;
            font-size: 9pt;
            padding: 8px;
            background-color: #fff3cd;
            border-radius: 4px;
        """)
        deevo_layout.addWidget(deevo_info)

        # Buttons for adding/removing pre-evolutions
        deevo_buttons = QHBoxLayout()
        add_deevo_btn = QPushButton("Add Pre-Evolution")
        add_deevo_btn.setMinimumHeight(40)
        add_deevo_btn.setStyleSheet(action_button_style)
        add_deevo_btn.clicked.connect(self.add_pre_evolution)
        add_jogress_deevo_btn = QPushButton("Add Jogress / DNA")
        add_jogress_deevo_btn.setMinimumHeight(40)
        add_jogress_deevo_btn.setStyleSheet(action_button_style)
        add_jogress_deevo_btn.clicked.connect(lambda _checked=False: self.add_pre_evolution(force_jogress=True))
        remove_deevo_btn = QPushButton("Remove Selected Pre-Evolution")
        remove_deevo_btn.setMinimumHeight(40)
        remove_deevo_btn.setStyleSheet(action_button_style)
        remove_deevo_btn.clicked.connect(self.remove_pre_evolution)
        deevo_buttons.addWidget(add_deevo_btn)
        deevo_buttons.addWidget(add_jogress_deevo_btn)
        deevo_buttons.addWidget(remove_deevo_btn)
        deevo_buttons.addStretch()
        deevo_layout.addLayout(deevo_buttons)

        deevo_lists = QHBoxLayout()
        deevo_lists.setSpacing(10)
        self._add_path_box(deevo_lists, "Normal", "deevolution_list", "#e1bee7", "#f3e5f5", 130)
        self._add_path_box(deevo_lists, "Jogress / DNA", "deevolution_jogress_list", "#bde0fe", "#edf6ff", 130)
        self._add_path_box(deevo_lists, "Mode Change", "deevolution_mode_change_list", "#ffd166", "#fff4d6", 130)
        deevo_layout.addLayout(deevo_lists)
        self._connect_path_list_group(
            ("deevolution_list", "deevolution_jogress_list", "deevolution_mode_change_list")
        )

        deevo_group.setLayout(deevo_layout)
        layout.addWidget(deevo_group)

        layout.addStretch()

        return tab

    def create_evolution_tree_tab(self) -> QWidget:
        """Create a visual evolution tree tab (like Digimon evolution chart)"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Title
        title = QLabel("🌳 Evolution Tree")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("""
            QLabel {
                color: #667eea;
                padding: 15px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f8f9fa, stop:1 #e9ecef);
                border-radius: 8px;
                border: 2px solid #dee2e6;
            }
        """)
        layout.addWidget(title)

        # Scroll area for the tree
        tree_scroll = QScrollArea()
        tree_scroll.setWidgetResizable(True)
        tree_scroll.setStyleSheet("""
            QScrollArea {
                border: 2px solid #667eea;
                border-radius: 8px;
                background-color: white;
            }
        """)

        self.evolution_tree_canvas = QWidget()
        self.evolution_tree_canvas.setMinimumSize(800, 600)
        self.evolution_tree_canvas.setStyleSheet("background-color: white;")

        # Add initial placeholder
        canvas_layout = QVBoxLayout(self.evolution_tree_canvas)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        placeholder = QLabel("🔍 Load a Digimon to see its evolution tree")
        placeholder.setStyleSheet("""
            QLabel {
                color: #999;
                font-size: 14pt;
                padding: 100px;
                text-align: center;
            }
        """)
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setWordWrap(True)
        canvas_layout.addWidget(placeholder)

        tree_scroll.setWidget(self.evolution_tree_canvas)
        layout.addWidget(tree_scroll)

        return tab

    def create_battle_tab(self) -> QWidget:
        """Create battle data management tab"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area for all content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title with modern styling
        title = QLabel("⚔️ Battle & Enemy Data")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("""
            QLabel {
                color: white;
                padding: 15px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 8px;
                border: none;
            }
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Battle enemy parameters
        enemy_group = QGroupBox("👾 Enemy Parameters (44 columns)")
        enemy_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #667eea;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
                font-size: 11pt;
            }
            QGroupBox::title {
                color: #667eea;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        enemy_layout = QFormLayout(enemy_group)
        enemy_layout.setSpacing(12)
        enemy_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        enemy_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Enemy ID
        enemy_id_label = QLabel("🆔 Enemy ID (Col 0):")
        enemy_id_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        enemy_id_label.setMinimumWidth(220)
        self.enemy_id_edit = QLineEdit()
        self.enemy_id_edit.setMinimumWidth(200)
        enemy_layout.addRow(enemy_id_label, self.enemy_id_edit)

        # Base Digimon ID
        base_id_label = QLabel("📌 Base Digimon ID (Col 2):")
        base_id_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        base_id_label.setMinimumWidth(220)
        self.base_digimon_id_edit = QLineEdit()
        self.base_digimon_id_edit.setMinimumWidth(200)
        enemy_layout.addRow(base_id_label, self.base_digimon_id_edit)

        # AI Level
        ai_level_label = QLabel("🤖 AI Level (Col 10):")
        ai_level_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        ai_level_label.setMinimumWidth(220)
        self.ai_level_edit = QSpinBox()
        self.ai_level_edit.setRange(0, 50)
        self.ai_level_edit.setMinimumWidth(150)
        enemy_layout.addRow(ai_level_label, self.ai_level_edit)

        # Battle stats (columns 17-23)
        hp_label = QLabel("❤️ Battle HP (Col 17):")
        hp_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        hp_label.setMinimumWidth(220)
        self.battle_hp_edit = QSpinBox()
        self.battle_hp_edit.setRange(1, 99999)
        self.battle_hp_edit.setMinimumWidth(150)
        enemy_layout.addRow(hp_label, self.battle_hp_edit)

        sp_label = QLabel("💙 Battle SP (Col 18):")
        sp_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        sp_label.setMinimumWidth(220)
        self.battle_sp_edit = QSpinBox()
        self.battle_sp_edit.setRange(1, 9999)
        self.battle_sp_edit.setMinimumWidth(150)
        enemy_layout.addRow(sp_label, self.battle_sp_edit)

        atk_label = QLabel("⚔️ Battle ATK (Col 19):")
        atk_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        atk_label.setMinimumWidth(220)
        self.battle_attack_edit = QSpinBox()
        self.battle_attack_edit.setRange(1, 9999)
        self.battle_attack_edit.setMinimumWidth(150)
        enemy_layout.addRow(atk_label, self.battle_attack_edit)

        def_label = QLabel("🛡️ Battle DEF (Col 20):")
        def_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        def_label.setMinimumWidth(220)
        self.battle_defense_edit = QSpinBox()
        self.battle_defense_edit.setRange(1, 9999)
        self.battle_defense_edit.setMinimumWidth(150)
        enemy_layout.addRow(def_label, self.battle_defense_edit)

        int_label = QLabel("🧠 Battle INT (Col 21):")
        int_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        int_label.setMinimumWidth(220)
        self.battle_intelligence_edit = QSpinBox()
        self.battle_intelligence_edit.setRange(1, 9999)
        self.battle_intelligence_edit.setMinimumWidth(150)
        enemy_layout.addRow(int_label, self.battle_intelligence_edit)

        spi_label = QLabel("✨ Battle SPI (Col 22):")
        spi_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        spi_label.setMinimumWidth(220)
        self.battle_spirit_edit = QSpinBox()
        self.battle_spirit_edit.setRange(1, 9999)
        self.battle_spirit_edit.setMinimumWidth(150)
        enemy_layout.addRow(spi_label, self.battle_spirit_edit)

        spd_label = QLabel("⚡ Battle SPD (Col 23):")
        spd_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        spd_label.setMinimumWidth(220)
        self.battle_speed_edit = QSpinBox()
        self.battle_speed_edit.setRange(1, 9999)
        self.battle_speed_edit.setMinimumWidth(150)
        enemy_layout.addRow(spd_label, self.battle_speed_edit)

        # AI behavior parameters
        skill_id_label = QLabel("🎯 AI Skill ID (Col 36):")
        skill_id_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        skill_id_label.setMinimumWidth(220)
        self.ai_skill_id_edit = QSpinBox()
        self.ai_skill_id_edit.setRange(0, 9999999)
        self.ai_skill_id_edit.setMinimumWidth(150)
        enemy_layout.addRow(skill_id_label, self.ai_skill_id_edit)

        aggression_label = QLabel("💢 AI Aggression (Col 32):")
        aggression_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        aggression_label.setMinimumWidth(220)
        self.ai_aggression_edit = QSpinBox()
        self.ai_aggression_edit.setRange(0, 100)
        self.ai_aggression_edit.setMinimumWidth(150)
        enemy_layout.addRow(aggression_label, self.ai_aggression_edit)

        layout.addWidget(enemy_group)

        # Encounter groups
        encounter_group = QGroupBox("🌍 Encounter Groups")
        encounter_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #84fab0;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
                font-size: 11pt;
            }
            QGroupBox::title {
                color: #2c9558;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        encounter_layout = QVBoxLayout(encounter_group)
        encounter_layout.setSpacing(10)

        encounter_label = QLabel("📍 Appears in encounter groups:")
        encounter_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        encounter_layout.addWidget(encounter_label)

        self.encounter_list = QListWidget()
        self.encounter_list.setStyleSheet("""
            QListWidget {
                border: 2px solid #dee2e6;
                border-radius: 6px;
                padding: 5px;
                background-color: white;
            }
            QListWidget::item {
                padding: 8px;
                margin: 2px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #e7f5ff;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #84fab0, stop:1 #8fd3f4);
                color: white;
            }
        """)
        encounter_layout.addWidget(self.encounter_list)

        encounter_buttons = QHBoxLayout()
        encounter_buttons.setSpacing(10)

        add_group_btn = QPushButton("➕ Add to Group")
        add_group_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #84fab0, stop:1 #8fd3f4);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #6ee89f, stop:1 #7bc9e8);
            }
        """)
        encounter_buttons.addWidget(add_group_btn)

        remove_group_btn = QPushButton("➖ Remove from Group")
        remove_group_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fa709a, stop:1 #fee140);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e85c89, stop:1 #ecd32f);
            }
        """)
        encounter_buttons.addWidget(remove_group_btn)

        encounter_layout.addLayout(encounter_buttons)

        layout.addWidget(encounter_group)

        # Battle formation
        formation_group = QGroupBox("📐 Battle Formation")
        formation_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #f093fb;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
                font-size: 11pt;
            }
            QGroupBox::title {
                color: #c967cc;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        formation_layout = QFormLayout(formation_group)
        formation_layout.setSpacing(12)
        formation_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        formation_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        form_id_label = QLabel("🆔 Formation ID:")
        form_id_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        form_id_label.setMinimumWidth(180)
        self.formation_id_edit = QLineEdit()
        self.formation_id_edit.setMinimumWidth(200)
        formation_layout.addRow(form_id_label, self.formation_id_edit)

        form_type_label = QLabel("📋 Formation Type:")
        form_type_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        form_type_label.setMinimumWidth(180)
        self.formation_type_edit = QLineEdit()
        self.formation_type_edit.setMinimumWidth(200)
        formation_layout.addRow(form_type_label, self.formation_type_edit)

        layout.addWidget(formation_group)

        layout.addStretch()

        # Set the scroll content and add to main layout
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        return tab


    def update_files_tab(self, digimon: DigimonData):
        """Update the files tab with current Digimon data status"""
        file_checks = [
            ("digimon_status.mbe/00_digimon_status_data.csv", bool(digimon.id), "1"),
            ("char_info.mbe/00_char_info.csv", bool(digimon.char_info_data), "1" if digimon.char_info_data else "0"),
            ("text/char_name.mbe/00_Sheet1.csv", bool(digimon.name), "1"),
            ("model_setting.mbe/00_model_setting.csv", bool(digimon.model_setting_data), "1" if digimon.model_setting_data else "0"),
            ("model_locator.mbe/00_model_locator.csv", bool(digimon.model_locator_data), "1" if digimon.model_locator_data else "0"),
            ("model_locator.mbe/01_model_locator_motion.csv", bool(digimon.model_locator_motion_data), str(len(digimon.model_locator_motion_data))),
            ("lod_chara.mbe/00_lod.csv", bool(digimon.lod_data), "1" if digimon.lod_data else "0"),
            ("lod_chara.mbe/01_lod_model.csv", bool(digimon.lod_model_data), "1" if digimon.lod_model_data else "0"),
            ("field_anime.mbe/00_field_move_animation.csv", bool(digimon.field_move_animation_data), str(len(digimon.field_move_animation_data)))
        ]

        complete_count = 0
        for i, (file_name, has_data, count) in enumerate(file_checks):
            status = "✓ Complete" if has_data else "✗ Missing"
            status_color = "green" if has_data else "red"

            # Update table
            status_item = QTableWidgetItem(status)
            status_item.setForeground(Qt.GlobalColor.green if has_data else Qt.GlobalColor.red)
            self.files_table.setItem(i, 1, status_item)
            self.files_table.setItem(i, 2, QTableWidgetItem(count))

            if has_data:
                complete_count += 1

        # Update export status
        if complete_count == 9:
            self.export_status_label.setText("Status: Complete! All 9 files ready for export")
            self.export_status_label.setStyleSheet("font-weight: bold; color: green;")
        else:
            missing_count = 9 - complete_count
            self.export_status_label.setText(f"Status: {missing_count} files missing data")
            self.export_status_label.setStyleSheet("font-weight: bold; color: orange;")

    def update_evolution_tab(self, digimon: DigimonData):
        """Update evolution tab with current Digimon data"""
        # Clear existing data
        for list_name in (
            "evolution_list", "evolution_jogress_list", "evolution_mode_change_list",
            "deevolution_list", "deevolution_jogress_list", "deevolution_mode_change_list",
        ):
            list_widget = getattr(self, list_name, None)
            if list_widget is not None:
                list_widget.clear()

        # Update evolution requirements label (using normalized condition data)
        target_conditions = normalize_evolution_conditions(digimon.evolution_conditions)
        if digimon.evolution_conditions:
            digimon.evolution_conditions = [target_conditions]
        self.requirements_label.setText(self._format_obtain_requirements_summary(target_conditions))

        # Populate evolution paths with detailed requirements
        outgoing_lists = {
            "normal": self.evolution_list,
            "jogress": self.evolution_jogress_list,
            "mode_change": self.evolution_mode_change_list,
        }
        incoming_lists = {
            "normal": self.deevolution_list,
            "jogress": self.deevolution_jogress_list,
            "mode_change": self.deevolution_mode_change_list,
        }

        for evo_index, evo in enumerate(digimon.evolution_paths):
            to_id = evo['to_id']
            to_name = None

            # First check if we have a stored chr_id in the evolution path (for custom Digimon)
            to_chr_id = evo.get('to_chr_id') or evo.get('chr_id')

            # Check imported Digimon first (custom Digimon from dsts-loader)
            if hasattr(self.loader, 'imported_digimon') and self.loader.imported_digimon:
                for imported_digimon in self.loader.imported_digimon:
                    if imported_digimon.id == to_id:
                        to_name = imported_digimon.name
                        break
                    # Also check by chr_id if we have it
                    if to_chr_id and imported_digimon.chr_id == to_chr_id:
                        to_name = imported_digimon.name
                        break

            # If not found in imported, try standard lookup by numeric ID
            if not to_name:
                to_name = self.loader._get_digimon_name_by_id(to_id)

            # If still not found, try chr_id lookup
            if not to_name:
                if not to_chr_id:
                    # Generate chr_id from numeric ID
                    to_chr_id = f"chr{to_id:03d}"
                to_name = self.loader._get_digimon_name_by_chr_id(to_chr_id)
                if not to_name or to_name == to_chr_id:
                    # Try without padding
                    to_chr_id_alt = f"chr{to_id}"
                    if to_chr_id_alt != to_chr_id:
                        to_name = self.loader._get_digimon_name_by_chr_id(to_chr_id_alt)
                        if to_name and to_name != to_chr_id_alt:
                            to_chr_id = to_chr_id_alt

            # Final fallback
            if not to_name:
                to_name = f"Unknown (ID: {to_id})"

            # Build requirements string - check for conditions first (new format), then raw_data (old format)
            req_str = ""
            if 'conditions' in evo and evo['conditions']:
                # Use the comprehensive requirements summary
                req_str = f" {self._format_requirements_summary(evo['conditions'])}"
            elif 'raw_data' in evo and len(evo['raw_data']) > 2:
                # Fall back to old raw_data format
                reqs = []
                level_req = evo['raw_data'][2] if len(evo['raw_data']) > 2 else 0
                if level_req and str(level_req).isdigit() and int(level_req) > 0:
                    reqs.append(f"Lv{level_req}")
                req_str = f" [{', '.join(reqs)}]" if reqs else ""

            category = self._evolution_path_category(evo)
            self._add_path_item(outgoing_lists[category], f"→ {to_name} (ID: {to_id}){req_str}", evo_index)

        # Populate de-evolution sources
        for deevo_index, deevo in enumerate(digimon.deevolution_sources):
            from_id = deevo['from_id']
            from_name = None

            # First check imported Digimon (custom Digimon from dsts-loader)
            if hasattr(self.loader, 'imported_digimon') and self.loader.imported_digimon:
                for imported_digimon in self.loader.imported_digimon:
                    if imported_digimon.id == from_id:
                        from_name = imported_digimon.name
                        break
                    # Also check by chr_id if we have it
                    from_chr_id = deevo.get('from_chr_id')
                    if from_chr_id and imported_digimon.chr_id == from_chr_id:
                        from_name = imported_digimon.name
                        break

            # If not found in imported, try standard lookup
            if not from_name:
                from_name = self.loader._get_digimon_name_by_id(from_id)

            # Try chr_id lookup as fallback
            if not from_name:
                from_chr_id = deevo.get('from_chr_id')
                if from_chr_id:
                    from_name = self.loader._get_digimon_name_by_chr_id(from_chr_id)
                else:
                    # Try generating chr_id from ID
                    from_chr_id = f"chr{from_id:03d}"
                    from_name = self.loader._get_digimon_name_by_chr_id(from_chr_id)
                    if not from_name or from_name == from_chr_id:
                        from_chr_id = f"chr{from_id}"
                        from_name = self.loader._get_digimon_name_by_chr_id(from_chr_id)

            # Final fallback
            if not from_name:
                from_name = f"Unknown (ID: {from_id})"

            category = self._evolution_path_category(deevo, target_conditions)
            req_str = ""
            if category == "jogress" and target_conditions:
                req_str = f" {self._format_requirements_summary(target_conditions)}"
            self._add_path_item(incoming_lists[category], f"← {from_name} (ID: {from_id}){req_str}", deevo_index)

        self._add_empty_path_placeholder(self.evolution_list, "(No normal evolution paths)")
        self._add_empty_path_placeholder(self.evolution_jogress_list, "(No Jogress/DNA evolution paths)")
        self._add_empty_path_placeholder(self.evolution_mode_change_list, "(No Mode Change evolution paths)")
        self._add_empty_path_placeholder(self.deevolution_list, "(No normal pre-evolutions)")
        self._add_empty_path_placeholder(self.deevolution_jogress_list, "(No Jogress/DNA pre-evolutions)")
        self._add_empty_path_placeholder(self.deevolution_mode_change_list, "(No Mode Change pre-evolutions)")

    def edit_evolution_requirements(self):
        """Edit requirements to obtain this Digimon"""
        if not self.current_digimon:
            QMessageBox.warning(self, "No Digimon Loaded", "Please load a Digimon first.")
            return

        existing = normalize_evolution_conditions(self.current_digimon.evolution_conditions)

        # Show the same dialog as used for evolution paths
        new_conditions = self._show_evolution_requirements_dialog(
            f"{self.current_digimon.name} (Requirements to obtain THIS Digimon)",
            existing
        )

        if new_conditions is not None:
            normalized_conditions = self._set_current_evolution_conditions(new_conditions)
            for evo in getattr(self.current_digimon, "evolution_paths", []):
                if safe_evolution_int(evo.get("to_id"), 0) == safe_evolution_int(self.current_digimon.id, 0):
                    evo["conditions"] = dict(normalized_conditions)
                    evo["export_conditions"] = True
            self.update_evolution_tab(self.current_digimon)
            self.mark_as_modified()
            QMessageBox.information(self, "Success", "Evolution requirements updated!")

    def update_evolution_tree_tab(self, digimon: DigimonData):
        """Update the visual evolution tree tab with current Digimon"""
        # This will be implemented to show the tree structure
        # For now, just clear the canvas
        old_layout = self.evolution_tree_canvas.layout()
        if old_layout:
            while old_layout.count():
                child = old_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            QWidget().setLayout(old_layout)

        canvas_layout = QVBoxLayout(self.evolution_tree_canvas)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(f"Evolution tree for {digimon.name} (ID: {digimon.id}) will be displayed here")
        label.setStyleSheet("color: #666; font-size: 12pt; padding: 40px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        canvas_layout.addWidget(label)

    def draw_evolution_tree(self, digimon: DigimonData):
        """Draw visual representation of evolution tree"""
        try:
            from PyQt6.QtWidgets import QTextBrowser

            # Calculate tree structure
            nodes = []

            # Add pre-evolutions (sources)
            for i, deevo in enumerate(digimon.deevolution_sources):
                from_id = deevo.get('from_id', 0)

                # Get name by numeric ID
                from_name = self.loader._get_digimon_name_by_id(from_id)
                if not from_name:
                    from_name = f"ID:{from_id}"

                nodes.append({
                    'name': from_name,
                    'type': 'source',
                    'id': from_id
                })

            # Add current Digimon (center)
            nodes.append({
                'name': digimon.name,
                'type': 'current',
                'id': digimon.id
            })

            # Add evolutions (targets)
            for i, evo in enumerate(digimon.evolution_paths):
                to_id = evo.get('to_id', 0)

                # Get name by numeric ID
                to_name = self.loader._get_digimon_name_by_id(to_id)
                if not to_name:
                    to_name = f"ID:{to_id}"

                nodes.append({
                    'name': to_name,
                    'type': 'target',
                    'id': to_id
                })

            # Create HTML-based tree visualization
            html = self.generate_tree_html(nodes, digimon)

            # Create or update text browser
            text_browser = QTextBrowser()
            text_browser.setHtml(html)
            text_browser.setMinimumSize(600, 400)
            text_browser.setOpenExternalLinks(False)

            # Debug: Print HTML length to verify it's being generated
            print(f"Generated HTML length: {len(html)}")
            print(f"Nodes count: {len(nodes)}")
            print(f"Current Digimon: {digimon.name}")

            # Replace canvas content
            old_layout = self.evolution_tree_canvas.layout()
            if old_layout:
                # Clear existing widgets
                while old_layout.count():
                    child = old_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                # Delete old layout
                QWidget().setLayout(old_layout)

            # Create new layout and add browser
            new_layout = QVBoxLayout(self.evolution_tree_canvas)
            new_layout.setContentsMargins(0, 0, 0, 0)
            new_layout.addWidget(text_browser)

        except Exception as e:
            # Show error in tree area
            error_label = QLabel(f"Error displaying tree: {str(e)}")
            error_label.setStyleSheet("color: red; padding: 20px;")
            error_label.setWordWrap(True)

            old_layout = self.evolution_tree_canvas.layout()
            if old_layout:
                while old_layout.count():
                    child = old_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                QWidget().setLayout(old_layout)

            new_layout = QVBoxLayout(self.evolution_tree_canvas)
            new_layout.addWidget(error_label)

    def generate_tree_html(self, nodes, digimon):
        """Generate HTML representation of evolution tree - Tournament bracket style"""
        html = """
        <html>
        <head>
        <style>
            body {
                font-family: Arial, sans-serif;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0;
            }
            .tournament-container {
                display: table;
                width: 100%;
                table-layout: fixed;
            }
            .tournament-row {
                display: table-row;
            }
            .tournament-cell {
                display: table-cell;
                vertical-align: middle;
                padding: 10px;
            }
            .column-left {
                width: 35%;
                text-align: right;
            }
            .column-center {
                width: 30%;
                text-align: center;
            }
            .column-right {
                width: 35%;
                text-align: left;
            }
            .section-title {
                color: white;
                font-size: 12px;
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 10px;
                padding: 5px 10px;
                background: rgba(255, 255, 255, 0.2);
                border-radius: 5px;
                display: inline-block;
            }
            .node {
                background: rgba(255, 255, 255, 0.95);
                color: #333;
                border: 2px solid white;
                border-radius: 8px;
                padding: 10px 12px;
                margin: 5px 0;
                font-weight: bold;
                font-size: 12px;
                box-shadow: 0 3px 6px rgba(0, 0, 0, 0.3);
                display: inline-block;
                min-width: 150px;
            }
            .node-current {
                background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%);
                color: white;
                font-size: 15px;
                padding: 20px;
                border: 3px solid white;
                min-width: 180px;
            }
            .node-source {
                background: linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%);
                color: white;
            }
            .node-target {
                background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%);
                color: #333;
            }
            .node-name {
                font-weight: bold;
            }
            .node-id {
                font-size: 10px;
                opacity: 0.8;
                margin-top: 4px;
            }
            .connector {
                color: white;
                font-size: 24px;
                font-weight: bold;
                padding: 0 10px;
            }
            .nodes-container {
                display: inline-block;
            }
            .empty-state {
                color: white;
                text-align: center;
                padding: 40px 20px;
                font-size: 14px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
            }
            .count-badge {
                background: rgba(255, 255, 255, 0.4);
                color: white;
                padding: 2px 6px;
                border-radius: 10px;
                font-size: 10px;
                margin-left: 5px;
            }
        </style>
        </head>
        <body>
        """

        # Pre-evolutions, current, and target nodes
        sources = [n for n in nodes if n['type'] == 'source']
        current = [n for n in nodes if n['type'] == 'current']
        targets = [n for n in nodes if n['type'] == 'target']

        # Check if we have any data
        if not sources and not targets:
            html += '<div class="empty-state">'
            html += '<b style="font-size: 16px;">⚠️ No Evolution Data Available</b><br/><br/>'
            html += 'This Digimon has no defined pre-evolutions or evolutions.<br/>'
            html += 'Use the buttons above to add evolution paths.'
            html += '</div>'
        else:
            html += '<div class="tournament-container">'
            html += '<div class="tournament-row">'

            # Left column - Pre-evolutions
            html += '<div class="tournament-cell column-left">'
            if sources:
                html += f'<div class="section-title">⬅️ PRE-EVOLUTION <span class="count-badge">{len(sources)}</span></div><br/>'
                html += '<div class="nodes-container">'
                for node in sources:
                    html += f'<div class="node node-source"><div class="node-name">{node["name"]}</div><div class="node-id">ID: {node["id"]}</div></div><br/>'
                html += '</div>'
            html += '</div>'

            # Center connector arrow
            html += '<div class="tournament-cell" style="width: 5%; text-align: center;">'
            if sources:
                html += '<div class="connector">→</div>'
            html += '</div>'

            # Center column - Current Digimon
            html += '<div class="tournament-cell column-center">'
            if current:
                current_node = current[0]
                html += '<div class="section-title">📍 CURRENT</div><br/>'
                html += f'<div class="node node-current"><div class="node-name">{current_node["name"]}</div><div class="node-id">ID: {current_node["id"]}</div></div>'
            html += '</div>'

            # Center-Right connector arrow
            html += '<div class="tournament-cell" style="width: 5%; text-align: center;">'
            if targets:
                html += '<div class="connector">→</div>'
            html += '</div>'

            # Right column - Evolutions
            html += '<div class="tournament-cell column-right">'
            if targets:
                html += f'<div class="section-title">➡️ EVOLUTION <span class="count-badge">{len(targets)}</span></div><br/>'
                html += '<div class="nodes-container">'
                for node in targets:
                    html += f'<div class="node node-target"><div class="node-name">{node["name"]}</div><div class="node-id">ID: {node["id"]}</div></div><br/>'
                html += '</div>'
            html += '</div>'

            html += '</div>' # Close tournament-row
            html += '</div>' # Close tournament-container

        html += """
        </body>
        </html>
        """

        return html

    def update_battle_tab(self, digimon: DigimonData):
        """Update battle tab with current Digimon data"""
        # Clear existing data
        self.encounter_list.clear()

        # Populate battle enemy data
        if digimon.battle_enemy_data:
            enemy = digimon.battle_enemy_data
            self.enemy_id_edit.setText(str(enemy.get('enemy_id', '')))
            self.base_digimon_id_edit.setText(str(enemy.get('base_id', '')))
            self.ai_level_edit.setValue(enemy.get('level', 1))

            # Battle stats
            self.battle_hp_edit.setValue(enemy.get('hp', 0))
            self.battle_sp_edit.setValue(enemy.get('sp', 0))
            self.battle_attack_edit.setValue(enemy.get('attack', 0))
            self.battle_defense_edit.setValue(enemy.get('defense', 0))
            self.battle_intelligence_edit.setValue(enemy.get('intelligence', 0))
            self.battle_spirit_edit.setValue(enemy.get('spirit', 0))
            self.battle_speed_edit.setValue(enemy.get('speed', 0))

            # AI parameters (would need to be loaded from raw_data)
            raw_data = enemy.get('raw_data', [])
            if len(raw_data) > 36:
                self.ai_skill_id_edit.setValue(int(raw_data[36]) if raw_data[36] else 0)
            if len(raw_data) > 32:
                self.ai_aggression_edit.setValue(int(raw_data[32]) if raw_data[32] else 0)
        else:
            self.enemy_id_edit.clear()
            self.base_digimon_id_edit.clear()
            self.ai_level_edit.setValue(1)
            self.battle_hp_edit.setValue(0)
            self.battle_sp_edit.setValue(0)
            self.battle_attack_edit.setValue(0)
            self.battle_defense_edit.setValue(0)
            self.battle_intelligence_edit.setValue(0)
            self.battle_spirit_edit.setValue(0)
            self.battle_speed_edit.setValue(0)
            self.ai_skill_id_edit.setValue(0)
            self.ai_aggression_edit.setValue(0)

        # Populate encounter groups
        for encounter in digimon.encounter_groups:
            encounter_id = encounter.get('encounter_id', 0)
            slot = encounter.get('slot', 0)
            count = encounter.get('enemy_count', 1)
            group_text = f"Encounter {encounter_id} (Slot {slot+1}, Count: {count})"
            self.encounter_list.addItem(group_text)

        # Populate battle formation data
        if digimon.battle_formation_data:
            formation = digimon.battle_formation_data
            self.formation_id_edit.setText(str(formation.get('formation_id', '')))
            self.formation_type_edit.setText(formation.get('formation_type', ''))
        else:
            self.formation_id_edit.clear()
            self.formation_type_edit.clear()


    def get_source_mode(self) -> str:
        """Return the selected source mode as base, dlc, or all."""
        if not hasattr(self, 'source_combo'):
            return "all"

        source_mode = self.source_combo.currentData()
        if source_mode is True:
            return "dlc"
        if source_mode is False:
            return "base"
        return source_mode or "all"

    def get_sort_mode(self) -> str:
        """Return the selected Digimon list sort mode."""
        if not hasattr(self, 'sort_combo'):
            return "name"
        return self.sort_combo.currentData() or "name"

    def is_loaded_digimon_from_dlc(self) -> bool:
        """Return whether the currently loaded Digimon came from DLC data."""
        return bool(getattr(self, 'current_digimon_from_dlc', False))

    def chr_sort_key(self, chr_id: str):
        """Sort chr IDs naturally, so chr99 comes before chr100."""
        clean_chr_id = (chr_id or "").strip('"').lower()
        split_at = len(clean_chr_id)
        while split_at > 0 and clean_chr_id[split_at - 1].isdigit():
            split_at -= 1

        prefix = clean_chr_id[:split_at]
        number_text = clean_chr_id[split_at:]
        number = int(number_text) if number_text else -1
        return (prefix, number, clean_chr_id)

    def make_digimon_display_name(self, entry: dict) -> str:
        """Create the visible label for a Digimon list entry."""
        prefix = "📥 " if entry.get("imported") else ""
        display_name = f"{prefix}{entry['name']} ({entry['chr_id']})"

        if self.get_source_mode() in ("all", "mods"):
            source_label = {
                "base": "Base",
                "dlc": "DLC",
                "imported": "Imported",
                "mod": entry.get("source_label", "Mod"),
            }.get(entry.get("source"), entry.get("source_label", entry.get("source", "")))
            if source_label:
                display_name = f"{display_name} [{source_label}]"

        return display_name

    def related_source_display_name(self, entry: dict) -> str:
        """Create the source selector label for original/base asset imports."""
        source_label = "DLC" if entry.get("source") == "dlc" else "Base"
        return f"{entry['name']} ({entry['chr_id']}) [{source_label}]"

    def get_related_source_entries(self) -> List[dict]:
        """Build source Digimon choices from base/DLC status rows."""
        if self._related_source_entries_cache is not None:
            return list(self._related_source_entries_cache)

        entries = []
        seen_chr_ids = set()

        status_files = []
        base_status = self.loader._resolve_prefixed_file(
            self.loader.data_path / "digimon_status.mbe" / "000_digimon_status_data.csv"
        )
        if base_status.exists():
            status_files.append(("base", base_status))
        status_files.extend(
            ("dlc", status_file)
            for _dlc_id, status_file in self.loader.iter_dlc_csv_files(
                "data", "digimon_status", "000_digimon_status_data.csv"
            )
        )

        for source_name, status_file in status_files:
            try:
                rows = self.loader.load_csv(status_file)
            except Exception:
                continue

            for row in rows[1:]:
                if len(row) <= 3:
                    continue
                chr_id = _clean_status_cell(row[3])
                if not chr_id or chr_id in seen_chr_ids:
                    continue

                try:
                    digimon_id = int(_clean_status_cell(row[0]))
                except (TypeError, ValueError):
                    digimon_id = 0

                char_key = _clean_status_cell(row[2]) if len(row) > 2 else ""
                name = self.loader._get_digimon_name(char_key) if char_key else None
                if not name:
                    name = self.loader._get_digimon_name_by_chr_id(chr_id) or chr_id

                seen_chr_ids.add(chr_id)
                entries.append({
                    "id": digimon_id,
                    "name": name,
                    "chr_id": chr_id,
                    "source": source_name,
                })

        entries.sort(key=lambda entry: (entry["name"].casefold(), self.chr_sort_key(entry["chr_id"])))
        self._related_source_entries_cache = list(entries)
        return list(entries)

    def populate_related_source_combo(self):
        """Refresh the Model Animation source Digimon dropdown."""
        if not hasattr(self, "related_source_combo"):
            return

        previous_chr_id = ""
        current_data = self.related_source_combo.currentData()
        if isinstance(current_data, dict):
            previous_chr_id = current_data.get("chr_id", "")
        if not previous_chr_id and hasattr(self, "animation_ref_edit"):
            previous_chr_id = self.animation_ref_edit.text().strip()

        self.related_source_entries = self.get_related_source_entries()
        self.related_source_combo.blockSignals(True)
        self.related_source_combo.clear()
        self.related_source_combo.addItem(RELATED_SOURCE_PROMPT, None)
        for entry in self.related_source_entries:
            self.related_source_combo.addItem(self.related_source_display_name(entry), entry)
        self.related_source_combo.blockSignals(False)

        if previous_chr_id:
            self.select_related_source_by_chr(previous_chr_id)

    def select_related_source_by_chr(self, chr_id: str):
        """Select a related source entry by chr_id if it exists."""
        if not hasattr(self, "related_source_combo") or not chr_id:
            return
        clean_chr_id = chr_id.strip().strip('"')
        for index in range(self.related_source_combo.count()):
            entry = self.related_source_combo.itemData(index)
            if isinstance(entry, dict) and entry.get("chr_id") == clean_chr_id:
                self.related_source_combo.setCurrentIndex(index)
                return
        self.related_source_combo.setCurrentIndex(0)

    def get_selected_related_source(self) -> Optional[dict]:
        """Return the selected source Digimon entry, accepting typed combo text."""
        if not hasattr(self, "related_source_combo"):
            return None

        typed = self.related_source_combo.currentText().strip().lower()
        current_index = self.related_source_combo.currentIndex()
        data = self.related_source_combo.currentData()
        current_label = self.related_source_combo.itemText(current_index).strip().lower() if current_index >= 0 else ""
        if isinstance(data, dict) and (not typed or typed == current_label):
            return data

        chr_match = re.search(r"\(([^)]+)\)", typed)
        typed_chr_id = chr_match.group(1).strip().lower() if chr_match else typed

        for entry in getattr(self, "related_source_entries", []):
            if typed_chr_id == entry["chr_id"].lower():
                return entry
            if typed and typed in entry["name"].lower():
                return entry
        return None

    def browse_related_extract_path(self):
        """Choose the extracted Time Stranger folder used for asset imports."""
        start_path = self.related_extract_path_edit.text().strip() if hasattr(self, "related_extract_path_edit") else ""
        if not start_path:
            start_path = str(get_existing_directory_start(get_default_extracted_game_path()))

        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Extracted Time Stranger Folder",
            start_path,
            QFileDialog.Option.ShowDirsOnly
        )
        if selected_dir:
            self.related_extract_path_edit.setText(selected_dir)

    def include_related_texture_extras(self) -> bool:
        """Return whether optional texture maps should be imported."""
        return bool(
            hasattr(self, "related_normals_toggle")
            and self.related_normals_toggle.isChecked()
        )

    def import_all_related_model_files(self) -> bool:
        """Return whether all matching model/animation files should be imported."""
        return bool(
            hasattr(self, "related_all_assets_toggle")
            and self.related_all_assets_toggle.isChecked()
        )

    def _chr_digits(self, chr_id: str) -> str:
        match = re.search(r"(\d+)$", (chr_id or "").strip().strip('"'))
        return match.group(1) if match else ""

    def _replace_token(self, text: str, old: str, new: str, avoid_digit_suffix: bool = False) -> str:
        if not old or old == new:
            return text
        pattern = re.escape(old)
        if avoid_digit_suffix:
            pattern += r"(?!\d)"
        return re.sub(pattern, new, text, flags=re.IGNORECASE)

    def _rename_related_asset(self, filename: str, source_entry: dict, target_chr_id: str, target_id: int) -> str:
        """Rename a source asset filename for the target Digimon and convert .img to .dds."""
        source_chr_id = source_entry.get("chr_id", "")
        source_digits = self._chr_digits(source_chr_id)
        target_digits = self._chr_digits(target_chr_id) or str(target_id)
        source_id = int(source_entry.get("id") or 0)
        target_id_text = str(target_id if target_id > 0 else target_digits)

        suffix = Path(filename).suffix
        stem = Path(filename).stem
        if suffix.lower() == ".img":
            suffix = ".dds"

        if source_id:
            source_id_text = str(source_id)
            source_padded = f"{source_id:04d}"
            source_icon_id = str(source_id + 1000)

            # Common UI/image naming patterns use numeric IDs instead of chr IDs.
            stem = self._replace_token(stem, f"ui_chara_icon_{source_icon_id}", f"ui_chara_icon_{target_id_text}", True)
            stem = self._replace_token(stem, f"ui_chara_icon_{source_id_text}", f"ui_chara_icon_{target_id_text}", True)
            stem = self._replace_token(stem, f"dot{source_id_text}", f"dot{target_id_text}", True)
            stem = self._replace_token(stem, f"digimon{source_id_text}", f"digimon{target_id_text}", True)
            stem = self._replace_token(stem, f"ef_chr_{source_padded}", f"ef_chr_{target_id_text}", True)

        # Most model, animation, and texture files carry the chr token directly.
        stem = self._replace_token(stem, source_chr_id, target_chr_id, True)

        # A few animation files use r### as a secondary related reference.
        if source_digits and target_digits:
            stem = self._replace_token(stem, f"r{source_digits}", f"r{target_digits}", True)

        return f"{stem}{suffix}"

    def _related_search_roots(self, extracted_root: Path) -> List[Path]:
        """Return likely extracted asset roots, preferring patch over app_0 overrides."""
        roots = []
        for name in ("patch.dx11", "app_0.dx11"):
            root = extracted_root / name
            if root.exists():
                roots.append(root)

        for root in sorted(extracted_root.glob("*.dx11")):
            if root not in roots:
                roots.append(root)

        return roots if roots else [extracted_root]

    def _related_file_matches(self, file_path: Path, source_entry: dict) -> bool:
        """Return whether a file looks related to the selected source Digimon."""
        name = file_path.name.lower()
        if name.startswith(("ui_digicard_card_", "ui_digicard_thum_")):
            return False

        source_chr_id = source_entry.get("chr_id", "").lower()
        source_id = int(source_entry.get("id") or 0)

        if source_chr_id and source_chr_id in name:
            return True

        if not source_id:
            return False

        source_id_text = str(source_id)
        source_padded = f"{source_id:04d}"
        source_icon_id = str(source_id + 1000)
        numeric_patterns = (
            f"dot{source_id_text}",
            f"ui_chara_icon_{source_id_text}",
            f"ui_chara_icon_{source_icon_id}",
            f"digimon{source_id_text}",
            f"ef_chr_{source_padded}",
        )
        return any(pattern in name for pattern in numeric_patterns)

    def _is_basic_related_model_file(self, file_path: Path, source_entry: dict) -> bool:
        """Return whether a model file is part of the lean recolor import set."""
        source_chr_id = source_entry.get("chr_id", "").lower()
        if not source_chr_id:
            return False

        name = file_path.name.lower()
        basic_names = {
            f"{source_chr_id}.anim",
            f"{source_chr_id}.geom",
            f"{source_chr_id}.nlst",
            f"{source_chr_id}_lod_2.anim",
            f"{source_chr_id}_lod_2.geom",
            f"{source_chr_id}_lod_2.nlst",
        }
        return name in basic_names

    def _is_optional_related_texture_map(self, file_path: Path, source_entry: dict) -> bool:
        """Return whether a texture is an optional normal/material/extra map."""
        source_chr_id = source_entry.get("chr_id", "").lower()
        if not source_chr_id:
            return False

        stem = file_path.stem.lower()
        if not stem.startswith(source_chr_id):
            return False

        tail = stem[len(source_chr_id):]
        return bool(re.search(r"\d[hlmns]$", tail))

    def _is_tiny_related_effect_texture(self, file_path: Path, source_entry: dict) -> bool:
        """Skip tiny effect/dot textures that do not help normal recolor imports."""
        stem = file_path.stem.lower()
        source_chr_id = source_entry.get("chr_id", "").lower()
        if source_chr_id and stem.startswith(source_chr_id):
            tail = stem[len(source_chr_id):]
            if re.fullmatch(r"e\d{2}|f\d{2}em", tail):
                return True
        return bool(TINY_EFFECT_TEXTURE_RE.fullmatch(stem))

    def _iter_related_asset_files(
        self,
        extracted_root: Path,
        source_entry: dict,
        include_texture_extras: bool = False,
        import_all_model_files: bool = False,
    ) -> List[Path]:
        """Find related model/animation files and images in an extracted game folder."""
        image_suffixes = {".img", ".dds"}
        asset_suffixes = {
            ".anim", ".geom", ".nlst", ".sprk", ".bson", ".skel", ".matl", ".mset", ".mot", ".bin",
            ".img", ".dds",
        }

        matches = []
        seen = set()
        for root in self._related_search_roots(extracted_root):
            if not root.exists():
                continue
            search_dirs = [root]
            images_dir = root / "images"
            if images_dir.exists():
                search_dirs.append(images_dir)

            for search_dir in search_dirs:
                source_chr_id = source_entry.get("chr_id", "").lower()
                source_id = int(source_entry.get("id") or 0)
                patterns = [f"*{source_chr_id}*"] if source_chr_id else []
                if search_dir.name.lower() == "images" and source_id:
                    patterns.extend([
                        f"*{source_id}*",
                        f"*{source_id + 1000}*",
                        f"*{source_id:04d}*",
                    ])

                candidate_files = []
                for pattern in dict.fromkeys(patterns):
                    try:
                        candidate_files.extend(search_dir.glob(pattern))
                    except OSError:
                        continue

                for file_path in candidate_files:
                    if not file_path.is_file():
                        continue
                    suffix = file_path.suffix.lower()
                    if suffix not in asset_suffixes:
                        continue
                    if suffix in image_suffixes or file_path.parent.name.lower() == "images":
                        if self._related_file_matches(file_path, source_entry):
                            if self._is_tiny_related_effect_texture(file_path, source_entry):
                                continue
                            if not include_texture_extras and self._is_optional_related_texture_map(file_path, source_entry):
                                continue
                            key = file_path.name.lower()
                            if key not in seen:
                                seen.add(key)
                                matches.append(file_path)
                    elif source_entry.get("chr_id", "").lower() in file_path.name.lower():
                        if not import_all_model_files and not self._is_basic_related_model_file(file_path, source_entry):
                            continue
                        key = file_path.name.lower()
                        if key not in seen:
                            seen.add(key)
                            matches.append(file_path)
        return matches

    def import_related_files_to_dsts_loader(
        self,
        dsts_loader_root: Path,
        digimon: DigimonData,
        overwrite: bool = False,
    ) -> dict:
        """Copy/rename source model files and convert source .img textures to .dds."""
        source_entry = self.get_selected_related_source()
        if not source_entry:
            return {"ok": False, "error": "Select a source Digimon first."}

        extracted_root = (
            Path(self.related_extract_path_edit.text().strip())
            if hasattr(self, "related_extract_path_edit")
            else get_default_extracted_game_path()
        )
        if not extracted_root.exists():
            return {"ok": False, "error": f"Extracted folder not found:\n{extracted_root}"}

        target_chr_id = (self.chr_id_edit.text().strip() if hasattr(self, "chr_id_edit") else digimon.chr_id).strip('"')
        target_id = self.id_spin.value() if hasattr(self, "id_spin") else digimon.id
        if not target_chr_id:
            return {"ok": False, "error": "Set the target Chr ID before importing related files."}

        dsts_loader_root = self._resolve_dsts_loader_root(Path(dsts_loader_root), allow_create=True)
        if not dsts_loader_root:
            return {"ok": False, "error": "Could not resolve the dsts-loader output folder."}

        patch_dir = dsts_loader_root / "patch"
        images_dir = patch_dir / "images"
        patch_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)

        copied = []
        skipped = []
        files = self._iter_related_asset_files(
            extracted_root,
            source_entry,
            include_texture_extras=self.include_related_texture_extras(),
            import_all_model_files=self.import_all_related_model_files(),
        )
        image_suffixes = {".img", ".dds"}
        seen_destinations = set()

        for source_file in files:
            dest_name = self._rename_related_asset(source_file.name, source_entry, target_chr_id, target_id)
            is_image = source_file.suffix.lower() in image_suffixes or source_file.parent.name.lower() == "images"
            dest_dir = images_dir if is_image else patch_dir
            dest_file = dest_dir / dest_name
            destination_key = str(dest_file).lower()
            if destination_key in seen_destinations:
                continue
            seen_destinations.add(destination_key)

            if dest_file.exists() and not overwrite:
                skipped.append(dest_file)
                continue

            shutil.copy2(source_file, dest_file)
            copied.append(dest_file)

        return {
            "ok": True,
            "source": source_entry,
            "target_chr_id": target_chr_id,
            "target_id": target_id,
            "copied": copied,
            "skipped": skipped,
            "found": len(files),
            "dsts_loader_root": dsts_loader_root,
        }

    def _parse_geom_texture_name(self, name: str) -> Optional[Tuple[str, int, str]]:
        """Split a texture basename into head, two-digit variant index, and tail."""
        match = GEOM_INDEXED_TEXTURE_RE.match(name)
        if not match:
            return None
        return (
            match.group("head"),
            int(match.group("idx")),
            match.group("tail") or "",
        )

    def _next_free_geom_texture_name(self, old_name: str, reserved_lower: Set[str]) -> Optional[str]:
        """Return the next same-length texture name by bumping its final two-digit index."""
        parsed = self._parse_geom_texture_name(old_name)
        if not parsed:
            return None

        head, index, tail = parsed
        for candidate_index in range(index + 1, 100):
            candidate = f"{head}{candidate_index:02d}{tail}"
            if candidate.lower() in reserved_lower:
                continue
            if len(candidate.encode("ascii")) == len(old_name.encode("ascii")):
                return candidate
        return None

    def _list_patch_texture_images(self, images_dir: Path) -> Dict[str, List[Path]]:
        """Return image files keyed by lowercase basename, matching the original geom helper script."""
        image_suffixes = {".img", ".dds", ".png"}
        image_basenames: Dict[str, List[Path]] = {}
        if not images_dir.exists():
            return image_basenames

        for path in sorted(images_dir.glob("*")):
            if not path.is_file() or path.suffix.lower() not in image_suffixes:
                continue
            image_basenames.setdefault(path.stem.lower(), []).append(path)
        return image_basenames

    def _extract_geom_texture_tokens(self, geom_path: Path) -> Set[str]:
        """Read ASCII-ish texture tokens from a .geom without attempting to parse the full format."""
        tokens: Set[str] = set()
        for match in GEOM_TEXTURE_TOKEN_RE.finditer(geom_path.read_bytes()):
            try:
                tokens.add(match.group().decode("ascii"))
            except UnicodeDecodeError:
                continue
        return tokens

    def _patch_geom_bytes(self, data: bytes, mapping: Dict[str, str]) -> Tuple[bytes, Dict[str, int]]:
        """Apply same-length texture token replacements to raw .geom bytes."""
        counts: Dict[str, int] = {}
        for old_name, new_name in sorted(mapping.items(), key=lambda item: (-len(item[0]), item[0])):
            old_bytes = old_name.encode("ascii")
            new_bytes = new_name.encode("ascii")
            if len(old_bytes) != len(new_bytes):
                raise ValueError(f"Unsafe .geom texture rename length: {old_name} -> {new_name}")

            count = data.count(old_bytes)
            counts[old_name] = count
            if count:
                data = data.replace(old_bytes, new_bytes)
        return data, counts

    def _build_geom_texture_rename_plan(
        self,
        patch_dir: Path,
        source_entry: dict,
        target_chr_id: str,
    ) -> dict:
        """Plan safe .geom texture token patches and matching image renames."""
        images_dir = patch_dir / "images"
        geom_files = sorted(patch_dir.glob("*.geom"))
        if not images_dir.is_dir():
            return {"ok": False, "error": f"Images folder not found:\n{images_dir}"}
        if not geom_files:
            return {"ok": False, "error": f"No .geom files found in:\n{patch_dir}"}

        image_basenames = self._list_patch_texture_images(images_dir)
        if not image_basenames:
            return {"ok": False, "error": f"No .img/.dds/.png files found in:\n{images_dir}"}

        geom_tokens: Set[str] = set()
        for geom_file in geom_files:
            geom_tokens.update(self._extract_geom_texture_tokens(geom_file))

        token_by_lower = {token.lower(): token for token in geom_tokens}
        reserved_lower = set(image_basenames.keys()) | {token.lower() for token in geom_tokens}
        source_chr_id = str(source_entry.get("chr_id", "")).strip().strip('"')
        source_chr_lower = source_chr_id.lower()
        target_chr_lower = target_chr_id.lower()

        mapping: Dict[str, str] = {}
        image_ops: List[Tuple[Path, Path]] = []
        destination_keys: Set[str] = set()
        skipped_unindexed: List[str] = []
        skipped_missing_images: List[str] = []

        for image_stem_lower, image_paths in sorted(image_basenames.items()):
            old_token = token_by_lower.get(image_stem_lower)
            existing_bumped_token = ""
            if old_token:
                token_parts = self._parse_geom_texture_name(old_token)
                if token_parts and token_parts[1] > 1:
                    # A source-style image already matching a non-01 .geom token
                    # is usually the result of a previous successful patch. Do
                    # not keep bumping it on repeated runs.
                    continue

            # The editor imports copied images under the new Chr ID first. The
            # original .geom still contains source-length texture tokens, so the
            # safe route is: target image name -> source token -> bumped variant.
            if not old_token and source_chr_lower and target_chr_lower and image_stem_lower.startswith(target_chr_lower):
                source_like_stem = source_chr_lower + image_stem_lower[len(target_chr_lower):]
                old_token = token_by_lower.get(source_like_stem)

            # If the user already renamed images manually, recover by matching a
            # bumped image name back to the older same-length token still inside
            # the .geom. Example: image chr395a02.dds + geom chr395a01.
            if not old_token and source_chr_lower and image_stem_lower.startswith(source_chr_lower):
                image_parts = self._parse_geom_texture_name(image_stem_lower)
                if image_parts:
                    image_head, image_index, image_tail = image_parts
                    for token in sorted(geom_tokens):
                        token_parts = self._parse_geom_texture_name(token)
                        if not token_parts:
                            continue
                        token_head, token_index, token_tail = token_parts
                        if not token.lower().startswith(source_chr_lower):
                            continue
                        if token_index >= image_index:
                            continue
                        if token_head.lower() == image_head.lower() and token_tail.lower() == image_tail.lower():
                            old_token = token
                            existing_bumped_token = image_paths[0].stem
                            break

            if not old_token:
                continue
            if source_chr_lower and not old_token.lower().startswith(source_chr_lower):
                continue

            new_token = mapping.get(old_token)
            if not new_token:
                new_token = existing_bumped_token or self._next_free_geom_texture_name(old_token, reserved_lower)
                if not new_token:
                    skipped_unindexed.append(old_token)
                    continue
                mapping[old_token] = new_token
                reserved_lower.add(new_token.lower())

            for image_path in image_paths:
                destination = image_path.with_name(new_token + image_path.suffix)
                destination_key = str(destination).lower()
                if destination_key in destination_keys:
                    continue
                destination_keys.add(destination_key)
                image_ops.append((image_path, destination))

        # The .geom is allowed to reference a bumped texture only when that
        # texture is actually available locally. Optional maps such as
        # chr###a01l/m/n/s should keep pointing at the source game's files when
        # the recolor did not import matching bumped copies.
        planned_image_basenames = set(image_basenames.keys())
        planned_image_basenames.update(destination.stem.lower() for _, destination in image_ops)
        missing_image_mapping = {
            old_token: new_token
            for old_token, new_token in mapping.items()
            if new_token.lower() not in planned_image_basenames
        }
        if missing_image_mapping:
            for old_token, new_token in sorted(missing_image_mapping.items()):
                skipped_missing_images.append(f"{old_token} -> {new_token}")
                mapping.pop(old_token, None)

            allowed_targets = {new_token.lower() for new_token in mapping.values()}
            image_ops = [
                (source, destination)
                for source, destination in image_ops
                if destination.stem.lower() in allowed_targets
            ]

        if not mapping:
            return {
                "ok": False,
                "error": (
                    "No matching texture names found to rename.\n\n"
                    "This usually means the .geom files were already patched, or the images do not match the selected source Digimon."
                ),
                "skipped_unindexed": skipped_unindexed,
                "skipped_missing_images": skipped_missing_images,
            }

        collisions = [
            destination for source, destination in image_ops
            if destination.exists() and str(source).lower() != str(destination).lower()
        ]
        if collisions:
            preview = "\n".join(f"- {path.name}" for path in collisions[:10])
            extra = f"\n... and {len(collisions) - 10} more" if len(collisions) > 10 else ""
            return {
                "ok": False,
                "error": f"Texture rename destination already exists. Nothing was changed:\n{preview}{extra}",
            }

        return {
            "ok": True,
            "geom_files": geom_files,
            "mapping": mapping,
            "image_ops": image_ops,
            "skipped_unindexed": skipped_unindexed,
            "skipped_missing_images": skipped_missing_images,
        }

    def rename_geom_textures_in_patch(self, dsts_loader_root: Path, source_entry: dict, target_chr_id: str) -> dict:
        """Patch copied .geom files so recolor images can use their own bumped texture names."""
        dsts_loader_root = self._resolve_dsts_loader_root(Path(dsts_loader_root), allow_create=False)
        if not dsts_loader_root:
            return {"ok": False, "error": "Could not resolve the dsts-loader folder."}

        patch_dir = dsts_loader_root / "patch"
        if not patch_dir.exists():
            return {"ok": False, "error": f"Patch folder not found:\n{patch_dir}"}

        plan = self._build_geom_texture_rename_plan(patch_dir, source_entry, target_chr_id)
        if not plan.get("ok"):
            return plan

        replacement_counts: Dict[str, int] = {}
        for geom_file in plan["geom_files"]:
            original_data = geom_file.read_bytes()
            patched_data, counts = self._patch_geom_bytes(original_data, plan["mapping"])
            total_replacements = sum(counts.values())
            if not total_replacements:
                continue

            geom_file.write_bytes(patched_data)
            replacement_counts[geom_file.name] = total_replacements

        renamed_images = []
        for source, destination in plan["image_ops"]:
            if str(source).lower() == str(destination).lower():
                continue
            source.rename(destination)
            renamed_images.append((source, destination))

        return {
            "ok": True,
            "mapping": plan["mapping"],
            "replacement_counts": replacement_counts,
            "renamed_images": renamed_images,
            "skipped_unindexed": plan.get("skipped_unindexed", []),
            "skipped_missing_images": plan.get("skipped_missing_images", []),
        }

    def format_geom_texture_rename_summary(self, summary: dict) -> str:
        """Create a compact status line for the .geom texture rename action."""
        if not summary.get("ok"):
            return summary.get("error", "Texture rename failed.")

        total_replacements = sum(summary.get("replacement_counts", {}).values())
        return (
            f"Renamed .geom textures: {len(summary.get('mapping', {}))} texture names, "
            f"{total_replacements} replacements, "
            f"{len(summary.get('renamed_images', []))} images renamed"
            f"{self._format_geom_skip_suffix(summary)}"
        )

    def _format_geom_skip_suffix(self, summary: dict) -> str:
        """Append compact skip counts for .geom texture references left on source assets."""
        missing_images = summary.get("skipped_missing_images", [])
        unindexed = summary.get("skipped_unindexed", [])
        parts = []
        if missing_images:
            parts.append(f"{len(missing_images)} missing local texture refs kept original")
        if unindexed:
            parts.append(f"{len(unindexed)} unindexed refs skipped")
        return f" ({'; '.join(parts)})" if parts else ""

    def rename_geom_textures_now(self):
        """Run the integrated geom texture rename helper for the current mod patch folder."""
        if not self.current_digimon:
            QMessageBox.warning(self, "No Digimon Loaded", "Load or create a Digimon before renaming .geom textures.")
            return

        self.update_digimon_from_form()
        source_entry = self.get_selected_related_source()
        if not source_entry:
            QMessageBox.warning(self, "No Source Digimon", "Select the original source Digimon first.")
            return

        target_chr_id = self.chr_id_edit.text().strip().strip('"') if hasattr(self, "chr_id_edit") else self.current_digimon.chr_id
        if not target_chr_id:
            QMessageBox.warning(self, "Missing Chr ID", "Set the target Chr ID before renaming .geom textures.")
            return

        dsts_loader_root = self._related_import_root_for_current_digimon()
        if not dsts_loader_root:
            selected_dir = QFileDialog.getExistingDirectory(
                self,
                "Select Reloaded II Mod or dsts-loader Directory for .geom Texture Rename",
                str(get_existing_directory_start(get_default_mod_loader_path())),
                QFileDialog.Option.ShowDirsOnly
            )
            if not selected_dir:
                return
            dsts_loader_root = self._resolve_dsts_loader_root(Path(selected_dir), allow_create=False)

        summary = self.rename_geom_textures_in_patch(dsts_loader_root, source_entry, target_chr_id)
        message = self.format_geom_texture_rename_summary(summary)
        self.related_import_status_label.setText(message)

        if summary.get("ok"):
            QMessageBox.information(self, ".geom Textures Renamed", message)
        else:
            QMessageBox.warning(self, ".geom Texture Rename Failed", message)

    def format_related_import_summary(self, summary: dict) -> str:
        """Create a compact human-readable import result."""
        if not summary.get("ok"):
            return summary.get("error", "Related file import failed.")
        source = summary.get("source", {})
        return (
            f"{source.get('name', 'Source')} ({source.get('chr_id', '?')}) -> "
            f"{summary.get('target_chr_id', '?')}: "
            f"{len(summary.get('copied', []))} copied, "
            f"{len(summary.get('skipped', []))} skipped, "
            f"{summary.get('found', 0)} found"
        )

    def _related_import_root_for_current_digimon(self) -> Optional[Path]:
        """Return the remembered dsts-loader root for the current Digimon, if any."""
        if not self.current_digimon:
            return None
        original_identity = dict(getattr(self, "loaded_digimon_identity", {}) or {})
        original_chr_id = str(original_identity.get("chr_id", ""))
        return self._imported_dsts_loader_root(self.current_digimon, original_chr_id) or self._active_dsts_loader_root()

    def import_related_files_now(self):
        """Manually import related model/image files into a dsts-loader folder."""
        if not self.current_digimon:
            QMessageBox.warning(self, "No Digimon Loaded", "Load or create a Digimon before importing related files.")
            return

        self.update_digimon_from_form()

        dsts_loader_root = self._related_import_root_for_current_digimon()
        if not dsts_loader_root:
            selected_dir = QFileDialog.getExistingDirectory(
                self,
                "Select Reloaded II Mod or dsts-loader Directory for Related Files",
                str(get_existing_directory_start(get_default_mod_loader_path())),
                QFileDialog.Option.ShowDirsOnly
            )
            if not selected_dir:
                return
            dsts_loader_root = self._resolve_dsts_loader_root(Path(selected_dir), allow_create=True)

        if not dsts_loader_root:
            QMessageBox.warning(self, "Import Failed", "Could not resolve the selected dsts-loader folder.")
            return

        overwrite_reply = QMessageBox.question(
            self,
            "Import Related Files",
            "Overwrite existing related files?\n\nChoose No to only copy files that are missing.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.No
        )
        if overwrite_reply == QMessageBox.StandardButton.Cancel:
            return

        summary = self.import_related_files_to_dsts_loader(
            dsts_loader_root,
            self.current_digimon,
            overwrite=overwrite_reply == QMessageBox.StandardButton.Yes,
        )
        message = self.format_related_import_summary(summary)
        self.related_import_status_label.setText(message)

        if summary.get("ok"):
            QMessageBox.information(self, "Related Files Imported", message)
        else:
            QMessageBox.warning(self, "Import Failed", message)

    def refresh_digimon_list_view(self):
        """Apply current sort/filter settings to the Digimon combo box."""
        entries = list(getattr(self, 'digimon_entries', []))
        sort_mode = self.get_sort_mode()
        filter_text = self.search_box.text().strip().lower() if hasattr(self, 'search_box') else ""
        previous_text = self.digimon_list.currentText() if hasattr(self, 'digimon_list') else ""

        if sort_mode == "chr_id":
            entries.sort(key=lambda entry: (self.chr_sort_key(entry["chr_id"]), entry["name"].casefold()))
        else:
            entries.sort(key=lambda entry: (entry["name"].casefold(), self.chr_sort_key(entry["chr_id"])))

        if filter_text:
            entries = [
                entry for entry in entries
                if filter_text in entry["name"].lower()
                or filter_text in entry["chr_id"].lower()
                or filter_text in self.make_digimon_display_name(entry).lower()
            ]

        self.digimon_data = {}
        display_names = []

        for entry in entries:
            display_name = self.make_digimon_display_name(entry)
            if display_name in self.digimon_data:
                display_name = f"{display_name} #{len(display_names) + 1}"
            display_names.append(display_name)
            self.digimon_data[display_name] = entry

        self.digimon_list.blockSignals(True)
        self.digimon_list.clear()
        self.digimon_list.addItems(display_names)
        if previous_text in display_names:
            self.digimon_list.setCurrentText(previous_text)
        self.digimon_list.blockSignals(False)
        self.on_digimon_selected(self.digimon_list.currentText())

        self.all_digimon_names = display_names.copy()

    def load_digimon_list(self):
        """Load list of available Digimon by selected source."""
        self._invalidate_evolution_picker_cache()
        source_mode = self.get_source_mode()
        source_requests = []
        if source_mode in ("base", "all"):
            source_requests.append(("base", False))
        if source_mode in ("dlc", "all"):
            source_requests.append(("dlc", True))

        self.digimon_entries = []
        seen_entries = set()
        include_mod_entries = source_mode in ("all", "mods")
        if include_mod_entries:
            self._load_mod_folder_digimon_cache()

        for source_name, from_dlc in source_requests:
            chr_ids = self.loader.get_all_digimon_chr_ids(from_dlc=from_dlc)
            for chr_id in chr_ids:
                entry_key = (source_name, chr_id)
                if entry_key in seen_entries:
                    continue
                seen_entries.add(entry_key)

                # Get the name for this chr_id (returns None if not found in char_name.mbe)
                name = self.loader._get_digimon_name_by_chr_id(chr_id)
                if not name:
                    continue

                self.digimon_entries.append({
                    "name": name,
                    "chr_id": chr_id,
                    "source": source_name,
                    "imported": False,
                })

        # Add Digimon from manually imported or auto-discovered Reloaded II mods.
        if include_mod_entries and hasattr(self.loader, 'imported_digimon'):
            for digimon in self.loader.imported_digimon:
                source_label = getattr(digimon, "imported_source_label", "") or self._mod_source_label(
                    Path(getattr(digimon, "imported_dsts_loader_root", ""))
                )
                source_name = "mod" if source_label.startswith(("Mod:", "Active Mod")) else "imported"
                self.digimon_entries.append({
                    "name": digimon.name,
                    "chr_id": digimon.chr_id,
                    "source": source_name,
                    "source_label": source_label,
                    "imported": True,
                })

        self.refresh_digimon_list_view()
        if hasattr(self, "related_source_combo"):
            self.populate_related_source_combo()

        if not self.digimon_entries:
            self.digimon_list.clear()
            if source_mode == "dlc":
                message = "(No DLC Digimon found)"
            elif source_mode == "mods":
                message = "(No mod Digimon found)"
            else:
                message = "(No Digimon found)"
            self.digimon_list.addItem(message)
            self.all_digimon_names = []

    def on_source_changed(self):
        """Handle source combo change - disable remove button if switching away from DLC"""
        if not self.current_digimon:
            self.remove_button.setEnabled(False)
        else:
            self.remove_button.setEnabled(self.is_loaded_digimon_from_dlc())

    def filter_digimon_list(self, text: str):
        """Filter Digimon list based on search text"""
        self.refresh_digimon_list_view()

    def on_digimon_selected(self, display_name: str):
        """Handle Digimon selection from list"""
        has_selection = bool(display_name)
        self.load_button.setEnabled(has_selection)
        entry = getattr(self, "digimon_data", {}).get(display_name) if has_selection else None
        is_imported_entry = isinstance(entry, dict) and bool(entry.get("imported"))
        if hasattr(self, "add_selected_to_mod_button"):
            self.add_selected_to_mod_button.setEnabled(has_selection and self._active_dsts_loader_root() is not None)
        if hasattr(self, "remove_selected_from_mod_button"):
            self.remove_selected_from_mod_button.setEnabled(is_imported_entry and self._active_dsts_loader_root() is not None)

    def load_selected_digimon(self):
        """Load the selected Digimon"""
        # Check for unsaved changes
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"You have unsaved changes to {self.current_digimon.name if self.current_digimon else 'the current Digimon'}.\n\n"
                "Do you want to save before switching?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )

            if reply == QMessageBox.StandardButton.Cancel:
                return  # Don't switch
            elif reply == QMessageBox.StandardButton.Save:
                self.save_current_digimon()
                if self.has_unsaved_changes:  # Save failed or was cancelled
                    return

        display_name = self.digimon_list.currentText()
        if display_name and display_name in self.digimon_data:
            entry = self.digimon_data[display_name]
            if isinstance(entry, dict):
                chr_id = entry["chr_id"]
                entry_source = entry.get("source", "base")
                is_imported_entry = entry.get("imported", False)
            else:
                chr_id = entry
                entry_source = "dlc" if self.get_source_mode() == "dlc" else "base"
                is_imported_entry = display_name.startswith("📥")

            self.current_digimon_from_dlc = entry_source == "dlc"

            # Check if this is an imported Digimon
            if is_imported_entry:
                if hasattr(self.loader, 'imported_digimon'):
                    for digimon in self.loader.imported_digimon:
                        if digimon.chr_id == chr_id:
                            self.current_digimon_from_dlc = False
                            self.load_digimon_data(digimon)
                            return

            # Otherwise load from normal sources
            digimon = self.loader.get_digimon_by_chr_id(chr_id)
            if digimon:
                self.load_digimon_data(digimon)
            else:
                QMessageBox.warning(self, "Error", f"Could not load Digimon {display_name}")

    def _selected_digimon_entry(self) -> Optional[dict]:
        """Return the currently selected list entry metadata."""
        display_name = self.digimon_list.currentText() if hasattr(self, "digimon_list") else ""
        entry = getattr(self, "digimon_data", {}).get(display_name)
        return entry if isinstance(entry, dict) else None

    def _digimon_from_entry(self, entry: dict) -> Optional[DigimonData]:
        """Load a Digimon object from a base/DLC/imported list entry."""
        chr_id = entry.get("chr_id", "")
        if entry.get("imported") and hasattr(self.loader, "imported_digimon"):
            for digimon in self.loader.imported_digimon:
                if digimon.chr_id == chr_id:
                    return digimon
        return self.loader.get_digimon_by_chr_id(chr_id)

    def _active_mod_name_map(self, dsts_loader_root: Path) -> Dict[str, str]:
        """Read char_key -> display name from the active mod's English text patch."""
        names: Dict[str, str] = {}
        name_dir = dsts_loader_root / "patch_text01" / "text" / "char_name.mbe"
        if not name_dir.exists():
            return names

        for csv_file in sorted(name_dir.glob("*.ap.csv")):
            try:
                rows = self.loader.load_csv(csv_file)
            except Exception:
                continue

            for row in rows[1:]:
                if len(row) < 2:
                    continue
                char_key = _clean_status_cell(row[0])
                name = _clean_status_cell(row[1])
                if char_key and name:
                    names[char_key] = name

        return names

    def _invalidate_evolution_picker_cache(self):
        """Discard cached data used by the evolution add dialogs."""
        self._evolution_picker_entries_cache = None
        self._evolution_char_name_map_cache = None
        self._evolution_target_map_cache = None

    def _load_evolution_char_name_map(self) -> Dict[str, str]:
        """Load base and DLC char_key -> name rows once for evolution pickers."""
        if self._evolution_char_name_map_cache is not None:
            return dict(self._evolution_char_name_map_cache)

        names: Dict[str, str] = {}

        def add_name_file(name_file: Path):
            try:
                rows = self.loader.load_csv(name_file)
            except Exception:
                return

            for row in rows[1:]:
                char_key = self._csv_cell(row, 0)
                name = self._csv_cell(row, 1)
                if char_key and name:
                    names[char_key] = name

        base_name_file = self.loader._resolve_prefixed_file(
            self.loader.text_path / "char_name.mbe" / "000_Sheet1.csv"
        )
        if base_name_file.exists():
            add_name_file(base_name_file)

        try:
            for _dlc_id, dlc_name_file in self.loader.iter_dlc_csv_files("text", "char_name", "000_Sheet1.csv"):
                add_name_file(dlc_name_file)
        except Exception:
            pass

        self._evolution_char_name_map_cache = dict(names)
        return dict(names)

    def _add_status_rows_to_evolution_picker(
        self,
        status_file: Path,
        source: str,
        names_by_char_key: Dict[str, str],
        add_entry,
    ):
        """Add lightweight picker entries from a digimon_status CSV."""
        try:
            rows = self.loader.load_csv(status_file)
        except Exception:
            return

        for row in rows[1:]:
            if len(row) <= FIELD_GUIDE_CHR_ID_COLUMN or not any(str(cell).strip() for cell in row):
                continue

            digimon_id = self._csv_cell(row, FIELD_GUIDE_DIGIMON_ID_COLUMN)
            char_key = self._csv_cell(row, 2)
            chr_id = self._csv_cell(row, FIELD_GUIDE_CHR_ID_COLUMN)
            name = names_by_char_key.get(char_key, "") or char_key or chr_id
            add_entry(digimon_id, chr_id, name, source)

    def _evolution_picker_entries(self) -> List[dict]:
        """Build Digimon choices for evolution dialogs from base, DLC, imports, and the active mod."""
        if self._evolution_picker_entries_cache is not None:
            return list(self._evolution_picker_entries_cache)

        entries: List[dict] = []
        seen_entries: Set[Tuple[int, str]] = set()

        def add_entry(digimon_id, chr_id: str, name: str, source: str):
            try:
                parsed_id = int(digimon_id)
            except (TypeError, ValueError):
                return

            clean_chr_id = _clean_status_cell(chr_id)
            if parsed_id <= 0 or not clean_chr_id:
                return

            clean_name = (name or "").strip()
            if not clean_name or clean_name == "Unknown":
                clean_name = self.loader._get_digimon_name_by_chr_id(clean_chr_id) or clean_chr_id

            key = (parsed_id, clean_chr_id.casefold())
            if key in seen_entries:
                return
            seen_entries.add(key)

            entries.append({
                "id": parsed_id,
                "chr_id": clean_chr_id,
                "name": clean_name,
                "source": source,
                "label": f"{clean_name} ({clean_chr_id}) - ID: {parsed_id} [{source}]",
            })

        names_by_char_key = self._load_evolution_char_name_map()

        base_status_file = self.loader._resolve_prefixed_file(
            self.loader.data_path / "digimon_status.mbe" / "000_digimon_status_data.csv"
        )
        if base_status_file.exists():
            self._add_status_rows_to_evolution_picker(base_status_file, "Base", names_by_char_key, add_entry)

        try:
            for _dlc_id, dlc_status_file in self.loader.iter_dlc_csv_files(
                "data", "digimon_status", "000_digimon_status_data.csv"
            ):
                self._add_status_rows_to_evolution_picker(dlc_status_file, "DLC", names_by_char_key, add_entry)
        except Exception:
            pass

        for digimon in getattr(self.loader, "imported_digimon", []):
            add_entry(
                getattr(digimon, "id", 0),
                getattr(digimon, "chr_id", ""),
                getattr(digimon, "name", ""),
                "Imported",
            )

        for mod_root, source_label in self._iter_reloaded_mod_dsts_loader_roots():
            names_by_char_key = self._active_mod_name_map(mod_root)
            for status_file in self._dsts_loader_status_files(mod_root):
                try:
                    rows = self.loader.load_csv(status_file)
                except Exception:
                    continue

                for row in rows[1:]:
                    if not row or not any(str(cell).strip() for cell in row):
                        continue
                    digimon_id = self._csv_cell(row, FIELD_GUIDE_DIGIMON_ID_COLUMN)
                    char_key = self._csv_cell(row, 2)
                    chr_id = self._csv_cell(row, FIELD_GUIDE_CHR_ID_COLUMN)
                    name = names_by_char_key.get(char_key, "") or char_key or chr_id
                    add_entry(digimon_id, chr_id, name, source_label)

        entries.sort(key=lambda entry: (entry["name"].casefold(), self.chr_sort_key(entry["chr_id"]), entry["id"]))
        self._evolution_picker_entries_cache = list(entries)
        return entries

    def _find_evolution_picker_entry(self, text: str, entries: List[dict]) -> Optional[dict]:
        """Resolve custom evolution text against the same entries shown in the dialog list."""
        query = (text or "").strip()
        if not query:
            return None

        folded_query = query.casefold()
        for entry in entries:
            if folded_query == entry["chr_id"].casefold() or query == str(entry["id"]):
                return entry

        for entry in entries:
            if folded_query in entry["name"].casefold() or folded_query in entry["label"].casefold():
                return entry

        return None

    def _collect_used_digimon_ids(self) -> Set[int]:
        """Collect Digimon IDs from base, DLC, imported rows, and the active mod payload."""
        used_ids = set(self.loader.get_all_digimon_ids())
        try:
            for _dlc_id, dlc_status_file in self.loader.iter_dlc_csv_files(
                "data", "digimon_status", "000_digimon_status_data.csv"
            ):
                rows = self.loader.load_csv(dlc_status_file)
                for row in rows[1:]:
                    if row and row[0]:
                        try:
                            used_ids.add(int(_clean_status_cell(row[0])))
                        except (TypeError, ValueError):
                            continue
        except Exception:
            pass

        for digimon in getattr(self.loader, "imported_digimon", []):
            try:
                used_ids.add(int(getattr(digimon, "id", 0)))
            except (TypeError, ValueError):
                continue

        active_root = self._active_dsts_loader_root()
        if active_root:
            try:
                for status_file in self._dsts_loader_status_files(active_root):
                    rows = self.loader.load_csv(status_file)
                    for row in rows[1:]:
                        if row and row[0]:
                            try:
                                used_ids.add(int(_clean_status_cell(row[0])))
                            except (TypeError, ValueError):
                                continue
            except Exception:
                pass

        return {digimon_id for digimon_id in used_ids if digimon_id > 0}

    def _collect_used_chr_ids(self) -> Set[str]:
        """Collect Chr IDs from base, DLC, imported rows, and the active mod payload."""
        used_chr_ids = set()
        for from_dlc in (False, True):
            try:
                used_chr_ids.update(
                    chr_id.strip().casefold()
                    for chr_id in self.loader.get_all_digimon_chr_ids(from_dlc=from_dlc)
                    if chr_id
                )
            except Exception:
                continue

        for digimon in getattr(self.loader, "imported_digimon", []):
            chr_id = str(getattr(digimon, "chr_id", "")).strip()
            if chr_id:
                used_chr_ids.add(chr_id.casefold())

        active_root = self._active_dsts_loader_root()
        if active_root:
            try:
                for status_file in self._dsts_loader_status_files(active_root):
                    rows = self.loader.load_csv(status_file)
                    for row in rows[1:]:
                        if len(row) > FIELD_GUIDE_CHR_ID_COLUMN:
                            chr_id = _clean_status_cell(row[FIELD_GUIDE_CHR_ID_COLUMN])
                            if chr_id:
                                used_chr_ids.add(chr_id.casefold())
            except Exception:
                pass

        return used_chr_ids

    def _collect_used_char_keys(self) -> Set[str]:
        """Collect Character Keys from base, DLC, imported rows, and the active mod payload."""
        used_char_keys = set()

        for from_dlc in (False, True):
            try:
                for chr_id in self.loader.get_all_digimon_chr_ids(from_dlc=from_dlc):
                    digimon = self.loader.get_digimon_by_chr_id(chr_id)
                    char_key = str(getattr(digimon, "char_key", "")).strip() if digimon else ""
                    if char_key:
                        used_char_keys.add(char_key.casefold())
            except Exception:
                continue

        for digimon in getattr(self.loader, "imported_digimon", []):
            char_key = str(getattr(digimon, "char_key", "")).strip()
            if char_key:
                used_char_keys.add(char_key.casefold())

        active_root = self._active_dsts_loader_root()
        if active_root:
            try:
                for status_file in self._dsts_loader_status_files(active_root):
                    rows = self.loader.load_csv(status_file)
                    for row in rows[1:]:
                        if len(row) > 2:
                            char_key = _clean_status_cell(row[2])
                            if char_key:
                                used_char_keys.add(char_key.casefold())
            except Exception:
                pass

        return used_char_keys

    def add_selected_to_active_mod(self):
        """Load the selected Digimon as an unsaved new entry for the active mod."""
        active_root = self._active_dsts_loader_root()
        if not active_root:
            QMessageBox.warning(
                self,
                "No Active Mod",
                "Import or export a Reloaded II mod first.\n\n"
                "After a mod is loaded, this button can add the selected Digimon as a new entry in that same dsts-loader payload."
            )
            return

        entry = self._selected_digimon_entry()
        if not entry:
            QMessageBox.warning(self, "No Selection", "Select a Digimon from the list first.")
            return

        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"You have unsaved changes to {self.current_digimon.name if self.current_digimon else 'the current Digimon'}.\n\n"
                "Do you want to save before adding a new mod entry?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Save:
                self.save_current_digimon()
                if self.has_unsaved_changes:
                    return

        template = self._digimon_from_entry(entry)
        if not template:
            QMessageBox.warning(self, "Load Failed", "Could not load the selected Digimon as a template.")
            return

        from copy import deepcopy
        new_digimon = deepcopy(template)
        source_name = template.name or entry.get("name", "Digimon")
        source_chr_id = template.chr_id
        animation_ref = getattr(template, "animation_ref", "") or source_chr_id

        # Keep the template's visible identity intact. The editor marks this as a
        # pending mod entry so Save/Export will require the user-selected final
        # IDs instead of silently inventing chr/id/key values.
        new_digimon.pending_new_mod_entry = True
        new_digimon.template_id = getattr(template, "id", "")
        new_digimon.template_chr_id = source_chr_id
        new_digimon.template_char_key = getattr(template, "char_key", "")
        new_digimon.animation_ref = animation_ref
        self._mark_import_source(new_digimon, active_root)

        self.current_digimon_from_dlc = False
        self.load_digimon_data(new_digimon)
        self.current_digimon_label.setText(f"📝 New Entry Template: {source_name} ({source_chr_id}) *")
        self.mark_as_modified()

        QMessageBox.information(
            self,
            "Template Loaded",
            f"✅ Loaded {source_name} as a new pending mod entry.\n\n"
            f"Template: {source_name} ({source_chr_id})\n"
            f"Active mod:\n{active_root}\n\n"
            "Choose the new Digimon ID, Chr ID, Character Key, and Field Guide slot, then use Save to Loaded Source."
        )

    def _csv_cell(self, row: List[str], index: int) -> str:
        """Return a cleaned CSV cell, or an empty string when the column is missing."""
        return _clean_status_cell(row[index]) if len(row) > index else ""

    def _remove_rows_from_mod_csv(self, filepath: Path, should_remove, drop_blank: bool = True) -> int:
        """Remove matching rows from a dsts-loader CSV while preserving its header."""
        import csv

        resolved_filepath = self._resolve_prefixed_file(filepath)
        if not resolved_filepath.exists():
            return 0

        with open(resolved_filepath, 'r', encoding='utf-8', newline='') as f:
            header = f.readline().rstrip('\n\r')
            rows = list(csv.reader(f))

        kept_rows = []
        removed_count = 0
        for row in rows:
            if drop_blank and not any(cell.strip() for cell in row):
                removed_count += 1
                continue
            if should_remove(row):
                removed_count += 1
                continue
            kept_rows.append(row)

        if removed_count:
            with open(resolved_filepath, 'w', encoding='utf-8', newline='') as f:
                if header:
                    f.write(header + '\n')
                writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                writer.writerows(kept_rows)

        return removed_count

    def _remove_digimon_from_dsts_loader(self, dsts_loader_root: Path, digimon: DigimonData) -> Dict[str, int]:
        """Remove one imported Digimon's rows from a dsts-loader payload."""
        root = Path(dsts_loader_root)
        patch_data = root / "patch" / "data"
        app_data = root / "app_0" / "data"

        id_texts = {str(getattr(digimon, "id", ""))}
        id_texts.discard("")
        chr_ids = {str(getattr(digimon, "chr_id", "")).strip()}
        chr_ids.discard("")
        char_keys = {str(getattr(digimon, "char_key", "")).strip()}
        char_keys.discard("")
        profile_keys = digimon_profile_key_variants(getattr(digimon, "id", ""))

        def matches_status(row):
            return (
                self._csv_cell(row, 0) in id_texts
                or self._csv_cell(row, 2) in char_keys
                or self._csv_cell(row, 3) in chr_ids
            )

        def matches_char_info(row):
            return (
                self._csv_cell(row, 0) in char_keys
                or self._csv_cell(row, 3) in chr_ids
                or self._csv_cell(row, 4) in id_texts
            )

        def matches_chr(row):
            return self._csv_cell(row, 0) in chr_ids

        def matches_lod_model(row):
            first = self._csv_cell(row, 0)
            lod_name = self._csv_cell(row, 2)
            return first in chr_ids or any(lod_name == f"{chr_id}_LOD_2" for chr_id in chr_ids)

        def matches_evolution_to(row):
            return self._csv_cell(row, 1) in id_texts or self._csv_cell(row, 3) in id_texts

        def matches_id(row):
            return self._csv_cell(row, 0) in id_texts

        def matches_char_key(row):
            return self._csv_cell(row, 0) in char_keys

        def matches_profile(row):
            return self._csv_cell(row, 0) in profile_keys

        removals = {
            "digimon_status": self._remove_rows_from_mod_csv(
                patch_data / "digimon_status.mbe" / "000_digimon_status_data.ap.csv",
                matches_status,
            ),
            "char_info": self._remove_rows_from_mod_csv(
                patch_data / "char_info.mbe" / "000_char_info.ap.csv",
                matches_char_info,
            ),
            "model_setting": self._remove_rows_from_mod_csv(
                patch_data / "model_setting.mbe" / "000_model_setting.ap.csv",
                matches_chr,
            ),
            "lod": self._remove_rows_from_mod_csv(
                patch_data / "lod_chara.mbe" / "000_lod.ap.csv",
                matches_chr,
            ),
            "lod_model": self._remove_rows_from_mod_csv(
                patch_data / "lod_chara.mbe" / "001_lod_model.ap.csv",
                matches_lod_model,
            ),
            "same_animation": self._remove_rows_from_mod_csv(
                patch_data / "anim_setting.mbe" / "001_same_animation_data.ap.csv",
                matches_chr,
            ),
            "evolution_to": self._remove_rows_from_mod_csv(
                patch_data / "evolution.mbe" / "001_evolution_to.ap.csv",
                matches_evolution_to,
            ),
            "evolution_condition": self._remove_rows_from_mod_csv(
                patch_data / "evolution.mbe" / "000_evolution_condition.ap.csv",
                matches_id,
            ),
            "model_outline": self._remove_rows_from_mod_csv(
                app_data / "model_outline.mbe" / "000_model_outline_battle.ap.csv",
                matches_chr,
            ),
        }

        for patch_text_dir in self._iter_patch_text_dirs(root):
            folder = self._normalize_text_folder_name(patch_text_dir.name)
            patch_text = patch_text_dir / "text"
            removals[f"{folder}/char_name"] = self._remove_rows_from_mod_csv(
                patch_text / "char_name.mbe" / "000_Sheet1.ap.csv",
                matches_char_key,
            )
            removals[f"{folder}/digimon_profile"] = self._remove_rows_from_mod_csv(
                patch_text / "digimon_profile.mbe" / "000_Sheet1.ap.csv",
                matches_profile,
            )
            removals[f"{folder}/belong"] = self._remove_rows_from_mod_csv(
                patch_text / "belong.mbe" / "000_Sheet1.ap.csv",
                matches_id,
            )

        return removals

    def remove_selected_from_active_mod(self):
        """Remove the selected imported Digimon from its dsts-loader mod files."""
        entry = self._selected_digimon_entry()
        if not entry or not entry.get("imported"):
            QMessageBox.warning(self, "No Imported Selection", "Select an imported Digimon entry from the list first.")
            return

        digimon = self._digimon_from_entry(entry)
        if not digimon:
            QMessageBox.warning(self, "Remove Failed", "Could not resolve the selected imported Digimon.")
            return

        original_identity = dict(getattr(self, "loaded_digimon_identity", {}) or {})
        root = self._imported_dsts_loader_root(digimon, str(original_identity.get("chr_id", ""))) or self._active_dsts_loader_root()
        if not root:
            QMessageBox.warning(self, "No Active Mod", "Could not resolve the selected Digimon's dsts-loader folder.")
            return

        reply = QMessageBox.question(
            self,
            "Remove Digimon from Mod",
            f"Remove {digimon.name or digimon.chr_id} from this mod?\n\n"
            f"ID: {digimon.id}\n"
            f"Chr ID: {digimon.chr_id}\n"
            f"Folder:\n{root}\n\n"
            "This removes matching rows from the mod CSV files. Asset files are left in place.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            removals = self._remove_digimon_from_dsts_loader(root, digimon)
        except PermissionError as exc:
            QMessageBox.warning(
                self,
                "Remove Failed",
                f"Could not write one of the mod CSV files:\n\n{exc}\n\n"
                "Close any open CSV editor tabs for this mod and try again."
            )
            return

        if hasattr(self.loader, "imported_digimon"):
            self.loader.imported_digimon = [
                imported for imported in self.loader.imported_digimon
                if not (
                    imported is digimon
                    or imported.id == digimon.id
                    or imported.chr_id == digimon.chr_id
                )
            ]

        if self.current_digimon and (
            self.current_digimon is digimon
            or self.current_digimon.id == digimon.id
            or self.current_digimon.chr_id == digimon.chr_id
        ):
            self.current_digimon = None
            self.current_digimon_label.setText("📂 No Digimon loaded")
            self.save_button.setEnabled(False)
            self.export_dlc_button.setEnabled(False)
            self.clear_modified_flag()

        self.load_digimon_list()
        total_removed = sum(removals.values())
        details = "\n".join(f"  • {name}: {count}" for name, count in removals.items() if count)
        QMessageBox.information(
            self,
            "Removed from Mod",
            f"✅ Removed {digimon.name or digimon.chr_id} from the active mod.\n\n"
            f"Rows removed: {total_removed}\n"
            + (f"\n{details}" if details else "\nNo matching rows were found; blank rows may already have been cleaned.")
        )

    def load_digimon_data(self, digimon: DigimonData):
        """Load Digimon data into the editor"""
        self.current_digimon = digimon
        self._loading_digimon_form = True
        self._remember_loaded_identity(digimon)
        self.current_digimon_label.setText(f"✏️ Editing: {digimon.name} ({digimon.chr_id})")

        # Clear unsaved changes flag when loading new Digimon
        self.clear_modified_flag()

        # Enable/disable remove button based on source
        self.remove_button.setEnabled(self.is_loaded_digimon_from_dlc())

        # Basic Info
        self.id_spin.setValue(digimon.id)
        self.char_key_edit.setText(digimon.char_key)
        self.chr_id_edit.setText(digimon.chr_id)
        self.name_edit.setText(digimon.name)

        # Sync animation reference - use template chr_id if available, otherwise use digimon's chr_id
        if hasattr(self, 'template_chr_id_for_animation'):
            self.animation_ref_edit.setText(self.template_chr_id_for_animation)
            self.select_related_source_by_chr(self.template_chr_id_for_animation)
            delattr(self, 'template_chr_id_for_animation')  # Clear after use
        elif getattr(digimon, "animation_ref", ""):
            self.animation_ref_edit.setText(digimon.animation_ref)
            self.select_related_source_by_chr(digimon.animation_ref)
        else:
            self.animation_ref_edit.setText(digimon.chr_id)
            self.select_related_source_by_chr(digimon.chr_id)

        # Set stage combo box
        # Ensure stage_id is in valid range (0-14, based on generation_name.mbe CSV)
        stage_id = max(0, min(14, digimon.stage_id)) if digimon.stage_id is not None else 0
        stage_index = self.stage_combo.findData(stage_id)
        if stage_index >= 0:
            self.stage_combo.setCurrentIndex(stage_index)
        else:
            # If stage_id is 0 or not found, set to index 0 (which should be the first stage)
            # Try to find index 0 explicitly
            stage_index_0 = self.stage_combo.findData(0)
            if stage_index_0 >= 0:
                self.stage_combo.setCurrentIndex(stage_index_0)
            else:
                self.stage_combo.setCurrentIndex(0)

        # Set type combo box
        type_index = self.type_combo.findData(digimon.type_id)
        if type_index >= 0:
            self.type_combo.setCurrentIndex(type_index)

        # Set personality combo box
        personality_index = self.personality_combo.findData(digimon.personality_id)
        if personality_index >= 0:
            self.personality_combo.setCurrentIndex(personality_index)
        else:
            # If personality_id is 0 or not found, set to index 0 (which should be "-")
            self.personality_combo.setCurrentIndex(0)

        # Set tribe combo box
        if hasattr(digimon, 'tribe_name') and digimon.tribe_name:
            tribe_index = self.tribe_combo.findText(digimon.tribe_name)
            if tribe_index < 0:
                self.tribe_combo.addItem(digimon.tribe_name)
                tribe_index = self.tribe_combo.findText(digimon.tribe_name)
            if tribe_index >= 0:
                self.tribe_combo.setCurrentIndex(tribe_index)
        else:
            # Default to first item (usually "None" or alphabetically first)
            self.tribe_combo.setCurrentIndex(0)

        # Profile text
        self.profile_text_edit.setPlainText(digimon.profile_text)
        self.load_multilanguage_text_tab(digimon)

        # Stats
        self.stat_widgets["hp"].setValue(digimon.base_hp)
        self.stat_widgets["sp"].setValue(digimon.base_sp)
        self.stat_widgets["atk"].setValue(digimon.base_atk)
        self.stat_widgets["def"].setValue(digimon.base_def)
        self.stat_widgets["int"].setValue(digimon.base_int)
        self.stat_widgets["spi"].setValue(digimon.base_spi)
        self.stat_widgets["spd"].setValue(digimon.base_spd)

        # Growth Pattern
        growth_index = self.growth_pattern_combo.findData(digimon.growth_pattern_id)
        if growth_index >= 0:
            self.growth_pattern_combo.setCurrentIndex(growth_index)
        else:
            self.growth_pattern_combo.setCurrentIndex(0)  # Default to pattern 1

        # Resistances
        self.resist_widgets["null"].setValue(digimon.res_null)
        self.resist_widgets["fire"].setValue(digimon.res_fire)
        self.resist_widgets["water"].setValue(digimon.res_water)
        self.resist_widgets["ice"].setValue(digimon.res_ice)
        self.resist_widgets["grass"].setValue(digimon.res_grass)
        self.resist_widgets["wind"].setValue(digimon.res_wind)
        self.resist_widgets["elec"].setValue(digimon.res_elec)
        self.resist_widgets["ground"].setValue(digimon.res_ground)
        self.resist_widgets["steel"].setValue(digimon.res_steel)
        self.resist_widgets["light"].setValue(digimon.res_light)
        self.resist_widgets["dark"].setValue(digimon.res_dark)

        # Skills
        self.signature_skills_editor.load_skills(digimon.signature_skills)
        self.generic_skills_editor.load_skills(digimon.generic_skills)

        # Update skill names for all skills
        self.signature_skills_editor.update_all_skill_names()
        self.generic_skills_editor.update_all_skill_names()

        # Traits
        self.traits_tab.load_traits(digimon.traits)

        # Model data
        self.model_id_edit.setText(digimon.model_id)
        self.motion_id_edit.setText(digimon.motion_id)

        # LOD data
        for key, widget in self.lod_widgets.items():
            widget.setValue(int(digimon.lod_data.get(key, 0)))

        # Model settings (from model_setting.mbe)
        if digimon.model_setting_data:
            self.battle_scale_spin.setValue(digimon.model_setting_data.get('battle_scale', 1.0))
            self.menu_scale_spin.setValue(digimon.model_setting_data.get('menu_scale', 1.0))
            self.field_scale_spin.setValue(digimon.model_setting_data.get('field_scale', 1.0))
            self.npc_collision_spin.setValue(digimon.model_setting_data.get('npc_collision', 0.0))
            self.shield_size_spin.setValue(digimon.model_setting_data.get('shield_size', 0.0))
            self.agent_distance_spin.setValue(digimon.model_setting_data.get('agent_distance', 0))
            self.agent_distance_2_spin.setValue(digimon.model_setting_data.get('agent_distance_2', 0.0))
            self.digimon_distance_spin.setValue(digimon.model_setting_data.get('digimon_distance_from_agent', 0.0))
            self.camera_distance_skill_spin.setValue(digimon.model_setting_data.get('camera_distance_skill', 0.0))
            self.rideable_checkbox.setChecked(digimon.model_setting_data.get('rideable', 0) != 0)
        else:
            # Reset to defaults if no model_setting data
            self.battle_scale_spin.setValue(1.0)
            self.menu_scale_spin.setValue(1.0)
            self.field_scale_spin.setValue(1.0)
            self.npc_collision_spin.setValue(0.0)
            self.shield_size_spin.setValue(0.0)
            self.agent_distance_spin.setValue(0)
            self.agent_distance_2_spin.setValue(0.0)
            self.digimon_distance_spin.setValue(0.0)
            self.camera_distance_skill_spin.setValue(0.0)
            self.rideable_checkbox.setChecked(False)

        # References
        self.field_guide_id_spin.setValue(digimon.field_guide_id)
        self.script_id_spin.setValue(digimon.script_id)
        self._status_ref_user_edited = digimon.script_id not in (-1, 0, digimon.id)
        self._loading_digimon_form = False

        # Update extended tabs
        self.update_evolution_tab(digimon)
        self.update_battle_tab(digimon)
        self.update_profile_text_stats()

        self.save_button.setEnabled(True)
        self.export_dlc_button.setEnabled(True)
        self.clear_modified_flag()

    def _remember_loaded_identity(self, digimon: DigimonData):
        """Snapshot the row identity originally loaded into the form."""
        self.loaded_digimon_identity = {
            "id": getattr(digimon, "id", 0),
            "chr_id": getattr(digimon, "chr_id", ""),
            "char_key": getattr(digimon, "char_key", ""),
            "field_guide_id": getattr(digimon, "field_guide_id", -1),
            "imported_dsts_loader_root": getattr(digimon, "imported_dsts_loader_root", ""),
            "imported_mod_root": getattr(digimon, "imported_mod_root", ""),
            "pending_new_mod_entry": bool(getattr(digimon, "pending_new_mod_entry", False)),
            "template_id": getattr(digimon, "template_id", ""),
            "template_chr_id": getattr(digimon, "template_chr_id", ""),
            "template_char_key": getattr(digimon, "template_char_key", ""),
        }

    def _current_identity_values(self) -> dict:
        """Return current and originally loaded IDs used for validation/merge matching."""
        identity = getattr(self, "loaded_digimon_identity", {}) or {}
        pending_new = bool(
            identity.get("pending_new_mod_entry")
            or (self.current_digimon and getattr(self.current_digimon, "pending_new_mod_entry", False))
        )

        if pending_new:
            chr_ids = set()
            raw_digimon_ids = set()
            char_keys = set()
        else:
            chr_ids = {self.chr_id_edit.text().strip()}
            raw_digimon_ids = {self.id_spin.value()}
            char_keys = {self.char_key_edit.text().strip()}

        if self.current_digimon and not pending_new:
            chr_ids.add(getattr(self.current_digimon, "chr_id", ""))
            raw_digimon_ids.add(getattr(self.current_digimon, "id", 0))
            char_keys.add(getattr(self.current_digimon, "char_key", ""))

        if not pending_new:
            chr_ids.add(identity.get("chr_id", ""))
            raw_digimon_ids.add(identity.get("id", 0))
            char_keys.add(identity.get("char_key", ""))

        digimon_ids = set()
        for value in raw_digimon_ids:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                digimon_ids.add(parsed)

        return {
            "chr_ids": {value for value in chr_ids if value},
            "digimon_ids": digimon_ids,
            "char_keys": {value for value in char_keys if value},
            "identity": identity,
            "pending_new_mod_entry": pending_new,
        }

    def launch_creation_wizard(self):
        """Launch the Digimon creation wizard"""
        wizard = DigimonCreationWizard(self, self.loader)
        wizard.exec()

        # Inform user if a new Digimon was created
        if wizard.new_digimon:
            # Ask if they want to import it for editing
            reply = QMessageBox.question(
                self,
                "Digimon Created",
                f"✅ {wizard.new_digimon.name} has been exported to dsts-loader format!\n\n"
                f"Would you like to import it for editing?\n"
                f"(This will import the Digimon from the folder you just exported to)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                # Import from the dsts-loader folder that was just exported to
                if hasattr(wizard, 'last_export_path') and wizard.last_export_path:
                    try:
                        from pathlib import Path
                        loader_path = self._resolve_dsts_loader_root(wizard.last_export_path)
                        if not loader_path:
                            QMessageBox.warning(
                                self,
                                "Import Failed",
                                "Could not resolve the exported dsts-loader folder.\n"
                                "Try using 'Import from dsts-loader' manually."
                            )
                            return

                        # Look for the exported digimon_status_data.ap.csv
                        status_files = self._dsts_loader_status_files(loader_path)

                        if not status_files:
                            QMessageBox.warning(
                                self,
                                "Import Failed",
                                "Could not find exported files.\n"
                                "Try using 'Import from dsts-loader' manually."
                            )
                            return

                        if not hasattr(self.loader, 'imported_digimon'):
                            self.loader.imported_digimon = []

                        imported_any = False
                        last_imported = None

                        for status_file in status_files:
                            digimon_list = self._parse_digimon_status_csv(status_file, loader_path)
                            for digimon in digimon_list:
                                self._upsert_imported_digimon(digimon, loader_path)
                                imported_any = True
                                last_imported = digimon

                        if imported_any and last_imported:
                            # Refresh list to show imported Digimon
                            self.load_digimon_list()

                            # Find and select the newly imported Digimon
                            first_digimon = last_imported
                            self.load_digimon_data(first_digimon)
                            self.current_digimon = first_digimon

                            # Try to select it in the list
                            display_name = f"📥 {first_digimon.name} ({first_digimon.chr_id})"
                            index = self.digimon_list.findText(display_name, Qt.MatchFlag.MatchExactly)
                            if index >= 0:
                                self.digimon_list.setCurrentIndex(index)

                            QMessageBox.information(
                                self,
                                "Import Successful",
                                f"✅ {first_digimon.name} has been loaded for editing!"
                            )
                        else:
                            QMessageBox.warning(
                                self,
                                "Import Failed",
                                "Could not import the newly created Digimon.\n"
                                "Try using 'Import from dsts-loader' manually."
                            )
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        QMessageBox.warning(
                            self,
                            "Import Failed",
                            f"Could not import the newly created Digimon:\n\n{str(e)}\n\n"
                            f"Try using 'Import from dsts-loader' manually."
                        )

    def _dsts_loader_status_files(self, dsts_loader_root: Path) -> List[Path]:
        """Return status .ap.csv files for a normalized dsts-loader payload root."""
        status_dir = dsts_loader_root / "patch" / "data" / "digimon_status.mbe"
        return sorted(status_dir.glob("*.ap.csv")) if status_dir.exists() else []

    def _dsts_loader_evolution_files(self, dsts_loader_root: Path) -> List[Path]:
        """Return evolution_to .ap.csv files for a normalized dsts-loader payload root."""
        evolution_dir = dsts_loader_root / "patch" / "data" / "evolution.mbe"
        return sorted(evolution_dir.glob("*_evolution_to.ap.csv")) if evolution_dir.exists() else []

    def _iter_reloaded_mod_dsts_loader_roots(self) -> List[Tuple[Path, str]]:
        """List dsts-loader payloads from the Reloaded II mods folder plus the active payload."""
        roots: List[Tuple[Path, str]] = []
        seen = set()

        def add_root(root: Path, label: str):
            try:
                key = str(root.resolve()).casefold()
            except Exception:
                key = str(root).casefold()
            if key in seen:
                return
            if not root.exists():
                return
            seen.add(key)
            roots.append((root, label))

        mods_root = get_default_mod_loader_path()
        if mods_root.exists():
            for mod_dir in sorted((path for path in mods_root.iterdir() if path.is_dir()), key=lambda path: path.name.casefold()):
                for loader_name in sorted(DSTS_LOADER_DIR_NAMES):
                    candidate = mod_dir / loader_name
                    if candidate.exists():
                        add_root(candidate, f"Mod: {mod_dir.name}")

        active_root = self._active_dsts_loader_root()
        if active_root:
            active_label = "Active Mod"
            inferred = self._infer_reloaded_mod_root(active_root)
            if inferred:
                active_label = f"Active Mod: {inferred.name}"
            add_root(active_root, active_label)

        return roots

    def _resolve_dsts_loader_root(self, selected_path: Path, allow_create: bool = False) -> Optional[Path]:
        """
        Normalize a selected folder to the actual dsts-loader payload root.

        Users often select the Reloaded II mod folder, while the editable CSV
        payload lives one level deeper in ``dsts-loader``. This accepts both
        shapes and also walks upward if the chosen folder is inside the payload.
        """
        selected = Path(selected_path)
        candidates: List[Path] = []

        def add_candidate(path: Path):
            if path not in candidates:
                candidates.append(path)

        add_candidate(selected)
        for loader_name in DSTS_LOADER_DIR_NAMES:
            add_candidate(selected / loader_name)

        for parent in [selected, *selected.parents]:
            if parent.name.lower() in DSTS_LOADER_DIR_NAMES:
                add_candidate(parent)
            for loader_name in DSTS_LOADER_DIR_NAMES:
                add_candidate(parent / loader_name)

        for candidate in candidates:
            if self._dsts_loader_status_files(candidate):
                return candidate

        if not allow_create:
            return None

        if selected.name.lower() in DSTS_LOADER_DIR_NAMES:
            return selected

        for loader_name in DSTS_LOADER_DIR_NAMES:
            child = selected / loader_name
            if child.exists():
                return child

        if (selected / "ModConfig.json").exists():
            return selected / "dsts-loader"

        return selected

    def _infer_reloaded_mod_root(self, dsts_loader_root: Path) -> Optional[Path]:
        """Return the Reloaded II mod folder when the payload sits below one."""
        root = Path(dsts_loader_root)
        if root.name.lower() in DSTS_LOADER_DIR_NAMES and (root.parent / "ModConfig.json").exists():
            return root.parent
        return None

    def _set_active_dsts_loader_root(self, dsts_loader_root: Path):
        """Remember the mod payload that new/imported Digimon should merge into."""
        root = Path(dsts_loader_root)
        self.active_dsts_loader_root = root
        self.active_reloaded_mod_root = self._infer_reloaded_mod_root(root)
        self._invalidate_evolution_picker_cache()
        if hasattr(self, "skill_browser_combo"):
            self.populate_skill_browser()
        if hasattr(self, "digimon_list"):
            self.on_digimon_selected(self.digimon_list.currentText())

    def _active_dsts_loader_root(self) -> Optional[Path]:
        """Return the currently imported/exported dsts-loader payload, if any."""
        root = getattr(self, "active_dsts_loader_root", None)
        return Path(root) if root else None

    def _mark_import_source(self, digimon: DigimonData, dsts_loader_root: Path):
        """Remember where an imported Digimon should be saved back to."""
        root = Path(dsts_loader_root)
        digimon.imported_dsts_loader_root = str(root)
        mod_root = self._infer_reloaded_mod_root(root)
        digimon.imported_mod_root = str(mod_root) if mod_root else ""

    def _mod_source_label(self, dsts_loader_root: Path) -> str:
        """Return a compact label for a dsts-loader source."""
        mod_root = self._infer_reloaded_mod_root(dsts_loader_root)
        if mod_root:
            return f"Mod: {mod_root.name}"
        return "Imported"

    def _quiet_upsert_imported_digimon(self, digimon: DigimonData, dsts_loader_root: Path, source_label: str = "") -> bool:
        """Cache a mod-folder Digimon without changing the active save target."""
        root = Path(dsts_loader_root)
        self._mark_import_source(digimon, root)
        digimon.imported_source_label = source_label or self._mod_source_label(root)

        if not hasattr(self.loader, 'imported_digimon'):
            self.loader.imported_digimon = []

        try:
            root_key = str(root.resolve()).casefold()
        except Exception:
            root_key = str(root).casefold()

        for index, existing in enumerate(self.loader.imported_digimon):
            existing_root = getattr(existing, "imported_dsts_loader_root", "")
            try:
                existing_root_key = str(Path(existing_root).resolve()).casefold() if existing_root else ""
            except Exception:
                existing_root_key = str(existing_root).casefold()

            if existing_root_key == root_key and (
                existing.chr_id == digimon.chr_id
                or existing.id == digimon.id
            ):
                self.loader.imported_digimon[index] = digimon
                return False

        self.loader.imported_digimon.append(digimon)
        return True

    def _load_mod_folder_digimon_cache(self):
        """Load Digimon entries found in configured Reloaded II mod folders."""
        if not hasattr(self.loader, 'imported_digimon'):
            self.loader.imported_digimon = []

        for mod_root, source_label in self._iter_reloaded_mod_dsts_loader_roots():
            try:
                root_key = str(mod_root.resolve()).casefold()
            except Exception:
                root_key = str(mod_root).casefold()

            status_files = self._dsts_loader_status_files(mod_root)
            if not status_files:
                continue

            try:
                file_signature = tuple(
                    (str(path.resolve()).casefold(), path.stat().st_mtime_ns, path.stat().st_size)
                    for path in status_files
                )
            except Exception:
                file_signature = tuple(str(path).casefold() for path in status_files)

            cache_key = repr((root_key, file_signature))
            if cache_key in self._auto_loaded_mod_roots:
                continue

            for status_file in status_files:
                try:
                    digimon_list = self._parse_digimon_status_csv(status_file, mod_root)
                except Exception as exc:
                    debug_log(f"Could not auto-load mod Digimon from {status_file}: {exc}")
                    continue

                for digimon in digimon_list:
                    self._quiet_upsert_imported_digimon(digimon, mod_root, source_label)

            self._auto_loaded_mod_roots.add(cache_key)

    def _upsert_imported_digimon(self, digimon: DigimonData, dsts_loader_root: Path) -> bool:
        """Add or replace an imported Digimon by ID/chr_id while preserving source tracking."""
        self._set_active_dsts_loader_root(dsts_loader_root)
        self._mark_import_source(digimon, dsts_loader_root)
        digimon.imported_source_label = self._mod_source_label(dsts_loader_root)
        if not hasattr(self.loader, 'imported_digimon'):
            self.loader.imported_digimon = []

        for index, existing in enumerate(self.loader.imported_digimon):
            if existing is digimon or existing.chr_id == digimon.chr_id or existing.id == digimon.id:
                self.loader.imported_digimon[index] = digimon
                return False

        self.loader.imported_digimon.append(digimon)
        return True

    def _find_imported_digimon(self, digimon: DigimonData, original_chr_id: str = "") -> Optional[DigimonData]:
        """Find the imported record matching the active Digimon, even if chr_id changed in the form."""
        if not hasattr(self.loader, 'imported_digimon'):
            return None

        chr_ids = {digimon.chr_id, original_chr_id}
        chr_ids.discard("")
        for imported in self.loader.imported_digimon:
            if imported is digimon or imported.chr_id in chr_ids or imported.id == digimon.id:
                return imported
        return None

    def _imported_dsts_loader_root(self, digimon: DigimonData, original_chr_id: str = "") -> Optional[Path]:
        """Return the remembered dsts-loader root for an imported Digimon."""
        source = getattr(digimon, "imported_dsts_loader_root", "")
        if source:
            return Path(source)

        imported = self._find_imported_digimon(digimon, original_chr_id)
        if imported:
            source = getattr(imported, "imported_dsts_loader_root", "")
            if source:
                return Path(source)
        return None

    def import_from_dsts_loader(self):
        """Import Digimon from dsts-loader format files"""
        import csv

        # Ask user to select either the Reloaded II mod root or its dsts-loader payload.
        default_path = get_default_mod_loader_path()

        loader_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Reloaded II Mod or dsts-loader Directory",
            str(get_existing_directory_start(default_path)),
            QFileDialog.Option.ShowDirsOnly
        )

        if not loader_dir:
            return

        selected_path = Path(loader_dir)
        loader_path = self._resolve_dsts_loader_root(selected_path)

        if not loader_path:
            QMessageBox.warning(
                self,
                "No Files Found",
                "No .ap.csv files found in this folder or its dsts-loader child.\n\n"
                "You can select either the Reloaded II mod folder, for example:\n"
                f"{get_default_mod_loader_path() / 'Youkomon'}\n\n"
                "or the inner dsts-loader folder."
            )
            return

        # Look for digimon_status_data.ap.csv files in the normalized payload root.
        status_files = self._dsts_loader_status_files(loader_path)

        if not status_files:
            QMessageBox.warning(
                self,
                "No Files Found",
                "No .ap.csv files found in patch/data/digimon_status.mbe/\n\n"
                "Make sure you selected the correct Reloaded II mod or dsts-loader directory."
            )
            return

        imported_count = 0
        imported_names = []
        first_imported_digimon = None

        try:
            for status_file in status_files:
                # Parse each status file
                digimon_list = self._parse_digimon_status_csv(status_file, loader_path)

                for digimon in digimon_list:
                    self._upsert_imported_digimon(digimon, loader_path)
                    imported_count += 1
                    imported_names.append(digimon.name)
                    if first_imported_digimon is None:
                        first_imported_digimon = digimon

            if imported_count == 0:
                QMessageBox.warning(
                    self,
                    "Import Failed",
                    "The selected files were found, but no Digimon rows could be imported."
                )
                return

            # Refresh the list
            self.load_digimon_list()

            # Ask if user wants to load the first imported Digimon for editing
            reply = QMessageBox.question(
                self,
                "Import Successful! 🎉",
                f"✅ Successfully imported {imported_count} Digimon:\n\n" +
                "\n".join(f"  • {name}" for name in imported_names[:10]) +
                (f"\n  ... and {len(imported_names) - 10} more" if len(imported_names) > 10 else "") +
                f"\n\nActive mod target:\n{loader_path}\n\n"
                "Create New will default to this mod and merge additional Digimon into it.\n\n"
                "Do you want to load the first imported Digimon for editing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )

            if reply == QMessageBox.StandardButton.Yes and first_imported_digimon:
                # Load the first imported Digimon
                first_digimon = first_imported_digimon
                self.load_digimon_data(first_digimon)
                self.current_digimon = first_digimon

                # Try to select it in the list (if it exists)
                try:
                    display_name = f"📥 {first_digimon.name} ({first_digimon.chr_id})"
                    index = self.digimon_list.findText(display_name, Qt.MatchFlag.MatchExactly)
                    if index >= 0:
                        self.digimon_list.setCurrentIndex(index)
                except Exception as select_error:
                    # Don't fail import if we can't select the item
                    print(f"Could not select imported item: {select_error}")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import Digimon:\n\n{str(e)}\n\n"
                "Make sure the files are in the correct dsts-loader format."
            )
            import traceback
            traceback.print_exc()

    def _parse_digimon_status_csv(self, csv_file: Path, base_path: Path):
        """Parse a digimon_status_data.ap.csv and related files"""
        import csv
        from copy import deepcopy

        digimon_list = []

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)  # Skip header

            for row in reader:
                if not row or len(row) < 4:
                    continue
                if not any(cell.strip() for cell in row):
                    continue

                raw_id = _clean_status_cell(row[0]) if len(row) > 0 else ""
                raw_char_key = _clean_status_cell(row[2]) if len(row) > 2 else ""
                raw_chr_id = _clean_status_cell(row[3]) if len(row) > 3 else ""
                if not raw_id or not raw_char_key or not raw_chr_id:
                    debug_log(f"Skipping incomplete imported status row from {csv_file.name}: {row[:4]}")
                    continue

                # Create new DigimonData object
                digimon = DigimonData()
                self._mark_import_source(digimon, base_path)

                # Parse basic info from digimon_status_data
                digimon.id = int(raw_id)
                digimon.char_key = raw_char_key
                digimon.chr_id = raw_chr_id
                digimon.stage_id = int(row[4]) if len(row) > 4 and row[4] else 0
                digimon.personality_id = int(row[5]) if len(row) > 5 and row[5] else 0
                digimon.type_id = int(row[6]) if len(row) > 6 and row[6] else 0
                digimon.generation_id = digimon.stage_id

                # Parse resistances (columns 7-17) - CORRECTED ORDER
                if len(row) > 17:
                    digimon.res_null = int(row[7]) if row[7] else 0
                    digimon.res_fire = int(row[8]) if row[8] else 0
                    digimon.res_water = int(row[9]) if row[9] else 0
                    digimon.res_ice = int(row[10]) if row[10] else 0      # Col10 = Ice
                    digimon.res_grass = int(row[11]) if row[11] else 0    # Col11 = Grass
                    digimon.res_wind = int(row[12]) if row[12] else 0     # Col12 = Wind
                    digimon.res_elec = int(row[13]) if row[13] else 0     # Col13 = Elec
                    digimon.res_ground = int(row[14]) if row[14] else 0   # Col14 = Ground
                    digimon.res_steel = int(row[15]) if row[15] else 0    # Col15 = Steel
                    digimon.res_light = int(row[16]) if row[16] else 0
                    digimon.res_dark = int(row[17]) if row[17] else 0

                # Parse traits (columns 19-60)
                # Handle multiple boolean formats: "true", "True", "1", "TRUE"
                digimon.traits = []
                for i in range(19, min(61, len(row))):
                    val = row[i].strip().lower() if row[i] else ''
                    digimon.traits.append(val in ('true', '1', 'yes'))

                # Parse base stats (columns 64-70)
                if len(row) > 70:
                    digimon.base_personality = int(row[61]) if row[61] else 0
                    digimon.base_hp = int(row[64]) if row[64] else 0
                    digimon.base_sp = int(row[65]) if row[65] else 0
                    digimon.base_atk = int(row[66]) if row[66] else 0
                    digimon.base_def = int(row[67]) if row[67] else 0
                    digimon.base_int = int(row[68]) if row[68] else 0
                    digimon.base_spi = int(row[69]) if row[69] else 0
                    digimon.base_spd = int(row[70]) if row[70] else 0

                # Parse signature skills (every 3 columns starting at 72)
                digimon.signature_skills = []
                for i in range(12):
                    idx = 72 + (i * 3)
                    if len(row) > idx + 2:
                        skill_id = int(row[idx]) if row[idx] else 0
                        slot = int(row[idx + 2]) if row[idx + 2] else 0
                        if skill_id > 0:
                            digimon.signature_skills.append({'id': skill_id, 'slot': slot})

                # Parse generic skills (every 3 columns starting at 108)
                digimon.generic_skills = []
                for i in range(4):
                    idx = 108 + (i * 3)
                    if len(row) > idx + 2:
                        skill_id = int(row[idx]) if row[idx] else 0
                        level = int(row[idx + 2]) if row[idx + 2] else 0
                        if skill_id > 0:
                            digimon.generic_skills.append({'id': skill_id, 'level': level})

                # Parse model type and animation set (columns 121-122)
                if len(row) > 122:
                    digimon.model_type = int(row[121]) if row[121] else 1  # Column 121: Model type
                    digimon.animation_set = int(row[122]) if row[122] else 1  # Column 122: Animation set
                    debug_log(f"Loaded model_type: {digimon.model_type}, animation_set: {digimon.animation_set}")

                # Parse field guide ID (column 131)
                if len(row) > 131:
                    field_guide_val = row[131].strip() if row[131] else ""
                    if field_guide_val:
                        try:
                            digimon.field_guide_id = int(field_guide_val)
                        except (ValueError, TypeError):
                            digimon.field_guide_id = -1
                    else:
                        digimon.field_guide_id = -1
                    debug_log(
                        f"Loaded field_guide_id: {digimon.field_guide_id} from column 131 "
                        f"(raw value: '{row[131] if len(row) > 131 else 'N/A'}')"
                    )
                else:
                    digimon.field_guide_id = -1

                # Parse status/profile reference ID (column 132)
                if len(row) > STATUS_REFERENCE_ID_COLUMN:
                    script_val = row[STATUS_REFERENCE_ID_COLUMN].strip() if row[STATUS_REFERENCE_ID_COLUMN] else ""
                    if script_val:
                        try:
                            digimon.script_id = int(script_val)
                        except (ValueError, TypeError):
                            digimon.script_id = -1
                    else:
                        digimon.script_id = -1
                    debug_log(
                        f"Loaded status reference ID: {digimon.script_id} from column {STATUS_REFERENCE_ID_COLUMN} "
                        f"(raw value: '{row[STATUS_REFERENCE_ID_COLUMN] if len(row) > STATUS_REFERENCE_ID_COLUMN else 'N/A'}')"
                    )
                else:
                    digimon.script_id = -1

                normalized_script_id = normalize_status_reference_id(
                    digimon.id,
                    digimon.field_guide_id,
                    digimon.script_id,
                )
                if normalized_script_id != digimon.script_id:
                    debug_log(
                        f"Corrected status reference ID from {digimon.script_id} to {normalized_script_id} "
                        f"for {digimon.name or digimon.chr_id}; column 132 must not mirror Field Guide ID."
                    )
                    digimon.script_id = normalized_script_id

                # Load name from char_name
                name_file = base_path / "patch_text01" / "text" / "char_name.mbe"
                digimon.name = self._load_name_from_csv(name_file, digimon.char_key)
                if not digimon.name:
                    digimon.name = digimon.char_key or digimon.chr_id or f"Digimon {digimon.id}"

                # Load profile from digimon_profile
                profile_file = base_path / "patch_text01" / "text" / "digimon_profile.mbe"
                digimon.profile_text = self._load_profile_from_csv(profile_file, digimon.id)
                debug_log(f"Loaded profile for ID {digimon.id}: '{digimon.profile_text[:50] if digimon.profile_text else 'EMPTY'}'...")

                # Load char_info data (contains motion_ref and model_ref)
                char_info_file = base_path / "patch" / "data" / "char_info.mbe"
                char_info_data = self._load_char_info_from_csv(char_info_file, digimon.char_key)
                if char_info_data:
                    digimon.motion_id = char_info_data.get('motion_ref', "")
                    digimon.model_id = char_info_data.get('model_ref', "")
                    debug_log(f"Loaded from char_info - model_id: '{digimon.model_id}', motion_id: '{digimon.motion_id}'")

                # Load model settings
                model_file = base_path / "patch" / "data" / "model_setting.mbe"
                digimon.model_setting_data = self._load_model_setting_from_csv(model_file, digimon.chr_id)

                # Load animation source mapping. Recolors usually keep a new
                # model/Chr ID but point animations at the original source Chr ID.
                anim_file = base_path / "patch" / "data" / "anim_setting.mbe"
                digimon.animation_ref = self._load_animation_ref_from_csv(anim_file, digimon.chr_id)

                # Load LOD data
                lod_file = base_path / "patch" / "data" / "lod_chara.mbe"
                digimon.lod_data = self._load_lod_from_csv(lod_file, digimon.chr_id)

                # Load evolution data
                evolution_file = base_path / "patch" / "data" / "evolution.mbe"
                digimon.evolution_paths, digimon.evolution_conditions = self._load_evolution_from_csv(evolution_file, digimon.id)

                # Load pre-evolutions from evolution_to.csv (Digimon that evolve INTO this one)
                evolution_file_path = base_path / "patch" / "data" / "evolution.mbe"
                digimon.deevolution_sources = self._load_preevolutions_from_csv(evolution_file_path, digimon.id)

                # Load tribe/belong data
                belong_file = base_path / "patch_text01" / "text" / "belong.mbe"
                digimon.tribe_name = self._load_tribe_from_csv(belong_file, digimon.id)

                digimon.localized_text = self._load_localized_text_from_dsts_loader(base_path, digimon)
                self._apply_english_localized_text_to_digimon(digimon)

                # Initialize other required data structures
                digimon.model_locator_data = {}
                digimon.model_locator_motion_data = []
                digimon.field_move_animation_data = []
                digimon.lod_model_data = {}

                digimon_list.append(digimon)

        return digimon_list

    def _load_text_table_value(self, base_path: Path, keys: Iterable[str]) -> str:
        """Load one value from a text table by any accepted key."""
        import csv

        key_set = {str(key).strip('"') for key in keys if str(key).strip('"')}
        if not key_set:
            return ""

        for csv_file in base_path.glob("*.ap.csv"):
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if len(row) >= 2 and row[0].strip('"') in key_set:
                            return row[1]
            except Exception as exc:
                debug_log(f"Error loading text table value from {csv_file}: {exc}")
                continue
        return ""

    def _iter_patch_text_dirs(self, base_path: Path, include_known: bool = False) -> List[Path]:
        """Return discovered patch_textXX folders under a dsts-loader root."""
        folder_paths: Dict[str, Path] = {}
        root = Path(base_path)

        if root.exists():
            for child in root.iterdir():
                if not child.is_dir():
                    continue
                if not TEXT_LANGUAGE_FOLDER_RE.match(child.name):
                    continue
                folder = self._normalize_text_folder_name(child.name)
                if folder:
                    folder_paths[folder] = child

        if include_known:
            for folder, _language_name in TEXT_LANGUAGE_FOLDERS:
                folder_paths.setdefault(folder, root / folder)

        return [folder_paths[folder] for folder in sorted(folder_paths, key=self._language_sort_key)]

    def _load_localized_text_from_dsts_loader(self, base_path: Path, digimon: DigimonData) -> Dict[str, Dict[str, str]]:
        """Load name/profile/belong text from every patch_textXX folder in a mod."""
        localized_text: Dict[str, Dict[str, str]] = {}

        for patch_text_dir in self._iter_patch_text_dirs(base_path):
            folder = self._normalize_text_folder_name(patch_text_dir.name)
            text_root = patch_text_dir / "text"
            values = {
                "name": self._load_text_table_value(text_root / "char_name.mbe", {digimon.char_key}),
                "profile_text": self._load_text_table_value(
                    text_root / "digimon_profile.mbe",
                    digimon_profile_key_variants(digimon.id),
                ),
                "tribe_name": self._load_text_table_value(text_root / "belong.mbe", {str(digimon.id)}),
            }

            if any(value.strip() for value in values.values()):
                localized_text[folder] = values

        return localized_text

    def _apply_english_localized_text_to_digimon(self, digimon: DigimonData):
        """Keep legacy single-language fields aligned with patch_text01."""
        localized_text = self._normalize_localized_text_map(getattr(digimon, "localized_text", {}))
        digimon.localized_text = localized_text
        english_values = localized_text.get(ENGLISH_TEXT_FOLDER, {})

        if english_values.get("name"):
            digimon.name = english_values["name"]
        elif not getattr(digimon, "name", "") or digimon.name == "Unknown":
            for values in localized_text.values():
                if values.get("name"):
                    digimon.name = values["name"]
                    break

        if english_values.get("profile_text"):
            digimon.profile_text = english_values["profile_text"]
        elif not getattr(digimon, "profile_text", ""):
            for values in localized_text.values():
                if values.get("profile_text"):
                    digimon.profile_text = values["profile_text"]
                    break

        if english_values.get("tribe_name"):
            digimon.tribe_name = english_values["tribe_name"]
        elif not getattr(digimon, "tribe_name", "") or digimon.tribe_name == "None":
            for values in localized_text.values():
                if values.get("tribe_name"):
                    digimon.tribe_name = values["tribe_name"]
                    break

    def _load_name_from_csv(self, base_path: Path, char_key: str) -> str:
        """Load Digimon name from char_name CSV files"""
        import csv

        csv_files = list(base_path.glob("*.ap.csv"))
        for csv_file in csv_files:
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    for row in reader:
                        if len(row) >= 2 and row[0].strip('"') == char_key:
                            return row[1].strip('"')
            except:
                continue
        return "Unknown"

    def _load_char_info_from_csv(self, base_path: Path, char_key: str) -> dict:
        """Load char_info data from CSV files"""
        import csv

        csv_files = list(base_path.glob("*.ap.csv"))
        for csv_file in csv_files:
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    for row in reader:
                        if len(row) >= 1 and row[0].strip('"') == char_key:
                            # Extract relevant fields and strip quotes
                            # Column 3 is this entry's Chr ID. Column 10 is the
                            # model/animation reference used by existing mods.
                            # Column 8: Audio ID (motion_ref)
                            model_ref = row[10].strip('"') if len(row) > 10 and row[10] else ""
                            motion_ref = row[8].strip('"') if len(row) > 8 and row[8] else ""
                            debug_log(
                                f"Found char_info for {char_key} - motion_ref (col8): "
                                f"'{motion_ref}', model_ref (col10): '{model_ref}'"
                            )
                            return {
                                'motion_ref': motion_ref,  # Column 8: Audio ID (motion_ref)
                                'model_ref': model_ref  # Column 10: model/animation reference
                            }
            except Exception as e:
                debug_log(f"Error loading char_info from {csv_file}: {e}")
                continue
        debug_log(f"No char_info found for char_key: {char_key}")
        return {}

    def _load_animation_ref_from_csv(self, base_path: Path, chr_id: str) -> str:
        """Load same_animation_data mapping for an imported dsts-loader Digimon."""
        import csv

        csv_files = list(base_path.glob("*.ap.csv"))
        for csv_file in csv_files:
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    for row in reader:
                        if len(row) >= 2 and row[0].strip('"') == chr_id:
                            return row[1].strip('"') if row[1] else ""
            except Exception as e:
                debug_log(f"Error loading animation ref from {csv_file}: {e}")
                continue
        return ""

    def _load_profile_from_csv(self, base_path: Path, digimon_id: int) -> str:
        """Load Digimon profile from digimon_profile CSV files"""
        import csv

        profile_keys = digimon_profile_key_variants(digimon_id)

        csv_files = list(base_path.glob("*.ap.csv"))
        for csv_file in csv_files:
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    for row in reader:
                        if len(row) >= 2 and row[0] in profile_keys:
                            return row[1]  # Don't strip quotes - csv.reader already handles that
            except:
                continue
        return ""

    def _load_model_setting_from_csv(self, base_path: Path, chr_id: str) -> dict:
        """Load model_setting data from CSV files"""
        import csv

        csv_files = list(base_path.glob("*.ap.csv"))
        for csv_file in csv_files:
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    header = next(reader)  # Skip header
                    for row in reader:
                        if len(row) >= 1 and row[0].strip('"') == chr_id:
                            result = {'raw_data': row}
                            # Parse known fields from model_setting.mbe
                            # Column indices based on research findings
                            if len(row) > 10:
                                try:
                                    result['npc_collision'] = float(row[10]) if row[10] else 0.0
                                except (ValueError, TypeError):
                                    result['npc_collision'] = 0.0
                            if len(row) > 38:
                                try:
                                    result['digimon_distance_from_agent'] = float(row[38]) if row[38] else 0.0
                                except (ValueError, TypeError):
                                    result['digimon_distance_from_agent'] = 0.0
                            if len(row) > 39:
                                try:
                                    result['agent_distance_2'] = float(row[39]) if row[39] else 0.0
                                except (ValueError, TypeError):
                                    result['agent_distance_2'] = 0.0
                            if len(row) > 40:
                                try:
                                    result['agent_distance'] = int(row[40]) if row[40] else 0
                                except (ValueError, TypeError):
                                    result['agent_distance'] = 0
                            if len(row) > 43:
                                try:
                                    result['camera_distance_skill'] = float(row[43]) if row[43] else 0.0
                                except (ValueError, TypeError):
                                    result['camera_distance_skill'] = 0.0
                            if len(row) > 47:
                                try:
                                    result['shield_size'] = float(row[47]) if row[47] else 0.0
                                except (ValueError, TypeError):
                                    result['shield_size'] = 0.0
                            if len(row) > 56:
                                try:
                                    result['battle_scale'] = float(row[56]) if row[56] else 1.0
                                except (ValueError, TypeError):
                                    result['battle_scale'] = 1.0
                            if len(row) > 58:
                                try:
                                    result['menu_scale'] = float(row[58]) if row[58] else 1.0
                                except (ValueError, TypeError):
                                    result['menu_scale'] = 1.0
                            if len(row) > 59:
                                try:
                                    result['field_scale'] = float(row[59]) if row[59] else 1.0
                                except (ValueError, TypeError):
                                    result['field_scale'] = 1.0
                            if len(row) > 71:
                                try:
                                    result['rideable'] = int(row[71]) if row[71] else 0
                                except (ValueError, TypeError):
                                    result['rideable'] = 0
                            return result
            except:
                continue
        return {}

    def _resolve_prefixed_file(self, file_path: Path) -> Path:
        """
        Resolve file path with flexible numeric prefix (e.g., 000_, 01_, 1_).
        Wraps the loader's method for use in DigimonEditor.
        """
        return self.loader._resolve_prefixed_file(file_path)

    def _load_lod_from_csv(self, base_path: Path, chr_id: str) -> dict:
        """Load LOD data from CSV files"""
        import csv

        lod_file = self._resolve_prefixed_file(base_path / "000_lod.ap.csv")
        if lod_file.exists():
            try:
                with open(lod_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    for row in reader:
                        if len(row) >= 4 and row[0].strip('"') == chr_id:
                            return {
                                'lod_distance_1': float(row[1]) if row[1] else 20,
                                'lod_distance_2': float(row[2]) if row[2] else 65,
                                'lod_distance_3': float(row[3]) if row[3] else 500
                            }
            except:
                pass

        return {'lod_distance_1': 20, 'lod_distance_2': 65, 'lod_distance_3': 500}

    def _load_evolution_from_csv(self, base_path: Path, digimon_id: int):
        """Load evolution paths and conditions from CSV files"""
        import csv

        def safe_int(value, default: int = 0) -> int:
            try:
                text = str(value).strip().strip('"')
                return int(text) if text else default
            except (TypeError, ValueError):
                return default

        def parse_condition_row(row):
            return {
                'mode': safe_int(row[2], 1) if len(row) > 2 else 1,
                'tamerLevel': safe_int(row[3]) if len(row) > 3 else 0,
                'HP': safe_int(row[4]) if len(row) > 4 else 0,
                'SP': safe_int(row[5]) if len(row) > 5 else 0,
                'ATK': safe_int(row[6]) if len(row) > 6 else 0,
                'DEF': safe_int(row[7]) if len(row) > 7 else 0,
                'INT': safe_int(row[8]) if len(row) > 8 else 0,
                'SPI': safe_int(row[9]) if len(row) > 9 else 0,
                'SPD': safe_int(row[10]) if len(row) > 10 else 0,
                'unknown1': safe_int(row[11]) if len(row) > 11 else 0,
                'unknown2': safe_int(row[12]) if len(row) > 12 else 0,
                'skillCountValor': safe_int(row[13]) if len(row) > 13 else 0,
                'skillCountPhilantropy': safe_int(row[14]) if len(row) > 14 else 0,
                'skillCountAmicable': safe_int(row[15]) if len(row) > 15 else 0,
                'skillCountWisdom': safe_int(row[16]) if len(row) > 16 else 0,
                'needsItem': safe_int(row[22]) if len(row) > 22 else 0,
                'jogressDbIdA': safe_int(row[24]) if len(row) > 24 else 0,
                'jogressPersonalityA': safe_int(row[26]) if len(row) > 26 else 0,
                'jogressDbIdB': safe_int(row[27]) if len(row) > 27 else 0,
                'jogressPersonalityB': safe_int(row[29]) if len(row) > 29 else 0
            }

        evolution_paths = []
        evolution_conditions = []
        conditions_by_target = {}

        # Load evolution paths from 001_evolution_to.ap.csv
        evo_file = self._resolve_prefixed_file(base_path / "001_evolution_to.ap.csv")
        if evo_file.exists():
            try:
                with open(evo_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    for row in reader:
                        if len(row) >= 4:
                            from_id = safe_int(row[1])
                            if from_id == digimon_id:
                                to_id = safe_int(row[3])
                                evo_type = safe_int(row[5]) if len(row) > 5 else 0
                                if to_id > 0:
                                    evolution_paths.append({
                                        'to_id': to_id,
                                        'evolution_type': evo_type
                                    })
            except Exception as e:
                print(f"Error loading evolution paths: {e}")

        # Load evolution conditions from 000_evolution_condition.ap.csv
        cond_file = self._resolve_prefixed_file(base_path / "000_evolution_condition.ap.csv")
        if cond_file.exists():
            try:
                with open(cond_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    for row in reader:
                        if len(row) >= 3:
                            target_id = safe_int(row[0])
                            if target_id <= 0:
                                continue
                            conditions = parse_condition_row(row)
                            conditions_by_target[target_id] = conditions
                            if target_id == digimon_id:
                                evolution_conditions.append(conditions)
            except Exception as e:
                print(f"Error loading evolution conditions: {e}")

        for evo_path in evolution_paths:
            conditions = conditions_by_target.get(evo_path.get('to_id', 0))
            if conditions:
                evo_path['conditions'] = conditions
                evo_path['export_conditions'] = True
                if safe_int(digimon_id) in jogress_partner_ids_from_conditions(conditions):
                    evo_path['export_partner_rows'] = True

        return evolution_paths, evolution_conditions

    def _load_preevolutions_from_csv(self, base_path: Path, digimon_id: int):
        """Load pre-evolutions from evolution_to.csv

        Pre-evolutions are Digimon that evolve INTO this Digimon.
        In evolution_to.csv:
        - Column 1 = source Digimon ID (the one that evolves)
        - Column 3 = target Digimon ID (what it evolves into)

        So pre-evolutions are entries where column 3 == digimon_id
        """
        import csv

        preevolution_sources = []

        evo_file = self._resolve_prefixed_file(base_path / "001_evolution_to.ap.csv")
        if evo_file.exists():
            try:
                with open(evo_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    for row in reader:
                        if len(row) >= 4:
                            source_id = int(row[1]) if row[1] else 0
                            target_id = int(row[3]) if row[3] else 0
                            evo_type = int(row[5]) if len(row) > 5 and row[5] else 0

                            # If this Digimon is the TARGET, then source is a pre-evolution
                            if target_id == digimon_id and source_id > 0:
                                preevolution_sources.append({
                                    'from_id': source_id,
                                    'evolution_type': evo_type
                                })
            except Exception as e:
                print(f"Error loading pre-evolutions: {e}")

        return preevolution_sources

    def _load_tribe_from_csv(self, base_path: Path, digimon_id: int) -> str:
        """Load tribe/belong data from CSV"""
        import csv

        tribe_file = self._resolve_prefixed_file(base_path / "000_Sheet1.ap.csv")
        if tribe_file.exists():
            try:
                with open(tribe_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    for row in reader:
                        if len(row) >= 2:
                            row_id = int(row[0]) if row[0] else 0
                            if row_id == digimon_id:
                                return row[1].strip('"') if row[1] else "None"
            except Exception as e:
                print(f"Error loading tribe: {e}")

        return "None"

    def create_new_digimon(self):
        """Create a new Digimon entry using a selected Digimon as template"""
        # Create dialog to select template Digimon
        dialog = QDialog(self)
        dialog.setWindowTitle("Create New Digimon")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)

        # Instructions
        instruction_label = QLabel(
            "Select a Digimon to use as a template.\n"
            "The new Digimon will copy all stats, skills, and properties\n"
            "from the selected template, which you can then customize."
        )
        instruction_label.setWordWrap(True)
        layout.addWidget(instruction_label)

        # Template selection
        layout.addWidget(QLabel("\nTemplate Digimon:"))
        template_combo = QComboBox()

        # Populate with all Digimon (sorted by ID)
        chr_ids = self.loader.get_all_digimon_chr_ids()

        # Sort by numeric part, handling non-numeric suffixes (e.g., chr183aa010101)
        def sort_key(chr_id):
            try:
                # Extract just the numeric part after 'chr'
                numeric_part = ''
                for char in chr_id.replace('chr', ''):
                    if char.isdigit():
                        numeric_part += char
                    else:
                        break
                return int(numeric_part) if numeric_part else 999999
            except:
                return 999999

        chr_ids_sorted = sorted(chr_ids, key=sort_key)

        for chr_id in chr_ids_sorted:
            name = self.loader._get_digimon_name_by_chr_id(chr_id)
            digimon_id = chr_id.replace('chr', '')
            template_combo.addItem(f"{name} ({chr_id})", chr_id)

        # Default to chr805 (Darkshadow)
        default_index = template_combo.findData("chr805")
        if default_index >= 0:
            template_combo.setCurrentIndex(default_index)

        layout.addWidget(template_combo)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # Show dialog
        if dialog.exec() == QDialog.DialogCode.Rejected:
            return  # User cancelled

        # Get selected template
        template_chr_id = template_combo.currentData()
        template_digimon = self.loader.get_digimon_by_chr_id(template_chr_id)

        if not template_digimon:
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to load template Digimon: {template_chr_id}"
            )
            return

        # Use template but with new ID and name
        digimon = template_digimon

        # Find the next available ID - check both base game and DLC
        existing_ids = self.loader.get_all_digimon_ids()
        # Also check DLC IDs
        try:
            for _dlc_id, dlc_status_file in self.loader.iter_dlc_csv_files(
                "data", "digimon_status", "000_digimon_status_data.csv"
            ):
                dlc_rows = self.loader.load_csv(dlc_status_file)
                for row in dlc_rows[1:]:  # Skip header
                    if len(row) > 0 and row[0]:
                        try:
                            existing_ids.append(int(row[0]))
                        except ValueError:
                            continue
        except Exception:
            pass  # If DLC check fails, just use base game IDs
        next_id = max(existing_ids) + 1 if existing_ids else 1000

        digimon.id = next_id
        digimon.name = f"New Digimon (based on {template_digimon.name})"
        digimon.char_key = "char_NEW_DIGIMON"  # User can customize this

        # Create NEW chr_id for this Digimon (like chr1000)
        # But store template chr_id for animations (saved in animation_ref_edit)
        new_chr_id = f"chr{next_id}"
        digimon.chr_id = new_chr_id  # NEW unique chr_id
        digimon.field_guide_id = first_free_field_guide_id(self.loader, new_chr_id)
        digimon.script_id = next_id

        # Store template chr_id separately (will be used in animation reference)
        self.template_chr_id_for_animation = template_chr_id

        self.load_digimon_data(digimon)

        # Show info message
        QMessageBox.information(
            self,
            "Template Loaded",
            f"✅ Created new Digimon based on {template_digimon.name}!\n\n"
            f"New ID: {next_id}\n"
            f"New Chr ID: {new_chr_id}\n"
            f"Field Guide ID: {digimon.field_guide_id}\n"
            f"Animation Reference: {template_chr_id}\n\n"
            f"The new Digimon has a unique chr_id ({new_chr_id})\n"
            f"but uses animations from {template_chr_id}.\n\n"
            f"Customize the stats and click 'Export Reloaded II Mod'."
        )

        # Refresh the digimon list to show the new Digimon
        self.load_digimon_list()

    def save_current_digimon(self):
        """Save the current Digimon data"""
        if not self.current_digimon:
            return

        # Store original values before updating
        loaded_identity = dict(getattr(self, "loaded_digimon_identity", {}) or {})
        is_pending_new = bool(
            loaded_identity.get("pending_new_mod_entry")
            or getattr(self.current_digimon, "pending_new_mod_entry", False)
        )
        if is_pending_new:
            original_id = -1
            original_chr_id = ""
            original_char_key = ""
        else:
            original_id = self.current_digimon.id
            original_chr_id = self.current_digimon.chr_id
            original_char_key = self.current_digimon.char_key
        chr_id_to_reload = self.current_digimon.chr_id

        if not self.validate_field_guide_id():
            return

        # Update current digimon with form data
        self.update_digimon_from_form()

        # Validate for duplicates
        if not self.validate_digimon_uniqueness(original_id, original_chr_id, original_char_key):
            # Revert changes
            if not is_pending_new:
                self.current_digimon.id = original_id
                self.current_digimon.chr_id = original_chr_id
                self.current_digimon.char_key = original_char_key
            return

        if is_pending_new:
            pending_root = self._imported_dsts_loader_root(self.current_digimon, "") or self._active_dsts_loader_root()
            if not pending_root:
                QMessageBox.warning(self, "No Active Mod", "Could not resolve the active mod folder for this pending entry.")
                return
            if self.save_to_dsts_loader(self.current_digimon, pending_root, ask_for_path=False):
                return

        # Imported Digimon keep their source folder, so Save Changes can update
        # the same Reloaded II/dsts-loader payload without asking again.
        imported_record = self._find_imported_digimon(self.current_digimon, original_chr_id)
        is_imported = imported_record is not None

        if is_imported:
            imported_root = self._imported_dsts_loader_root(self.current_digimon, original_chr_id)
            if imported_root:
                self.save_to_dsts_loader(self.current_digimon, imported_root, ask_for_path=False)
                return

            # Create custom dialog for save options
            dialog = QMessageBox(self)
            dialog.setWindowTitle("Save Imported Digimon")
            dialog.setText(f"Where would you like to save {self.current_digimon.name}?")
            dialog.setInformativeText(
                "📥 dsts-loader: Update the .ap.csv files\n"
                "📦 Reloaded II Mod: Create/update a ready-to-load mod folder"
            )

            dsts_button = dialog.addButton("📥 Save to dsts-loader", QMessageBox.ButtonRole.AcceptRole)
            dlc_button = dialog.addButton("📦 Export Reloaded II Mod", QMessageBox.ButtonRole.ActionRole)
            cancel_button = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)

            dialog.exec()
            clicked = dialog.clickedButton()

            if clicked == cancel_button:
                return
            elif clicked == dsts_button:
                # Save to dsts-loader
                self.save_to_dsts_loader(self.current_digimon)
                return
            elif clicked == dlc_button:
                self.export_digimon_to_reloaded_mod(
                    self.current_digimon,
                    dict(getattr(self, "loaded_digimon_identity", {}) or {})
                )
                return

        # Check if this Digimon is from DLC or base game
        is_from_dlc = self.is_loaded_digimon_from_dlc()

        if is_from_dlc:
            # Save to DLC instead of base game
            dlc_exporter = DLCExporter(self.loader)
            animation_ref = self.animation_ref_edit.text().strip() if self.animation_ref_edit.text().strip() else self.current_digimon.chr_id

            if dlc_exporter.save_digimon_to_dlc(self.current_digimon, animation_ref):
                self.clear_modified_flag()
                QMessageBox.information(self, "Success", "Digimon data saved to DLC successfully!")
                # Invalidate caches to ensure fresh data is loaded
                if hasattr(self.loader, '_invalidate_digimon_status_cache'):
                    self.loader._invalidate_digimon_status_cache()
                # Clear profile cache to reload updated profile text
                self.loader._digimon_profiles_cache = None
                # Clear char_names cache if it exists to force fresh name lookup
                if hasattr(self.loader, '_char_names_cache'):
                    self.loader._char_names_cache = None
                # Refresh the digimon list to show any changes
                self.load_digimon_list()
                # Small delay to ensure file writes are complete
                QApplication.processEvents()
                # Reload the Digimon data to reflect any changes from save
                digimon = self.loader.get_digimon_by_chr_id(chr_id_to_reload)
                if digimon:
                    # Ensure name is loaded from DLC files
                    digimon.name = self.loader._get_digimon_name(digimon.char_key, check_dlc=True)
                    self.load_digimon_data(digimon)
            else:
                QMessageBox.warning(self, "Error", "Failed to save Digimon data to DLC")
        else:
            # Save to base game files
            if self.loader.save_digimon_data(self.current_digimon):
                self.clear_modified_flag()
                QMessageBox.information(self, "Success", "Digimon data saved successfully!")
                # Invalidate caches to ensure fresh data is loaded
                if hasattr(self.loader, '_invalidate_digimon_status_cache'):
                    self.loader._invalidate_digimon_status_cache()
                # Clear profile cache to reload updated profile text
                self.loader._digimon_profiles_cache = None
                # Clear char_names cache if it exists to force fresh name lookup
                if hasattr(self.loader, '_char_names_cache'):
                    self.loader._char_names_cache = None
                # Refresh the digimon list to show any changes
                self.load_digimon_list()
                # Small delay to ensure file writes are complete
                QApplication.processEvents()
                # Reload the Digimon data to reflect any changes from save
                digimon = self.loader.get_digimon_by_chr_id(chr_id_to_reload)
                if digimon:
                    # Ensure name is loaded from files
                    digimon.name = self.loader._get_digimon_name(digimon.char_key, check_dlc=True)
                    self.load_digimon_data(digimon)
            else:
                QMessageBox.warning(self, "Error", "Failed to save Digimon data")

    def remove_digimon_from_dlc(self):
        """Remove the current Digimon from DLC files"""
        if not self.current_digimon:
            QMessageBox.warning(self, "No Digimon", "Please load a Digimon first.")
            return

        # Check if this Digimon is from DLC
        is_from_dlc = self.is_loaded_digimon_from_dlc()
        if not is_from_dlc:
            QMessageBox.warning(
                self,
                "Cannot Remove",
                "This Digimon is from the base game and cannot be removed.\n\n"
                "Only Digimon from DLC can be removed."
            )
            return

        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            "Remove Digimon from DLC",
            f"⚠️ WARNING: This will permanently remove {self.current_digimon.name} (ID: {self.current_digimon.id}) from all DLC files!\n\n"
            f"This action cannot be undone.\n\n"
            f"The following will be removed:\n"
            f"- Character info\n"
            f"- Status data\n"
            f"- Evolution paths\n"
            f"- Name and profile text\n"
            f"- Model and animation data\n\n"
            f"Are you absolutely sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        # Remove from DLC
        dlc_exporter = DLCExporter(self.loader)
        success = dlc_exporter.remove_digimon_from_dlc(
            digimon_id=self.current_digimon.id,
            chr_id=self.current_digimon.chr_id,
            char_key=self.current_digimon.char_key
        )

        if success:
            QMessageBox.information(
                self,
                "Success",
                f"✅ {self.current_digimon.name} has been removed from DLC files!\n\n"
                f"All references to this Digimon have been cleaned up.\n"
                f"Remember to repack DLC to MBE files to finalize the changes."
            )
            # Clear current digimon and refresh list
            self.current_digimon = None
            self.current_digimon_label.setText("📂 No Digimon loaded")
            self.remove_button.setEnabled(False)
            self.save_button.setEnabled(False)
            self.export_dlc_button.setEnabled(False)
            self.load_digimon_list()
        else:
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to remove {self.current_digimon.name} from DLC.\n\n"
                f"Check the console for details."
            )

    def get_reloaded_mod_export_options(self, digimon: DigimonData) -> Optional[dict]:
        """Ask for Reloaded II mod folder and ModConfig metadata."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Export Reloaded II Mod")
        dialog.setMinimumWidth(620)

        layout = QVBoxLayout(dialog)

        info = QLabel(
            "This creates a Reloaded II mod folder with ModConfig.json and a dsts-loader payload."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #555; padding: 8px; background-color: #f8f9fa; border-radius: 6px;")
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(10)

        folder_edit = QLineEdit()
        folder_edit.setText(make_default_mod_folder_name(digimon.name))
        folder_edit.setPlaceholderText("Example: Youkomon")
        form.addRow("Folder Name:", folder_edit)

        mod_name_edit = QLineEdit()
        mod_name_edit.setText(digimon.name or "Custom Digimon")
        form.addRow("Mod Name:", mod_name_edit)

        author_edit = QLineEdit()
        author_edit.setText(getattr(self, "last_mod_author", os.environ.get("USERNAME", "")))
        author_edit.setPlaceholderText("Your name")
        form.addRow("Author:", author_edit)

        version_edit = QLineEdit()
        version_edit.setText("1.0.0")
        form.addRow("Version:", version_edit)

        description_edit = QTextEdit()
        description_edit.setPlainText(f"Adds {digimon.name} to Digimon Story Time Stranger.")
        description_edit.setMaximumHeight(90)
        form.addRow("Description:", description_edit)

        path_preview = QLabel()
        path_preview.setWordWrap(True)
        path_preview.setStyleSheet("color: #495057; padding: 8px; background-color: #eef4ff; border-radius: 6px;")
        form.addRow("Output:", path_preview)

        layout.addLayout(form)

        result = {}

        def update_preview():
            folder_name = sanitize_mod_folder_name(folder_edit.text(), make_default_mod_folder_name(digimon.name))
            mod_root = get_default_mod_loader_path() / folder_name
            path_preview.setText(str(mod_root / "dsts-loader"))

        def validate_and_accept():
            folder_name = sanitize_mod_folder_name(folder_edit.text(), make_default_mod_folder_name(digimon.name))
            mod_name = mod_name_edit.text().strip()
            author = author_edit.text().strip()
            version = version_edit.text().strip() or "1.0.0"
            description = description_edit.toPlainText().strip()

            if not mod_name:
                QMessageBox.warning(dialog, "Missing Mod Name", "Please enter a mod name.")
                return
            if not author:
                QMessageBox.warning(dialog, "Missing Author", "Please enter your user/author name.")
                return
            if not description:
                QMessageBox.warning(dialog, "Missing Description", "Please enter a mod description.")
                return

            mod_root = get_default_mod_loader_path() / folder_name
            if mod_root.exists():
                reply = QMessageBox.question(
                    dialog,
                    "Update Existing Mod Folder",
                    f"The folder already exists:\n{mod_root}\n\n"
                    "Update ModConfig.json and merge this Digimon into its dsts-loader files?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                if reply == QMessageBox.StandardButton.No:
                    return

            result.update({
                "folder_name": folder_name,
                "mod_id": make_mod_id_from_folder_name(folder_name),
                "mod_name": mod_name,
                "author": author,
                "version": version,
                "description": description,
                "mod_root": mod_root,
                "dsts_loader_root": mod_root / "dsts-loader"
            })
            self.last_mod_author = author
            dialog.accept()

        folder_edit.textChanged.connect(update_preview)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Export Mod")
        buttons.accepted.connect(validate_and_accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        update_preview()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return result

    def write_reloaded_mod_config(self, options: dict):
        """Write ModConfig.json for a generated Reloaded II mod folder."""
        mod_root = options["mod_root"]
        mod_root.mkdir(parents=True, exist_ok=True)
        config = build_reloaded_mod_config(
            mod_id=options["mod_id"],
            mod_name=options["mod_name"],
            author=options["author"],
            description=options["description"],
            version=options["version"]
        )
        with open(mod_root / "ModConfig.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.write("\n")

    def _clear_mvgl_fileloader_cache(self) -> str:
        """
        Clear MVGL FileLoader's generated cache after dsts-loader files change.

        FileLoader builds packed .mbe cache files from every enabled mod. If that
        cache survives while app_0 MBE patches change, FileLoader can fail on
        startup with duplicate archive keys such as "app_0". The cache is safe to
        delete because Reloaded rebuilds it on the next launch.
        """
        cache_path = get_mvgl_fileloader_cache_path()
        if not cache_path.exists():
            return ""

        try:
            allowed_root = (get_default_mod_loader_path() / "MVGL.FileLoader.Reloaded" / "cached").resolve()
            resolved_cache = cache_path.resolve()
            if resolved_cache != allowed_root and allowed_root not in resolved_cache.parents:
                raise RuntimeError(f"Refusing to clear unexpected cache path: {resolved_cache}")

            def retry_readonly(func, path, exc_info):
                try:
                    os.chmod(path, 0o700)
                    func(path)
                except Exception:
                    raise exc_info[1]

            shutil.rmtree(resolved_cache, onerror=retry_readonly)
            return "MVGL FileLoader cache was cleared so Reloaded can rebuild it."
        except Exception as exc:
            return (
                "Could not clear MVGL FileLoader cache automatically.\n"
                f"Cache path: {cache_path}\n"
                f"Reason: {exc}\n\n"
                "If Reloaded shows a duplicate app_0 error, close the game/Reloaded and delete that cache folder."
            )

    def _consume_mvgl_cache_notice(self) -> str:
        """Return and clear the latest cache notice for save/export dialogs."""
        notice = getattr(self, "last_mvgl_cache_notice", "")
        self.last_mvgl_cache_notice = ""
        return f"\n\n{notice}" if notice else ""

    def export_digimon_to_reloaded_mod(self, digimon: DigimonData, original_identity: Optional[dict] = None) -> Optional[Path]:
        """Create/update a Reloaded II mod folder and merge this Digimon into dsts-loader files."""
        options = self.get_reloaded_mod_export_options(digimon)
        if not options:
            return None

        self.write_reloaded_mod_config(options)
        dsts_loader_root = options["dsts_loader_root"]
        dsts_loader_root.mkdir(parents=True, exist_ok=True)

        original_identity = dict(original_identity or {})
        pending_new = bool(
            original_identity.get("pending_new_mod_entry")
            or getattr(digimon, "pending_new_mod_entry", False)
        )
        merge_identity = {} if pending_new else original_identity

        if not self._merge_digimon_to_dsts_loader(dsts_loader_root, digimon, merge_identity):
            QMessageBox.warning(self, "Export Failed", "Failed to write dsts-loader files for the Reloaded II mod.")
            return None

        self._set_active_dsts_loader_root(dsts_loader_root)
        if pending_new:
            digimon.pending_new_mod_entry = False
            self.loaded_digimon_identity = {}
        self._upsert_imported_digimon(digimon, dsts_loader_root)
        self._remember_loaded_identity(digimon)
        return options["mod_root"]

    def export_to_dlc(self):
        """Export the current Digimon as a Reloaded II compatible mod folder."""
        if not self.current_digimon:
            return
        loaded_identity = dict(getattr(self, "loaded_digimon_identity", {}) or {})
        is_pending_new = bool(
            loaded_identity.get("pending_new_mod_entry")
            or getattr(self.current_digimon, "pending_new_mod_entry", False)
        )
        if is_pending_new:
            original_id = -1
            original_chr_id = ""
            original_char_key = ""
        else:
            original_id = self.current_digimon.id
            original_chr_id = self.current_digimon.chr_id
            original_char_key = self.current_digimon.char_key

        if not self.validate_field_guide_id():
            return

        # Update current digimon with form data
        self.update_digimon_from_form()

        if not self.validate_digimon_uniqueness(original_id, original_chr_id, original_char_key):
            if not is_pending_new:
                self.current_digimon.id = original_id
                self.current_digimon.chr_id = original_chr_id
                self.current_digimon.char_key = original_char_key
            return

        original_identity = dict(getattr(self, "loaded_digimon_identity", {}) or {})
        mod_root = self.export_digimon_to_reloaded_mod(self.current_digimon, original_identity)
        if mod_root:
            self.clear_modified_flag()
            cache_notice = self._consume_mvgl_cache_notice()
            QMessageBox.information(
                self,
                "Success",
                f"✅ {self.current_digimon.name} exported as a Reloaded II mod!\n\n"
                f"Mod folder:\n{mod_root}\n\n"
                f"dsts-loader payload:\n{mod_root / 'dsts-loader'}"
                f"{cache_notice}"
            )

    def save_to_dsts_loader(self, digimon: DigimonData, dsts_loader_root: Optional[Path] = None, ask_for_path: bool = True) -> bool:
        """Save Digimon back to a dsts-loader payload, merging with existing data."""
        if not self.validate_field_guide_id():
            return False

        if dsts_loader_root is None and ask_for_path:
            default_path = get_default_mod_loader_path()

            loader_dir = QFileDialog.getExistingDirectory(
                self,
                "Select Reloaded II Mod or dsts-loader Directory to Save To",
                str(get_existing_directory_start(default_path)),
                QFileDialog.Option.ShowDirsOnly
            )

            if not loader_dir:
                return False

            selected_path = Path(loader_dir)
        elif dsts_loader_root is not None:
            selected_path = Path(dsts_loader_root)
        else:
            return False

        # Update form data before saving
        self.update_digimon_from_form()

        output_path = self._resolve_dsts_loader_root(selected_path, allow_create=True)
        if not output_path:
            QMessageBox.warning(self, "Error", "Could not resolve the selected dsts-loader folder.")
            return False

        # Check if destination already has files
        patch_data_dir = output_path / "patch" / "data"
        has_existing = False
        if patch_data_dir.exists():
            status_file = patch_data_dir / "digimon_status.mbe" / "000_digimon_status_data.ap.csv"
            resolved_status_file = self._resolve_prefixed_file(status_file)
            if resolved_status_file.exists():
                has_existing = True

        # Always use merge mode to preserve other Digimon data
        original_identity = dict(getattr(self, "loaded_digimon_identity", {}) or {})
        pending_new = bool(
            original_identity.get("pending_new_mod_entry")
            or getattr(digimon, "pending_new_mod_entry", False)
        )
        merge_identity = {} if pending_new else original_identity
        if self._merge_digimon_to_dsts_loader(output_path, digimon, merge_identity):
            self._set_active_dsts_loader_root(output_path)
            if pending_new:
                digimon.pending_new_mod_entry = False
                self.loaded_digimon_identity = {}
            self._upsert_imported_digimon(digimon, output_path)
            self._remember_loaded_identity(digimon)
            self.clear_modified_flag()
            cache_notice = self._consume_mvgl_cache_notice()
            if has_existing:
                QMessageBox.information(
                    self,
                    "Success! ✅",
                    f"✅ {digimon.name} has been updated in dsts-loader!\n\n"
                    f"Location: {output_path}\n\n"
                    "Other Digimon data was preserved."
                    f"{cache_notice}"
                )
            else:
                QMessageBox.information(
                    self,
                    "Success! ✅",
                    f"✅ {digimon.name} has been saved to dsts-loader format!\n\n"
                    f"Location: {output_path}\n\n"
                    "All .ap.csv files have been created."
                    f"{cache_notice}"
                )
            return True
        else:
            QMessageBox.warning(self, "Error", "Failed to save to dsts-loader format")
            return False

    def save_to_dlc(self, digimon: DigimonData, chr_id_to_reload: str):
        """Save Digimon to DLC files"""
        dlc_exporter = DLCExporter(self.loader)
        animation_ref = self.animation_ref_edit.text().strip() if self.animation_ref_edit.text().strip() else digimon.chr_id

        if dlc_exporter.save_digimon_to_dlc(digimon, animation_ref):
            self.clear_modified_flag()
            QMessageBox.information(
                self,
                "Success! ✅",
                f"✅ {digimon.name} has been saved to DLC!\n\n"
                "The Digimon is now available in DLC files."
            )
            # Invalidate caches
            if hasattr(self.loader, '_invalidate_digimon_status_cache'):
                self.loader._invalidate_digimon_status_cache()
            self.loader._digimon_profiles_cache = None
            if hasattr(self.loader, '_char_names_cache'):
                self.loader._char_names_cache = None

            # Refresh list
            self.load_digimon_list()

            # Reload Digimon
            QApplication.processEvents()
            digimon_reloaded = self.loader.get_digimon_by_chr_id(chr_id_to_reload)
            if digimon_reloaded:
                digimon_reloaded.name = self.loader._get_digimon_name(digimon_reloaded.char_key, check_dlc=True)
                self.load_digimon_data(digimon_reloaded)
        else:
            QMessageBox.warning(self, "Error", "Failed to save to DLC")

    def update_digimon_from_form(self):
        """Update current Digimon with data from form"""
        if not self.current_digimon:
            return

        # Basic Info
        self.current_digimon.id = self.id_spin.value()
        self.current_digimon.char_key = self.char_key_edit.text()
        self.current_digimon.chr_id = self.chr_id_edit.text()
        self.current_digimon.name = self.name_edit.text()
        self.current_digimon.stage_id = self.stage_combo.currentData() if self.stage_combo.currentData() is not None else 0
        self.current_digimon.type_id = self.type_combo.currentData() if self.type_combo.currentData() is not None else 0
        self.current_digimon.generation_id = self.stage_combo.currentData() if self.stage_combo.currentData() is not None else 0  # Generation is the same as stage
        self.current_digimon.personality_id = self.personality_combo.currentData() if self.personality_combo.currentData() is not None else 0
        self.current_digimon.base_personality = self.personality_combo.currentData() if self.personality_combo.currentData() is not None else 0
        self.current_digimon.tribe_name = self.tribe_combo.currentText() if self.tribe_combo.currentText() else "None"

        # Profile text
        self.current_digimon.profile_text = self.profile_text_edit.toPlainText()
        self.collect_multilanguage_text_from_form()

        # Stats
        self.current_digimon.base_hp = self.stat_widgets["hp"].value()
        self.current_digimon.base_sp = self.stat_widgets["sp"].value()
        self.current_digimon.base_atk = self.stat_widgets["atk"].value()
        self.current_digimon.base_def = self.stat_widgets["def"].value()
        self.current_digimon.base_int = self.stat_widgets["int"].value()
        self.current_digimon.base_spi = self.stat_widgets["spi"].value()
        self.current_digimon.base_spd = self.stat_widgets["spd"].value()
        self.current_digimon.growth_pattern_id = self.growth_pattern_combo.currentData() if self.growth_pattern_combo.currentData() is not None else 1

        # Resistances
        self.current_digimon.res_null = self.resist_widgets["null"].value()
        self.current_digimon.res_fire = self.resist_widgets["fire"].value()
        self.current_digimon.res_water = self.resist_widgets["water"].value()
        self.current_digimon.res_ice = self.resist_widgets["ice"].value()
        self.current_digimon.res_grass = self.resist_widgets["grass"].value()
        self.current_digimon.res_wind = self.resist_widgets["wind"].value()
        self.current_digimon.res_elec = self.resist_widgets["elec"].value()
        self.current_digimon.res_ground = self.resist_widgets["ground"].value()
        self.current_digimon.res_steel = self.resist_widgets["steel"].value()
        self.current_digimon.res_light = self.resist_widgets["light"].value()
        self.current_digimon.res_dark = self.resist_widgets["dark"].value()

        # Skills
        self.current_digimon.signature_skills = self.signature_skills_editor.get_skills()
        self.current_digimon.generic_skills = self.generic_skills_editor.get_skills()

        # Traits
        self.current_digimon.traits = self.traits_tab.get_traits()

        # Model data
        self.current_digimon.model_id = self.model_id_edit.text()
        self.current_digimon.motion_id = self.motion_id_edit.text()
        self.current_digimon.animation_ref = self.animation_ref_edit.text().strip()

        # LOD data - FIX: Save LOD distances from widgets
        if not hasattr(self.current_digimon, 'lod_data') or not self.current_digimon.lod_data:
            self.current_digimon.lod_data = {}

        for key, widget in self.lod_widgets.items():
            self.current_digimon.lod_data[key] = widget.value()

        # Model settings (from model_setting.mbe)
        if not hasattr(self.current_digimon, 'model_setting_data') or not self.current_digimon.model_setting_data:
            self.current_digimon.model_setting_data = {}

        # Update parsed fields from UI
        self.current_digimon.model_setting_data['battle_scale'] = self.battle_scale_spin.value()
        self.current_digimon.model_setting_data['menu_scale'] = self.menu_scale_spin.value()
        self.current_digimon.model_setting_data['field_scale'] = self.field_scale_spin.value()
        self.current_digimon.model_setting_data['npc_collision'] = self.npc_collision_spin.value()
        self.current_digimon.model_setting_data['shield_size'] = self.shield_size_spin.value()
        self.current_digimon.model_setting_data['agent_distance'] = self.agent_distance_spin.value()
        self.current_digimon.model_setting_data['agent_distance_2'] = self.agent_distance_2_spin.value()
        self.current_digimon.model_setting_data['digimon_distance_from_agent'] = self.digimon_distance_spin.value()
        self.current_digimon.model_setting_data['camera_distance_skill'] = self.camera_distance_skill_spin.value()
        self.current_digimon.model_setting_data['rideable'] = 1 if self.rideable_checkbox.isChecked() else 0

        # Update raw_data array if it exists
        if 'raw_data' in self.current_digimon.model_setting_data:
            raw_data = self.current_digimon.model_setting_data['raw_data']
            # Update specific columns based on research findings
            if len(raw_data) > 10:
                raw_data[10] = str(self.npc_collision_spin.value())
            if len(raw_data) > 38:
                raw_data[38] = str(self.digimon_distance_spin.value())
            if len(raw_data) > 39:
                raw_data[39] = str(self.agent_distance_2_spin.value())
            if len(raw_data) > 40:
                raw_data[40] = str(self.agent_distance_spin.value())
            if len(raw_data) > 43:
                raw_data[43] = str(self.camera_distance_skill_spin.value())
            if len(raw_data) > 47:
                raw_data[47] = str(self.shield_size_spin.value())
            if len(raw_data) > 56:
                raw_data[56] = str(self.battle_scale_spin.value())
            if len(raw_data) > 58:
                raw_data[58] = str(self.menu_scale_spin.value())
            if len(raw_data) > 59:
                raw_data[59] = str(self.field_scale_spin.value())
            if len(raw_data) > 71:
                raw_data[71] = str(1 if self.rideable_checkbox.isChecked() else 0)

        # Evolution data - FIX: Save evolution paths from evolution tab
        # Note: Evolution paths are managed through add_evolution/remove_evolution methods
        # which directly modify self.current_digimon.evolution_paths and deevolution_sources
        # So they should already be updated, but we ensure the data structure exists
        if not hasattr(self.current_digimon, 'evolution_paths'):
            self.current_digimon.evolution_paths = []
        if not hasattr(self.current_digimon, 'deevolution_sources'):
            self.current_digimon.deevolution_sources = []
        if getattr(self.current_digimon, 'evolution_conditions', None):
            self.current_digimon.evolution_conditions = [
                normalize_evolution_conditions(self.current_digimon.evolution_conditions)
            ]
        elif not hasattr(self.current_digimon, 'evolution_conditions'):
            self.current_digimon.evolution_conditions = []

        # References
        self.current_digimon.field_guide_id = self.field_guide_id_spin.value()
        self.current_digimon.script_id = self.script_id_spin.value()
        normalized_script_id = normalize_status_reference_id(
            self.current_digimon.id,
            self.current_digimon.field_guide_id,
            self.current_digimon.script_id,
        )
        if normalized_script_id != self.current_digimon.script_id:
            self.current_digimon.script_id = normalized_script_id
            self.script_id_spin.blockSignals(True)
            self.script_id_spin.setValue(normalized_script_id)
            self.script_id_spin.blockSignals(False)

    def add_evolution(self, force_jogress: bool = False):
        """Add a new evolution path"""
        if not self.current_digimon:
            return

        # Create dialog to select target Digimon
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Evolution")
        dialog.setMinimumSize(550, 600)
        layout = QVBoxLayout(dialog)

        # Instructions
        info_label = QLabel("Select a Digimon from the list below, or enter a custom Digimon name/ID in the text field.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; padding: 10px; background-color: #f8f9fa; border-radius: 6px;")
        layout.addWidget(info_label)

        path_type_combo = QComboBox()
        path_type_combo.addItem("Normal evolution", EVOLUTION_TYPE_NORMAL)
        path_type_combo.addItem("Jogress / DNA", EVOLUTION_TYPE_NORMAL)
        path_type_combo.addItem("Mode Change path", EVOLUTION_TYPE_MODE_CHANGE)
        if force_jogress:
            path_type_combo.setCurrentIndex(path_type_combo.findText("Jogress / DNA"))
        path_type_combo.setToolTip("Jogress/DNA writes type 0 source edges plus partner requirements in evolution_condition.")
        layout.addWidget(QLabel("Evolution path type:"))
        layout.addWidget(path_type_combo)

        # Tab widget for list selection vs custom input
        tab_widget = QTabWidget()

        # Tab 1: Select from list
        list_tab = QWidget()
        list_layout = QVBoxLayout(list_tab)
        list_layout.addWidget(QLabel("Select target Digimon:"))

        # Search box
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("Search Digimon...")
        list_layout.addWidget(search_edit)

        target_list = QListWidget()
        target_list.setMinimumHeight(300)

        # Populate with official and custom Digimon. Custom mod rows are stored
        # on each list item so the dialog does not need to parse labels.
        picker_entries = self._evolution_picker_entries()
        for entry in picker_entries:
            item = QListWidgetItem(entry["label"])
            item.setData(100, entry)
            target_list.addItem(item)

        # Filter on search
        def filter_digimon(text):
            for i in range(target_list.count()):
                item = target_list.item(i)
                if item:
                    item.setHidden(text.lower() not in item.text().lower())
        search_edit.textChanged.connect(filter_digimon)

        list_layout.addWidget(target_list)
        tab_widget.addTab(list_tab, "Select from List")

        # Tab 2: Custom input
        custom_tab = QWidget()
        custom_layout = QVBoxLayout(custom_tab)

        custom_info = QLabel("Enter a Digimon by name or ID.\nExamples:\n• Digimon Name: 'Agumon'\n• Chr ID: 'chr050'\n• Numeric ID: '50'")
        custom_info.setWordWrap(True)
        custom_info.setStyleSheet("color: #666; padding: 10px; background-color: #e7f5ff; border-radius: 6px;")
        custom_layout.addWidget(custom_info)

        custom_input = QLineEdit()
        custom_input.setPlaceholderText("Enter Digimon name, chr_id (e.g., chr050), or numeric ID")
        custom_layout.addWidget(QLabel("Custom Digimon:"))
        custom_layout.addWidget(custom_input)

        # Also allow custom ID directly
        custom_id_label = QLabel("Or enter numeric ID directly:")
        custom_id_spin = QSpinBox()
        custom_id_spin.setRange(1, 999999)
        custom_id_spin.setValue(1000)
        custom_layout.addWidget(custom_id_label)
        custom_layout.addWidget(custom_id_spin)

        custom_layout.addStretch()
        tab_widget.addTab(custom_tab, "Custom Input")

        layout.addWidget(tab_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            target_digimon_id = None
            target_chr_id = None

            if tab_widget.currentIndex() == 0:
                # List tab selected
                selected_item = target_list.currentItem()
                if selected_item:
                    entry = selected_item.data(100)
                    if entry:
                        target_digimon_id = entry.get("id")
                        target_chr_id = entry.get("chr_id")
            else:
                # Custom tab selected
                custom_text = custom_input.text().strip()
                found = False
                if custom_text:
                    picker_entry = self._find_evolution_picker_entry(custom_text, picker_entries)
                    if picker_entry:
                        target_chr_id = picker_entry["chr_id"]
                        target_digimon_id = picker_entry["id"]
                        found = True

                    # First check imported Digimon (custom Digimon from dsts-loader)
                    if not found and hasattr(self.loader, 'imported_digimon') and self.loader.imported_digimon:
                        for imported_digimon in self.loader.imported_digimon:
                            # Check by name (case-insensitive partial match)
                            if custom_text.lower() in imported_digimon.name.lower():
                                target_chr_id = imported_digimon.chr_id
                                target_digimon_id = imported_digimon.id
                                found = True
                                break
                            # Check by chr_id (exact match)
                            if imported_digimon.chr_id.lower() == custom_text.lower():
                                target_chr_id = imported_digimon.chr_id
                                target_digimon_id = imported_digimon.id
                                found = True
                                break
                            # Check by numeric ID
                            if str(imported_digimon.id) == custom_text:
                                target_chr_id = imported_digimon.chr_id
                                target_digimon_id = imported_digimon.id
                                found = True
                                break

                    # If not found in imported, try standard lookup
                    if not target_digimon_id:
                        # Try to find by name first
                        chr_ids_all = self.loader.get_all_digimon_chr_ids()
                        found = False
                        for chr_id in chr_ids_all:
                            name = self.loader._get_digimon_name_by_chr_id(chr_id)
                            if name and custom_text.lower() in name.lower():
                                target_chr_id = chr_id
                                target_digimon = self.loader.get_digimon_by_chr_id(chr_id)
                                if target_digimon:
                                    target_digimon_id = target_digimon.id
                                    found = True
                                    break

                        # If not found by name, try as chr_id
                        if not found and (custom_text.startswith('chr') or custom_text.startswith('CHR')):
                            target_chr_id = custom_text.lower().replace('chr', 'chr')
                            target_digimon = self.loader.get_digimon_by_chr_id(target_chr_id)
                            if target_digimon:
                                target_digimon_id = target_digimon.id

                        # If still not found, try as numeric ID
                        if not found and custom_text.isdigit():
                            target_digimon_id = int(custom_text)
                            # Try to find chr_id from ID
                            try:
                                status_file = self.loader._resolve_prefixed_file(self.loader.data_path / "digimon_status.mbe" / "000_digimon_status_data.csv")
                                if status_file.exists():
                                    rows = self.loader.load_csv(status_file)
                                    for row in rows[1:]:
                                        if len(row) > 0 and row[0] == str(target_digimon_id):
                                            if len(row) > 3:
                                                target_chr_id = row[3].strip('"')
                                                break
                            except:
                                pass

                # If custom input didn't work, use spinbox value
                if not target_digimon_id:
                    target_digimon_id = custom_id_spin.value()
                    # Generate chr_id from numeric ID
                    target_chr_id = f"chr{target_digimon_id:03d}"

            # Add evolution if we have an ID
            if target_digimon_id:
                # Check if evolution already exists
                existing = False
                for evo in self.current_digimon.evolution_paths:
                    if evo.get('to_id') == target_digimon_id:
                        existing = True
                        break

                if existing:
                    QMessageBox.warning(self, "Already Exists", f"Evolution to Digimon ID {target_digimon_id} already exists!")
                    return

                selected_evolution_type = safe_evolution_int(path_type_combo.currentData(), EVOLUTION_TYPE_NORMAL)
                new_conditions = {}
                export_conditions = False
                export_partner_rows = False
                if self._path_type_combo_is_jogress(path_type_combo):
                    default_conditions = self._find_evolution_conditions_for_target(target_digimon_id)
                    default_conditions = self._prefill_jogress_partner(default_conditions, self.current_digimon.id)
                    display_name = target_chr_id if target_chr_id else f"ID {target_digimon_id}"
                    new_conditions = self._show_evolution_requirements_dialog(
                        f"{display_name} (Jogress/DNA target)",
                        default_conditions
                    )
                    if new_conditions is None:
                        return
                    new_conditions = normalize_evolution_conditions(new_conditions)
                    if not self._validate_jogress_conditions(
                        new_conditions,
                        self.current_digimon.id,
                        "Jogress / DNA Evolution"
                    ):
                        return
                    for partner_id in jogress_partner_ids_from_conditions(new_conditions):
                        partner_targets = self._evolution_targets_for_digimon(partner_id)
                        if str(target_digimon_id) not in partner_targets and len(partner_targets) >= 6:
                            partner_name = self.loader._get_digimon_name_by_id(partner_id) or f"ID {partner_id}"
                            QMessageBox.warning(
                                self,
                                "Evolution Limit Reached",
                                f"Cannot add Jogress/DNA partner {partner_name}.\n\n"
                                f"That Digimon already has 6 evolution targets."
                            )
                            return
                    selected_evolution_type = EVOLUTION_TYPE_NORMAL
                    export_conditions = True
                    export_partner_rows = True

                # Add to evolution paths
                new_evo = {
                    'evolution_id': 0,  # Will be assigned when saved
                    'from_id': self.current_digimon.id,
                    'to_id': target_digimon_id,
                    'to_chr_id': target_chr_id,  # Store chr_id for reference
                    'evolution_type': selected_evolution_type,
                    'condition_flags': ['0', '-1', '-1', '-1', '-1', '-1'],
                    'raw_data': []
                }
                if new_conditions:
                    new_evo['conditions'] = new_conditions
                    new_evo['export_conditions'] = export_conditions
                    new_evo['export_partner_rows'] = export_partner_rows
                self.current_digimon.evolution_paths.append(new_evo)

                # Refresh the evolution tab
                self.update_evolution_tab(self.current_digimon)
                self.mark_as_modified()
                display_name = target_chr_id if target_chr_id else f"ID {target_digimon_id}"
                QMessageBox.information(self, "Success", f"Added evolution to {display_name}")
            else:
                QMessageBox.warning(self, "Invalid Input", "Could not find or parse the Digimon. Please check your input.")

    def _show_evolution_requirements_dialog(self, target_name: str, existing_conditions: dict = None):
        """Show comprehensive dialog to configure evolution requirements"""
        existing_conditions = normalize_evolution_conditions(existing_conditions or {})

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Evolution Requirements → {target_name}")
        dialog.setMinimumWidth(500)

        layout = QVBoxLayout(dialog)

        # Scroll area for all fields
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # Info label
        info = QLabel("Configure the requirements needed to evolve to this Digimon.\nLeave values at 0 for no requirement.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; padding: 8px; background: #f0f0f0; border-radius: 4px; margin-bottom: 10px;")
        scroll_layout.addWidget(info)

        # Agent Rank (column 2 in evolution_condition.csv)
        mode_group = QGroupBox("Agent Rank Requirement")
        mode_layout = QVBoxLayout()
        mode_combo = QComboBox()
        mode_combo.addItem("Rank 1", 1)
        mode_combo.addItem("Rank 2", 2)
        mode_combo.addItem("Rank 3", 3)
        mode_combo.addItem("Rank 4", 4)
        mode_combo.addItem("Rank 5", 5)
        mode_combo.addItem("Rank 6", 6)
        mode_combo.addItem("Rank 7", 7)
        mode_combo.addItem("Rank 8", 8)
        mode_combo.addItem("Rank 9", 9)
        mode_combo.addItem("Rank 10", 10)
        # Set existing rank
        existing_mode = existing_conditions.get('mode', 1)
        mode_combo.setCurrentIndex(mode_combo.findData(existing_mode) if mode_combo.findData(existing_mode) >= 0 else 0)
        mode_layout.addWidget(mode_combo)
        mode_group.setLayout(mode_layout)
        scroll_layout.addWidget(mode_group)

        # Tamer Level
        tamer_group = QGroupBox("Tamer Requirements")
        tamer_layout = QFormLayout()
        tamer_level_spin = QSpinBox()
        tamer_level_spin.setRange(0, 99)
        tamer_level_spin.setValue(existing_conditions.get('tamerLevel', 0))
        tamer_level_spin.setSuffix(" (0 = no requirement)")
        tamer_layout.addRow("Tamer Level:", tamer_level_spin)
        tamer_group.setLayout(tamer_layout)
        scroll_layout.addWidget(tamer_group)

        # Stat Requirements
        stats_group = QGroupBox("Stat Requirements")
        stats_layout = QFormLayout()

        hp_spin = QSpinBox()
        hp_spin.setRange(0, 99999)
        hp_spin.setValue(existing_conditions.get('HP', 0))
        hp_spin.setSuffix(" HP")
        stats_layout.addRow("HP:", hp_spin)

        sp_spin = QSpinBox()
        sp_spin.setRange(0, 99999)
        sp_spin.setValue(existing_conditions.get('SP', 0))
        sp_spin.setSuffix(" SP")
        stats_layout.addRow("SP:", sp_spin)

        atk_spin = QSpinBox()
        atk_spin.setRange(0, 9999)
        atk_spin.setValue(existing_conditions.get('ATK', 0))
        atk_spin.setSuffix(" ATK")
        stats_layout.addRow("ATK:", atk_spin)

        def_spin = QSpinBox()
        def_spin.setRange(0, 9999)
        def_spin.setValue(existing_conditions.get('DEF', 0))
        def_spin.setSuffix(" DEF")
        stats_layout.addRow("DEF:", def_spin)

        int_spin = QSpinBox()
        int_spin.setRange(0, 9999)
        int_spin.setValue(existing_conditions.get('INT', 0))
        int_spin.setSuffix(" INT")
        stats_layout.addRow("INT:", int_spin)

        spi_spin = QSpinBox()
        spi_spin.setRange(0, 9999)
        spi_spin.setValue(existing_conditions.get('SPI', 0))
        spi_spin.setSuffix(" SPI")
        stats_layout.addRow("SPI:", spi_spin)

        spd_spin = QSpinBox()
        spd_spin.setRange(0, 9999)
        spd_spin.setValue(existing_conditions.get('SPD', 0))
        spd_spin.setSuffix(" SPD")
        stats_layout.addRow("SPD:", spd_spin)

        stats_group.setLayout(stats_layout)
        scroll_layout.addWidget(stats_group)

        # Extra requirement fields observed in evolution_condition columns 11/12.
        extra_group = QGroupBox("Extra Requirement Fields")
        extra_layout = QFormLayout()

        extra_011_spin = QSpinBox()
        extra_011_spin.setRange(0, 9999)
        extra_011_spin.setValue(existing_conditions.get('unknown1', 0))
        extra_011_spin.setToolTip(
            "evolution_condition column 11. Official data only uses this on Lucemon (30) and Parallelmon (40); all known Jogress rows use 0."
        )
        extra_layout.addRow("Column 11:", extra_011_spin)

        extra_012_spin = QSpinBox()
        extra_012_spin.setRange(0, 9999)
        extra_012_spin.setValue(existing_conditions.get('unknown2', 0))
        extra_012_spin.setToolTip(
            "evolution_condition column 12. No nonzero official Base/DLC rows were found in the local data scan."
        )
        extra_layout.addRow("Column 12:", extra_012_spin)

        extra_group.setLayout(extra_layout)
        scroll_layout.addWidget(extra_group)

        # Skill Count Requirements
        skills_group = QGroupBox("Skill Count Requirements (by Personality)")
        skills_layout = QFormLayout()

        valor_spin = QSpinBox()
        valor_spin.setRange(0, 999)
        valor_spin.setValue(existing_conditions.get('skillCountValor', 0))
        skills_layout.addRow("Valor Skills:", valor_spin)

        philanthropy_spin = QSpinBox()
        philanthropy_spin.setRange(0, 999)
        philanthropy_spin.setValue(existing_conditions.get('skillCountPhilantropy', 0))
        skills_layout.addRow("Philanthropy Skills:", philanthropy_spin)

        amicable_spin = QSpinBox()
        amicable_spin.setRange(0, 999)
        amicable_spin.setValue(existing_conditions.get('skillCountAmicable', 0))
        skills_layout.addRow("Amicable Skills:", amicable_spin)

        wisdom_spin = QSpinBox()
        wisdom_spin.setRange(0, 999)
        wisdom_spin.setValue(existing_conditions.get('skillCountWisdom', 0))
        skills_layout.addRow("Wisdom Skills:", wisdom_spin)

        skills_group.setLayout(skills_layout)
        scroll_layout.addWidget(skills_group)

        # Item Requirement
        item_group = QGroupBox("Item Requirement (Mode 2)")
        item_layout = QFormLayout()
        item_spin = QSpinBox()
        item_spin.setRange(0, 999999)
        item_spin.setValue(existing_conditions.get('needsItem', 0))
        item_spin.setSuffix(" (Item ID, 0 = none)")
        item_layout.addRow("Required Item:", item_spin)
        item_group.setLayout(item_layout)
        scroll_layout.addWidget(item_group)

        # Jogress Requirements
        jogress_group = QGroupBox("Jogress/DNA Digivolution Requirements")
        jogress_layout = QFormLayout()

        jogress_a_id_spin = QSpinBox()
        jogress_a_id_spin.setRange(0, 999999)
        jogress_a_id_spin.setValue(existing_conditions.get('jogressDbIdA', 0))
        jogress_a_id_spin.setSuffix(" (Partner A ID)")
        jogress_layout.addRow("Partner A Digimon ID:", jogress_a_id_spin)

        jogress_a_personality_spin = QSpinBox()
        jogress_a_personality_spin.setRange(0, 99)
        jogress_a_personality_spin.setValue(existing_conditions.get('jogressPersonalityA', 0))
        jogress_a_personality_spin.setSuffix(" (Personality)")
        jogress_layout.addRow("Partner A Personality:", jogress_a_personality_spin)

        jogress_b_id_spin = QSpinBox()
        jogress_b_id_spin.setRange(0, 999999)
        jogress_b_id_spin.setValue(existing_conditions.get('jogressDbIdB', 0))
        jogress_b_id_spin.setSuffix(" (Partner B ID)")
        jogress_layout.addRow("Partner B Digimon ID:", jogress_b_id_spin)

        jogress_b_personality_spin = QSpinBox()
        jogress_b_personality_spin.setRange(0, 99)
        jogress_b_personality_spin.setValue(existing_conditions.get('jogressPersonalityB', 0))
        jogress_b_personality_spin.setSuffix(" (Personality)")
        jogress_layout.addRow("Partner B Personality:", jogress_b_personality_spin)

        jogress_group.setLayout(jogress_layout)
        scroll_layout.addWidget(jogress_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return {
                'mode': mode_combo.currentData(),
                'tamerLevel': tamer_level_spin.value(),
                'HP': hp_spin.value(),
                'SP': sp_spin.value(),
                'ATK': atk_spin.value(),
                'DEF': def_spin.value(),
                'INT': int_spin.value(),
                'SPI': spi_spin.value(),
                'SPD': spd_spin.value(),
                'unknown1': extra_011_spin.value(),
                'unknown2': extra_012_spin.value(),
                'skillCountValor': valor_spin.value(),
                'skillCountPhilantropy': philanthropy_spin.value(),
                'skillCountAmicable': amicable_spin.value(),
                'skillCountWisdom': wisdom_spin.value(),
                'needsItem': item_spin.value(),
                'jogressDbIdA': jogress_a_id_spin.value(),
                'jogressPersonalityA': jogress_a_personality_spin.value(),
                'jogressDbIdB': jogress_b_id_spin.value(),
                'jogressPersonalityB': jogress_b_personality_spin.value()
            }
        return None  # Cancelled

    def _format_requirements_summary(self, conditions: dict) -> str:
        """Format evolution requirements as a short summary"""
        parts = []
        if conditions.get('tamerLevel', 0) > 0:
            parts.append(f"Tamer Lv{conditions['tamerLevel']}")

        stats = []
        for stat in ['HP', 'SP', 'ATK', 'DEF', 'INT', 'SPI', 'SPD']:
            if conditions.get(stat, 0) > 0:
                stats.append(f"{stat}{conditions[stat]}")
        if stats:
            parts.append(", ".join(stats))

        if conditions.get('needsItem', 0) > 0:
            parts.append(f"Item#{conditions['needsItem']}")

        extras = []
        if conditions.get('unknown1', 0) > 0:
            extras.append(f"Col11 {conditions['unknown1']}")
        if conditions.get('unknown2', 0) > 0:
            extras.append(f"Col12 {conditions['unknown2']}")
        if extras:
            parts.append(", ".join(extras))

        jogress_partners = jogress_partner_ids_from_conditions(normalize_evolution_conditions(conditions))
        if jogress_partners:
            parts.append(f"Jogress {' + '.join(f'ID{partner_id}' for partner_id in jogress_partners)}")

        if parts:
            return f"[{'; '.join(parts)}]"
        return "[No requirements]"

    def edit_evolution(self):
        """Edit selected evolution path with detailed requirements editor"""
        if not self.current_digimon:
            return

        current_index = self._selected_path_index(
            ("evolution_list", "evolution_jogress_list", "evolution_mode_change_list")
        )
        if current_index is None:
            QMessageBox.warning(self, "Warning", "Please select an evolution to edit")
            return

        if current_index >= len(self.current_digimon.evolution_paths):
            return

        evo = self.current_digimon.evolution_paths[current_index]

        # Get target Digimon name
        to_id = evo['to_id']
        to_name = self.loader._get_digimon_name_by_id(to_id)
        if not to_name:
            to_name = f"ID {to_id}"

        # Get existing conditions or create default
        existing_conditions = evo.get('conditions', {})

        # Use the same comprehensive dialog as the wizard
        new_conditions = self._show_evolution_requirements_dialog(to_name, existing_conditions)

        if new_conditions is not None:
            new_conditions = normalize_evolution_conditions(new_conditions)
            if evolution_conditions_have_jogress(new_conditions):
                if not self._validate_jogress_conditions(
                    new_conditions,
                    self.current_digimon.id,
                    "Jogress / DNA Evolution"
                ):
                    return
                for partner_id in jogress_partner_ids_from_conditions(new_conditions):
                    partner_targets = self._evolution_targets_for_digimon(partner_id)
                    if str(to_id) not in partner_targets and len(partner_targets) >= 6:
                        partner_name = self.loader._get_digimon_name_by_id(partner_id) or f"ID {partner_id}"
                        QMessageBox.warning(
                            self,
                            "Evolution Limit Reached",
                            f"Cannot add Jogress/DNA partner {partner_name}.\n\n"
                            f"That Digimon already has 6 evolution targets."
                        )
                        return
            # Update the evolution path with new conditions
            self.current_digimon.evolution_paths[current_index]['conditions'] = new_conditions
            self.current_digimon.evolution_paths[current_index]['export_conditions'] = True
            if evolution_conditions_have_jogress(new_conditions):
                self.current_digimon.evolution_paths[current_index]['evolution_type'] = EVOLUTION_TYPE_NORMAL
                self.current_digimon.evolution_paths[current_index]['export_partner_rows'] = True
            else:
                self.current_digimon.evolution_paths[current_index].pop('export_partner_rows', None)

            # Update display
            self.update_evolution_tab(self.current_digimon)

            self.mark_as_modified()
            QMessageBox.information(self, "Success", f"Evolution requirements updated for {to_name}")

    # Old evolution dialog has been replaced with _show_evolution_requirements_dialog

    def remove_evolution(self):
        """Remove selected evolution path"""
        if not self.current_digimon:
            return

        current_index = self._selected_path_index(
            ("evolution_list", "evolution_jogress_list", "evolution_mode_change_list")
        )
        if current_index is None:
            QMessageBox.warning(self, "Warning", "Please select an evolution to remove")
            return

        if current_index < len(self.current_digimon.evolution_paths):
            evo = self.current_digimon.evolution_paths[current_index]
            reply = QMessageBox.question(self, "Confirm",
                                         f"Remove evolution to ID {evo['to_id']}?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.current_digimon.evolution_paths.pop(current_index)
                self.update_evolution_tab(self.current_digimon)
                self.mark_as_modified()
                QMessageBox.information(self, "Success", "Evolution removed")

    def _build_evolution_target_map(self) -> Dict[int, Set[str]]:
        """Build source Digimon ID -> unique target IDs from saved evolution files."""
        if self._evolution_target_map_cache is not None:
            return self._evolution_target_map_cache

        target_map: Dict[int, Set[str]] = {}

        def add_targets_from_file(evolution_to_file: Path):
            if not evolution_to_file.exists():
                return
            rows = self.loader.load_csv(evolution_to_file)
            for row in rows[1:]:
                if len(row) <= 3:
                    continue
                source_id = _parse_optional_int(self._csv_cell(row, 1))
                target_id = self._csv_cell(row, 3)
                if source_id is not None and target_id:
                    target_map.setdefault(source_id, set()).add(target_id)

        try:
            # Check base game evolution_to.csv
            evolution_to_file = self.loader._resolve_prefixed_file(self.loader.data_path / "evolution.mbe" / "001_evolution_to.csv")
            add_targets_from_file(evolution_to_file)

            # Also check DLC files
            for _dlc_id, dlc_path in self.loader.iter_dlc_csv_files("data", "evolution", "001_evolution_to.csv"):
                add_targets_from_file(dlc_path)

            # Include every Reloaded II mod payload so occupied slots are visible
            # even before importing a specific mod into the current editor session.
            for mod_root, _source_label in self._iter_reloaded_mod_dsts_loader_roots():
                for mod_evolution_file in self._dsts_loader_evolution_files(mod_root):
                    add_targets_from_file(mod_evolution_file)
        except Exception as e:
            print(f"Error counting evolutions: {e}")

        self._evolution_target_map_cache = target_map
        return target_map

    def _pending_evolution_targets_for_source(self, digimon_id: int) -> Set[str]:
        """Return unsaved target IDs that would consume slots for a source Digimon."""
        targets: Set[str] = set()
        digimon_id = safe_evolution_int(digimon_id, 0)
        if digimon_id <= 0 or not self.current_digimon:
            return targets

        current_id = safe_evolution_int(getattr(self.current_digimon, "id", 0), 0)
        for evo in getattr(self.current_digimon, "evolution_paths", []):
            target_id = evo.get('to_id')
            if not target_id:
                continue

            if current_id == digimon_id:
                targets.add(str(target_id))

            if evo.get('export_partner_rows'):
                partner_ids = jogress_partner_ids_from_conditions(evo.get('conditions', {}))
                if digimon_id in partner_ids:
                    targets.add(str(target_id))

        for deevo in getattr(self.current_digimon, "deevolution_sources", []):
            if safe_evolution_int(deevo.get('from_id'), 0) == digimon_id and current_id > 0:
                targets.add(str(current_id))

        return targets

    def _evolution_targets_for_digimon(self, digimon_id: int) -> Set[str]:
        """Count saved and pending evolution targets for slot-limit checks."""
        digimon_id = safe_evolution_int(digimon_id, 0)
        targets = set(self._build_evolution_target_map().get(digimon_id, set()))
        targets.update(self._pending_evolution_targets_for_source(digimon_id))
        return targets

    def get_evolution_count_for_digimon(self, digimon_id: int) -> int:
        """Count unique evolution targets from base, DLC, Reloaded II mods, and pending edits."""
        return len(self._evolution_targets_for_digimon(digimon_id))

    def add_pre_evolution(self, force_jogress: bool = False):
        """Add a pre-evolution (a Digimon that evolves INTO this one)"""
        if not self.current_digimon:
            QMessageBox.warning(self, "Warning", "Please select a Digimon first")
            return

        # Create dialog to select source Digimon
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Pre-Evolution")
        dialog.setMinimumSize(550, 550)
        layout = QVBoxLayout(dialog)

        # Info banner
        info_banner = QLabel(
            "⚠️ Adding a pre-evolution creates an evolution entry where THAT Digimon evolves into THIS one.\n"
            "Each Digimon can only have 6 evolution targets maximum. Base, DLC, and Reloaded II mod rows are counted."
        )
        info_banner.setStyleSheet("background-color: #fff3cd; padding: 10px; border-radius: 6px; color: #856404;")
        info_banner.setWordWrap(True)
        layout.addWidget(info_banner)

        path_type_combo = QComboBox()
        path_type_combo.addItem("Normal evolution", EVOLUTION_TYPE_NORMAL)
        path_type_combo.addItem("Jogress / DNA", EVOLUTION_TYPE_NORMAL)
        path_type_combo.addItem("Mode Change path", EVOLUTION_TYPE_MODE_CHANGE)
        if force_jogress:
            path_type_combo.setCurrentIndex(path_type_combo.findText("Jogress / DNA"))
        path_type_combo.setToolTip("Jogress/DNA writes type 0 source edges plus partner requirements for this target.")
        layout.addWidget(QLabel("Incoming path type:"))
        layout.addWidget(path_type_combo)

        # Tab widget for list selection vs custom input
        tab_widget = QTabWidget()

        # Tab 1: Select from list
        list_tab = QWidget()
        list_layout = QVBoxLayout(list_tab)

        # Search
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("Search Digimon...")
        list_layout.addWidget(search_edit)

        # Evolution count label
        evo_count_label = QLabel("Select a Digimon to see their evolution slot count")
        evo_count_label.setStyleSheet("padding: 5px; font-style: italic; color: #666;")
        list_layout.addWidget(evo_count_label)

        list_layout.addWidget(QLabel("Select Digimon to add as pre-evolution:"))
        source_list = QListWidget()
        source_list.setMinimumHeight(300)
        list_layout.addWidget(source_list)
        tab_widget.addTab(list_tab, "Select from List")

        # Tab 2: Custom input
        custom_tab = QWidget()
        custom_layout = QVBoxLayout(custom_tab)

        custom_info = QLabel("Enter a Digimon by name or ID.\nExamples:\n• Digimon Name: 'Agumon'\n• Chr ID: 'chr050'\n• Numeric ID: '50'")
        custom_info.setWordWrap(True)
        custom_info.setStyleSheet("color: #666; padding: 10px; background-color: #e7f5ff; border-radius: 6px;")
        custom_layout.addWidget(custom_info)

        custom_input = QLineEdit()
        custom_input.setPlaceholderText("Enter Digimon name, chr_id (e.g., chr050), or numeric ID")
        custom_layout.addWidget(QLabel("Custom Digimon:"))
        custom_layout.addWidget(custom_input)

        # Also allow custom ID directly
        custom_id_label = QLabel("Or enter numeric ID directly:")
        custom_id_spin = QSpinBox()
        custom_id_spin.setRange(1, 999999)
        custom_id_spin.setValue(1000)
        custom_layout.addWidget(custom_id_label)
        custom_layout.addWidget(custom_id_spin)

        custom_layout.addStretch()
        tab_widget.addTab(custom_tab, "Custom Input")

        # Populate with official and custom Digimon. This mirrors Add Evolution
        # so active Reloaded II mod entries can also be selected as sources.
        picker_entries = self._evolution_picker_entries()
        for entry in picker_entries:
            digimon_id = entry["id"]
            chr_id = entry["chr_id"]
            name = entry["name"]
            evo_count = self.get_evolution_count_for_digimon(digimon_id)

            if evo_count >= 6:
                status = "❌ FULL"
            elif evo_count >= 5:
                status = f"⚠️ {evo_count}/6"
            else:
                status = f"✅ {evo_count}/6"

            item = QListWidgetItem(f"{name} [{status}] ({chr_id}) - ID: {digimon_id} [{entry['source']}]")
            item.setData(100, {'id': digimon_id, 'chr_id': chr_id, 'evo_count': evo_count, 'source': entry['source']})

            if evo_count >= 6:
                item.setForeground(Qt.GlobalColor.red)
            elif evo_count >= 5:
                item.setForeground(Qt.GlobalColor.darkYellow)

            source_list.addItem(item)

        # Update count on selection
        def update_evo_count():
            current = source_list.currentItem()
            if current:
                data = current.data(100)
                if data:
                    count = data.get('evo_count', 0)
                    status = "✅ Can add" if count < 6 else "❌ FULL - Cannot add!"
                    color = "#28a745" if count < 6 else "#dc3545"
                    evo_count_label.setText(f"Evolution slots: {count}/6 — {status} (base/DLC/mods)")
                    evo_count_label.setStyleSheet(f"padding: 5px; font-weight: bold; color: {color};")

        source_list.currentItemChanged.connect(lambda: update_evo_count())

        # Filter
        def filter_list(text):
            for i in range(source_list.count()):
                item = source_list.item(i)
                item.setHidden(text.lower() not in item.text().lower())
        search_edit.textChanged.connect(filter_list)

        layout.addWidget(tab_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            from_id = None
            from_chr_id = None
            evo_count = 0

            if tab_widget.currentIndex() == 0:
                # List tab selected
                current = source_list.currentItem()
                if current:
                    data = current.data(100)
                    if data:
                        from_id = data.get('id', 0)
                        from_chr_id = data.get('chr_id', '')
                        evo_count = data.get('evo_count', 0)
            else:
                # Custom tab selected
                custom_text = custom_input.text().strip()
                found = False
                if custom_text:
                    picker_entry = self._find_evolution_picker_entry(custom_text, picker_entries)
                    if picker_entry:
                        from_chr_id = picker_entry["chr_id"]
                        from_id = picker_entry["id"]
                        evo_count = self.get_evolution_count_for_digimon(from_id)
                        found = True

                    # First check imported Digimon (custom Digimon from dsts-loader)
                    if not found and hasattr(self.loader, 'imported_digimon') and self.loader.imported_digimon:
                        for imported_digimon in self.loader.imported_digimon:
                            # Check by name (case-insensitive partial match)
                            if custom_text.lower() in imported_digimon.name.lower():
                                from_chr_id = imported_digimon.chr_id
                                from_id = imported_digimon.id
                                evo_count = self.get_evolution_count_for_digimon(from_id)
                                found = True
                                break
                            # Check by chr_id (exact match)
                            if imported_digimon.chr_id.lower() == custom_text.lower():
                                from_chr_id = imported_digimon.chr_id
                                from_id = imported_digimon.id
                                evo_count = self.get_evolution_count_for_digimon(from_id)
                                found = True
                                break
                            # Check by numeric ID
                            if str(imported_digimon.id) == custom_text:
                                from_chr_id = imported_digimon.chr_id
                                from_id = imported_digimon.id
                                evo_count = self.get_evolution_count_for_digimon(from_id)
                                found = True
                                break

                    # If not found in imported, try standard lookup
                    if not from_id:
                        # Try to find by name first
                        chr_ids_all = self.loader.get_all_digimon_chr_ids()
                        found = False
                        for chr_id in chr_ids_all:
                            name = self.loader._get_digimon_name_by_chr_id(chr_id)
                            if name and custom_text.lower() in name.lower():
                                from_chr_id = chr_id
                                digimon_obj = self.loader.get_digimon_by_chr_id(chr_id)
                                if digimon_obj:
                                    from_id = digimon_obj.id
                                    # Check evolution count
                                    evo_count = self.get_evolution_count_for_digimon(from_id)
                                    found = True
                                    break

                        # If not found by name, try as chr_id
                        if not found and (custom_text.startswith('chr') or custom_text.startswith('CHR')):
                            from_chr_id = custom_text.lower().replace('chr', 'chr')
                            digimon_obj = self.loader.get_digimon_by_chr_id(from_chr_id)
                            if digimon_obj:
                                from_id = digimon_obj.id
                                evo_count = self.get_evolution_count_for_digimon(from_id)

                        # If still not found, try as numeric ID
                        if not found and custom_text.isdigit():
                            from_id = int(custom_text)
                            # Try to find chr_id from ID
                            try:
                                status_file = self.loader._resolve_prefixed_file(self.loader.data_path / "digimon_status.mbe" / "000_digimon_status_data.csv")
                                if status_file.exists():
                                    rows = self.loader.load_csv(status_file)
                                    for row in rows[1:]:
                                        if len(row) > 0 and row[0] == str(from_id):
                                            if len(row) > 3:
                                                from_chr_id = row[3].strip('"')
                                                break
                            except:
                                pass
                            if from_id:
                                evo_count = self.get_evolution_count_for_digimon(from_id)

                # If custom input didn't work, use spinbox value
                if not from_id:
                    from_id = custom_id_spin.value()
                    # Generate chr_id from numeric ID
                    from_chr_id = f"chr{from_id:03d}"
                    evo_count = self.get_evolution_count_for_digimon(from_id)

            if from_id:
                selected_evolution_type = safe_evolution_int(path_type_combo.currentData(), EVOLUTION_TYPE_NORMAL)

                if self._path_type_combo_is_jogress(path_type_combo):
                    default_conditions = normalize_evolution_conditions(self.current_digimon.evolution_conditions)
                    default_conditions = self._prefill_jogress_partner(default_conditions, from_id)
                    new_conditions = self._show_evolution_requirements_dialog(
                        f"{self.current_digimon.name} (Jogress/DNA target)",
                        default_conditions
                    )
                    if new_conditions is None:
                        return
                    new_conditions = normalize_evolution_conditions(new_conditions)
                    if not self._validate_jogress_conditions(
                        new_conditions,
                        from_id,
                        "Jogress / DNA Pre-Evolution"
                    ):
                        return

                    partner_ids = jogress_partner_ids_from_conditions(new_conditions)
                    if self.current_digimon.id in partner_ids:
                        QMessageBox.warning(
                            self,
                            "Jogress / DNA Pre-Evolution",
                            "The target Digimon cannot also be one of its own Jogress/DNA source partners."
                        )
                        return

                    partners_to_add = []
                    for partner_id in partner_ids:
                        existing = any(
                            safe_evolution_int(deevo.get('from_id'), 0) == partner_id
                            for deevo in self.current_digimon.deevolution_sources
                        )
                        if not existing and self.get_evolution_count_for_digimon(partner_id) >= 6:
                            partner_name = self.loader._get_digimon_name_by_id(partner_id) or f"ID {partner_id}"
                            QMessageBox.warning(
                                self,
                                "Evolution Limit Reached",
                                f"Cannot add Jogress/DNA partner {partner_name}.\n\n"
                                f"That Digimon already has 6 evolution targets."
                            )
                            return
                        partner_chr_id = from_chr_id if partner_id == from_id else self._chr_id_for_digimon_id(partner_id)
                        partners_to_add.append((partner_id, partner_chr_id))

                    for partner_id, partner_chr_id in partners_to_add:
                        self._ensure_deevolution_source(partner_id, partner_chr_id, EVOLUTION_TYPE_NORMAL)

                    self._set_current_evolution_conditions(new_conditions)
                    self.update_evolution_tab(self.current_digimon)
                    self.mark_as_modified()
                    partner_text = " + ".join(str(partner_id) for partner_id, _chr_id in partners_to_add)
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Jogress/DNA pre-evolution added: {partner_text} -> {self.current_digimon.name}"
                    )
                    return

                # Check limit
                if evo_count >= 6:
                    from_name = self.loader._get_digimon_name_by_id(from_id) or f"ID {from_id}"
                    QMessageBox.warning(
                        self,
                        "Evolution Limit Reached",
                        f"❌ Cannot add pre-evolution!\n\n"
                        f"{from_name} already has 6 evolution targets.\n"
                        f"Choose a different Digimon with available slots."
                    )
                    return

                # Check if already exists
                for deevo in self.current_digimon.deevolution_sources:
                    if deevo.get('from_id') == from_id:
                        QMessageBox.information(self, "Already Added", "This pre-evolution already exists.")
                        return

                # Add pre-evolution
                self.current_digimon.deevolution_sources.append({
                    'from_id': from_id,
                    'from_chr_id': from_chr_id or f"chr{from_id:03d}",
                    'evolution_type': selected_evolution_type
                })

                self.update_evolution_tab(self.current_digimon)
                self.mark_as_modified()
                display_name = from_chr_id if from_chr_id else f"ID {from_id}"
                QMessageBox.information(self, "Success", f"Pre-evolution added! {display_name} now evolves into {self.current_digimon.name}")
            else:
                QMessageBox.warning(self, "Invalid Input", "Could not find or parse the Digimon. Please check your input.")

    def remove_pre_evolution(self):
        """Remove selected pre-evolution"""
        if not self.current_digimon:
            return

        current_index = self._selected_path_index(
            ("deevolution_list", "deevolution_jogress_list", "deevolution_mode_change_list")
        )
        if current_index is None:
            QMessageBox.warning(self, "Warning", "Please select a pre-evolution to remove")
            return

        if current_index < len(self.current_digimon.deevolution_sources):
            deevo = self.current_digimon.deevolution_sources[current_index]
            from_id = deevo.get('from_id', 0)
            from_name = self.loader._get_digimon_name_by_id(from_id) or f"ID {from_id}"
            target_conditions = normalize_evolution_conditions(self.current_digimon.evolution_conditions)
            jogress_partner_ids = jogress_partner_ids_from_conditions(target_conditions)
            remove_jogress_group = safe_evolution_int(from_id, 0) in jogress_partner_ids

            confirm_text = (
                f"Remove pre-evolution from {from_name}?\n\n"
                f"This means {from_name} will no longer evolve into {self.current_digimon.name}."
            )
            if remove_jogress_group:
                partner_text = " + ".join(str(partner_id) for partner_id in jogress_partner_ids)
                confirm_text = (
                    f"Remove Jogress/DNA pre-evolution {partner_text} -> {self.current_digimon.name}?\n\n"
                    "Both partner source rows and the DNA partner requirement will be cleared together."
                )
            reply = QMessageBox.question(
                self, "Confirm",
                confirm_text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                if remove_jogress_group:
                    partner_set = set(jogress_partner_ids)
                    self.current_digimon.deevolution_sources = [
                        source for source in self.current_digimon.deevolution_sources
                        if safe_evolution_int(source.get('from_id'), 0) not in partner_set
                    ]
                    target_conditions['jogressDbIdA'] = 0
                    target_conditions['jogressPersonalityA'] = 0
                    target_conditions['jogressDbIdB'] = 0
                    target_conditions['jogressPersonalityB'] = 0
                    self._set_current_evolution_conditions(target_conditions)
                else:
                    self.current_digimon.deevolution_sources.pop(current_index)
                self.update_evolution_tab(self.current_digimon)
                self.mark_as_modified()
                QMessageBox.information(self, "Success", "Pre-evolution removed")


    def export_csv(self):
        """Export all CSV files with any changes made in the editor"""
        # Update current digimon with form data if one is loaded
        if self.current_digimon:
            if not self.validate_field_guide_id():
                return
            self.update_digimon_from_form()
            # Save changes to the original files first
            if not self.loader.save_digimon_data(self.current_digimon):
                QMessageBox.warning(self, "Warning", "Failed to save current Digimon changes")
                return

        # Get directory to save to
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Export Directory",
            str(get_existing_directory_start(get_default_mod_loader_path()))
        )
        if directory:
            from pathlib import Path
            output_path = Path(directory)
            resolved_dsts_path = self._resolve_dsts_loader_root(output_path)
            use_dsts_format = resolved_dsts_path is not None or self._is_dsts_loader_directory(output_path)

            if not use_dsts_format:
                format_dialog = QMessageBox(self)
                format_dialog.setWindowTitle("Select Export Format")
                format_dialog.setText(
                    "The selected folder doesn't look like a dsts-loader mod.\n"
                    "How would you like to export the CSV files?"
                )
                dsts_button = format_dialog.addButton("dsts-loader layout", QMessageBox.ButtonRole.AcceptRole)
                standard_button = format_dialog.addButton("Standard layout", QMessageBox.ButtonRole.DestructiveRole)
                cancel_button = format_dialog.addButton(QMessageBox.StandardButton.Cancel)
                format_dialog.setDefaultButton(standard_button)
                format_dialog.exec()

                clicked = format_dialog.clickedButton()
                if clicked == cancel_button:
                    return
                if clicked == dsts_button:
                    use_dsts_format = True
                    resolved_dsts_path = self._resolve_dsts_loader_root(output_path, allow_create=True)

            # If we have a current Digimon and dsts-loader format, offer merge option
            if use_dsts_format and self.current_digimon:
                output_path = resolved_dsts_path or self._resolve_dsts_loader_root(output_path, allow_create=True) or output_path
                # Check if destination already has files
                patch_data_dir = output_path / "patch" / "data"
                has_existing = False
                if patch_data_dir.exists():
                    status_file = patch_data_dir / "digimon_status.mbe" / "000_digimon_status_data.ap.csv"
                    if status_file.exists():
                        has_existing = True

                if has_existing:
                    # Offer merge vs overwrite
                    merge_dialog = QMessageBox(self)
                    merge_dialog.setWindowTitle("Export to dsts-loader")
                    merge_dialog.setText(
                        f"Found existing Digimon data in {directory}.\n\n"
                        "How would you like to export?"
                    )
                    merge_dialog.setIcon(QMessageBox.Icon.Question)
                    merge_button = merge_dialog.addButton("Merge (Update Current Digimon Only)", QMessageBox.ButtonRole.AcceptRole)
                    overwrite_button = merge_dialog.addButton("Overwrite All (Replace Everything)", QMessageBox.ButtonRole.DestructiveRole)
                    cancel_button = merge_dialog.addButton(QMessageBox.StandardButton.Cancel)
                    merge_dialog.setDefaultButton(merge_button)
                    merge_dialog.exec()

                    clicked = merge_dialog.clickedButton()
                    if clicked == cancel_button:
                        return

                    if clicked == merge_button:
                        # Merge: Update only the current Digimon, preserve others
                        original_identity = dict(getattr(self, "loaded_digimon_identity", {}) or {})
                        if self._merge_digimon_to_dsts_loader(output_path, self.current_digimon, original_identity):
                            QMessageBox.information(
                                self,
                                "Success",
                                f"✅ {self.current_digimon.name} has been updated in dsts-loader!\n\n"
                                "Other Digimon data was preserved."
                            )
                        else:
                            QMessageBox.warning(self, "Error", "Failed to merge Digimon data")
                        return
                    # else continue with overwrite (below)
                else:
                    # No existing data, just export single Digimon (this creates new files with just this Digimon)
                    original_identity = dict(getattr(self, "loaded_digimon_identity", {}) or {})
                    if self._merge_digimon_to_dsts_loader(output_path, self.current_digimon, original_identity):
                        QMessageBox.information(
                            self,
                            "Success",
                            f"✅ {self.current_digimon.name} has been exported to dsts-loader!"
                        )
                    else:
                        QMessageBox.warning(self, "Error", "Failed to export Digimon data")
                    return

            # Show warning about overwriting existing data (only for full export)
            warning_text = ""
            if use_dsts_format:
                output_path = resolved_dsts_path or self._resolve_dsts_loader_root(output_path, allow_create=True) or output_path
                warning_text = (
                    "⚠️ WARNING: Exporting to dsts-loader format will:\n\n"
                    "• DELETE all existing files in the destination directory\n"
                    "• REPLACE them with only the DLC data currently in your DLC folder\n"
                    "• This means if you have other Digimon data in dsts-loader that isn't in your DLC folder, it will be LOST\n\n"
                    "Only the Digimon data currently in your DLC folder will be exported.\n\n"
                    "Do you want to continue?"
                )
            else:
                warning_text = (
                    "⚠️ WARNING: Exporting all CSV files will:\n\n"
                    "• DELETE all existing files in the destination directory\n"
                    "• REPLACE them with copies of all files from your Base/data and Base/text folders\n"
                    "• Any files in the destination that don't exist in the source will be LOST\n\n"
                    "Do you want to continue?"
                )

            warning_dialog = QMessageBox(self)
            warning_dialog.setWindowTitle("⚠️ Confirm Export")
            warning_dialog.setText(warning_text)
            warning_dialog.setIcon(QMessageBox.Icon.Warning)
            warning_dialog.addButton(QMessageBox.StandardButton.Yes)
            warning_dialog.addButton(QMessageBox.StandardButton.No)
            warning_dialog.setDefaultButton(QMessageBox.StandardButton.No)

            if warning_dialog.exec() != QMessageBox.StandardButton.Yes:
                return

            if use_dsts_format:
                if self.exporter.export_for_dsts_loader(output_path):
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Exported DLC CSV files for dsts-loader to {directory}"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Error",
                        "Failed to export CSV files for dsts-loader"
                    )
            elif self.exporter.export_all_csv_files(output_path):
                QMessageBox.information(
                    self,
                    "Success",
                    f"Successfully exported all CSV files to {directory}"
                )
            else:
                QMessageBox.warning(self, "Error", "Failed to export CSV files")

    def _localized_texts_for_export(self, digimon: DigimonData) -> Dict[str, Dict[str, str]]:
        """Return localized text rows that should be written to dsts-loader."""
        localized_text = self._normalize_localized_text_map(getattr(digimon, "localized_text", {}))
        english_values = {
            "name": getattr(digimon, "name", "") or "",
            "profile_text": getattr(digimon, "profile_text", "") or "",
            "tribe_name": getattr(digimon, "tribe_name", "") or "None",
        }
        localized_text[ENGLISH_TEXT_FOLDER] = english_values

        export_text: Dict[str, Dict[str, str]] = {}
        for folder in sorted(localized_text, key=self._language_sort_key):
            values = localized_text[folder]
            export_text[folder] = {
                "name": str(values.get("name", "") or ""),
                "profile_text": str(values.get("profile_text", "") or ""),
                "tribe_name": str(values.get("tribe_name", "") or ""),
            }

        digimon.localized_text = export_text
        return export_text

    def _merge_localized_text_files(
        self,
        base_path: Path,
        digimon: DigimonData,
        wizard,
        match_char_keys: Set[str],
        match_profile_keys: Set[str],
        match_ids: Set[str],
    ):
        """Merge localized name/profile/belong rows into patch_textXX folders."""
        localized_text = self._localized_texts_for_export(digimon)

        for folder, values in localized_text.items():
            export_values = dict(values)
            patch_text = base_path / folder / "text"

            if folder != ENGLISH_TEXT_FOLDER and not any(str(value).strip() for value in export_values.values()):
                self._remove_rows_from_mod_csv(
                    patch_text / "char_name.mbe" / "000_Sheet1.ap.csv",
                    lambda r: self._csv_cell(r, 0) in match_char_keys,
                )
                self._remove_rows_from_mod_csv(
                    patch_text / "digimon_profile.mbe" / "000_Sheet1.ap.csv",
                    lambda r: self._csv_cell(r, 0) in match_profile_keys,
                )
                self._remove_rows_from_mod_csv(
                    patch_text / "belong.mbe" / "000_Sheet1.ap.csv",
                    lambda r: self._csv_cell(r, 0) in match_ids,
                )
                continue

            (patch_text / "char_name.mbe").mkdir(parents=True, exist_ok=True)
            (patch_text / "digimon_profile.mbe").mkdir(parents=True, exist_ok=True)
            (patch_text / "belong.mbe").mkdir(parents=True, exist_ok=True)

            char_name_file = patch_text / "char_name.mbe" / "000_Sheet1.ap.csv"
            self._merge_csv_row(
                char_name_file,
                digimon,
                lambda path, row_digimon, name_text=export_values["name"]: wizard._write_char_name_ap_csv(
                    path,
                    row_digimon,
                    name_text=name_text,
                ),
                lambda r: self._csv_cell(r, 0) in match_char_keys,
            )

            profile_file = patch_text / "digimon_profile.mbe" / "000_Sheet1.ap.csv"
            self._merge_csv_row(
                profile_file,
                digimon,
                lambda path, row_digimon, profile_text=export_values["profile_text"], name_text=export_values["name"]: wizard._write_profile_ap_csv(
                    path,
                    row_digimon,
                    profile_text=profile_text,
                    name_text=name_text,
                ),
                lambda r: self._csv_cell(r, 0) in match_profile_keys,
                drop_malformed=True,
            )

            belong_file = patch_text / "belong.mbe" / "000_Sheet1.ap.csv"
            self._merge_csv_row(
                belong_file,
                digimon,
                lambda path, row_digimon, tribe_name=export_values["tribe_name"]: wizard._write_belong_ap_csv(
                    path,
                    row_digimon,
                    tribe_name=tribe_name,
                ),
                lambda r: self._csv_cell(r, 0) in match_ids,
            )

    def _merge_digimon_to_dsts_loader(
        self,
        base_path: Path,
        digimon: DigimonData,
        original_identity: Optional[dict] = None,
        animation_ref: Optional[str] = None,
        sync_form: bool = True,
    ) -> bool:
        """Merge a single Digimon into existing dsts-loader files, preserving other entries"""
        try:
            from pathlib import Path
            import csv

            # Create directory structure
            patch_data = base_path / "patch" / "data"
            patch_text = base_path / ENGLISH_TEXT_FOLDER / "text"
            app_data = base_path / "app_0" / "data"

            # Create directories if they don't exist
            (patch_data / "digimon_status.mbe").mkdir(parents=True, exist_ok=True)
            (patch_data / "char_info.mbe").mkdir(parents=True, exist_ok=True)
            (patch_data / "model_setting.mbe").mkdir(parents=True, exist_ok=True)
            (patch_data / "lod_chara.mbe").mkdir(parents=True, exist_ok=True)
            (patch_data / "evolution.mbe").mkdir(parents=True, exist_ok=True)
            (patch_data / "anim_setting.mbe").mkdir(parents=True, exist_ok=True)
            (patch_text / "char_name.mbe").mkdir(parents=True, exist_ok=True)
            (patch_text / "digimon_profile.mbe").mkdir(parents=True, exist_ok=True)
            (patch_text / "belong.mbe").mkdir(parents=True, exist_ok=True)
            (app_data / "model_outline.mbe").mkdir(parents=True, exist_ok=True)

            # Normal editor saves sync the visible form first. Wizard exports pass
            # a fully built Digimon object and skip this to avoid touching the
            # previously loaded form while adding a second Digimon to a mod.
            if sync_form and hasattr(self, 'update_digimon_from_form'):
                self.update_digimon_from_form()

            # Use wizard's write methods to create the data row for this Digimon
            wizard = DigimonCreationWizard(parent=None, loader=self.loader)

            # Keep field guide/profile reference diagnostics available without noisy normal exports.
            debug_log(f"Writing digimon - field_guide_id={digimon.field_guide_id}, status_reference_id={digimon.script_id}")

            original_identity = original_identity or {}
            match_ids = {str(digimon.id)}
            if original_identity.get("id"):
                match_ids.add(str(original_identity["id"]))
            match_chr_ids = {digimon.chr_id}
            if original_identity.get("chr_id"):
                match_chr_ids.add(str(original_identity["chr_id"]))
            match_char_keys = {digimon.char_key}
            if original_identity.get("char_key"):
                match_char_keys.add(str(original_identity["char_key"]))
            match_profile_keys = set()
            for digimon_id in match_ids:
                match_profile_keys.update(digimon_profile_key_variants(digimon_id))

            def cell(row, index: int) -> str:
                return row[index].strip('"') if len(row) > index and row[index] else ""

            # Merge digimon_status_data
            status_file = patch_data / "digimon_status.mbe" / "000_digimon_status_data.ap.csv"
            self._merge_csv_row(
                status_file,
                digimon,
                wizard._write_digimon_status_ap_csv,
                lambda r: cell(r, 3) in match_chr_ids or cell(r, 0) in match_ids,
            )

            # Merge char_info
            char_info_file = patch_data / "char_info.mbe" / "000_char_info.ap.csv"
            self._merge_csv_row(char_info_file, digimon, wizard._write_char_info_ap_csv, lambda r: cell(r, 0) in match_char_keys)

            # Merge model_setting (if we have the data)
            if digimon.model_setting_data:
                model_file = patch_data / "model_setting.mbe" / "000_model_setting.ap.csv"
                self._merge_csv_row(model_file, digimon, wizard._write_model_setting_ap_csv, lambda r: cell(r, 0) in match_chr_ids)

            # Merge lod files
            lod_file = patch_data / "lod_chara.mbe" / "000_lod.ap.csv"
            self._merge_csv_row(lod_file, digimon, wizard._write_lod_ap_csv, lambda r: cell(r, 0) in match_chr_ids)

            lod_model_file = patch_data / "lod_chara.mbe" / "001_lod_model.ap.csv"
            self._merge_csv_row(lod_model_file, digimon, wizard._write_lod_model_ap_csv, lambda r: cell(r, 0) in match_chr_ids)

            evolution_cond_file = patch_data / "evolution.mbe" / "000_evolution_condition.ap.csv"
            jogress_cleanup_targets, jogress_cleanup_edges = self._jogress_cleanup_from_existing_conditions(
                evolution_cond_file,
                match_ids,
            )

            # Merge evolution files
            evolution_file = patch_data / "evolution.mbe" / "001_evolution_to.ap.csv"
            self._merge_evolution_file(
                evolution_file,
                digimon,
                wizard._write_evolution_ap_csv,
                match_ids,
                cleanup_entry_keys=jogress_cleanup_edges,
            )

            condition_match_ids = set(match_ids)
            condition_match_ids.update(jogress_cleanup_targets)
            for evo in getattr(digimon, "evolution_paths", []):
                if evo.get("export_conditions"):
                    target_id = evo.get("to_id")
                    if target_id:
                        condition_match_ids.add(str(target_id))
            self._merge_csv_row(
                evolution_cond_file,
                digimon,
                wizard._write_evolution_condition_ap_csv,
                lambda r: cell(r, 0) in condition_match_ids
            )

            # Merge anim_setting - need to handle special signature
            anim_ref = animation_ref or digimon.chr_id
            if animation_ref is None and hasattr(self, "animation_ref_edit") and self.animation_ref_edit.text().strip():
                anim_ref = self.animation_ref_edit.text().strip()
            anim_file = patch_data / "anim_setting.mbe" / "001_same_animation_data.ap.csv"
            resolved_anim_file = self._resolve_prefixed_file(anim_file)
            import tempfile
            temp_anim = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8')
            temp_anim.close()
            try:
                wizard._write_anim_setting_ap_csv(Path(temp_anim.name), digimon.chr_id, anim_ref)
                with open(temp_anim.name, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    anim_header = next(reader)
                    anim_new_rows = list(reader)
                Path(temp_anim.name).unlink()

                # Merge anim file
                anim_existing_rows = []
                if resolved_anim_file.exists():
                    with open(resolved_anim_file, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        anim_existing_header = next(reader, None)
                        if anim_existing_header:
                            anim_header = anim_existing_header
                            anim_existing_rows = list(reader)

                # Keep saves from carrying over blank rows left by manual CSV edits.
                anim_existing_rows = [
                    row for row in anim_existing_rows
                    if any(cell.strip() for cell in row)
                ]

                found_anim = False
                merged_anim_rows = []
                for row in anim_existing_rows:
                    if cell(row, 0) in match_chr_ids:
                        if not found_anim and anim_new_rows:
                            merged_anim_rows.extend(anim_new_rows)
                        found_anim = True
                        continue
                    merged_anim_rows.append(row)

                if found_anim:
                    anim_existing_rows = merged_anim_rows
                elif anim_new_rows:
                    anim_existing_rows.extend(anim_new_rows)

                with open(resolved_anim_file, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(anim_header)
                    for row in anim_existing_rows:
                        writer.writerow(row)
            except Exception as e:
                print(f"Error merging anim_setting: {e}")
                if Path(temp_anim.name).exists():
                    Path(temp_anim.name).unlink()

            # Merge localized text files
            self._merge_localized_text_files(
                base_path,
                digimon,
                wizard,
                match_char_keys,
                match_profile_keys,
                match_ids,
            )

            # Merge model_outline
            outline_file = app_data / "model_outline.mbe" / "000_model_outline_battle.ap.csv"
            self._merge_csv_row(outline_file, digimon, wizard._write_model_outline_ap_csv, lambda r: cell(r, 0) in match_chr_ids)

            self.last_mvgl_cache_notice = self._clear_mvgl_fileloader_cache()
            return True

        except Exception as e:
            print(f"Error merging Digimon to dsts-loader: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _merge_csv_row(self, filepath: Path, digimon_or_data, write_func, find_row_func, drop_malformed: bool = False):
        """Merge a single row into a CSV file, preserving other rows"""
        import csv
        import tempfile

        # Generate new row data by writing to temp file
        temp_file = filepath.parent / f"_temp_{filepath.name}"
        header_str = None
        new_rows = []
        try:
            # Call write_func with appropriate arguments
            if isinstance(digimon_or_data, tuple):
                write_func(temp_file, *digimon_or_data)
            else:
                write_func(temp_file, digimon_or_data)

            # Read the new row from temp file (header is a string, data rows use csv.reader)
            if temp_file.exists():
                with open(temp_file, 'r', encoding='utf-8') as f:
                    header_str = f.readline().rstrip('\n\r')  # Read header as raw string
                    reader = csv.reader(f)
                    new_rows = list(reader)
                temp_file.unlink()  # Delete temp file
            else:
                print(f"Warning: Temp file {temp_file} was not created")
                return

            if not new_rows:
                return  # No data to merge

            # Read existing file if it exists
            existing_rows = []
            header_to_use = header_str if header_str else ""
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_header = f.readline().rstrip('\n\r')
                    if existing_header:
                        header_to_use = existing_header  # Use existing header if file exists
                    reader = csv.reader(f)
                    existing_rows = list(reader)

            # Empty spreadsheet rows look harmless, but the import path treats a
            # status row as a Digimon entry. Drop only fully blank rows so normal
            # optional empty columns remain intact.
            existing_rows = [
                row for row in existing_rows
                if any(cell.strip() for cell in row)
            ]

            if drop_malformed and new_rows:
                expected_columns = len(new_rows[0])
                existing_rows = [
                    row for row in existing_rows
                    if len(row) == expected_columns
                ]

            # Replace all matching old/current rows with the freshly generated row.
            # This also collapses duplicates left by earlier saves that appended
            # after a chr_id/ID change instead of updating the original entry.
            found = False
            merged_rows = []
            for row in existing_rows:
                if find_row_func(row):
                    if not found:
                        merged_rows.extend(new_rows)
                    found = True
                    continue
                merged_rows.append(row)

            if found:
                existing_rows = merged_rows
            else:
                existing_rows.extend(new_rows)

            # Write back preserving dsts-loader format
            if header_to_use:
                with open(filepath, 'w', encoding='utf-8', newline='') as f:
                    # Write header (as raw string to preserve format)
                    f.write(header_to_use + '\n')
                    # Write rows - csv.writer handles proper quoting/escaping
                    writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                    for row in existing_rows:
                        writer.writerow(row)
            else:
                print(f"Warning: No header available for {filepath.name}, skipping write")

        except Exception as e:
            print(f"Error merging {filepath.name}: {e}")
            import traceback
            traceback.print_exc()
            if temp_file.exists():
                temp_file.unlink()

    def _jogress_cleanup_from_existing_conditions(
        self,
        filepath: Path,
        match_ids: Iterable[str],
    ) -> Tuple[Set[str], Set[Tuple[str, str]]]:
        """Find old DNA targets/edges involving this Digimon in an existing mod."""
        import csv

        match_ids = {str(value) for value in match_ids if str(value)}
        cleanup_targets: Set[str] = set()
        cleanup_edges: Set[Tuple[str, str]] = set()
        resolved_filepath = self._resolve_prefixed_file(filepath)
        if not resolved_filepath.exists():
            return cleanup_targets, cleanup_edges

        try:
            with open(resolved_filepath, 'r', encoding='utf-8', newline='') as f:
                f.readline()
                reader = csv.reader(f)
                for row in reader:
                    target_id = self._csv_cell(row, 0)
                    if not target_id:
                        continue
                    partner_ids = [
                        str(partner_id)
                        for partner_id in jogress_partner_ids_from_conditions(row)
                    ]
                    if not partner_ids or not match_ids.intersection(partner_ids):
                        continue
                    cleanup_targets.add(target_id)
                    for partner_id in partner_ids:
                        cleanup_edges.add((partner_id, target_id))
        except Exception as e:
            print(f"Error inspecting Jogress cleanup rows in {filepath.name}: {e}")

        return cleanup_targets, cleanup_edges

    def _merge_evolution_file(
        self,
        filepath: Path,
        digimon,
        write_func,
        match_ids: Optional[Iterable[str]] = None,
        cleanup_entry_keys: Optional[Iterable[Tuple[str, str]]] = None,
    ):
        """Merge evolution data, removing old entries for this digimon first"""
        import csv
        match_ids = {str(value) for value in (match_ids or {digimon.id}) if str(value)}
        cleanup_entry_keys = {
            (str(source_id), str(target_id))
            for source_id, target_id in (cleanup_entry_keys or set())
            if str(source_id) and str(target_id)
        }

        # Generate new evolution rows
        temp_file = filepath.parent / f"_temp_{filepath.name}"
        try:
            write_func(temp_file, digimon)

            # Read new rows
            with open(temp_file, 'r', encoding='utf-8') as f:
                header_str = f.readline().rstrip('\n\r')
                reader = csv.reader(f)
                new_rows = list(reader)
            temp_file.unlink()
            new_entry_keys = {
                (row[1], row[3])
                for row in new_rows
                if len(row) > 3 and row[1] and row[3]
            }

            # Resolve filepath to handle any numeric prefix variation
            resolved_filepath = self._resolve_prefixed_file(filepath)

            # Read existing file (use resolved path)
            existing_rows = []
            header_to_use = header_str
            if resolved_filepath.exists():
                    with open(resolved_filepath, 'r', encoding='utf-8') as f:
                        existing_header = f.readline().rstrip('\n\r')
                        if existing_header:
                            header_to_use = existing_header
                        reader = csv.reader(f)
                        existing_rows = list(reader)

            existing_rows = [
                row for row in existing_rows
                if any(cell.strip() for cell in row)
            ]

            # Remove existing entries for this Digimon (both as source and target),
            # including the originally loaded ID if the user changed it.
            filtered_rows = []
            for row in existing_rows:
                if len(row) > 1:
                    source_id = row[1] if row[1] else None
                    target_id = row[3] if len(row) > 3 and row[3] else None
                    if (
                        source_id not in match_ids
                        and target_id not in match_ids
                        and (source_id, target_id) not in new_entry_keys
                        and (source_id, target_id) not in cleanup_entry_keys
                    ):
                        filtered_rows.append(row)

            # Add new rows
            filtered_rows.extend(new_rows)

            # Write back preserving format (use resolved path to maintain existing prefix)
            with open(resolved_filepath, 'w', encoding='utf-8', newline='') as f:
                # Write header (as raw string to preserve format)
                f.write(header_to_use + '\n')
                # Write rows
                writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                for row in filtered_rows:
                    writer.writerow(row)

        except Exception as e:
            print(f"Error merging evolution file {filepath.name}: {e}")
            if temp_file.exists():
                temp_file.unlink()

    def _is_dsts_loader_directory(self, path: Path) -> bool:
        """Check if the selected export path appears to be a dsts-loader directory."""
        try:
            if self._resolve_dsts_loader_root(path) is not None:
                return True
            lowered_parts = [part.lower() for part in path.parts]
            if any(loader_name in lowered_parts for loader_name in DSTS_LOADER_DIR_NAMES):
                return True
            if path.name.lower() in {"addcont_01", "addcont_01_text01", "addcont_02", "addcont_02_text01", "addcont_03", "addcont_03_text01", "addcont_17", "addcont_17_text01", "data", "text"}:
                parent_parts = [part.lower() for part in path.parent.parts]
                if any(loader_name in parent_parts for loader_name in DSTS_LOADER_DIR_NAMES):
                    return True
            return any(
                (path / f"addcont_{dlc_id}").exists()
                and (path / f"addcont_{dlc_id}_text01").exists()
                for dlc_id in self.loader.get_dlc_ids()
            )
        except Exception:
            return False

    def repack_mbe_files(self):
        """Repack exported CSV folders to .mbe files"""
        # Let user select source folder (containing .mbe folders)
        source_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Source Folder (containing .mbe folders)",
            str(Path.cwd())
        )

        if not source_dir:
            return  # User cancelled

        # Let user select target folder for .mbe files
        target_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Target Folder for .mbe files",
            str(Path.cwd())
        )

        if not target_dir:
            return  # User cancelled

        # Repack the files
        if repack_mbe_files(Path(source_dir), Path(target_dir)):
            QMessageBox.information(self, "Success",
                f"Successfully repacked .mbe files to {target_dir}")
        else:
            QMessageBox.warning(self, "Error", "Failed to repack .mbe files")

    def repack_dlc_mbe_files(self):
        """Repack DLC CSV folders to .mbe files"""
        # Confirm action
        reply = QMessageBox.question(
            self,
            "Repack DLC to MBE",
            "This will repack all DLC CSV folders into .mbe files.\n\n"
            "DLC folders to be repacked:\n"
            "- DLC/addcont_01-03,17.dx11/data/mbe/*_dlc01-03,17.mbe/\n"
            "- DLC/addcont_01-03,17_text01.dx11/text/mbe/*_dlc01-03,17.mbe/\n\n"
            "Requires DSCSToolsCLI.exe in the workspace root.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        # Repack the DLC files
        if repack_dlc_mbe_files():
            QMessageBox.information(
                self,
                "Success",
                "✅ Successfully repacked DLC .mbe files!\n\n"
                "The DLC is now ready to use in-game.\n"
                "Copy the DLC folder to your game's directory."
            )
        else:
            QMessageBox.warning(
                self,
                "Error",
                "❌ Failed to repack DLC .mbe files.\n\n"
                "Make sure DSCSToolsCLI.exe is in the workspace root\n"
                "and that you have exported Digimon to DLC first."
            )

    def populate_stage_dropdown(self):
        """Populate the stage dropdown with localized names"""
        for i in range(15):  # Stages 0-14 (based on generation_name.mbe CSV)
            stage_name = self.loader.get_generation_name(i)
            clean_name = self.loader.clean_ui_text(stage_name)
            self.stage_combo.addItem(clean_name, i)

    def populate_type_dropdown(self):
        """Populate the type dropdown with localized names"""
        for i in range(7):  # Types 0-6
            type_name = self.loader.get_type_name(i)
            clean_name = self.loader.clean_ui_text(type_name)
            self.type_combo.addItem(clean_name, i)

    def populate_personality_dropdown(self):
        """Populate the personality dropdown with localized names"""
        for i in range(17):  # Personalities 0-16
            personality_name = self.loader.get_personality_name(i)
            clean_name = self.loader.clean_ui_text(personality_name)
            self.personality_combo.addItem(clean_name, i)

    def populate_tribe_dropdown(self):
        """Populate the tribe dropdown with unique tribes from belong.mbe"""
        unique_tribes = set()
        try:
            # Try to load from backup folder first (most complete)
            belong_file = self.loader._resolve_prefixed_file(Path("backup") / "text" / "belong.mbe" / "000_Sheet1.csv")
            if not belong_file.exists():
                # Try loader's text path
                belong_file = self.loader._resolve_prefixed_file(self.loader.text_path / "belong.mbe" / "000_Sheet1.csv")

            if belong_file.exists():
                rows = self.loader.load_csv(belong_file)
                for row in rows[1:]:  # Skip header
                    if len(row) >= 2:
                        tribe_name = row[1].strip('"')
                        if tribe_name:
                            unique_tribes.add(tribe_name)
        except Exception as e:
            print(f"Error loading tribes: {e}")
            # Fallback to common tribes
            unique_tribes = {"None", "Mammal", "Beast Man", "Dragon", "Machine", "Beast", "Bird", "Insectoid", "Reptile"}

        # Add to combo box (sorted)
        for tribe_name in sorted(unique_tribes):
            self.tribe_combo.addItem(tribe_name)

    def _active_skill_data_root(self) -> Optional[Path]:
        active_root = self._active_dsts_loader_root()
        return active_root / "patch" / "data" if active_root else None

    def _skill_name_map_from_mod(self, dsts_loader_root: Path) -> Dict[str, str]:
        names: Dict[str, str] = {}
        skill_name_dir = dsts_loader_root / "patch_text01" / "text" / "skill_name.mbe"
        if not skill_name_dir.exists():
            return names

        for csv_file in sorted(skill_name_dir.glob("*.ap.csv")):
            try:
                rows = self.loader.load_csv(csv_file)
            except Exception:
                continue
            for row in rows[1:]:
                if len(row) >= 2:
                    key = _clean_status_cell(row[0])
                    value = _clean_status_cell(row[1])
                    if key and value:
                        names[key] = value
        return names

    def _active_mod_skill_options(self) -> List[tuple]:
        """Return skill browser options from the active Reloaded II mod payload."""
        active_root = self._active_dsts_loader_root()
        if not active_root:
            return []

        skill_file = self._resolve_prefixed_file(
            active_root / "patch" / "data" / "battle_skill.mbe" / "000_battle_skill_list.ap.csv"
        )
        if not skill_file.exists():
            return []

        names = self._skill_name_map_from_mod(active_root)
        options = []
        seen = set()
        try:
            rows = self.loader.load_csv(skill_file)
            for row in rows[1:]:
                if not row or not row[0]:
                    continue
                try:
                    skill_id = int(_clean_status_cell(row[0]))
                except (TypeError, ValueError):
                    continue
                if skill_id in seen:
                    continue
                seen.add(skill_id)

                name_id = _clean_status_cell(row[4]) if len(row) > 4 else ""
                skill_name = names.get(str(skill_id)) or names.get(name_id) or self.loader.get_skill_name(skill_id)
                skill_name = self.loader.clean_ui_text(skill_name) if skill_name else ""
                if not skill_name or skill_name.startswith("Skill_"):
                    skill_name = name_id or f"Skill {skill_id}"
                options.append((skill_id, f"ID {skill_id}: {skill_name} [Active Mod]"))
        except Exception as exc:
            print(f"Error loading active mod skill options: {exc}")
        return sorted(options, key=lambda option: option[0])

    def _load_advanced_skill_data(self, skill_id: int) -> Dict[str, object]:
        """Load a skill for the advanced editor, preferring the active mod payload."""
        active_data_root = self._active_skill_data_root()
        if active_data_root:
            skill_data = self.loader.load_skill_data(skill_id, data_root=active_data_root, prefer_ap=True)
            if skill_data:
                skill_data["_data_root"] = active_data_root
                skill_data["_prefer_ap"] = True
                skill_data["_source_label"] = "Active Mod"
                return skill_data

        skill_data = self.loader.load_skill_data(skill_id)
        if skill_data:
            skill_data["_data_root"] = None
            skill_data["_prefer_ap"] = False
            skill_data["_source_label"] = "Base/DLC Workspace"
        return skill_data

    def _advanced_skill_contexts(self) -> List[tuple]:
        """Return mode-change lookup contexts, with the current skill source first."""
        contexts = []
        current_root = getattr(self, "current_advanced_skill_data_root", None)
        current_prefer_ap = bool(getattr(self, "current_advanced_skill_prefer_ap", False))
        current_label = getattr(self, "current_advanced_skill_source_label", "")
        contexts.append((current_root, current_prefer_ap, current_label or "Current Skill Source"))

        active_root = self._active_skill_data_root()
        if active_root:
            contexts.append((active_root, True, "Active Mod"))
        contexts.append((None, False, "Base/DLC Workspace"))

        unique_contexts = []
        seen = set()
        for data_root, prefer_ap, label in contexts:
            key = (str(Path(data_root).resolve()).casefold() if data_root else "", prefer_ap)
            if key in seen:
                continue
            seen.add(key)
            unique_contexts.append((data_root, prefer_ap, label))
        return unique_contexts

    def _set_mode_change_skill_values(self, skill_ids: List[int]):
        if not hasattr(self, "mode_change_skill_widgets"):
            return
        for index, widget in enumerate(self.mode_change_skill_widgets):
            widget.setValue(skill_ids[index] if index < len(skill_ids) else 0)

    def _mode_change_skill_values(self) -> List[int]:
        if not hasattr(self, "mode_change_skill_widgets"):
            return []
        return [widget.value() for widget in self.mode_change_skill_widgets if widget.value() > 0]

    def _populate_mode_change_fields(self, mode_data: Optional[Dict[str, object]], source_label: str = ""):
        if not hasattr(self, "mode_change_source_digimon_edit"):
            return

        if not mode_data:
            self.mode_change_source_digimon_edit.setValue(0)
            self.mode_change_flag_4_edit.setValue(1)
            self.mode_change_flag_5_edit.setValue(1)
            self._set_mode_change_skill_values([])
            if hasattr(self, "mode_change_status_label"):
                self.mode_change_status_label.setText("No mode row loaded.")
            return

        self.mode_change_source_digimon_edit.setValue(int(mode_data.get("source_digimon_id", 0) or 0))
        self.mode_change_flag_4_edit.setValue(int(mode_data.get("flag_4", 1) or 1))
        self.mode_change_flag_5_edit.setValue(int(mode_data.get("flag_5", 1) or 1))
        self._set_mode_change_skill_values([int(skill_id) for skill_id in mode_data.get("skill_ids", [])])
        if hasattr(self, "mode_change_status_label"):
            location = source_label or mode_data.get("source_file", "")
            self.mode_change_status_label.setText(f"Loaded mode row {mode_data.get('mode_change_id', '')} from {location}.")

    def clear_mode_change_fields(self):
        if hasattr(self, "skill_mode_change_edit"):
            self.skill_mode_change_edit.setValue(-1)
        self._populate_mode_change_fields(None)

    def populate_mode_change_from_current_digimon(self):
        if not self.current_digimon:
            QMessageBox.warning(self, "No Digimon Loaded", "Load a Digimon before building a mode-change row.")
            return

        source_id = self.id_spin.value() if hasattr(self, "id_spin") else int(getattr(self.current_digimon, "id", 0) or 0)
        if source_id <= 0:
            QMessageBox.warning(self, "Missing Digimon ID", "Set a valid Digimon ID before building a mode-change row.")
            return

        skill_ids = []
        if hasattr(self, "signature_skills_editor"):
            skill_ids = [skill.get("id", 0) for skill in self.signature_skills_editor.get_skills()]
        if not skill_ids:
            skill_ids = [skill.get("id", 0) for skill in getattr(self.current_digimon, "signature_skills", [])]

        self.skill_mode_change_edit.setValue(source_id * 10 + 1)
        self.mode_change_source_digimon_edit.setValue(source_id)
        self.mode_change_flag_4_edit.setValue(1)
        self.mode_change_flag_5_edit.setValue(1)
        self._set_mode_change_skill_values([skill_id for skill_id in skill_ids if skill_id])
        if hasattr(self, "mode_change_status_label"):
            self.mode_change_status_label.setText(
                f"Prepared mode row {source_id * 10 + 1} for Digimon {source_id}. Save the skill to write 003_skill_mode_change."
            )

    def load_mode_change_row_for_current_skill(self, show_messages: bool = False):
        if not hasattr(self, "skill_mode_change_edit"):
            return

        mode_change_id = self.skill_mode_change_edit.value()
        if mode_change_id <= 0:
            self._populate_mode_change_fields(None)
            if show_messages:
                QMessageBox.information(self, "No Mode Change", "This skill does not point to a mode-change row.")
            return

        for data_root, prefer_ap, label in self._advanced_skill_contexts():
            mode_data = self.loader.load_skill_mode_change_data(
                mode_change_id,
                data_root=data_root,
                prefer_ap=prefer_ap,
            )
            if mode_data:
                self._populate_mode_change_fields(mode_data, label)
                if show_messages:
                    QMessageBox.information(self, "Mode Row Loaded", f"Loaded mode row {mode_change_id} from {label}.")
                return

        self._populate_mode_change_fields(None)
        if hasattr(self, "mode_change_status_label"):
            self.mode_change_status_label.setText(
                f"Mode row {mode_change_id} was not found. Fill Source Digimon ID and Mode Skill Set, then save to create it."
            )
        if show_messages:
            QMessageBox.warning(
                self,
                "Mode Row Missing",
                f"Mode row {mode_change_id} was not found in the active mod or base workspace."
            )

    def _mode_change_data_from_widgets(self) -> Dict[str, object]:
        return {
            "mode_change_id": self.skill_mode_change_edit.value(),
            "source_digimon_id": self.mode_change_source_digimon_edit.value(),
            "flag_4": self.mode_change_flag_4_edit.value(),
            "flag_5": self.mode_change_flag_5_edit.value(),
            "skill_ids": self._mode_change_skill_values(),
        }

    def populate_skill_browser(self):
        """Populate the searchable skill browser dropdown."""
        if not hasattr(self, "skill_browser_combo"):
            return

        current_skill_id = self.advanced_skill_id_edit.value() if hasattr(self, "advanced_skill_id_edit") else 0
        self.skill_browser_combo.blockSignals(True)
        self.skill_browser_combo.clear()
        self.skill_browser_combo.addItem("Select a skill...", 0)

        seen_skill_ids = set()
        for skill_id, label in self._active_mod_skill_options():
            self.skill_browser_combo.addItem(label, skill_id)
            seen_skill_ids.add(skill_id)
            if skill_id == current_skill_id:
                self.skill_browser_combo.setCurrentIndex(self.skill_browser_combo.count() - 1)

        for skill_id, label in get_skill_options(self.loader):
            if skill_id in seen_skill_ids:
                continue
            self.skill_browser_combo.addItem(label, skill_id)
            if skill_id == current_skill_id:
                self.skill_browser_combo.setCurrentIndex(self.skill_browser_combo.count() - 1)

        self.skill_browser_combo.blockSignals(False)
        configure_searchable_combo(self.skill_browser_combo)

    def filter_skill_list(self):
        """Kept for compatibility; the skill browser is now a searchable dropdown."""
        return

    def open_skill_browser_dropdown(self):
        """Open the Advanced Skill Browser dropdown."""
        if hasattr(self, "skill_browser_combo"):
            self.skill_browser_combo.setFocus(Qt.FocusReason.MouseFocusReason)
            self.skill_browser_combo.showPopup()

    def load_skill_from_browser(self, item=None):
        """Load a skill from the browser dropdown."""
        if hasattr(item, "data"):
            skill_id = item.data(Qt.ItemDataRole.UserRole)
        elif isinstance(item, int) and hasattr(self, "skill_browser_combo"):
            skill_id = self.skill_browser_combo.itemData(item)
        elif hasattr(self, "skill_browser_combo"):
            skill_id = self.skill_browser_combo.currentData()
        else:
            skill_id = None

        if skill_id:
            self.advanced_skill_id_edit.setValue(skill_id)
            # This will trigger update_advanced_skill_display automatically

    def _buff_set_csv_path(self, data_root: Optional[Path] = None, prefer_ap: bool = False) -> Path:
        """Resolve the buff set CSV for a skill data root."""
        root = Path(data_root) if data_root else self.loader.data_path
        filename = "002_buff_set.ap.csv" if prefer_ap else "002_buff_set.csv"
        battle_skill_dir = "battle_skill.mbe"
        dlc_match = re.search(r"addcont_(\d+)\.dx11", str(root), re.IGNORECASE)
        if dlc_match:
            battle_skill_dir = f"battle_skill_dlc{dlc_match.group(1)}.mbe"

        buff_set_file = self.loader._resolve_prefixed_file(root / battle_skill_dir / filename)
        if not buff_set_file.exists() and dlc_match and not prefer_ap:
            # DLC 17 currently ships this table without the leading zero.
            legacy_file = self.loader._resolve_prefixed_file(root / battle_skill_dir / "02_buff_set.csv")
            if legacy_file.exists():
                return legacy_file
        return buff_set_file

    def _buff_set_contexts(self) -> List[Tuple[Optional[Path], bool, str]]:
        """Return buff-set lookup contexts, preferring the current skill source."""
        contexts: List[Tuple[Optional[Path], bool, str]] = []
        current_root = getattr(self, "current_advanced_skill_data_root", None)
        current_prefer_ap = bool(getattr(self, "current_advanced_skill_prefer_ap", False))
        current_label = getattr(self, "current_advanced_skill_source_label", "")
        if current_root:
            contexts.append((current_root, current_prefer_ap, current_label or "Current Skill Source"))

        active_root = self._active_skill_data_root()
        if active_root:
            contexts.append((active_root, True, "Active Mod"))
        contexts.append((None, False, "Base Workspace"))
        try:
            for dlc_id, dlc_root in self.loader.iter_dlc_data_roots():
                contexts.append((dlc_root, False, f"DLC {dlc_id}"))
        except Exception:
            pass

        unique_contexts = []
        seen = set()
        for data_root, prefer_ap, label in contexts:
            key = (str(Path(data_root).resolve()).casefold() if data_root else "", prefer_ap)
            if key in seen:
                continue
            seen.add(key)
            unique_contexts.append((data_root, prefer_ap, label))
        return unique_contexts

    def _load_buff_set_map(self, data_root: Optional[Path] = None, prefer_ap: bool = False) -> Dict[int, List[dict]]:
        """Load buff set rows as decoded effect entries."""
        buff_set_file = self._buff_set_csv_path(data_root, prefer_ap)
        if not buff_set_file.exists():
            return {}

        try:
            cache_key = (str(buff_set_file.resolve()).casefold(), buff_set_file.stat().st_mtime)
        except OSError:
            cache_key = (str(buff_set_file).casefold(), 0.0)

        cached = self._buff_set_cache.get(cache_key)
        if cached is not None:
            return cached

        buff_sets: Dict[int, List[dict]] = {}
        try:
            rows = self.loader.load_csv(buff_set_file)
        except Exception as exc:
            print(f"Error loading buff set data from {buff_set_file}: {exc}")
            return {}

        slot_starts = range(6, 57, 5)
        for row in rows[1:]:
            if not row:
                continue
            set_id = safe_evolution_int(_clean_status_cell(row[0]) if len(row) > 0 else "", -1)
            if set_id < 0:
                continue

            entries = []
            for start in slot_starts:
                effect_id = safe_evolution_int(row[start] if len(row) > start else 0, 0)
                if effect_id <= 0:
                    continue
                rate = safe_evolution_int(row[start + 1] if len(row) > start + 1 else 0, 0)
                change_percent = safe_evolution_int(row[start + 2] if len(row) > start + 2 else 0, 0)
                turn_override = safe_evolution_int(row[start + 3] if len(row) > start + 3 else 0, 0)
                name = self.loader.get_buff_name(effect_id)
                entries.append({
                    "effect_id": effect_id,
                    "name": name,
                    "rate": rate,
                    "change_percent": change_percent,
                    "turn_override": turn_override,
                })
            buff_sets[set_id] = entries

        stale_keys = [key for key in self._buff_set_cache if key[0] == cache_key[0] and key != cache_key]
        for key in stale_keys:
            self._buff_set_cache.pop(key, None)
        self._buff_set_cache[cache_key] = buff_sets
        return buff_sets

    def _format_buff_effect_summary(self, entry: dict) -> str:
        """Return a compact label for one buff effect entry."""
        pieces = [entry.get("name", f"Buff {entry.get('effect_id', '')}")]
        change_percent = entry.get("change_percent", 0)
        rate = entry.get("rate", 0)
        turns = entry.get("turn_override", 0)
        if change_percent:
            pieces.append(f"{change_percent}%")
        if rate:
            pieces.append(f"{rate}% rate")
        if turns > 0:
            pieces.append(f"{turns}t")
        elif turns == -1:
            pieces.append("until removed")
        return " / ".join(str(piece) for piece in pieces if str(piece))

    def _describe_buff_set(self, buff_set_id: int) -> Tuple[str, str]:
        """Return a short label and tooltip for a buff set ID."""
        for data_root, prefer_ap, source_label in self._buff_set_contexts():
            buff_sets = self._load_buff_set_map(data_root, prefer_ap)
            if buff_set_id not in buff_sets:
                continue

            entries = buff_sets.get(buff_set_id, [])
            if not entries:
                return f"Set {buff_set_id}: No effects", f"Set {buff_set_id} found in {source_label}, but all effect slots are empty."

            effect_labels = [self._format_buff_effect_summary(entry) for entry in entries]
            preview = "; ".join(effect_labels[:2])
            if len(effect_labels) > 2:
                preview += f"; +{len(effect_labels) - 2} more"
            tooltip = f"Set {buff_set_id} from {source_label}\n" + "\n".join(f"- {label}" for label in effect_labels)
            return f"Set {buff_set_id}: {preview}", tooltip

        return f"Set {buff_set_id}: Not found", f"No row for buff set {buff_set_id} was found in the active mod or Base data."

    def update_buff_name_display(self, buff_index: int, buff_set_id: int):
        """Update the buff name label when buff set ID changes"""
        if buff_index < len(self.buff_name_labels):
            if buff_set_id > 0:
                summary, tooltip = self._describe_buff_set(buff_set_id)
                self.buff_name_labels[buff_index].setText(summary)
                self.buff_name_labels[buff_index].setToolTip(tooltip)
            else:
                self.buff_name_labels[buff_index].setText("")
                self.buff_name_labels[buff_index].setToolTip("")

    def update_advanced_skill_display(self):
        """Update advanced skill display when skill ID changes"""
        skill_id = self.advanced_skill_id_edit.value()
        if hasattr(self, "skill_browser_combo"):
            index = self.skill_browser_combo.findData(skill_id)
            if index >= 0 and self.skill_browser_combo.currentIndex() != index:
                self.skill_browser_combo.blockSignals(True)
                self.skill_browser_combo.setCurrentIndex(index)
                self.skill_browser_combo.blockSignals(False)
        if skill_id > 0:
            # Load skill data. Active mods win so custom skills save back to their .ap.csv payload.
            skill_data = self._load_advanced_skill_data(skill_id)
            if skill_data:
                self.current_advanced_skill_data_root = skill_data.get("_data_root")
                self.current_advanced_skill_prefer_ap = bool(skill_data.get("_prefer_ap", False))
                self.current_advanced_skill_source_label = str(skill_data.get("_source_label", "Base/DLC Workspace"))

                # Update skill name
                skill_name = self.loader.get_skill_name(skill_id)
                clean_name = self.loader.clean_ui_text(skill_name)
                self.advanced_skill_name_edit.setText(clean_name if clean_name else "")

                # Show description (from skill_explanation.mbe if available)
                description_text = self.loader.get_skill_explanation(skill_id)
                if description_text:
                    self.advanced_skill_desc.setPlainText(description_text)
                else:
                    self.advanced_skill_desc.setPlainText("No description found for this skill.")

                # Update all form fields with loaded data
                self.skill_power_edit.setValue(skill_data.get("power", 0))
                self.skill_sp_cost_edit.setValue(skill_data.get("sp_cost", 0))
                self.skill_cp_cost_edit.setValue(skill_data.get("cp_cost", 0))
                self.skill_animation_id_edit.setValue(skill_data.get("animation_id", 0))
                self.skill_effect_id_edit.setValue(skill_data.get("effect_id", 0))
                self.skill_mode_change_edit.setValue(skill_data.get("mode_change_id", 0))
                self.skill_jogress_skill_edit.setValue(skill_data.get("jogress_skill_id", 0))
                self.skill_jogress_p1_edit.setValue(skill_data.get("jogress_partner_1", 0))
                self.skill_jogress_p2_edit.setValue(skill_data.get("jogress_partner_2", 0))
                self.load_mode_change_row_for_current_skill(show_messages=False)
                self.skill_accuracy_edit.setValue(skill_data.get("accuracy", 0))
                self.skill_crit_rate_edit.setValue(skill_data.get("crit_rate", 0))

                # Set damage type
                damage_type = skill_data.get("damage_type", 0)
                if damage_type < self.skill_damage_type_combo.count():
                    self.skill_damage_type_combo.setCurrentIndex(damage_type)

                # Set element
                element = skill_data.get("element", 0)
                for i in range(self.skill_element_combo.count()):
                    if self.skill_element_combo.itemData(i) == element:
                        self.skill_element_combo.setCurrentIndex(i)
                        break

                self.skill_min_hits_edit.setValue(skill_data.get("min_hits", 1))
                self.skill_max_hits_edit.setValue(skill_data.get("max_hits", 1))

                # Set additional properties
                prop1 = skill_data.get("additional_property_1", 0)
                if prop1 < self.skill_additional_prop1_combo.count():
                    self.skill_additional_prop1_combo.setCurrentIndex(prop1)

                prop2 = skill_data.get("additional_property", 0)
                if prop2 < self.skill_additional_prop2_combo.count():
                    self.skill_additional_prop2_combo.setCurrentIndex(prop2)

                # Set conditional effects
                cond_type = skill_data.get("conditional_type", 0)
                if cond_type < self.skill_conditional_type_combo.count():
                    self.skill_conditional_type_combo.setCurrentIndex(cond_type)

                cond_effect = skill_data.get("conditional_effect", 0)
                if cond_effect < self.skill_conditional_effect_combo.count():
                    self.skill_conditional_effect_combo.setCurrentIndex(cond_effect)

                self.skill_conditional_arg_edit.setValue(skill_data.get("conditional_arg", 0))

                # Set buff sets
                for i, widget in enumerate(self.buff_set_widgets):
                    buff_key = f"buff_set_{i}"
                    widget.setValue(skill_data.get(buff_key, 0))

                # Set special effects
                self.skill_hp_drain_edit.setValue(skill_data.get("hp_drain", 0))
                self.skill_sp_drain_edit.setValue(skill_data.get("sp_drain", 0))
                self.skill_recoil_edit.setValue(skill_data.get("recoil", 0))
                self.skill_always_hits_check.setChecked(skill_data.get("always_hits", False))
            else:
                self.current_advanced_skill_data_root = None
                self.current_advanced_skill_prefer_ap = False
                self.current_advanced_skill_source_label = ""
                self.advanced_skill_name_edit.setText("Skill not found")
                self.advanced_skill_desc.setPlainText("")
                self.clear_mode_change_fields()
        else:
            self.current_advanced_skill_data_root = None
            self.current_advanced_skill_prefer_ap = False
            self.current_advanced_skill_source_label = ""
            self.advanced_skill_name_edit.setText("")
            self.advanced_skill_desc.setPlainText("")
            self.clear_mode_change_fields()

    def save_advanced_skill(self):
        """Save the current skill data"""
        skill_id = self.advanced_skill_id_edit.value()
        if skill_id <= 0:
            QMessageBox.warning(self, "Error", "Please enter a valid skill ID")
            return

        mode_change_data = self._mode_change_data_from_widgets()
        if mode_change_data["mode_change_id"] > 0:
            if mode_change_data["source_digimon_id"] <= 0:
                QMessageBox.warning(
                    self,
                    "Mode Change Source Missing",
                    "Mode Change ID is positive, but the 003_skill_mode_change row has no Source Digimon ID."
                )
                return
            if not mode_change_data["skill_ids"]:
                QMessageBox.warning(
                    self,
                    "Mode Change Skills Missing",
                    "Mode Change ID is positive, but the 003_skill_mode_change row has no skill IDs."
                )
                return

        data_root = getattr(self, "current_advanced_skill_data_root", None)
        prefer_ap = bool(getattr(self, "current_advanced_skill_prefer_ap", False))
        source_label = getattr(self, "current_advanced_skill_source_label", "Base/DLC Workspace")

        # Collect all form data
        skill_data = {
            "skill_id": skill_id,
            "power": self.skill_power_edit.value(),
            "sp_cost": self.skill_sp_cost_edit.value(),
            "cp_cost": self.skill_cp_cost_edit.value(),
            "animation_id": self.skill_animation_id_edit.value(),
            "effect_id": self.skill_effect_id_edit.value(),
            "mode_change_id": self.skill_mode_change_edit.value(),
            "jogress_skill_id": self.skill_jogress_skill_edit.value(),
            "jogress_partner_1": self.skill_jogress_p1_edit.value(),
            "jogress_partner_2": self.skill_jogress_p2_edit.value(),
            "accuracy": self.skill_accuracy_edit.value(),
            "crit_rate": self.skill_crit_rate_edit.value(),
            "damage_type": self.skill_damage_type_combo.currentIndex(),
            "element": self.skill_element_combo.currentData(),
            "min_hits": self.skill_min_hits_edit.value(),
            "max_hits": self.skill_max_hits_edit.value(),
            "additional_property_1": self.skill_additional_prop1_combo.currentIndex(),
            "additional_property": self.skill_additional_prop2_combo.currentIndex(),
            "conditional_type": self.skill_conditional_type_combo.currentIndex(),
            "conditional_effect": self.skill_conditional_effect_combo.currentIndex(),
            "conditional_arg": self.skill_conditional_arg_edit.value(),
            "hp_drain": self.skill_hp_drain_edit.value(),
            "sp_drain": self.skill_sp_drain_edit.value(),
            "recoil": self.skill_recoil_edit.value(),
            "always_hits": self.skill_always_hits_check.isChecked()
        }

        # Add buff sets
        for i, widget in enumerate(self.buff_set_widgets):
            skill_data[f"buff_set_{i}"] = widget.value()

        # Save skill data
        skill_saved = self.loader.save_skill_data(skill_data, data_root=data_root, prefer_ap=prefer_ap)
        mode_saved = True
        if skill_saved and mode_change_data["mode_change_id"] > 0:
            mode_saved = self.loader.save_skill_mode_change_data(
                mode_change_data,
                data_root=data_root,
                prefer_ap=prefer_ap,
            )

        # Save skill name if it was edited
        skill_name = self.advanced_skill_name_edit.text().strip()
        name_saved = True
        if skill_name and skill_name != "Skill not found" and not prefer_ap:
            name_saved = self.loader.save_skill_name(skill_id, skill_name)

        # Show result message
        if skill_saved and mode_saved and name_saved:
            QMessageBox.information(self, "Success", f"Skill {skill_id} saved successfully to {source_label}!")
        elif skill_saved and not mode_saved:
            QMessageBox.warning(self, "Partial Success", f"Skill {skill_id} saved, but the mode-change row could not be saved.")
        elif skill_saved:
            QMessageBox.warning(self, "Partial Success", f"Skill {skill_id} saved, but skill name could not be saved.")
        elif name_saved:
            QMessageBox.warning(self, "Partial Success", f"Skill name saved, but skill data could not be saved.")
        else:
            QMessageBox.critical(self, "Error", "Failed to save skill data and name")


def main():
    app = QApplication(sys.argv)
    install_spinbox_wheel_guard()

    # Set application properties
    app.setApplicationName("DTS Creator")
    app.setApplicationVersion("1.0")

    # Fix for Windows 11 - Set global palette to ensure text is visible
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#333333"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#333333"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#333333"))
    palette.setColor(QPalette.ColorRole.Base, QColor("white"))
    palette.setColor(QPalette.ColorRole.Window, QColor("#f8f9fa"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#667eea"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#999999"))
    app.setPalette(palette)

    # Global stylesheet to ensure text visibility on Windows 11
    app.setStyleSheet("""
        QComboBox, QListWidget, QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
            color: #333333;
            background-color: white;
        }
        QComboBox QAbstractItemView {
            color: #333333;
            background-color: white;
            selection-background-color: #667eea;
            selection-color: white;
        }
        QComboBox QAbstractItemView::item {
            color: #333333;
        }
        QListWidget::item {
            color: #333333;
        }
        QListWidget::item:selected {
            color: white;
            background-color: #667eea;
        }
        QTableWidget {
            color: #333333;
            background-color: white;
        }
        QTableWidget::item {
            color: #333333;
        }
        QLabel {
            color: #333333;
        }
        QGroupBox {
            color: #333333;
        }
        QCheckBox {
            color: #333333;
        }
        QRadioButton {
            color: #333333;
        }
    """)

    # Create and show main window
    window = DigimonEditor()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
