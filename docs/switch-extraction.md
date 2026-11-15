# Extract Switch archives and compare assets

In **MVGL Tools**, select **Time Stranger (Switch)**, then **Extract MVGL
Archive**. Batch mode reads `.mvgl` and `.cpk` files recursively, including DLC
subfolders. The default source is `D:\Emulators\Ryujinx\Games\Extracted`, and the
default output is `D:\Digimon Modding\Time Stranger - Switch - Extracted`.
Inputs must already be decrypted game archives.

## Archive formats and output

Switch archives use different MVGL record widths from PC. `app/Switch_Archives.py`
handles both `nx64` and `ounce64` variants directly. On PC the bundled backend is MVGLToolsCLI v2.0.3. CPK support covers the named,
uncompressed media containers found in the supplied game files. Unsupported
compression/container layouts fail explicitly. The Python extractor optionally
uses `lz4` for faster decompression and includes a fallback.

Each archive keeps its own folder, including numbered `nx_patch` layers and
nested DLC. CPK folders retain `.cpk`, avoiding collisions with matching MVGL
names. `_switch_extraction` contains completion records and SHA-256 manifests.
Repeated extraction verifies existing files and skips identical content. Replacing different files requires the CLI’s `--overwrite` is used.

## Extract MBE tables

**Extract MBE Tables From Folder** uses the existing MBE backend. Its Switch
filter includes base, numbered patches, all DLC, and English text. Tables go
under `Tables/nx64` or `Tables/ounce64`, with later numbered patches applied
after base tables. Disable the filter to retain every language and original
archive layer. Sparse `ounce64` DLC files are kept separate from the `nx64`
base game.

Switch support covers extraction and table inspection. The main editor reads PC Base/DLC tables and exports PC Reloaded II mods.

To extract from the command line, use Python 3.11 or newer.

```powershell
py -u app/Switch_Archives.py "D:\Emulators\Ryujinx\Games\Extracted" "D:\Digimon Modding\Time Stranger - Switch - Extracted"
```

## Compare Switch and PC assets

Compare either raw archive folders or extracted trees with `app/Compare_Assets.py`.

```powershell
py app/Compare_Assets.py --windows "D:\Programs\Steam\steamapps\common\Digimon Story Time Stranger\gamedata" --switch "D:\Emulators\Ryujinx\Games\Extracted" --output "D:\Digimon Modding\Time Stranger - Switch - Extracted\Comparison" --hash-ext ".geom,.mbe,.lua,.nlst"
```

The comparison normalizes archive names, path case, and numbered patch layers. It keeps language, DLC, and CPK variants identifiable. Supply `--hash-ext` to verify matching file contents. A size-only match is reported as unverified. Generated `Tables`
and `_switch_extraction` directories are excluded from extracted-tree inputs.
Use a report folder outside the input trees. `--switch-platform ounce64`
compares the sparse alternate-platform DLC separately. Results include model
IDs, extra LOD filenames, provenance CSVs, and a Markdown summary in the chosen
output folder.

[Back to the Mod Studio guide index](../README.md#guides)
