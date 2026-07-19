"""Tests for the reproducible build helpers."""

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from paper_mono_nerd_patched import build


def test_sha256_reads_the_complete_file(tmp_path: Path) -> None:
    path = tmp_path / "input.bin"
    contents = b"paper-mono" * 200_000
    path.write_bytes(contents)

    assert build.sha256(path) == hashlib.sha256(contents).hexdigest()


def test_download_verified_reuses_a_valid_cached_file(tmp_path: Path) -> None:
    path = tmp_path / "cached.otf"
    path.write_bytes(b"font")
    digest = hashlib.sha256(b"font").hexdigest()

    assert build.download_verified("https://invalid.example/font", path, digest, True) == path


def test_download_verified_rejects_missing_offline_input(tmp_path: Path) -> None:
    with pytest.raises(build.BuildError, match="offline build needs"):
        build.download_verified(
            "https://invalid.example/font", tmp_path / "missing.otf", "0" * 64, True
        )


def test_safe_extract_rejects_parent_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../outside", "unsafe")

    with pytest.raises(build.BuildError, match="unsafe path"):
        build.safe_extract(archive, tmp_path / "output")


def test_write_manifest_records_pinned_inputs(tmp_path: Path) -> None:
    build.write_manifest(tmp_path)

    manifest = json.loads((tmp_path / "BUILD-MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["paper_mono"]["commit"] == build.PAPER_MONO_COMMIT
    assert manifest["nerd_fonts"]["commit"] == build.NERD_FONTS_COMMIT
    assert manifest["build"]["outputs"] == list(build.OUTPUT_FONT_NAMES)
