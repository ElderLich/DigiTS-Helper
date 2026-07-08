# DigiTS Helper

Tools for Digimon Story Time Stranger data editing, extracted MBE/CSV review,
MVGL extraction helpers, and Reloaded II `dsts-loader` mod import/export.

This repository was split from:

```text
D:\Digimon Modding\Programs\DigiTS Helper
```

The standalone split intentionally excludes the old `Misc` folder.

## Main Tools

- `digimon_editor.py` - main PyQt Digimon editor.
- `data_loader.py` - base/DLC data loading and table helpers.
- `mvgl_tools_gui.py` - GUI wrapper for MVGL extraction/repack operations.
- `csv_exporter.py` and `MBE_Editor.py` - CSV/MBE inspection and export tools.

## Data Folders

- `Base` - extracted base game data used by the helper.
- `DLC` - supported add-on data folders.
- `Header Reports` - reference notes for Time Stranger table headers.
- `MVGLTools` - local MVGL command-line tooling used by the GUI.

Generated caches and local extraction output are ignored by Git.
