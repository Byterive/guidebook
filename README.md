# guidebook

Plain-language guides, refreshed when your project changes.

Version 0.1.1 · early, working

## What it does

We built guidebook to turn a project into guides that people who are not the author can read. It reads the project folder, writes guides for different readers (a client, a new teammate, a maintainer), builds them as web pages, and refreshes only the pages whose sources changed when you run `update`. It never edits your existing files; it writes only `.guidebook/`, `docs/guide-src/` and `docs/guide/`.

## Install

As a Claude Code plugin, through the Byterive marketplace:

```
/plugin marketplace add Byterive/kit
/plugin install guidebook@byterive-kit
```

We have not yet tested the marketplace install end to end. It works when Claude Code loads the plugin from a folder, and the tool also runs from a clone of this repository (see below).

## What you get

| Command | What it does | Result |
|---|---|---|
| `init <project folder>` | Proposes guide versions with reasons; add `--yes` to approve | Writes `.guidebook/guide.json` and builds the first guide |
| `status <project folder>` | Compares the guide with the project | Says fresh or stale and why (exit code 1 if stale) |
| `update <project folder>` | Rewrites only what changed (`--no-model`, `--dry-run`, `--max-calls N`) | Fresh pages; your own edits are kept |
| `serve <project folder>` | Serves the guide on http://127.0.0.1:8765 | A "Check and update" button |

From a clone, run them as `python bin/guidebook <command> <project folder>`. In Claude Code, use `/guidebook:guide init`, `status`, `update` or `serve`. Kickoff integration: `docs/kickoff-contract.md`.

Pages land in `<project>/docs/guide-src/<version>/` and the web version in `<project>/docs/guide/`. If you edit a generated page and its sources change too, the new text goes to `<page>.proposed.md` and your page is left alone.

Lower-level steps: `python -m guidebook pages <project folder> --no-model` writes the Markdown pages only; `python -m guidebook build <project folder>` builds the HTML from existing pages. Set `PYTHONPATH=src` first.

## Needs and limits

- Python 3.10 or newer, and the `markdown` package (`pip install markdown`).
- Claude Code is optional. Without it, guidebook writes the pages without model text (`--no-model`). With it, short "In plain words" sections are written through `claude -p`, cached in `.guidebook/cache`.
- It writes only `.guidebook/` and `docs/guide-src/` (plus the built `docs/guide/`). It skips secrets, `.env*`, keys and git-ignored files, and scrubs the emails, tokens and absolute paths it recognises before anything is stored or written; check the output before you share a guide.
- Still early. We have checked the pages in Chrome only. Where the project does not say something, the guide says "not known".

To run the tests: `cd tests && python -m unittest`.

## Licence

MIT. Copyright (c) 2026 Junaid Iqbal (Byterive).

*Independent project by Byterive. Not affiliated with or endorsed by Anthropic.* [byterive.com](https://byterive.com)
