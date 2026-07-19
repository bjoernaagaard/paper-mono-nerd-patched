"""Verify Paper Mono Nerd Font Mono artifacts without third-party Python packages."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

from .config import (
    FONT_PATCHER_SHA256,
    NERD_FONTS_COMMIT,
    NERD_FONTS_VERSION,
    OUTPUT_FONT_NAMES,
    PAPER_MONO_COMMIT,
    PAPER_MONO_TAG,
    PATCHER_CACHE_DIR_NAME,
)


class VerificationError(RuntimeError):
    """A failed artifact invariant."""


def table_directory(data: bytes) -> dict[str, tuple[int, int]]:
    """Read the OpenType table directory and validate its bounds."""

    if len(data) < 12 or data[:4] not in (b"OTTO", b"\x00\x01\x00\x00"):
        raise VerificationError("not a supported OpenType/TrueType font")
    table_count = struct.unpack_from(">H", data, 4)[0]
    directory_end = 12 + table_count * 16
    if directory_end > len(data):
        raise VerificationError("truncated OpenType table directory")
    tables: dict[str, tuple[int, int]] = {}
    for index in range(table_count):
        offset = 12 + index * 16
        tag = data[offset : offset + 4].decode("ascii", errors="replace")
        table_offset, table_length = struct.unpack_from(">II", data, offset + 8)
        if table_offset + table_length > len(data):
            raise VerificationError(f"table {tag!r} is outside the font file")
        tables[tag] = (table_offset, table_length)
    return tables


def cmap_codepoints(data: bytes, tables: dict[str, tuple[int, int]]) -> set[int]:
    """Collect mapped Unicode codepoints from cmap formats 4, 12, and 13."""

    offset, length = tables.get("cmap", (0, 0))
    if not offset:
        raise VerificationError("font has no cmap table")
    cmap = data[offset : offset + length]
    if len(cmap) < 4:
        raise VerificationError("truncated cmap table")
    records = struct.unpack_from(">H", cmap, 2)[0]
    codepoints: set[int] = set()
    for index in range(records):
        record_offset = 4 + index * 8
        if record_offset + 8 > len(cmap):
            raise VerificationError("truncated cmap encoding record")
        subtable_offset = struct.unpack_from(">I", cmap, record_offset + 4)[0]
        if subtable_offset + 2 > len(cmap):
            raise VerificationError("cmap subtable is outside cmap")
        fmt = struct.unpack_from(">H", cmap, subtable_offset)[0]
        if fmt == 4:
            codepoints.update(cmap_format_4(cmap, subtable_offset))
        elif fmt in (12, 13):
            codepoints.update(cmap_format_12_or_13(cmap, subtable_offset))
    return codepoints


def cmap_format_4(cmap: bytes, offset: int) -> set[int]:
    """Read a format 4 BMP cmap."""

    if offset + 14 > len(cmap):
        raise VerificationError("truncated cmap format 4 header")
    length = struct.unpack_from(">H", cmap, offset + 2)[0]
    seg_count_times_two = struct.unpack_from(">H", cmap, offset + 6)[0]
    end = offset + length
    if end > len(cmap) or length < 16:
        raise VerificationError("invalid cmap format 4 length")
    segments = seg_count_times_two // 2
    end_codes = offset + 14
    start_codes = end_codes + 2 * segments + 2
    id_deltas = start_codes + 2 * segments
    id_range_offsets = id_deltas + 2 * segments
    if id_range_offsets + 2 * segments > end:
        raise VerificationError("truncated cmap format 4 segments")
    codepoints: set[int] = set()
    for index in range(segments):
        segment_end = struct.unpack_from(">H", cmap, end_codes + 2 * index)[0]
        segment_start = struct.unpack_from(">H", cmap, start_codes + 2 * index)[0]
        if segment_end == 0xFFFF:
            continue
        if segment_start > segment_end:
            raise VerificationError("invalid cmap format 4 segment")
        delta = struct.unpack_from(">h", cmap, id_deltas + 2 * index)[0]
        range_offset = struct.unpack_from(">H", cmap, id_range_offsets + 2 * index)[0]
        for codepoint in range(segment_start, segment_end + 1):
            if range_offset == 0:
                glyph_id = (codepoint + delta) & 0xFFFF
            else:
                glyph_offset = id_range_offsets + 2 * index + range_offset
                glyph_offset += 2 * (codepoint - segment_start)
                if glyph_offset + 2 > end:
                    raise VerificationError("cmap format 4 glyph offset is outside the table")
                glyph_id = struct.unpack_from(">H", cmap, glyph_offset)[0]
                if glyph_id:
                    glyph_id = (glyph_id + delta) & 0xFFFF
            if glyph_id:
                codepoints.add(codepoint)
    return codepoints


def cmap_format_12_or_13(cmap: bytes, offset: int) -> set[int]:
    """Read a format 12/13 Unicode cmap."""

    if offset + 16 > len(cmap):
        raise VerificationError("truncated cmap format 12/13 header")
    length = struct.unpack_from(">I", cmap, offset + 4)[0]
    group_count = struct.unpack_from(">I", cmap, offset + 12)[0]
    end = offset + length
    if end > len(cmap) or offset + 16 + group_count * 12 > end:
        raise VerificationError("invalid cmap format 12/13 groups")
    codepoints: set[int] = set()
    for index in range(group_count):
        group_offset = offset + 16 + index * 12
        start, stop, glyph_id = struct.unpack_from(">III", cmap, group_offset)
        if start > stop or stop > 0x10FFFF:
            raise VerificationError("invalid cmap format 12/13 range")
        if glyph_id:
            codepoints.update(range(start, stop + 1))
    return codepoints


def advance_widths(data: bytes, tables: dict[str, tuple[int, int]]) -> list[int]:
    """Return one horizontal advance width per glyph."""

    try:
        hhea_offset, _ = tables["hhea"]
        maxp_offset, _ = tables["maxp"]
        hmtx_offset, hmtx_length = tables["hmtx"]
    except KeyError as exc:
        raise VerificationError(f"font is missing required metrics table {exc.args[0]}") from exc
    glyph_count = struct.unpack_from(">H", data, maxp_offset + 4)[0]
    metric_count = struct.unpack_from(">H", data, hhea_offset + 34)[0]
    if metric_count == 0 or metric_count > glyph_count:
        raise VerificationError("invalid horizontal metric count")
    if metric_count * 4 > hmtx_length:
        raise VerificationError("truncated hmtx table")
    metrics = [
        struct.unpack_from(">H", data, hmtx_offset + index * 4)[0] for index in range(metric_count)
    ]
    return metrics + [metrics[-1]] * (glyph_count - metric_count)


def name_strings(data: bytes, tables: dict[str, tuple[int, int]]) -> set[str]:
    """Decode the common name-table records used for family and style names."""

    offset, length = tables.get("name", (0, 0))
    if not offset or length < 6:
        return set()
    name = data[offset : offset + length]
    count, storage_offset = struct.unpack_from(">HH", name, 2)
    strings: set[str] = set()
    for index in range(count):
        record_offset = 6 + index * 12
        if record_offset + 12 > len(name):
            raise VerificationError("truncated name record")
        platform, _, _, name_id, string_length, string_offset = struct.unpack_from(
            ">HHHHHH", name, record_offset
        )
        if name_id not in (1, 2, 4, 6):
            continue
        start = storage_offset + string_offset
        raw = name[start : start + string_length]
        encoding = "utf-16-be" if platform in (0, 3) else "mac_roman"
        strings.add(raw.decode(encoding, errors="replace"))
    return strings


def expected_nerd_codepoints(patcher_dir: Path) -> set[int]:
    """Load the exact icon cmap inventory shipped with the pinned patcher."""

    path = patcher_dir / "glyphnames.json"
    if not path.is_file():
        raise VerificationError(
            f"missing {path}; run `uv run poe build` first so the pinned Nerd Fonts inventory "
            "is cached"
        )
    try:
        inventory = json.loads(path.read_text(encoding="utf-8"))
        codes = {
            int(part.removeprefix("0x"), 16)
            for name, glyph in inventory.items()
            if name != "METADATA"
            for part in str(glyph["code"]).replace("U+", "0x").split(",")
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid Nerd Fonts glyph inventory: {path}") from exc
    if not codes:
        raise VerificationError("Nerd Fonts glyph inventory is empty")
    return codes


def verify_font(path: Path, expected_icons: set[int]) -> None:
    """Check coverage, mono metrics, and patched naming for one font."""

    data = path.read_bytes()
    tables = table_directory(data)
    codepoints = cmap_codepoints(data, tables)
    missing = expected_icons - codepoints
    if missing:
        sample = ", ".join(f"U+{code:04X}" for code in sorted(missing)[:12])
        raise VerificationError(
            f"{path.name} is missing {len(missing)} Nerd Fonts codepoints ({sample})"
        )
    required_base = {0x20, 0x30, 0x41, 0x61, 0x7E}
    if not required_base <= codepoints:
        raise VerificationError(f"{path.name} is missing a basic Paper Mono character")
    widths = advance_widths(data, tables)
    nonzero_widths = {width for width in widths if width}
    if len(nonzero_widths) != 1:
        raise VerificationError(
            f"{path.name} is not monospaced ({len(nonzero_widths)} nonzero advance widths)"
        )
    names = name_strings(data, tables)
    if not any("Nerd Font" in name and "Mono" in name for name in names):
        raise VerificationError(f"{path.name} has no Nerd Font Mono name record")
    print(f"verified {path.name}: {len(codepoints)} codepoints, width {next(iter(nonzero_widths))}")


def verify(font_dir: Path, patcher_dir: Path) -> None:
    """Verify all outputs and their provenance record."""

    expected_icons = expected_nerd_codepoints(patcher_dir)
    manifest_path = font_dir / "BUILD-MANIFEST.json"
    if not manifest_path.is_file():
        raise VerificationError(f"missing {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["paper_mono"]["commit"] != PAPER_MONO_COMMIT:
        raise VerificationError("manifest Paper Mono commit is not pinned to the configured source")
    if manifest["nerd_fonts"]["commit"] != NERD_FONTS_COMMIT:
        raise VerificationError("manifest Nerd Fonts commit is not pinned to the configured source")
    if manifest["nerd_fonts"]["font_patcher_zip_sha256"] != FONT_PATCHER_SHA256:
        raise VerificationError(
            "manifest FontPatcher checksum does not match the configured archive"
        )
    if manifest["paper_mono"]["tag"] != PAPER_MONO_TAG:
        raise VerificationError("manifest Paper Mono tag is not the configured release")
    if manifest["nerd_fonts"]["version"] != NERD_FONTS_VERSION:
        raise VerificationError("manifest Nerd Fonts version is not the configured release")
    for filename in OUTPUT_FONT_NAMES:
        path = font_dir / filename
        if not path.is_file():
            raise VerificationError(f"missing expected output {path}")
        verify_font(path, expected_icons)
    for required_license in (
        font_dir / "LICENSES" / "Paper-Mono-LICENSE.txt",
        font_dir / "LICENSES" / "Nerd-Fonts-LICENSE.txt",
    ):
        if not required_license.is_file():
            raise VerificationError(f"missing required attribution file {required_license}")
    print(f"verified complete Nerd Fonts inventory: {len(expected_icons)} unique codepoints")


def parse_args() -> argparse.Namespace:
    """Parse verification options."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-dir", type=Path, default=Path("dist"))
    parser.add_argument("--patcher-dir", type=Path, default=Path(".cache") / PATCHER_CACHE_DIR_NAME)
    return parser.parse_args()


def main() -> int:
    """Run the CLI and report failed invariants."""

    args = parse_args()
    try:
        verify(args.font_dir.resolve(), args.patcher_dir.resolve())
    except (OSError, KeyError, json.JSONDecodeError, VerificationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
