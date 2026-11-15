"""Installed mod inventory and single-cell edits, using temporary source files."""
import csv
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QComboBox, QDialogButtonBox

from field_guide_slots import change_slot, scan_inventory
from field_guide_slots_dialog import FieldGuideSlotsDialog


class FixtureLoader:
    def __init__(self, root):
        self.data_path = root / "data"
        self.text_path = root / "text"
        self.dlc = []

    def _resolve_prefixed_file(self, path):
        return path

    def iter_dlc_csv_files(self, kind, folder, sheet):
        return self.dlc if kind == "data" else []


class SlotTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve() / "Mods"
        self.root.mkdir()
        self.loader = FixtureLoader(self.root.parent / "Base")
        self.base = self.loader.data_path / "digimon_status.mbe/000_digimon_status_data.csv"
        self.status(self.base, [(8, 511), (9, 17)], typed=False)
        self.first = self.mod("One")
        self.second = self.mod("Two")
        self.status(self.first, [(55, 511), (56, 516)])
        self.status(self.second, [(58, 511)])

    def mod(self, name):
        folder = self.root / name
        folder.mkdir()
        (folder / "ModConfig.json").write_text(json.dumps({
            "ModId": f"mod.{name}", "ModName": f"Install {name}", "ModVersion": "1.2",
        }))
        return folder / "dsts-loader/patch/data/digimon_status.mbe/000_digimon_status_data.ap.csv"

    @staticmethod
    def status(path, pairs, typed=True):
        headers = [f"int32 {i}" for i in range(136)]
        indices = (0, 2, 3, 131, 132)
        selected = (headers[0], "string2 2", "string2 3", headers[131], headers[132]) if typed else (
            "id", "char_key", "chr_id", "field_guide_id", "script_id")
        for index, heading in zip(indices, selected):
            headers[index] = heading
        out = io.StringIO(newline="")
        writer = csv.writer(out, lineterminator="\r\n", quoting=csv.QUOTE_ALL)
        writer.writerow(headers)
        for identity, slot in pairs:
            row = ["-1"] * len(headers)
            row[0], row[2], row[3] = identity, f"key_{identity}", f"chr{identity}"
            row[1] = 'élan,"a"\r\nsecond line'
            row[131], row[132] = slot, identity
            writer.writerow(row)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(out.getvalue().encode("utf-8-sig"))

    def inventory(self):
        return scan_inventory(self.root, self.loader)

    def selected(self, identity=55):
        return self.inventory().ids[identity][0]

    def test_conflicts_names_metadata_and_unsupported_entries(self):
        self.mod("Empty")
        packed = self.mod("Packed").parent
        packed.parent.mkdir(parents=True)
        packed.write_bytes(b"EXPA")
        dlc = self.root.parent / "DLC/000_digimon_status_data.csv"
        self.status(dlc, [(9009, 17)], typed=False)
        self.loader.dlc = [("03", dlc)]
        names = self.root / "One/dsts-loader/patch_text01/text/char_name.mbe/000_Sheet1.ap.csv"
        names.parent.mkdir(parents=True)
        names.write_text("string2 0,string2 1\nkey_55,Shoutmon X7\n", encoding="utf-8")
        # A backup-looking loader tree outside either mod payload must not count.
        self.status(self.root / "One/backup/dsts-loader/patch/data/digimon_status.mbe/000_digimon_status_data.ap.csv", [(100, 800)])
        d = self.inventory()
        self.assertEqual(len(d.mods), 4)
        self.assertEqual(d.mods[self.root / "One"], ("mod.One", "1.2"))
        self.assertEqual(len(d.slots[511]), 3)
        self.assertEqual(d.state(d.ids[55][0]), "Slot conflict")
        self.assertEqual(d.ids[55][0].name, "Shoutmon X7")
        self.assertEqual(d.state(d.ids[9][0]), "Shared stock slot")
        self.assertNotIn(800, d.slots)
        self.assertEqual([(e.source, d.state(e)) for e in d.entries if e.mod and not e.record], [
            ("Install Empty", "No status rows"), ("Install Packed", "Packed status table")])
        self.assertTrue(any(str(packed) in warning for warning in d.warnings))

    def test_save_changes_only_the_selected_field_and_keeps_original(self):
        original = self.first.read_bytes()
        other = self.second.read_bytes()
        change = change_slot(self.root, self.loader, self.selected(56), 570)
        self.assertEqual(change.backup.read_bytes(), original)
        self.assertEqual(self.first.read_bytes(), original.replace(b'"516"', b'"570"', 1))
        self.assertEqual(change.table, self.first)
        self.assertEqual(change.payload, self.root / "One/dsts-loader")
        self.assertEqual((change.digimon_id, change.old_slot, change.new_slot), (56, 516, 570))
        self.assertEqual(self.second.read_bytes(), other)
        self.assertEqual(self.inventory().ids[56][0].slot, 570)
        self.assertEqual(list(self.first.parent.glob(".guide-*")), [])

    def test_stale_row_occupied_destination_and_write_failure(self):
        selected = self.selected()
        self.status(self.second, [(58, 512)])
        with self.assertRaisesRegex(ValueError, "already used"):
            change_slot(self.root, self.loader, selected, 512)
        self.status(self.first, [(55, 511), (56, 666)])
        with self.assertRaisesRegex(ValueError, "changed"):
            change_slot(self.root, self.loader, selected, 512)
        selected = self.selected()
        before = self.first.read_bytes()
        with patch("field_guide_slots.os.replace", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                change_slot(self.root, self.loader, selected, 700)
        self.assertEqual(self.first.read_bytes(), before)
        self.assertEqual(list(self.first.parent.glob(".guide-*")), [])
        for slot in (12, -1, 1000, None):
            with self.assertRaises(ValueError):
                change_slot(self.root, self.loader, selected, slot)
        with self.assertRaisesRegex(ValueError, "editable"):
            change_slot(self.root, self.loader, self.selected(8), 700)

    def test_distinguishes_id_overlap_and_exact_shared_override(self):
        self.status(self.first, [(8, 511), (9, 555), (44, -1)])
        self.status(self.second, [])
        d = self.inventory()
        self.assertEqual(d.state(d.ids[8][0]), "Shared entry")
        self.assertEqual(d.state(d.ids[9][0]), "ID overlap")
        self.assertEqual(d.state(d.ids[44][0]), "Unassigned")

    def test_simultaneous_saves_cannot_claim_same_slot(self):
        one, two = self.selected(55), self.selected(58)

        def competing_save(root, loader):
            with self.assertRaisesRegex(ValueError, "in progress"):
                change_slot(root, loader, two, 720)
            return scan_inventory(root, loader)

        with patch("field_guide_slots.scan_inventory", side_effect=competing_save):
            change_slot(self.root, self.loader, one, 720)
        with self.assertRaisesRegex(ValueError, "already used"):
            change_slot(self.root, self.loader, two, 720)

    def test_dialog_filters_sorts_and_edits_installed_copy(self):
        app = QApplication.instance() or QApplication([])
        dialog = FieldGuideSlotsDialog(self.root, self.loader)
        dialog.show()
        app.processEvents()
        dialog.search.setText("mod.One")
        dialog.table.sortItems(4, Qt.SortOrder.DescendingOrder)
        app.processEvents()
        visible = [r for r in range(dialog.table.rowCount()) if not dialog.table.isRowHidden(r)]
        self.assertEqual([dialog.table.item(r, 4).text() for r in visible], ["56", "55"])
        dialog.table.selectRow(visible[0])
        self.assertTrue(dialog.edit.isEnabled())
        self.assertEqual(dialog.selected().digimon_id, 56)
        self.assertIn("v1.2", dialog.detail.text())

        def choose():
            sheet = app.activeModalWidget()
            choices = sheet.findChild(QComboBox)
            choices.setCurrentIndex(choices.findData(555))
            sheet.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()

        QTimer.singleShot(0, choose)
        dialog.edit.click()
        self.assertEqual(len(dialog.changes), 1)
        self.assertEqual(dialog.changes[0].new_slot, 555)
        self.assertEqual(self.selected(56).slot, 555)
        self.assertIn("Saved", dialog.detail.text())
        dialog.close()


if __name__ == "__main__":
    unittest.main()
