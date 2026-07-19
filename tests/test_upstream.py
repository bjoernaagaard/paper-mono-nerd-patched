"""Tests for upstream Paper Mono release discovery and locking."""

import hashlib
import json
from pathlib import Path

import pytest

from paper_mono_nerd_patched import upstream


def test_discover_latest_lock_resolves_commit_and_hashes_fonts() -> None:
    commit = "b" * 40

    def get_api(path: str, token: str | None) -> object:
        assert token == "token"
        if path == "releases/latest":
            return {"tag_name": "v0.400"}
        if path == "commits/v0.400":
            return {"sha": commit}
        if path == f"contents/fonts/otf?ref={commit}":
            return [
                {"type": "file", "name": "PaperMono-Bold.otf"},
                {"type": "file", "name": "README.md"},
                {"type": "file", "name": "PaperMono-Regular.otf"},
            ]
        raise AssertionError(f"unexpected API path: {path}")

    def get_bytes(url: str, token: str | None) -> bytes:
        assert token == "token"
        return url.encode()

    lock = upstream.discover_latest_lock("token", get_api=get_api, get_bytes=get_bytes)

    assert lock["tag"] == "v0.400"
    assert lock["commit"] == commit
    fonts = lock["fonts"]
    assert isinstance(fonts, list)
    assert [font["weight"] for font in fonts] == ["Regular", "Bold"]
    regular_url = f"{upstream.RAW_ROOT}/{commit}/fonts/otf/PaperMono-Regular.otf"
    assert fonts[0]["sha256"] == hashlib.sha256(regular_url.encode()).hexdigest()


def test_update_lock_writes_a_new_release_atomically(tmp_path: Path) -> None:
    path = tmp_path / "paper-mono.json"
    current = {"tag": "v0.300", "commit": "a" * 40}
    latest: upstream.JsonObject = {
        "schema": 1,
        "tag": "v0.400",
        "commit": "b" * 40,
        "fonts": [],
    }
    path.write_text(json.dumps(current), encoding="utf-8")

    assert upstream.update_lock(path, latest)
    assert json.loads(path.read_text(encoding="utf-8")) == latest
    assert not path.with_suffix(".json.tmp").exists()
    assert not upstream.update_lock(path, latest)


def test_update_lock_rejects_a_moved_release_tag(tmp_path: Path) -> None:
    path = tmp_path / "paper-mono.json"
    path.write_text(json.dumps({"tag": "v0.400", "commit": "a" * 40}), encoding="utf-8")

    with pytest.raises(upstream.UpdateError, match=r"upstream tag v0\.400 moved"):
        upstream.update_lock(path, {"tag": "v0.400", "commit": "b" * 40})
