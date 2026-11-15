"""Create a native battle skill using a selected skill's settings and bindings."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPlainTextEdit, QSpinBox, QVBoxLayout,
)

from editor_theme import apply_modern_dialog_theme
from skill_records import MAX_SKILL_ID


class SkillAuthorDialog(QDialog):
    def __init__(self, parent, catalog, template_id=0, *, destination_hint=""):
        super().__init__(parent)
        self.catalog = catalog
        self.draft = None
        self.setWindowTitle("Create Skill")
        self.resize(600, 600)
        apply_modern_dialog_theme(self)
        layout = QVBoxLayout(self)

        template_label = QLabel("Skill template")
        layout.addWidget(template_label)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find a template by skill name or ID")
        self.search.setClearButtonEnabled(True)
        template_label.setBuddy(self.search)
        layout.addWidget(self.search)
        self.templates = QListWidget()
        self.templates.setAccessibleName("Skill templates")
        self.templates.setMinimumHeight(120)
        layout.addWidget(self.templates, 1)
        default = QListWidgetItem("Basic attack defaults", self.templates)
        default.setData(Qt.ItemDataRole.UserRole, 0)
        selected = default
        for skill_id, record in sorted(catalog.records.items(), key=lambda pair: (pair[1].name.casefold(), pair[0])):
            item = QListWidgetItem(f"{record.name}  ·  ID {skill_id}", self.templates)
            item.setData(Qt.ItemDataRole.UserRole, skill_id)
            item.setToolTip(str(record.source))
            if skill_id == template_id:
                selected = item

        self.template_details = QLabel()
        self.template_details.setTextFormat(Qt.TextFormat.PlainText)
        self.template_details.setWordWrap(True)
        layout.addWidget(self.template_details)

        form = QFormLayout()
        self.skill_id = QSpinBox()
        self.skill_id.setRange(1, MAX_SKILL_ID)
        self.skill_id.setValue(catalog.suggest_id())
        form.addRow("New skill ID", self.skill_id)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Name shown in the game")
        form.addRow("New skill name", self.name_edit)
        self.description = QPlainTextEdit()
        self.description.setPlaceholderText("Leave blank for the game's automatic explanation.")
        self.description.setMaximumHeight(94)
        form.addRow("Description", self.description)
        layout.addLayout(form)
        if destination_hint:
            hint = QLabel(destination_hint)
            hint.setWordWrap(True)
            hint.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(hint)
        if catalog.unreadable_sheets:
            unreadable = QLabel("Some skill tables could not be read. Their IDs are missing from the availability check.")
            unreadable.setWordWrap(True)
            unreadable.setToolTip("\n".join(catalog.unreadable_sheets))
            layout.addWidget(unreadable)

        self.error = QLabel()
        self.error.setTextFormat(Qt.TextFormat.PlainText)
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #ffae98;")
        self.error.hide()
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.create_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.create_button.setText("Create skill")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.search.textChanged.connect(self.filter_templates)
        self.templates.currentItemChanged.connect(self.template_changed)
        self.name_edit.textChanged.connect(self.update_button)
        self.skill_id.valueChanged.connect(self.update_button)
        self.templates.setCurrentItem(selected)
        self.templates.scrollToItem(selected)
        self.name_edit.setFocus()

    def filter_templates(self, text):
        query = text.strip().casefold()
        first = None
        for index in range(self.templates.count()):
            item = self.templates.item(index)
            matches = query in item.text().casefold()
            item.setHidden(not matches)
            if matches and first is None:
                first = item
        current = self.templates.currentItem()
        if current is None or current.isHidden():
            self.templates.setCurrentItem(first)
        if self.templates.currentItem():
            self.templates.scrollToItem(self.templates.currentItem())

    def template_changed(self, item, previous):
        if item is None:
            self.template_details.setText("No matching templates.")
        else:
            template_id = item.data(Qt.ItemDataRole.UserRole)
            # The backend uses the native Attack row for an empty template choice.
            record = self.catalog.template_for(template_id or None)
            if record is None:
                self.template_details.setText("Basic attack data is unavailable. Choose a listed skill.")
            elif len(record.row) <= 36:
                self.template_details.setText(f"{record.name} has an incomplete battle skill record.")
            else:
                row = record.row
                self.template_details.setText(
                    f"{record.name}  ·  Power {row[23]}  ·  SP {row[36]}  ·  "
                    f"Action {row[10]}  ·  Effect {row[12]}"
                )
            if not self.description.document().isModified():
                self.description.setPlainText(record.description if record else "")
                self.description.document().setModified(False)
        self.update_button()

    def update_button(self):
        self.error.hide()
        self.create_button.setEnabled(bool(self.name_edit.text().strip()) and self.templates.currentItem() is not None)

    def accept(self):
        item = self.templates.currentItem()
        if item is None or not self.name_edit.text().strip():
            return
        description = self.description.toPlainText()
        try:
            self.draft = self.catalog.create(
                self.skill_id.value(), self.name_edit.text().strip(),
                template_id=item.data(Qt.ItemDataRole.UserRole) or None,
                description=description if self.description.document().isModified() or not description else None,
            )
        except (ValueError, OSError) as exc:
            self.error.setText(str(exc))
            self.error.show()
            return
        super().accept()


def create_skill_dialog(parent, catalog, template_id=0, *, destination_hint=""):
    dialog = SkillAuthorDialog(parent, catalog, template_id, destination_hint=destination_hint)
    return dialog.draft if dialog.exec() == QDialog.DialogCode.Accepted else None
