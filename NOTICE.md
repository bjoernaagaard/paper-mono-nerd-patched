# License and attribution

The Python and Poe build tooling in this repository is MIT-licensed; see
[`LICENSE`](LICENSE).

The generated fonts are not licensed by this repository. They are derivative
font software and retain the upstream licenses and attributions of the
components used to build them:

- Paper Mono is copyright Lost Coast Labs, Inc. (Paper Design), based on Geist
  Mono by Vercel in collaboration with basement.studio, and is released under
  the [SIL Open Font License 1.1](https://scripts.sil.org/OFL).
- The icon glyphs and patcher come from
  [Nerd Fonts v3.4.0](https://github.com/ryanoasis/nerd-fonts/releases/tag/v3.4.0).
  Nerd Fonts documents the patcher under MIT and the glyph sources under their
  respective licenses.

`uv run poe build` downloads and verifies the exact upstream license texts, then
copies them and every license-bearing file shipped with the Nerd Fonts
patcher into `dist/LICENSES/`. Distribute that directory with the generated
fonts. The exact source refs and checksums are recorded in
`dist/BUILD-MANIFEST.json`.
