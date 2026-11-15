"""Edit a localized trait name in a mod's native digimon_class_name sheet."""
import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QIODevice, QLockFile, QSaveFile
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
                             QLineEdit, QMessageBox)

from Data_Loader import TRAIT_COLUMNS
from MBE_Editor import MBEEditor


HEADER = ["string2 0", "string 1"]
TABLE = "digimon_class_name.mbe"


def mod_sheet_path(payload, archive):
    if not re.fullmatch(r"app_text\d{2}", archive):
        raise ValueError("Choose a game text language.")
    directory = Path(payload) / archive / "text" / TABLE
    if directory.is_file():
        raise ValueError(f"This mod supplies a packed trait table at {directory}.")
    matches = [p for p in directory.glob("*.csv")
               if re.fullmatch(r"(?:\d+_)?Sheet1\.csv", p.name, re.IGNORECASE)]
    if len(matches) > 1:
        raise ValueError(f"Multiple replacement sheets exist in {directory}.")
    return matches[0] if matches else directory / "000_Sheet1.csv"


def _csv_rows(content, headers):
    try:
        records = csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        if next(records, None) not in headers:
            raise ValueError("Unrecognized trait name table header.")
        return [row for row in records if row]
    except csv.Error as exc:
        raise ValueError(f"Invalid trait name CSV: {exc}") from exc


def _names(rows):
    if any(len(row) != 2 for row in rows):
        raise ValueError("Expected a key and a name on each trait row.")
    names = dict(rows)
    if len(names) != len(rows) or any(str(i) not in names for i in range(len(TRAIT_COLUMNS))):
        raise ValueError("Expected one row per built-in trait in the replacement sheet.")
    return names


def english_mod_names(payload):
    if payload:
        path = mod_sheet_path(payload, "app_text01")
        if path.is_file():
            return _names(_csv_rows(path.read_bytes(), [HEADER]))
    return {}


@dataclass
class TraitNameSheet:
    path: Path
    original: bytes | None
    rows: list

    @classmethod
    def load(cls, payload, archive, extracted_root, english_csv):
        path = mod_sheet_path(payload, archive)
        original = path.read_bytes() if path.is_file() else None
        if original is not None:
            rows = _csv_rows(original, [HEADER])
        else:
            native = Path(extracted_root) / (archive + ".dx11") / "text" / TABLE
            if native.is_file():
                with native.open("rb") as stream:
                    sheets = MBEEditor._parse_mbe_data(stream)
                if (len(sheets) != 1 or sheets[0]["name"] != "Sheet1"
                        or [col["name"] for col in sheets[0]["columns"]] != ["string2", "string"]):
                    raise ValueError(f"Unrecognized trait name table in {native}.")
                rows = sheets[0]["rows"]
            elif archive == "app_text01":
                rows = _csv_rows(Path(english_csv).read_bytes(), [HEADER, ["key", "text"]])
            else:
                raise ValueError(f"Set the extracted game folder in Configure Paths to read {native}.")
        _names(rows)
        return cls(path, original, rows)

    def rename(self, trait_id, name):
        name = name.strip()
        if trait_id not in range(len(TRAIT_COLUMNS)) or not name or any(c in name for c in "\r\n\x00"):
            raise ValueError("Choose a built-in trait and enter a single-line name.")
        rows = [[key, name if key == str(trait_id) else text] for key, text in self.rows]
        if rows == self.rows:
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(self.path) + ".lock")
        if not lock.tryLock(0):
            raise OSError("The trait sheet is already being edited.")
        try:
            current = self.path.read_bytes() if self.path.exists() else None
            if current != self.original:
                raise ValueError("The trait sheet changed. Reopen it to load the latest names.")
            output = io.StringIO(newline="")
            output.write(",".join(HEADER) + "\n")
            csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator="\n").writerows(rows)
            data = output.getvalue().encode("utf-8")
            target = QSaveFile(str(self.path))
            if not target.open(QIODevice.OpenModeFlag.WriteOnly):
                raise OSError(target.errorString())
            if target.write(data) != len(data):
                target.cancelWriting()
                raise OSError(target.errorString())
            if not target.commit():
                raise OSError(target.errorString())
            return True
        finally:
            lock.unlock()


class TraitRenameDialog(QDialog):
    def __init__(self, payload, languages, extracted_root, english_csv, parent):
        super().__init__(parent)
        self.setWindowTitle("Rename trait for mod")
        self.setMinimumWidth(490)
        self.payload = payload
        self.extracted_root = extracted_root
        self.english_csv = english_csv
        self.sheet = None
        form = QFormLayout(self)
        form.addRow("Mod folder", QLabel(str(payload)))
        self.language = QComboBox()
        for archive, label in languages:
            self.language.addItem(label, archive)
        self.language.setCurrentIndex(self.language.findData("app_text01"))
        form.addRow("Language", self.language)
        self.trait = QComboBox()
        form.addRow("Trait", self.trait)
        self.name = QLineEdit()
        form.addRow("New name", self.name)
        self.note = QLabel()
        self.note.setWordWrap(True)
        form.addRow(self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.language.currentIndexChanged.connect(self.load_language)
        self.trait.currentIndexChanged.connect(self.select_trait)
        self.name.textChanged.connect(self.update_save)
        self.load_language()

    def load_language(self):
        previous = self.trait.currentData()
        self.sheet = None
        self.trait.clear()
        try:
            self.sheet = TraitNameSheet.load(self.payload, self.language.currentData(),
                                              self.extracted_root, self.english_csv)
            self.note.setText("This changes the displayed name for every Digimon using this trait in the selected language.")
            names = dict(self.sheet.rows)
            for i in sorted(range(len(TRAIT_COLUMNS)), key=lambda i: names[str(i)].casefold()):
                self.trait.addItem(f"{names[str(i)]} (ID {i})", i)
            if previous is not None:
                self.trait.setCurrentIndex(self.trait.findData(previous))
        except (ValueError, OSError) as exc:
            self.note.setText(str(exc))
        self.select_trait()

    def select_trait(self):
        key = self.trait.currentData()
        self.name.setEnabled(key is not None)
        self.name.setText(dict(self.sheet.rows)[str(key)] if key is not None else "")
        self.update_save()

    def update_save(self):
        key, name = self.trait.currentData(), self.name.text().strip()
        self.save_button.setEnabled(bool(name and key is not None and name != dict(self.sheet.rows)[str(key)]))

    def save(self):
        try:
            if self.sheet.rename(self.trait.currentData(), self.name.text()):
                self.accept()
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Could not rename trait", f"{exc}\n\nIf the CSV is open elsewhere, close it and retry.")
