"""Installed mod Field Guide slot manager for Time Stranger Mod Studio."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from field_guide_slots import CUSTOM_MAX, CUSTOM_MIN, change_slot, scan_inventory


class FieldGuideSlotsDialog(QDialog):
    def __init__(self, mods_root, loader, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Installed Mods • Field Guide")
        self.resize(1030, 650)
        self.root = Path(mods_root)
        self.loader = loader
        self.inventory = None
        self.changes = []
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        title = QLabel("Field Guide slots")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 6)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #e8f2f1;")
        layout.addWidget(title)

        path_bar = QHBoxLayout()
        self.path = QLabel()
        self.path.setTextFormat(Qt.TextFormat.PlainText)
        self.path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_bar.addWidget(self.path, 1)
        browse = QPushButton("Change folder…")
        browse.clicked.connect(self.choose_folder)
        path_bar.addWidget(browse)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        path_bar.addWidget(refresh)
        layout.addLayout(path_bar)

        self.summary = QLabel()
        layout.addWidget(self.summary)
        filter_bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find a mod, Digimon, slot or ID…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_rows)
        filter_bar.addWidget(self.search, 1)
        self.status = QComboBox()
        self.status.addItems(["All statuses", "Slot conflicts", "ID overlaps", "Shared entries", "Unassigned"])
        self.status.currentIndexChanged.connect(self.filter_rows)
        filter_bar.addWidget(self.status)
        self.show_stock = QCheckBox("Show base game and DLC")
        self.show_stock.setStyleSheet("QCheckBox { color: #e8f2f1; }")
        self.show_stock.toggled.connect(self.filter_rows)
        filter_bar.addWidget(self.show_stock)
        layout.addLayout(filter_bar)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Mod / source", "Digimon", "Guide slot", "Status", "Digimon ID", "Chr ID"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0b2025;
                alternate-background-color: #10292e;
                color: #e1eeee;
                border: 1px solid #3d6567;
                selection-background-color: #3b6264;
                selection-color: white;
            }
            QHeaderView::section {
                background-color: #1b383d; color: #ccdfde;
                padding: 6px; border: 0; border-right: 1px solid #3d6063;
            }
        """)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        for column in range(6):
            mode = QHeaderView.ResizeMode.Stretch if column < 2 else QHeaderView.ResizeMode.ResizeToContents
            header.setSectionResizeMode(column, mode)
        self.table.itemSelectionChanged.connect(self.update_selection)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.model().layoutChanged.connect(self.filter_rows)
        layout.addWidget(self.table, 1)

        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.detail)
        bar = QHBoxLayout()
        self.issues = QPushButton("Scan details…")
        self.issues.clicked.connect(self.show_warnings)
        bar.addWidget(self.issues)
        bar.addStretch()
        self.edit = QPushButton("Change slot…")
        self.edit.clicked.connect(self.edit_selected)
        bar.addWidget(self.edit)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        bar.addWidget(close)
        layout.addLayout(bar)
        self.refresh()

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select the Reloaded II Mods folder", str(self.root))
        if folder:
            self.root = Path(folder)
            self.refresh()

    def refresh(self):
        self.path.setText(str(self.root))
        self.table.clearSelection()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.inventory = None
        try:
            data = scan_inventory(self.root, self.loader)
        except (ValueError, OSError) as exc:
            self.summary.setText("Choose a readable Reloaded II Mods folder to see its Field Guide entries.")
            self.detail.setText(str(exc))
            self.issues.setEnabled(False)
            self.edit.setEnabled(False)
            return
        self.inventory = data
        self.table.setRowCount(len(data.entries))
        occupied = {entry.slot for entry in data.entries if data.state(entry) == "Slot conflict"}
        rows = sum(1 for e in data.entries if e.mod and e.digimon_id is not None)
        self.summary.setText(f"{len(data.mods)} installed mods   •   {rows} mod entries   •   {len(occupied)} conflicting slots")
        self.issues.setEnabled(bool(data.warnings))
        for index, entry in enumerate(data.entries):
            state = data.state(entry)
            values = [entry.source, entry.name or "—", entry.slot if entry.slot is not None and entry.slot >= 0 else "—",
                      state, entry.digimon_id if entry.digimon_id is not None else "—", entry.chr_id or "—"]
            for column, value in enumerate(values):
                item = QTableWidgetItem()
                item.setData(Qt.ItemDataRole.DisplayRole, value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, index)
                    item.setToolTip(str(entry.table or entry.mod or entry.source))
                if column == 3 and state in ("Slot conflict", "ID overlap"):
                    bg = "#7a352f" if state == "Slot conflict" else "#705321"
                    item.setBackground(QBrush(QColor(bg)))
                    item.setForeground(QBrush(QColor("#ffffff")))
                self.table.setItem(index, column, item)
        self.table.setSortingEnabled(True)
        self.table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.filter_rows()

    def filter_rows(self):
        if self.inventory is None:
            return
        query = self.search.text().strip().casefold()
        state_filter = (None, "Slot conflict", "ID overlap", "Shared entry", "Unassigned")[self.status.currentIndex()]
        for row in range(self.table.rowCount()):
            entry = self.inventory.entries[self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)]
            mod_id, version = self.inventory.mods.get(entry.mod, ("", ""))
            haystack = " ".join(str(v) for v in (entry.source, entry.name, entry.key, entry.chr_id,
                                                 entry.digimon_id, entry.slot, entry.mod.name if entry.mod else "",
                                                 mod_id, version))
            visible = (bool(entry.mod) or self.show_stock.isChecked()) and query in haystack.casefold()
            state = self.inventory.state(entry)
            visible = visible and (not state_filter or state == state_filter or
                                   (state_filter == "Shared entry" and state == "Shared stock slot"))
            self.table.setRowHidden(row, not visible)
        self.update_selection()

    def selected(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected or not self.inventory or self.table.isRowHidden(selected[0].row()):
            return None
        return self.inventory.entries[selected[0].data(Qt.ItemDataRole.UserRole)]

    def update_selection(self):
        entry = self.selected()
        self.edit.setEnabled(bool(entry and entry.editable))
        if entry is None:
            self.detail.setText("Select a mod entry to inspect its source and change its Field Guide slot.")
            return
        text = str(entry.table or entry.mod or entry.source)
        if entry.record:
            text += f"  •  CSV record {entry.record + 1}"
        if entry.note:
            text += f"  •  {entry.note}"
        mod_id, version = self.inventory.mods.get(entry.mod, ("", ""))
        if mod_id:
            text += f"\n{mod_id}" + (f"  ·  v{version}" if version else "")
        peers = [peer for peer in self.inventory.slots.get(entry.slot, []) if peer != entry]
        if peers:
            text += "\nAlso uses this slot: " + ", ".join(f"{peer.source} ({peer.name}, ID {peer.digimon_id})" for peer in peers)
        if self.inventory.state(entry) == "ID overlap":
            overlaps = [p for p in self.inventory.ids[entry.digimon_id] if p.slot != entry.slot]
            text += "\nOther assignments for this Digimon ID: " + ", ".join(f"{p.source} (slot {p.slot})" for p in overlaps)
        self.detail.setText(text)

    def show_warnings(self):
        if self.inventory and self.inventory.warnings:
            message = QMessageBox(self)
            message.setWindowTitle("Field Guide scan details")
            message.setText(f"{len(self.inventory.warnings)} source(s) or rows could not be read completely.")
            message.setDetailedText("\n".join(self.inventory.warnings))
            message.exec()

    def edit_selected(self):
        entry = self.selected()
        if not entry or not entry.editable:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Change Field Guide slot")
        form = QFormLayout(dialog)
        for label, value in (("Mod", entry.source), ("Digimon", f"{entry.name}  ·  ID {entry.digimon_id}"),
                             ("Current slot", str(entry.slot) if entry.slot is not None and entry.slot >= 0 else "Unassigned"),
                             ("Status table", str(entry.table.relative_to(entry.mod)))):
            text = QLabel(value)
            text.setTextFormat(Qt.TextFormat.PlainText)
            form.addRow(label, text)
        choices = QComboBox()
        choices.addItem("Choose a free custom slot…", None)
        for slot in range(CUSTOM_MIN, CUSTOM_MAX + 1):
            if not self.inventory.slots.get(slot):
                choices.addItem(str(slot), slot)
        form.addRow("New slot", choices)
        note = QLabel("Saving updates this row in the installed mod. A copy of the original CSV is kept in the mod’s Time Stranger Mod Studio Backups folder.")
        if self.inventory.warnings:
            note.setText(note.text() + " Some sources could not be read. Available slots reflect the scanned rows.")
        note.setWordWrap(True)
        form.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setEnabled(False)
        choices.currentIndexChanged.connect(lambda index: save.setEnabled(index > 0))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            change = change_slot(self.root, self.loader, entry, choices.currentData())
        except (ValueError, OSError) as exc:
            explanation = str(exc)
            if isinstance(exc, PermissionError):
                explanation += "\nClose any editor tab holding the CSV and check write access to this mod."
            QMessageBox.warning(self, "Could not change slot", explanation)
            self.refresh()
            return
        self.changes.append(change)
        self.refresh()
        self.detail.setText(f"Saved {entry.name} to slot {change.new_slot}. Original CSV: {change.backup}")
