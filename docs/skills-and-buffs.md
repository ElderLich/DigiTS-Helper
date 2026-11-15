# Skills and buffs

## Clone and assign a skill

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

## Compatibility and buffs

- To nullify unfavorable compatibility, use Advanced Skills → Additional Property
  2 → value **3**. Value **9** is the attribute-only variant.
- Buff sets combine up to eleven effect IDs. Choose known effects or enter
  an ID directly, then assign the set to the skill's condition, target/user
  application, or removal field.
- Clone or edit `battle_buff` rows in the active mod,
  including custom elemental definitions already present there. Unknown columns remain available as raw values. A new ID reuses behavior supported by the
  game engine.

With an active mod, saving a Base/DLC skill creates an override for that skill
in the mod's patch. Buff definitions and sets are saved immediately. Save the
skill afterward to assign the set. Extract packed `.mbe` replacements to CSV
before importing them through this workflow.

See the [mod/skill audit](../reference/Research/mod-skill-audit-2026-11-14.md) and
[Workshop skill reference](https://hyotan-dev.github.io/dstsworkshop/documentation/mbe/battle_skill/)
for the table mappings and validation details.

[Back to the Mod Studio guide index](../README.md#guides)
