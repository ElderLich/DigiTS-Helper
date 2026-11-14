# DigiTS Helper

Tools for Digimon Story Time Stranger data editing, extracted MBE/CSV review,
MVGL extraction helpers, and Reloaded II `dsts-loader` mod import/export.

This repository was split from:

```text
D:\Digimon Modding\Programs\DigiTS Helper
```

The standalone split intentionally excludes the old `Misc` folder.

## Main Tools

- `digimon_editor.py` - main PyQt Digimon editor.
- `data_loader.py` - base/DLC data loading and table helpers.
- `mvgl_tools_gui.py` - GUI wrapper for MVGL extraction/repack operations.
- `csv_exporter.py` and `MBE_Editor.py` - CSV/MBE inspection and export tools.

## Data Folders

- `Base` - extracted base game data used by the helper.
- `DLC` - supported add-on data folders.
- `Header Reports` - reference notes for Time Stranger table headers.
- `MVGLTools` - local MVGL command-line tooling used by the GUI.

Generated caches and local extraction output are ignored by Git.

## Editing mods and skills

Load a Reloaded II mod before editing. **Save to Loaded Source** merges the
selected Digimon into that payload; **Export / Copy Mod** writes a separate mod.
Existing unrelated rows are retained.

- `lod_chara.mbe` contains the LOD distances and model references. Imports and
  exports preserve all ten slots, including custom LOD filenames.
- `model_locator.mbe` is exported when the template or imported mod supplies
  locator data. Cloning keeps its source locator asset reference.
- **Evolution → Edit Chrono Devolution Forms** edits the six stage IDs used by
  Chronomon's final-boss attack. Templates carry their captured forms; unknown
  forms are not invented. These are separate from ordinary evolution paths.
- **Advanced Skills → Additional Property 2 → 3** nullifies unfavorable
  compatibility. Value **9** is the attribute-only variant.
- **Create Buff Set** combines up to eleven effect IDs. Choose a known effect
  or enter an ID directly. The skill fields distinguish checking a condition,
  applying effects to target/user, and removing effects from target/user.
- **Edit Buff Definitions** clones or edits `battle_buff` rows in the active
  mod. This includes custom elemental definitions already in that mod. Unknown
  columns remain raw, and new IDs reuse behavior supported by the game engine.

With an active mod, saving a Base/DLC skill copies only that skill into the
mod's patch before applying edits. Buff definitions and sets are saved to the
active mod immediately; save the skill afterward to assign the set.
Packed `.mbe` replacements must first be extracted to CSV with the extraction
tools. This editor does not infer new buff engine behavior from an ID.

See the [mod/skill regression audit](Research/mod-skill-audit-2026-11-14.md) and
the [DSTS Workshop skill reference](https://hyotan-dev.github.io/dstsworkshop/documentation/mbe/battle_skill/).

## Checks

Run `py -m unittest discover -s tests -v` for temporary-payload roundtrip and
offscreen PyQt checks. Run `py -m py_compile` on the top-level Python files for
the complete syntax check. Tests never modify installed mods or Base tables.
