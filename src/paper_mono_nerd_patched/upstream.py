"""Update the committed Paper Mono release lock from GitHub's latest release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

API_ROOT = "https://api.github.com/repos/paper-design/paper-mono"
RAW_ROOT = "https://raw.githubusercontent.com/paper-design/paper-mono"
LOCK_PATH = Path(__file__).with_name("paper-mono.json")
TAG_PATTERN = re.compile(r"v\d+(?:\.\d+)+(?:[-._][A-Za-z0-9]+)*\Z")
FONT_PATTERN = re.compile(r"PaperMono-([A-Za-z0-9]+)\.otf\Z")
WEIGHT_ORDER = {
    weight: index
    for index, weight in enumerate(
        ("Thin", "ExtraLight", "Light", "Regular", "Medium", "SemiBold", "Bold", "ExtraBold")
    )
}

JsonObject = dict[str, object]
ApiGetter = Callable[[str, str | None], object]
Downloader = Callable[[str, str | None], bytes]


class UpdateError(RuntimeError):
    """An unsafe or malformed upstream release update."""


def _request(url: str, token: str | None, accept: str) -> bytes:
    headers = {
        "Accept": accept,
        "User-Agent": "paper-mono-nerd-patched-release-checker/1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except (OSError, urllib.error.URLError) as exc:
        raise UpdateError(f"could not fetch {url}: {exc}") from exc


def api_get(path: str, token: str | None) -> object:
    """Fetch one GitHub API response."""

    url = f"{API_ROOT}/{path.lstrip('/')}"
    try:
        return json.loads(_request(url, token, "application/vnd.github+json"))
    except json.JSONDecodeError as exc:
        raise UpdateError(f"GitHub returned invalid JSON for {url}") from exc


def download(url: str, token: str | None) -> bytes:
    """Download one immutable upstream file."""

    return _request(url, token, "application/octet-stream")


def discover_latest_lock(
    token: str | None = None,
    *,
    get_api: ApiGetter = api_get,
    get_bytes: Downloader = download,
) -> JsonObject:
    """Resolve the latest release to a commit and hash every static OTF input."""

    release = _object(get_api("releases/latest", token), "latest release")
    tag = _string(release, "tag_name", "latest release")
    if not TAG_PATTERN.fullmatch(tag):
        raise UpdateError(f"unexpected Paper Mono release tag: {tag!r}")

    encoded_tag = urllib.parse.quote(tag, safe="")
    commit_value = _object(get_api(f"commits/{encoded_tag}", token), "release commit")
    commit = _string(commit_value, "sha", "release commit")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise UpdateError(f"unexpected Paper Mono commit: {commit!r}")

    contents = get_api(f"contents/fonts/otf?ref={commit}", token)
    if not isinstance(contents, list):
        raise UpdateError("Paper Mono fonts/otf response is not a directory listing")
    fonts: list[JsonObject] = []
    seen_weights: set[str] = set()
    for item in contents:
        entry = _object(item, "font directory entry")
        if entry.get("type") != "file":
            continue
        filename = _string(entry, "name", "font directory entry")
        match = FONT_PATTERN.fullmatch(filename)
        if match is None:
            continue
        weight = match.group(1)
        if weight in seen_weights:
            raise UpdateError(f"duplicate Paper Mono weight in upstream release: {weight}")
        seen_weights.add(weight)
        url = f"{RAW_ROOT}/{commit}/fonts/otf/{urllib.parse.quote(filename)}"
        fonts.append(
            {
                "weight": weight,
                "filename": filename,
                "sha256": hashlib.sha256(get_bytes(url, token)).hexdigest(),
            }
        )
    if not fonts:
        raise UpdateError("latest Paper Mono release contains no static PaperMono-*.otf files")
    fonts.sort(key=lambda font: (WEIGHT_ORDER.get(str(font["weight"]), 10_000), font["weight"]))

    license_url = f"{RAW_ROOT}/{commit}/LICENSE.txt"
    return {
        "schema": 1,
        "tag": tag,
        "commit": commit,
        "license_sha256": hashlib.sha256(get_bytes(license_url, token)).hexdigest(),
        "fonts": fonts,
    }


def update_lock(path: Path, latest: JsonObject) -> bool:
    """Atomically update a lock, rejecting mutation of an already-seen release tag."""

    current = _object(json.loads(path.read_text(encoding="utf-8")), "current release lock")
    current_tag = _string(current, "tag", "current release lock")
    current_commit = _string(current, "commit", "current release lock")
    latest_tag = _string(latest, "tag", "latest release lock")
    latest_commit = _string(latest, "commit", "latest release lock")
    if current_tag == latest_tag and current_commit != latest_commit:
        raise UpdateError(
            f"upstream tag {latest_tag} moved from {current_commit} to {latest_commit}; "
            "manual review is required"
        )
    if current == latest:
        return False
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(latest, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return True


def _object(value: object, label: str) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise UpdateError(f"{label} is not a JSON object")
    return value


def _string(value: JsonObject, key: str, label: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise UpdateError(f"{label} has no valid {key}")
    return item


def parse_args() -> argparse.Namespace:
    """Parse updater options."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    parser.add_argument(
        "--github-output",
        type=Path,
        default=Path(os.environ["GITHUB_OUTPUT"]) if os.environ.get("GITHUB_OUTPUT") else None,
        help="Append changed, tag, commit, and release URL values for GitHub Actions",
    )
    return parser.parse_args()


def main() -> int:
    """Update the release lock and expose the result to GitHub Actions."""

    args = parse_args()
    try:
        latest = discover_latest_lock(os.environ.get("GITHUB_TOKEN"))
        changed = update_lock(args.lock, latest)
    except (OSError, TypeError, ValueError, json.JSONDecodeError, UpdateError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    tag = _string(latest, "tag", "latest release lock")
    commit = _string(latest, "commit", "latest release lock")
    release_url = f"https://github.com/paper-design/paper-mono/releases/tag/{tag}"
    print(f"Paper Mono {tag} at {commit}: {'update available' if changed else 'already current'}")
    if args.github_output is not None:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"changed={'true' if changed else 'false'}\n")
            output.write(f"tag={tag}\n")
            output.write(f"commit={commit}\n")
            output.write(f"release_url={release_url}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
