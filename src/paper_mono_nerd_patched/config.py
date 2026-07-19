"""Pinned inputs and output conventions for the font build."""

from __future__ import annotations

from dataclasses import dataclass

PAPER_MONO_TAG = "v0.300"
PAPER_MONO_COMMIT = "98b402029c787b7c8130f9527ded897c09faacdb"
PAPER_MONO_BASE_URL = (
    f"https://raw.githubusercontent.com/paper-design/paper-mono/{PAPER_MONO_COMMIT}"
)
PAPER_MONO_LICENSE_URL = f"{PAPER_MONO_BASE_URL}/LICENSE.txt"
PAPER_MONO_LICENSE_SHA256 = "6c09ddf064a0b0f7cfffd555c674bfa08bb1e1a75a3e4b7b1a63c8f7cbb5a1f2"

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


SOURCE_FONTS = (
    SourceFont(
        "Thin",
        "PaperMono-Thin.otf",
        "8ed242877a84dd5cf56b19b85c2755c583c65e5838e7d4be1703419096719361",
    ),
    SourceFont(
        "ExtraLight",
        "PaperMono-ExtraLight.otf",
        "143f78efe26255eb88dd80907252db97b6603549874a06eb27b608602a2f59c9",
    ),
    SourceFont(
        "Light",
        "PaperMono-Light.otf",
        "c6b86905a88201ff829761448f051c417283f593507776aa160aa56110d8fc4c",
    ),
    SourceFont(
        "Regular",
        "PaperMono-Regular.otf",
        "7f44079090c28c68e8e9594df990e0cdd6c41167c4bbf94c8b5fcce043df691d",
    ),
    SourceFont(
        "Medium",
        "PaperMono-Medium.otf",
        "6d9a2a6b31ccd0d85547d803dabd5766daaf70e6997c5cde8c04398988b67971",
    ),
    SourceFont(
        "SemiBold",
        "PaperMono-SemiBold.otf",
        "dbc770b524cfb235d818960be6d45bd58282f76488bb462f4898b24fcbf2cd76",
    ),
    SourceFont(
        "Bold",
        "PaperMono-Bold.otf",
        "8e1a0527308221488903ebdf8b5f4293323b9450c4eec448f1d3367d949eb6a5",
    ),
    SourceFont(
        "ExtraBold",
        "PaperMono-ExtraBold.otf",
        "c21ed8ebbd5b3cdeb9551b2e5e647929d1fedf16520822717ccafbc808c4ff1c",
    ),
)

OUTPUT_FONT_NAMES = tuple(f"PaperMonoNerdFontMono-{source.weight}.otf" for source in SOURCE_FONTS)
PATCHER_CACHE_DIR_NAME = f"nerd-fonts-{NERD_FONTS_VERSION}"
