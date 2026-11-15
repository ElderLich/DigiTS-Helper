"""Locate editable Studio files and external tools independently of the launch directory."""
from pathlib import Path
import sys


def studio_root() -> Path:
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parents[1]
    folder = Path(sys.executable).resolve().parent
    if folder.name.casefold() == "dist" and (folder.parent / "app/digimon_editor.py").is_file():
        return folder.parent
    return folder


def table_root(root=None) -> Path:
    root = studio_root() if root is None else Path(root)
    if not (root / "data/Base").is_dir() and (root / "Base").is_dir():
        return root
    return root / "data"


def dependency(folder: str, filename: str, root=None) -> Path:
    root = studio_root() if root is None else Path(root)
    locations = [root / "dependencies" / folder, root / "_internal", root]
    if folder == "mvgl":
        locations.append(root.parent)  # Older MVGL GUI installations.
    for directory in locations:
        path = directory / filename
        if path.is_file():
            return path
    return locations[0] / filename
