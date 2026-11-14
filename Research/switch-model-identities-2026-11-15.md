# Identities of the 29 Switch-only non-LOD model filenames

Investigated on 2026-11-15 using the supplied Switch extraction and the installed
Windows archives/extraction. All 29 GEOMs were parsed and rendered, their
textures and skeletons inspected, and model/field/scene references compared.

## Conclusion

**None of these 29 models is a Digimon.** They comprise **3 human NPC models**
and **26 scenery, prop, or environmental-effect models**. No new proper
character name or localized individual model name was established. The readable
object descriptions below come from visual inspection, supported by internal
mesh/material names; they are not invented official game names.

The initial count measured filenames absent from the Windows archive inventory.
It did not establish 29 new designs. Several of these objects already occur
under different names, as modular variants, or inside Windows scene geometry.

## The three human models

| File | Observed identity | Evidence |
| --- | --- | --- |
| `mob010.geom` | Unnamed soldier/guard: helmet with goggles, uniform, equipment pouches, boots and rifle | Human skeleton with 33 ordered bone hashes matching Windows `mob030`. Both platforms already have `mob010` model-setting/union-model rows. No confirmed placement or character-name link was found. |
| `npc105k.geom` | Unnamed male theater crowd NPC wearing a tailcoat/long formal coat | 70 ordered bone hashes match existing `npc105` rigs. Animation mapping explicitly reuses `npc105a`; corresponding Windows actors use `npc105ii010101`. |
| `npc106k.geom` | Unnamed female theater crowd NPC wearing a long dress, long gloves, necklace and cloche-style hat | Same 74 bone-name/hash set as existing `npc106` rigs. Animation mapping reuses `npc106a`; corresponding Windows actors use `npc106ii010101`. |

The field tables establish **32 replacements of existing actors**, preserving
their IDs and labels: 18 male and 13 female instances in **The In-Between
Theater**, plus one male instance in **Elevator Hall**. This is direct evidence
of crowd-model replacement, rather than newly introduced named characters.

`mob010` is the least resolved of the three. Its actual shape is a human soldier,
but no formal identity, organization, or active scene placement was established.
Its referenced diffuse texture `mob010_B01.img` is absent from the supplied
Switch image files. The preview therefore shows neutral material for that part;
no replacement texture was guessed. The rifle at its feet is in the static
inspection pose, not an observed in-game animation.

Two misleading name matches were explicitly rejected:

- A Central Town field actor whose **label** is `mob010` actually selects
  `chr437`; it does not identify or place this human mesh.
- `char_SPECIAL_FORCES` maps to `chr811`, not `mob010` or `mob030`. A rifle bone
  alone is insufficient to call this model the named Special Forces character.

## All 26 environment models

Area names are the game's English labels where a direct scene/table association
exists. **Family** means the area association is inferred from the filename
family; exact placement was not established.

| Model basename | Visual description | Area / association | Windows comparison |
| --- | --- | --- | --- |
| `d0109step02` | Linked cogwheel/gear platforms | Chill Cosmic: Throne Room | Switch instance suffixes match Windows `d01step02` in the same scene; same seven textures. |
| `d0202hlow6fa` | Tall patchwork/shanty building section | Central Town: Downtown | Existing `d0202hlow6fa1` family; authored names also occur in Windows `d0277b`. |
| `d02desk03a` | Round barrel table with cups and a container | Central Town: Shanty | Authored mesh names already appear in Windows `d0203f`, `d0204f`, and `d02planter02a`; shares textures with `d02desk03b`. |
| `d02drum01f` | Stack of colored metal barrels | Central Town family | Shares all four textures with existing Windows `d02drum01` variants. |
| `d02friger01c` | Open chest refrigerator/freezer components | Central Town family | Shares all four textures with Windows `d02friger01a/b`. |
| `d02hut01e_a` | Multi-storey patchwork house/shack | Central Town family | Shares 12 textures and mesh lineage with Windows `d02hut01e/e1/e2`; exact separate-variant use unresolved. |
| `d02island02b` | Multi-level circular market/platform structure with awnings and furnishings | Central Town family | Shares all 15 textures with Windows `d02island02a`; related floor/gear/hut/leaf components. |
| `d02lamp07a` | Hanging lamp with supporting wire | Central Town: Shanty | Exact authored groups/meshes already occur in Windows scenes; related `d02lamp07a1`. |
| `d02lamp07b` | Hanging cable/pendant component | Central Town: Shanty | Exact authored mesh names already occur in Windows `d0203f` and `e0003f`. |
| `d02shop01c` | Rustic counter with three stools and surrounding containers | Central Town family | Shares all four textures with existing Windows `d02shop01` variants. |
| `d02tapestry01a` | Rectangular patterned textile/banner | Warrior's Watering Hole | Exact authored objects already occur in Windows `d0204f`; shared tapestry textures. |
| `d02tapestry03b` | Rectangular patterned hanging textile with decorative lower panels | Central Town family | Shares all four textures with Windows `d02tapestry03a`; nine-bone cloth/prop rig. |
| `d02tapestry03c` | Curved/draped patterned textile with decorative lower panels | Central Town family | Shares all four textures with Windows `d02tapestry03a`; two-bone static prop. |
| `d09sky` | Purple sky/cloud shell and associated environmental geometry | Akashic Records: Periphery / wider d09 scene family | Exact `d09sky` node and all five textures already occur in Windows scene geometry, including `d0900f/d0901f/d0905f`. |
| `flag01d` | Freestanding advertising banner on a weighted base | Shinjuku: Kabukicho, Theater Square | Existing flag family and shared textures. Scene instance counts suggest a `flag01c` replacement; exact transform equivalence was not established. |
| `h0201tube02b` | Tall cylindrical tube/shaft and effect/occlusion components | Outer Dungeon family | Shares `h02_pattern01_C` with Windows `h0201tube01a`; exact placement unresolved. |
| `h02line02a` | Thin curved line/ribbon effect mesh | Outer Dungeon family | Exact authored mesh name preserved in Windows `h08line02a`; Switch 656 vertices versus Windows 2,624. |
| `h02line02b` | Thin curved line/ribbon effect mesh | Outer Dungeon family | Exact authored mesh name preserved in Windows `h08line02b`; 656 versus 2,624 vertices. |
| `h02line02c` | Thin curved line/ribbon effect mesh | Outer Dungeon family | Exact authored mesh name preserved in Windows `h08line02c`; 656 versus 2,624 vertices. |
| `h02line02d` | Thin curved line/ribbon effect mesh | Outer Dungeon family | Exact authored mesh name preserved in Windows `h08line02d`; 656 versus 2,624 vertices. |
| `h02line02e` | Thin curved line/ribbon effect mesh | Outer Dungeon family | Related `h02line/h08line` family; exact counterpart not established. |
| `h02line02f` | Thin curved line/ribbon effect mesh | Outer Dungeon family | Related `h02line/h08line` family; exact counterpart not established. |
| `h02line02g` | Thin curved line/ribbon effect mesh | Outer Dungeon family | Exact authored mesh name preserved in Windows `h08line02g`; 656 versus 2,624 vertices. |
| `h02line02h` | Thin curved line/ribbon effect mesh | Outer Dungeon family | Exact authored mesh name preserved in Windows `h08line02h`; 656 versus 2,624 vertices. |
| `t0107toilet02` | Blue portable toilet cubicle | Wall of Hope | Same mesh name and all four textures as Windows `t0107toilet01`. Two new-name plus four old-name instances replace six Windows old-name instances. |
| `t0201gate` | Tall narrow gate/barrier frame with a base mechanism | Akihabara Station: Electric Town South Exit family | Same `gate01_mesh` name and all five textures as Windows `t0201gate01`; direct placement of the new standalone basename unresolved. |

The environmental line/tube models use animated or specialized game shaders.
Their static previews show the underlying meshes, including occlusion geometry
where present; the game's full animated appearance is not reproduced.

## Preview gallery and evidence

Saved beside the extraction at:

`D:\Digimon Modding\Time Stranger - Switch - Extracted\Comparison\ModelIdentities`

- `gallery/human-models.png`: the three human models.
- `gallery/environment-models-1.png` and `gallery/environment-models-2.png`:
  all 26 props/effects with filenames.
- `all-29-renders/`: individual previews, source hashes, texture paths,
  dimensions, and warnings in `render-report.json`.
- `identification-table.json`, `all-29-geometry.json`: geometry, skeleton,
  material/texture, and Windows-family evidence.
- `names-and-usage.json`: localized area names, actor replacements, exact
  scene-name evidence, and distinctions between direct and family associations.
- `reference-hits.json`, `nlst-reference-hits.json`,
  `scene-embedded-references.json`: supporting references.
- `inspect_geom.py`, `render_switch_models.py`, `build_contact_sheets.py`:
  reproducible local inspection/rendering scripts.

Validation: **29/29 models rendered**, all **46 Switch material blocks**
validated, and all **29 original source hashes unchanged** after rendering.
All referenced preview textures were found except `mob010_B01.img`.

The disposable renderer normalizes observed Switch index/primitive/attribute
tags and converts the material record layout (30 shader keys, header `0x6A8`)
to the existing inspection backend's PC layout (14 keys, header `0x328`) in
temporary copies. Original geometry payloads/textures remain the evidence;
lighting and native shader interpretation are approximate. This is an
inspection workflow, not a validated Switch-to-PC mod conversion feature.

No source game assets, installed mods, Blender preferences, or production
importer code were changed. Rendered game assets and large generated evidence
files remain local and are not committed to the source repository.
