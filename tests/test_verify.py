"""Tests for the dependency-free OpenType verification helpers."""

import json
import struct
from pathlib import Path

import pytest

from paper_mono_nerd_patched import verify


def test_table_directory_reads_a_valid_record() -> None:
    data = bytearray(32)
    data[:4] = b"OTTO"
    struct.pack_into(">H", data, 4, 1)
    data[12:16] = b"name"
    struct.pack_into(">II", data, 20, 28, 4)

    assert verify.table_directory(bytes(data)) == {"name": (28, 4)}


def test_table_directory_rejects_an_out_of_bounds_table() -> None:
    data = bytearray(28)
    data[:4] = b"OTTO"
    struct.pack_into(">H", data, 4, 1)
    data[12:16] = b"cmap"
    struct.pack_into(">II", data, 20, 28, 1)

    with pytest.raises(verify.VerificationError, match="outside the font file"):
        verify.table_directory(bytes(data))


def test_expected_nerd_codepoints_parses_all_supported_notations(tmp_path: Path) -> None:
    inventory = {
        "METADATA": {"code": "ignored"},
        "one": {"code": "U+E000"},
        "many": {"code": "0xE001,0xE002"},
    }
    (tmp_path / "glyphnames.json").write_text(json.dumps(inventory), encoding="utf-8")

    assert verify.expected_nerd_codepoints(tmp_path) == {0xE000, 0xE001, 0xE002}
