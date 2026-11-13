---
title: guidebook privacy policy
summary: What guidebook reads, writes and sends, how long data is kept, and how to contact us.
keywords: [guidebook, privacy, data, policy]
status: confirmed
updated: 2026-11-13
---

# guidebook privacy

This page says what guidebook does with your data. It applies to guidebook version 0.2.0 and later releases of that line, until a newer version of this file replaces it. Date: 2026-11-13.

## What it reads
The files in the project folder you point it at. It skips secrets, `.env` files, keys and git-ignored files. Before anything is stored or written, it scrubs the emails, tokens and absolute paths it recognises.

## What it writes and where
Only three places in your project: `.guidebook/` (including a cache of model answers in `.guidebook/cache`), `docs/guide-src/` and the built `docs/guide/`. It does not edit your existing files.

## What it sends and to whom
With `--no-model`, nothing is sent anywhere.

With Claude Code present, `guidebook explain` and the model steps of `pages` and `update` send text taken from your project, after the scrubbing above, to Claude through `claude -p`. That is your own Claude Code, so the text goes where Claude Code sends your prompts.

`guidebook serve` starts without the model, so its Check and update button sends nothing anywhere. If you start it with `--model`, the button, like `init --model`, sends scrubbed project text to Claude through `claude -p` for each changed page, up to 20 calls per press, and nothing else leaves your computer.

The `serve` command shows the guide on `http://127.0.0.1:8765`, which only your own computer can reach. guidebook has no other connection to a website or service.

## How long data is kept
The guide, its sources and the cache stay in your project folder until you delete them. guidebook keeps nothing anywhere else.

## Who it is for
We do not design guidebook for people under 18, and we do not knowingly collect data from them.

## Other software
guidebook runs inside Claude Code. Claude Code and the other tools it works with handle your data under their own terms. This page covers only guidebook.

## Contact
Use the contact details on [byterive.com](https://byterive.com). We do not publish an email address for privacy questions yet.

*Independent project by Byterive. Not affiliated with or endorsed by Anthropic.* · [byterive.com](https://byterive.com)
