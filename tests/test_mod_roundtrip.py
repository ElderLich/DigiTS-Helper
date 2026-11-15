"""Regression tests run against temporary mod payloads, never installed mods."""
import csv
import os
import re
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.chdir(ROOT)

from PyQt6.QtWidgets import QApplication, QToolTip
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QHelpEvent
import digimon_editor as gui
from Data_Loader import DigimonData, MBELoader, read_trait_flags
from trait_names import TraitNameSheet, english_mod_names
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

    @classmethod
    def tearDownClass(cls):
        # Dispose native widgets while QApplication and Python event filters are
        # still alive, rather than relying on interpreter shutdown order.
        cls.editor.close()
        cls.editor.deleteLater()
        cls.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        cls.app.processEvents()
        cls.editor = None

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

    def test_edit_installed_guide_slot_preserves_form_edits_and_other_mods(self):
        current = self.specimen()
        current.imported_dsts_loader_root = str(self.root)
        other = self.specimen()
        other.imported_dsts_loader_root = str(self.root.parent / 'Other' / 'dsts-loader')
        self.editor.current_digimon = current
        self.editor._remember_loaded_identity(current)
        self.editor.field_guide_id_spin.setValue(601)
        self.editor.has_unsaved_changes = True
        with patch.object(self.editor.loader, 'imported_digimon', [current, other], create=True):
            change = SimpleNamespace(payload=self.root, digimon_id=current.id, new_slot=602)
            self.editor._sync_edited_field_guide_slot(change)
            self.assertEqual(self.editor.field_guide_id_spin.value(), 602)
            self.assertEqual(self.editor.loaded_digimon_identity['field_guide_id'], 602)
            self.assertEqual(current.field_guide_id, 602)
            self.assertEqual(other.field_guide_id, 601)
            self.editor.field_guide_id_spin.setValue(650)
            change.new_slot = 603
            self.editor._sync_edited_field_guide_slot(change)
            self.assertEqual(self.editor.field_guide_id_spin.value(), 650)
            self.assertEqual(self.editor.loaded_digimon_identity['field_guide_id'], 603)
            self.assertTrue(self.editor.has_unsaved_changes)
        self.editor.has_unsaved_changes = False

    def test_renamed_editor_reads_previous_path_settings(self):
        legacy = self.root / gui.LEGACY_PATH_SETTINGS_FILE_NAME
        legacy.write_text('{"reloaded_mods_path":"original"}', encoding='utf-8')
        with patch.object(gui, 'get_app_settings_dir', return_value=self.root), patch.object(gui, '_PATH_SETTINGS_CACHE', None):
            self.assertEqual(gui.load_path_settings()[gui.PATH_SETTINGS_MODS_KEY], 'original')
            gui.save_path_settings({gui.PATH_SETTINGS_MODS_KEY: 'updated'})
            gui._PATH_SETTINGS_CACHE = None
            self.assertEqual(gui.load_path_settings()[gui.PATH_SETTINGS_MODS_KEY], 'updated')
            self.assertTrue((self.root / gui.PATH_SETTINGS_FILE_NAME).is_file())
            self.assertIn('original', legacy.read_text(encoding='utf-8'))

    def test_classification_tooltips_follow_template_and_hovered_row(self):
        template = self.specimen()
        template.growth_pattern_id = 2
        template.personality_id = 16
        page = gui.ClassificationPage(SimpleNamespace(loader=self.editor.loader, template_digimon=template))
        self.addCleanup(page.close)
        page.show()
        self.app.processEvents()

        for combo, editor_combo, selected, hover_id, text, hover_text in (
            (page.growth_combo, self.editor.growth_pattern_combo, 2, 1, '2–20', '2–35'),
            (page.personality_combo, self.editor.personality_combo, 16, 11, 'INT and HP', 'DEF and ATK'),
        ):
            self.assertEqual(combo.currentData(), selected)
            self.assertIn(text, combo.toolTip())
            combo.showPopup()
            view = combo.view()
            row = combo.findData(hover_id)
            index = combo.model().index(row, 0)
            view.scrollTo(index)
            self.app.processEvents()
            pos = view.visualRect(index).center()
            self.assertEqual(view.indexAt(pos), index)
            event = QHelpEvent(QEvent.Type.ToolTip, pos, view.viewport().mapToGlobal(pos))
            self.app.sendEvent(view.viewport(), event)
            self.assertIn(hover_text, QToolTip.text())
            self.assertEqual(QToolTip.text(), editor_combo.itemData(editor_combo.findData(hover_id), Qt.ItemDataRole.ToolTipRole))
            self.assertEqual(combo.currentData(), selected)
            combo.hidePopup()
            combo.setCurrentIndex(row)
            self.assertIn(hover_text, combo.toolTip())
            QToolTip.hideText()

    def test_wizard_groups_template_paths_and_retains_edits_on_back(self):
        wizard = gui.DigimonCreationWizard(self.editor, self.editor.loader)
        self.addCleanup(wizard.deleteLater)
        templates, basic, page = wizard.page(0), wizard.page(1), wizard.page(7)
        templates.template_search.setText('chr037')  # Leviamon, as in the reported example
        basic.id_spin.setValue(55015)
        wizard.setStartId(7)
        wizard.show()
        self.app.processEvents()
        self.assertEqual(page.deevolution_list.count(), 3)
        for row, name in enumerate(('Whamon', 'WaruSeadramon', 'SkullSeadramon')):
            self.assertIn(name, page.deevolution_list.item(row).text())
        self.assertIsNone(page.evolution_mode_change_list.item(0).data(Qt.ItemDataRole.UserRole))

        templates.template_search.setText('chr088')  # Omnimon
        page.initializePage()
        self.assertEqual(page.deevolution_jogress_list.count(), 2)
        self.assertEqual(page.deevolution_mode_change_list.count(), 2)
        self.assertEqual(page.evolution_mode_change_list.count(), 2)
        template_paths = list(wizard.template_digimon.evolution_paths)
        removed = page.evolution_mode_change_list.item(1)
        removed_id = page.current_digimon.evolution_paths[removed.data(Qt.ItemDataRole.UserRole)]['to_id']
        page.evolution_mode_change_list.setCurrentItem(removed)
        with patch.object(gui.QMessageBox, 'question', return_value=gui.QMessageBox.StandardButton.Yes), \
                patch.object(gui.QMessageBox, 'information'):
            page.remove_evolution()
        with patch.object(page, '_iter_reloaded_mod_dsts_loader_roots', return_value=[]), \
                patch.object(gui.QMessageBox, 'warning') as warning:
            wizard.next()
        warning.assert_not_called()
        self.assertEqual(wizard.currentId(), 8)
        wizard.back()
        self.assertEqual(wizard.currentId(), 7)
        self.assertNotIn(removed_id, [p['to_id'] for p in page.current_digimon.evolution_paths])
        self.assertEqual(wizard.template_digimon.evolution_paths, template_paths)
        self.assertTrue(all(p['from_id'] == 88 for p in template_paths))
        self.assertTrue(all(p['from_id'] == 55015 for p in page.current_digimon.evolution_paths))

    def test_wizard_dna_and_mode_change_export_and_reopen(self):
        wizard = gui.DigimonCreationWizard(self.editor, self.editor.loader)
        self.addCleanup(wizard.deleteLater)
        wizard.page(0).template_search.setText('chr678')  # MagnaGarurumon
        basic, page = wizard.page(1), wizard.page(7)
        basic.id_spin.setValue(55015)
        basic.chr_id_edit.setText('chr55015')
        basic.name_edit.setText('Wizard test')
        basic.char_key_edit.setText('WIZARD_TEST')
        page.initializePage()
        self.assertIn('ID: 104', page.evolution_jogress_list.item(0).text())

        def select_dna(dialog):
            self.assertEqual(dialog.findChild(gui.QComboBox).currentText(), 'Jogress / DNA')
            dialog.findChild(gui.QTabWidget).setCurrentIndex(1)
            dialog.findChild(gui.QSpinBox).setValue(55017)
            return gui.QDialog.DialogCode.Accepted

        with patch.object(page, '_iter_reloaded_mod_dsts_loader_roots', return_value=[]), \
                patch.object(gui.QDialog, 'exec', select_dna), patch.object(gui.QMessageBox, 'information'), \
                patch.object(page, '_show_evolution_requirements_dialog',
                             return_value={'jogressDbIdA': 55015, 'jogressDbIdB': 55016}):
            page.add_evolution(force_jogress=True)
        self.assertEqual(page.evolution_jogress_list.count(), 2)
        # Revisiting Basic Info must also update the authored DNA partner ID.
        basic.id_spin.setValue(55020)
        page.initializePage()

        def export(digimon, identity, **options):
            self.assertTrue(self.editor._merge_digimon_to_dsts_loader(
                self.root, digimon, original_identity=identity, **options))
            return self.root.parent

        with patch.object(self.editor, 'export_digimon_to_reloaded_mod', side_effect=export), \
                patch.object(gui.QMessageBox, 'critical') as error, patch.object(gui.QMessageBox, 'information'):
            wizard.finish_wizard()
        error.assert_not_called()
        self.assertTrue(wizard.export_succeeded)
        folder = self.root / 'patch/data/evolution.mbe'
        edges = {(int(r[1]), int(r[3]), int(r[5])) for r in read_csv(folder / '001_evolution_to.ap.csv')[1:]}
        self.assertEqual(edges, {(55020, 104, 0), (55020, 675, 2), (675, 55020, 2),
                                 (670, 55020, 0), (55020, 55017, 0), (55016, 55017, 0)})
        conditions = {int(r[0]): r for r in read_csv(folder / '000_evolution_condition.ap.csv')[1:]}
        self.assertEqual(set(conditions), {55020, 55017})
        self.assertEqual((conditions[55017][24], conditions[55017][27]), ('55020', '55016'))
        status = self.root / 'patch/data/digimon_status.mbe/000_digimon_status_data.ap.csv'
        reopened, = self.editor._parse_digimon_status_csv(status, self.root)
        self.editor.load_digimon_data(reopened)
        self.assertEqual(self.editor.evolution_jogress_list.count(), 2)
        self.assertIn('ID: 675', self.editor.evolution_mode_change_list.item(0).text())

    def test_template_filter_clears_hidden_selection_and_resolves_character_id(self):
        wizard = SimpleNamespace(loader=self.editor.loader, template_digimon=None)
        page = gui.TemplateSelectionPage(wizard)
        self.assertEqual(wizard.template_digimon.chr_id, 'chr805')
        page.template_search.setText('LaNtMoN')
        hits = [page.template_list.item(i).text() for i in range(page.template_list.count())
                if not page.template_list.item(i).isHidden()]
        self.assertIn('Gallantmon (chr126)', hits)
        self.assertIn('Gallantmon (chr813)', hits)
        self.assertFalse(page.isComplete())
        page.template_search.setText('CHR813')
        self.assertEqual(wizard.template_digimon.chr_id, 'chr813')
        page.template_search.setText('no such template')
        self.assertFalse(page.isComplete())
        self.assertIn('No matching', page.preview_label.text())
        page.deleteLater()

    def test_sorted_traits_keep_native_indices_through_export_and_import(self):
        tab = self.editor.traits_tab
        labels = [tab.trait_grid.itemAtPosition(row, col).widget().text()
                  for col in range(3) for row in range(14)]
        self.assertEqual(labels, sorted(labels, key=str.casefold))
        specimen = self.specimen()
        table = self.root / 'patch/data/digimon_status.mbe/000_digimon_status_data.ap.csv'
        table.parent.mkdir(parents=True)
        class Writer:
            _escape_csv_value = gui.DigimonCreationWizard._escape_csv_value
        writer = Writer()
        exporter = gui.CSVExporter()
        for i in range(42):
            flags = [n == i for n in range(42)]
            tab.load_traits(flags)
            specimen.traits = tab.get_traits()
            gui.DigimonCreationWizard._write_digimon_status_ap_csv(writer, table, specimen)
            row = read_csv(table)[1]
            self.assertEqual(row[51], str(int(i == 32)))
            self.assertEqual(read_trait_flags(row), flags)
            self.assertEqual(read_trait_flags(exporter._create_digimon_status_row(specimen)), flags)
        parsed, = self.editor._parse_digimon_status_csv(table, self.root, load_related=False)
        self.assertEqual(parsed.traits, specimen.traits)
        row[51] = '-2'
        self.assertTrue(read_trait_flags(row)[32])

    def test_mod_trait_rename_preserves_other_names_and_detects_stale_edits(self):
        english_csv = ROOT / 'Base/text/digimon_class_name.mbe/000_Sheet1.csv'
        source = read_csv(english_csv)[1:]
        args = self.root, 'app_text01', self.root.parent / 'missing dump', english_csv
        first = TraitNameSheet.load(*args)
        stale = TraitNameSheet.load(*args)
        self.assertTrue(first.rename(0, 'Azure, "Knight"'))
        with self.assertRaisesRegex(ValueError, 'changed'):
            stale.rename(1, 'Pantheon')
        reopened = TraitNameSheet.load(*args)
        self.assertTrue(reopened.rename(1, 'Pantheon'))
        rows = read_csv(reopened.path)
        expected = [[key, {'0': 'Azure, "Knight"', '1': 'Pantheon'}.get(key, name)] for key, name in source]
        self.assertEqual(rows, [['string2 0', 'string 1'], *expected])
        self.assertEqual(english_mod_names(self.root), dict(expected))
        self.assertEqual(read_csv(english_csv)[1:], source)
        with self.assertRaisesRegex(ValueError, 'extracted game folder'):
            TraitNameSheet.load(self.root, 'app_text02', args[2], english_csv)

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
