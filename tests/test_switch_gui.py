"""Archive/table planning regressions; no installed game files are changed."""
from pathlib import Path
from functools import wraps
import subprocess
import sys
import tempfile
import tkinter as tk
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
TK_CHILD_FLAG = "--isolated-tk"
RUNNING_TK_CHILD = __name__ == "__main__" and TK_CHILD_FLAG in sys.argv
if RUNNING_TK_CHILD:
    sys.argv.remove(TK_CHILD_FLAG)

from mvgl_tools_gui import MVGLToolsGUI


def isolated_tk(test_method):
    """Keep Tcl/Tk teardown out of the process used by the PyQt editor tests."""
    @wraps(test_method)
    def run(self):
        if RUNNING_TK_CHILD:
            return test_method(self)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), TK_CHILD_FLAG, "-v",
             f"{type(self).__name__}.{test_method.__name__}"],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        if "Tk display unavailable:" in output:
            self.skipTest(output.strip())
    return run


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def planner(game="dsts-switch"):
    gui = MVGLToolsGUI.__new__(MVGLToolsGUI)
    gui.game_var = Value(game)
    gui.dsts_base_english_only_var = Value(True)
    gui.cli_path = "MVGLToolsCLI.exe"
    return gui


class SwitchGUIPlanningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source"
        self.target = Path(self.temp.name) / "tables"
        self.source.mkdir()

    def table(self, path):
        target = self.source / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"EXPA")
        return target

    def test_windows_editor_filter_keeps_existing_dlc_scope(self):
        gui = planner("dsts")
        for name in ("app_0.dx11", "patch.dx11", "app_text01.dx11", "patch_text01.dx11",
                     "addcont_01.dx11", "addcont_03_text01.dx11", "addcont_17.dx11"):
            self.assertTrue(gui.should_include_dsts_archive(name), name)
        for name in ("addcont_12.dx11", "app_text00.dx11", "addcont_17_text02.dx11",
                     "app_0.nx64", "addcont_17.ounce64", "addcont_17_dev.dx11"):
            self.assertFalse(gui.should_include_dsts_archive(name), name)

    def test_switch_includes_all_dlc_patches_and_both_variants(self):
        gui = planner()
        for name in ("app_0.nx64", "nx_patch_03.nx64", "nx_patch_10_text01.nx64",
                     "addcont_05.nx64", "addcont_12.ounce64", "addcont_06_dev.nx64",
                     "addcont_17_text01.nx64", "app_0.nx64.cpk"):
            self.assertTrue(gui.should_include_dsts_archive(name), name)
        for name in ("app_0.dx11", "patch.dx11", "nx_patch_03_text00.nx64",
                     "addcont_17_text30.nx64", "app_voice01.nx64"):
            self.assertFalse(gui.should_include_dsts_archive(name), name)

    def test_recursive_plan_keeps_platforms_and_dlc_separate(self):
        self.table("app_0.nx64/data/common.mbe")
        self.table("DLC/addcont_12.nx64/data/extra.mbe")
        self.table("DLC/addcont_12.ounce64/data/extra.mbe")
        self.table("DLC/addcont_12_dev.nx64/data/debug.mbe")
        self.table("DLC/addcont_12_text01.nx64/text/name.mbe")
        self.table("DLC/addcont_12_text00.nx64/text/name.mbe")
        self.table("app_0.dx11/data/windows.mbe")
        gui = planner()
        commands, scan = gui.build_recursive_mbe_commands("unpack-mbe-dir", "dsts-switch", self.source, self.target)
        self.assertEqual((scan["included_files"], scan["skipped_files"]), (5, 2))
        self.assertEqual({Path(command[-1]).relative_to(self.target).as_posix() for command in commands}, {
            "nx64/Base/data", "nx64/DLC/addcont_12.nx64/data/mbe",
            "ounce64/DLC/addcont_12.ounce64/data/mbe", "nx64/DLC/addcont_12_dev.nx64/data/mbe",
            "nx64/DLC/addcont_12_text01.nx64/text/mbe",
        })
        self.assertTrue(all(command[1] == "--game=dsts" for command in commands))

    def test_numbered_patches_override_base_in_numeric_order(self):
        for archive in ("nx_patch_10.nx64", "nx_patch_2.nx64", "app_0.nx64"):
            self.table(f"{archive}/data/status.mbe")
        commands, _scan = planner().build_recursive_mbe_commands("unpack-mbe-dir", "dsts-switch", self.source, self.target)
        self.assertEqual([Path(command[-2]).parent.name for command in commands],
                         ["app_0.nx64", "nx_patch_2.nx64", "nx_patch_10.nx64"])
        self.assertEqual({command[-1] for command in commands}, {str(self.target / "nx64/Base/data")})

    def test_unfiltered_mode_preserves_all_original_layers(self):
        self.table("DLC/addcont_17.nx64/data/status.mbe")
        self.table("DLC/addcont_17.ounce64/data/status.mbe")
        self.table("nx_patch_03_text00.nx64/text/name.mbe")
        gui = planner()
        gui.dsts_base_english_only_var.set(False)
        commands, scan = gui.build_recursive_mbe_commands("unpack-mbe-dir", "dsts-switch", self.source, self.target)
        self.assertEqual(scan["skipped_files"], 0)
        for command in commands:
            self.assertEqual(Path(command[-1]).relative_to(self.target), Path(command[-2]).relative_to(self.source))

    def test_windows_output_remains_unchanged(self):
        self.table("app_0.dx11/data/status.mbe")
        self.table("DLC/addcont_17.dx11/data/status.mbe")
        commands, _scan = planner("dsts").build_recursive_mbe_commands("unpack-mbe-dir", "dsts", self.source, self.target)
        self.assertEqual({Path(command[-1]).relative_to(self.target).as_posix() for command in commands},
                         {"Base/data", "DLC/addcont_17.dx11/data/mbe"})


class SwitchGUIStateTests(unittest.TestCase):
    def setUp(self):
        if not RUNNING_TK_CHILD:
            return
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.gui = MVGLToolsGUI(self.root)

    def select_game(self, game):
        self.gui.game_var.set(game)
        self.gui.on_game_change()

    def select_operation(self, mode):
        self.gui.mode_var.set(self.gui.get_operation_label(mode))
        self.gui.on_mode_change()

    @isolated_tk
    def test_game_switch_restores_user_paths_and_batch_choice(self):
        gui = self.gui
        gui.source_var.set("pc-input")
        gui.target_var.set("pc-output")
        gui.batch_var.set(True)
        self.select_game("dsts-switch")
        self.assertTrue(gui.batch_var.get())
        self.assertEqual(gui.source_var.get(), str(gui.SWITCH_DEFAULT_ARCHIVE_DIR))
        self.assertEqual(gui.target_var.get(), str(gui.SWITCH_DEFAULT_EXTRACTED_DIR))
        gui.batch_var.set(False)
        gui.source_var.set("one.nx64.mvgl")
        gui.target_var.set("switch-output")
        self.select_game("dsts")
        self.assertTrue(gui.batch_var.get())
        self.assertEqual((gui.source_var.get(), gui.target_var.get()), ("pc-input", "pc-output"))
        self.select_game("dsts-switch")
        self.assertFalse(gui.batch_var.get())
        self.assertEqual((gui.source_var.get(), gui.target_var.get()), ("one.nx64.mvgl", "switch-output"))

    @isolated_tk
    def test_switch_table_defaults_and_archive_choice_survive_operation_changes(self):
        gui = self.gui
        self.select_game("dsts-switch")
        self.select_operation("unpack-mbe-dir")
        self.assertEqual(gui.source_var.get(), str(gui.SWITCH_DEFAULT_EXTRACTED_DIR))
        self.assertEqual(gui.target_var.get(), str(gui.SWITCH_DEFAULT_EXTRACTED_DIR / "Tables"))
        self.select_operation("unpack-mvgl")
        self.assertTrue(gui.batch_var.get())

    @isolated_tk
    def test_game_switch_closes_old_menu_and_resets_unsupported_operation(self):
        gui = self.gui
        self.select_operation("pack-mvgl")
        destroyed = []
        gui.operation_menu_window = SimpleNamespace(destroy=lambda: destroyed.append(True))
        self.select_game("dsts-switch")
        self.assertEqual(destroyed, [True])
        self.assertIsNone(gui.operation_menu_window)
        self.assertEqual(gui.get_selected_mode(), "unpack-mvgl")
        self.assertEqual(gui.get_operation_labels(), tuple(gui.get_operation_label(mode) for mode in gui.SWITCH_OPERATIONS))
        self.assertNotIn(gui.get_operation_label("pack-mvgl"), gui.get_operation_labels())


if __name__ == "__main__":
    unittest.main()
