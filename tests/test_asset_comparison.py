"""Cross-platform comparisons must not confuse packaging with extra content."""
from pathlib import Path
import sys
import tempfile
import unittest
import hashlib
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Compare_Assets import Asset, asset_digest, compare, inventory, parse_layer, write_report


class AssetComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.windows = self.root / "windows"
        self.switch = self.root / "switch"

    def add(self, root, relative, contents=b"model"):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)

    def test_numbered_patches_overlay_base_but_not_other_languages(self):
        self.add(self.switch, "app_0.nx64/chr001.geom", b"old")
        self.add(self.switch, "nx_patch_02.nx64/chr001.geom", b"two")
        self.add(self.switch, "nx_patch_10.nx64/chr001.geom", b"newest")
        self.add(self.switch, "app_text00.nx64/text/name.mbe", b"jp")
        self.add(self.switch, "app_text01.nx64/text/name.mbe", b"en")
        self.add(self.switch, "nx_patch_03_text01.nx64/text/name.mbe", b"patch")
        data = inventory(self.switch, "nx64").effective()
        self.assertEqual(data["assets/chr001.geom"][0].size, 6)
        self.assertEqual(data["text00/text/name.mbe"][0].size, 2)
        self.assertEqual(data["text01/text/name.mbe"][0].size, 5)

    def test_base_integrated_dlc_and_lod_do_not_imply_new_character(self):
        self.add(self.windows, "addcont_01.dx11/chr123.geom")
        self.add(self.switch, "nx_patch_01.nx64/chr123.geom")
        self.add(self.switch, "nx_patch_01.nx64/chr123_lod_3.geom")
        result = compare(inventory(self.windows), inventory(self.switch))
        self.assertEqual(result["summary"]["models"]["common"], 1)
        self.assertEqual(result["summary"]["character_model_ids"]["only_switch"], [])
        self.assertEqual(result["summary"]["models"]["only_switch"], ["assets/chr123_lod_3.geom"])

    def test_ounce64_stays_out_of_nx64_comparison(self):
        self.add(self.switch, "DLC/addcont_17.nx64/chr123.geom")
        self.add(self.switch, "DLC/addcont_17.ounce64/chr999.geom")
        result = inventory(self.switch, "nx64")
        self.assertEqual(set(result.effective()), {"assets/chr123.geom"})
        self.assertEqual(result.excluded_platforms, {"ounce64": 1})

    def test_equal_size_is_not_equal_content_and_dlc_variants_remain(self):
        self.add(self.windows, "app_0.dx11/chr123.geom", b"same")
        self.add(self.windows, "addcont_01.dx11/chr123.geom", b"dlc!")
        self.add(self.switch, "app_0.nx64/chr123.geom", b"diff")
        self.add(self.switch, "DLC/addcont_17.nx64/chr123.geom", b"dlc!")
        a, b = inventory(self.windows), inventory(self.switch)
        self.assertEqual(len(a.effective()["assets/chr123.geom"]), 2)
        result = compare(a, b, [".geom"])
        self.assertEqual(result["common"][0]["status"], "matching_content_variant")
        (self.switch / "DLC/addcont_17.nx64/chr123.geom").write_bytes(b"nope")
        result = compare(a, inventory(self.switch), [".geom"])
        self.assertEqual(result["common"][0]["status"], "different_content")

    def test_cpk_and_voice_namespace_and_report(self):
        self.add(self.windows, "app_0.dx11.cpk/sound/music.acb")
        self.add(self.switch, "app_0.nx64.cpk/sound/music.acb")
        self.add(self.windows, "app_voice00.dx11/1.lips")
        self.add(self.switch, "app_voice01.nx64/1.lips")
        result = compare(inventory(self.windows), inventory(self.switch))
        self.assertEqual(result["summary"]["common_paths"], 1)
        self.assertIn("voice01/1.lips", result["only_switch"])
        write_report(result, self.root / "report")
        self.assertTrue((self.root / "report/comparison.md").is_file())
        self.assertEqual(parse_layer("nx_patch_03_text01.nx64.mvgl").priority, 3)

    def test_empty_or_unknown_inputs_fail(self):
        self.windows.mkdir()
        with self.assertRaisesRegex(ValueError, "No recognized"):
            inventory(self.windows)

    def test_archive_inventory_uses_backend_paths_and_keeps_cpk_variant(self):
        self.add(self.switch, "app_0.nx64.mvgl", b"archive")
        self.add(self.switch, "app_0.nx64.cpk", b"archive")
        self.add(self.switch, "DLC/addcont_05.ounce64.mvgl", b"archive")
        with patch("Switch_Archives.inventory_archive",
                   return_value=[SimpleNamespace(path="BGM/Track.acb", size=4)]):
            result = inventory(self.switch, "nx64")
        self.assertEqual(result.source_kind, "archives")
        self.assertEqual(len(result.effective()["assets/bgm/track.acb"]), 2)
        self.assertEqual(result.platform_filter, "nx64")
        self.assertEqual(result.excluded_platforms, {"ounce64": 1})

    def test_generated_tables_do_not_change_asset_inventory(self):
        self.add(self.switch, "app_0.nx64/data/actual.mbe")
        self.add(self.switch, "Tables/nx64/DLC/addcont_17.nx64/data/actual.mbe/000.csv")
        self.add(self.switch, "_switch_extraction/app_0.nx64/fake.geom")
        self.assertEqual(set(inventory(self.switch).effective()), {"assets/data/actual.mbe"})

    def test_uncompressed_archive_hash_reads_only_bounded_payload(self):
        path = self.root / "app_0.nx64.cpk"
        path.write_bytes(b"header" + b"payload" + b"trailer")
        entry = SimpleNamespace(offset=6, size=7, compression="none")
        asset = Asset("assets/movie.usm", "movie.usm", 7,
                      parse_layer(path.name), path, entry)
        with patch("Switch_Archives.read_entry", side_effect=AssertionError("must stream")):
            self.assertEqual(asset_digest(asset), hashlib.sha256(b"payload").hexdigest())


if __name__ == "__main__":
    unittest.main()
