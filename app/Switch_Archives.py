"""Extract Time Stranger Switch MDB1 archives without the Windows-only backend.

Switch MDB1 uses 16-byte data records (QII), compared with the PC QQQ records.
Both use raw LZ4 blocks. Layout verified against the supplied nx64/ounce64
archives and MVGLTools' DSTSNX declaration:
https://github.com/SydMontague/MVGLTools/blob/master/MVGLTools/include/MDB1.h

This module extracts already decrypted game files; it does not open NSP/NCA.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import struct
import tempfile
from typing import BinaryIO, Callable


class ArchiveError(ValueError):
    """An archive is malformed or cannot safely be extracted."""


@dataclass(frozen=True)
class ArchiveEntry:
    path: str
    size: int
    offset: int
    stored_size: int
    compression: str = "none"


def safe_relative_path(name: str) -> str:
    """Accept only portable relative paths, including on Windows hosts."""
    name = name.replace("\\", "/")
    parts = name.split("/")
    if not name or name.startswith("/") or any(
        part in ("", ".", "..") or part.endswith((" ", "."))
        or any(ord(c) < 32 or c in ':<>"|?*' for c in part)
        or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)
        for part in parts
    ):
        raise ArchiveError(f"Unsafe archive path: {name!r}")
    return str(PurePosixPath(*parts))


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise ArchiveError(f"Truncated archive: expected {size} bytes, got {len(data)}")
    return data


def inventory_mvgl(path: str | Path) -> list[ArchiveEntry]:
    """Read Switch or PC MDB1 entries without reading their payloads."""
    path = Path(path)
    archive_size = path.stat().st_size
    with path.open("rb") as stream:
        magic, trees, names, records, data_start, total_size = struct.unpack(
            "<4sIIIQQ", _read_exact(stream, 32)
        )
        if magic != b"MDB1":
            raise ArchiveError(f"Not an MDB1 archive: {path}")
        if trees != names or trees < 1 or records > trees or total_size != archive_size:
            raise ArchiveError(f"Invalid MDB1 counts or total size: {path}")
        table_start = 32 + trees * 16 + names * 128
        # The known game archives have a contiguous, unpadded metadata area.
        candidates = [width for width in (16, 24) if table_start + records * width == data_start]
        if records == 0 and table_start == data_start:
            candidates = [16]
        if len(candidates) != 1 or data_start > archive_size:
            raise ArchiveError(f"Unsupported MDB1 record layout: {path}")
        if data_start > 256 * 1024 * 1024:
            raise ArchiveError(f"MDB1 metadata exceeds the supported 256 MiB bound: {path}")
        width = candidates[0]
        metadata = _read_exact(stream, data_start - 32)
    data_record_format = "<QII" if width == 16 else "<QQQ"
    name_start = trees * 16
    record_start = name_start + names * 128
    entries = []
    seen = set()
    for i in range(trees):
        data_id = struct.unpack_from("<I", metadata, i * 16 + 4)[0]
        if data_id == 0xFFFFFFFF:
            continue
        if data_id >= records:
            raise ArchiveError(f"MDB1 entry {i} references missing data record {data_id}")
        raw_name = metadata[name_start + i * 128:name_start + (i + 1) * 128]
        try:
            extension = raw_name[:4].split(b"\0", 1)[0].decode("utf-8").strip()
            name = raw_name[4:].split(b"\0", 1)[0].decode("utf-8").rstrip(" ")
        except UnicodeDecodeError as exc:
            raise ArchiveError(f"Invalid UTF-8 MDB1 filename at entry {i}") from exc
        relative = safe_relative_path(f"{name}.{extension}")
        if relative.casefold() in seen:
            raise ArchiveError(f"Duplicate MDB1 output path: {relative}")
        seen.add(relative.casefold())
        offset, size, stored_size = struct.unpack_from(data_record_format, metadata, record_start + data_id * width)
        offset += data_start
        if offset < data_start or offset + stored_size > archive_size:
            raise ArchiveError(f"MDB1 payload outside archive: {relative}")
        entries.append(ArchiveEntry(relative, size, offset, stored_size,
                                    "none" if size == stored_size else "lz4"))
    return entries


def decompress_lz4(data: bytes, expected_size: int) -> bytes:
    """Decode a raw block, using python-lz4 when installed or a checked fallback."""
    try:
        from lz4.block import decompress
    except ImportError:
        return _decompress_lz4_python(data, expected_size)
    try:
        result = decompress(data, uncompressed_size=expected_size)
    except Exception as exc:
        raise ArchiveError(f"Invalid LZ4 block: {exc}") from exc
    if len(result) != expected_size:
        raise ArchiveError("LZ4 decoded size differs from the archive record")
    return result


def _decompress_lz4_python(data: bytes, expected_size: int) -> bytes:
    output = bytearray()
    cursor = 0

    def length(base: int) -> int:
        nonlocal cursor
        if base == 15:
            while True:
                if cursor >= len(data):
                    raise ArchiveError("Truncated LZ4 length")
                extra = data[cursor]
                cursor += 1
                base += extra
                if extra != 255:
                    break
        return base

    while cursor < len(data):
        token = data[cursor]
        cursor += 1
        literal_size = length(token >> 4)
        if cursor + literal_size > len(data) or len(output) + literal_size > expected_size:
            raise ArchiveError("LZ4 literals exceed the block bounds")
        output.extend(data[cursor:cursor + literal_size])
        cursor += literal_size
        if cursor == len(data):
            break
        if cursor + 2 > len(data):
            raise ArchiveError("Truncated LZ4 match offset")
        distance = data[cursor] | (data[cursor + 1] << 8)
        cursor += 2
        count = length(token & 15) + 4
        if not distance or distance > len(output) or len(output) + count > expected_size:
            raise ArchiveError("Invalid LZ4 back-reference")
        # Repeat a whole back-reference period instead of copying byte by byte.
        pattern = bytes(output[-distance:])
        output.extend((pattern * ((count + distance - 1) // distance))[:count])
    if len(output) != expected_size:
        raise ArchiveError(f"LZ4 decoded {len(output)} bytes, expected {expected_size}")
    return bytes(output)


def inventory_archive(path: str | Path) -> list[ArchiveEntry]:
    path = Path(path)
    with path.open("rb") as stream:
        magic = stream.read(4)
    if magic == b"MDB1":
        return inventory_mvgl(path)
    if magic == b"CPK ":
        from CPK_Archives import inventory_cpk
        return inventory_cpk(path)
    raise ArchiveError(f"Unsupported archive magic {magic!r}: {path}")


def _read_entry(stream: BinaryIO, entry: ArchiveEntry) -> bytes:
    stream.seek(entry.offset)
    data = _read_exact(stream, entry.stored_size)
    if entry.compression == "lz4":
        data = decompress_lz4(data, entry.size)
    elif entry.compression != "none":
        raise ArchiveError(f"Unsupported compression {entry.compression!r}: {entry.path}")
    if len(data) != entry.size:
        raise ArchiveError(f"Incorrect decoded size for {entry.path}: {len(data)} != {entry.size}")
    return data


def read_entry(path: str | Path, entry: ArchiveEntry) -> bytes:
    with Path(path).open("rb") as stream:
        return _read_entry(stream, entry)


def discover_archives(source: str | Path) -> list[Path]:
    source = Path(source).resolve(strict=True)
    if source.is_file():
        if source.suffix.lower() not in (".mvgl", ".cpk"):
            raise ArchiveError("Select an MVGL/CPK archive or its containing folder")
        return [source]
    return sorted((p for p in source.rglob("*") if p.is_file()
                   and p.suffix.lower() in (".mvgl", ".cpk")), key=lambda p: p.as_posix().casefold())


def archive_output_relative(archive: Path, source: Path) -> Path:
    relative = archive.relative_to(source)
    return relative.parent / (relative.name if archive.suffix.lower() == ".cpk" else relative.stem)


def _output_path(root: Path, relative: str) -> Path:
    output = root.joinpath(*safe_relative_path(relative).split("/"))
    # Resolving existing parents rejects symlinks/junctions escaping the target.
    if not output.resolve().is_relative_to(root.resolve()):
        raise ArchiveError(f"Output path escapes extraction root: {relative}")
    return output


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".switch-manifest-", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _hash_file(path: Path) -> str:
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
        return digest.hexdigest()


def extract(source: str | Path, target: str | Path, log: Callable[[str], None] = print,
            *, overwrite: bool = False) -> dict:
    """Extract one archive directly to target, or a tree into separate layers.

    Existing identical files are verified and skipped. Different existing files
    require explicit overwrite=True. Each complete layer has a JSON manifest
    containing original offsets, sizes and SHA-256 hashes of the output files.
    """
    source = Path(source).resolve(strict=True)
    target = Path(target).resolve()
    if target == source or (source.is_dir() and target.is_relative_to(source)):
        raise ArchiveError("Extraction target must be outside the source tree")
    manifest_root = target / "_switch_extraction"
    if not manifest_root.resolve().is_relative_to(target):
        raise ArchiveError("Manifest directory escapes extraction target")
    archives = discover_archives(source)
    if not archives:
        raise ArchiveError(f"No .mvgl or .cpk archives found in {source}")
    target.mkdir(parents=True, exist_ok=True)
    summary = {"source": str(source), "target": str(target), "archives": [],
               "files": 0, "bytes": 0, "written": 0, "skipped": 0, "complete": False}
    summary_path = _output_path(manifest_root, "summary.json")
    _atomic_json(summary_path, summary)
    for number, archive in enumerate(archives, 1):
        relative = archive_output_relative(archive, source) if source.is_dir() else Path(".")
        output_root = target / relative
        if not output_root.resolve().is_relative_to(target):
            raise ArchiveError(f"Archive layer escapes extraction target: {relative}")
        entries = inventory_archive(archive)
        log(f"[{number}/{len(archives)}] {archive.name}: {len(entries):,} files, "
            f"{sum(e.size for e in entries):,} bytes")
        manifest = {"format_version": 1, "archive": str(archive),
                    "archive_size": archive.stat().st_size,
                    "archive_mtime_ns": archive.stat().st_mtime_ns,
                    "output": str(output_root), "complete": False, "entries": []}
        manifest_name = (archive.relative_to(source).as_posix() if source.is_dir() else archive.name) + ".json"
        manifest_path = _output_path(manifest_root, manifest_name)
        _atomic_json(manifest_path, manifest)
        layer_written = layer_skipped = 0
        output_root.mkdir(parents=True, exist_ok=True)
        with archive.open("rb") as stream:
            for index, entry in enumerate(entries, 1):
                output = _output_path(output_root, entry.path)
                output.parent.mkdir(parents=True, exist_ok=True)
                # Stream uncompressed movies/audio instead of allocating a whole file.
                digest = hashlib.sha256()
                with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".switch-extract-",
                                                 suffix=".tmp", delete=False) as temp:
                    temporary = Path(temp.name)
                    try:
                        if entry.compression == "none":
                            if entry.size != entry.stored_size:
                                raise ArchiveError(f"Invalid uncompressed size: {entry.path}")
                            stream.seek(entry.offset)
                            remaining = entry.stored_size
                            while remaining:
                                data = _read_exact(stream, min(4 * 1024 * 1024, remaining))
                                temp.write(data)
                                digest.update(data)
                                remaining -= len(data)
                        else:
                            data = _read_entry(stream, entry)
                            temp.write(data)
                            digest.update(data)
                    except BaseException:
                        temp.close()
                        temporary.unlink(missing_ok=True)
                        raise
                try:
                    checksum = digest.hexdigest()
                    if output.exists():
                        if output.is_file() and output.stat().st_size == entry.size and _hash_file(output) == checksum:
                            layer_skipped += 1
                        elif overwrite:
                            os.replace(temporary, output)
                            layer_written += 1
                        else:
                            raise FileExistsError(f"Different file already exists: {output}. Use --overwrite to replace it.")
                    else:
                        os.replace(temporary, output)
                        layer_written += 1
                finally:
                    temporary.unlink(missing_ok=True)
                manifest["entries"].append({**asdict(entry), "sha256": checksum})
                if index % 5000 == 0:
                    log(f"  {archive.name}: {index:,}/{len(entries):,} files")
        manifest["complete"] = True
        manifest["completed_utc"] = datetime.now(timezone.utc).isoformat()
        _atomic_json(manifest_path, manifest)
        summary["archives"].append({"archive": str(archive), "output": str(output_root),
                                     "manifest": str(manifest_path), "files": len(entries),
                                     "written": layer_written, "skipped": layer_skipped})
        summary["files"] += len(entries)
        summary["bytes"] += sum(e.size for e in entries)
        summary["written"] += layer_written
        summary["skipped"] += layer_skipped
        _atomic_json(summary_path, summary)
    summary["complete"] = True
    _atomic_json(summary_path, summary)
    log(f"Complete: {len(archives)} archives, {summary['files']:,} files; "
        f"{summary['written']:,} written, {summary['skipped']:,} identical files skipped.")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path, nargs="?")
    parser.add_argument("--list", action="store_true", help="Print archive inventories as JSON without extracting")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing files that differ")
    args = parser.parse_args()
    try:
        if args.list:
            print(json.dumps({str(p): [asdict(e) for e in inventory_archive(p)]
                              for p in discover_archives(args.source)}, indent=2))
        elif args.target is None:
            parser.error("target is required unless --list is used")
        else:
            extract(args.source, args.target, overwrite=args.overwrite)
    except (OSError, ValueError, ImportError) as exc:
        parser.exit(1, f"Extraction failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
