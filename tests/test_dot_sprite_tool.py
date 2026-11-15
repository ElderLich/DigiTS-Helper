import io
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PIL import Image
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from dot_sprite_tool import DotSpriteTab, FrameGrid, encode_dot, output_path, save_texture


class DotSpriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_exact_quadrants_and_native_texture_layout(self):
        sheet = Image.new("RGBA", (48, 64))
        for index in range(12):
            x, y = index % 3 * 16, index // 3 * 16
            for pt in ((0, 0), (15, 15), (1, 11)):
                sheet.putpixel((x + pt[0], y + pt[1]), (index * 20, 120, 255, 255))
        grid = FrameGrid(sheet)
        self.assertEqual(grid.defaults(), [0, 1, 11, 10])
        native = encode_dot(grid, grid.defaults())
        self.assertEqual(len(native), 2176)
        self.assertEqual(native[:4], b"DDS ")
        self.assertEqual(struct.unpack_from("<4I", native, 92), (0x7C00, 0x3E0, 0x1F, 0x8000))
        self.assertEqual(struct.unpack_from("<H", native, 130)[0], 0x03e0)
        with Image.open(io.BytesIO(native)) as decoded:
            for quadrant, index in enumerate(grid.defaults()):
                x, y = quadrant % 2 * 16, quadrant // 2 * 16
                expected = grid.tile(index)
                actual = decoded.crop((x, y, x + 16, y + 16))
                self.assertEqual(actual.getchannel("A").tobytes(), expected.getchannel("A").tobytes())
                for pos in ((0, 0), (15, 15), (1, 11)):
                    self.assertLessEqual(abs(actual.getpixel(pos)[0] - index * 20), 5)
            grid2 = FrameGrid(decoded.copy())
            self.assertEqual(encode_dot(grid2, grid2.defaults()), native)

    def test_offsets_gutters_and_partial_edges(self):
        im = Image.new("RGBA", (39, 23))
        im.putpixel((21, 3), (255, 0, 0, 255))
        grid = FrameGrid(im, 2, 3, 3, 0)
        self.assertEqual(len(grid), 2)
        self.assertEqual(grid.tile(1).getpixel((0, 0)), (255, 0, 0, 255))
        self.assertEqual(len(FrameGrid(im, 30, 3)), 0)
        with self.assertRaises(ValueError):
            grid.tile(2)

    def test_assign_preview_export_reopen_and_cancel(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            source = directory / "Color.png"
            Image.new("RGBA", (48, 64), (255, 32, 0, 255)).save(source)
            tab = DotSpriteTab()
            self.addCleanup(tab.deleteLater)
            self.assertFalse(tab.export.isEnabled())
            tab.open_sheet(source)
            tab.frames.setCurrentIndex(tab.model.index(7))
            tab.slot_buttons[2].click()
            self.assertEqual(tab.slots, [0, 1, 7, 10])
            tab.zoom.setCurrentIndex(0)
            self.assertEqual(tab.atlas_preview.pixmap().width(), 32)
            self.assertEqual(tab.pose_preview.pixmap().width(), 16)
            with patch.object(QFileDialog, "getOpenFileName", return_value=("", "")):
                tab.choose_source()
            self.assertEqual(tab.slots, [0, 1, 7, 10])
            (directory / "ModConfig.json").write_text("{}")
            tab.folder.setText(str(directory))
            tab.digimon_id.setValue(37)
            self.assertTrue(tab.export.isEnabled())
            tab.export.click()
            dest = directory / "dsts-loader/patch/images/dot037.img"
            data = dest.read_bytes()
            self.assertEqual(data, tab.native_data)
            tab.open_sheet(dest)
            self.assertEqual(tab.native_data, data)
            self.assertEqual(tab.slots, [0, 1, 2, 3])
            with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as ask, \
                    patch("dot_sprite_tool.save_texture") as save:
                tab.export.click()
            ask.assert_called_once()
            save.assert_not_called()
            tab.grid_fields[0].setValue(31)
            self.assertFalse(tab.export.isEnabled())
            self.assertIsNone(tab.native_data)

    def test_existing_dds_and_file_races(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "dsts-loader/patch/images"
            self.assertEqual(output_path(root, 761), folder / "dot761.img")
            self.assertEqual(output_path(root / "dsts-loader", 761), folder / "dot761.img")
            self.assertEqual(output_path(folder.parent, 761), folder / "dot761.img")
            folder.mkdir(parents=True)
            dest = folder / "dot761.dds"
            dest.write_bytes(b"existing")
            self.assertEqual(output_path(folder, 761), dest)
            with self.assertRaises(FileExistsError):
                save_texture(dest, b"new", None)
            with self.assertRaises(OSError):
                save_texture(dest, b"new", b"earlier version")
            self.assertEqual(dest.read_bytes(), b"existing")
            (folder / "dot761.img").write_bytes(b"other")
            with self.assertRaises(ValueError):
                output_path(folder, 761)
