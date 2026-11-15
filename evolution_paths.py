"""Shared evolution and pre-evolution controls for Digimon creation and editing."""
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from Data_Loader import DigimonData
from editor_theme import (
    apply_modern_dialog_theme, modern_action_button_style, modern_groupbox_style,
    modern_info_panel_style, modern_muted_text_style, modern_status_panel_style, modern_warning_panel_style,
)


EVOLUTION_TYPE_NORMAL = 0
EVOLUTION_TYPE_MODE_CHANGE = 2


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


class EvolutionPathControls:
    """Shared path lists, pickers and requirements editors for the active Digimon."""

    def _safe_evolution_int(self, value, default: int = 0) -> int:
        return safe_evolution_int(value, default)

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
                if len(row) > 61 and self._csv_cell(row, 0) == str(digimon_id):
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

        return self._saved_evolution_conditions_for_target(target_id) or default_evolution_conditions()

    def _saved_evolution_conditions_for_target(self, target_id: int) -> Optional[dict]:
        def scan_condition_file(condition_file: Path) -> Optional[dict]:
            if not condition_file.exists():
                return None
            rows = self.loader.load_csv(condition_file)
            for row in rows[1:]:
                if row and self._csv_cell(row, 0) == str(target_id):
                    return normalize_evolution_conditions(row)
            return None

        for imported in getattr(self.loader, "imported_digimon", []):
            if imported.id != target_id:
                continue
            if imported.evolution_conditions:
                return normalize_evolution_conditions(imported.evolution_conditions)
            root = getattr(imported, "imported_dsts_loader_root", "")
            if root and getattr(imported, "imported_lazy_related_pending", False):
                path = Path(root) / "patch/data/evolution.mbe/000_evolution_condition.ap.csv"
                conditions = scan_condition_file(self.loader._resolve_prefixed_file(path))
                if conditions is not None:
                    return conditions

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

        return None

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
        if self.compact_paths:
            list_widget.setWordWrap(True)
            list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid rgba(143, 211, 207, 105);
                border-radius: 2px;
                padding: 5px;
                background-color: rgba(4, 18, 23, 205);
                color: #e8f2f1;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 2px;
                margin: 2px;
                border-bottom: 1px solid rgba(143, 211, 207, 32);
            }
            QListWidget::item:selected {
                background-color: #d8872b;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: rgba(35, 78, 77, 210);
                color: #ffffff;
            }
        """)
        return list_widget

    def _add_path_box(self, parent_layout, title: str, attr_name: str, selected_color: str, hover_color: str, min_height: int = 120):
        box = QGroupBox(title)
        box.setStyleSheet(modern_groupbox_style("rgba(136, 233, 224, 150)", "#88e9e0"))
        box_layout = QVBoxLayout(box)
        list_widget = self._make_path_list_widget(selected_color, hover_color, min_height)
        setattr(self, attr_name, list_widget)
        box_layout.addWidget(list_widget)
        parent_layout.addWidget(box)

    def _clear_path_peer_selections(self, active_list: QListWidget, list_names: Iterable[str]):
        if not active_list.selectedItems():
            return
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
            list_widget.itemSelectionChanged.connect(
                lambda active=list_widget, names=list_names: self._clear_path_peer_selections(active, names)
            )
            if edit_on_double_click:
                list_widget.itemDoubleClicked.connect(lambda _item: self.edit_evolution())

    def _selected_path_index(self, list_names: Iterable[str]) -> Optional[int]:
        for list_name in list_names:
            list_widget = getattr(self, list_name, None)
            if list_widget is None:
                continue
            selected_items = list_widget.selectedItems()
            if not selected_items:
                continue
            path_index = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if path_index is None:
                continue
            try:
                return int(path_index)
            except (TypeError, ValueError):
                continue
        return None

    def _add_path_item(self, list_widget: QListWidget, label: str, path_index: int, details: str = ""):
        text = label + details
        item = QListWidgetItem(label if self.compact_paths else text)
        item.setData(Qt.ItemDataRole.UserRole, path_index)
        item.setToolTip(text)
        list_widget.addItem(item)

    def _add_empty_path_placeholder(self, list_widget: QListWidget, text: str):
        if list_widget.count() == 0:
            item = QListWidgetItem("No paths" if self.compact_paths else text)
            item.setData(Qt.ItemDataRole.UserRole, None)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setForeground(QColor("#7f9698"))
            list_widget.addItem(item)

    def create_evolution_tab(self, *, compact=False) -> QWidget:
        """Build the path controls for the editor tab or the narrower wizard page."""
        self.compact_paths = compact
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)

        evolution_panel_style = modern_groupbox_style("rgba(136, 233, 224, 150)", "#88e9e0")
        evolution_hint_style = """
            QLabel {
                color: #dce9ea;
                background-color: rgba(4, 18, 23, 165);
                border: 1px solid rgba(143, 211, 207, 45);
                border-left: 4px solid #88e9e0;
                border-radius: 2px;
                padding: 10px 12px;
                font-size: 10pt;
                font-weight: 500;
            }
        """
        evolution_status_style = """
            QLabel {
                color: #e8f2f1;
                background-color: rgba(6, 24, 29, 190);
                border: 1px solid rgba(143, 211, 207, 45);
                border-left: 4px solid #88e9e0;
                border-radius: 2px;
                padding: 8px 10px;
                font-size: 10pt;
            }
        """
        evolution_warning_style = """
            QLabel {
                color: #f0c982;
                background-color: rgba(73, 48, 15, 165);
                border: 1px solid rgba(216, 135, 43, 120);
                border-left: 4px solid #d8872b;
                border-radius: 2px;
                padding: 9px 12px;
                font-size: 9.5pt;
            }
        """

        def configure_evolution_button(button: QPushButton, accent: str = "#d8872b", minimum_width: int = 150) -> None:
            button.setMinimumHeight(40)
            button.setMinimumWidth(minimum_width)
            button.setStyleSheet(modern_action_button_style(accent))

        if not compact:
            # Title
            title = QLabel("Evolution Management")
            title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            title.setStyleSheet("""
                QLabel {
                    color: #f5fffc;
                    padding: 13px 16px;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(5, 43, 48, 230),
                        stop:0.76 rgba(13, 61, 60, 215),
                        stop:1 rgba(216, 135, 43, 215));
                    border: 1px solid rgba(136, 233, 224, 135);
                    border-left: 4px solid #d8872b;
                    border-radius: 2px;
                }
            """)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(title)

            # Instructions
            info_label = QLabel(
                "First, set the requirements needed to evolve INTO this Digimon.\n"
                "Then configure evolution paths (what this Digimon can evolve into) and view pre-evolutions."
            )
            info_label.setWordWrap(True)
            info_label.setStyleSheet(evolution_hint_style)
            layout.addWidget(info_label)

        # Evolution Requirements section (for obtaining THIS Digimon)
        req_group = QGroupBox("Requirements to Obtain This Digimon")
        req_group.setStyleSheet(evolution_panel_style)
        req_layout = QVBoxLayout()
        req_layout.setContentsMargins(18, 22, 18, 18)
        req_layout.setSpacing(10)

        if not compact:
            req_info = QLabel(
                "These are the requirements that other Digimon must meet to evolve INTO this Digimon.\n"
                "Leave values at 0 for no requirement."
            )
            req_info.setWordWrap(True)
            req_info.setStyleSheet("color: #dce9ea; font-size: 10pt; font-weight: 500; border: none; background: transparent;")
            req_layout.addWidget(req_info)

        edit_req_btn = QPushButton("Edit This Digimon's Requirements")
        edit_req_btn.setToolTip("Edit the requirements other Digimon must meet to evolve into this Digimon")
        configure_evolution_button(edit_req_btn, "#d8872b")
        edit_req_btn.clicked.connect(self.edit_evolution_requirements)
        req_layout.addWidget(edit_req_btn)

        self.requirements_label = QLabel("Mode: No Requirements (default)")
        self.requirements_label.setStyleSheet(evolution_status_style)
        self.requirements_label.setWordWrap(True)
        req_layout.addWidget(self.requirements_label)

        if not compact:
            chrono_button = QPushButton('Edit Chrono Devolution Forms')
            chrono_button.setToolTip('Choose the six forms used by Chronomon in the final boss fight.')
            configure_evolution_button(chrono_button, '#88e9e0')
            chrono_button.clicked.connect(self.edit_chronodevolution_forms)
            req_layout.addWidget(chrono_button)

        req_group.setLayout(req_layout)
        layout.addWidget(req_group)

        # Evolution paths section
        evo_group = QGroupBox("Evolution Paths (What this Digimon evolves into)")
        evo_group.setStyleSheet(evolution_panel_style)
        evo_layout = QVBoxLayout()
        evo_layout.setContentsMargins(18, 22, 18, 18)
        evo_layout.setSpacing(12)

        evo_buttons = QGridLayout()
        evo_buttons.setSpacing(8)
        add_evo_btn = QPushButton("Add Evolution Path")
        configure_evolution_button(add_evo_btn, "#20d6a3")
        add_evo_btn.clicked.connect(self.add_evolution)
        add_jogress_evo_btn = QPushButton("Add Jogress / DNA")
        configure_evolution_button(add_jogress_evo_btn, "#88e9e0")
        add_jogress_evo_btn.clicked.connect(lambda _checked=False: self.add_evolution(force_jogress=True))
        edit_evo_btn = QPushButton("Edit Target Requirements")
        edit_evo_btn.setToolTip("These requirements apply to every path into the selected target Digimon.")
        configure_evolution_button(edit_evo_btn, "#d8872b", 205)
        edit_evo_btn.clicked.connect(self.edit_evolution)
        remove_evo_btn = QPushButton("Remove Selected Evolution")
        configure_evolution_button(remove_evo_btn, "#d8872b", 205)
        remove_evo_btn.clicked.connect(self.remove_evolution)
        for position, button in enumerate((add_evo_btn, add_jogress_evo_btn, edit_evo_btn, remove_evo_btn)):
            row, column = divmod(position, 2 if compact else 4)
            evo_buttons.addWidget(button, row, column)
        if not compact:
            evo_buttons.setColumnStretch(4, 1)
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
        deevo_group = QGroupBox("Pre-Evolutions (Digimon that evolve INTO this one)")
        deevo_group.setStyleSheet(evolution_panel_style)
        deevo_layout = QVBoxLayout()
        deevo_layout.setContentsMargins(18, 22, 18, 18)
        deevo_layout.setSpacing(12)

        deevo_info = QLabel(
            "💡 Adding a pre-evolution creates an evolution entry where THAT Digimon evolves into THIS one.\n"
            "⚠️ Each Digimon can only have 6 evolution targets maximum. Base, DLC, and Reloaded II mod rows are counted."
        )
        deevo_info.setWordWrap(True)
        deevo_info.setStyleSheet(evolution_warning_style)
        deevo_layout.addWidget(deevo_info)

        # Buttons for adding/removing pre-evolutions
        deevo_buttons = QGridLayout()
        deevo_buttons.setSpacing(8)
        add_deevo_btn = QPushButton("Add Pre-Evolution")
        configure_evolution_button(add_deevo_btn, "#20d6a3")
        add_deevo_btn.clicked.connect(self.add_pre_evolution)
        add_jogress_deevo_btn = QPushButton("Add Jogress / DNA")
        configure_evolution_button(add_jogress_deevo_btn, "#88e9e0")
        add_jogress_deevo_btn.clicked.connect(lambda _checked=False: self.add_pre_evolution(force_jogress=True))
        remove_deevo_btn = QPushButton("Remove Selected Pre-Evolution")
        configure_evolution_button(remove_deevo_btn, "#d8872b", 230)
        remove_deevo_btn.clicked.connect(self.remove_pre_evolution)
        for position, button in enumerate((add_deevo_btn, add_jogress_deevo_btn, remove_deevo_btn)):
            row, column = divmod(position, 2 if compact else 3)
            deevo_buttons.addWidget(button, row, column)
        if not compact:
            deevo_buttons.setColumnStretch(3, 1)
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

            # A mod may add only the edge and use the target's existing game requirements.
            if "conditions" not in evo:
                evo["conditions"] = self._saved_evolution_conditions_for_target(to_id) or {}
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
            partners = jogress_partner_ids_from_conditions(evo.get("conditions", {}))
            if category == "jogress" and partners and digimon.id not in partners:
                req_str += "\nEdit Target Requirements to use this Digimon as a DNA partner."
            self._add_path_item(outgoing_lists[category], f"→ {to_name} (ID: {to_id})", evo_index, req_str)

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
            self._add_path_item(incoming_lists[category], f"← {from_name} (ID: {from_id})", deevo_index, req_str)

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
            self._evolution_edited()
            QMessageBox.information(self, "Success", "Evolution requirements updated!")

    def add_evolution(self, force_jogress: bool = False):
        """Add a new evolution path"""
        if not self.current_digimon:
            return

        # Create dialog to select target Digimon
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Evolution")
        dialog.setMinimumSize(550, 600)
        apply_modern_dialog_theme(dialog)
        layout = QVBoxLayout(dialog)

        source_id = safe_evolution_int(getattr(self.current_digimon, "id", 0), 0)
        source_name = getattr(self.current_digimon, "name", "") or f"ID {source_id}"
        source_slot_count = self.get_evolution_count_for_digimon(source_id) if source_id > 0 else 0
        source_free_slots = max(0, 6 - source_slot_count)

        # Instructions
        info_label = QLabel(
            "Select a target Digimon below, or enter a custom Digimon name/ID. "
            "Adding a path uses one outgoing evolution slot on the currently edited Digimon."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(modern_info_panel_style())
        layout.addWidget(info_label)

        slot_status_label = None
        if source_id <= 0 or source_slot_count >= 5:
            slot_status_label = QLabel()
            slot_status_label.setWordWrap(True)
        if source_id <= 0 and slot_status_label:
            slot_status_label.setText(
                "Evolution slots: set the current Digimon ID first to count base, DLC, mod, and pending paths."
            )
            slot_status_label.setStyleSheet(modern_status_panel_style("#88e9e0"))
        elif source_slot_count >= 6 and slot_status_label:
            slot_status_label.setText(
                f"❌ {source_name} has {source_slot_count}/6 evolution slots used (0 free). "
                "Remove an existing path before adding another."
            )
            slot_status_label.setStyleSheet(modern_warning_panel_style())
        elif source_slot_count >= 5 and slot_status_label:
            slot_status_label.setText(
                f"⚠️ {source_name} has {source_slot_count}/6 evolution slots used "
                f"({source_free_slots} free)."
            )
            slot_status_label.setStyleSheet(modern_status_panel_style("#d8872b"))
        if slot_status_label:
            layout.addWidget(slot_status_label)

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

        target_count_label = QLabel("Select a target to see that Digimon's own outgoing evolution slots.")
        target_count_label.setStyleSheet(modern_muted_text_style())
        list_layout.addWidget(target_count_label)

        target_list = QListWidget()
        target_list.setMinimumHeight(300)

        # Populate with official and custom Digimon. Custom mod rows are stored
        # on each list item so the dialog does not need to parse labels.
        picker_entries = self._evolution_picker_entries()
        for entry in picker_entries:
            target_count = self.get_evolution_count_for_digimon(entry["id"])
            target_free_slots = max(0, 6 - target_count)
            if target_count >= 6:
                status = "❌ FULL"
            elif target_count >= 5:
                status = f"⚠️ {target_count}/6 used, {target_free_slots} free"
            else:
                status = f"✅ {target_count}/6 used, {target_free_slots} free"

            item = QListWidgetItem(
                f"{entry['name']} [{status}] ({entry['chr_id']}) - ID: {entry['id']} [{entry['source']}]"
            )
            item_data = dict(entry)
            item_data["evo_count"] = target_count
            item.setData(100, item_data)
            if target_count >= 6:
                item.setForeground(Qt.GlobalColor.red)
            elif target_count >= 5:
                item.setForeground(Qt.GlobalColor.darkYellow)
            target_list.addItem(item)

        def update_target_count():
            current = target_list.currentItem()
            if not current:
                return
            data = current.data(100)
            if not data:
                return
            count = data.get("evo_count", 0)
            free_slots = max(0, 6 - count)
            if count >= 6:
                status = "FULL"
                color = "#ff6b7d"
            elif count >= 5:
                status = f"{free_slots} free"
                color = "#d8872b"
            else:
                status = f"{free_slots} free"
                color = "#20d6a3"
            target_count_label.setText(
                f"{data.get('name', 'Target')} outgoing slots: {count}/6 used ({status})."
            )
            target_count_label.setStyleSheet(modern_status_panel_style(color))

        target_list.currentItemChanged.connect(lambda: update_target_count())

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
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button and source_id > 0 and source_slot_count >= 6:
            ok_button.setEnabled(False)
            ok_button.setToolTip("This Digimon already has 6 evolution targets. Remove one before adding another.")
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

                if source_id > 0:
                    source_targets = self._evolution_targets_for_digimon(source_id)
                    target_key = str(target_digimon_id)
                    if target_key in source_targets:
                        QMessageBox.warning(
                            self,
                            "Already Exists",
                            f"Evolution to Digimon ID {target_digimon_id} already exists in base, DLC, mod, or pending data!"
                        )
                        return
                    if len(source_targets) >= 6:
                        QMessageBox.warning(
                            self,
                            "Evolution Limit Reached",
                            f"Cannot add evolution to Digimon ID {target_digimon_id}.\n\n"
                            f"{source_name} already has 6 evolution targets.\n"
                            f"Remove an existing path before adding another."
                        )
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
                self._evolution_edited()
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
        apply_modern_dialog_theme(dialog)

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
            QMessageBox.warning(self, "Warning", "Please select an evolution target to edit")
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
            self._evolution_edited()
            QMessageBox.information(self, "Success", f"Target requirements updated for {to_name}")

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
                self._evolution_edited()
                QMessageBox.information(self, "Success", "Evolution removed")

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
        apply_modern_dialog_theme(dialog)
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
                    self._evolution_edited()
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

                self._evolution_edited()
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
                self._evolution_edited()
                QMessageBox.information(self, "Success", "Pre-evolution removed")

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

    def _evolution_edited(self):
        self.update_evolution_tab(self.current_digimon)
