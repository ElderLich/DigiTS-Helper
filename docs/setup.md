# Install and configure Mod Studio

On Windows, double-click **Time Stranger Mod Studio.cmd** to edit Digimon
and mods. Double-click **Time Stranger Art Studio.cmd** for sprites and
portraits. Each launcher opens its executable in `dist/` when available.
Otherwise it starts the application from `app/` using the Windows Python
launcher. Install the source dependencies once if you use that route.

```powershell
py -m pip install -r dependencies/requirements.txt
```

## Archive and Lua tools

For archives, double-click **MVGL Tools.cmd**. For Lua scripts, double-click
**Lua Decompiler.cmd**. Both launchers are in the repository root. MVGL Tools uses Tkinter, included with the standard Windows Python installer. Lua decompilation also requires Java.

## Configure game data

The main editor reads extracted base tables from `data/Base/data` and
`data/Base/text`, with optional DLC tables under `data/DLC` (addcont_01–03 and 17 in the bundled table set). Use **Configure Paths** to set your extracted
game folder and Reloaded II Mods folder. Machine-specific paths are saved in
the ignored `Time_Stranger_Mod_Studio_Paths.json` file. Existing installations
can keep their saved paths when upgrading.

Bundled tools live under `dependencies/`. The MVGL backend and its support
files are in `mvgl/`, CPK tools are in `cpk/`, DSCSTools is in `dscs/`
and the Lua decompiler is in `unluac/`.
See the [extraction guide](https://hyotan-dev.github.io/dstsworkshop/tutorials/extractdata/)
for preparing game data.

[Back to the Mod Studio guide index](../README.md#guides)
