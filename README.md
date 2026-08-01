# Living Japanese Slang for Yomitan

Turns [Wes Robertson's Living Japanese Slang Dictionary](https://wesleycrobertson.wordpress.com/2022/06/19/living-japanese-slang-dictionary/) into a Yomitan dictionary. It fetches the live WordPress source, parses every capsule, applies a small documented editorial layer, builds the archive, validates it, and writes an HTML report of what changed.

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

Release dates use the machine's local calendar day, and that same `YYYY-MM-DD` is used everywhere in a run. `--offline --date YYYY-MM-DD` reproduces a past run from its snapshot. A normal run fails if WordPress is unreachable rather than falling back to stale data.

## The editorial layer

Everything that isn't a direct read of the source lives in [`overrides.toml`](overrides.toml). Right now that's three decisions:

1. recover the mislabeled `キメる` meaning
2. fix its source link
3. tag `シュバる` as `v5`, based on the sourced example `シュバってきた`

## Releases

A weekly GitHub Actions workflow builds against the live source, runs the tests, and stops on parser errors or warnings nobody's reviewed. It only publishes when canonical entries or overrides change; unrelated posts and raw-source noise don't trigger a release.

If there's a change, it bumps `data/current-entries.json` and `data/state.json`, tags the day, and publishes the ZIP alongside source-linked release notes, the full report, evidence, snapshots, and checksums.

It also runs a compatibility check against a pinned Yomitan checkout, on top of the built-in validator.

## License

The updater code is GPL-3.0-or-later, see [`LICENSE`](LICENSE).

The dictionary data belongs to Wes Robertson / Scripting Japan and is distributed under CC BY-NC-SA 4.0. Details in [`DATA-LICENSE.md`](DATA-LICENSE.md).
