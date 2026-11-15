import os
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from profile_portrait import PORTRAIT_FILL, PortraitPanel, crop_artwork, tutorial_portrait


class PortraitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_original_and_shadow_drive_alpha_independently_of_channel_split(self):
        image = Image.new("RGBA", (512, 512))
        image.paste((200, 240, 250, 255), (20, 20, 50, 50))
        result = tutorial_portrait(image)
        self.assertEqual(result.getchannel("A").getbbox(), (20, 20, 58, 53))
        self.assertEqual(result.getpixel((26, 54))[3], 0)  # displaced copy alone
        self.assertEqual(result.getpixel((56, 40))[3], 255)  # solid black shadow
        self.assertEqual(result.getpixel((100, 100)), (*PORTRAIT_FILL, 0))
        self.assertNotEqual(result.getpixel((53, 40))[:3], result.getpixel((56, 40))[:3])

    def test_rectangular_artwork_keeps_its_proportions_in_square_crop(self):
        image = Image.new("RGBA", (80, 40), (200, 60, 100, 255))
        full = crop_artwork(image, (0, 0, 1), 80)
        self.assertEqual(full.getchannel("A").getbbox(), (0, 20, 80, 60))
        self.assertEqual(crop_artwork(image, (0.25, 0.25, 0.5), 40).getextrema()[3], (255, 255))
        with self.assertRaisesRegex(ValueError, "empty"):
            tutorial_portrait(Image.new("RGBA", (512, 512)))

    def test_flat_artwork_exports_from_panel_without_external_tools(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.png"
            result = Path(folder) / "styled.png"
            image = Image.new("RGBA", (512, 512))
            image.paste("red", (22, 32, 222, 412))
            image.save(source)
            panel = PortraitPanel(initial_model=source)
            self.addCleanup(panel.shutdown)
            panel.select_tool = lambda *args: self.fail("PNG flow requested an external tool")
            native_saves = []
            panel.saved.connect(native_saves.append)
            panel.start_render(False)
            self.assertTrue(panel.png_save.isEnabled())
            self.assertFalse(panel.portrait_preview.pixmap().isNull())
            panel.start_render(True, result)
            self.assertEqual(native_saves, [])
            with Image.open(result) as exported:
                self.assertEqual(exported.tobytes(), tutorial_portrait(image).tobytes())
            self.app.processEvents()
