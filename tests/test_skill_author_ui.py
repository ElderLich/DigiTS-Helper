import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6 import sip
from PyQt6.QtWidgets import QApplication, QComboBox, QPushButton, QSpinBox

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from Data_Loader import MBELoader
from digimon_editor import DigimonCreationWizard
from skill_author_dialog import SkillAuthorDialog
from skill_records import SkillCatalog


class SkillAuthorUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        base = Path(__file__).resolve().parents[1] / "data/Base"
        cls.loader = MBELoader(base / "data", base / "text")
        cls.catalog = SkillCatalog.load(cls.loader)

    def test_template_search_and_duplicate_id(self):
        dialog = SkillAuthorDialog(None, self.catalog, 20371)
        self.addCleanup(sip.delete, dialog)
        self.assertIn("Biting Crush", dialog.template_details.text())
        dialog.name_edit.setText("New move")
        dialog.search.setText("no matching skill here")
        self.assertFalse(dialog.create_button.isEnabled())
        dialog.search.setText("20372")
        self.assertIn("Tail Strike", dialog.template_details.text())
        new_id = dialog.skill_id.value()
        dialog.skill_id.setValue(20372)
        dialog.accept()
        self.assertIsNone(dialog.draft)
        self.assertTrue(dialog.error.text())
        dialog.skill_id.setValue(new_id)
        dialog.description.selectAll()
        dialog.description.insertPlainText("Distinct description.")
        dialog.accept()
        self.assertEqual(dialog.draft.description, "Distinct description.")
        self.assertEqual(dialog.draft.row[10:], self.catalog.records[20372].row[10:])
        self.assertNotIn(new_id, self.catalog.records)

    def test_empty_slot_can_create_with_basic_attack_defaults(self):
        dialog = SkillAuthorDialog(None, self.catalog)
        self.addCleanup(sip.delete, dialog)
        self.assertEqual(dialog.templates.currentItem().text(), "Basic attack defaults")
        dialog.name_edit.setText("Seventh Lightning")
        dialog.accept()
        self.assertEqual(dialog.draft.name, "Seventh Lightning")
        self.assertEqual(dialog.draft.row[10:], self.catalog.template_for().row[10:])

    def test_wizard_slot_assignment_and_back_navigation(self):
        wizard = DigimonCreationWizard(loader=self.loader)
        self.addCleanup(sip.delete, wizard)
        # Use only the fixture catalog and wizard drafts.
        with patch.object(wizard, "_skill_mod_roots", return_value=[]):
            wizard.page(0).template_search.setText("chr037")
            wizard.setStartId(6)
            wizard.show()
            self.app.processEvents()
            page = wizard.page(6)
            slots = page.signature_skills_editor
            slots.load_skills([{"id": 20371, "slot": -1}, {"id": 0, "slot": 2}, {"id": 20372, "slot": 3}])
            first, _, third = slots.skill_widgets[:3]
            first.findChild(QComboBox).showPopup()
            first.findChild(QComboBox).hidePopup()
            record = self.catalog.create(39_519_901, "Biting Crush Triadens", template_id=20372)
            with patch("digimon_editor.create_skill_dialog", return_value=record) as create:
                third.findChild(QPushButton, "create_skill_2").click()
            self.assertEqual(create.call_args.args[2], 20372)
            self.assertEqual(slots.get_skills()[:3], [
                {"id": 20371, "slot": -1}, {"id": 0, "slot": 2}, {"id": record.skill_id, "slot": 3},
            ])
            self.assertEqual(page.skill_drafts, {record.skill_id: record})
            self.assertEqual(third.findChild(QComboBox).currentData(), record.skill_id)
            self.assertIn(record.name, third.findChild(QComboBox).currentText())
            slots.populate_skill_combo(0)
            self.assertGreater(first.findChild(QComboBox).findData(record.skill_id), 0)
            self.assertIn(record.skill_id, page.generic_skills_editor.available_skills())
            wizard.next()
            wizard.back()
            self.assertEqual(wizard.currentId(), 6)
            self.assertEqual(slots.get_skills()[2], {"id": record.skill_id, "slot": 3})
            self.assertEqual(first.findChild(QSpinBox, "skill_level_0").value(), -1)
