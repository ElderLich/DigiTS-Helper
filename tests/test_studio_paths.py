from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import CSV_Exporter
import studio_paths


class StudioPathsTests(unittest.TestCase):
    def test_checkout_and_portable_executables_find_their_external_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            exe = root / "dist" / "Studio.exe"
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(exe)):
                self.assertEqual(studio_paths.studio_root(), exe.parent)
                (root / "app").mkdir()
                (root / "app/digimon_editor.py").touch()
                self.assertEqual(studio_paths.studio_root(), root)
                (root / "Base").mkdir()
                self.assertEqual(studio_paths.table_root(), root)
                (root / "data/Base").mkdir(parents=True)
                self.assertEqual(studio_paths.table_root(), root / "data")
                filename = "MVGLToolsCLI.exe"
                old = root / "_internal" / filename
                old.parent.mkdir()
                old.touch()
                self.assertEqual(studio_paths.dependency("mvgl", filename), old)
                new = root / "dependencies/mvgl" / filename
                new.parent.mkdir(parents=True)
                new.touch()
                self.assertEqual(studio_paths.dependency("mvgl", filename), new)

    def test_exporting_into_the_checkout_preserves_all_existing_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "data/Base/data"
            text = data.with_name("text")
            for folder in (data, text, root / "data/DLC"):
                folder.mkdir(parents=True)
                (folder / "sample.csv").write_text("preserved")
            exporter = CSV_Exporter.CSVExporter(data, text)
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertFalse(exporter.export_all_csv_files(root))
            self.assertEqual(len(list(root.rglob("sample.csv"))), 3)
            with redirect_stdout(StringIO()):
                self.assertTrue(exporter.export_all_csv_files(root / "export"))
            for kind in ("data", "text", "DLC"):
                self.assertEqual((root / "export" / kind / "sample.csv").read_text(), "preserved")

    def test_repack_keeps_previous_outputs_when_a_tool_reports_success_without_an_mbe(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "input"
            dest = root / "out"
            dest.mkdir()
            for name in ("one.mbe", "two.mbe"):
                (source / name).mkdir(parents=True)
                (source / name / "000_table.csv").write_text("int32 0\n1\n")
                (dest / name).write_bytes(b"old")
            cli = root / "MVGLToolsCLI.exe"
            cli.touch()

            def pack(command, **kwargs):
                self.assertEqual(command[:3], [str(cli), "--game=dsts", "--mode=pack-mbe"])
                self.assertEqual(kwargs["cwd"], cli.parent)
                if Path(command[-1]).name == "one.mbe":
                    Path(command[-1]).write_bytes(b"EXPA\x01\x00\x00\x00")
                return CSV_Exporter.subprocess.CompletedProcess(command, 0, "", "")

            with patch.object(CSV_Exporter, "dependency", return_value=cli), \
                    patch.object(CSV_Exporter.subprocess, "run", side_effect=pack), redirect_stdout(StringIO()):
                self.assertFalse(CSV_Exporter.repack_mbe_files(source, dest))
            self.assertEqual({p.name: p.read_bytes() for p in dest.iterdir()},
                             {"one.mbe": b"old", "two.mbe": b"old"})


if __name__ == "__main__":
    unittest.main()
