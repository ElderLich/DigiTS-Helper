import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QDir

from field_guide_unlock import (
    AUX_OFFSET, CAPACITY, GUIDE_OFFSET, RECORD_SIZE, REGISTERED, SAVE_SIZE,
    _aes, apply_unlock, find_steam_save_directory, open_field_guide_unlock, preview_unlock,
)


class SteamSaveLocationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.client = self.root / "Custom Steam"
        self.apps = self.client / "steamapps"
        self.apps.mkdir(parents=True)
        self.registry = patch("field_guide_unlock._steam_client_paths", return_value=[self.client])
        self.registry.start()
        self.addCleanup(self.registry.stop)

    def make_saves(self, library, name="Digimon Story Time Stranger"):
        folder = library / "steamapps" / "common" / name / "gamedata" / "savedata"
        folder.mkdir(parents=True)
        return folder

    def test_picker_defaults_to_game_and_shows_both_slot_naming_schemes(self):
        expected = self.make_saves(self.client)
        with patch("field_guide_unlock.QFileDialog.getOpenFileName", return_value=("", "")) as picker:
            open_field_guide_unlock(None, [])
        _, _, folder, filters = picker.call_args.args
        self.assertEqual(Path(folder), expected)
        patterns = filters.split("(", 1)[1].split(")", 1)[0].split()
        for name in ("0000.bin", "0123.bin", "savedata01.dat"):
            self.assertTrue(QDir.match(patterns, name))
        for name in ("slot_0000.bin", "sysdata_dx11.bin", "0000.bin.pre-guide-test.bak"):
            self.assertFalse(QDir.match(patterns, name))
        autosaves = filters.split("Autosave only (", 1)[1].split(")", 1)[0].split()
        self.assertEqual(autosaves, ["0000.bin", "savedata00.dat"])

    def test_manifest_in_secondary_library_takes_priority_over_stale_folder(self):
        self.make_saves(self.client)
        library = self.root / "Game Library"
        expected = self.make_saves(library, "Time Stranger Custom")
        escaped = str(library).replace("\\", "\\\\")
        (self.apps / "libraryfolders.vdf").write_text(
            f'"libraryfolders"\n{{\n"1"\n{{\n"path" "{escaped}"\n"apps"\n{{\n"1984270" "12345"\n}}\n}}\n}}',
            encoding="utf-8-sig")
        (library / "steamapps/appmanifest_1984270.acf").write_text(
            '"AppState"\n{\n"installdir" "Time Stranger Custom"\n}', encoding="utf-8")
        self.assertEqual(find_steam_save_directory(), expected)

    def test_legacy_library_and_missing_game(self):
        library = self.root / "Games"
        (self.apps / "libraryfolders.vdf").write_text(
            f'"LibraryFolders"\n{{\n"1" "{library.as_posix()}"\n}}', encoding="utf-8")
        self.assertIsNone(find_steam_save_directory())
        self.assertEqual(self.make_saves(library), find_steam_save_directory())


@unittest.skipUnless(os.name == "nt", "PC save encryption uses Windows CNG")
class UnlockTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.slot = Path(directory.name) / "savedata00.dat"
        self.plain = bytearray(SAVE_SIZE)
        header = b"5, 3097152, 176, 0, Test Agent"
        self.plain[:len(header)] = header
        self.record(0, 22, 0x8101, 0x2345, 0xFEDCBA9876543210, 0x8632)
        self.record(1, 99882, 0x1026, 0x0200, 0xABCDEF, 0x8050)
        self.record(2, 41, 0, 0, 0, 0)
        self.save()

    def record(self, index, identifier, flags, unknown=0, details=0, aux=0):
        struct.pack_into("<iHHQ", self.plain, GUIDE_OFFSET + index * RECORD_SIZE,
                         identifier, flags, unknown, details)
        struct.pack_into("<H", self.plain, AUX_OFFSET + index * 2, aux)

    def save(self):
        self.slot.write_bytes(_aes(bytes(self.plain), encrypt=True))

    def test_changes_only_the_registration_bit_and_new_id(self):
        original = self.slot.read_bytes()
        identifiers = [22, 99882, 751234, 22]
        plan = preview_unlock(self.slot, identifiers)
        self.assertEqual((plan.existing, plan.updated, plan.added), (1, 1, 1))
        self.assertEqual(self.slot.read_bytes(), original)
        backup = apply_unlock(plan)
        self.assertEqual(backup.read_bytes(), original)
        self.plain[GUIDE_OFFSET + 4] |= REGISTERED
        self.record(3, 751234, REGISTERED)
        self.assertEqual(_aes(self.slot.read_bytes(), encrypt=False), self.plain)
        self.assertIsNone(apply_unlock(preview_unlock(self.slot, identifiers)))
        self.assertEqual([p.resolve() for p in self.slot.parent.glob("*.bak")], [backup])

    def test_rejects_stale_preview_and_retains_failed_write_backup(self):
        plan = preview_unlock(self.slot, [22])
        self.plain[0x1200] = 42
        self.save()
        original = self.slot.read_bytes()
        with self.assertRaisesRegex(ValueError, "changed"):
            apply_unlock(plan)
        self.assertEqual(list(self.slot.parent.glob("*.bak")), [])
        with patch("field_guide_unlock.os.replace", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                apply_unlock(preview_unlock(self.slot, [22]))
        self.assertEqual(self.slot.read_bytes(), original)
        self.assertEqual(list(self.slot.parent.glob("*.tmp")), [])
        self.assertEqual(next(self.slot.parent.glob("*.bak")).read_bytes(), original)

    def test_rejects_unrecognised_layout_and_record_overflow(self):
        self.record(2, 22, 0)
        self.save()
        with self.assertRaisesRegex(ValueError, "repeated"):
            preview_unlock(self.slot, [22])
        self.record(2, 0, 0, aux=1)
        self.save()
        with self.assertRaisesRegex(ValueError, "empty Field Guide record"):
            preview_unlock(self.slot, [22])
        self.record(2, 0, 0)
        self.save()
        with self.assertRaisesRegex(ValueError, "free records"):
            preview_unlock(self.slot, range(1, CAPACITY + 100))
        self.plain[0] = ord("6")
        self.save()
        with self.assertRaisesRegex(ValueError, "version 5"):
            preview_unlock(self.slot, [22])
        self.slot.write_bytes(b"param file")
        with self.assertRaisesRegex(ValueError, "3,098,176"):
            preview_unlock(self.slot, [22])
