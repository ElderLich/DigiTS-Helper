"""Regression tests run against temporary mod payloads, never installed mods."""
import csv
import os
import re
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.chdir(ROOT)

from PyQt6.QtWidgets import QApplication
import digimon_editor as gui
from Data_Loader import DigimonData, MBELoader
from Mod_Tables import (BUFF_SET_HEADER, SKILL_HEADER, chrono_forms_for,
                        load_optional_model_tables, read_table)


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as source:
        return list(csv.reader(source))


class ModRoundtripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.editor = gui.DigimonEditor()
        cls.editor._clear_mvgl_fileloader_cache = lambda: ''
        cls.editor._load_initial_digimon_list = lambda: None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'dsts-loader'
        self.root.mkdir()
        self.editor.active_dsts_loader_root = self.root
        self.editor.current_digimon = None
        self.editor.current_advanced_skill_data_root = None
        self.editor._buff_set_cache.clear()

    def specimen(self, identity=55015):
        return DigimonData(
            id=identity, chr_id=f'chr{identity}', char_key=f'DIGIMON{identity}',
            name='Roundtrip', field_guide_id=601, script_id=identity,
            model_locator_data={'chr_id': f'chr{identity}', 'locator_ref': 'chr307LOC'},
            model_locator_motion_data=[{'motion_key': f'chr{identity}_bs01', 'motion_name': 'bs02'}],
            lod_data={'lod_distance_1': 22, 'lod_distance_2': 88, 'lod_distance_3': 500, 'lod_distance_8': 123},
            lod_model_data={'chr_id': f'chr{identity}', 'lod_model_ref': 'custom_lod',
                            'raw_data': [f'chr{identity}', '', 'custom_lod', 'extra_lod'] + [''] * 7},
            chronodevolution_forms=[387, 307, identity, -1, -1, -1],
            chronodevolution_source_id=identity,
        )

    def test_runtime_headers_match_captured_native_schema_report(self):
        report = (ROOT / 'Header Reports/DSTS_Header_Report.md').read_text(encoding='utf-8')
        skill_section = report.split('## battle_skill.json', 1)[1].split('\n## ', 1)[0]
        for name, header in [('battle_skill_list', SKILL_HEADER), ('buff_set', BUFF_SET_HEADER)]:
            section = skill_section.split('### ' + name + '\n', 1)[1].split('\n### ', 1)[0]
            captured = re.findall(r'^\| \d+ \| `([^`]+)`', section, re.MULTILINE)
            self.assertEqual(header, captured)

    def test_mod_merge_and_import_keep_optional_rows_and_other_digimon(self):
        first, other = self.specimen(), self.specimen(55016)
        for specimen in (first, other):
            self.assertTrue(self.editor._merge_digimon_to_dsts_loader(self.root, specimen, sync_form=False),
                            self.editor.last_merge_error_message)
        first.model_locator_motion_data[0]['motion_name'] = 'bs03'
        self.assertTrue(self.editor._merge_digimon_to_dsts_loader(self.root, first, sync_form=False))
        status = self.root / 'patch/data/digimon_status.mbe/000_digimon_status_data.ap.csv'
        entries = self.editor._parse_digimon_status_csv(status, self.root, load_related=True)
        self.assertEqual({entry.id for entry in entries}, {55015, 55016})
        result = next(entry for entry in entries if entry.id == first.id)
        self.assertEqual(result.model_locator_data['locator_ref'], 'chr307LOC')
        self.assertEqual(result.model_locator_motion_data[0]['motion_name'], 'bs03')
        self.assertEqual(result.lod_data['lod_distance_8'], 123)
        self.assertEqual(result.lod_model_data['raw_data'][2:4], ['custom_lod', 'extra_lod'])
        self.assertEqual(result.chronodevolution_forms, first.chronodevolution_forms)
        removed = self.editor._remove_digimon_from_dsts_loader(self.root, first)
        self.assertEqual(removed['patch/model_locator'], 1)
        self.assertEqual(removed['patch/model_locator_motion'], 1)
        self.assertEqual(removed['patch/chronodevolution'], 1)
        remaining = read_table(self.root / 'patch/data', 'model_locator.mbe', 'model_locator', True)
        self.assertEqual(remaining[1][0], other.chr_id)

    def test_chrono_clone_rekeys_self_only_and_retains_unused_stages(self):
        specimen = self.specimen()
        specimen.id = 99901
        self.assertEqual(chrono_forms_for(specimen), [387, 307, 99901, -1, -1, -1])

    def test_cloning_keeps_source_locator_and_remaps_derived_lod_names(self):
        specimen = self.specimen()
        specimen.lod_model_data['raw_data'][2:4] = ['chr55015_LOD_2', 'chr55015_LOD_3']
        specimen.lod_model_data['lod_model_ref'] = 'chr55015_LOD_2'
        specimen.chr_id = 'chr99901'
        # Writer methods do not require a constructed wizard or event loop.
        class Writer:
            _escape_csv_value = gui.DigimonCreationWizard._escape_csv_value
        writer = Writer()
        gui.DigimonCreationWizard._update_chr_id_references(writer, specimen, 'chr55015', 'chr99901')
        self.assertEqual(specimen.model_locator_data['locator_ref'], 'chr307LOC')
        target = self.root / 'lod.csv'
        gui.DigimonCreationWizard._write_lod_model_ap_csv(writer, target, specimen)
        self.assertEqual(read_csv(target)[1][2:4], ['chr99901_LOD_2', 'chr99901_LOD_3'])

    def test_optional_app_layer_and_patch_precedence(self):
        specimen = self.specimen()
        specimen.model_locator_data = {}
        specimen.model_locator_motion_data = []
        for layer, ref in [('app_0', 'sourceLOC'), ('patch', 'overrideLOC')]:
            path = self.root / layer / 'data/model_locator.mbe'
            path.mkdir(parents=True)
            (path / 'model_locator.ap.csv').write_text('string3 0,string3 1\nchr55015,' + ref + '\n')
        load_optional_model_tables(specimen, [self.root / 'app_0/data', self.root / 'patch/data'], True)
        self.assertEqual(specimen.model_locator_data['locator_ref'], 'overrideLOC')

    def test_custom_buff_definition_and_set_roundtrip(self):
        records = self.editor._buff_definition_records()
        source = records[42]
        row = list(source['row'])
        row[0] = '900123'
        row[6] = '42'
        success, path, message = self.editor._save_buff_definition_to_active_mod(source['header'], row)
        self.assertTrue(success, message)
        options = dict(self.editor._available_buff_effect_options())
        self.assertIn(900123, options)
        self.assertIn('Active Mod', options[900123])
        payload = {'set_id': 900234, 'effects': [{'effect_id': 900123, 'rate': 100,
                                                  'change_percent': 25, 'turn_override': 4}]}
        success, target, message = self.editor._save_buff_set_to_active_mod(payload)
        self.assertTrue(success, message)
        rows = read_csv(target)
        self.assertEqual(rows[0], BUFF_SET_HEADER)
        self.assertEqual(len(rows[1]), 60)
        self.assertEqual(rows[1][6:10], ['900123', '100', '25', '4'])
        self.assertEqual(self.editor._load_buff_set_map(self.root / 'patch/data', True)[900234][0]['effect_id'], 900123)

    def test_numeric_buff_id_entry_is_used_instead_of_stale_combo_selection(self):
        dialog = gui.BuffSetCreatorDialog(None, [(42, 'Fire Resistance Up')], 900100, set(), 'test')
        dialog.effect_combos[0].setCurrentIndex(1)
        dialog.effect_combos[0].setEditText('987654')
        self.assertEqual(dialog.buff_set_data()['effects'][0]['effect_id'], 987654)
        dialog.effect_combos[0].setEditText('Fire nonsense')
        with self.assertRaises(ValueError):
            dialog.buff_set_data()
        dialog.close()

    def test_skill_save_preserves_unedited_fields_and_csv_strings(self):
        data = self.root / 'patch/data'
        directory = data / 'battle_skill.mbe'
        directory.mkdir(parents=True)
        path = directory / '000_battle_skill_list.ap.csv'
        row = ['0'] * 73
        row[0], row[4], row[5], row[33], row[39], row[72] = '123', '456', '789', '7', '1', 'Comma, quote " and\nnewline'
        other = list(row)
        other[0] = '124'
        with path.open('w', newline='') as target:
            csv.writer(target).writerows([SKILL_HEADER, row, other])
        self.assertTrue(self.editor.loader.save_skill_data({'skill_id': 123, 'additional_property': 3,
                                                            'conditional_effect_arg': 25}, data, True))
        saved = read_csv(path)
        self.assertEqual(saved[2], other)
        self.assertEqual([saved[1][i] for i in (4, 5, 33, 39, 72)], [row[i] for i in (4, 5, 33, 39, 72)])
        self.assertEqual(saved[1][27], '3')
        self.assertEqual(saved[1][50], '25')
        self.assertFalse(self.editor.loader.save_skill_data({'skill_id': 999}, data, True))

    def test_skill_choice_ids_match_documented_sparse_enums(self):
        effect = self.editor.skill_additional_prop2_combo
        self.assertIn('Nullifies unfavorable compatibility', effect.itemText(effect.findData(3)))
        damage = self.editor.skill_damage_type_combo
        self.assertIn('Healing', damage.itemText(damage.findData(8)))
        conditional = self.editor.skill_conditional_effect_combo
        self.assertIn('Apply target buff', conditional.itemText(conditional.findData(4)))
        self.assertIn('Restore HP', conditional.itemText(conditional.findData(5)))

    def test_editing_base_skill_creates_only_one_mod_override(self):
        source = self.editor.loader.load_csv(self.editor.loader._battle_skill_csv_path())
        skill_id = int(source[1][0])
        base_file = self.editor.loader._battle_skill_csv_path()
        original = base_file.read_bytes()
        data_root = self.editor._prepare_skill_mod_patch(skill_id)
        rows = read_table(data_root, 'battle_skill.mbe', 'battle_skill_list', True)
        self.assertEqual(rows[0], SKILL_HEADER)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1], source[1])
        self.assertEqual(base_file.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
