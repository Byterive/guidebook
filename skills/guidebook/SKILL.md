---
name: guidebook
description: Use when the user asks for a guide, manual or plain-language explanation of a project, after a thread wrap-up, or when a guide may be out of date. Reads the project and writes versioned HTML guides; keeps them current.
---

# guidebook

Turns a project into plain-language guides (layman, client-or-investor, teammate, maintainer, quick-start, or custom) and refreshes only what changed.

## When to run what
| Situation | Run |
|---|---|
| User asks for a guide, a manual, "explain this project to X" and no `.guidebook/guide.json` exists | `/guidebook:guide init` (propose first, write after approval) |
| After a wrap-up, a big change to PROJECT_STATUS, DECISIONS or NEXT, or before sharing the guide | `/guidebook:guide status`, then `update` if it says stale |
| User wants to look at the guide | `/guidebook:guide serve` |
| Guide exists and the user only asks a question about the project | Do not run anything; answer from the project files |

## How to behave
- Facts come only from the project's files. Unknown stays "not known". Status words are PASSED, FAILED, DOUBTFUL, UNTESTED, UNKNOWN; projects with other words map them in `.guidebook/guide.json` `status_map`.
- Never edit generated pages (`generated: true`). Change the source files and run update. If the user edited a generated page, update writes `<page>.proposed.md` instead; show them the difference and let them merge.
- Default to no model calls when the user did not ask for them; say how many calls an update made.
- A failing guidebook call never fails a wrap-up: report the output and carry on.
- Never push or publish. Scrub warnings in `status` (emails, tokens, private paths in pages) must be fixed before the guide is shared.
- Details of the config files and the kickoff contract: `docs/kickoff-contract.md` in the plugin folder.
