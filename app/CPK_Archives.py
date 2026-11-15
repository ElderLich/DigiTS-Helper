"""Read the named TOC-based CRI CPK archives shipped with Time Stranger.

All offsets and lengths are checked before reading; no game executables run.
UTF layout/TOC base reference: esperknight/CriPakTools, CPK.cs (ReadTOC).
The game's observed CPK payloads are uncompressed. Other compression and
ITOC-only archives are rejected explicitly rather than silently mis-extracted.
"""

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import struct


class CPKError(ValueError):
    """Malformed or unsupported CPK input."""


@dataclass(frozen=True)
class CPKEntry:
    path: str
    offset: int
    size: int
    stored_size: int
    compression: str = "none"


def _exact(stream, count):
    data = stream.read(count)
    if len(data) != count:
        raise CPKError("Truncated CPK data")
    return data


def _parse_utf(data):
    if data[:4] != b"@UTF":
        # CRI's optional table mask, unrelated to payload compression.
        mask = 0x655F
        decoded = bytearray(data)
        for i in range(len(decoded)):
            decoded[i] ^= mask & 0xFF
            mask = (mask * 0x4115) & 0xFFFFFFFF
        data = bytes(decoded)
    if len(data) < 32 or data[:4] != b"@UTF":
        raise CPKError("Invalid CPK UTF table")
    length, rows_at, strings_at, blobs_at, _, column_count, row_length, row_count = (
        struct.unpack_from(">5I2HI", data, 4)
    )
    end = length + 8
    rows_at += 8
    strings_at += 8
    blobs_at += 8
    if not (32 <= rows_at <= strings_at <= blobs_at <= end <= len(data)):
        raise CPKError("Invalid UTF section bounds")
    if row_count > 1_000_000 or column_count > 4096:
        raise CPKError("Excessive UTF row or column count")
    if rows_at + row_length * row_count > strings_at:
        raise CPKError("UTF rows exceed table bounds")

    def string_at(offset):
        start = strings_at + offset
        if not strings_at <= start < blobs_at:
            raise CPKError("UTF string offset outside string section")
        stop = data.find(b"\0", start, blobs_at)
        if stop < 0:
            raise CPKError("Unterminated UTF string")
        try:
            return data[start:stop].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CPKError("Unsupported non-UTF-8 CPK filename") from exc

    formats = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i",
               6: "Q", 7: "q", 8: "f", 9: "d", 10: "I", 11: "II"}

    def value_at(kind, cursor, limit):
        if kind not in formats:
            raise CPKError(f"Unsupported UTF column type {kind}")
        fmt = ">" + formats[kind]
        width = struct.calcsize(fmt)
        if cursor + width > limit:
            raise CPKError("Truncated UTF value")
        values = struct.unpack_from(fmt, data, cursor)
        value = values[0]
        if kind == 10:
            value = string_at(value)
        elif kind == 11:
            start, size = values
            if blobs_at + start + size > end:
                raise CPKError("UTF blob outside table")
            value = data[blobs_at + start:blobs_at + start + size]
        return value, cursor + width

    columns = []
    cursor = 32
    for _ in range(column_count):
        if cursor + 5 > rows_at:
            raise CPKError("Truncated UTF column definition")
        flags, name_at = struct.unpack_from(">BI", data, cursor)
        cursor += 5
        storage, kind = flags >> 4, flags & 15
        if storage not in (1, 3, 5):
            raise CPKError(f"Unsupported UTF storage mode {storage}")
        constant = None
        if storage == 3:
            constant, cursor = value_at(kind, cursor, rows_at)
        name = string_at(name_at)
        if any(column[0] == name for column in columns):
            raise CPKError(f"Duplicate UTF column {name!r}")
        columns.append((name, kind, storage, constant))
    rows = []
    for index in range(row_count):
        cursor = rows_at + row_length * index
        limit = cursor + row_length
        row = {}
        for name, kind, storage, constant in columns:
            value = constant
            if storage == 5:
                value, cursor = value_at(kind, cursor, limit)
            row[name] = value
        rows.append(row)
    return rows


def _read_table(stream, offset, magic, archive_size):
    if offset < 0 or offset + 16 > archive_size:
        raise CPKError("CPK table offset outside archive")
    stream.seek(offset)
    found, _, size = struct.unpack("<4sIQ", _exact(stream, 16))
    if found != magic:
        raise CPKError(f"Expected {magic!r} at {offset}, found {found!r}")
    if size > archive_size - offset - 16 or size > 256 * 1024 * 1024:
        raise CPKError("Invalid or excessive CPK table size")
    return _parse_utf(_exact(stream, size))


def _integer(row, name):
    value = row.get(name)
    if not isinstance(value, int) or value < 0:
        raise CPKError(f"Missing/invalid CPK {name}")
    return value


def _safe_name(name):
    name = name.replace("\\", "/")
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or any(part in ("", ".", "..")
            for part in name.split("/")) or ":" in name or "\0" in name):
        raise CPKError(f"Unsafe CPK entry path: {name!r}")
    # Windows trims these suffixes and treats device names specially.
    devices = {"con", "prn", "aux", "nul"} | {
        f"{prefix}{i}" for prefix in ("com", "lpt") for i in range(1, 10)
    }
    if any(part.endswith((".", " ")) or part.split(".")[0].casefold() in devices
           or any(ch in part for ch in '<>"|?*') or any(ord(ch) < 32 for ch in part)
           for part in path.parts):
        raise CPKError(f"Unsafe Windows CPK entry path: {name!r}")
    return path.as_posix()


def inventory_cpk(path):
    """Return validated named entries without reading any payloads."""
    path = Path(path)
    archive_size = path.stat().st_size
    with path.open("rb") as stream:
        headers = _read_table(stream, 0, b"CPK ", archive_size)
        if len(headers) != 1:
            raise CPKError("CPK must have exactly one header row")
        header = headers[0]
        toc = _integer(header, "TocOffset")
        content = _integer(header, "ContentOffset")
        if content > archive_size:
            raise CPKError("CPK content offset outside archive")
        rows = _read_table(stream, toc, b"TOC ", archive_size)
        if header.get("Files") != len(rows):
            raise CPKError("CPK file count does not match named TOC")
        base = min(toc, content)
        entries, names = [], set()
        for row in rows:
            filename, directory = row.get("FileName"), row.get("DirName") or ""
            if not isinstance(filename, str) or not isinstance(directory, str):
                raise CPKError("CPK entry missing a filename")
            name = _safe_name(f"{directory}/{filename}" if directory else filename)
            if name.casefold() in names:
                raise CPKError(f"Duplicate CPK output path {name!r}")
            names.add(name.casefold())
            size, stored = _integer(row, "ExtractSize"), _integer(row, "FileSize")
            offset = base + _integer(row, "FileOffset")
            if offset < content or offset + stored > archive_size:
                raise CPKError(f"CPK payload outside content bounds: {name}")
            entries.append(CPKEntry(name, offset, size, stored,
                                    "none" if size == stored else "unsupported"))
    return entries


def read_cpk_entry(path, entry):
    """Read one uncompressed entry; use copy_cpk_entry for large media."""
    if entry.compression != "none":
        raise CPKError(f"Compressed CPK payload is unsupported: {entry.path}")
    with Path(path).open("rb") as stream:
        stream.seek(entry.offset)
        return _exact(stream, entry.stored_size)


def copy_cpk_entry(path, entry, destination):
    """Stream into a NEW destination file and return its SHA-256 digest.

    The caller owns path containment, directory creation and atomic promotion.
    Opening exclusively ensures this function never overwrites another file.
    """
    if entry.compression != "none":
        raise CPKError(f"Compressed CPK payload is unsupported: {entry.path}")
    digest = hashlib.sha256()
    with Path(path).open("rb") as source, Path(destination).open("xb") as target:
        source.seek(entry.offset)
        remaining = entry.stored_size
        while remaining:
            block = _exact(source, min(4 * 1024 * 1024, remaining))
            target.write(block)
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()
