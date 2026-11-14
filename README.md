# DigiTS Helper

**Build Digimon mods. Keep the tables connected.**

A Windows desktop toolkit for *Digimon Story: Time Stranger*: edit Digimon,
skills, buffs and evolution data, inspect MBE tables, and build Reloaded II
`dsts-loader` mods from extracted game files.

[Get started](#get-started) · [Mod workflow](#mod-workflow) · [Skills & buffs](#skills--buffs) · [Credits](#credits)

## What it does

| Tool | Purpose |
| --- | --- |
| **Digimon editor** | Stats, names, profiles, Field Guide entries, traits, skills, evolution paths and model references |
| **Advanced skills** | Skill properties, compatibility rules, buff sets and custom buff definitions |
| **Mod import/export** | Load existing payloads, merge edits, or export a separate Reloaded II mod |
| **MBE editor** | Inspect and edit binary MBE tables and CSV sheets |
| **MVGL Tools GUI** | Extract/repack archives and MBE tables through MVGLToolsCLI |

The editor reads Base, DLC (`addcont_01`–`03`, `17`) and imported mod data.
Related model tables include all ten LOD slots, locator references and motion
rows. Chrono Devolution forms are supported separately from ordinary evolution
paths.

## Get started

Use a Windows Python installation with **PyQt6**. The archive GUI also uses
Tkinter, included with the standard Windows Python installer.

Run these commands **from this repository's folder**:

```powershell
py -m pip install PyQt6
py digimon_editor.py
```

Other tools launch independently:

```powershell
py MBE_Editor.py
py mvgl_tools_gui.py
```

The main editor expects extracted tables under `Base/data` and `Base/text`,
with optional DLC data under `DLC`. Use **Configure Paths** to set your extracted
game folder and Reloaded II Mods folder. Machine-specific paths are saved in
the ignored `DigiTS_Helper_Paths.json` file.

For archive operations, place `MVGLToolsCLI.exe` and its accompanying resources
in `_internal` or alongside the GUI. The older MBE repack helpers use
`DSCSToolsCLI.exe` from the repository folder. These are separate tools with
different command-line interfaces; use the supplied backend for each workflow.
See the [extraction guide](https://hyotan-dev.github.io/dstsworkshop/tutorials/extractdata/)
for preparing game data.

## Mod workflow

1. **Load a mod or choose a template.** Adding a new entry stages a copy; choose
   its Digimon ID, Chr ID, character key and Field Guide ID before saving.
2. **Edit the data.** The editor checks ID collisions and keeps related rows
   connected. Imported custom LOD filenames and source locator references are
   retained.
3. **Save to Loaded Source** to update that source. For an imported mod, this
   merges the selected entry into its payload while retaining unrelated rows.
4. **Export / Copy Mod** to create a separate mod. Save your form edits first
   when exporting the loaded source.

The resulting layout is compatible with Reloaded II:

```text
My Mod/
├── ModConfig.json
└── dsts-loader/
    ├── patch/data/
    └── patch_text01/text/
```

Optional tables are included when source data exists. For example,
`model_locator.mbe` needs a captured locator reference, and
`002_chronodevolution.ap.csv` needs known form IDs. The latter controls
Chronomon's final-boss transformation attack; it is not the normal de-evolution
table. Edit it through **Evolution → Edit Chrono Devolution Forms**.

## Skills & buffs

- **Nullify unfavorable compatibility:** Advanced Skills → Additional Property
  2 → value **3**. Value **9** is the attribute-only variant.
- **Buff sets:** combine up to eleven effect IDs. Choose known effects or enter
  an ID directly, then assign the set to the skill's condition, target/user
  application, or removal field.
- **Buff definitions:** clone or edit `battle_buff` rows in the active mod,
  including custom elemental definitions already present there. Unknown columns
  remain available as raw values; a new ID reuses behavior supported by the
  game engine.

With an active mod, saving a Base/DLC skill creates an override for that skill
in the mod's patch. Buff definitions and sets are saved immediately; save the
skill afterward to assign the set. Extract packed `.mbe` replacements to CSV
before importing them through this workflow.

See the [mod/skill audit](Research/mod-skill-audit-2026-11-14.md) and
[Workshop skill reference](https://hyotan-dev.github.io/dstsworkshop/documentation/mbe/battle_skill/)
for the table mappings and validation details.

## How it works

`Data_Loader.py` resolves Base, DLC and mod tables. `digimon_editor.py` presents
those rows as connected editors; `CSV_Exporter.py` and `Mod_Tables.py` preserve
runtime headers and merge changes into the mod layout. `MBE_Editor.py` handles
direct table inspection, while `mvgl_tools_gui.py` runs the external archive
tools.

For model and animation conversion, use the companion
[Time Stranger Importer](https://github.com/ElderLich/Time-Stranger-Importer).
Native New Century skill-effect, camera and audio conversion for in-game use
is **in progress**; this editor does not convert Unity prefabs or sound banks.

## Development

```powershell
py -m unittest discover -s tests -v
$files = Get-ChildItem -File -Filter *.py | ForEach-Object { $_.FullName }
py -m py_compile @files
```

The regression suite uses temporary mod payloads and offscreen PyQt checks.
It covers import/export roundtrips, optional model tables, skill overrides,
buff definitions and CSV preservation without changing installed mods or Base
tables.

## Credits

- **SydMontague** — [MVGLTools / DSCSTools](https://github.com/SydMontague/MVGLTools),
  the extraction and repacking tools used by the GUI.
- **Hyotan and the DSTS Workshop contributors** —
  [format documentation and modding guides](https://hyotan-dev.github.io/dstsworkshop/).
- **The Digimon modding community** — table research, mod examples and bug
  reports that help verify real workflows.

This is an unofficial community tool. Digimon and game assets belong to their
respective owners; bundled third-party tools retain their original terms.
