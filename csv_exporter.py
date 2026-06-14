"""
CSV Exporter for DTS Creator.

This module writes Digimon data back into the unpacked MVGLTools CSV layout.
There are two export shapes to keep separate:

1. Raw extracted CSV folders under ``data`` and ``text``.
   These preserve the original MVGLTools format exactly, including header names,
   integer/bool spelling, and quoted empty cells.
2. dsts-loader patch folders.
   These are runtime patch files used by Reloaded II and must strip numeric file
   prefixes, convert some header types, and quote cells in the shape expected by
   MVGL.FileLoader.Reloaded.

The comments in this file intentionally document the format quirks. A small
formatting change can make Reloaded II reject the CSV or make MVGLTools repack a
file that looks valid but behaves differently in game.
"""

import csv
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple
from Data_Loader import DigimonData, MBELoader


class CSVExporter:
    """Export Digimon edits while preserving the game's fragile table formats."""
    
    def __init__(self, data_path: str = "data", text_path: str = "text"):
        self.data_path = Path(data_path)
        self.text_path = Path(text_path)
        self.loader = MBELoader(data_path, text_path)
        
    def export_digimon_to_csv(self, digimon: DigimonData, output_dir: Path) -> bool:
        """
        Export one Digimon into the legacy editable CSV tree.

        This is the broad editor/export path, not the Reloaded II folder writer.
        It writes the core tables that define a playable Digimon, then appends
        optional extended systems such as evolution and encounter data.
        """
        try:
            # Raw CSV exports keep the same top-level split as the unpacked game.
            output_data_dir = output_dir / "data"
            output_text_dir = output_dir / "text"
            
            print(f"Exporting complete Digimon data for {digimon.name} ({digimon.chr_id})")
            
            # Core data: status, model references, names, LOD, and field movement.
            self._export_digimon_status(digimon, output_data_dir)
            self._export_char_info(digimon, output_data_dir)
            self._export_char_name(digimon, output_text_dir)
            self._export_model_setting(digimon, output_data_dir)
            self._export_model_locator(digimon, output_data_dir)
            self._export_lod_data(digimon, output_data_dir)
            self._export_field_anime(digimon, output_data_dir)
            
            # Optional gameplay data is split out so missing sections do not block
            # simple model/name/status edits.
            self._export_extended_character_data(digimon, output_data_dir)
            
            print(f"Successfully exported all 9 core files + extended data for {digimon.name}")
            return True
            
        except Exception as e:
            print(f"Error exporting Digimon {digimon.chr_id}: {e}")
            return False
    
    def _export_digimon_status(self, digimon: DigimonData, output_dir: Path):
        """Export digimon status data to CSV"""
        status_dir = output_dir / "digimon_status.mbe"
        status_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing data to get header and preserve other entries
        original_file = self.data_path / "digimon_status.mbe" / "00_digimon_status_data.csv"
        output_file = status_dir / "00_digimon_status_data.csv"
        
        if original_file.exists():
            # Read original data
            original_rows = self.loader.load_csv(original_file)
            
            # Find and replace/add our digimon's row
            found = False
            for i, row in enumerate(original_rows[1:], 1):  # Skip header
                if len(row) > 3 and row[3] == digimon.chr_id:
                    # Replace existing row
                    original_rows[i] = self._create_digimon_status_row(digimon)
                    found = True
                    break
            
            if not found:
                # Add new row
                original_rows.append(self._create_digimon_status_row(digimon))
            
            # Write updated data preserving original format
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                for row in original_rows:
                    # Write row manually to preserve exact format
                    f.write(','.join(row) + '\n')
        else:
            # Create new file with header and our data
            header = self._get_digimon_status_header()
            data_row = self._create_digimon_status_row(digimon)
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                f.write(','.join(header) + '\n')
                f.write(','.join(data_row) + '\n')
    
    def _create_digimon_status_row(self, digimon: DigimonData) -> List[str]:
        """Create a digimon status CSV row matching original format exactly"""
        # The status table currently has 136 columns. Keep explicit positions here
        # because several columns are still unnamed in the mined headers.
        row = [""] * 136
        
        # Basic identity/classification fields. The hand-written quotes mirror
        # MVGLTools' raw CSV output; do not replace this method with csv.writer
        # unless the whole file format is retested in-game.
        row[0] = str(digimon.id)
        row[1] = '""'  # empty column with quotes
        row[2] = f'"{digimon.char_key}"'
        row[3] = f'"{digimon.chr_id}"'
        row[4] = str(digimon.stage_id)
        row[5] = str(digimon.personality_id)
        row[6] = str(digimon.type_id)
        
        # Elemental resistances
        row[7] = str(digimon.res_null)
        row[8] = str(digimon.res_fire)
        row[9] = str(digimon.res_water)
        row[10] = str(digimon.res_ice)
        row[11] = str(digimon.res_grass)
        row[12] = str(digimon.res_wind)
        row[13] = str(digimon.res_elec)
        row[14] = str(digimon.res_ground)
        row[15] = str(digimon.res_steel)
        row[16] = str(digimon.res_light)
        row[17] = str(digimon.res_dark)
        row[18] = '""'  # empty column with quotes
        
        # Traits (boolean flags starting at index 19)
        for i, trait in enumerate(digimon.traits):
            if 19 + i < len(row):
                row[19 + i] = "1" if trait else "0"
        
        # Base personality and stats
        row[61] = str(digimon.base_personality)
        row[64] = str(digimon.base_hp)
        row[65] = str(digimon.base_sp)
        row[66] = str(digimon.base_atk)
        row[67] = str(digimon.base_def)
        row[68] = str(digimon.base_int)
        row[69] = str(digimon.base_spi)
        row[70] = str(digimon.base_spd)
        
        # Signature skills are stored as 12 repeating three-column blocks:
        # skill id, empty spacer, learn slot.
        skill_indices = [
            (72, 74), (75, 77), (78, 80), (81, 83), (84, 86), (87, 89),
            (90, 92), (93, 95), (96, 98), (99, 101), (102, 104), (105, 107)
        ]
        
        for i, skill in enumerate(digimon.signature_skills):
            if i < len(skill_indices):
                id_idx, slot_idx = skill_indices[i]
                row[id_idx] = str(skill["id"])
                row[slot_idx] = str(skill["slot"])
                # Add empty fields between skills
                if id_idx + 1 < len(row):
                    row[id_idx + 1] = '""'
                if slot_idx + 1 < len(row):
                    row[slot_idx + 1] = '""'
        
        # Generic skills are four repeating three-column blocks:
        # skill id, empty spacer, required level.
        generic_indices = [(108, 110), (111, 113), (114, 116), (117, 119)]
        
        for i, skill in enumerate(digimon.generic_skills):
            if i < len(generic_indices):
                id_idx, level_idx = generic_indices[i]
                row[id_idx] = str(skill["id"])
                row[level_idx] = str(skill["level"])
                # Add empty fields between skills
                if id_idx + 1 < len(row):
                    row[id_idx + 1] = '""'
                if level_idx + 1 < len(row):
                    row[level_idx + 1] = '""'
        
        # References used by field guide/script systems. Field Guide ID lives in
        # column 131 and is the value the editor marks as occupied/free.
        row[131] = str(digimon.field_guide_id) if digimon.field_guide_id != -1 else ""
        row[132] = str(digimon.script_id) if digimon.script_id != -1 else ""
        
        # Fill remaining fields to match original structure exactly
        for i in range(133, len(row)):
            if row[i] == "":
                if i == 133:  # Field 133 should be -1
                    row[i] = "-1"
                elif i == 135:  # Field 135 should be -1
                    row[i] = "-1"
                else:
                    row[i] = "0"
        
        return row
    
    def _get_digimon_status_header(self) -> List[str]:
        """Get the header row for digimon status CSV"""
        # Fallback only. Normal exports preserve the original header from disk, but
        # this keeps a new file structurally valid if the source table is missing.
        header = ["id", "empty", "char_key", "chr_id", "stage_id", "empty", "type_id"]
        return header + [""] * (136 - len(header))  # Pad to 136 columns
    
    def _export_char_info(self, digimon: DigimonData, output_dir: Path):
        """Export character info to CSV"""
        char_dir = output_dir / "char_info.mbe"
        char_dir.mkdir(parents=True, exist_ok=True)
        
        original_file = self.data_path / "char_info.mbe" / "00_char_info.csv"
        output_file = char_dir / "00_char_info.csv"
        
        if original_file.exists():
            # Read and update existing data
            original_rows = self.loader.load_csv(original_file)
            
            # Find and replace/add our digimon's row
            found = False
            for i, row in enumerate(original_rows[1:], 1):  # Skip header
                if len(row) > 0 and row[0] == digimon.char_key:
                    # Replace existing row
                    original_rows[i] = self._create_char_info_row(digimon)
                    found = True
                    break
            
            if not found:
                # Add new row
                original_rows.append(self._create_char_info_row(digimon))
            
            # Write updated data
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(original_rows)
    
    def _create_char_info_row(self, digimon: DigimonData) -> List[str]:
        """Create a character info CSV row"""
        return [
            digimon.char_key,
            "",  # empty
            "",  # empty
            digimon.chr_id,
            str(1000 + digimon.id),  # Some ID mapping
            "",  # empty
            "0",  # gender flag
            "0",  # some flag
            "",  # motion/animation reference
            "0",  # flag
            "",  # model reference
            "0",  # flag
            "",  # empty
            "0"   # flag
        ]
    
    def _export_char_name(self, digimon: DigimonData, output_dir: Path):
        """Export character name to CSV"""
        name_dir = output_dir / "char_name.mbe"
        name_dir.mkdir(parents=True, exist_ok=True)
        
        original_file = self.text_path / "char_name.mbe" / "00_Sheet1.csv"
        output_file = name_dir / "00_Sheet1.csv"
        
        if original_file.exists():
            # Read and update existing data
            original_rows = self.loader.load_csv(original_file)
            
            # Find and replace/add our digimon's row
            found = False
            for i, row in enumerate(original_rows[1:], 1):  # Skip header
                if len(row) > 0 and row[0] == digimon.char_key:
                    # Replace existing row
                    original_rows[i] = [digimon.char_key, digimon.name]
                    found = True
                    break
            
            if not found:
                # Add new row
                original_rows.append([digimon.char_key, digimon.name])
            
            # Write updated data
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(original_rows)
    
    def _export_model_setting(self, digimon: DigimonData, output_dir: Path):
        """Export model setting data to CSV"""
        model_dir = output_dir / "model_setting.mbe"
        model_dir.mkdir(parents=True, exist_ok=True)
        
        original_file = self.data_path / "model_setting.mbe" / "00_model_setting.csv"
        output_file = model_dir / "00_model_setting.csv"
        
        if original_file.exists():
            # Read and update existing data
            original_rows = self.loader.load_csv(original_file)
            
            # Find and replace/add our digimon's row
            found = False
            for i, row in enumerate(original_rows[1:], 1):  # Skip header
                if len(row) > 0 and row[0] == digimon.chr_id:
                    # Use stored data if available, otherwise preserve original
                    if digimon.model_setting_data and "raw_data" in digimon.model_setting_data:
                        original_rows[i] = digimon.model_setting_data["raw_data"]
                    found = True
                    break
            
            if not found and digimon.model_setting_data and "raw_data" in digimon.model_setting_data:
                # Add new row
                original_rows.append(digimon.model_setting_data["raw_data"])
            
            # Write updated data
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(original_rows)
    
    def _export_lod_data(self, digimon: DigimonData, output_dir: Path):
        """Export LOD data to CSV"""
        if not digimon.lod_data:
            return
            
        lod_dir = output_dir / "lod_chara.mbe"
        lod_dir.mkdir(parents=True, exist_ok=True)
        
        # Create LOD row
        lod_row = [
            digimon.chr_id,
            str(digimon.lod_data.get("lod_distance_1", 20)),
            str(digimon.lod_data.get("lod_distance_2", 65)),
            str(digimon.lod_data.get("lod_distance_3", 500))
        ] + ["0"] * 7  # Pad with zeros
        
        output_file = lod_dir / "00_lod.csv"
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(lod_row)
    
    def _export_model_locator(self, digimon: DigimonData, output_dir: Path):
        """Export model locator data to CSV"""
        locator_dir = output_dir / "model_locator.mbe"
        locator_dir.mkdir(parents=True, exist_ok=True)
        
        # Export 00_model_locator.csv
        if digimon.model_locator_data:
            original_file = self.data_path / "model_locator.mbe" / "00_model_locator.csv"
            output_file = locator_dir / "00_model_locator.csv"
            
            if original_file.exists():
                original_rows = self.loader.load_csv(original_file)
                
                # Find and update row
                found = False
                for i, row in enumerate(original_rows[1:], 1):
                    if len(row) > 0 and row[0] == digimon.chr_id:
                        original_rows[i] = [
                            digimon.model_locator_data["chr_id"],
                            digimon.model_locator_data["locator_ref"]
                        ]
                        found = True
                        break
                
                if not found:
                    original_rows.append([
                        digimon.model_locator_data["chr_id"],
                        digimon.model_locator_data["locator_ref"]
                    ])
                
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(original_rows)
        
        # Export 01_model_locator_motion.csv
        if digimon.model_locator_motion_data:
            original_file = self.data_path / "model_locator.mbe" / "01_model_locator_motion.csv"
            output_file = locator_dir / "01_model_locator_motion.csv"
            
            if original_file.exists():
                original_rows = self.loader.load_csv(original_file)
                
                # Remove existing entries for this chr_id
                chr_prefix = f"{digimon.chr_id}_"
                original_rows = [row for row in original_rows if not (len(row) > 0 and row[0].startswith(chr_prefix))]
                
                # Add new entries
                for motion_data in digimon.model_locator_motion_data:
                    original_rows.append([
                        motion_data["motion_key"],
                        motion_data["motion_name"]
                    ])
                
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(original_rows)
    
    
    def _export_field_anime(self, digimon: DigimonData, output_dir: Path):
        """Export field animation data to CSV"""
        anime_dir = output_dir / "field_anime.mbe"
        anime_dir.mkdir(parents=True, exist_ok=True)
        
        # Export 00_field_move_animation.csv only
        if digimon.field_move_animation_data:
            original_file = self.data_path / "field_anime.mbe" / "00_field_move_animation.csv"
            output_file = anime_dir / "00_field_move_animation.csv"
            
            if original_file.exists():
                original_rows = self.loader.load_csv(original_file)
                
                # Remove existing entries for this chr_id
                chr_prefix = digimon.chr_id
                filtered_rows = [original_rows[0]]  # Keep header
                for row in original_rows[1:]:
                    if not (len(row) > 0 and chr_prefix in row[0]):
                        filtered_rows.append(row)
                
                # Add new entries
                for anim_data in digimon.field_move_animation_data:
                    filtered_rows.append(anim_data["raw_data"])
                
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(filtered_rows)
    
    def _export_extended_character_data(self, digimon: DigimonData, output_dir: Path):
        """Export all extended character data"""
        self._export_evolution_data(digimon, output_dir)
        self._export_battle_enemy_data(digimon, output_dir)
        self._export_battle_formation_data(digimon, output_dir)
        self._export_encounter_groups(digimon, output_dir)
        # Note: Quest references, flags, and NPC placements are typically managed
        # by the game's quest system and may not need direct editing
    
    def _export_evolution_data(self, digimon: DigimonData, output_dir: Path):
        """Export evolution data to CSV"""
        if not digimon.evolution_paths and not digimon.evolution_conditions:
            return
        
        # Export evolution paths
        if digimon.evolution_paths:
            evo_to_dir = output_dir / "evolution.mbe"
            evo_to_dir.mkdir(parents=True, exist_ok=True)
            
            original_file = self.data_path / "evolution.mbe" / "01_evolution_to.csv"
            output_file = evo_to_dir / "01_evolution_to.csv"
            
            if original_file.exists():
                original_rows = self.loader.load_csv(original_file)
                
                # Remove existing entries for this Digimon
                filtered_rows = [original_rows[0]]  # Keep header
                for row in original_rows[1:]:
                    if not (len(row) > 1 and row[1] == str(digimon.id)):
                        filtered_rows.append(row)
                
                # Add new entries
                for evo_path in digimon.evolution_paths:
                    filtered_rows.append(evo_path["raw_data"])
                
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(filtered_rows)
        
        # Export evolution conditions
        if digimon.evolution_conditions:
            original_file = self.data_path / "evolution.mbe" / "00_evolution_condition.csv"
            output_file = evo_to_dir / "00_evolution_condition.csv"
            
            if original_file.exists():
                original_rows = self.loader.load_csv(original_file)
                
                # Remove existing entries for this Digimon's evolution IDs
                evo_ids = [str(cond["evolution_id"]) for cond in digimon.evolution_conditions]
                filtered_rows = [original_rows[0]]  # Keep header
                for row in original_rows[1:]:
                    if not (len(row) > 0 and row[0] in evo_ids):
                        filtered_rows.append(row)
                
                # Add new entries
                for cond in digimon.evolution_conditions:
                    filtered_rows.append(cond["raw_data"])
                
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(filtered_rows)
    
    def _export_battle_enemy_data(self, digimon: DigimonData, output_dir: Path):
        """Export battle enemy data to CSV"""
        if not digimon.battle_enemy_data:
            return
        
        enemy_dir = output_dir / "battle_enemy.mbe"
        enemy_dir.mkdir(parents=True, exist_ok=True)
        
        original_file = self.data_path / "battle_enemy.mbe" / "00_enemy_parameter.csv"
        output_file = enemy_dir / "00_enemy_parameter.csv"
        
        if original_file.exists():
            original_rows = self.loader.load_csv(original_file)
            
            # Find and update row
            found = False
            for i, row in enumerate(original_rows[1:], 1):
                if len(row) > 2 and row[2] == str(digimon.id):
                    original_rows[i] = digimon.battle_enemy_data["raw_data"]
                    found = True
                    break
            
            if not found:
                original_rows.append(digimon.battle_enemy_data["raw_data"])
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(original_rows)
    
    def _export_battle_formation_data(self, digimon: DigimonData, output_dir: Path):
        """Export battle formation data to CSV"""
        if not digimon.battle_formation_data:
            return
        
        formation_dir = output_dir / "battle_formation.mbe"
        formation_dir.mkdir(parents=True, exist_ok=True)
        
        original_file = self.data_path / "battle_formation.mbe" / "00_battle_formation.csv"
        output_file = formation_dir / "00_battle_formation.csv"
        
        if original_file.exists():
            original_rows = self.loader.load_csv(original_file)
            
            # Find and update row
            found = False
            for i, row in enumerate(original_rows[1:], 1):
                if len(row) > 0 and str(row[0]) == str(digimon.id):
                    original_rows[i] = digimon.battle_formation_data["raw_data"]
                    found = True
                    break
            
            if not found:
                original_rows.append(digimon.battle_formation_data["raw_data"])
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(original_rows)
    
    def _export_encounter_groups(self, digimon: DigimonData, output_dir: Path):
        """Export encounter group data to CSV"""
        if not digimon.encounter_groups:
            return
        
        encounter_dir = output_dir / "battle_enemy.mbe"
        encounter_dir.mkdir(parents=True, exist_ok=True)
        
        original_file = self.data_path / "battle_enemy.mbe" / "01_encount_group.csv"
        output_file = encounter_dir / "01_encount_group.csv"
        
        if original_file.exists():
            original_rows = self.loader.load_csv(original_file)
            
            # Remove existing entries for this Digimon
            filtered_rows = [original_rows[0]]  # Keep header
            for row in original_rows[1:]:
                # Check if this row contains references to this Digimon
                should_keep = True
                for encounter in digimon.encounter_groups:
                    if len(row) > 0 and row[0] == encounter['group_id']:
                        should_keep = False
                        break
                if should_keep:
                    filtered_rows.append(row)
            
            # Add new entries
            for encounter in digimon.encounter_groups:
                filtered_rows.append(encounter["raw_data"])
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(filtered_rows)
    
    def export_all_modified_data(self, digimon_list: List[DigimonData], output_dir: Path) -> bool:
        """Export all modified Digimon data to a directory structure"""
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            
            for digimon in digimon_list:
                self.export_digimon_to_csv(digimon, output_dir)
            
            return True
            
        except Exception as e:
            print(f"Error exporting all data: {e}")
            return False
    
    def export_all_csv_files(self, output_dir: Path) -> bool:
        """
        Export all CSV files from data and text directories, preserving structure, including DLC.
        
        This preserves the original format matching backup/data:
        - Headers use 'int' (not 'int32')
        - Booleans use '0'/'1' (not 'false'/'true')
        - Empty strings use '""' (quoted empty strings)
        
        Files are copied as-is without transformation.
        For dsts-loader format, use export_for_dsts_loader() instead.
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy each tree whole so unknown tables stay available for data mining.
            data_source = self.data_path
            data_dest = output_dir / "data"
            
            if data_source.exists():
                if data_dest.exists():
                    shutil.rmtree(data_dest)
                shutil.copytree(data_source, data_dest)
                print(f"Copied all data CSV files to {data_dest}")
            
            text_source = self.text_path
            text_dest = output_dir / "text"
            
            if text_source.exists():
                if text_dest.exists():
                    shutil.rmtree(text_dest)
                shutil.copytree(text_source, text_dest)
                print(f"Copied all text CSV files to {text_dest}")
            
            # DLC is kept under its own root because addcont_* names matter when
            # repacking and when generating dsts-loader patch paths.
            workspace_root = self.data_path.parent
            dlc_source_dir = workspace_root / "DLC"
            
            if dlc_source_dir.exists():
                dlc_dest_dir = output_dir / "DLC"
                if dlc_dest_dir.exists():
                    shutil.rmtree(dlc_dest_dir)
                shutil.copytree(dlc_source_dir, dlc_dest_dir)
                print(f"Copied all DLC CSV files to {dlc_dest_dir}")
            
            return True
            
        except Exception as e:
            print(f"Error exporting all CSV files: {e}")
            import traceback
            traceback.print_exc()
            return False

    def export_for_dsts_loader(self, dsts_loader_dir: Path, dlc_name: str = "addcont_17") -> bool:
        """
        Export DLC CSV files into a dsts-loader friendly structure.

        Structure:
            dsts-loader/
                <dlc_name>/data/<*.mbe>/<csv without numeric prefix>
                <dlc_name>_text01/text/<*.mbe>/<csv without numeric prefix>

        The default remains addcont_17 because custom Digimon are currently
        authored there. Pass another addcont_* name when exporting a different
        DLC payload.
        """
        try:
            workspace_root = self.data_path.parent
            data_source = workspace_root / "DLC" / f"{dlc_name}.dx11" / "data" / "mbe"
            text_source = workspace_root / "DLC" / f"{dlc_name}_text01.dx11" / "text" / "mbe"

            if not data_source.exists():
                print(f"[dsts-loader export] DLC data source not found: {data_source}")
                return False

            dest_data_root, dest_text_root = self._resolve_dsts_loader_targets(dsts_loader_dir, dlc_name)

            self._copy_mbe_tree_to_dsts(data_source, dest_data_root)

            if text_source.exists():
                self._copy_mbe_tree_to_dsts(text_source, dest_text_root)
            else:
                print(f"[dsts-loader export] DLC text source not found: {text_source}")

            print(f"[dsts-loader export] Finished writing CSV files to {dsts_loader_dir}")
            return True
        except Exception as e:
            print(f"Error exporting to dsts-loader structure: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _copy_mbe_tree_to_dsts(self, source_root: Path, dest_root: Path):
        """
        Copy .mbe folders from source to destination.

        dsts-loader addresses tables by their plain CSV names, while MVGLTools
        extraction prefixes them with ordering numbers such as ``000_``. This
        method strips those prefixes and rewrites only CSV files that need
        Reloaded/MVGL.FileLoader formatting.
        """
        if dest_root.exists():
            # Replace the generated tree so removed source CSVs do not linger in a
            # later mod export.
            shutil.rmtree(dest_root)
        dest_root.mkdir(parents=True, exist_ok=True)

        for folder in source_root.iterdir():
            if not folder.is_dir() or folder.suffix != ".mbe":
                continue

            dest_folder = dest_root / folder.name
            dest_folder.mkdir(parents=True, exist_ok=True)

            for file in folder.iterdir():
                if not file.is_file():
                    continue
                
                # Prefer 000_ files over old 00_ variants when both were extracted.
                if file.name.startswith('00_') and not file.name.startswith('000_'):
                    new_name = '000_' + file.name[3:]
                    new_file = folder / new_name
                    if new_file.exists():
                        file = new_file
                
                dest_name = self._strip_numeric_prefix(file.name) if file.suffix.lower() == ".csv" else file.name
                dest_path = dest_folder / dest_name
                
                if file.suffix.lower() == ".csv":
                    # Transform CSV format for dsts-loader
                    self._transform_csv_for_dsts_loader(file, dest_path)
                else:
                    # Copy non-CSV files as-is
                    shutil.copy2(file, dest_path)

    @staticmethod
    def _strip_numeric_prefix(filename: str) -> str:
        """Remove leading NN_ prefix from filenames to match dsts-loader expectations."""
        if "_" in filename:
            prefix, rest = filename.split("_", 1)
            if prefix.isdigit():
                return rest
        return filename
    
    def _transform_csv_for_dsts_loader(self, source_file: Path, dest_file: Path):
        """
        Transform CSV file format for dsts-loader compatibility:
        - int -> int32 in headers
        - 0/1 -> false/true for boolean values
        - Empty cells: ""
        - String columns: quoted
        - Numeric columns: unquoted

        The output is built manually instead of using csv.writer because
        csv.writer would quote fields based on Python's CSV rules, not the more
        specific MVGL.FileLoader expectations.
        """
        try:
            # Read CSV file using csv.reader
            with open(source_file, 'r', encoding='utf-8') as f_in:
                reader = csv.reader(f_in)
                rows = list(reader)
            
            if not rows:
                # Empty file, just copy
                import shutil
                shutil.copy2(source_file, dest_file)
                return
            
            # The header names double as type information, so every later cell is
            # formatted according to its source column.
            header_row = rows[0]
            header_types = [cell.strip() for cell in header_row]
            
            # Transform header: int -> int32
            transformed_header = [
                cell.replace('int ', 'int32 ') if cell.startswith('int ') else cell 
                for cell in header_types
            ]
            
            # Write transformed file
            with open(dest_file, 'w', encoding='utf-8', newline='') as f_out:
                # Write header (no quotes)
                f_out.write(','.join(transformed_header) + '\n')
                
                # Process and write data rows
                for row in rows[1:]:
                    if not row:
                        f_out.write('\n')
                        continue
                    
                    output_parts = []
                    for col_idx, cell in enumerate(row):
                        if col_idx >= len(header_types):
                            # Extra columns beyond header - write as-is
                            output_parts.append(cell if cell else '""')
                            continue
                        
                        col_type = header_types[col_idx].lower()
                        
                        if 'bool' in col_type:
                            if cell == '0':
                                output_parts.append('false')
                            elif cell == '1':
                                output_parts.append('true')
                            else:
                                output_parts.append(cell)
                        
                        elif 'string' in col_type:
                            # String: always quoted
                            if not cell or cell == '""':
                                output_parts.append('""')
                            else:
                                # Escape quotes in the string by doubling them
                                escaped = cell.replace('"', '""')
                                output_parts.append(f'"{escaped}"')
                        
                        elif 'empty' in col_type:
                            # Empty column: always ""
                            output_parts.append('""')
                        
                        elif 'int' in col_type or 'float' in col_type:
                            # Numeric: never quoted
                            if not cell or cell == '""':
                                output_parts.append('""')
                            else:
                                output_parts.append(cell)
                        
                        else:
                            # Unknown column families are preserved conservatively.
                            if not cell:
                                output_parts.append('""')
                            else:
                                output_parts.append(cell)
                    
                    f_out.write(','.join(output_parts) + '\n')
                    
        except Exception as e:
            print(f"Error transforming CSV {source_file}: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: just copy the file
            import shutil
            shutil.copy2(source_file, dest_file)

    def _resolve_dsts_loader_targets(self, selected_path: Path, dlc_name: str) -> Tuple[Path, Path]:
        """
        Determine where to place data/text folders based on the selected directory.

        Supports selecting the dsts-loader root, an addcont_* folder, a data/text
        folder inside one, or an empty mod folder.
        """
        selected = selected_path.resolve()
        dlc_folder = dlc_name.lower()
        text_folder = f"{dlc_name}_text01".lower()
        name = selected.name.lower()

        if name == "dsts-loader":
            data_root = selected / dlc_name / "data"
            text_root = selected / f"{dlc_name}_text01" / "text"
        elif name == dlc_folder:
            data_root = selected / "data"
            text_root = selected.parent / f"{dlc_name}_text01" / "text"
        elif name == text_folder:
            data_root = selected.parent / dlc_name / "data"
            text_root = selected / "text"
        elif name == "data" and selected.parent.name.lower() == dlc_folder:
            data_root = selected
            text_root = selected.parents[1] / f"{dlc_name}_text01" / "text"
        elif name == "text" and selected.parent.name.lower() == text_folder:
            data_root = selected.parents[1] / dlc_name / "data"
            text_root = selected
        else:
            data_root = selected / dlc_name / "data"
            text_root = selected / f"{dlc_name}_text01" / "text"

        return data_root, text_root


if __name__ == "__main__":
    # Test the exporter with chr805
    from Data_Loader import MBELoader
    
    loader = MBELoader()
    digimon = loader.get_digimon_by_chr_id("chr805")
    
    if digimon:
        exporter = CSVExporter()
        output_path = Path("exported_data")
        
        if exporter.export_digimon_to_csv(digimon, output_path):
            print(f"Successfully exported {digimon.name} to {output_path}")
        else:
            print("Export failed")
    else:
        print("Could not load chr805 for testing")


def repack_mbe_files(source_dir: Path, target_dir: Path) -> bool:
    """
    Repack loose .mbe folders to packed .mbe files using DSCSToolsCLI.

    This is the simple non-DLC helper. DLC repacking needs extra addcont_* path
    handling, so it lives in repack_dlc_mbe_files().
    """
    try:
        # Ensure target directory exists
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all .mbe folders in source directory
        mbe_folders = [f for f in source_dir.iterdir() if f.is_dir() and f.suffix == '.mbe']
        
        if not mbe_folders:
            print(f"No .mbe folders found in {source_dir}")
            return False
        
        success_count = 0
        for mbe_folder in mbe_folders:
            # Create target .mbe file path
            target_mbe_file = target_dir / mbe_folder.name
            
            # Use Unix-style paths with forward slashes for DSCSToolsCLI
            source_path = str(mbe_folder.relative_to(Path.cwd())).replace('\\', '/')
            target_path = str(target_mbe_file.relative_to(Path.cwd())).replace('\\', '/')
            
            # Run DSCSToolsCLI --mbepack command with Unix-style paths
            # On Windows, use DSCSToolsCLI.exe directly (not ./DSCSToolsCLI.exe)
            cmd = [
                "DSCSToolsCLI.exe",
                "--mbepack",
                source_path,
                target_path
            ]
            
            print(f"Repacking {mbe_folder.name}...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"Successfully repacked {mbe_folder.name}")
                success_count += 1
            else:
                print(f"Error repacking {mbe_folder.name}: {result.stderr}")
        
        print(f"Successfully repacked {success_count}/{len(mbe_folders)} .mbe files")
        return success_count > 0
        
    except Exception as e:
        print(f"Error during MBE repacking: {e}")
        return False


def repack_dlc_mbe_files(dlc_names=None) -> bool:
    """
    Repack DLC CSV folders into .mbe files using DSCSToolsCLI.
    
    Args:
        dlc_names: Optional DLC name or iterable of DLC names. Defaults to
            MBELoader.DSTS_DLC_IDS, currently addcont_01-03 and addcont_17.
    
    Returns:
        bool: True if repacking was successful
    """
    try:
        workspace_root = Path(__file__).resolve().parent

        if dlc_names is None:
            dlc_names = [f"addcont_{dlc_id}" for dlc_id in MBELoader.DSTS_DLC_IDS]
        elif isinstance(dlc_names, str):
            dlc_names = [dlc_names]

        mbe_folders = []

        for dlc_name in dlc_names:
            dlc_id = dlc_name.split("_", 1)[-1]
            if not dlc_id.isdigit():
                print(f"Skipping unknown DLC name: {dlc_name}")
                continue

            dlc_data_source_dir = workspace_root / "DLC" / f"{dlc_name}.dx11" / "data" / "mbe"
            dlc_text_source_dir = workspace_root / "DLC" / f"{dlc_name}_text01.dx11" / "text" / "mbe"
            dlc_data_target_dir = workspace_root / "export" / "DLC" / f"{dlc_name}.dx11" / "data"
            dlc_text_target_dir = workspace_root / "export" / "DLC" / f"{dlc_name}_text01.dx11" / "text"
            suffix = f"_dlc{int(dlc_id):02d}.mbe"

            if not dlc_data_source_dir.exists() and not dlc_text_source_dir.exists():
                print(f"DLC source directories not found for {dlc_name}; skipping.")
                continue

            if dlc_data_source_dir.exists():
                for folder in dlc_data_source_dir.iterdir():
                    if folder.is_dir() and folder.name.endswith(suffix):
                        mbe_folders.append((folder, dlc_data_target_dir))

            if dlc_text_source_dir.exists():
                for folder in dlc_text_source_dir.iterdir():
                    if folder.is_dir() and folder.name.endswith(suffix):
                        mbe_folders.append((folder, dlc_text_target_dir))
        
        if not mbe_folders:
            print("No DLC .mbe folders found to repack")
            return False
        
        print(f"\n=== Repacking {len(mbe_folders)} DLC .mbe folders ===")
        print("Source: DLC/addcont_01-03/17.dx11/...")
        print("Target: export/DLC/addcont_01-03/17.dx11/...")
        success_count = 0
        
        for mbe_folder, target_dir in mbe_folders:
            # Check if folder contains CSV files
            csv_files = list(mbe_folder.glob("*.csv"))
            if not csv_files:
                print(f"⚠️ Warning: {mbe_folder.name} contains no CSV files, skipping...")
                continue
            
            print(f"  Found {len(csv_files)} CSV file(s) in folder")
            
            # Verify source folder exists
            if not mbe_folder.exists() or not mbe_folder.is_dir():
                print(f"⚠️ Warning: Source folder does not exist: {mbe_folder}")
                continue
            
            # Create target .mbe file path in export/DLC/
            # Ensure target directory exists
            target_dir.mkdir(parents=True, exist_ok=True)
            target_mbe_file = target_dir / mbe_folder.name
            
            # Convert to absolute paths first
            abs_source = mbe_folder.absolute()
            abs_target = target_mbe_file.absolute()
            
            # Check if target already exists - if it's a file, we'll overwrite it; if it's a directory, skip
            if abs_target.exists():
                if abs_target.is_dir():
                    print(f"  ⚠️ Warning: Target path is a directory (conflict with folder name): {abs_target.name}")
                    print(f"     This means there's both a folder and file with the same name - skipping...")
                    continue
                elif abs_target.is_file():
                    # Existing .mbe file - we'll overwrite it
                    print(f"  Found existing .mbe file, will overwrite: {abs_target.name}")
            
            # Remove existing .mbe file if it exists (DSCSToolsCLI will create it)
            if abs_target.exists():
                try:
                    abs_target.unlink()
                except Exception as e:
                    print(f"  Warning: Could not remove existing file: {e}")
            
            # Use Windows-style paths with backslashes for DSCSToolsCLI on Windows
            # DSCSToolsCLI on Windows expects native Windows paths, quoted
            # Do NOT add trailing backslash - DSCSToolsCLI doesn't need it
            source_path = str(abs_source)
            target_path = str(abs_target)
            
            # Quote paths to handle spaces and special characters
            source_path_quoted = f'"{source_path}"'
            target_path_quoted = f'"{target_path}"'
            
            # Keep these path diagnostics visible; failed repacks are usually path
            # quoting, missing CLI, or file-lock problems.
            print(f"  Source path: {source_path}")
            print(f"  Target path: {target_path}")
            print(f"  Source exists: {abs_source.exists()}")
            print(f"  Target dir exists: {abs_target.parent.exists()}")
            
            # Check if DSCSToolsCLI.exe exists
            dscstools_path = workspace_root / "DSCSToolsCLI.exe"
            if not dscstools_path.exists():
                print(f"❌ Error: DSCSToolsCLI.exe not found in {workspace_root}")
                print(f"   Please ensure DSCSToolsCLI.exe is in the workspace root directory.")
                return False
            
            # Run DSCSToolsCLI --mbepack command with quoted Windows paths
            cmd = [
                str(dscstools_path),
                "--mbepack",
                source_path_quoted,
                target_path_quoted
            ]
            
            print(f"\nRepacking {mbe_folder.name}...")
            print(f"  Source folder: {abs_source}")
            print(f"  Target file: {abs_target}")
            print(f"  Command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=workspace_root)
            
            if result.returncode == 0:
                # Wait a moment for file system to sync
                import time
                time.sleep(0.2)
                
                # Check if target file was created
                if abs_target.exists() and abs_target.is_file():
                    file_size = abs_target.stat().st_size
                    if file_size > 0:
                        print(f"✅ Successfully repacked {mbe_folder.name} ({file_size:,} bytes)")
                        success_count += 1
                    else:
                        print(f"⚠️ Warning: File created but is empty (0 bytes)")
                        print(f"  DSCSToolsCLI may have failed silently.")
                        print(f"  Try running manually: {' '.join(cmd)}")
                        if result.stdout:
                            print(f"  Output: {result.stdout}")
                        if result.stderr:
                            print(f"  Error: {result.stderr}")
                else:
                    print(f"⚠️ Warning: Repack reported success but target file not found!")
                    print(f"  Expected: {abs_target}")
                    if result.stdout:
                        print(f"  Output: {result.stdout}")
                    if result.stderr:
                        print(f"  Error: {result.stderr}")
            else:
                print(f"❌ Error repacking {mbe_folder.name} (exit code: {result.returncode})")
                if result.stdout:
                    print(f"  Output: {result.stdout}")
                if result.stderr:
                    print(f"  Error: {result.stderr}")
        
        print(f"\n✅ Successfully repacked {success_count}/{len(mbe_folders)} DLC .mbe files")
        return success_count > 0
        
    except Exception as e:
        print(f"Error during DLC MBE repacking: {e}")
        import traceback
        traceback.print_exc()
        return False
