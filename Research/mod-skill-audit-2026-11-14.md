# Mod tables and skill editor audit — 14 November 2026

The report concerns the Reloaded II import/export and Advanced Skills paths.
Installed mods were inspected read-only. The screenshot's folder is
`lod_chara.mbe`, not `load_chara.mbe`.

## Findings and repairs

| Area | Defect | Result |
| --- | --- | --- |
| LOD | Import discarded the model row; save regenerated one fixed LOD name and zeroed later distances | All ten distances and model slots survive import/save |
| Model locators | Main mod save omitted both tables; import discarded their data | Locator and motion rows are read from app_0/patch and merged by character/motion key |
| Locator cloning | Template clone renamed the LOC asset reference without creating the asset | New character keeps the source locator reference |
| Chrono Devolution | The table was absent from import/save | Captured six-stage forms are preserved, template self-ID is remapped, and an explicit editor supplies new forms |
| Compatibility | Compact dropdown index wrote 2 for effect ID 3 | Dropdown stores explicit game IDs, including unknown loaded values |
| Damage / conditional effect | Other sparse enums were also shifted; conditional apply-buff entry was missing | Fixed damage, healing, major damage and conditional recovery use their actual IDs |
| Conditional amount | Column 50 could not be edited | Separate Effect Argument control preserves/edits that value |
| Skill save | Unexposed name, fixed description and target fields were reset; CSV joins broke quoted text | Only supplied fields change and CSV strings roundtrip |
| Buff sets | New files used friendly workspace headers; automatic assignment used the condition-only slot | Runtime typed headers and explicit apply/remove labels; automatic assignment uses Apply to target |
| Custom effects | Discovery read Base battle_buff only | Active mod and DLC definitions are selectable; raw effect IDs are accepted |
| Buff definitions | No authoring path | Clone/edit the full typed row into the active mod, preserving undocumented columns |
| Base skill in mod | Adding a custom set to a Base skill saved the skill to Base | Selected skill becomes a one-row mod override before edits |

Optional locator rows are written only when supplied by a template or mod.
Chrono Devolution is a specific boss mechanic, not a generated reverse
evolution graph. Missing source forms need explicit choices in the editor.

## Local evidence

The installed mod tree contained 48 patch `lod_chara.mbe` folders, 21 patch
`model_locator.mbe` folders and 38 `002_chronodevolution.ap.csv` files.
These counts describe this local snapshot; folder presence alone does not
prove a mod's in-game behavior.

The updated import path read:

| Mod | Digimon | Locator rows | Chrono rows | LOD model rows |
| --- | ---: | ---: | ---: | ---: |
| 4 Digimon Sovereign | 6 | 6 | 6 | 6 |
| WarGreymon X Antibody | 1 | 1 | 0 | 1 |
| Sabedramon | 1 | 0 | 1 | 1 |
| Youkomon | 2 | 0 | 0 | 2 |

Custom `battle_buff` patches exist in nine installed mods, including
4 Digimon Sovereign and Beelzemon X. No authorship is inferred from filenames;
this audit does not identify which file is the modder Mastemon's original.

## Sources and validation

- [Workshop: skill damage and extra effects](https://hyotan-dev.github.io/dstsworkshop/documentation/mbe/battle_skill/#damage)
- [Workshop: buff sets](https://hyotan-dev.github.io/dstsworkshop/documentation/mbe/battle_skill/#002_buff_setcsv)
- [Workshop: Chrono Devolution](https://hyotan-dev.github.io/dstsworkshop/documentation/mbe/evolution/#002_chronodevolutioncsv)
- `Header Reports/DSTS_Header_Report.md`: captured native column types.
- `Base/data` and installed mod CSVs: row and overlay evidence.

Regression tests cover actual offscreen PyQt controls, temporary full mod
merge/import with unrelated Digimon preserved, custom definitions and sets,
typed headers, explicit ID entry, sparse skill enum IDs, hidden-field and
quoted-string preservation, template Chrono self-ID remapping, and Base skill
copy without altering Base data. Python compilation covers every top-level
helper module. No in-game battle acceptance is claimed by these tests.
