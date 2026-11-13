# Style guide - a portable documentation-site look

Original work by Junaid Iqbal (Byterive), copied into this repo from the project where the first guidebook was built; no third-party code beyond public packages and Google Fonts. Everything needed to recreate one visual style in another project: colours, type, CSS, HTML templates and a Markdown-to-website builder. **This folder needs nothing from any other project.** Every link inside it points to a file inside it. Only public packages and Google Fonts are used from outside.

## What is inside

| Path | What it is |
|---|---|
| `components.md` | every component: class names, when to use it, a snippet |
| `tokens/` | colours, fonts, sizes as JSON and as CSS custom properties |
| `site/` | static site kit: `style.css`, `search.template.js`, `templates/*.html`, `build_site.py`, `content-rules.md` |

## Reuse in 2 steps

1. Copy this whole folder into the new project (any location).
2. Choose the brand name, an optional accent colour and the pages, build the site, then check the result at phone width and in dark mode.

## What to replace

The brand name (a build argument), the accent colour if wanted (`tokens/design-tokens.json` and the `--acc` variable in `site/style.css`), your own pages, the status words if your project uses others (`--status-words`, and the keys in `STATUS_COLOR`). Keep class names and spacing.

## Requirements

Python 3.10 or newer. Package: `markdown` (site builder). Internet access only for the Google Fonts file (Archivo); offline the system sans-serif is used.
