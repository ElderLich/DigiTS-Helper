import csv
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import skill_records as sk


class NativeSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = self.root / "mod" / "dsts-loader"
        self.data = self.root / "data"
        self.text = self.root / "text"
        dlc_data = self.root / "dlc_data"
        dlc_text = self.root / "dlc_text"
        self.loader = SimpleNamespace(data_path=self.data, text_path=self.text,
                                      iter_dlc_data_roots=lambda: [("01", dlc_data)],
                                      iter_dlc_text_roots=lambda: [("01", dlc_text)])
        base = Path(__file__).resolve().parents[1] / "Base/data/battle_skill.mbe/000_battle_skill_list.csv"
        with base.open(encoding="utf-8", newline="") as f:
            header, *rows = csv.reader(f)
        self.donors = {int(row[0]): row for row in rows if row and row[0] in {"10011", "20371", "20372"}}
        self.write(self.data / "battle_skill.mbe/000_battle_skill_list.csv", header, self.donors.values())
        self.write(self.text / "skill_name.mbe/000_Sheet1.csv", ["key", "text"],
                   [["20371", "Biting Crush"], ["20372", "Tail Strike"], ["35000", "Reserved"]])
        self.write(self.text / "skill_explanation.mbe/000_Sheet1.csv", ["key", "text"],
                   [["20372", 'First line,\n"second" line.']])
        row = self.donors[20371].copy()
        row[0], row[4] = "30001", "34000"
        self.write(dlc_data / "battle_skill_dlc01.mbe/0_battle_skill_list.csv", header, [row])
        self.write(dlc_text / "skill_name_dlc01.mbe/00_Sheet1.csv", ["key", "text"], [["34000", "DLC skill"]])

    def write(self, path, header, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)

    def catalog(self, drafts=(), mods=()):
        return sk.SkillCatalog.load(self.loader, mods, self.payload, drafts)

    def test_independent_skills_keep_donor_fields_text_and_keyed_voice(self):
        voice = sk.BOUND_SHEETS["battle_skill_voice_number"][1]
        self.write(self.data / "battle_skill.mbe/007_battle_skill_voice_number.csv", voice, [["20371", "", "2", ""]])
        cat = self.catalog()
        auto = cat.create(61001, 'Seventh Lightning', template_id=20371)
        fixed = cat.create(61002, 'Biting Crush Triadens', template_id=20372)
        self.assertEqual(auto.row[5], "0")
        self.assertEqual(fixed.row[5], "61002")
        self.assertEqual(auto.row[6:], tuple(self.donors[20371][6:]))
        self.assertEqual(fixed.row[6:], tuple(self.donors[20372][6:]))
        clone_of_draft = self.catalog([fixed]).create(61003, "Third", template_id=61002)
        self.assertEqual(clone_of_draft.row[5], "61003")
        sk.commit_skill_records(self.payload, [auto, fixed], self.loader)
        reopened = self.catalog()
        self.assertEqual(reopened.records[61002].description, 'First line,\n"second" line.')
        self.assertEqual(reopened.records[61001].bound_rows, (("battle_skill_voice_number", ("61001", "", "2", "")),))
        self.assertEqual(reopened.records[61002].name, "Biting Crush Triadens")
        self.assertEqual(reopened.records[20372].name, "Tail Strike")

    def test_reserved_ids_include_text_dlc_mod_and_pending_skills(self):
        other = self.root / "Other/dsts-loader"
        row = self.donors[20371].copy()
        row[0], row[4], row[5] = "61000", "62000", "62001"
        self.write(other / "patch/data/battle_skill.mbe/0_battle_skill_list.ap.csv", sk.SKILL_HEADER,
                   [row, ["70000", "", "", "", "bad name key", "0"],
                    ["71000", "", "", "", "71000", "0"], ["20371", "", "", "", "999999", "0"]])
        cat = self.catalog([self.catalog().create(61001, "Pending")], [other])
        self.assertEqual(cat.records[30001].name, "DLC skill")
        self.assertEqual(cat.records[20371].row, tuple(self.donors[20371]))
        self.assertNotIn(71000, cat.records)
        for key in (30001, 34000, 35000, 61000, 61001, 62000, 62001, 70000, 71000, 999999):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "already used"):
                cat.create(key, "New")
        draft = self.catalog().create(61000, "Stale")
        with self.assertRaisesRegex(ValueError, "already used"):
            sk.commit_skill_records(self.payload, [draft], self.loader, [other])
        self.assertFalse(list(self.payload.rglob("*.csv")))

    def test_save_failure_and_caller_failure_restore_payload(self):
        existing = self.payload / "patch/data/battle_skill.mbe/00_battle_skill_list.ap.csv"
        self.write(existing, sk.SKILL_HEADER, [])
        before = existing.read_bytes()
        draft = self.catalog().create(61001, "New", template_id=20372)
        replace_file = sk._replace

        def fail_name(path, data):
            if path.parent.name == "skill_name.mbe":
                raise PermissionError("Name table is open")
            replace_file(path, data)

        with patch.object(sk, "_replace", side_effect=fail_name), self.assertRaises(PermissionError):
            sk.commit_skill_records(self.payload, [draft], self.loader)
        self.assertEqual(existing.read_bytes(), before)
        with self.assertRaisesRegex(RuntimeError, "Digimon export failed"):
            with sk.skill_record_transaction(self.payload, [draft], self.loader):
                raise RuntimeError("Digimon export failed")
        self.assertEqual(list(self.payload.rglob("*.csv")), [existing])
        self.assertEqual(existing.read_bytes(), before)
        sk.commit_skill_records(self.payload, [draft], self.loader)
        self.assertEqual(self.catalog().records[61001].name, "New")

    def test_append_to_extracted_named_sheets_and_preserve_their_existing_rows(self):
        from shutil import copyfile

        battle = self.payload / "patch/data/battle_skill.mbe/000_battle_skill_list.csv"
        battle.parent.mkdir(parents=True)
        copyfile(self.data / "battle_skill.mbe/000_battle_skill_list.csv", battle)
        names = self.payload / "patch_text01/text/skill_name.mbe/000_Sheet1.csv"
        self.write(names, ["key", "text"], [["20371", "Existing, quoted"]])
        previous = battle.read_bytes(), names.read_bytes()
        draft = self.catalog().create(61003, "New skill", template_id=20371)
        sk.commit_skill_records(self.payload, [draft], self.loader)
        self.assertTrue(battle.read_bytes().startswith(previous[0]))
        self.assertTrue(names.read_bytes().startswith(previous[1]))
        sk.save_skill_name_override(self.payload, 61003, "Edited skill")
        cat = self.catalog()
        self.assertEqual((cat.records[61003].name, cat.records[20371].name), ("Edited skill", "Existing, quoted"))

    def test_blank_defaults_renaming_and_native_limits(self):
        draft = self.catalog().create(61000, "New")
        self.assertEqual(draft.row[5:], tuple(self.donors[10011][5:]))
        self.assertEqual(self.catalog().create(sk.MAX_SKILL_ID, "High ID").row[0], "2147483647")
        sk.commit_skill_records(self.payload, [draft], self.loader)
        path = self.payload / "patch_text01/text/skill_name.mbe/000_Sheet1.ap.csv"
        extra = b'\r\n"61001","Other,\r\nquoted"\r\n'
        path.write_bytes(path.read_bytes() + extra)
        sk.save_skill_name_override(self.payload, 61000, 'New, "name"')
        self.assertTrue(path.read_bytes().endswith(extra))
        self.assertEqual(self.catalog().records[61000].name, 'New, "name"')
        bad = self.catalog().create(63000, "Invalid")
        row = list(bad.row)
        row[40] = "256"
        with self.assertRaisesRegex(ValueError, "native range"):
            sk.commit_skill_records(self.payload, [replace(bad, row=tuple(row))], self.loader)
