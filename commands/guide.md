---
description: Build and refresh plain-language guides for this project (init, status, update, serve)
argument-hint: init | status | update | serve [options]
---

Run the guidebook command the user asked for: `$ARGUMENTS` (the first word is the subcommand).

Launcher: `python "${CLAUDE_PLUGIN_ROOT}/bin/guidebook" <subcommand> . <options>` (the `.` is the project folder; use another folder only if the user named one).

## init
1. Run `init .` with no `--yes`. It reads the project and PROPOSES versions with reasons, and writes nothing.
2. Show the user the proposal (versions, reasons, notes, file count). Ask which versions they want and whether the model may write the plain-words sections (default: no model). Use AskUserQuestion.
3. Only after they approve, run `init . --versions <names> --yes` (add `--model` only if they allowed it). `--dry-run` lists every file without writing.
4. Report the path of `docs/guide/index.html` and the status of the first build.

## status
Run `status .`. Say what is fresh or stale and why, in the user's words. Exit code 1 means something is stale; that is information, not an error. If stale, offer `/guidebook:guide update`.

## update
1. Run `update . --dry-run` first if more than a few pages would change, show the list, then run `update .` (add `--no-model` if the user wants zero model calls).
2. Report: pages written, proposals (pages the user edited; the new text is in `<page>.proposed.md`; never overwrite their page), model calls made, and whether the HTML was rebuilt.

## serve
Run `serve .` in the background. Tell the user the address (http://127.0.0.1:8765/). The "Check and update" button runs update without the model unless `--model` was passed. Stop it only when the user asks.

## Rules
- Never edit generated pages yourself; edit the project's source files, then run update.
- Never push or publish; GitHub Pages is the user's choice.
- If a command fails, show its real output and stop; do not retry with other flags.
