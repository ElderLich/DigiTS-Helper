"""Compare Time Stranger resources across extracted trees or MVGL/CPK archives.

Archive folders are provenance, not part of a resource's identity. Base/patch
layers overlay within their own namespace; separate DLC variants remain visible.
Language and voice namespaces are never collapsed into one another. Byte/size
differences alone do not establish new content or platform compatibility.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any, Iterable


LAYER = re.compile(
    r"^(?P<name>app_(?:\d+|text\d+|voice\d+)|(?:nx_|ounce_)?patch(?:_\d+)?"
    r"(?:_text\d+)?|addcont_\d+(?:_(?:text\d+|dev))?)"
    r"(?:\.(?P<platform>dx11|nx64|ounce64))?(?:\.(?:mvgl|cpk))?$", re.I
)
CHARACTER = re.compile(r"^(chr\d+)(?=[_.]|$)", re.I)


@dataclass(frozen=True)
class Layer:
    name: str
    platform: str
    namespace: str
    domain: str
    priority: int
    container: str


def parse_layer(name: str) -> Layer | None:
    match = LAYER.fullmatch(name)
    if not match:
        return None
    base = match["name"].lower()
    namespace_match = re.search(r"(?:^|_)(text\d+|voice\d+)$", base)
    namespace = namespace_match[1] if namespace_match else "assets"
    dlc = re.match(r"addcont_\d+", base)
    domain = dlc[0] if dlc else "base"
    patch = re.match(r"(?:nx_|ounce_)?patch(?:_(\d+))?", base)
    priority = int(patch[1] or 1) if patch else 0
    if base.endswith("_dev"):
        # Development payloads do not override production assets.
        namespace += "/dev"
    return Layer(base, (match["platform"] or "").lower(), namespace,
                 domain, priority, "cpk" if name.lower().endswith(".cpk") else "mvgl")


@dataclass
class Asset:
    key: str
    relative_path: str
    size: int
    layer: Layer
    origin: Path
    entry: Any = field(default=None, repr=False)

    @property
    def extension(self) -> str:
        return PurePosixPath(self.relative_path).suffix.lower()

    def provenance(self) -> str:
        return f"{self.origin}::{self.relative_path}" if self.entry is not None else str(self.origin)


@dataclass
class Inventory:
    root: Path
    source_kind: str
    assets: list[Asset]
    layers: dict[str, dict]
    excluded_platforms: dict[str, int]
    ignored_files: int = 0
    platform_filter: str | None = None

    def effective(self) -> dict[str, list[Asset]]:
        """Keep latest base patch per path and independent DLC/container variants.

        CPK and MVGL are retained separately rather than assuming their search
        order. Ambiguous same-priority duplicates also remain explicit.
        """
        grouped: dict[tuple, list[Asset]] = defaultdict(list)
        for asset in self.assets:
            grouped[(asset.key, asset.layer.domain, asset.layer.container)].append(asset)
        result: dict[str, list[Asset]] = defaultdict(list)
        for (key, _domain, _container), variants in grouped.items():
            priority = max(a.layer.priority for a in variants)
            result[key].extend(a for a in variants if a.layer.priority == priority)
        return dict(result)

    def statistics(self) -> dict:
        effective = self.effective()
        return {
            "root": str(self.root), "source_kind": self.source_kind,
            "platform_filter": self.platform_filter,
            "physical_files": len(self.assets),
            "physical_bytes": sum(a.size for a in self.assets),
            "logical_paths": len(effective),
            "extensions": dict(sorted(Counter(a.extension for a in self.assets).items())),
            "layers": self.layers, "excluded_platforms": self.excluded_platforms,
            "ignored_files": self.ignored_files,
            "multiple_effective_variants": sum(len(a) > 1 for a in effective.values()),
        }


def _make_asset(path: str, size: int, layer: Layer, origin: Path, entry=None) -> Asset:
    relative = path.replace("\\", "/").lstrip("/")
    parts = PurePosixPath(relative).parts
    if ".." in parts or not parts:
        raise ValueError(f"Invalid resource path: {path!r}")
    key = f"{layer.namespace}/{relative}".lower()
    return Asset(key, relative, size, layer, origin, entry)


def inventory(root: Path | str, platform: str | None = None) -> Inventory:
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"Input is not a directory: {root}")
    archives: list[Path] = []
    files: list[Path] = []
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and
                         not (Path(directory) == root and d.casefold() in ("tables", "_switch_extraction")) and
                         not Path(directory, d).is_symlink())
        for name in sorted(names):
            path = Path(directory, name)
            if path.is_symlink():
                continue
            files.append(path)
            if path.suffix.lower() in (".mvgl", ".cpk") and parse_layer(path.name):
                archives.append(path)
    assets: list[Asset] = []
    layers: dict[str, dict] = {}
    excluded = Counter()
    ignored = 0

    def add_layer(label: str, layer: Layer, records: Iterable[Asset]) -> None:
        nonlocal assets
        records = list(records)
        layers[label] = {"files": len(records), "bytes": sum(a.size for a in records),
                         "platform": layer.platform, "container": layer.container,
                         "domain": layer.domain, "namespace": layer.namespace,
                         "priority": layer.priority}
        assets.extend(records)

    if archives:
        from Switch_Archives import inventory_archive
        for archive in archives:
            layer = parse_layer(archive.name)
            if platform and layer.platform and layer.platform != platform:
                excluded[layer.platform] += 1
                continue
            entries = inventory_archive(archive)
            add_layer(archive.relative_to(root).as_posix(), layer,
                      (_make_asset(e.path, e.size, layer, archive, e) for e in entries))
        kind = "archives"
        ignored = len(files) - len(archives)
    else:
        records: dict[str, list[Asset]] = defaultdict(list)
        layer_objects = {}
        for path in files:
            relative = path.relative_to(root)
            found = next(((i, parse_layer(p)) for i, p in enumerate(relative.parts[:-1])
                          if parse_layer(p)), None)
            if found is None:
                ignored += 1
                continue
            index, layer = found
            if platform and layer.platform and layer.platform != platform:
                excluded[layer.platform] += 1
                continue
            label = PurePosixPath(*relative.parts[:index + 1]).as_posix()
            asset_path = PurePosixPath(*relative.parts[index + 1:]).as_posix()
            records[label].append(_make_asset(asset_path, path.stat().st_size, layer, path))
            layer_objects[label] = layer
        for label, entries in records.items():
            add_layer(label, layer_objects[label], entries)
        kind = "extracted"
    if not assets:
        raise ValueError(f"No recognized Time Stranger resources for platform {platform!r} in {root}")
    return Inventory(root, kind, assets, layers, dict(excluded), ignored, platform)


def asset_digest(asset: Asset) -> str:
    digest = hashlib.sha256()
    if asset.entry is not None and asset.entry.compression == "none":
        # CPK movie/audio entries can be gigabytes; hash only their bounded
        # stored range without materializing the complete payload in memory.
        remaining = asset.size
        with asset.origin.open("rb") as stream:
            stream.seek(asset.entry.offset)
            while remaining:
                block = stream.read(min(1024 * 1024, remaining))
                if not block:
                    raise ValueError(f"Truncated archive payload: {asset.provenance()}")
                digest.update(block)
                remaining -= len(block)
    elif asset.entry is not None:
        from Switch_Archives import read_entry
        digest.update(read_entry(asset.origin, asset.entry))
    else:
        with asset.origin.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def _character_ids(keys: Iterable[str]) -> set[str]:
    result = set()
    for key in keys:
        filename = PurePosixPath(key).name
        match = CHARACTER.match(filename)
        if match and filename.endswith(".geom"):
            result.add(match[1].lower())
    return result


def compare(windows: Inventory, switch: Inventory,
            hash_extensions: Iterable[str] = ()) -> dict:
    left, right = windows.effective(), switch.effective()
    left_keys, right_keys = set(left), set(right)
    common = sorted(left_keys & right_keys)
    only_windows, only_switch = sorted(left_keys - right_keys), sorted(right_keys - left_keys)
    extensions = {e.lower() if e.startswith(".") else "." + e.lower() for e in hash_extensions}
    digest_cache = {}

    def digest(asset):
        key = (str(asset.origin), asset.relative_path)
        if key not in digest_cache:
            digest_cache[key] = asset_digest(asset)
        return digest_cache[key]

    statuses = Counter()
    rows = []
    for key in common:
        a, b = left[key], right[key]
        size_match = bool({f.size for f in a} & {f.size for f in b})
        if PurePosixPath(key).suffix.lower() in extensions:
            matches = ({digest(f) for f in a} & {digest(f) for f in b}) if size_match else set()
            status = "matching_content_variant" if matches else "different_content"
        else:
            status = "matching_size_unverified" if size_match else "different_size"
        statuses[status] += 1
        rows.append({"path": key, "status": status,
                     "windows_sizes": sorted({f.size for f in a}),
                     "switch_sizes": sorted({f.size for f in b}),
                     "windows_sources": [f.provenance() for f in a],
                     "switch_sources": [f.provenance() for f in b]})
    left_models = {k for k in left_keys if k.endswith(".geom")}
    right_models = {k for k in right_keys if k.endswith(".geom")}
    left_chr, right_chr = _character_ids(left_models), _character_ids(right_models)
    new_models = right_models - left_models
    new_lods = {k for k in new_models if re.search(r"_lod_\d+(?=\.geom$)", k)}
    lods_with_windows_base = {k for k in new_lods
                             if re.sub(r"_lod_\d+(?=\.geom$)", "", k) in left_models}
    summary = {
        "windows": windows.statistics(), "switch": switch.statistics(),
        "common_paths": len(common), "only_windows_paths": len(only_windows),
        "only_switch_paths": len(only_switch), "common_path_statuses": dict(statuses),
        "hash_extensions": sorted(extensions),
        "only_switch_extensions": dict(sorted(Counter(PurePosixPath(k).suffix for k in only_switch).items())),
        "only_windows_extensions": dict(sorted(Counter(PurePosixPath(k).suffix for k in only_windows).items())),
        "models": {"windows": len(left_models), "switch": len(right_models),
                   "common": len(left_models & right_models),
                   "only_switch": sorted(right_models - left_models),
                   "only_windows": sorted(left_models - right_models),
                   "only_switch_lod_count": len(new_lods),
                   "only_switch_lods_with_windows_base": len(lods_with_windows_base),
                   "only_switch_non_lod": sorted(new_models - new_lods)},
        "character_model_ids": {"windows": len(left_chr), "switch": len(right_chr),
                                "only_switch": sorted(right_chr - left_chr),
                                "only_windows": sorted(left_chr - right_chr)},
        "method": [
            "Paths are relative to archive roots; dx11/nx64 suffixes and packaging do not create new assets.",
            "Text and voice language namespaces remain separate. _dev payloads have a separate namespace.",
            "Within each base/DLC and container namespace, the highest numbered patch wins for each path.",
            "Independent DLC and MVGL/CPK variants remain visible; matching_content_variant means at least one pair matches.",
            "Different hashes/sizes can be platform conversions; they do not establish new models or gameplay.",
            "New chr IDs are inferred from chrNNN*.geom filenames, not proof of playable Digimon.",
            "Presence comparison covers supplied archives/trees only; it does not assert runtime load order or unlockability.",
            "Generated Tables and _switch_extraction directories at the extraction root are excluded.",
        ],
    }
    return {"summary": summary, "common": rows,
            "only_windows": {k: left[k] for k in only_windows},
            "only_switch": {k: right[k] for k in only_switch}}


def write_report(result: dict, output: Path | str) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    summary = result["summary"]
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (output / "common_paths.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ["path", "status", "windows_sizes", "switch_sizes", "windows_sources", "switch_sources"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in result["common"]:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v for k, v in row.items()})
    for side in ("only_switch", "only_windows"):
        with (output / f"{side}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["logical_path", "size", "source", "layer", "container"])
            for key, assets in result[side].items():
                for asset in assets:
                    writer.writerow([key, asset.size, asset.provenance(), asset.layer.name, asset.layer.container])
    with (output / "models.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["status", "logical_path", "character_id"])
        for side in ("only_switch", "only_windows"):
            for key in summary["models"][side]:
                match = CHARACTER.match(PurePosixPath(key).name)
                writer.writerow([side, key, match[1] if match else ""])
    lines = ["# Time Stranger Switch / Windows asset comparison", "",
             f"Windows source: `{summary['windows']['root']}` ({summary['windows']['source_kind']}).", "",
             f"Switch source: `{summary['switch']['root']}` ({summary['switch']['source_kind']}; platform filter: **{summary['switch']['platform_filter'] or 'all'}**).", "",
             "| Measure | Windows | Switch |", "| --- | ---: | ---: |",
             f"| Physical files | {summary['windows']['physical_files']:,} | {summary['switch']['physical_files']:,} |",
             f"| Logical paths | {summary['windows']['logical_paths']:,} | {summary['switch']['logical_paths']:,} |",
             f"| Model paths (.geom) | {summary['models']['windows']:,} | {summary['models']['switch']:,} |",
             f"| Character model IDs | {summary['character_model_ids']['windows']:,} | {summary['character_model_ids']['switch']:,} |", "",
             f"Common logical paths: **{summary['common_paths']:,}**. Switch-only: **{summary['only_switch_paths']:,}**. Windows-only: **{summary['only_windows_paths']:,}**.", "",
             f"Switch-only model paths: **{len(summary['models']['only_switch']):,}**. Switch-only character model IDs: **{len(summary['character_model_ids']['only_switch']):,}**.", "",
             f"Of those model paths, **{summary['models']['only_switch_lod_count']:,}** are numbered LOD variants; **{summary['models']['only_switch_lods_with_windows_base']:,}** have an exact base-model filename in Windows. **{len(summary['models']['only_switch_non_lod']):,}** are non-LOD filenames.", "",
             "Switch-only character IDs: " + (", ".join(f"`{x}`" for x in summary["character_model_ids"]["only_switch"]) or "none") + ".", "",
             "## Common file comparison", "", "| Status | Paths |", "| --- | ---: |"]
    lines.extend(f"| {status} | {count:,} |" for status, count in sorted(summary["common_path_statuses"].items()))
    if summary["switch"]["platform_filter"] == "ounce64":
        lines += ["", "This is a separate comparison of the supplied ounce64 payloads. A sparse DLC-only set is not a complete game baseline; Windows-only counts here are coverage differences."]
    lines += ["", "## Interpretation", ""] + ["- " + note for note in summary["method"]]
    lines += ["", "`models.csv` lists all unique model paths. `only_switch.csv` and `only_windows.csv` include provenance and sizes; `common_paths.csv` includes common-path comparisons. `summary.json` contains complete layer coverage and counts.", ""]
    (output / "comparison.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows", required=True, type=Path)
    parser.add_argument("--switch", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--switch-platform", choices=("nx64", "ounce64"), default="nx64",
                        help="Compare one platform at a time; sparse ounce64 DLC is not a full game dump.")
    parser.add_argument("--hash-ext", default="",
                        help="Comma-separated extensions to compare using SHA-256 (e.g. .geom,.mbe,.lua). Other files compare size only.")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    for source in (args.windows.resolve(), args.switch.resolve()):
        if output == source or source in output.parents:
            parser.error("Keep reports outside the source trees so later inventories remain clean.")
    print("Inventorying Windows...", flush=True)
    windows = inventory(args.windows, "dx11")
    print("Inventorying Switch...", flush=True)
    switch = inventory(args.switch, args.switch_platform)
    print("Comparing logical assets...", flush=True)
    result = compare(windows, switch, (x.strip() for x in args.hash_ext.split(",") if x.strip()))
    write_report(result, output)
    summary = result["summary"]
    print(json.dumps({"report": str(output / "comparison.md"),
                      "common_paths": summary["common_paths"],
                      "switch_only_paths": summary["only_switch_paths"],
                      "switch_only_models": len(summary["models"]["only_switch"]),
                      "switch_only_character_ids": summary["character_model_ids"]["only_switch"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
