# Living Japanese Slang for Yomitan

Turns [Wes Robertson's Living Japanese Slang Dictionary](https://wesleycrobertson.wordpress.com/2022/06/19/living-japanese-slang-dictionary/) into a Yomitan dictionary. It fetches the live WordPress source and every article linked by its capsules, parses every entry, applies a documented editorial layer, builds the archive, validates it, and writes an HTML report of what changed.

## Get the dictionary

Download the Yomitan ZIP from the [latest release](https://github.com/welpo/living-japanese-slang/releases/latest) and import it into Yomitan.

To build it yourself, [install uv](https://docs.astral.sh/uv/getting-started/installation/) and run:

```sh
uv run ljs-update
```

This writes to `dist/`:

- a dated Yomitan ZIP
- `report.html`, showing additions and edits
- normalized entries, anomalies, evidence, a source inventory, and a build summary
- a snapshot of the source as it was fetched

Release dates use the machine's local calendar day, and that same `YYYY-MM-DD` is used everywhere in a run. `--offline --date YYYY-MM-DD` rebuilds from a snapshot created with the current capture format. A normal run fails if WordPress is unreachable rather than falling back to stale data.

To turn the newest local dictionary ZIP into a self-contained, JavaScript-free browsing page, run:

```sh
uv run ljs-explore
```

You can also pass a specific ZIP and use `--output` to choose the HTML path.

## The editorial layer

Everything that isn't a direct read of the source lives in [`overrides.toml`](overrides.toml), with a source-grounded reason beside it. This includes:

- recovering a mislabeled field, such as the `キメる` meaning
- correcting capsule links which point to the wrong article section
- exposing source-listed alternative spellings and readings as separate searchable Yomitan terms
- correcting clear capsule typos when the linked article establishes the intended headword
- adding inflection metadata when a sourced example demonstrates it, such as `シュバってきた` for `シュバる`

The normalized audit record keeps the capsule wording. Search-oriented headword corrections and alternatives affect the generated Yomitan rows, so provenance remains visible while each real form is usable.

## Releases

A weekly GitHub Actions workflow builds against the live source, runs the tests, and stops on parser errors or warnings nobody's reviewed. It publishes when canonical entries, overrides, or the semantic dictionary output change; unrelated posts, build dates, and raw-source noise don't trigger a release.

If there's a change, it bumps `data/current-entries.json` and `data/state.json`, tags the day, and publishes the ZIP alongside source-linked release notes, the full report, evidence, snapshots, and checksums.

It also runs a compatibility check against a pinned Yomitan checkout, on top of the built-in validator.

## License

The updater code is GPL-3.0-or-later, see [`LICENSE`](LICENSE).

The dictionary data belongs to Wes Robertson / Scripting Japan and is distributed under CC BY-NC-SA 4.0. Details in [`DATA-LICENSE.md`](DATA-LICENSE.md).
