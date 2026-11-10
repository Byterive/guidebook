---
title: Kickoff contract
summary: The config files, manifest and commands that kickoff and guidebook agree on (contract 1), so either side can change without reading the other's code.
keywords: [kickoff, contract, guide.json, manifest, commands, exit codes]
status: confirmed
updated: 2026-10-25
---

# Kickoff contract (contract 1)

Guidebook works without kickoff. Kickoff only calls guidebook if the `guidebook` command exists. The owner of this schema is guidebook; kickoff keeps a short copy and the `contract` number.

## Detect guidebook
Run `guidebook --version`. It prints `guidebook <version> (kickoff contract <n>)`. If the command is missing, skip the guide and do not fail. Without installing, the launcher is `python <plugin folder>/bin/guidebook`.

## `.kickoff/guide.json` (written by kickoff)
| Field | Type | Meaning | Default |
|---|---|---|---|
| `contract` | number | schema version; guidebook warns and keeps going if it is higher than it understands | 1 |
| `enabled` | boolean | `false`: guidebook does nothing and exits 0 | true |
| `brand` | text | name in the guide header | folder name |
| `versions` | list | names (`layman`, `client`, `teammate`, `maintainer`, `quick-start`) or version objects | `["layman"]` |
| `output` | text | folder for the built guide, relative to the project | `docs/guide` |
| `publish` | text | `local` or `github-pages` (only prepares a folder, never pushes) | `local` |
| `hub` | text | folder of the main guide; empty means none (used by the hub phases, ignored today) | empty |

## `.guidebook/guide.json` (guidebook's own, optional)
Same fields as above plus:
| Field | Meaning |
|---|---|
| `status_map` | maps the project's own status words onto the five (`{"DONE": "PASSED"}`); targets must be PASSED, FAILED, DOUBTFUL, UNTESTED or UNKNOWN; no new colours |

A version object has: `name`, `audience`, `depth` (`one-page`, `standard`, `full`), `scope` (folder prefixes), `reader`, `tone`, `skip`.

Merge rule: a non-empty field in `.kickoff/guide.json` wins; anything it does not set comes from `.guidebook/guide.json`; `status_map` is read only from `.guidebook/guide.json`. `.guidebook/ignore` lists extra paths to skip.

## What kickoff calls
| When | Command | Notes |
|---|---|---|
| first setup | `guidebook init . --dry-run` then, after the user approves, `guidebook init . --versions <names> --yes` | init proposes and writes nothing without `--yes` |
| `/wrapup` | `guidebook update .` | add `--no-model` for zero model calls; a failure is reported and never fails the wrap-up |
| `/doctor` | check that `<output>/guide.manifest.json` exists | nothing else |
| health | `guidebook status .` | exit code 1 means stale, 0 means fresh; a disabled guide exits 0 |

Kickoff never renders HTML and never edits files under `docs/guide-src/`.

## Built guide: `<output>/guide.manifest.json`
```
{ "contract": 1, "brand": "...", "output": "docs/guide",
  "versions": [ { "name", "audience", "depth", "reader", "dir",
                  "pages": [ { "rel", "html", "title", "summary", "section" } ] } ] }
```
A page built from a `PROJECT_STATUS.md` section (How to run, Setup, Data, Troubleshooting) also has `"kind": "howto"` and `"howto_section"` (`how-to-run`, `setup`, `data` or `troubleshooting`). Other pages have neither key. `section` stays the folder name (`1-start`, `4-reference`). Each of those four pages is hashed from its own section text only, and the section's first word (CONFIRMED, GUESSED, UNKNOWN) sets its badge. A project without the heading gets no page.

A copy is kept in `.guidebook/manifest.json`. It has no timestamps; build times and the project commit are in `.guidebook/state.json`.

## Exit codes
`0` done or nothing to do; `1` status found something stale or `init` found nothing to read; `2` bad arguments or a missing guide for `serve`.

## Files guidebook owns
`.guidebook/` (config, ignore, facts, state, manifest, model cache), `docs/guide-src/<version>/` (pages; a page with `generated: true` is guidebook's until the user edits it), `<output>/` (built HTML). Pages without `generated: true` and files starting with `_` are the user's.
