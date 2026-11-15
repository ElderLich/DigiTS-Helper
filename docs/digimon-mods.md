# Create, edit and export a Digimon

## Choose a template

In **Create New → Select Template**, type any part of a Digimon name or character
ID in **Search templates**. The list filters as you type and shows the character
ID beside each name so you can distinguish variants.

1. **Load a mod or choose a template.** Adding a new entry stages a copy. Choose
   its Digimon ID, Chr ID, character key and Field Guide ID before saving.
2. **Edit the data.** The editor checks ID collisions and keeps related rows
   connected. The editor preserves custom filenames across the ten LOD slots, locator references and related motion rows.
3. **Save to Loaded Source** to update that source. For an imported mod, this
   merges the selected entry into its payload while retaining unrelated rows.
4. **Export / Copy Mod** to create a separate mod. Save your form edits first
   when exporting the loaded source.

## Export structure

The resulting folder opens in Reloaded II.

```text
My Mod/
├── ModConfig.json
└── dsts-loader/
    ├── patch/data/
    └── patch_text01/text/
```

Optional tables are included when source data exists. For example,
`model_locator.mbe` needs a captured locator reference, and
`002_chronodevolution.ap.csv` needs known form IDs. The latter controls the transformation used by Chronomon’s final-boss attack. Edit it through **Evolution → Edit Chrono Devolution Forms**.

## Mode changes

In **Evolution**, add a **Mode Change path** from the base form to the new form and a return path. Reopen the exported entry and check both directions. Use the new model and animation reference for a form with its own exported rig and motions.

## Rename a trait

The **Traits** tab lists traits alphabetically down each column. Choose
**Rename trait for mod…**, select the language and trait, then enter its new
name. This replaces the displayed name for every Digimon using that trait while
the mod is active. Trait assignments and game effects keep their original IDs.
The editor previews English names. For another language, configure the extracted
game folder so the editor can preserve the other names in that language.

[Back to the Mod Studio guide index](../README.md#guides)
