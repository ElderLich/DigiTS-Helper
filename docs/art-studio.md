# Portraits and dot sprites

Open **Time Stranger Art Studio.cmd** from the repository root.

## Make a dot sprite

**Dot Sprites** opens an existing sprite sheet or native dot atlas. Select a
16 × 16 source frame and click its position in the four-frame game atlas.
The enlarged preview keeps the pixels square. Enter the Digimon ID, choose
the mod or staging folder and click **Export dot sprite**.

## Make a portrait

**Portraits** opens a GLB, glTF, native GEOM or an existing transparent
PNG. For a model, adjust **Camera turn** and **Tilt** before clicking **Render
preview**. Drag a square around the face and check **Game portrait**.
The preview applies the tutorial's teal color treatment, red/blue channel
offset, selective black adjustment and hard shadow. Its opacity includes
the model and its shadow. **Save styled PNG…** saves a 512 × 512 cutout.
To install a game icon, enter the icon ID from the Digimon's `char_info`
row, choose the mod or staging folder and click **Save profile picture**.
This creates a 512 × 512 BC7 texture with ten mip levels.

For a face crop, compare the eye line and face size with the base form’s official icon in the extracted game assets.

## Output files and tools

Both tabs write to `dsts-loader/patch/images` in the chosen mod. For Leviamon X,
Digimon ID 761 and icon ID 761 produce `dot761.img` and `ui_chara_icon_761.img`.
Model capture uses Blender. GEOM requires the Time Stranger Importer addon.
Native portrait export uses NVIDIA Texture Tools' `nvcompress.exe`. The app
can prompt for either executable on first use. Sprite sheets and transparent
PNG inputs open directly.

[Back to the Mod Studio guide index](../README.md#guides)
