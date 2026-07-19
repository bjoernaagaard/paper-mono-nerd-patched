"""Pinned inputs and output conventions for the font build."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

NERD_FONTS_VERSION = "v3.4.0"
NERD_FONTS_COMMIT = "fa7b859994228a9c8759f99c55a8d31ee92a1b5e"
NERD_FONTS_LICENSE_URL = (
    f"https://raw.githubusercontent.com/ryanoasis/nerd-fonts/{NERD_FONTS_COMMIT}/LICENSE"
)
NERD_FONTS_LICENSE_SHA256 = "1f6ad4edae6479aaace3112ede5279a23284ae54b2a34db66357aef5f64df160"
FONT_PATCHER_URL = (
    "https://github.com/ryanoasis/nerd-fonts/releases/download/"
    f"{NERD_FONTS_VERSION}/FontPatcher.zip"
)
FONT_PATCHER_SHA256 = "a8f11e511ed7c69e96680858c06b50a643ea7752e26d5cd13dd5e5cc53ab1760"


@dataclass(frozen=True)
class SourceFont:
    """One immutable upstream Paper Mono static OTF input."""

    weight: str
    filename: str
    sha256: str

    @property
    def url(self) -> str:
        return f"{PAPER_MONO_BASE_URL}/fonts/otf/{self.filename}"


def _load_paper_mono_lock() -> tuple[str, str, str, tuple[SourceFont, ...]]:
    """Load and validate the committed upstream release lock."""

    path = Path(__file__).with_name("paper-mono.json")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        tag = value["tag"]
        commit = value["commit"]
        license_sha256 = value["license_sha256"]
        fonts = tuple(
            SourceFont(font["weight"], font["filename"], font["sha256"]) for font in value["fonts"]
        )
    except (KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid Paper Mono release lock: {path}") from exc
    values = (tag, commit, license_sha256)
    if not all(isinstance(item, str) and item for item in values) or not fonts:
        raise RuntimeError(f"invalid Paper Mono release lock: {path}")
    if not all(
        font.weight and font.filename.startswith("PaperMono-") and len(font.sha256) == 64
        for font in fonts
    ):
        raise RuntimeError(f"invalid Paper Mono font entry in release lock: {path}")
    return tag, commit, license_sha256, fonts


(
    PAPER_MONO_TAG,
    PAPER_MONO_COMMIT,
    PAPER_MONO_LICENSE_SHA256,
    SOURCE_FONTS,
) = _load_paper_mono_lock()
PAPER_MONO_BASE_URL = (
    f"https://raw.githubusercontent.com/paper-design/paper-mono/{PAPER_MONO_COMMIT}"
)
PAPER_MONO_LICENSE_URL = f"{PAPER_MONO_BASE_URL}/LICENSE.txt"

OUTPUT_FONT_NAMES = tuple(f"PaperMonoNerdFontMono-{source.weight}.otf" for source in SOURCE_FONTS)
PATCHER_CACHE_DIR_NAME = f"nerd-fonts-{NERD_FONTS_VERSION}"
