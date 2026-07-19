"""Download pinned inputs and build Paper Mono Nerd Font Mono OTFs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from .config import (
    FONT_PATCHER_SHA256,
    FONT_PATCHER_URL,
    NERD_FONTS_COMMIT,
    NERD_FONTS_LICENSE_SHA256,
    NERD_FONTS_LICENSE_URL,
    NERD_FONTS_VERSION,
    OUTPUT_FONT_NAMES,
    PAPER_MONO_COMMIT,
    PAPER_MONO_LICENSE_SHA256,
    PAPER_MONO_LICENSE_URL,
    PAPER_MONO_TAG,
    PATCHER_CACHE_DIR_NAME,
    SOURCE_FONTS,
)


class BuildError(RuntimeError):
    """A user-actionable build failure."""


def sha256(path: Path) -> str:
    """Return a file's SHA-256 digest."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified(url: str, destination: Path, expected_sha256: str, offline: bool) -> Path:
    """Download one immutable input, reusing it only when its digest matches."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and sha256(destination) == expected_sha256:
        return destination
    if offline:
        raise BuildError(f"offline build needs a verified cached file: {destination}")

    temporary: Path | None = None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "paper-mono-nerd-patched/1"})
        with (
            urllib.request.urlopen(request, timeout=120) as response,
            tempfile.NamedTemporaryFile(
                mode="wb", dir=destination.parent, prefix=f".{destination.name}.", delete=False
            ) as stream,
        ):
            temporary = Path(stream.name)
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        if sha256(temporary) != expected_sha256:
            raise BuildError(f"checksum mismatch for {url}; refusing to use the download")
        os.replace(temporary, destination)
        return destination
    except (OSError, urllib.error.URLError) as exc:
        raise BuildError(f"could not download {url}: {exc}") from exc
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def safe_extract(archive: Path, destination: Path) -> None:
    """Extract a zip only when every member stays below its destination."""

    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(root):
                raise BuildError(f"unsafe path in FontPatcher.zip: {member.filename}")
        bundle.extractall(destination)


def ensure_patcher(cache_dir: Path, offline: bool) -> Path:
    """Fetch and unpack the pinned Nerd Fonts patcher."""

    archive = cache_dir / f"FontPatcher-{NERD_FONTS_VERSION}.zip"
    patcher_dir = cache_dir / PATCHER_CACHE_DIR_NAME
    archive = download_verified(FONT_PATCHER_URL, archive, FONT_PATCHER_SHA256, offline)
    temporary = Path(tempfile.mkdtemp(prefix="font-patcher-", dir=cache_dir))
    try:
        safe_extract(archive, temporary)
        if not all(
            (temporary / relative).is_file() for relative in ("font-patcher", "glyphnames.json")
        ):
            raise BuildError("FontPatcher.zip did not contain the expected patcher files")
        if patcher_dir.exists():
            shutil.rmtree(patcher_dir)
        os.replace(temporary, patcher_dir)
        return patcher_dir
    except (OSError, zipfile.BadZipFile) as exc:
        raise BuildError(f"could not unpack {archive}: {exc}") from exc
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def find_fontforge(requested: str) -> str:
    """Resolve the FontForge executable without attempting installation."""

    resolved = shutil.which(requested)
    if resolved is None:
        raise BuildError(
            "FontForge is required but was not found. Install it in the build environment "
            "(on Debian/Ubuntu: fontforge and python3-fontforge), then run `uv run poe build`."
        )
    return resolved


def patch_one(fontforge: str, patcher: Path, source: Path, weight: str, work_dir: Path) -> Path:
    """Patch one source font using the official complete mono invocation."""

    output_dir = work_dir / weight
    output_dir.mkdir(parents=True)
    command = [
        fontforge,
        "--script",
        str(patcher),
        "--complete",
        "--mono",
        "--no-progressbars",
        "--quiet",
        "--outputdir",
        str(output_dir),
        str(source),
    ]
    print(f"Patching {source.name} with Nerd Fonts {NERD_FONTS_VERSION} (--complete --mono)")
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise BuildError(
            f"FontForge failed while patching {source.name} (exit {result.returncode})"
        )

    candidates = sorted(output_dir.glob("*.otf"))
    if len(candidates) != 1:
        found = ", ".join(path.name for path in candidates) or "none"
        raise BuildError(f"expected one patched OTF for {source.name}, found: {found}")
    return candidates[0]


def copy_license_bundle(
    patcher_dir: Path, stage: Path, paper_license: Path, nerd_license: Path
) -> None:
    """Copy upstream license texts beside the generated fonts."""

    licenses = stage / "LICENSES"
    licenses.mkdir(parents=True)
    shutil.copy2(paper_license, licenses / "Paper-Mono-LICENSE.txt")
    shutil.copy2(nerd_license, licenses / "Nerd-Fonts-LICENSE.txt")

    glyph_licenses = licenses / "nerd-fonts-glyph-sources"
    for candidate in sorted((patcher_dir / "src" / "glyphs").rglob("*")):
        if not candidate.is_file():
            continue
        upper_name = candidate.name.upper()
        if not upper_name.startswith(("LICENSE", "OFL", "COPYING", "APACHE")):
            continue
        target = glyph_licenses / candidate.relative_to(patcher_dir / "src" / "glyphs")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate, target)


def write_manifest(stage: Path) -> None:
    """Write a machine-readable provenance record into the artifact."""

    manifest = {
        "paper_mono": {
            "tag": PAPER_MONO_TAG,
            "commit": PAPER_MONO_COMMIT,
            "otf_sha256": {source.filename: source.sha256 for source in SOURCE_FONTS},
        },
        "nerd_fonts": {
            "version": NERD_FONTS_VERSION,
            "commit": NERD_FONTS_COMMIT,
            "font_patcher_zip_sha256": FONT_PATCHER_SHA256,
        },
        "build": {
            "font_patcher_flags": ["--complete", "--mono"],
            "output_format": "static OTF",
            "outputs": list(OUTPUT_FONT_NAMES),
            "inputs": {
                source.weight: {"url": source.url, "sha256": source.sha256}
                for source in SOURCE_FONTS
            },
        },
    }
    (stage / "BUILD-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def publish(stage: Path, output_dir: Path) -> None:
    """Publish only the generated files, preserving unrelated user files."""

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename in (*OUTPUT_FONT_NAMES, "BUILD-MANIFEST.json"):
        target = output_dir / filename
        if target.exists():
            target.unlink()
        os.replace(stage / filename, target)
    old_licenses = output_dir / "LICENSES"
    if old_licenses.exists():
        shutil.rmtree(old_licenses)
    os.replace(stage / "LICENSES", old_licenses)


def build(fontforge: str, output_dir: Path, cache_dir: Path, offline: bool) -> None:
    """Run the complete download, patch, provenance, and publish pipeline."""

    resolved_fontforge = find_fontforge(fontforge)
    cache_dir.mkdir(parents=True, exist_ok=True)
    source_dir = cache_dir / "paper-mono-sources"
    sources: dict[str, Path] = {}
    for source in SOURCE_FONTS:
        sources[source.weight] = download_verified(
            source.url, source_dir / source.filename, source.sha256, offline
        )
    paper_license = download_verified(
        PAPER_MONO_LICENSE_URL,
        source_dir / "Paper-Mono-LICENSE.txt",
        PAPER_MONO_LICENSE_SHA256,
        offline,
    )
    nerd_license = download_verified(
        NERD_FONTS_LICENSE_URL,
        cache_dir / "Nerd-Fonts-LICENSE.txt",
        NERD_FONTS_LICENSE_SHA256,
        offline,
    )
    patcher_dir = ensure_patcher(cache_dir, offline)

    with tempfile.TemporaryDirectory(prefix="paper-mono-build-", dir=cache_dir) as temporary:
        work_dir = Path(temporary) / "patched"
        stage = Path(temporary) / "dist"
        stage.mkdir()
        for source in SOURCE_FONTS:
            patched = patch_one(
                resolved_fontforge,
                patcher_dir / "font-patcher",
                sources[source.weight],
                source.weight,
                work_dir,
            )
            shutil.copy2(patched, stage / f"PaperMonoNerdFontMono-{source.weight}.otf")
        copy_license_bundle(patcher_dir, stage, paper_license, nerd_license)
        write_manifest(stage)
        publish(stage, output_dir)
    print(f"Built {len(SOURCE_FONTS)} fonts in {output_dir}")


def parse_args() -> argparse.Namespace:
    """Parse build options."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fontforge",
        default=os.environ.get("FONTFORGE", "fontforge"),
        help="FontForge executable (default: FONTFORGE or fontforge)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache"))
    parser.add_argument(
        "--offline", action="store_true", help="Use only already downloaded, verified inputs"
    )
    return parser.parse_args()


def main() -> int:
    """Run the CLI and turn expected failures into concise diagnostics."""

    args = parse_args()
    try:
        build(args.fontforge, args.output_dir.resolve(), args.cache_dir.resolve(), args.offline)
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
