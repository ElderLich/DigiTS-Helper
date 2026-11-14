# Switch / Windows extraction and asset audit — 2026-11-15

## Result

No additional Digimon model IDs or Digimon status IDs were found in the supplied
Switch dump relative to the installed Windows version. Switch has many extra
model filenames, principally lower-detail variants, plus platform-specific
NPC/environment variants and rendering data. The extra anime-song audio banks
reflect different DLC coverage; the evidence does not establish platform
exclusivity.

## Inputs and extraction

- Switch archives: `D:\Emulators\Ryujinx\Games\Extracted`, including nested
  `DLC`, `nx_patch_01` through `nx_patch_03`, all supplied languages/voices,
  and four `ounce64` DLC archives.
- Output: `D:\Digimon Modding\Time Stranger - Switch - Extracted`.
- Windows archives: `D:\Programs\Steam\steamapps\common\Digimon Story Time Stranger\gamedata`.
  These include the CPK media omitted from the existing extracted tree at
  `D:\Digimon Modding\Time Stranger Extracted`.
  All **196,663 Windows MVGL paths and uncompressed sizes** match that extracted
  tree, with no missing/extra paths or size mismatches; this check did not hash
  every existing Windows extracted file.
- Extracted **115 archives**: **110 MVGL + 5 CPK**, **208,973 files**,
  **31,303,966,143 bytes** (31.30 GB / 29.15 GiB). No archive failures.
- Verified every output file against its manifest size and re-read SHA-256 for
  **336 deterministic samples** across the archives. The extractor hashed every
  decoded payload during extraction. Manifests are in `_switch_extraction`.
- The non-archive `nx_save_data_owner_ids` input is not part of archive extraction.

The supplied Switch dump contains DLC IDs 05–10, 12–15, and 17. Windows includes
DLC 01–03, 05–08, 12–15, and 17. In particular, the Windows files contain the
additional story-DLC Digimon; the supplied Switch folder has no separate
`addcont_01`, `addcont_02`, or `addcont_03` archives.

## Comparable inventory

The main comparison uses `nx64`. It compares case-normalized logical resource
paths rather than archive folder names. Numbered patches override earlier base
variants within their namespace. Languages, independent DLC, developer layers,
and CPK/MVGL variants retain provenance. This is a static asset comparison, not
a runtime load-order or unlockability test.

| Measure | Windows | Switch nx64 |
| --- | ---: | ---: |
| Files across archive layers | 197,157 | 207,381 |
| Logical paths | 172,251 | 186,447 |
| Unique `.geom` paths | 15,296 | 21,362 |
| `chrNNN` model IDs | 579 | 543 |
| Digimon status IDs, including variant/boss rows | 635 | 603 |

There are **116,401 common logical paths**, **70,046 Switch-only paths**, and
**55,850 Windows-only paths**. These totals include shader formats, languages,
LOD files, and different DLC coverage; they are not counts of new gameplay
assets. In particular, **48,738** Switch-only paths are `.shad` files.

The four `ounce64` archives contain another **1,592 physical files** / **1,320
logical paths**. They contain **no `.geom` files**, so they add no character
model IDs. They are sparse DLC supplements, not a full alternate-platform dump.

## Models and Digimon

- **0 Switch-only `chrNNN` model IDs**; **36 Windows-only model IDs**.
- **0 Switch-only Digimon status IDs**; **32 Windows-only status IDs**.
  These are table records, not a playable roster count. The absent Switch rows
  include story-DLC forms such as BlitzGreymon, CresGarurumon, several Omnimon
  forms, X Antibody forms, and Bancho forms.
- **6,693 Switch-only model filenames**: **6,664 numbered LOD variants** and
  **29 non-LOD variants**. **6,564** of those LODs have an exact corresponding
  Windows base-model filename. The remainder requires variant-name matching;
  none introduces a new `chrNNN` model ID.
- `npc105k` and `npc106k` are replacement human NPC variants. Switch
  `anim_setting_nx` maps them to existing `npc105a` / `npc106a` animation families.
  Shared `t3001` mob records 6002001–6002003 use Windows
  `npc105ii010101` / `npc106ii010101` and Switch `npc105k` / `npc106k`.
- `mob010` already appears in Windows model-setting/union-model references,
  although the supplied Windows archives lack its standalone geometry. Its
  Switch geometry does not by itself establish a new NPC identity.

All 29 non-LOD Switch-only geometry filenames:

```text
d0109step02       d0202hlow6fa      d02desk03a        d02drum01f
d02friger01c      d02hut01e_a       d02island02b      d02lamp07a
d02lamp07b        d02shop01c        d02tapestry01a    d02tapestry03b
d02tapestry03c    d09sky           flag01d          h0201tube02b
h02line02a        h02line02b       h02line02c       h02line02d
h02line02e        h02line02f       h02line02g       h02line02h
mob010           npc105k          npc106k          t0107toilet02
t0201gate
```

These are filename-level differences; visual novelty of every environment/prop
variant was not established by rendering each model. Existing Switch models
can also differ from Windows under the same name. For example, both platforms
use DDS data in `images/chr001a01.img`, but the inspected Switch texture is
512×512 versus 1024×1024 on Windows. Extracting files does not guarantee they
can be dropped into Windows mods without conversion.

## Other differences

- **16 additional audio banks**, `bgm506.acb` through `bgm521.acb`, occur in
  `DLC/addcont_09.nx64.cpk`. These are the anime-song DLC (including Butter-Fly,
  brave heart, and First Riders). Windows has byte-identical `bgm_setting.mbe`
  and English `bgm_name.mbe` with these IDs, but its supplied installation lacks
  `addcont_09.dx11.cpk`. This is an observed DLC coverage difference.
- **43 additional MBE paths** include Switch animation/model/LOD overrides,
  culling/shadow/UI/settings tables, `battle_enemy_dlc10`, `quest_sub_dlc10`,
  small developer lists, and per-language `common_message_nx64` tables. Table
  presence alone does not demonstrate an exclusive quest or playable character.
- **No Switch-only Lua filenames** were found.
- Additional shaders, scene/physics variants, and UI/texture resources are
  listed with exact archive provenance in the detailed CSVs.

## Content comparison and evidence

SHA-256 comparison was enabled for common `.geom`, `.mbe`, `.lua`, and `.nlst`
paths. **16,896** common paths have a matching content variant; **16,929**
differ in content. Other extensions use size only: **28,694** differ in size
and **53,882** have matching sizes with content unverified. A differing hash
does not distinguish platform conversion from semantic content changes.

| Common extension | Matching content variant | Different content |
| --- | ---: | ---: |
| `.geom` | 0 | 14,669 |
| `.mbe` | 3,221 | 47 |
| `.lua` | 1,178 | 41 |
| `.nlst` | 12,497 | 2,172 |

Detailed local evidence is saved beside the extraction in `Comparison`:

- `comparison.md`, `summary.json`, `common_paths.csv`, `only_switch.csv`,
  `only_windows.csv`, and `models.csv`.
- `roster-audit.json`: parsed `digimon_status_data` and English name records.
- `variant-reference-hits.json` / `variant-table-rows.json`: NPC/music table
  references used to distinguish variants and DLC coverage.
- `extraction-verification.json`: post-extraction checks.
- `windows-baseline-check.json`: existing Windows extraction coverage check.
- `ounce64/`: independent comparison of the four sparse alternate variants.

The source changes and regression tests are in this repository; extracted game
assets and the large generated CSV inventories are not committed.

Reproduce extraction/comparison using the commands in the main README. Switch
MBE samples were also parsed by `MBEEditor._parse_mbe_data` and exported by the
bundled MVGLToolsCLI with `--game=dsts --mode=unpack-mbe`. Main-editor loading,
Switch repacking, and mod deployment are outside the implemented support.

Validation: all **41 regression tests** pass with process exit 0, and every
top-level helper Python module compiles. Tk state checks run in subprocesses;
the existing Qt test editor is explicitly destroyed before interpreter shutdown
to avoid a native teardown crash observed during full-suite validation.
