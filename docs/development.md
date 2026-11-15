# Development and packaging

The Python sources and application assets live in `app/`. `Data_Loader.py`
resolves Base, DLC and mod tables. `digimon_editor.py` presents those rows in the
editor. `CSV_Exporter.py` and `Mod_Tables.py` preserve runtime headers and merge
changes into the mod layout. MVGL Tools extracts and repacks native archives
and tables using the bundled backend.

Blender model, motion and native presentation exports are covered in the companion importer. [Time Stranger Importer](https://github.com/ElderLich/Time-Stranger-Importer)

## Run tests and build Windows executables

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

[Back to the Mod Studio guide index](../README.md#guides)
