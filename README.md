# Paper Mono Nerd Patched

Pinned-input, integrity-verified build tooling that patches Paper Mono's static
OTF weights with the complete Nerd Fonts glyph set. The default output is the
monospaced Nerd Font variant (`--complete --mono`), suitable for terminals and
editors.

## Outputs

`uv run poe all` builds and verifies eight static OTFs in `dist/`:

```text
PaperMonoNerdFontMono-Thin.otf
PaperMonoNerdFontMono-ExtraLight.otf
PaperMonoNerdFontMono-Light.otf
PaperMonoNerdFontMono-Regular.otf
PaperMonoNerdFontMono-Medium.otf
PaperMonoNerdFontMono-SemiBold.otf
PaperMonoNerdFontMono-Bold.otf
PaperMonoNerdFontMono-ExtraBold.otf
```

The artifact also contains `BUILD-MANIFEST.json` and `LICENSES/`. The manifest
records the exact inputs and checksums; the license directory must travel with
the fonts when they are redistributed.

## Pinned inputs and offline builds

The build does not track a moving `main` branch or a latest download:

| Input | Pinned ref | Integrity check |
| --- | --- | --- |
| Paper Mono static OTFs | Latest reviewed upstream release, resolved to an immutable commit | Per-weight SHA-256 in `src/paper_mono_nerd_patched/paper-mono.json` |
| Nerd Fonts FontPatcher | `v3.4.0`, commit `fa7b859994228a9c8759f99c55a8d31ee92a1b5e` | `a8f11e511ed7c69e96680858c06b50a643ea7752e26d5cd13dd5e5cc53ab1760` |

Inputs are cached under `.cache/`, which is ignored by Git. A build never
accepts a cached file unless its expected digest matches. To reproduce a
previously populated cache without network access:

```sh
uv run poe build            # downloads and verifies pinned inputs
uv run poe verify           # verifies all outputs and the complete pinned glyph inventory
uv run poe build --offline  # uses only the verified local cache
```

FontForge is an external system dependency and is not pinned by this project,
so generated files are verified against semantic invariants rather than claimed
to be byte-for-byte reproducible across different FontForge versions.

## Requirements

- [uv](https://docs.astral.sh/uv/) (installs Python 3.13+ and the development tools)
- FontForge with its Python scripting support

No machine-wide installation is performed by this repository. On Debian or
Ubuntu, the CI runner installs the ephemeral `fontforge` and
`python3-fontforge` packages. On a local machine, provide an existing binary:

```sh
uv run poe build --fontforge /path/to/fontforge
```

The build fails before downloading anything if FontForge is unavailable.

## Build and checks

```sh
uv sync --locked  # create the environment without changing uv.lock
uv run poe check  # lockfile, lint, format, types, tests, and package build
uv run poe all    # build, then fully verify the fonts
uv run poe clean  # remove generated outputs, downloads, and tool caches
```

[Poe the Poet](https://poethepoet.natn.io/) is installed in the development
dependency group. Run `uv run poe --help` to list all tasks. The installed project also
exposes `paper-mono-build` and `paper-mono-verify` commands. Python dependencies,
task definitions, and tool configuration live in `pyproject.toml`; `uv.lock` is
the reproducibility boundary for the environment.

Verification parses the OpenType tables directly, so it does not need
fonttools. It checks every generated file, basic Paper Mono coverage, the complete
unique codepoint inventory from Nerd Fonts' pinned `glyphnames.json`, a single
advance width for every glyph, Nerd Font Mono naming, provenance, and required
license files.

## Automated releases

The `Check for Paper Mono releases` workflow polls the upstream GitHub releases
daily and can also be run manually. When it finds a new release, it resolves the
tag to an immutable commit, hashes every static OTF and the upstream license,
and opens a pull request containing the new release lock. It refuses to update
automatically if an already-seen upstream tag moves to another commit.

Merging that pull request triggers `Publish patched font release`, which builds
and verifies the fonts before publishing a versioned zip and SHA-256 file as a
GitHub release. The workflow never publishes an unverified font build.

Repository Actions settings must allow GitHub Actions to create pull requests
for the scheduled updater to open its PR. The workflows use only the repository's
built-in `GITHUB_TOKEN`; no additional secret is required.

## Attribution

See [`NOTICE.md`](NOTICE.md) for upstream attribution and licensing details.
The generated font software remains under the upstream terms; this repository's
MIT license applies only to its build tooling and documentation.
