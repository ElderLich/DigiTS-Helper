import json
from pathlib import Path
import struct
import tempfile
import unittest

from Switch_Archives import (
    ArchiveError, _decompress_lz4_python, archive_output_relative, extract,
    inventory_archive, read_entry, safe_relative_path,
)


def make_mvgl(files, width=16):
    """Construct independent MDB1 records: (name, extension, decoded_size, bytes)."""
    count = len(files) + 1
    start = 32 + count * 16 + count * 128 + len(files) * width
    trees = bytearray(struct.pack("<IIII", 0xFFFFFFFF, 0xFFFFFFFF, 0, 1))
    names = bytearray(128)
    records = bytearray()
    payloads = bytearray()
    for index, (name, extension, size, payload) in enumerate(files):
        trees.extend(struct.pack("<IIII", index, index, 0, 0))
        names.extend(extension.encode().ljust(4, b" ") + name.encode().ljust(124, b"\0"))
        records.extend(struct.pack("<QII" if width == 16 else "<QQQ", len(payloads), size, len(payload)))
        payloads.extend(payload)
    return struct.pack("<4sIIIQQ", b"MDB1", count, count, len(files), start, start + len(payloads)) + trees + names + records + payloads


class SwitchArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, name, files, width=16):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(make_mvgl(files, width))
        return path

    def test_switch_and_pc_record_sizes_and_payloads(self):
        for width in (16, 24):
            with self.subTest(width=width):
                path = self.write(f"{width}.mvgl", [("data\\test", "mbe", 4, b"EXPA")], width)
                entry, = inventory_archive(path)
                self.assertEqual(entry.path, "data/test.mbe")
                self.assertEqual(read_entry(path, entry), b"EXPA")

    def test_lz4_overlap_and_literal_tail(self):
        encoded = b"\x15a\x01\x00\x50zzzzz"
        expected = b"aaaaaaaaaazzzzz"
        path = self.write("lz4.nx64.mvgl", [("test", "bin", len(expected), encoded)])
        entry, = inventory_archive(path)
        self.assertEqual(entry.compression, "lz4")
        self.assertEqual(read_entry(path, entry), expected)
        self.assertEqual(_decompress_lz4_python(encoded, len(expected)), expected)

    def test_lz4_rejects_invalid_or_truncated_data(self):
        for block, size in [(b"\xf0", 20), (b"\x30ab", 3), (b"\x00\0\0", 4),
                            (b"\x10a\x02\0", 5), (b"\x10a", 2)]:
            with self.subTest(block=block):
                with self.assertRaises(ArchiveError):
                    _decompress_lz4_python(block, size)

    def test_corrupt_header_and_payload_bounds(self):
        path = self.write("broken.mvgl", [("x", "bin", 1, b"x")])
        original = path.read_bytes()
        for offset, data in [(8, struct.pack("<I", 77)), (16, struct.pack("<Q", 33)),
                             (24, struct.pack("<Q", len(original) + 1)),
                             (32 + 2 * 16 + 2 * 128, struct.pack("<Q", len(original)))]:
            with self.subTest(offset=offset):
                modified = bytearray(original)
                modified[offset:offset + len(data)] = data
                path.write_bytes(modified)
                with self.assertRaises(ArchiveError):
                    inventory_archive(path)

    def test_unsafe_names_and_case_collisions(self):
        for name in ("../escape", "C:/escape", "/absolute", "a//b", "NUL", "a. ", "a:stream"):
            with self.subTest(name=name):
                with self.assertRaises(ArchiveError):
                    safe_relative_path(name)
        path = self.write("duplicate.mvgl", [("X", "bin", 1, b"x"), ("x", "bin", 1, b"y")])
        with self.assertRaisesRegex(ArchiveError, "Duplicate"):
            inventory_archive(path)
        path = self.write("traversal.mvgl", [("../bad", "bin", 1, b"x")])
        with self.assertRaisesRegex(ArchiveError, "Unsafe"):
            inventory_archive(path)

    def test_recursive_layers_manifest_resume_and_conflict(self):
        self.write("input/DLC/addcont_05.nx64.mvgl", [("data/test", "bin", 1, b"n")])
        self.write("input/DLC/addcont_05.ounce64.mvgl", [("data/test", "bin", 1, b"o")])
        source = self.root / "input"
        target = self.root / "output"
        result = extract(source, target, log=lambda _: None)
        self.assertEqual((result["files"], result["written"]), (2, 2))
        self.assertEqual((target / "DLC/addcont_05.nx64/data/test.bin").read_bytes(), b"n")
        manifest = json.loads((target / "_switch_extraction/DLC/addcont_05.nx64.mvgl.json").read_text())
        self.assertTrue(manifest["complete"])
        self.assertEqual(len(manifest["entries"][0]["sha256"]), 64)
        result = extract(source, target, log=lambda _: None)
        self.assertEqual((result["written"], result["skipped"]), (0, 2))
        conflict = target / "DLC/addcont_05.nx64/data/test.bin"
        conflict.write_bytes(b"!")
        with self.assertRaises(FileExistsError):
            extract(source, target, log=lambda _: None)
        self.assertEqual(conflict.read_bytes(), b"!")
        self.assertFalse(json.loads((target / "_switch_extraction/summary.json").read_text())["complete"])
        self.assertFalse(json.loads((target / "_switch_extraction/DLC/addcont_05.nx64.mvgl.json").read_text())["complete"])
        extract(source, target, log=lambda _: None, overwrite=True)
        self.assertEqual(conflict.read_bytes(), b"n")
        self.assertFalse(list(target.rglob(".switch-extract-*.tmp")))

    def test_cpk_layer_name_does_not_collide(self):
        self.assertEqual(archive_output_relative(Path("input/DLC/x.nx64.cpk"), Path("input")),
                         Path("DLC/x.nx64.cpk"))
        self.assertEqual(archive_output_relative(Path("input/DLC/x.nx64.mvgl"), Path("input")),
                         Path("DLC/x.nx64"))

    def test_reject_target_inside_source(self):
        source = self.root / "input"
        source.mkdir()
        with self.assertRaisesRegex(ArchiveError, "outside"):
            extract(source, source / "output", log=lambda _: None)


if __name__ == "__main__":
    unittest.main()
