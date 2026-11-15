# Time Stranger Mod Studio

**Build Digimon mods. Keep the tables connected.**

A Windows desktop toolkit for *Digimon Story: Time Stranger*: edit Digimon,
skills, buffs and evolution data, inspect MBE tables, and build Reloaded II
`dsts-loader` mods from extracted game files.

[Get started](#get-started) · [Art Studio](#time-stranger-art-studio) · [Mod workflow](#mod-workflow) · [Skills & buffs](#skills--buffs) · [Credits](#credits)

## What it does

| Tool | Purpose |
| --- | --- |
| **Digimon editor** | Stats, names, profiles, Field Guide entries, traits, skills, evolution paths and model references |
| **Art Studio** | Create native dot sprites from sprite sheets and profile pictures from models or transparent PNG artwork |
| **Field Guide** | Review installed mods and slot conflicts, change a mod's slot, or register catalogued species in a PC save |
| **Advanced skills** | Skill properties, compatibility rules, buff sets and custom buff definitions |
| **Mod import/export** | Load existing payloads, merge edits, or export a separate Reloaded II mod |
| **MVGL Tools** | Extract PC/Switch archives and MBE tables; PC repacking through MVGLToolsCLI |

The editor reads Base, DLC (`addcont_01`–`03`, `17`) and imported mod data.
Related model tables include all ten LOD slots, locator references and motion
rows. Chrono Devolution forms are supported separately from ordinary evolution
paths.

## Get started

On Windows, double-click **Time Stranger Mod Studio.cmd** to edit Digimon
and mods. Double-click **Time Stranger Art Studio.cmd** for sprites and
portraits. Each launcher opens its executable in `dist/` when available.
Otherwise it starts the application from `app/` using the Windows Python
launcher. Install the source dependencies once if you use that route.

```powershell
py -m pip install -r dependencies/requirements.txt
```

For archives, double-click **MVGL Tools.cmd**. For Lua scripts, double-click
**Lua Decompiler.cmd**. Both launchers are in the repository root. MVGL Tools
uses Tkinter, included with the standard Windows Python installer. Lua
decompilation also requires Java.

The main editor reads extracted base tables from `data/Base/data` and
`data/Base/text`, with optional DLC tables under `data/DLC`. Use **Configure Paths** to set your extracted
game folder and Reloaded II Mods folder. Machine-specific paths are saved in
the ignored `Time_Stranger_Mod_Studio_Paths.json` file. Existing installations
can keep their saved paths when upgrading.

Bundled tools live under `dependencies/`. The MVGL backend and its support
files are in `mvgl/`, CPK tools are in `cpk/`, DSCSTools is in `dscs/`
and the Lua decompiler is in `unluac/`.
See the [extraction guide](https://hyotan-dev.github.io/dstsworkshop/tutorials/extractdata/)
for preparing game data.

### Time Stranger Art Studio

Open **Time Stranger Art Studio.cmd** from the repository root.

- **Dot Sprites** opens an existing sprite sheet or native dot atlas. Select a
  16 × 16 source frame and click its position in the four-frame game atlas.
  The enlarged preview keeps the pixels square. Enter the Digimon ID, choose
  the mod or staging folder and click **Export dot sprite**.
- **Portraits** opens a GLB, glTF, native GEOM or an existing transparent
  PNG. For a model, adjust **Camera turn** and **Tilt** before clicking **Render
  preview**. Drag a square around the face and check **Game portrait**.
  The preview applies the tutorial's teal color treatment, red/blue channel
  offset, selective black adjustment and hard shadow. Its opacity includes
  the model and its shadow. **Save styled PNG…** saves a 512 × 512 cutout.
  To install a game icon, enter the icon ID from the Digimon's `char_info`
  row, choose the mod or staging folder and click **Save profile picture**.
  This creates a 512 × 512 BC7 texture with ten mip levels.

Both tabs write to `dsts-loader/patch/images` in the chosen mod. For Leviamon X,
Digimon ID 761 and icon ID 761 produce `dot761.img` and `ui_chara_icon_761.img`.
Model capture uses Blender. GEOM requires the Time Stranger Importer addon.
Native portrait export uses NVIDIA Texture Tools' `nvcompress.exe`. The app
can prompt for either executable on first use. Sprite sheets and transparent
PNG inputs open directly.

### Switch extraction

In **MVGL Tools**, select **Time Stranger (Switch)**, then **Extract MVGL
Archive**. Batch mode reads `.mvgl` and `.cpk` files recursively, including DLC
subfolders. The default source is `D:\Emulators\Ryujinx\Games\Extracted`, and the
default output is `D:\Digimon Modding\Time Stranger - Switch - Extracted`.
Inputs must already be decrypted game archives; NSP/NCA extraction is separate.

Switch archives use different MVGL record widths from PC. `app/Switch_Archives.py`
handles both `nx64` and `ounce64` variants directly; the bundled MVGLToolsCLI
v2.0.3 cannot unpack these Switch archives. CPK support covers the named,
uncompressed media containers found in the supplied game files. Unsupported
compression/container layouts fail explicitly. The Python extractor optionally
uses `lz4` for faster decompression and includes a fallback.

Each archive keeps its own folder, including numbered `nx_patch` layers and
nested DLC. CPK folders retain `.cpk`, avoiding collisions with matching MVGL
names. `_switch_extraction` contains completion records and SHA-256 manifests.
Repeated extraction verifies existing files and skips identical content;
different existing files are preserved unless the CLI's `--overwrite` is used.

**Extract MBE Tables From Folder** uses the existing MBE backend. Its Switch
filter includes base, numbered patches, all DLC, and English text. Tables go
under `Tables/nx64` or `Tables/ounce64`, with later numbered patches applied
after base tables. Disable the filter to retain every language and original
archive layer. Sparse `ounce64` DLC files are kept separate from the `nx64`
base game.

Switch support covers extraction and table inspection. The main Digimon
editor's Base/DLC loading and Reloaded II mod exports still target PC;
**Configure Paths** does not import the isolated Switch table layout. Switch
repacking, deployment, and cross-platform asset compatibility are not provided.

For command-line extraction (Python 3.11 or newer):

```powershell
py -u app/Switch_Archives.py "D:\Emulators\Ryujinx\Games\Extracted" "D:\Digimon Modding\Time Stranger - Switch - Extracted"
```

Compare either raw archive folders or extracted trees with `app/Compare_Assets.py`.

```powershell
py app/Compare_Assets.py --windows "D:\Programs\Steam\steamapps\common\Digimon Story Time Stranger\gamedata" --switch "D:\Emulators\Ryujinx\Games\Extracted" --output "D:\Digimon Modding\Time Stranger - Switch - Extracted\Comparison" --hash-ext ".geom,.mbe,.lua,.nlst"
```

The comparison normalizes archive names, path case, and numbered patch layers;
it keeps language, DLC, and CPK variants identifiable. Without `--hash-ext`,
equal size is reported as unverified, not equal content. Generated `Tables`
and `_switch_extraction` directories are excluded from extracted-tree inputs.
Use a report folder outside the input trees. `--switch-platform ounce64`
compares the sparse alternate-platform DLC separately. Results include model
IDs, extra LOD filenames, provenance CSVs, and a Markdown summary in the chosen
output folder.

## Mod workflow

### Field Guide

In the sidebar’s **Field Guide** section, choose **Installed Mod Slots…** to search by mod, species, or slot.
Select **Slot conflicts** to find shared numbers, select a mod row, and use
**Change slot…** to pick a free custom slot. The editor backs up the selected
status CSV before changing the assignment.

To make species visible without evolving them, close the game and choose
**Unlock Field Guide…** in the same section. The picker opens the game's
`gamedata\savedata` folder in your Steam library. Open your account folder
and choose **0000.bin** for the autosave. The Steam userdata copy is named
`savedata00.dat`. The **Autosave only** filter shows these two filenames.
Review the counts for the base game, DLC and installed
mod catalogue. **Apply** creates a dated, byte-verified backup beside the
selected slot before registering species. To restore, close the game and copy
the backup over the original slot filename. Run the unlocker again after
installing another species mod.

### Creating and editing mods

In **Create New → Select Template**, type any part of a Digimon name or character
ID in **Search templates**. The list filters as you type and shows the character
ID beside each name so you can distinguish variants.

The **Traits** tab lists traits alphabetically down each column. Choose
**Rename trait for mod…**, select the language and trait, then enter its new
name. This replaces the displayed name for every Digimon using that trait while
the mod is active. Trait assignments and game effects keep their original IDs.
The editor previews English names. For another language, configure the extracted
game folder so the editor can preserve the other names in that language.

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

To build a skill list for a loaded mod, open **Advanced → Skill Browser → New skill…**.
Search for a template by name or ID, or choose **Basic attack defaults**. Give
the skill its own English name and accept or change the suggested free ID.
The template supplies its battle properties and native animation and effect
references. Any mod supplying those assets must also be available in the game.

Select the new skill under **Skills → Signature Skills** or **Generic Skills**,
then choose **Save to Loaded Source**. You can also click **New skill…** on a
slot to clone and replace its current skill in one step. In the creation wizard,
use **Step 7 → Skills**. **Finish** saves the assigned new definitions together
with the Digimon.

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

See the [mod/skill audit](reference/Research/mod-skill-audit-2026-11-14.md) and
[Workshop skill reference](https://hyotan-dev.github.io/dstsworkshop/documentation/mbe/battle_skill/)
for the table mappings and validation details.

## How it works

The Python sources and application assets live in `app/`. `Data_Loader.py`
resolves Base, DLC and mod tables. `digimon_editor.py` presents those rows in the
editor. `CSV_Exporter.py` and `Mod_Tables.py` preserve runtime headers and merge
changes into the mod layout. MVGL Tools extracts and repacks native archives
and tables using the bundled backend.

For model and animation conversion, use the companion
[Time Stranger Importer](https://github.com/ElderLich/Time-Stranger-Importer).
Native New Century skill-effect, camera and audio conversion for in-game use
is **in progress**; this editor does not convert Unity prefabs or sound banks.

## Development

From the repository root, run the tests or build the Windows applications.

```powershell
py -m unittest discover -s tests -v
py -m compileall -q app
py -m pip install PyInstaller
py -m PyInstaller packaging/art_studio.spec
py -m PyInstaller packaging/digimon_editor.spec
```

The packager writes the executables to `dist/`. The `reference/` folder
holds the header reports, Lua files and research notes.

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
