import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

from CPK_Archives import (CPKError, copy_cpk_entry, inventory_cpk,
                          read_cpk_entry)


def utf_table(columns, values, masked=False):
    strings = bytearray(b"fixture\0")

    def string(value):
        offset = len(strings)
        strings.extend(value.encode("utf-8") + b"\0")
        return offset

    definitions = bytearray()
    row = bytearray()
    for (name, kind), value in zip(columns, values):
        definitions.extend(struct.pack(">BI", 0x50 | kind, string(name)))
        if kind == 10:
            row.extend(struct.pack(">I", string(value)))
        elif kind == 6:
            row.extend(struct.pack(">Q", value))
        else:
            row.extend(struct.pack(">I", value))
    rows_at = 32 + len(definitions)
    strings_at = rows_at + len(row)
    end = strings_at + len(strings)
    data = bytearray(struct.pack(">4s5I2HI", b"@UTF", end - 8,
        rows_at - 8, strings_at - 8, end - 8, 0, len(columns), len(row), 1))
    data.extend(definitions + row + strings)
    if masked:
        mask = 0x655F
        for i in range(len(data)):
            data[i] ^= mask & 255
            mask = (mask * 0x4115) & 0xFFFFFFFF
    return bytes(data)


def fixture(path, name="sample.awb", directory="audio", masked=False,
            offset=0x700, size=None, extract_size=None):
    payload = b"AFS2" + bytes(range(256)) * 3
    size = len(payload) if size is None else size
    extract_size = size if extract_size is None else extract_size
    header = utf_table([("TocOffset", 6), ("ContentOffset", 6), ("Files", 4)],
                       [0x100, 0x800, 1], masked)
    toc = utf_table([("DirName", 10), ("FileName", 10), ("FileSize", 4),
                     ("ExtractSize", 4), ("FileOffset", 6)],
                    [directory, name, size, extract_size, offset], masked)
    data = bytearray(0x800)
    data[:16 + len(header)] = struct.pack("<4sIQ", b"CPK ", 255, len(header)) + header
    data[0x100:0x110 + len(toc)] = struct.pack("<4sIQ", b"TOC ", 255, len(toc)) + toc
    path.write_bytes(data + payload)
    return payload


class CPKArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "test.cpk"

    def test_plain_and_masked_tables_read_identical_payload(self):
        for masked in (False, True):
            with self.subTest(masked=masked):
                payload = fixture(self.source, masked=masked)
                entries = inventory_cpk(self.source)
                self.assertEqual(len(entries), 1)
                entry = entries[0]
                self.assertEqual(entry.path, "audio/sample.awb")
                self.assertEqual(entry.offset, 0x800)
                self.assertEqual(read_cpk_entry(self.source, entry), payload)

    def test_stream_copy_preserves_bytes_and_existing_destination(self):
        payload = fixture(self.source)
        entry = inventory_cpk(self.source)[0]
        target = self.root / "output.awb"
        self.assertEqual(copy_cpk_entry(self.source, entry, target),
                         hashlib.sha256(payload).hexdigest())
        self.assertEqual(target.read_bytes(), payload)
        with self.assertRaises(FileExistsError):
            copy_cpk_entry(self.source, entry, target)
        self.assertEqual(target.read_bytes(), payload)

    def test_traversal_and_windows_aliases_rejected(self):
        for name in ("../escape", "/absolute", "C:drive", "name:stream", "NUL",
                     "aux.bin", "trailing.", "trailing ", "folder//file"):
            with self.subTest(name=name):
                fixture(self.source, name=name, directory="")
                with self.assertRaises(CPKError):
                    inventory_cpk(self.source)

    def test_payload_bounds_and_truncation_rejected(self):
        for values in ({"offset": 0}, {"size": 999999}):
            fixture(self.source, **values)
            with self.assertRaises(CPKError):
                inventory_cpk(self.source)
        self.source.write_bytes(b"CPK ")
        with self.assertRaises(CPKError):
            inventory_cpk(self.source)

    def test_unsupported_compression_cannot_be_silently_copied(self):
        fixture(self.source, extract_size=9000)
        entry = inventory_cpk(self.source)[0]
        self.assertEqual(entry.compression, "unsupported")
        with self.assertRaises(CPKError):
            read_cpk_entry(self.source, entry)
        with self.assertRaises(CPKError):
            copy_cpk_entry(self.source, entry, self.root / "output")
        self.assertFalse((self.root / "output").exists())


if __name__ == "__main__":
    unittest.main()
